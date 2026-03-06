"""BugHunt deep-dive interview view (question + final evaluation)."""

import json
import os
import re

import openai
from django.conf import settings
from django.http import StreamingHttpResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle  # [수정일: 2026-03-06] AI throttle
from rest_framework.views import APIView
from core.views.user_view import CsrfExemptSessionAuthentication  # [수정일: 2026-03-06] CSRF 우회 세션 인증

class BugHuntInterviewView(APIView):
    """
    S4+ 딥다이브 면접 API.
    Step별로 LLM 면접관이 유저와 2~3턴 대화하며 이해도를 평가한다.
    """
    # [수정일: 2026-03-06] 세션 쿠키로 인증하되 CSRF 토큰은 요구하지 않음
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]
    # [수정일: 2026-03-06] AI API 요청 제한 (OpenAI 비용 보호, 10회/분)
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'ai'

    MAX_TURNS = 3
    INTERVIEW_MODEL = "gpt-5.2"

    @staticmethod
    def _parse_json_object(raw_text):
        if not raw_text:
            raise json.JSONDecodeError("empty response", "", 0)

        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", cleaned)
            if not match:
                raise
            return json.loads(match.group(0))

    def post(self, request):
        data = request.data
        step_context = data.get('step_context', {})
        conversation = data.get('conversation', [])
        turn = data.get('turn', 0)
        candidate_name = data.get('candidate_name', '')
        use_stream = bool(data.get('stream', False))

        if not step_context:
            return Response({"error": "step_context is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            api_key = getattr(settings, "OPENAI_API_KEY", "") or os.getenv("OPENAI_API_KEY", "")
            if not api_key:
                return Response({"error": "OPENAI_API_KEY not configured"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            client = openai.OpenAI(api_key=api_key)

            rubric = step_context.get('interview_rubric', {})
            is_final_turn = (turn > self.MAX_TURNS)

            # 스트리밍은 질문 턴에서만 사용 (최종 평가는 구조화 JSON 유지)
            if use_stream and not is_final_turn:
                return self._stream_question_response(
                    client=client,
                    step_context=step_context,
                    rubric=rubric,
                    conversation=conversation,
                    turn=turn,
                    candidate_name=candidate_name
                )

            system_prompt = self._build_system_prompt(step_context, rubric, is_final_turn, candidate_name)

            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(conversation)

            response = client.chat.completions.create(
                model=self.INTERVIEW_MODEL,
                messages=messages,
                temperature=0.6,
                max_completion_tokens=800,
                response_format={"type": "json_object"}
            )

            raw = response.choices[0].message.content
            result = self._parse_json_object(raw)

            if not isinstance(result, dict):
                raise json.JSONDecodeError("result is not object", str(raw), 0)

            if is_final_turn:
                result.setdefault("type", "evaluation")
                result.setdefault("message", "답변을 종합해 보면 핵심 개념 이해는 좋지만 근거를 더 구체화하면 좋겠습니다.")
                result.setdefault("score", 65)
                result.setdefault("understanding_level", "Surface")
                result.setdefault("matched_concepts", [])
                result.setdefault("weak_point", "답변 근거의 구체성")
            else:
                result.setdefault("type", "question")
                result.setdefault("message", "좋은 설명입니다. 한 단계 더 깊게 설명해주시겠어요?")

            return Response(result, status=status.HTTP_200_OK)

        except json.JSONDecodeError:
            if is_final_turn:
                return Response({
                    "type": "evaluation",
                    "message": "종합적으로 핵심은 이해하셨습니다. 다만 실무 적용 근거를 더 구체적으로 말하면 더 높은 점수를 받을 수 있습니다.",
                    "score": 60,
                    "understanding_level": "Surface",
                    "matched_concepts": [],
                    "weak_point": "실무 적용 근거의 구체성"
                }, status=status.HTTP_200_OK)
            return Response({
                "type": "question",
                "message": "답변을 분석하고 있습니다. 조금 더 구체적으로 설명해주시겠어요?",
                "turn": turn
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _stream_question_response(self, client, step_context, rubric, conversation, turn, candidate_name=''):
        system_prompt = self._build_stream_prompt(step_context, rubric, turn, candidate_name)
        messages = [{"role": "system", "content": system_prompt}] + conversation

        def event_stream():
            try:
                stream = client.chat.completions.create(
                    model=self.INTERVIEW_MODEL,
                    messages=messages,
                    temperature=0.6,
                    max_completion_tokens=400,
                    stream=True,
                )
                for chunk in stream:
                    delta = chunk.choices[0].delta if chunk.choices else None
                    token = getattr(delta, "content", None) or ""
                    if token:
                        payload = json.dumps({"token": token}, ensure_ascii=False)
                        yield f"data: {payload}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as e:
                payload = json.dumps({"error": str(e)}, ensure_ascii=False)
                yield f"data: {payload}\n\n"
                yield "data: [DONE]\n\n"

        response = StreamingHttpResponse(
            event_stream(),
            content_type='text/event-stream; charset=utf-8'
        )
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response

    def _build_system_prompt(self, step_context, rubric, is_final_turn, candidate_name=''):
        buggy_code = step_context.get('buggy_code', '')
        user_code = step_context.get('user_code', '')
        error_info = step_context.get('error_info', {})
        display_name = (candidate_name or '').strip() or '지원자'

        core = rubric.get('core_concepts', [])
        mechanism = rubric.get('mechanism_concepts', [])
        application = rubric.get('application_concepts', [])

        rubric_text = (
            f"핵심 개념 (core): {', '.join(core)}\n"
            f"메커니즘 개념 (mechanism): {', '.join(mechanism)}\n"
            f"응용 개념 (application): {', '.join(application)}"
        )

        if is_final_turn:
            return f"""너는 주니어 AI 엔지니어 기술 면접관이다. 한국어로 대화한다.
{display_name}님이 아래 코드의 버그를 수정했고, 지금까지 대화를 나눴다.
이번이 마지막 턴이다. {display_name}님의 마지막 답변을 평가하고 종합 평가를 JSON으로 반환하라.

[버그 코드]
{buggy_code}

[유저가 수정한 코드]
{user_code}

[버그 정보]
타입: {error_info.get('type', '')}
설명: {error_info.get('description', '')}

[평가 기준 - 채점 루브릭]
{rubric_text}

[채점 방법 - 주니어 엔지니어 기준으로 관대하게 채점하라]
대화 전체를 종합해서 채점하라 (마지막 답변만이 아님).
피드백 문장에서는 반드시 "{display_name}님" 호칭을 사용하라.

1) core (40점 만점):
   - 핵심 원인을 자기 말로 설명했으면 30~40점 (전문 용어 불필요, 의미가 맞으면 충분)
   - 방향은 맞지만 부정확하면 15~25점
   - 전혀 모르면 0~10점

2) mechanism (35점 만점):
   - 내부 동작을 구체적으로 설명했으면 25~35점
   - 개념은 알지만 설명이 모호하면 10~20점
   - 언급 없으면 0~5점

3) application (25점 만점):
   - 실무 적용 방법을 1가지라도 구체적으로 제시하면 15~25점
   - 추상적으로만 언급하면 5~12점
   - 언급 없으면 0점

[understanding_level 기준]
- 90점 이상: "Excellent"
- 70~89점: "Good"
- 40~69점: "Surface"
- 39점 이하: "Poor"

반드시 아래 JSON 형식으로만 응답하라:
{{
  "type": "evaluation",
  "message": "2~3문장의 종합 피드백 (잘한 점 + 부족한 점)",
  "score": 0에서 100 사이 정수 (core + mechanism + application의 합),
  "core_score": 0에서 40 사이 정수,
  "mechanism_score": 0에서 35 사이 정수,
  "application_score": 0에서 25 사이 정수,
  "understanding_level": "Excellent|Good|Surface|Poor",
  "matched_concepts": ["유저가 보여준 개념들"],
  "weak_point": "부족한 부분 (없으면 null)"
}}"""

    def _build_stream_prompt(self, step_context, rubric, turn, candidate_name=''):
        buggy_code = step_context.get('buggy_code', '')
        user_code = step_context.get('user_code', '')
        error_info = step_context.get('error_info', {})
        display_name = (candidate_name or '').strip() or '지원자'
        remaining = self.MAX_TURNS - turn

        core = rubric.get('core_concepts', [])
        mechanism = rubric.get('mechanism_concepts', [])
        application = rubric.get('application_concepts', [])

        rubric_text = (
            f"핵심 개념 (core): {', '.join(core)}\n"
            f"메커니즘 개념 (mechanism): {', '.join(mechanism)}\n"
            f"응용 개념 (application): {', '.join(application)}"
        )

        return f"""너는 주니어 AI 엔지니어를 면접하는 기술 면접관이다. 한국어로 대화한다.
{display_name}님이 아래 코드의 버그를 수정했다. 수정 이유와 이해도를 파악하기 위해 질문한다.

[대상 수준 - 매우 중요]
상대방은 AI/ML을 배우고 있는 주니어 엔지니어다.
- 물어봐도 되는 것: 개념의 "왜", 내부 동작 원리, 코드 동작 순서, 해당 버그와 직접 관련된 내용
- 절대 물어보면 안 되는 것: gradient accumulation 구현, loss scaling, learning rate scheduling 전략, 분산 학습, 커스텀 옵티마이저 등 시니어 레벨 주제
- 루브릭에 있는 개념 범위 안에서만 질문하라. 루브릭에 없는 심화 주제로 넘어가지 마라.

[현재 진행 상황]
현재 {turn}/{self.MAX_TURNS}턴 (남은 질문 기회: {remaining}회)

턴별 질문 방향:
- 1턴 (첫 답변 후): core 개념을 정확히 이해했는지 확인. 틀린 부분이 있으면 반드시 짚어라.
- 2턴: mechanism 개념으로 넘어가라. "내부적으로 어떤 일이 일어나는지" 물어라.
- 3턴 (마지막): application 개념을 물어라. 단, 주니어 수준의 실무 (디버깅 방법, 확인 방법) 한정.

[버그 코드]
{buggy_code}

[유저가 수정한 코드]
{user_code}

[버그 정보]
타입: {error_info.get('type', '')}
설명: {error_info.get('description', '')}

[평가 기준 - 채점 루브릭]
{rubric_text}

[적응형 질문 전략 - 유저의 직전 답변을 기준으로 판단하라]

1) 답변이 정확하고 구체적인 경우:
   → "잘 이해하고 계시네요"를 짧게 인정한 뒤, 루브릭의 다음 단계 개념을 물어라.
   → 단, 반드시 루브릭 범위 안의 개념만 물어라.

2) 방향은 맞지만 부정확하거나 빠진 부분이 있는 경우:
   → 틀린 부분을 부드럽게 짚어라. (예: "~라고 하셨는데, 실제로는 조금 다릅니다. 그러면 ~는 어떤 식으로 동작할까요?")
   → 틀린 것을 그냥 넘어가지 마라. 교정이 최우선이다.

3) "모르겠다" 또는 매우 모호한 답변인 경우:
   → 난이도를 확 낮춰라. 같은 개념을 더 쉽게 다시 물어라.
   → 짧은 힌트를 제시하라. (예: "힌트를 드리자면, backward()를 호출할 때 .grad 값이 어떻게 변하는지 생각해보시면 됩니다. 혹시 아시나요?")
   → 절대로 같은 난이도나 더 어려운 질문을 내지 마라.

4) 완전히 방향이 틀린 경우:
   → 틀린 부분을 정중하게 알려주고, 올바른 방향의 단서를 준 뒤 더 쉬운 질문을 하라.

[규칙]
- 정답을 직접 알려주지 마라. 유도 질문만 하라.
- 질문은 1~2문장으로 짧고 명확하게 하라. 한 번에 여러 질문을 하지 마라.
- 반드시 존댓말을 사용하라.
- 유저를 부를 때는 반드시 "{display_name}님" 호칭을 사용하라.
- 내부 평가/분석 과정은 절대 노출하지 마라.
- 출력은 JSON이 아닌, 사용자에게 보여줄 "질문 문장만" 출력하라.
"""
