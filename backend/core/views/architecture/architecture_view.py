# [작성일: 2026-02-20] Architecture Practice 평가 및 질문 생성 View
import openai
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle  # [수정일: 2026-03-06] AI throttle
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from core.views.user_view import CsrfExemptSessionAuthentication  # [수정일: 2026-03-06] CSRF 우회 세션 인증
import json
import re
import traceback
import sys

# 6대 기둥 정의 (Well-Architected Framework)
PILLAR_DATA = {
    'reliability': {
        'name': '신뢰성 (Reliability)',
        'keywords': ['장애', '다운', 'spof', '중단', '복구', 'failover', 'redundancy', '가용성', 'availability']
    },
    'performance_optimization': {
        'name': '성능 최적화 (Performance Optimization)',
        'keywords': ['트래픽', '급증', '동시', 'latency', '지연', '느림', '성능', 'throughput', '처리량', 'cache', 'cdn']
    },
    'operational_excellence': {
        'name': '운영 우수성 (Operational Excellence)',
        'keywords': ['모니터링', '로그', 'alert', '경보', '운영', 'cicd', '배포', 'deploy', 'debug']
    },
    'cost_optimization': {
        'name': '비용 최적화 (Cost Optimization)',
        'keywords': ['비용', '예산', 'cost', '저렴', '절감', 'spot', 'reserved', '요금']
    },
    'security': {
        'name': '보안 (Security)',
        'keywords': ['보안', '유출', '해킹', '암호화', 'encryption', 'iam', '권한', 'vpc', 'firewall', 'waf']
    },
    'sustainability': {
        'name': '지속가능성 (Sustainability)',
        'keywords': ['환경', '효율', '장기', 'green', 'efficiency', '지속']
    }
}

# 루브릭 등급 정의 (0점부터 시작)
RUBRIC_GRADES = {
    'excellent': {
        'range': [90, 100],
        'label': '우수 (Excellent)',
        'emoji': '✨',
        'criteria': [
            '✅ 구체적인 기술/패턴 명시 (기술명, 설정값 포함)',
            '✅ 트레이드오프 깊이 있게 설명',
            '✅ 실무 기반 또는 사례 기반 답변',
            '✅ 제약조건 완벽하게 반영',
            '✅ 아키텍처 설계와 100% 일관성'
        ]
    },
    'good': {
        'range': [72, 89], # 75 -> 72
        'label': '양호 (Good)',
        'emoji': '✓',
        'criteria': [
            '✅ 핵심 개념 정확',
            '✅ 구체적 기술 1-2개 언급',
            '✅ 트레이드오프 기본 수준 언급',
            '⚠️ 일부 제약조건 반영',
            '⚠️ 대부분 아키텍처와 일관성'
        ]
    },
    'fair': {
        'range': [55, 71], # 60 -> 55
        'label': '보통 (Fair)',
        'emoji': '⚠️',
        'criteria': [
            '⚠️ 개념은 맞으나 구체성 부족',
            '⚠️ 일반적인 답변만 제공',
            '❌ 트레이드오프 미언급',
            '❌ 제약조건 일부만 반영',
            '❌ 아키텍처와 부분적 불일치'
        ]
    },
    'poor': {
        'range': [40, 59],
        'label': '미흡 (Poor)',
        'emoji': '❌',
        'criteria': [
            '❌ 개념 이해는 있으나 부정확',
            '❌ 구체적 기술 없음',
            '❌ 문제 상황 충분히 고려 안 함',
            '❌ 제약조건 무시',
            '❌ 아키텍처와 주요 불일치'
        ]
    },
    'failing': {
        'range': [0, 39],
        'label': '부족 (Failing)',
        'emoji': '✗',
        'criteria': [
            '❌ 답변 없음 또는 완전 오류',
            '❌ 문제 상황 이해 부족',
            '❌ 기술 기초 부족',
            '❌ 설계와 모순',
            '❌ 실무 불가능한 설계'
        ]
    }
}

