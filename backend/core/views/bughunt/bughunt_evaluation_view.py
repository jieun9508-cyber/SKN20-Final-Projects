"""BugHunt final evaluation view (step interview results aggregation)."""

import json
import re

import openai
from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle  # [수정일: 2026-03-06] AI throttle
from rest_framework.views import APIView
from core.views.user_view import CsrfExemptSessionAuthentication  # [수정일: 2026-03-06] CSRF 우회 세션 인증

class BugHuntEvaluationView(APIView):
    """
    [수정일: 2026-02-11]
    Step별 딥다이브 면접 결과를 종합하여 최종 평가를 생성합니다.
    면접 점수를 재채점하지 않고, 기존 면접 결과를 종합·분석하여
    전체적인 디버깅 역량 요약과 학습 방향을 제시합니다.
    """
    # [수정일: 2026-03-06] 세션 쿠키로 인증하되 CSRF 토큰은 요구하지 않음
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]
    # [수정일: 2026-03-06] AI API 요청 제한 (OpenAI 비용 보호, 10회/분)
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'ai'

    EVAL_MODEL = "gpt-5-mini"

    def post(self, request):
        data = request.data
        mission_title = data.get('missionTitle', 'Unknown Mission')
        steps = data.get('steps', [])
        explanations = data.get('explanations', {})
        user_codes = data.get('userCodes', {})
        performance = data.get('performance', {})
        interview_results = data.get('interviewResults', {})

        if not steps:
            return Response({"error": "Steps data is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            api_key = settings.OPENAI_API_KEY
            if not api_key:
                return Response({"error": "API Key not configured"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            client = openai.OpenAI(api_key=api_key)

            # Step별 컨텍스트 구성
            step_context_parts = []
            for idx, s in enumerate(steps):
                step_num = idx + 1
                step_num_str = str(step_num)
                original_code = s.get('buggy_code', '')
                modified_code = user_codes.get(step_num_str, '')
                true_cause = s.get('error_info', {}).get('description', '정보 없음')
                correct_logic = s.get('error_info', {}).get('suggestion', '정보 없음')

                # 면접 결과가 있는 경우
                iv = interview_results.get(step_num_str, {})
                iv_score = iv.get('score', '없음')
                iv_level = iv.get('understanding_level', '없음')
                iv_concepts = ', '.join(iv.get('matched_concepts', [])) or '없음'
                iv_weak = iv.get('weak_point', '없음') or '없음'

                step_context_parts.append(f"""### Step {step_num}: {s.get('title', '')}
- 버그 원인(정답): {true_cause}
- 권장 해결책(정답): {correct_logic}
- 원본 코드 → 사용자 수정 코드: (코드 수정 완료됨)
- [면접 결과] 점수: {iv_score}/100 | 이해 수준: {iv_level}
- [면접 결과] 파악한 개념: {iv_concepts}
- [면접 결과] 보완 필요: {iv_weak}""")

            step_context_str = '\n\n'.join(step_context_parts)

            # 면접 점수 통계
            iv_scores = []
            for idx in range(len(steps)):
                iv = interview_results.get(str(idx + 1), {})
                if isinstance(iv.get('score'), (int, float)):
                    iv_scores.append(iv['score'])
            avg_score = round(sum(iv_scores) / len(iv_scores)) if iv_scores else 50

            system_message = """너는 주니어 AI 엔지니어의 디버깅 역량을 종합 평가하는 시니어 멘토이다.

[역할]
- 각 Step별 딥다이브 면접 결과가 이미 채점되어 있다.
- 너는 점수를 재채점하지 않는다.
- 면접 결과를 종합 분석하여 전체적인 디버깅 역량 평가와 학습 방향을 제시한다.
- 교육적이고 격려하는 톤을 유지하되, 부족한 점은 명확히 짚어준다.
- 존댓말을 사용한다."""

            prompt = f"""## 종합 평가 대상

미션: {mission_title}

[풀이 성과]
- 코드 제출 실패: {performance.get('codeSubmitFailCount', 0)}회
- 힌트 사용: {performance.get('hintCount', 0)}회
- 총 소요 시간: {performance.get('totalDebugTime', 0)}초

[Step별 면접 결과]
{step_context_str}

[면접 점수 평균]: {avg_score}/100

---

## 종합 평가 지침

1. **Step별 면접 점수를 그대로 인정**한다. 재채점하지 않는다.
2. **thinking_score**는 면접 점수 평균({avg_score})을 기본으로 하되, 아래 보정을 적용한다:
   - 힌트 0회 + 제출 실패 0회 → +3점 보너스
   - 힌트 3회 이상 → -2점
   - 전 Step 이해 수준이 모두 Deep 이상 → +5점 보너스
   - 보정 후 0~100 범위로 클램프
3. **code_risk**: 이해 수준이 낮을수록 위험도가 높다.
   - Deep → 10, Conceptual → 25, Surface → 50, None/Unknown → 70
   - 여러 Step의 평균으로 계산
4. **thinking_pass**: thinking_score >= 60이면 true
5. **step_feedbacks**: 각 Step별로 면접에서 드러난 강점과 약점을 1~2문장으로 요약
6. **총평**: 전체 디버깅 역량을 3~5문장으로 종합 분석. 잘한 점, 부족한 점, 구체적 학습 방향을 포함

---

## 출력 형식

**반드시 아래 JSON만 출력하라. 다른 텍스트 금지.**

{{
  "thinking_pass": true,
  "code_risk": 25,
  "thinking_score": {avg_score},
  "총평": "종합 평가 내용을 존댓말로 작성",
  "step_feedbacks": [
    {{"step": 1, "feedback": "Step 1 면접 결과 기반 요약 피드백", "step_score": 0}},
    {{"step": 2, "feedback": "Step 2 면접 결과 기반 요약 피드백", "step_score": 0}},
    {{"step": 3, "feedback": "Step 3 면접 결과 기반 요약 피드백", "step_score": 0}}
  ]
}}

**주의**:
- step_feedbacks의 step_score는 해당 Step의 면접 점수를 그대로 사용
- step_feedbacks 개수는 실제 Step 수({len(steps)}개)와 일치
- thinking_score는 보정 적용된 최종 값
"""

            response = client.chat.completions.create(
                model=self.EVAL_MODEL,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=2000
            )

            response_text = response.choices[0].message.content.strip()
            print(f"[BugHuntEval] Raw response: {response_text[:500]}")

            # JSON 파싱
            json_match = None
            match = re.search(r'\{[\s\S]*\}', response_text)
            if match:
                json_match = match.group()

            if json_match:
                result = json.loads(json_match)
                print(f"[BugHuntEval] Parsed result: thinking_score={result.get('thinking_score')}")
                return Response({
                    "thinking_pass": bool(result.get('thinking_pass', False)),
                    "code_risk": int(result.get('code_risk', 50)),
                    "thinking_score": int(result.get('thinking_score', avg_score)),
                    "총평": result.get('총평', result.get('summary', '평가를 완료했습니다.')),
                    "step_feedbacks": result.get('step_feedbacks', [])
                }, status=status.HTTP_200_OK)
            else:
                print(f"[BugHuntEval] JSON parse failed, raw: {response_text}")
                return Response({"error": "Invalid JSON format from AI"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            print(f"[BugHuntEval] Exception: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

