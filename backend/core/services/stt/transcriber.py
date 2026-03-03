"""
transcriber.py -- STT (Speech-to-Text) 변환 모듈 (faster-whisper large-v3 기반)

수정일: 2026-03-01
변경 내용: RunPod 호출 방식을 기존 Pod 직접 호출(FastAPI)에서
          Serverless + Network Volume 방식(/runsync JSON API)으로 전환

동작 모드:
    1. RunPod Serverless 모드 (STT_RUNPOD_URL + RUNPOD_API_KEY 설정 시)
       - 오디오를 base64 인코딩하여 RunPod Serverless 엔드포인트로 POST
       - Authorization Bearer 헤더로 인증
       - 응답: {"status": "COMPLETED", "output": {"transcript", "confidence", "language"}}

    2. 로컬 모드 (환경변수 미설정 시)
       - faster-whisper medium 모델을 로컬 CPU에서 실행
       - 개발/테스트 환경용 (GPU 없이도 동작)

사용처:
    - stt_service.py의 process_audio()에서 호출
    - _RUNPOD_URL 값을 stt_service.py에서 import하여 VAD 분기 판단에 사용

환경변수:
    STT_RUNPOD_URL  : RunPod Serverless 엔드포인트 URL
                      예: https://api.runpod.ai/v2/qta6vox8pub0vl/runsync
    RUNPOD_API_KEY  : RunPod API 인증 키
                      예: rpa_XXXX...

이전 방식 (Pod 직접 호출):
    - STT_RUNPOD_URL = "http://213.192.x.x:40XXX" (Pod IP:Port)
    - multipart file upload으로 /transcribe 엔드포인트 호출
    - 인증 없음
    현재 방식 (Serverless):
    - STT_RUNPOD_URL = "https://api.runpod.ai/v2/{endpoint_id}/runsync"
    - base64 JSON + Bearer 인증
    - RunPod이 자동으로 워커 스케일링
"""
import base64
import io
import math
import os

import requests as _requests


# =============================================================================
# 환경변수 로드
# =============================================================================

# [2026-03-01] RunPod Serverless 엔드포인트 URL
# 예: https://api.runpod.ai/v2/qta6vox8pub0vl/runsync
# 비어있으면 로컬 모드로 동작
_RUNPOD_URL = os.environ.get("STT_RUNPOD_URL", "").rstrip("/")

# [2026-03-01] RunPod API 인증 키 (Serverless 방식에서 필수)
# Bearer 토큰으로 Authorization 헤더에 포함
_RUNPOD_API_KEY = os.environ.get("RUNPOD_API_KEY", "")

# 로컬 모드용: faster-whisper 설치 여부 확인
try:
    from faster_whisper import WhisperModel
    _WHISPER_AVAILABLE = True
except ImportError:
    _WHISPER_AVAILABLE = False

# 로컬 모델 싱글톤 인스턴스
_model_instance = None


# =============================================================================
# 로컬 모드
# =============================================================================

def _get_local_model() -> 'WhisperModel':
    """로컬 faster-whisper 모델 싱글톤 로더

    처음 호출 시 모델을 메모리에 로드하고, 이후 호출에서는 캐시된 인스턴스를 반환.
    GPU(CUDA)가 있으면 float16, 없으면 CPU + int8으로 로드.

    Returns:
        WhisperModel: 로드된 모델 인스턴스
    """
    global _model_instance
    if _model_instance is None:
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
            compute_type = "float16" if device == "cuda" else "int8"
        except ImportError:
            device = "cpu"
            compute_type = "int8"

        # 로컬용은 medium 모델 사용 (large-v3는 CPU에서 너무 느림)
        model_size = "medium"
        print(f"[STT] faster-whisper {model_size} 로딩 중... (device={device}, compute={compute_type})")
        _model_instance = WhisperModel(model_size, device=device, compute_type=compute_type)
        print("[STT] 로컬 모델 로드 완료")

    return _model_instance


def _transcribe_local(audio_bytes: bytes) -> dict:
    """로컬 faster-whisper 모델로 음성 → 텍스트 변환

    RunPod 미설정 시(개발/테스트 환경) 사용.
    medium 모델 + CPU 기반이므로 RunPod 대비 느리고 정확도가 낮음.

    Args:
        audio_bytes: 오디오 파일 바이트 데이터 (webm, wav 등)

    Returns:
        dict: {
            "transcript": str,    # 변환된 텍스트
            "confidence": float,  # 신뢰도 (0.0 ~ 1.0)
            "language": str,      # 감지된 언어 코드
            "error": str | None,  # 에러 메시지 (정상 시 None)
        }
    """
    if not _WHISPER_AVAILABLE:
        return {
            "transcript": "",
            "confidence": 0.0,
            "language": "ko",
            "error": "faster-whisper가 설치되지 않았습니다. pip install faster-whisper",
        }

    try:
        model = _get_local_model()
        audio_io = io.BytesIO(audio_bytes)

        segments, info = model.transcribe(
            audio_io,
            language="ko",
            beam_size=5,
            best_of=5,
            temperature=0.0,
            condition_on_previous_text=False,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
        )

        texts = []
        logprobs = []
        for segment in segments:
            text = segment.text.strip()
            if text:
                texts.append(text)
                logprobs.append(segment.avg_logprob)

        transcript = " ".join(texts).strip()

        # avg_logprob → 확률 변환: exp(logprob), 0.0~1.0 범위로 클램핑
        if logprobs:
            avg_logprob = sum(logprobs) / len(logprobs)
            confidence = round(min(1.0, max(0.0, math.exp(avg_logprob))), 3)
        else:
            confidence = 0.0

        return {
            "transcript": transcript,
            "confidence": confidence,
            "language": info.language,
            "error": None,
        }

    except Exception as e:
        print(f"[STT] 로컬 변환 오류: {e}")
        return {
            "transcript": "",
            "confidence": 0.0,
            "language": "ko",
            "error": str(e),
        }