def format_axis_weights(axis_weights):
    """가중치 정보 포맷팅"""
    if not axis_weights or len(axis_weights) == 0:
        return '(가중치 정보 없음 - 균등 평가)'

    sorted_weights = sorted(
        [(k, v.get('weight', 0), v.get('reason', '')) for k, v in axis_weights.items()],
        key=lambda x: x[1],
        reverse=True
    )

    formatted = []
    for idx, (key, weight, reason) in enumerate(sorted_weights, 1):
        pillar = PILLAR_DATA.get(key, {})
        formatted.append(f"{idx}. {pillar.get('name', key)} [가중치: {weight}%]\n   {reason or ''}")

    return '\n\n'.join(formatted)


def format_rubric_for_prompt():
    """루브릭 등급 포맷팅"""
    formatted = []
    for key, rubric in RUBRIC_GRADES.items():
        criteria_text = '\n   '.join(rubric.get('criteria', []))
        formatted.append(
            f"{rubric['emoji']} **{rubric['label']}** ({rubric['range'][0]}-{rubric['range'][1]}점)\n"
            f"   {criteria_text}"
        )
    return '\n\n'.join(formatted)


def format_axis_specific_rubrics():
    """축별 루브릭 포맷팅"""
    axis_rubrics = {
        'performance_optimization': {
            'excellent': 'latency 목표값, 캐싱 전략, 인덱싱, 샤딩 등 구체적 최적화 방안과 트레이드오프 설명',
            'good': '성능 최적화 고려, 캐시/인덱싱 등 1-2개 기술 언급',
            'fair': '성능 최적화 인식 있으나 구체성 부족',
            'poor': '성능 최적화 방안 불충분',
            'failing': '성능 최적화 무시'
        },
        'reliability': {
            'excellent': '데이터 무결성, 트랜잭션, 멱등성, RTO/RPO, Failover, 모니터링 전략 상세',
            'good': '신뢰성 방안 기본 수준 설명 (복제, 백업 등)',
            'fair': '신뢰성 고려 있으나 구체성 부족',
            'poor': '신뢰성 방안 미흡',
            'failing': '신뢰성 무시'
        },
        'operational_excellence': {
            'excellent': '자동화, 모니터링, 로깅, 배포 전략, IaC, 장애 대응 프로세스 상세',
            'good': '운영 측면 고려, 모니터링/로깅 등 기본 방안 언급',
            'fair': '운영 고려 있으나 구체성 부족',
            'poor': '운영 방안 미흡',
            'failing': '운영 측면 무시'
        },
        'cost_optimization': {
            'excellent': '리소스 최적화, 예약 인스턴스, 스팟 인스턴스, 스토리지 계층화, 비용 모니터링 상세',
            'good': '비용 고려, 리소스 효율화 등 1-2개 방안 언급',
            'fair': '비용 인식 있으나 구체성 부족',
            'poor': '비용 최적화 방안 미흡',
            'failing': '비용 측면 무시'
        },
        'security': {
            'excellent': '암호화(전송/저장), IAM, VPC, 최소 권한, 감사 로깅, 규정 준수 등 다층 보안 전략',
            'good': '보안 고려, 1-2개 기술 (암호화, IAM 등) 언급',
            'fair': '보안 인식 있으나 미흡',
            'poor': '보안 방안 불충분',
            'failing': '보안 무시'
        },
        'sustainability': {
            'excellent': '에너지 효율, 리소스 활용 최적화, 탄소 배출 최소화, 지역 선택 전략 상세',
            'good': '지속가능성 고려, 리소스 효율화 등 기본 방안 언급',
            'fair': '지속가능성 인식 있으나 구체성 부족',
            'poor': '지속가능성 방안 미흡',
            'failing': '지속가능성 무시'
        }
    }

    formatted = []
    for axis, rubric in axis_rubrics.items():
        pillar = PILLAR_DATA.get(axis, {})
        formatted.append(
            f"### {pillar.get('name', axis)}\n"
            f"- 우수: {rubric['excellent']}\n"
            f"- 양호: {rubric['good']}\n"
            f"- 보통: {rubric['fair']}\n"
            f"- 미흡: {rubric['poor']}\n"
            f"- 부족: {rubric['failing']}"
        )
    return '\n\n'.join(formatted)


