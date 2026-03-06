import sys
import traceback
import openai
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.throttling import ScopedRateThrottle  # [수정일: 2026-03-06] AI throttle
from core.views.user_view import CsrfExemptSessionAuthentication  # [수정일: 2026-03-06] CSRF 우회 세션 인증

# [수정일: 2026-02-08] AI Proxy View 추가 (Antigravity)
@method_decorator(csrf_exempt, name='dispatch')
class AIProxyView(APIView):
    """
    OpenAI API 프록시 뷰 (프론트엔드에서 API Key 노출 방지)
    """
    # [수정일: 2026-03-06] 세션 쿠키로 인증하되 CSRF 토큰은 요구하지 않음
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]
    # [수정일: 2026-03-06] AI API 요청 제한 (OpenAI 비용 보호, 10회/분)
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'ai'

    def post(self, request):
        try:
            # 1. 요청 데이터 추출
            messages = request.data.get('messages', [])
            model = request.data.get('model', 'gpt-4o-mini')
            max_tokens = request.data.get('max_tokens', 1500)
            temperature = request.data.get('temperature', 0.7)
            response_format = request.data.get('response_format')

            if not messages:
                return Response({"error": "Messages are required"}, status=status.HTTP_400_BAD_REQUEST)

            # 2. API Key 확인
            api_key = settings.OPENAI_API_KEY
            if not api_key:
                print("[AIProxy] Error: OPENAI_API_KEY is missing in settings.", flush=True)
                return Response({"error": "OpenAI API Key is missing on server"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            client = openai.OpenAI(api_key=api_key)

            # 3. OpenAI API 호출
            # [2026-02-13] 프론트엔드 전달 파라미터 및 response_format 통합 적용
            print(f"[AIProxy] Calling OpenAI (model={model}, max_tokens={max_tokens}, temperature={temperature})...", flush=True)
            
            call_params = {
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature
            }
            
            if response_format:
                call_params["response_format"] = response_format

            response = client.chat.completions.create(**call_params)

            # 4. 응답 반환
            ai_content = response.choices[0].message.content
            print(f"[AIProxy] OpenAI Call Success! (Model: {model})", flush=True)
            return Response({"content": ai_content}, status=status.HTTP_200_OK)

        except openai.AuthenticationError as e:
            print(f"[AIProxy] Authentication Error (Check API Key): {e}", file=sys.stderr, flush=True)
            return Response({"error": "Invalid API Key or Authentication Error"}, status=status.HTTP_401_UNAUTHORIZED)
        except openai.RateLimitError as e:
            print(f"[AIProxy] Rate Limit Error (Quota Exceeded?): {e}", file=sys.stderr, flush=True)
            return Response({"error": "Rate Limit Exceeded"}, status=status.HTTP_429_TOO_MANY_REQUESTS)
        except Exception as e:
            tb = traceback.format_exc()
            print(f"[AIProxy] General Error: {e}\n{tb}", file=sys.stderr, flush=True)
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
