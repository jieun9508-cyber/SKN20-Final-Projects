"""
interviewer.py -- L4 Interviewer (대화 생성기 + 말투 보정 통합)

수정일: 2026-03-01
설명: LLM 1번 호출. intent + humanizer_context -> 자연스러운 면접관 질문 생성.
      L4와 L5는 LLM 호출 1번으로 처리한다.

[2026-03-01 변경사항]
  - _build_interviewer_prompt()에 [실제 면접 기출 질문] 섹션 추가.
    humanizer_context["bank_questions"]에서 현재 슬롯의 기출 질문을 가져와
    시스템 프롬프트에 주입. LLM이 실제 면접 데이터를 참고하여 질문을 생성하도록 함.
"""
import openai
from django.conf import settings


def generate_question(intent: str, humanizer_context: dict, previous_answer: str = '', conversation_history: list = None):
    """
    intent와 컨텍스트를 받아 자연스러운 면접관 질문을 스트리밍으로 생성한다.

    Args:
        intent: L3 Planner가 결정한 질문 의도
        humanizer_context: L5 Humanizer가 조립한 컨텍스트
        previous_answer: 지원자의 직전 답변 (후속 질문 생성에 사용)
        conversation_history: 이전 대화 목록 [{"q": "질문", "a": "답변"}, ...]

    Yields:
        str: 질문 텍스트의 토큰 단위 조각
    """
    api_key = getattr(settings, 'OPENAI_API_KEY', '') or ''
    if not api_key:
        yield "다음 경험에 대해 좀 더 말씀해 주시겠어요?"
        return

    client = openai.OpenAI(api_key=api_key)
    prompt = _build_interviewer_prompt(intent, humanizer_context)

    messages = [{"role": "system", "content": prompt}]

    # 이전 대화 히스토리 주입 (최근 4턴)
    for turn in (conversation_history or [])[-4:]:
        messages.append({"role": "assistant", "content": turn["q"]})
        messages.append({"role": "user", "content": turn["a"]})

    # 현재 답변
    if previous_answer:
        messages.append({"role": "user", "content": f"[지원자 답변]\n{previous_answer}\n\n위 답변을 바탕으로 후속 질문을 생성하라."})
    else:
        messages.append({"role": "user", "content": "질문을 생성하라."})

    try:
        stream = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.7,
            max_tokens=200,
            stream=True,
        )

        for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            token = getattr(delta, "content", None) or ""
            if token:
                yield token

    except Exception as e:
        print(f"[Interviewer] 오류: {e}")
        yield "조금 더 구체적으로 말씀해 주시겠어요?"


def generate_question_sync(intent: str, humanizer_context: dict, previous_answer: str = '', conversation_history: list = None) -> str:
    """
    동기 방식으로 질문을 생성한다 (첫 질문 생성 등에 사용).

    Returns:
        완성된 질문 문자열
    """
    return "".join(generate_question(intent, humanizer_context, previous_answer, conversation_history))