def generate_rubric_prompt(problem, architecture_context, user_explanation, deep_dive_qna):
    """루브릭 기반 평가 프롬프트 생성"""
    qna_array = deep_dive_qna if isinstance(deep_dive_qna, list) else []

    # Q&A 텍스트 생성
    qna_text = ''
    for idx, item in enumerate(qna_array):
        if item.get('answer'):
            qna_text += f"""
### 질문 {idx + 1} [{item.get('category', '기타')}]
**질문**: {item.get('question', '')}
**의도**: {item.get('gap', '설계 의도 확인')}
**사용자 답변**: {item.get('answer', '')}
"""

    # 가중치 정보
    weight_info = format_axis_weights(problem.get('axis_weights') if isinstance(problem, dict) else {})

    # 루브릭 포맷팅
    rubric_format = format_rubric_for_prompt()
    axis_rubric_format = format_axis_specific_rubrics()

    # System Message 분리
    system_message = """당신은 **시니어 클라우드 솔루션 아키텍트**입니다.
지원자의 시스템 아키텍처 설계와 질문 답변을 루브릭 기준으로 평가합니다."""

    # 프롬프트 작성
    prompt = f"""## 📋 문제 정보

### 시나리오
{problem.get('scenario', '시스템 아키텍처 설계') if isinstance(problem, dict) else '시스템 아키텍처 설계'}

### 미션
{chr(10).join([f"{i+1}. {m}" for i, m in enumerate(problem.get('missions', []) if isinstance(problem, dict) else [])] or ['없음'])}

### 제약조건
{chr(10).join([f"{i+1}. {c}" for i, c in enumerate(problem.get('constraints', []) if isinstance(problem, dict) else [])] or ['없음'])}

---

## 🔥 평가 가중치 (문제 특성)

이 문제는 다음 측면들을 중시합니다:

{weight_info}

---

## 🏗️ 지원자의 아키텍처

{architecture_context or '(아키텍처 정보 없음)'}

---

## 💬 지원자의 설계 설명

"{user_explanation or '(설명 없음)'}"

---

## 📝 심화 질문 및 답변

{qna_text or '(질문/답변 없음)'}

---

## ⭐ 루브릭 기준 (0점부터 시작)

### 공통 기준

{rubric_format}

### 축별 맞춤형 기준

{axis_rubric_format}

---

## ⚠️ 평가 규칙

### 1. 점수 산정 기준 (중요!)
- **0점부터 시작** - 답변이 없거나 완전 오류면 0점
- **각 기둥별로 정확히 1개 점수만 부여** (0-100)
- **루브릭 등급에 따라 점수 부여**:
  - Excellent: 90-100점
  - Good: 72-89점 (수정: 75 -> 72)
  - Fair: 55-71점 (수정: 60 -> 55)
  - Poor: 40-54점
  - Failing: 0-39점

### 2. 평가 방법
1. 사용자의 아키텍처 설계를 확인
2. 사용자 설명과 Q&A 답변을 검토
3. 각 기둥별로 위 루브릭 기준을 적용
4. 0-100 범위에서 점수 부여 (정수)
5. **각 기둥마다 정확히 5-7문장의 피드백 작성**
6. **반드시 정확히 6개 기둥 평가**

### 3. 구체적 평가 항목
각 기둥마다:
- ✅ 아키텍처에서 이 기둥을 명시적으로 다뤘는가?
- ✅ 사용자 설명/답변에서 구체적으로 언급했는가?
- ✅ 실제 기술 이름/설정값을 제시했는가?
- ✅ 트레이드오프를 이해하고 있는가?
- ✅ 제약조건을 반영했는가?

### 4. 최종 점수 계산
```
최종 점수 = Σ(각 기둥 점수 × 해당 기둥 가중치%) / 100
```

---

## 출력 형식 (JSON만, 반드시 정확히 6개 기둥)

반드시 다음 JSON 형식으로 응답하세요:

```json
{{
  "evaluations": [
    {{
      "axis": "performance_optimization",
      "axisName": "성능 최적화",
      "weight": 30,
      "grade": "good",
      "score": 82,
      "feedback": "구체적인 피드백 (5-7문장)",
      "expectedAnswer": "이 기둥에 대해 기대했던 모범 답변/설계 방향"
    }},
    ...정확히 6개...
  ],
  "referenceAnswers": [
    {{
      "questionIndex": 0,
      "question": "원본 질문",
      "expectedAnswer": "기대했던 모범 답변 (구체적 기술/수치 포함)"
    }},
    {{
      "questionIndex": 1,
      "question": "원본 질문",
      "expectedAnswer": "기대했던 모범 답변"
    }},
    ...질문 개수만큼...
  ],
  "overallScore": 76,
  "overallGrade": "good",
  "summary": "전반적인 평가 요약",
  "strengths": ["강점 1", "강점 2"],
  "weaknesses": ["약점 1"],
  "recommendations": ["추천사항 1"]
}}
```

**주의사항**:
- 반드시 정확히 6개 기둥 + 각 기둥별 expectedAnswer
- 각 기둥 점수는 0-100 정수
- referenceAnswers는 사용자가 답변한 질문 개수만큼 포함
- 각 expectedAnswer는 구체적인 기술명/수치를 포함해야 함
- 반드시 JSON 형식만 출력"""

    return system_message, prompt


