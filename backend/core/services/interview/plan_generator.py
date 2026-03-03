"""
plan_generator.py -- 면접 계획 생성기

수정일: 2026-03-01
설명: 채용공고 + 사용자 취약점 + 실제 면접 기출 질문 → interview_plan 생성.
      technical_depth 슬롯의 evidence는 채용공고 기술 스택 기반으로 동적 생성.

[2026-03-01 변경사항]
  - question_bank_service 연동: DB의 실제 면접 기출 질문을 프롬프트에 주입하여
    LLM이 허구의 토픽 대신 실제 데이터 기반으로 면접 계획을 수립하도록 개선.
  - _build_plan_prompt() 중복 코드 정리 (채용공고 파싱 블록 1회로 통합)
"""
import json
import openai
from django.conf import settings

# job_role 코드 → 프롬프트용 라벨 매핑 (common_data.json JOB_ROLE과 동기화)
JOB_ROLE_LABELS = {
    "frontend": "프론트엔드 개발자",
    "backend": "백엔드 개발자",
    "server": "서버 개발자",
    "fullstack": "풀스택 개발자",
    "devops": "DevOps / 시스템 관리자",
    "ai": "AI / ML 엔지니어",
    "data_scientist": "데이터 사이언티스트",
    "mlops": "MLOps 엔지니어",
    "mobile": "모바일 앱 개발자",
    "data": "데이터 엔지니어",
    "security": "보안 엔지니어",
    "etc": "기타",
}

DEFAULT_POSITION = "AI / 소프트웨어 엔지니어"


def _resolve_position(user_job_roles: list) -> str:
    """유저의 job_role 코드 리스트 → 프롬프트용 직무 문자열 변환"""
    if not user_job_roles:
        return DEFAULT_POSITION
    labels = [JOB_ROLE_LABELS.get(r, r) for r in user_job_roles if r != "etc"]
    return " / ".join(labels) if labels else DEFAULT_POSITION


def generate_plan(job_posting, user_weakness: dict, user_job_roles: list = None) -> dict:
    """
    채용공고 + 취약점 + DB 기출 질문 → 면접 슬롯 순서와 각 슬롯의 설정 생성.

    Args:
        job_posting: SavedJobPosting 인스턴스 (None이면 유저 직무 기반 연습 모드)
        user_weakness: {"weak_topics": [...], "weak_categories": [...], "strength_topics": [...]}
        user_job_roles: 유저 프로필의 job_role 코드 리스트 (예: ["ai", "backend"])

    Returns:
        {
            "slots": [...],
            "total_slots": N,
            "weakness_boost": [...]
        }
    """
    if user_job_roles is None:
        user_job_roles = []

    api_key = getattr(settings, 'OPENAI_API_KEY', '') or ''
    if not api_key:
        return _get_default_plan(job_posting, user_weakness, user_job_roles)

    client = openai.OpenAI(api_key=api_key)

    # [2026-03-01] DB에서 기업/직무 기출 질문 조회
    real_questions = _fetch_real_questions(job_posting)

    prompt = _build_plan_prompt(job_posting, user_weakness, real_questions, user_job_roles)

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "너는 면접 계획 수립 전문가다. "
                        "채용공고와 지원자 취약점 데이터, 그리고 실제 면접 기출 질문을 "
                        "바탕으로 맞춤형 면접 계획을 JSON으로 생성한다.\n"
                        "반드시 JSON만 출력한다."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=1500,
        )

        raw = response.choices[0].message.content
        plan = json.loads(raw)
        return _validate_and_normalize_plan(plan, job_posting, user_weakness)

    except Exception as e:
        print(f"[PlanGenerator] 오류: {e}")
        return _get_default_plan(job_posting, user_weakness, user_job_roles)


def _fetch_real_questions(job_posting) -> list:
    """DB에서 기업/직무에 해당하는 실제 면접 기출 질문을 조회한다.

    [2026-03-01 신규]
    question_bank_service.get_questions_for_plan()을 호출하여
    슬롯별 기출 질문을 최대 20개 반환.
    DB 연결 실패 시 빈 리스트 반환 (기존 동작 유지).

    Args:
        job_posting: SavedJobPosting 인스턴스 또는 None

    Returns:
        [{"slot_type": "technical", "question_text": "...", "source": "jobkorea"}, ...]
    """
    try:
        from core.services.interview.question_bank_service import get_questions_for_plan
        company = job_posting.company_name if job_posting else ""
        job = job_posting.position if job_posting else ""
        print(f"[PlanGenerator] 기출 질문 조회 중... 기업: '{company}' | 직무: '{job}'")
        result = get_questions_for_plan(company=company, job=job)
        if result:
            print(f"[PlanGenerator] ✅ 플랜용 기출 {len(result)}개 조회됨")
        else:
            print(f"[PlanGenerator] ⚠️ 플랜용 기출 질문 없음")
        return result
    except Exception as e:
        print(f"[PlanGenerator] 기출 질문 조회 실패 (무시): {e}")
        return []