# =============================================================================
# RunPod Serverless 모드
# =============================================================================

def _transcribe_remote(audio_bytes: bytes) -> dict:
    """RunPod Serverless 엔드포인트로 STT 요청 전송

    [2026-03-01] 기존 Pod 직접 호출(FastAPI multipart) → Serverless JSON API로 전환

    변경 전 (Pod 방식):
        - multipart file upload: {"audio": (filename, bytes, mimetype)}
        - URL: {POD_IP}/transcribe
        - 인증: 없음

    변경 후 (Serverless 방식):
        - base64 JSON: {"input": {"audio_base64": "...", "language": "ko"}}
        - URL: https://api.runpod.ai/v2/{endpoint_id}/runsync (그대로 사용)
        - 인증: Authorization: Bearer {RUNPOD_API_KEY}

    RunPod Serverless 응답 구조:
        성공: {"id": "...", "status": "COMPLETED", "output": {"transcript", "confidence", "language"}}
        실패: {"id": "...", "status": "FAILED", "error": "..."}

    Args:
        audio_bytes: 오디오 파일 바이트 데이터 (webm, wav 등)

    Returns:
        dict: {
            "transcript": str,
            "confidence": float,
            "language": str,
            "error": str | None,
        }
    """
    try:
        # ── 1. 요청 헤더 구성 ─────────────────────────────────────────
        # Serverless API는 Bearer 토큰 인증 필수
        headers = {
            "Authorization": f"Bearer {_RUNPOD_API_KEY}",
            "Content-Type": "application/json",
        }

        # ── 2. 오디오를 base64로 인코딩하여 JSON 페이로드 구성 ────────
        # 기존 multipart file upload 대신 base64 문자열로 전송
        # runpod_server.py의 handler()가 이를 디코딩하여 처리
        payload = {
            "input": {
                "audio_base64": base64.b64encode(audio_bytes).decode("utf-8"),
                "language": "ko",
            }
        }

        # ── 3. RunPod Serverless 엔드포인트 호출 ─────────────────────
        # _RUNPOD_URL에 이미 /runsync가 포함되어 있으므로 경로 추가 불필요
        # timeout=90: Serverless Cold Start 시간 고려하여 기존 60초 → 90초로 확장
        resp = _requests.post(
            _RUNPOD_URL,
            json=payload,
            headers=headers,
            timeout=90,
        )
        resp.raise_for_status()
        data = resp.json()

        # ── 4. Serverless 응답 파싱 ──────────────────────────────────
        # 성공: {"status": "COMPLETED", "output": {...}}
        # 실패: {"status": "FAILED", "error": "..."}
        status = data.get("status")

        if status == "COMPLETED":
            output = data.get("output", {})

            # 핸들러에서 에러가 반환된 경우 (handler 내부 예외)
            if "error" in output:
                print(f"[STT] RunPod 핸들러 에러: {output['error']}")
                return {
                    "transcript": "",
                    "confidence": 0.0,
                    "language": "ko",
                    "error": output["error"],
                }

            # 정상 응답: transcript, confidence, language
            output.setdefault("error", None)
            return output

        else:
            # FAILED, IN_QUEUE, IN_PROGRESS 등 비정상 상태
            error_msg = data.get("error", f"RunPod 상태: {status}")
            print(f"[STT] RunPod 비정상 응답: {status} — {error_msg}")
            return {
                "transcript": "",
                "confidence": 0.0,
                "language": "ko",
                "error": error_msg,
            }

    except _requests.exceptions.Timeout:
        print("[STT] RunPod 호출 타임아웃 (90초 초과)")
        return {
            "transcript": "",
            "confidence": 0.0,
            "language": "ko",
            "error": "RunPod 요청 타임아웃 (90초 초과). Cold Start 중일 수 있습니다.",
        }
    except Exception as e:
        print(f"[STT] RunPod 호출 실패: {e}")
        return {
            "transcript": "",
            "confidence": 0.0,
            "language": "ko",
            "error": str(e),
        }


# =============================================================================
# 메인 진입점
# =============================================================================

def transcribe(audio_bytes: bytes) -> dict:
    """음성 바이트 → 한국어 텍스트 변환 (메인 진입점)

    STT_RUNPOD_URL + RUNPOD_API_KEY 환경변수 설정 시 RunPod Serverless GPU 사용.
    미설정 시 로컬 faster-whisper 모델(CPU) 사용.

    stt_service.py의 process_audio()에서 호출.

    Args:
        audio_bytes: 오디오 파일 바이트 데이터

    Returns:
        dict: {"transcript", "confidence", "language", "error"}
    """
    if _RUNPOD_URL:
        print(f"[STT] RunPod Serverless 사용: {_RUNPOD_URL}")
        return _transcribe_remote(audio_bytes)
    else:
        print("[STT] 로컬 모델 사용 (STT_RUNPOD_URL 미설정)")
        return _transcribe_local(audio_bytes)
