"""
feedback_generator.py — 최종 피드백 생성기
면접 종료 후 slot_states 기반으로 정성적 피드백을 LLM으로 생성한다.
점수나 합격/불합격 판정 금지. 증거 기반 정성적 피드백만 제공.
"""
import json
import openai
from django.conf import settings
from core.services.interview.constants import EVIDENCE_LABELS, SLOT_REQUIRED


def generate_feedback(session) -> dict:
    """
    InterviewSession의 slot_states를 기반으로 최종 피드백을 생성한다.

    Args:
        session: InterviewSession 인스턴스 (slot_states, interview_plan 포함)

    Returns:
        InterviewFeedback 모델에 저장할 데이터 dict
    """
    slot_states = session.slot_states
    interview_plan = session.interview_plan

    # 슬롯별 summary 구성 (LLM 없이 evidence 기반으로 먼저 구성)
    slot_summary = _build_slot_summary(slot_states, interview_plan)

    api_key = getattr(settings, 'OPENAI_API_KEY', '') or ''
    if not api_key:
        return _build_fallback_feedback(slot_summary)

    client = openai.OpenAI(api_key=api_key)
    prompt = _build_feedback_prompt(slot_summary, session)

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "너는 면접 피드백 전문가다. "
                        "증거 기반으로만 정성적 피드백을 제공한다.\n"
                        "점수, 합격/불합격 판정 절대 금지.\n"
                        "반드시 JSON으로만 출력한다."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.5,
            max_tokens=2000,
        )

        raw = response.choices[0].message.content
        result = json.loads(raw)

        # slot_summary는 LLM 결과로 업데이트
        if "slot_summary" in result:
            for slot_name, llm_summary in result["slot_summary"].items():
                if slot_name in slot_summary:
                    slot_summary[slot_name]["summary"] = llm_summary.get("summary", "")

        return {
            "slot_summary": slot_summary,
            "overall_summary": result.get("overall_summary", "면접이 완료되었습니다."),
            "top_strengths": result.get("top_strengths", []),
            "top_improvements": result.get("top_improvements", []),
            "recommendation": result.get("recommendation", ""),
        }

    except Exception as e:
        print(f"[FeedbackGenerator] 오류: {e}")
        return _build_fallback_feedback(slot_summary)


def _build_slot_summary(slot_states: dict, interview_plan: dict) -> dict:
    """슬롯별 evidence 기반 summary 구성 (LLM 없음)"""
    topic_map = {s["slot"]: s.get("topic", "") for s in interview_plan.get("slots", [])}

    summary = {}
    for slot_name, state in slot_states.items():
        evidence = state.get("evidence", {})
        required = state.get("required", SLOT_REQUIRED.get(slot_name, []))

        confirmed_evidence = [k for k, v in evidence.items() if v]
        missing_evidence = [k for k in required if not evidence.get(k)]
        confirmed_required = [k for k in required if evidence.get(k)]

        summary[slot_name] = {
            "topic": topic_map.get(slot_name, slot_name),
            "final_status": state.get("status", "UNKNOWN"),
            "confirmed_evidence": confirmed_evidence,
            "confirmed_required": confirmed_required,
            "missing_evidence": missing_evidence,
            "attempt_count": state.get("attempt_count", 0),
            "summary": "",  # LLM이 채울 예정
        }

    return summary


