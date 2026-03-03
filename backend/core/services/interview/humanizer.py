"""
humanizer.py -- L5 Humanizer (컨텍스트 조립 유틸)

수정일: 2026-03-01
설명: LLM 없음. L4 Interviewer에 전달할 컨텍스트를 조립하는 유틸 함수.
"""
from core.services.interview.plan_generator import _resolve_position


def build_context(session, plan_slot: dict = None) -> dict:
    """
    L4 Interviewer 프롬프트에 주입할 컨텍스트를 조립한다.
    LLM 호출 없음.
    """
    if plan_slot is None:
        plan_slot = session.get_current_slot_plan()

    current_slot_state = session.slot_states.get(session.current_slot, {})
    attempt_count = current_slot_state.get("attempt_count", 1)

    # 채용공고 정보
    company_name = ""
    position = ""
    job_responsibilities = ""
    required_qualifications = ""
    preferred_qualifications = ""

    if session.job_posting:
        company_name = session.job_posting.company_name or ""
        position = session.job_posting.position or ""
        job_responsibilities = (session.job_posting.job_responsibilities or "")[:400]
        required_qualifications = (session.job_posting.required_qualifications or "")[:300]
        preferred_qualifications = (session.job_posting.preferred_qualifications or "")[:200]
    else:
        # 공고 없이 시작: 유저 프로필의 job_role 기반 직무 설정
        user_job_roles = session.interview_plan.get("user_job_roles", [])
        position = _resolve_position(user_job_roles)

    weakness_boost = session.interview_plan.get("weakness_boost", [])

    # [2026-03-01] 현재 슬롯에 해당하는 기출 질문 추출
    #   interview_plan["bank_questions"]는 session_view.py에서 세션 생성 시 저장됨.
    #   키: "motivation", "technical", "collaboration", "problem_solving", "growth"
    #   technical_depth, technical_depth_2 등은 모두 "technical" 키로 통합됨.
    bank_questions = session.interview_plan.get("bank_questions", {})
    slot_key = session.current_slot
    if slot_key.startswith("technical"):
        slot_key = "technical"
    current_bank = bank_questions.get(slot_key, [])

    return {
        "slot": session.current_slot,
        "topic": plan_slot.get("topic", session.current_slot),
        "is_slot_transition": session.just_moved_slot,
        "attempt_count": attempt_count,
        "is_first_question": (session.current_turn == 0),
        "company_name": company_name,
        "position": position,
        "job_responsibilities": job_responsibilities,
        "required_qualifications": required_qualifications,
        "preferred_qualifications": preferred_qualifications,
        "weakness_boost": weakness_boost,
        "bank_questions": current_bank,  # [2026-03-01] 현재 슬롯 기출 질문
    }
