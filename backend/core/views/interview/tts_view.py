"""
TTS API 엔드포인트
POST /api/core/tts/synthesize/
텍스트 → 음성(mp3) 변환 (OpenAI TTS)
"""
import os

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle  # [수정일: 2026-03-06] AI throttle
from core.views.user_view import CsrfExemptSessionAuthentication  # [수정일: 2026-03-06] CSRF 우회 세션 인증

from openai import OpenAI

_client = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    return _client


@method_decorator(csrf_exempt, name='dispatch')
class TTSSynthesizeView(APIView):
    """
    POST /api/core/tts/synthesize/

    Body (JSON):
        {
            "text": "읽어줄 텍스트",
            "voice": "alloy"   // 선택 (기본값: alloy)
        }

    Response:
        Content-Type: audio/mpeg
        Body: mp3 오디오 바이너리
    """
    # [수정일: 2026-03-06] 세션 쿠키로 인증하되 CSRF 토큰은 요구하지 않음
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]
    # [수정일: 2026-03-06] AI API 요청 제한 (OpenAI TTS 비용 보호, 10회/분)
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'ai'

    # OpenAI TTS 지원 음성 목록
    VALID_VOICES = {"alloy", "echo", "fable", "onyx", "nova", "shimmer"}
    # alloy (기본, 중성)
    # nova (여성 느낌)
    # onyx (남성 느낌)
    # shimmer (부드러운 여성)
    def post(self, request):
        text = request.data.get("text", "").strip()
        if not text:
            return Response(
                {"error": "텍스트가 비어 있습니다. (key: text)"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(text) > 4096:
            return Response(
                {"error": "텍스트가 너무 깁니다. (최대 4096자)"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        voice = request.data.get("voice", "alloy")
        if voice not in self.VALID_VOICES:
            voice = "alloy"

        fmt = request.data.get("format", "mp3")
        if fmt not in {"mp3", "wav"}:
            fmt = "mp3"

        try:
            client = _get_client()
            response = client.audio.speech.create(
                model="tts-1",
                voice=voice,
                input=text,
                response_format=fmt,
            )

            audio_bytes = response.content
            content_type = "audio/wav" if fmt == "wav" else "audio/mpeg"

            return HttpResponse(
                audio_bytes,
                content_type=content_type,
                status=200,
            )

        except Exception as e:
            print(f"[TTS] OpenAI TTS 오류: {e}")
            return Response(
                {"error": f"음성 변환 중 오류가 발생했습니다: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
