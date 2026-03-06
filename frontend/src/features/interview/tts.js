// alloy(중성) | nova(여성) | onyx(남성) | shimmer(부드러운 여성) | echo | fable
const DEFAULT_VOICE = 'nova'

// 재생 속도 (1.0 = 기본, 1.1~1.2 = 약간 빠르게, 0.9 = 약간 느리게)
const PLAYBACK_RATE = 1.1

class TTSManager {
    constructor() {
        this.voice = DEFAULT_VOICE;
        this.isMuted = false;
        this._currentAudio = null;
        this._queue = [];         // 재생 대기열
        this._processing = false;
        this.onQueueEmpty = null; // 큐가 모두 비었을 때 호출되는 콜백
        this.onFirstPlay = null;  // 첫 오디오가 실제로 재생될 때 1회 호출
    }

    /**
     * 텍스트를 큐에 추가. 재생 중이면 순서대로 이어서 재생.
     * Promise를 반환하여 실제 오디오 재생이 시작되는 시점을 알려준다.
     * @param {string} text
     * @returns {Promise<void>}
     */
    speak(text) {
        if (this.isMuted || !text?.trim()) return Promise.resolve();

        return new Promise((resolve) => {
            this._queue.push({
                text: text.trim(),
                onStart: resolve // 오디오가 실제로 재생 시작될 때 호출될 콜백
            });
            if (!this._processing) {
                this._processQueue();
            }
        });
    }

    async _processQueue() {
        if (this._queue.length === 0) {
            this._processing = false;
            if (this.onQueueEmpty) {
                this.onQueueEmpty();
            }
            return;
        }

        this._processing = true;
        const item = this._queue[0];
        const text = item.text;

        try {
            // [수정일: 2026-03-06] credentials 추가 (IsAuthenticated 인증용 세션 쿠키 전송)
            const response = await fetch('/api/core/tts/synthesize/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ text, voice: this.voice }),
            });

            if (!response.ok) {
                console.error('[TTS] API 오류:', response.status, await response.text());
                if (item.onStart) item.onStart(); // 블로킹 방지
                this._queue.shift();
                this._processQueue();
                return;
            }

            const audioBlob = await response.blob();
            const audioUrl = URL.createObjectURL(audioBlob);

            this._currentAudio = new Audio(audioUrl);
            this._currentAudio.playbackRate = PLAYBACK_RATE;
            this._currentAudio.onended = () => {
                URL.revokeObjectURL(audioUrl);
                this._currentAudio = null;
                this._queue.shift();
                this._processQueue();
            };

            await this._currentAudio.play();

            // 실제 재생이 성공적으로 시작된 이 시점에 Promise를 resolve하여 비디오와 강제 동기화
            if (item.onStart) {
                item.onStart();
            }

            if (this.onFirstPlay) {
                const cb = this.onFirstPlay;
                this.onFirstPlay = null;
                cb();
            }

        } catch (e) {
            console.error('[TTS] 재생 오류:', e);
            if (item.onStart) item.onStart(); // 블로킹 방지
            this._queue.shift();
            this._processQueue();
        }
    }

    get isEmpty() {
        return !this._processing && this._queue.length === 0 && !this._currentAudio;
    }

    stop() {
        this._queue = [];
        this._processing = false;
        this.onFirstPlay = null;
        if (this._currentAudio) {
            this._currentAudio.pause();
            this._currentAudio = null;
        }
    }

    setMute(muted) {
        this.isMuted = muted;
        if (muted) this.stop();
    }

    toggleMute() {
        this.setMute(!this.isMuted);
        return this.isMuted;
    }
}

export const tts = new TTSManager();