def _build_feedback_prompt(slot_summary: dict, session) -> str:
    """feedback_generator LLM 프롬프트 생성

    [2026-03-04 변경사항]
      - 실제 면접 대화 내용을 프롬프트에 포함하여
        LLM이 지원자의 구체적인 답변을 참조한 피드백을 생성하도록 개선.
    """
    job_posting = session.job_posting
    company_info = ""
    if job_posting:
        company_info = f"- 회사: {job_posting.company_name}\n- 직무: {job_posting.position}"

    slot_details = []
    for slot_name, summary in slot_summary.items():
        confirmed_labels = [EVIDENCE_LABELS.get(k, k.replace("_", " ")) for k in summary["confirmed_evidence"]]
        missing_labels = [EVIDENCE_LABELS.get(k, k.replace("_", " ")) for k in summary["missing_evidence"]]

        slot_details.append(
            f"- {slot_name} ({summary['final_status']}): "
            f"확인됨={confirmed_labels}, 미확인={missing_labels}"
        )

    slots_str = "\n".join(slot_details)

    # [2026-03-04] 실제 면접 대화 내용 추출
    conversation_section = _build_conversation_section(session)

    return f"""다음 면접 결과를 바탕으로 정성적 피드백을 생성하라.

[채용 정보]
{company_info if company_info else "정보 없음"}

[역량 슬롯별 결과]
{slots_str}
{conversation_section}

[피드백 작성 규칙]
1. 점수, 합격/불합격 판정 절대 금지
2. evidence 판정 결과를 기준으로 피드백하되, 실제 대화 내용은 구체적 서술을 위한 참고로 사용하라.
3. 지원자가 실제로 언급한 기술, 프로젝트, 경험을 구체적으로 인용하여 피드백하라.
4. 답변이 질문의 의도와 무관하거나, 구체적 사례 없이 추상적으로만 답한 경우 명확하게 지적하라.
   예: "팀워크 강화 방법으로 '커피를 샀다'고만 답변하셨는데, 구체적인 협업 전략이나 갈등 해결 경험이 확인되지 않았습니다."
5. 강점(top_strengths)은 실제로 구체적인 경험·기술·사례가 확인된 경우에만 작성하라. 내용이 부족하면 강점 대신 "확인된 강점 없음"으로 표기하라.
6. UNCERTAIN 슬롯은 "충분히 확인되지 않았다"고 표현
7. top_improvements: 증거가 부족했던 부분마다 (1) 무엇이 부족했는지 지적 + (2) 어떻게 답변하면 좋았을지 모범 답변 예시를 함께 제공하라. (2-3개)
   예: "협업 역량에서 본인의 역할이 '팀원이었다' 수준으로만 언급되었습니다. → '팀 내에서 API 설계를 주도하며, 프론트엔드 팀과 주 2회 스펙 리뷰를 진행했습니다'처럼 구체적인 행동을 설명하면 효과적입니다."
8. 한국어 존댓말 사용. 단, 부드럽게 감싸기보다 사실 기반으로 직접적인 피드백을 제공하라.

[출력 형식]
{{
    "slot_summary": {{
        "slotName": {{
            "summary": "이 역량에 대한 1-2문장 정성적 서술 (지원자의 실제 답변 내용 참조)"
        }}
    }},
    "overall_summary": "전반적인 면접 총평 (3-4문장)",
    "top_strengths": ["강점 1 - 실제 답변 근거 포함", "강점 2 - 실제 답변 근거 포함"],
    "top_improvements": ["부족한 점 + → 모범 답변 예시", "부족한 점 + → 모범 답변 예시"],
    "recommendation": "이 포지션 준비를 위한 학습 추천 방향 (1-2문장)"
}}"""


def _build_conversation_section(session) -> str:
    """실제 면접 대화 내용을 슬롯별로 정리하여 프롬프트 섹션으로 반환한다.

    [2026-03-04 신규]
    """
    turns = session.turns.exclude(
        answer=''
    ).order_by('turn_number').values('slot', 'question', 'answer')

    slot_conversations = {}
    for turn in turns:
        slot_conversations.setdefault(turn['slot'], []).append(
            f"  Q: {turn['question']}\n  A: {turn['answer']}"
        )

    if not slot_conversations:
        return ""

    lines = ["\n[실제 면접 대화 내용]"]
    for slot_name, convs in slot_conversations.items():
        lines.append(f"\n({slot_name})")
        lines.extend(convs)

    return "\n".join(lines)


def _build_fallback_feedback(slot_summary: dict) -> dict:
    """LLM 실패 시 evidence 기반 기본 피드백"""
    clear_slots = [s for s, d in slot_summary.items() if d["final_status"] == "CLEAR"]
    partial_slots = [s for s, d in slot_summary.items() if d["final_status"] == "PARTIAL"]
    uncertain_slots = [s for s, d in slot_summary.items() if d["final_status"] == "UNCERTAIN"]

    strengths = [f"{s} 역량이 확인됐습니다" for s in clear_slots[:2]]
    improvements = [f"{s} 역량에 대한 추가 설명이 필요합니다" for s in (partial_slots + uncertain_slots)[:2]]

    total = len(slot_summary)
    clear_count = len(clear_slots)

    overall = (
        f"총 {total}개 역량 중 {clear_count}개에서 충분한 답변을 확인했습니다. "
        f"{'전반적으로 구조적인 답변이 이루어졌습니다.' if clear_count >= total // 2 else '더 구체적인 경험 사례를 준비하면 좋겠습니다.'}"
    )

    return {
        "slot_summary": slot_summary,
        "overall_summary": overall,
        "top_strengths": strengths or ["면접을 완료했습니다."],
        "top_improvements": improvements or ["각 역량에 대해 구체적인 사례를 준비해보세요."],
        "recommendation": "실제 프로젝트 경험을 STAR 방식으로 정리해 보세요.",
    }
