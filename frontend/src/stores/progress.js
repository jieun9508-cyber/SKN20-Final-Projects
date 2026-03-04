import { defineStore } from 'pinia';
import axios from 'axios';


export const useProgressStore = defineStore('progress', {
    state: () => ({
        // 유닛별 전체 진행도 (UserProgress 모델 데이터)
        unitProgresses: [],
        // 개별 문제 해결 및 최고 점수 기록 (UserSolvedProblem 모델 데이터)
        solvedRecords: [],
        isLoading: false,
        error: null,
    }),

    // [수정일: 2026-02-24] Antigravity - LocalStorage 진행도를 서버 기반으로 마이그레이션
    actions: {
        // 1. 유저의 전체 진행 상태 서버에서 불러오기
        async fetchAllProgress() {
            this.isLoading = true;
            this.error = null;
            try {
                // UserProgress 조회
                const progressRes = await axios.get('/api/core/activity/progress/');
                this.unitProgresses = progressRes.data;

                // UserSolvedProblem 조회
                const solvedRes = await axios.get('/api/core/activity/solved-problems/');
                this.solvedRecords = solvedRes.data;

            } catch (err) {
                console.error('Failed to fetch user progress:', err);
                // 비로그인 상태이거나 토큰 만료 등일 때 에러 기록
                this.error = err.response?.data?.error || '진행 상태를 서버에서 불러오지 못했습니다.';
            } finally {
                this.isLoading = false;
            }
        },

        // 2. 특정 유닛(Practice)의 진행 노드(Stage) 해금 시
        async unlockNode(practiceId, nodeIndex) {
            // 프론트에서 먼저 낙관적 업데이트
            const existing = this.unitProgresses.find(p => p.unit_id === practiceId);
            const targetIndex = Number(nodeIndex);
            let newNodes = [targetIndex];

            if (existing) {
                // [수정일: 2026-02-24]
                // [수정내용: new set(...) 오타로 인한 ReferenceError를 해결하기 위해 자바스크립트 내장 객체인 new Set(...)으로 수정하여 스테이지 해금 정상화]
                newNodes = [...new Set([...(existing.unlocked_nodes || []), targetIndex])].sort((a, b) => a - b);
                existing.unlocked_nodes = newNodes;
            } else {
                this.unitProgresses.push({
                    unit_id: practiceId,
                    unlocked_nodes: newNodes,
                    progress_rate: 0
                });
            }

            console.log('[ProgressStore] unlockNode:', { practiceId, nodeIndex: targetIndex, newNodes, existingFound: !!existing });

            try {
                await axios.post('/api/core/activity/progress/', {
                    practice_id: practiceId,
                    unlocked_nodes: newNodes
                });
                console.log('[ProgressStore] unlockNode POST success:', { practiceId, newNodes });
            } catch (err) {
                console.error('Failed to update unlock status:', err);
                this.error = '해금 상태를 저장하지 못했습니다.';
            }
        },

        // [수정일: 2026-02-27] 로그아웃 시 이전 사용자 진행도 초기화
        resetProgress() {
            this.unitProgresses = [];
            this.solvedRecords = [];
            this.error = null;
        },

        // [수정일: 2026-02-27] 다음 노드 해금 편의 액션
        // gameStore.unlockNextStage()의 해금 로직을 progressStore로 이전
        async unlockNextStage(practiceId, nodeIndex) {
            if (!practiceId) return;
            // 다음 노드 해금 (현재 노드는 이미 해금 상태)
            await this.unlockNode(practiceId, nodeIndex + 1);
        },

        // 3. 문제(미션) 클리어 및 점수 제출 시
        // BugHunt나 PseudocodePractice에서 클리어 시 호출합니다.
        async submitScore(detailId, score, submittedData = {}) {
            try {
                const res = await axios.post('/api/core/activity/submit/', {
                    detail_id: detailId,
                    score: Math.round(score),
                    submitted_data: submittedData
                });

                // 결과 반영 후 전체 다시 패치해서 상태 맞춰주기 (혹은 로컬 업데이트)
                await this.fetchAllProgress();

                return res.data; // { total_points, current_rank, progress_rate }
            } catch (err) {
                console.error('Failed to submit score:', err);
                this.error = '점수를 저장하지 못했습니다.';
                throw err;
            }
        }
    },

    getters: {
        // 특정 유닛의 해금 노드 목록 반환
        getUnlockedNodes: (state) => (practiceId) => {
            const p = state.unitProgresses.find(p => p.unit_id === practiceId);
            return p ? p.unlocked_nodes : [0]; // 기본적으로 0번 노드는 열림
        },

        // [수정일: 2026-02-27] unit_title 기반으로 해금 노드 목록 반환
        getUnlockedNodesByTitle: (state) => (unitTitle) => {
            const p = state.unitProgresses.find(p => p.unit_title === unitTitle);
            return p ? p.unlocked_nodes : [0];
        },

        // 특정 연습상세문제의 최고 점수 반환
        getBestScore: (state) => (detailId) => {
            const records = state.solvedRecords.filter(r => r.practice_detail === detailId);
            if (records.length === 0) return 0;
            return Math.max(...records.map(r => r.score));
        },

        // 묶음 조회가 필요한 경우 (예: BugHunt의 전체 찾은 버그 수 합산 등)
        getSubmittedDataSum: (state) => (practiceIdKeyword) => {
            // 예: detailId에 'bughunt'가 포함된 레코드들만 필터링
            return state.solvedRecords.filter(r => r.practice_detail && String(r.practice_detail).includes(practiceIdKeyword));
        }
    }
});