def _build_plan_prompt(job_posting, user_weakness: dict, real_questions: list = None, user_job_roles: list = None) -> str:
    """plan_generator LLM 프롬프트 생성."""
    # 채용공고 정보 파싱 (1회만 실행)
    if job_posting:
        required_skills = ", ".join(job_posting.required_skills or [])
        preferred_skills = ", ".join(job_posting.preferred_skills or [])
        company_name = job_posting.company_name
        position = job_posting.position
        job_res = job_posting.job_responsibilities[:300] if job_posting.job_responsibilities else ""
        exp_range = job_posting.experience_range
    else:
        resolved_position = _resolve_position(user_job_roles or [])
        required_skills = "없음"
        preferred_skills = "없음"
        company_name = "미지정 (특정 회사명을 만들어내지 마라)"
        position = resolved_position
        job_res = f"{resolved_position} 관련 업무 전반"
        exp_range = "주니어/신입"

    weak_topics = ", ".join(user_weakness.get("weak_topics", []))
    strength_topics = ", ".join(user_weakness.get("strength_topics", []))

    # [2026-03-01] 실제 면접 기출 데이터 섹션 생성
    bank_section = ""
    if real_questions:
        # 슬롯별로 그룹핑
        by_slot = {}
        for q in real_questions:
            by_slot.setdefault(q["slot_type"], []).append(q["question_text"])

        lines = []
        for slot, questions in by_slot.items():
            # 슬롯당 최대 5개 질문, " / "로 구분
            q_str = " / ".join(questions[:5])
            lines.append(f"  - {slot}: {q_str}")

        bank_section = (
            "\n[실제 면접 기출 데이터]\n"
            "아래는 이 기업/직무에서 실제로 출제된 면접 질문이다.\n"
            "이 데이터를 참고하여 면접 계획의 슬롯과 토픽을 결정하라.\n"
            "기출 데이터에 없는 허구의 토픽을 만들지 마라.\n"
            + "\n".join(lines)
        )

    return f"""다음 채용공고와 지원자 데이터를 바탕으로 면접 계획을 수립하라.

[채용공고]
- 회사: {company_name}
- 직무: {position}
- 담당 업무: {job_res}
- 필수 기술: {required_skills}
- 우대 기술: {preferred_skills}
- 경력: {exp_range}

[지원자 데이터]
- 취약 토픽: {weak_topics if weak_topics else "없음"}
- 강점 토픽: {strength_topics if strength_topics else "없음"}
{bank_section}

[면접 계획 수립 규칙]
1. 총 4~6개 슬롯을 선택한다.
2. 슬롯 유형: motivation, technical_depth, collaboration, problem_solving, growth
3. 회사가 "미지정"이면 면접 연습 모드이다. 이 경우:
   - 절대로 특정 회사명(삼성, LG, 네이버, 한전 등)을 생성하거나 언급하지 마라.
   - IT/소프트웨어 분야 면접으로 진행하되, 특정 회사를 전제하지 마라.
   - motivation 슬롯의 topic은 "{position} 커리어 방향성"으로, first_intent는 "해당 분야 관심 계기와 성장 방향 확인"으로 설정하라.
   - technical_depth는 지원자의 취약/강점 토픽 기반으로만 선택하라. 취약/강점 토픽도 없으면 technical_depth를 제외하라.
4. 회사가 지정된 경우 technical_depth는 1~2개 선택. 반드시 채용공고의 필수 기술(required_skills) 또는 직무 설명에서 언급된 기술로만 선택한다.
   - 취약 토픽이 채용공고 기술과 관련 없으면 절대 사용하지 않는다.
   - 채용공고에 기술 스택이 명시되어 있으면 그 기술을 우선한다.
   - 채용공고에 기술 스택이 없으면 직무명/담당업무에서 핵심 기술을 추론한다.
   - 실제 면접 기출 데이터가 있으면, 기출에서 자주 등장하는 기술 토픽을 우선한다.
5. motivation은 반드시 포함하되 첫 번째로 배치
6. collaboration과 problem_solving 중 1개 이상 포함
7. technical_depth 슬롯에는 해당 기술에 맞는 required_evidence를 3~4개 동적 생성
   - 범용 단어(concept/application/tradeoff) 사용 금지
   - 해당 기술 구체적인 내용으로 키 생성 (한글 허용, 언더스코어로 구분)
   - 예: Python 비동기면 → ["asyncio_개념", "실제_사용_경험", "동기방식과_차이", "한계_인식"]
   - 예: Django ORM이면 → ["ORM_동작방식", "N+1_문제_인식", "쿼리_최적화_경험", "트랜잭션_처리"]

[출력 형식]
{{
    "slots": [
        {{
            "slot": "motivation",
            "topic": "지원 동기",
            "max_attempts": 2,
            "first_intent": "지원 이유와 직무 적합성 확인"
        }},
        {{
            "slot": "technical_depth",
            "topic": "Python 비동기",
            "max_attempts": 3,
            "first_intent": "비동기 처리 방식 이해 확인",
            "source": "required_skills",
            "required_evidence": ["asyncio_개념", "실제_사용_경험", "동기방식과_차이", "한계_인식"],
            "optional_evidence": ["이벤트루프_이해", "라이브러리_선택"]
        }},
        {{
            "slot": "collaboration",
            "topic": "팀 협업 경험",
            "max_attempts": 3,
            "first_intent": "팀에서의 역할과 기여 확인"
        }}
    ],
    "total_slots": 4,
    "weakness_boost": ["비동기", "예외처리"]
}}"""