def _build_interviewer_prompt(intent: str, ctx: dict) -> str:
    """Interviewer 프롬프트 생성 (L4 + L5 통합)

    [2026-03-01] bank_questions가 ctx에 포함되어 있으면
    [실제 면접 기출 질문] 섹션을 시스템 프롬프트에 추가한다.
    """

    slot = ctx.get("slot", "")
    topic = ctx.get("topic", slot)
    is_slot_transition = ctx.get("is_slot_transition", False)
    attempt_count = ctx.get("attempt_count", 1)
    is_first_question = ctx.get("is_first_question", False)
    company_name = ctx.get("company_name", "")
    position = ctx.get("position", "")
    job_responsibilities = ctx.get("job_responsibilities", "")
    required_qualifications = ctx.get("required_qualifications", "")
    preferred_qualifications = ctx.get("preferred_qualifications", "")
    weakness_boost = ctx.get("weakness_boost", [])
    bank_questions = ctx.get("bank_questions", [])  # [2026-03-01] 기출 질문

    weakness_info = ""
    if weakness_boost:
        weakness_list = ", ".join(weakness_boost)
        weakness_info = (
            f"\n[지원자 취약 영역]\n"
            f"- 분석된 취약 영역: {weakness_list}\n"
            f"- 현재 주제와 관련이 있다면, 이 영역에 대한 구체적인 경험이나 이해를 확인하는 방향으로 질문하라."
        )

    company_info = ""
    if company_name:
        # 채용공고가 있는 경우
        job_detail = ""
        if job_responsibilities:
            job_detail += f"\n- 주요 업무: {job_responsibilities}"
        if required_qualifications:
            job_detail += f"\n- 필수 자격요건: {required_qualifications}"
        if preferred_qualifications:
            job_detail += f"\n- 우대 사항: {preferred_qualifications}"
        company_info = f"\n[채용 정보]\n- 회사: {company_name}\n- 직무: {position}{job_detail}"
    else:
        # 공고 없이 시작 (면접 연습 모드)
        position_label = position if position else "AI / 소프트웨어 엔지니어"
        company_info = (
            f"\n[면접 연습 모드]\n"
            f"- 지원자는 특정 채용공고 없이 면접 연습 중이다.\n"
            f"- 지원자의 관심 직무: {position_label}\n"
            f"- 절대로 특정 회사명(삼성, LG, 네이버, 한전 등)을 언급하거나 만들어내지 마라.\n"
            f"- '지원 동기' 질문 시 특정 회사 대신 '{position_label} 분야에 관심을 갖게 된 계기나 커리어 방향'을 물어라.\n"
            f"- '저희 회사', '당사' 같은 표현도 사용하지 마라."
        )

    transition_guide = ""
    if is_slot_transition and not is_first_question:
        transition_guide = (
            "\n[슬롯 전환 규칙]\n"
            "- 이전 주제에서 자연스럽게 전환하는 브릿지 문장을 먼저 작성하라.\n"
            "- 예: '말씀 잘 들었습니다. 이번에는 다른 경험에 대해 여쭤보겠습니다.'\n"
            "- 예: '그 경험이 잘 이해됐습니다. 이제는 기술적인 부분으로 넘어가볼까요?'"
        )

    repeat_guide = ""
    if attempt_count >= 2:
        repeat_guide = (
            "\n[재시도 규칙]\n"
            f"- 이 주제로 {attempt_count}번째 질문이다.\n"
            "- 이전과 다른 각도에서 접근하는 도입부를 사용하라.\n"
            "- 예: '조금 더 구체적으로 말씀해 주실 수 있을까요?'\n"
            "- 예: '다른 관점에서 여쭤보겠습니다.'"
        )

    first_question_guide = ""
    if is_first_question:
        first_question_guide = (
            "\n[첫 질문 규칙]\n"
            "- 먼저 자연스러운 인사 한 문장으로 시작하라. 예: '안녕하세요, 오늘 면접에 응해주셔서 감사합니다.'\n"
            "- 인사 직후 바로 첫 면접 질문을 이어서 작성하라.\n"
            "- 예: '안녕하세요, 반갑습니다. 팀 프로젝트에서 어떤 역할을 맡아보신 경험이 있으신가요?'"
        )

    # [2026-03-01] 실제 면접 기출 질문 섹션 생성
    #   humanizer가 interview_plan["bank_questions"]에서 현재 슬롯 질문을 추출하여 전달.
    #   LLM이 기출 질문을 참고하되, 대화 흐름에 맞게 자연스럽게 변형하도록 지시.
    bank_guide = ""
    if bank_questions:
        q_list = "\n".join(
            f"  {i+1}. {q['question_text']}"
            for i, q in enumerate(bank_questions)
        )
        bank_guide = (
            f"\n[실제 면접 기출 질문]\n"
            f"아래는 이 기업/직무에서 실제로 출제된 면접 질문이다.\n"
            f"이 질문들을 기반으로 면접을 진행하되, 대화 흐름에 맞게 자연스럽게 변형하라.\n"
            f"{q_list}\n"
            f"- 질문을 그대로 읽지 말고, 지원자의 답변과 현재 맥락에 맞게 재구성하라.\n"
            f"- 기출 질문의 핵심 의도를 유지하면서 자연스러운 면접 대화를 이어가라."
        )

    opening_rule = (
        "1. 짧은 인사 한 문장 후 바로 질문으로 이어가라."
        if is_first_question
        else (
            "1. 바로 질문으로 시작하거나, 직전 답변의 구체적 내용을 짧게 언급하며 연결하라.\n"
            "   - 좋은 예: '그 장애 상황에서 결국 어떻게 됐나요?' / '말씀하신 팀 갈등과 관련해서 본인 역할이 어떠셨나요?'\n"
            "   - 나쁜 예: '흥미롭네요, 그렇다면...' / '좋습니다.' / '그렇군요.' (내용 없는 감탄·호응 시작 금지)"
        )
    )

    return f"""당신은 자연스러운 한국어 면접관이다.
지원자의 답변을 듣고 적절한 후속 질문을 한다.
{company_info}{weakness_info}{bank_guide}

[면접 맥락]
- 현재 평가 주제: {topic}
- 질문 의도: {intent}
- 슬롯 전환 여부: {"예" if is_slot_transition else "아니오"}
- 동일 주제 시도 횟수: {attempt_count}
{first_question_guide}
{transition_guide}
{repeat_guide}

[필수 규칙]
{opening_rule}
2. 질문은 반드시 하나여야 한다. (복수 질문 금지)
3. evidence 단어(role, action, result 등 영어 키)를 직접 언급하지 마라.
4. "결과를 말해주세요"처럼 직접적인 요구 금지.
   대신: "그 이후 어떻게 됐나요?" / "팀 분위기가 어떻게 바뀌었나요?"
5. 직설적 표현을 부드럽게 완화하라.
6. 전체 응답은 2-4문장 이내로 간결하게 작성하라.
7. 한국어로만 답하라.
8. 채용공고의 주요 업무와 자격요건을 참고하여, 해당 직무에서 실제로 필요한 역량을 확인하는 방향으로 질문하라.
   예: 공고에 "Python 백엔드 API 개발"이 있으면 → API 설계나 성능 경험을 연결지어 질문
9. 후속 질문은 '질문 의도'에 집중하되, 지원자가 언급한 구체적인 사례나 키워드를 자연스럽게 연결해 질문하라.
   예: 지원자가 "배포 중 장애"를 언급했고 의도가 "결과 변화 확인"이라면 → "그 장애가 결국 어떻게 해결됐나요?"

[절대 금지]
- "흥미롭네요/흥미롭습니다/흥미로운 경험이네요" 같은 내용 없는 감탄 금지
- "그렇군요/아 그렇군요/네, 알겠습니다" 같은 단독 호응어로 시작 금지
- "네, 잘 들었습니다" / "네 잘들었습니다" / "말씀 잘 들었습니다" 금지
- 동일한 반응 표현을 두 번 이상 사용 금지
- "STAR 방식으로 답해주세요" 금지
- "행동(Action)이 뭔지", "결과(Result)가 뭔지" 같은 직접적 증거 요구 금지
- "좋습니다/훌륭합니다" 같은 과도한 칭찬 금지
- 평가나 점수 관련 언급 금지
- 절대로 지원자가 말하지 않은 내용을 '~라고 하셨는데'처럼 언급하지 마라.
- 기출 질문은 주제 참고용일 뿐, 지원자 답변에 없는 내용은 전제로 삼지 마라.

[출력 형식]
자연스러운 면접관 말투의 질문 문장만 출력하라. JSON이나 마크다운 사용 금지."""
