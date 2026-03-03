from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from core.models import UserProfile
from core.views.ai_coach.coach_view import AICoachView
from core.views.ai_coach.coach_prompt import is_off_topic


class _FakeChunk:
    def __init__(self, content=None, tool_calls=None):
        delta = SimpleNamespace(content=content, tool_calls=tool_calls)
        self.choices = [SimpleNamespace(delta=delta)]


class _FakeClient:
    class _Completions:
        @staticmethod
        def create(**kwargs):
            # tool call 없이 바로 토큰 응답 → [DONE] 경로 검증
            return iter([
                _FakeChunk(content="안녕하세요. "),
                _FakeChunk(content="코치 응답입니다."),
            ])

    class _Chat:
        completions = _Completions()

    chat = _Chat()


class AICoachViewTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AICoachView.as_view()

        self.auth_user = User.objects.create_user(
            username="coach_tester",
            email="coach_tester@example.com",
            password="test-pass-1234",
        )
        self.profile = UserProfile.objects.create(
            username="coach_tester",
            user_name="Coach Tester",
            email="coach_tester@example.com",
            password="dummy-password",
        )

    @staticmethod
    def _collect_stream(response):
        chunks = []
        for chunk in response.streaming_content:
            chunks.append(chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk)
        return "".join(chunks)

    def test_is_off_topic_guardrail_keywords(self):
        self.assertTrue(is_off_topic("맛집 추천해줘"))
        self.assertTrue(is_off_topic("ㅋㅋㅋㅋ"))
        self.assertFalse(is_off_topic("내 약점 분석해줘"))

    def test_off_topic_returns_guardrail_stream_without_llm(self):
        req = self.factory.post("/api/core/ai-coach/chat/", {"message": "맛집 추천해줘"}, format="json")
        force_authenticate(req, user=self.auth_user)

        response = self.view(req)

        self.assertEqual(response.status_code, 200)
        payload = self._collect_stream(response)
        self.assertIn('"variant": "blocked"', payload)
        self.assertIn("학습 데이터를 기반", payload)
        self.assertIn("data: [DONE]", payload)

    @override_settings(OPENAI_API_KEY="")
    def test_returns_503_when_openai_key_missing(self):
        req = self.factory.post("/api/core/ai-coach/chat/", {"message": "내 점수 알려줘"}, format="json")
        force_authenticate(req, user=self.auth_user)

        response = self.view(req)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data.get("error"), "LLM 서비스를 사용할 수 없습니다.")

    @override_settings(OPENAI_API_KEY="test-key")
    @patch("core.views.ai_coach.coach_view.openai.OpenAI", return_value=_FakeClient())
    def test_streaming_response_emits_tokens_and_done(self, _mock_openai):
        req = self.factory.post("/api/core/ai-coach/chat/", {"message": "내 약점 분석해줘"}, format="json")
        force_authenticate(req, user=self.auth_user)

        response = self.view(req)

        self.assertEqual(response.status_code, 200)
        payload = self._collect_stream(response)
        self.assertIn('"type": "token"', payload)
        self.assertIn("코치 응답입니다", payload)
        self.assertIn("data: [DONE]", payload)