def select_relevant_pillars(scenario, missions, constraints):
    """시나리오 기반 관련 Pillar 선별"""
    full_text = ' '.join([
        scenario or '',
        *missions,
        *constraints
    ]).lower()

    scores = {}
    for key, pillar in PILLAR_DATA.items():
        scores[key] = sum(1 for keyword in pillar['keywords'] if keyword in full_text)

    sorted_pillars = sorted(
        [(k, v) for k, v in scores.items()],
        key=lambda x: x[1],
        reverse=True
    )[:3]

    # 최소 2개는 보장
    if len(sorted_pillars) < 2:
        for key in ['reliability', 'performance_optimization', 'security']:
            if not any(k == key for k, _ in sorted_pillars):
                sorted_pillars.append((key, 0))
                if len(sorted_pillars) >= 2:
                    break

    return [
        {'key': k, 'name': PILLAR_DATA[k]['name']}
        for k, _ in sorted_pillars[:3]
    ]


def categorize_components(components):
    """컴포넌트를 역할별로 분류"""
    type_map = {
        'elb': 'entry', 'alb': 'entry', 'nlb': 'entry',
        'cloudfront': 'entry', 'apigateway': 'entry', 'route53': 'entry',
        'ec2': 'compute', 'lambda': 'compute', 'ecs': 'compute',
        'eks': 'compute', 'fargate': 'compute', 'beanstalk': 'compute',
        'rds': 'storage', 's3': 'storage', 'dynamodb': 'storage',
        'elasticache': 'storage', 'redis': 'storage', 'aurora': 'storage', 'ebs': 'storage',
        'waf': 'security', 'shield': 'security', 'securitygroup': 'security',
        'iam': 'security', 'cognito': 'security',
        'vpc': 'network', 'subnet': 'network', 'natgateway': 'network',
        'internetgateway': 'network', 'transitgateway': 'network'
    }

    categories = {cat: [] for cat in set(type_map.values())}
    categories['other'] = []

    for comp in components:
        comp_type = (comp.get('type') or '').lower()
        comp_text = (comp.get('text') or '').lower()

        category = 'other'
        for keyword, cat in type_map.items():
            if keyword in comp_type or keyword in comp_text:
                category = cat
                break

        categories[category].append(comp)

    return categories