def _validate_and_normalize_plan(plan: dict, job_posting, user_weakness: dict) -> dict:
    """plan 구조 검증 및 정규화"""
    if "slots" not in plan or not isinstance(plan["slots"], list):
        return _get_default_plan(job_posting, user_weakness)

    slots = plan["slots"]

    # 슬롯이 없으면 기본 계획 반환
    if not slots:
        return _get_default_plan(job_posting, user_weakness)

    # 각 슬롯 필수 필드 검증
    required_fields = ["slot", "topic", "max_attempts", "first_intent"]
    normalized_slots = []
    for s in slots:
        if not all(f in s for f in required_fields):
            continue
        normalized_slots.append(s)

    if not normalized_slots:
        return _get_default_plan(job_posting, user_weakness)

    # 중복 슬롯 이름 → 고유 이름으로 변환 (technical_depth → technical_depth_2)
    seen = {}
    for s in normalized_slots:
        name = s["slot"]
        if name in seen:
            seen[name] += 1
            s["slot"] = f"{name}_{seen[name]}"
        else:
            seen[name] = 1

    plan["slots"] = normalized_slots
    plan["total_slots"] = len(normalized_slots)
    if "weakness_boost" not in plan:
        plan["weakness_boost"] = user_weakness.get("weak_topics", [])[:3]

    return plan


def _get_default_plan(job_posting, user_weakness: dict, user_job_roles: list = None) -> dict:
    """LLM 실패 시 기본 면접 계획"""
    if job_posting:
        motivation_slot = {
            "slot": "motivation",
            "topic": "지원 동기",
            "max_attempts": 2,
            "first_intent": "지원 이유와 회사 리서치 여부 확인"
        }
    else:
        resolved = _resolve_position(user_job_roles or [])
        motivation_slot = {
            "slot": "motivation",
            "topic": f"{resolved} 커리어 방향성",
            "max_attempts": 2,
            "first_intent": f"{resolved} 분야 관심 계기와 성장 방향 확인"
        }
    slots = [
        motivation_slot,
        {
            "slot": "collaboration",
            "topic": "팀 협업 경험",
            "max_attempts": 3,
            "first_intent": "팀에서의 역할과 기여 방식 확인"
        },
        {
            "slot": "problem_solving",
            "topic": "문제 해결 경험",
            "max_attempts": 3,
            "first_intent": "문제 상황과 해결 과정 확인"
        },
        {
            "slot": "growth",
            "topic": "성장 경험",
            "max_attempts": 2,
            "first_intent": "도전 경험과 변화 확인"
        }
    ]

    # 채용공고에 기술 스택이 있으면 technical_depth 추가
    required_skills = (job_posting.required_skills or []) if job_posting else []
    if required_skills:
        skill = required_skills[0]
        slots.insert(1, {
            "slot": "technical_depth",
            "topic": skill,
            "max_attempts": 3,
            "first_intent": f"{skill} 이해도 확인",
            "source": "required_skills",
            "required_evidence": [
                f"{skill}_개념",
                f"{skill}_사용_경험",
                f"{skill}_선택_이유",
            ],
            "optional_evidence": [f"{skill}_한계_인식"]
        })

    return {
        "slots": slots,
        "total_slots": len(slots),
        "weakness_boost": user_weakness.get("weak_topics", [])[:3]
    }
