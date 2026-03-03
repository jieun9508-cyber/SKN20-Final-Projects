"""
runpod_server.py -- RunPod Serverless STT 핸들러 (faster-whisper large-v3)

수정일: 2026-03-01
변경 내용: 기존 FastAPI Pod 방식 → RunPod Serverless + Network Volume 방식으로 전환

동작 방식:
    1. RunPod Serverless가 이 스크립트를 워커로 실행
    2. Network Volume에 저장된 faster-whisper large-v3 모델을 로드 (Warm Start 시 재사용)
    3. 클라이언트(transcriber.py)가 base64 인코딩된 오디오를 JSON으로 전송
    4. 핸들러가 디코딩 → faster-whisper로 STT 수행 → 결과 반환

요청 형식 (RunPod Serverless /runsync):
    POST https://api.runpod.ai/v2/{endpoint_id}/runsync
    Headers: { "Authorization": "Bearer {RUNPOD_API_KEY}" }
    Body: {
        "input": {
            "audio_base64": "<base64 인코딩된 오디오>",
            "language": "ko"   # 선택, 기본값 "ko"
        }
    }

응답 형식 (RunPod Serverless 래핑):
    {
        "status": "COMPLETED",
        "output": {
            "transcript": "변환된 텍스트",
            "confidence": 0.85,
            "language": "ko"
        }
    }

클라이언트 연동:
    - transcriber.py의 _transcribe_remote()에서 호출
    - 응답 필드명: transcript, confidence, language (클라이언트 규격과 일치)

이전 방식 (FastAPI Pod):
    - FastAPI + uvicorn 기반, multipart file upload
    - 전용 Pod 상시 가동 필요 (비용 높음)
    현재 방식 (Serverless):
    - runpod.serverless.start() 기반, base64 JSON
    - 요청 없으면 워커 0으로 스케일 다운 (비용 절감)
    - Network Volume으로 모델 캐시 (Cold Start 최소화)
"""
import base64
import math
import tempfile
import os

# [2026-03-02] HuggingFace 모델 캐시를 Network Volume에 저장
# 첫 Cold Start 시 모델 다운로드 → /runpod-volume/hf_cache/에 저장
# 이후 Cold Start 시 캐시에서 로딩 → 모델 다운로드 시간(~90초) 절약
os.environ["HF_HOME"] = "/runpod-volume/hf_cache"

import runpod
from faster_whisper import WhisperModel


# =============================================================================
# 모델 로드 — 핸들러 밖에서 실행하여 Warm Start 시 재사용
# =============================================================================
# Network Volume 경로: /runpod-volume 에 모델 캐시가 저장됨
# large-v3: 가장 높은 정확도, GPU(CUDA) + float16으로 최대 속도
MODEL_SIZE = "large-v3"
print(f"[STT Handler] {MODEL_SIZE} 모델 로딩 중...")
model = WhisperModel(MODEL_SIZE, device="cuda", compute_type="float16")
print(f"[STT Handler] {MODEL_SIZE} 모델 로드 완료 — 요청 대기 중")


def handler(job):
    """
    RunPod Serverless 핸들러 진입점

    [2026-03-01] FastAPI 방식에서 Serverless 방식으로 전환
    - base64 오디오 수신 → 임시 파일 디코딩 → faster-whisper 변환
    - 응답 필드명을 클라이언트(transcriber.py)와 통일: transcript, confidence, language

    Args:
        job (dict): RunPod이 전달하는 작업 객체
            job["input"]["audio_base64"] (str): base64 인코딩된 오디오 데이터 (필수)
            job["input"]["language"] (str): 인식 언어 (선택, 기본값 "ko")

    Returns:
        dict: {
            "transcript": str,    # 변환된 텍스트
            "confidence": float,  # 신뢰도 (0.0 ~ 1.0, avg_logprob 기반)
            "language": str,      # 감지된 언어 코드
        }
        또는 에러 시:
        dict: {"error": str}
    """
    job_input = job.get("input", {})
    audio_base64 = job_input.get("audio_base64")

    # ── 입력 검증 ──────────────────────────────────────────────────────
    if not audio_base64:
        return {"error": "audio_base64 필드가 비어있습니다."}

    # 클라이언트에서 전달하는 language 파라미터 (기본값: 한국어)
    language = job_input.get("language", "ko")

    try:
        # ── 1. Base64 디코딩 ──────────────────────────────────────────
        audio_bytes = base64.b64decode(audio_base64)

        # ── 2. 임시 파일 저장 ─────────────────────────────────────────
        # tempfile 사용: 동시 요청 시 파일 경로 충돌 방지
        # suffix=".webm": 브라우저 MediaRecorder가 webm 형식으로 녹음
        # delete=False: transcribe 완료 후 수동 삭제 (with 블록 밖에서 사용 가능)
        tmp = tempfile.NamedTemporaryFile(suffix=".webm", delete=False)
        try:
            tmp.write(audio_bytes)
            tmp.flush()
            tmp.close()

            # ── 3. faster-whisper STT 실행 ────────────────────────────
            # transcriber.py의 _transcribe_local()과 동일한 옵션 적용
            #   - language: 클라이언트 지정 언어 (기본 "ko")
            #   - beam_size=5: 빔 서치 폭 (정확도 ↑)
            #   - best_of=5: 후보 중 최선 선택 (정확도 ↑)
            #   - temperature=0.0: 결정론적 디코딩 (hallucination 방지)
            #   - condition_on_previous_text=False: 이전 세그먼트 의존 제거 (반복 방지)
            #   - vad_filter=True: 무음 구간 자동 스킵
            #   - min_silence_duration_ms=500: 0.5초 이상 무음 시 세그먼트 분리
            segments, info = model.transcribe(
                tmp.name,
                language=language,
                beam_size=5,
                best_of=5,
                temperature=0.0,
                condition_on_previous_text=False,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500),
            )

            # ── 4. 세그먼트 결합 + 신뢰도 계산 ───────────────────────
            # transcriber.py의 _transcribe_local()과 동일한 로직
            texts = []
            logprobs = []
            for segment in segments:
                text = segment.text.strip()
                if text:
                    texts.append(text)
                    logprobs.append(segment.avg_logprob)

            transcript = " ".join(texts).strip()

            # avg_logprob → 확률 변환 (exp 함수)
            # logprob이 0에 가까울수록 신뢰도 1.0, 음수가 클수록 낮아짐
            if logprobs:
                avg_logprob = sum(logprobs) / len(logprobs)
                confidence = round(min(1.0, max(0.0, math.exp(avg_logprob))), 3)
            else:
                confidence = 0.0

        finally:
            # ── 5. 임시 파일 정리 ─────────────────────────────────────
            os.unlink(tmp.name)

        # ── 6. 결과 반환 ─────────────────────────────────────────────
        # 필드명: transcript, confidence, language
        # → 클라이언트(transcriber.py)의 _transcribe_remote() 응답 규격과 일치
        return {
            "transcript": transcript,
            "confidence": confidence,
            "language": info.language,
        }

    except Exception as e:
        print(f"[STT Handler] 변환 오류: {e}")
        return {"error": str(e)}


# =============================================================================
# Serverless 서비스 시작
# =============================================================================
# RunPod이 이 엔트리포인트를 호출하여 워커를 실행
# 기존 FastAPI + uvicorn 방식 대비:
#   - 요청 없으면 워커 0으로 자동 스케일 다운 (비용 절감)
#   - Network Volume에 모델 캐시되어 Cold Start 최소화
runpod.serverless.start({"handler": handler})