def analyze_connections(connections, components):
    """연결 관계 분석"""
    result = []
    for conn in connections:
        from_comp = next((c for c in components if c.get('id') == conn.get('from')), None)
        to_comp = next((c for c in components if c.get('id') == conn.get('to')), None)

        if not from_comp or not to_comp:
            continue

        flow_type = 'Data Flow'
        from_type = (from_comp.get('type') or '').lower()
        to_type = (to_comp.get('type') or '').lower()

        if 'elb' in from_type or 'alb' in from_type:
            flow_type = 'Traffic Distribution'
        elif 'rds' in to_type or 'dynamodb' in to_type:
            flow_type = 'Database Query'
        elif 'ec2' in from_type and 's3' in to_type:
            flow_type = 'File Storage'
        elif 'cache' in to_type or 'redis' in to_type:
            flow_type = 'Cache Access'

        result.append(f"{from_comp.get('text')} → {to_comp.get('text')} ({flow_type})")

    return result


@method_decorator(csrf_exempt, name='dispatch')
class ArchitectureEvaluationView(APIView):
    """
    [수정일: 2026-02-20]
    시스템 아키텍처 루브릭 기반 평가

    [변경사항]
    - 프롬프트는 백엔드에서 생성 (프론트엔드는 데이터만 전송)
    - 백엔드: 프롬프트 생성 + LLM 호출 담당
    """
    # [수정일: 2026-03-06] 세션 쿠키로 인증하되 CSRF 토큰은 요구하지 않음
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]
    # [수정일: 2026-03-06] AI API 요청 제한 (OpenAI 비용 보호, 10회/분)
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'ai'

    def post(self, request):
        data = request.data
        problem = data.get('problem', {})
        architecture_context = data.get('architectureContext', '')
        user_explanation = data.get('userExplanation', '')
        deep_dive_qna = data.get('deepDiveQnA', [])

        print(f"[DEBUG] Architecture Evaluation Start", flush=True)

        try:
            api_key = settings.OPENAI_API_KEY
            if not api_key:
                return Response(
                    {"error": "OpenAI API Key is missing"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # Step 1: 백엔드에서 프롬프트 생성
            system_message, prompt = generate_rubric_prompt(
                problem,
                architecture_context,
                user_explanation,
                deep_dive_qna
            )

            client = openai.OpenAI(api_key=api_key)

            # Step 2: LLM 호출 (gpt-4o-mini 사용)
            print(f"[DEBUG] Calling AI for Evaluation with gpt-4o-mini...", flush=True)
            print(f"[DEBUG] Prompt length: {len(prompt)}, System prompt length: {len(system_message)}", flush=True)

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_completion_tokens=4500
            )

            print(f"[DEBUG] Response received: {response}", flush=True)
            content = response.choices[0].message.content
            if content:
                content = content.strip()
            print(f"[DEBUG] Raw AI Response: {content[:500] if content else 'EMPTY'}", flush=True)
            print(f"[ArchEval] Raw response: {content[:500] if content else 'EMPTY'}", flush=True)

            # Step 3: JSON 파싱 (BugHuntEval 패턴 적용)
            json_match = None
            match = re.search(r'\{[\s\S]*\}', content)
            if match:
                json_match = match.group()

            if json_match:
                result = json.loads(json_match)
                print(f"[ArchEval] Parsed result: overallScore={result.get('overallScore')}", flush=True)

                # 전체 점수 계산
                evaluations = result.get('evaluations', [])
                weighted_sum = 0
                total_weight = 0

                for ev in evaluations:
                    weight = ev.get('weight', 0)
                    score = ev.get('score', 0)
                    weighted_sum += (score * weight / 100)
                    total_weight += weight

                overall_score = int(round(weighted_sum))

                return Response({
                    "evaluations": evaluations,
                    "referenceAnswers": result.get('referenceAnswers', []),
                    "overallScore": overall_score,
                    "overallGrade": result.get('overallGrade', 'fair'),
                    "summary": result.get('summary', '평가 완료'),
                    "strengths": result.get('strengths', []),
                    "weaknesses": result.get('weaknesses', []),
                    "recommendations": result.get('recommendations', [])
                }, status=status.HTTP_200_OK)
            else:
                print(f"[ArchEval] JSON parse failed, raw: {content}", flush=True)
                return Response(
                    {"error": "Invalid JSON format from AI"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        except Exception as e:
            tb = traceback.format_exc()
            print(f"[CRITICAL] Architecture Evaluation Error: {e}", flush=True)
            print(f"[CRITICAL] Traceback:\n{tb}", file=sys.stderr, flush=True)
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@method_decorator(csrf_exempt, name='dispatch')
class ArchitectureQuestionGeneratorView(APIView):
    """
    [작성일: 2026-02-20]
    심화 질문 생성
    """
    # [수정일: 2026-03-06] 세션 쿠키로 인증하되 CSRF 토큰은 요구하지 않음
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]
    # [수정일: 2026-03-06] AI API 요청 제한 (OpenAI 비용 보호, 10회/분)
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'ai'

    def post(self, request):
        data = request.data
        problem = data.get('problem', {})
        components = data.get('components', [])
        connections = data.get('connections', [])
        mermaid_code = data.get('mermaidCode', '')
        user_explanation = data.get('userExplanation', '')

        print(f"[DEBUG] Question Generation Start", flush=True)

        try:
            api_key = settings.OPENAI_API_KEY
            if not api_key:
                return Response(
                    {"error": "OpenAI API Key is missing"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            client = openai.OpenAI(api_key=api_key)
            print(f"[DEBUG] OpenAI Client Initialized", flush=True)

            # 컴포넌트 분류
            categorized = categorize_components(components)

            # 연결 분석
            meaningful_connections = analyze_connections(connections, components)

            # 관련 Pillar 선별
            scenario = problem.get('scenario', '')
            missions = problem.get('missions', [])
            constraints = problem.get('constraints', [])
            relevant_pillars = select_relevant_pillars(scenario, missions, constraints)

            # 컴포넌트 텍스트 생성
            category_texts = []
            if categorized['entry']:
                category_texts.append(
                    f"**🚪 진입점 (Entry Points)**\n" +
                    '\n'.join([f"- {c.get('text')} ({c.get('type')})" for c in categorized['entry']])
                )
            if categorized['compute']:
                category_texts.append(
                    f"**⚙️ 컴퓨팅 계층 (Compute)**\n" +
                    '\n'.join([f"- {c.get('text')} ({c.get('type')})" for c in categorized['compute']])
                )
            if categorized['storage']:
                category_texts.append(
                    f"**💾 저장소 계층 (Storage)**\n" +
                    '\n'.join([f"- {c.get('text')} ({c.get('type')})" for c in categorized['storage']])
                )
            if categorized['security']:
                category_texts.append(
                    f"**🔒 보안 계층 (Security)**\n" +
                    '\n'.join([f"- {c.get('text')} ({c.get('type')})" for c in categorized['security']])
                )

            architecture_overview = '\n\n'.join(category_texts)

            # System Message 분리
            system_message = """당신은 **시니어 클라우드 솔루션 아키텍트**입니다.

## 🎯 당신의 임무
1. 지원자의 아키텍처를 **비판적으로 분석** (안티패턴 체크)
2. 부족한 영역 3가지에 대해 **날카로운 질문** 생성"""

            # 프롬프트 생성
            prompt = f"""## 📋 문제 상황

### 시나리오
{scenario or '시스템 아키텍처 설계'}

### 미션
{chr(10).join([f"{i+1}. {m}" for i, m in enumerate(missions)])}

### 제약조건
{chr(10).join([f"{i+1}. {c}" for i, c in enumerate(constraints)])}

---

## 🏗️ 지원자의 아키텍처

### 역할별 컴포넌트 분류
{architecture_overview or '(컴포넌트 없음)'}

### 데이터 흐름
{chr(10).join(meaningful_connections) if meaningful_connections else '(연결 없음)'}

---

## 💬 지원자의 설명
"{user_explanation or '(설명 없음)'}"

---

## 🔍 안티패턴 체크리스트 (Critical)

### ⚠️ 신뢰성 안티패턴
- [ ] **SPOF (Single Point of Failure)**: 단일 컴포넌트 장애 시 전체 서비스 중단?
- [ ] **No Redundancy**: 중요 컴포넌트의 복제본이 없음?
- [ ] **단일 AZ 배치**: 모든 리소스가 1개 가용영역에만?

### ⚡ 성능 안티패턴
- [ ] **단일 경로 병목**: 모든 트래픽이 1개 경로로만 흐름?
- [ ] **Auto Scaling 부재**: 트래픽 급증 시 수동 증설만 가능?
- [ ] **캐싱 전략 없음**: DB에 직접 쿼리만 하는 구조?

### 🔒 보안 안티패턴
- [ ] **Public DB**: 데이터베이스가 Public Subnet에 노출?
- [ ] **Network Segmentation 부족**: VPC/Subnet 분리 없음?

---

## 📝 질문 생성 규칙

질문은 다음을 만족해야 합니다:
1. **안티패턴 우선**: 체크리스트에서 발견된 문제를 먼저 질문
2. **상황 기반**: "~한 상황이 발생하면" 형태 (Failure Scenario)
3. **구체적**: 배치된 컴포넌트/상황을 언급
4. **개방형**: 설계 의도/대응 방안을 설명하게 유도

---

## 출력 형식 (JSON만)

```json
{{
  "questions": [
    {{
      "category": "신뢰성",
      "gap": "부족한 부분 설명",
      "scenario": "구체적인 장애 시나리오",
      "question": "실제 질문 (배치된 컴포넌트 언급)"
    }},
    {{
      "category": "성능",
      "gap": "부족한 부분 설명",
      "scenario": "구체적인 장애 시나리오",
      "question": "실제 질문"
    }},
    {{
      "category": "운영",
      "gap": "부족한 부분 설명",
      "scenario": "구체적인 장애 시나리오",
      "question": "실제 질문"
    }}
  ]
}}
```"""

            print(f"[DEBUG] Calling AI for Question Generation with gpt-5-mini...", flush=True)
            print(f"[DEBUG] Prompt length: {len(prompt)}, System prompt length: {len(system_message)}", flush=True)

            response = client.chat.completions.create(
                model="gpt-5-mini",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=4000
            )

            print(f"[DEBUG] Response received: {response}", flush=True)
            content = response.choices[0].message.content
            if content:
                content = content.strip()
            print(f"[DEBUG] Raw AI Response: {content[:500] if content else 'EMPTY'}", flush=True)
            print(f"[ArchQuestion] Raw response: {content[:500] if content else 'EMPTY'}", flush=True)

            # JSON 파싱 (BugHuntEval 패턴 적용)
            json_match = None
            match = re.search(r'\{[\s\S]*\}', content)
            if match:
                json_match = match.group()

            if json_match:
                result = json.loads(json_match)
                print(f"[ArchQuestion] Parsed result: questions_count={len(result.get('questions', []))}", flush=True)

                return Response({
                    "questions": result.get('questions', []),
                    "selectedPillars": [p['name'] for p in relevant_pillars],
                    "metadata": {
                        "componentCount": len(components),
                        "connectionCount": len(connections)
                    }
                }, status=status.HTTP_200_OK)
            else:
                print(f"[ArchQuestion] JSON parse failed, raw: {content}", flush=True)
                return Response(
                    {"error": "Invalid JSON format from AI"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        except Exception as e:
            tb = traceback.format_exc()
            print(f"[CRITICAL] Question Generation Error: {e}", flush=True)
            print(f"[CRITICAL] Traceback:\n{tb}", file=sys.stderr, flush=True)
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
