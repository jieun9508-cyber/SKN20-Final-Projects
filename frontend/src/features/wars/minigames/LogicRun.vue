<template>
  <div class="logic-run" :class="{ 'shake': shaking, 'flash-ok': flashOk, 'flash-fail': flashFail, 'banana-slip': bananaSlip }">
    <!-- [2026-03-04] 오답 장애물 이모지 오버레이 -->
    <transition name="obstacle-pop">
      <div v-if="bananaSlip" class="obstacle-overlay">
        <span class="obstacle-emoji">{{ bananaEmoji }}</span>
      </div>
    </transition>
    <div class="crt-lines"></div>

    <!-- ===== INTRO ===== -->
    <div v-if="phase === 'intro'" class="intro-screen">
      <div class="intro-box">
        <div class="intro-badge">AICE 자격증 대비 모드</div>
        <h1 class="intro-title glitch" data-text="LOGIC RUN">LOGIC RUN</h1>
        <p class="intro-sub">목표 등급을 선택하고 실전문제를 풀어보세요!</p>
        <div class="intro-rules">
          <div class="rule-item">Phase 1: 스피드 퀴즈 (5라운드, 40점 만점 / 오답 감점)</div>
          <div class="rule-item">Phase 2: 의사코드 설계 (90초, 60점 만점)</div>
          <div class="rule-item">100점 만점 등급제 (S: 90+ / A: 75+ / B: 60+ / C: 40+)</div>
          <div class="rule-item">AI 평가방식: AICE 채점 기준 기반 1:1 피드백 제공</div>
        </div>
        <div class="team-select">
          <p class="team-label">AICE 자격증 등급 선택</p>
          <div class="difficulty-select neon-border">
            <button
              v-for="diff in difficultyOptions"
              :key="diff.id"
              class="btn-diff"
              :class="{ active: selectedDifficulty === diff.id }"
              @click="selectedDifficulty = diff.id"
            >
              {{ diff.label }}
            </button>
          </div>
          
          <p class="team-label" style="margin-top: 1rem;">방 관리 (1대1 경쟁)</p>
          <div class="room-input-group">
            <input v-model="inputRoomId" placeholder="방 번호 입력..." class="room-input" @keyup.enter="joinRoom" />
            <button @click="joinRoom" class="btn-join">입장/변경</button>
          </div>
          <div v-if="roomId" class="battle-lobby-info">
            <div class="battle-lobby-card">
              <template v-if="rs.roomPlayers.value[0]">
                <img :src="rs.roomPlayers.value[0].avatar_url || '/image/duck_idle.png'" class="lobby-avatar" />
                <div class="lobby-name p1">{{ rs.roomPlayers.value[0].name }}</div>
                <div class="lobby-diff neon-text" style="font-size: 0.75rem; margin-top: 4px; color: #a8b2c1;">
                  {{ rs.roomPlayers.value[0].difficulty || '선택 안 됨' }}
                </div>
              </template>
              <div v-else class="lobby-slot-empty">P1 대기중...</div>
            </div>

            <div class="battle-vs">VS</div>

            <div class="battle-lobby-card">
              <template v-if="rs.roomPlayers.value[1]">
                <img :src="rs.roomPlayers.value[1].avatar_url || '/image/duck_idle.png'" class="lobby-avatar" />
                <div class="lobby-name p2">{{ rs.roomPlayers.value[1].name }}</div>
                <div class="lobby-diff neon-text" style="font-size: 0.75rem; margin-top: 4px; color: #a8b2c1;">
                  {{ rs.roomPlayers.value[1].difficulty || '선택 안 됨' }}
                </div>
              </template>
              <div v-else class="lobby-slot-empty">
                <div class="hourglass">⏳</div>
                대기 중...
              </div>
            </div>
          </div>
        </div>
        
        <!-- [추가] AI 문제 생성 중 표시 -->
        <div v-if="isStarting && !rs.gameStarted.value" class="ai-generating-box">
          <div class="spinner-small"></div>
          <div class="gen-msg neon-c">{{ genProgressMsg || 'AI 문제 생성 중...' }}</div>
        </div>
        <button v-else
          @click="requestStart" 
          class="btn-start blink-border" 
          :disabled="!rs.connected.value || rs.roomPlayers.value.length < 2 && false"
        >
          ▶ START GAME
        </button>
        <button @click="$router.push('/practice/wars')" class="btn-exit-lobby">← 나가기</button>

        <!-- [추가] 에러 메시지(토스트) 표시 -->
        <div v-if="errorMsg" class="error-toast">{{ errorMsg }}</div>
      </div>
    </div>

    <!-- ===== PLAY: PHASE 1 (SPEED FILL) ===== -->
    <div v-if="phase === 'play' && currentGamePhase === 'speedFill'" class="game-screen phase1">
      <!-- 상단 HUD: 점수 & 라운드 & 타이머 -->
      <div class="hud">
        <div class="hud-cell">
          <span class="hud-lbl">P1 SCORE</span>
          <span class="hud-val neon-c">{{ scoreP1 }}점</span>
        </div>
        <div class="hud-cell">
          <span class="hud-lbl">R{{ currentRound + 1 }}/{{ totalRounds }}</span>
          <span class="hud-badge">SPEED FILL</span>
        </div>
        <div class="hud-cell">
          <span class="hud-lbl">P2 SCORE</span>
          <span class="hud-val neon-y">{{ scoreP2 }}점</span>
        </div>
      </div>

      <!-- 게임 영역: Phase 1 -->
      <div class="game-area phase1-layout">
        <!-- 좌측: 게임 화면 -->
        <div class="game-left">
          <!-- ← 수정: 각 플레이어 중심 화면 -->
          <div class="runner-stage dual-track">
            <!-- 상단: 상대 레인 -->
            <div class="lane opponent-lane" :class="isP1 ? 'p2-lane' : 'p1-lane'">
              <div class="lane-label">👥 상대</div>
              <div class="runner-char" :style="{ left: opponentProgressPct + '%' }" :class="{ running: true }">
                <!-- ← [수정: 2026-03-04] 접속한 닉네임 표기 추가 -->
                <div class="runner-name opponent-name">{{ opponentName }}</div>
                <img :src="(isP1 ? playerP2?.avatarUrl : playerP1?.avatarUrl) || '/image/duck_idle.png'" class="main-avatar" />
                <div class="dust-effect"></div>
              </div>
            </div>

            <!-- 하단: 내 레인 -->
            <div class="lane my-lane" :class="isP1 ? 'p1-lane' : 'p2-lane'">
              <div class="runner-char" :style="{ left: myProgressPct + '%' }" :class="{ running: true, stumble: stumbling }">
                <!-- ← [수정: 2026-03-04] 접속한 닉네임 표기 추가 -->
                <div class="runner-name my-name">{{ myName }}</div>
                <img :src="(isP1 ? playerP1?.avatarUrl : playerP2?.avatarUrl) || '/image/duck_idle.png'" class="main-avatar" />
                <div class="dust-effect"></div>
              </div>
              <div class="lane-label">🎮 나</div>
            </div>

            <!-- 결승선 -->
            <div class="finish-line"></div>
          </div>

          <!-- 컨텍스트 정보: 라운드 진행 + 카테고리 힌트 -->
          <div class="line-info">
            <span class="line-badge">{{ currentRound + 1 }} / {{ totalRounds }}</span>
            <span class="round-progress-bar">
              <span
                v-for="i in totalRounds" :key="i"
                class="round-dot"
                :class="{ done: i <= currentRound, current: i === currentRound + 1 }"
              ></span>
            </span>
            <span class="context-text">🎯 {{ selectedDifficulty }} &nbsp;·&nbsp; {{ currentQuest?.title?.slice(0, 24) || 'AICE 실전 퀴즈' }}</span>
          </div>
        </div>

        <!-- 우측: 빈칸 채우기 패널 -->
        <div class="game-right">
          <!-- 4지선다형 객관식 문제 패널 -->
          <div class="code-block-panel neon-border aice-quiz-panel">
            <div class="editor-header">
              <div class="editor-tabs">
                <div class="tab active">AICE 실전 퀴즈</div>
              </div>
              <div class="editor-meta">MULTIPLE CHOICE</div>
            </div>

            <!-- 문제 텍스트 (AICE 문제) -->
            <div class="quiz-question-display">
              <h3 class="question-text">{{ currentRoundData?.context }}</h3>
            </div>

            <!-- 보기 (4지선다) -->
            <div class="quiz-options-area">
              <div class="option-buttons-grid">
                <button
                  v-for="(opt, oIdx) in (currentRoundData?.options || [])"
                  :key="oIdx"
                  @click="selectOptionAnswer(oIdx)"
                  class="btn-option quiz-btn"
                >
                  <span class="opt-num">{{ oIdx + 1 }}</span>. {{ opt }}
                </button>
              </div>
            </div>

            <div class="editor-footer">
              <div class="ef-left">AICE 실전 대비</div>
              <div class="ef-right">
                <span class="combo-display" v-if="currentCombo > 0">🔥 x{{ currentCombo }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ===== PLAY: PHASE 2 (DESIGN SPRINT) ===== -->
    <div v-if="phase === 'play' && currentGamePhase === 'designSprint'" class="game-screen phase2">
      <!-- 상태별 HUD 표시 -->
      <div v-if="phase2Status === 'editing'" class="hud">
        <div class="hud-cell flex-grow">
          <span class="hud-lbl">DESIGN SPRINT</span>
          <span class="hud-val neon-c">{{ myChecksCompleted }}/{{ totalChecks }} checks</span>
        </div>
        <div class="hud-cell timer-cell" :class="{ danger: roundTimeout <= 15 }">
          <div class="timer-bar-track">
            <div class="timer-bar-fill" :style="{ width: roundTimeoutPct + '%' }" :class="{ danger: roundTimeout <= 15 }"></div>
          </div>
          <span class="timer-num">{{ roundTimeout }}s</span>
        </div>
        <div class="hud-cell flex-grow">
          <span class="hud-lbl">OPP PROGRESS</span>
          <span class="hud-val neon-y">{{ oppChecksCompleted }}/{{ totalChecks }} checks</span>
        </div>
      </div>

      <!-- 대기 상태 HUD -->
      <div v-else-if="phase2Status === 'waiting'" class="hud waiting-hud">
        <div class="hud-cell flex-grow">
          <span class="hud-lbl">📤 YOU SUBMITTED</span>
          <span class="hud-val neon-c">{{ myEvaluation?.checkCount }}/{{ totalChecks }} checks</span>
        </div>
        <div class="hud-cell timer-cell" :class="{ danger: phase2WaitingTimeout <= 10 }">
          <div class="timer-bar-track">
            <div class="timer-bar-fill" :style="{ width: (phase2WaitingTimeout / 30) * 100 + '%' }" :class="{ danger: phase2WaitingTimeout <= 10 }"></div>
          </div>
          <span class="timer-num">{{ phase2WaitingTimeout }}s</span>
        </div>
        <div class="hud-cell flex-grow">
          <span class="hud-lbl">{{ opponentSubmitted ? '✅ OPPONENT SUBMITTED' : '⏳ WAITING FOR OPPONENT' }}</span>
          <span class="hud-val" :class="{ 'neon-y': opponentSubmitted }">{{ opponentSubmitted ? '제출됨' : 'Waiting...' }}</span>
        </div>
      </div>

      <!-- 게임 영역: Phase 2 -->
      <div class="game-area phase2-layout">
        <!-- 편집 중인 상태 -->
        <template v-if="phase2Status === 'editing'">
          <!-- 좌측: 시나리오 & 체크리스트 -->
          <div class="game-left phase2-left">
            <!-- 시나리오 박스 -->
            <div class="scenario-box neon-border">
              <div class="scenario-header">📋 시나리오</div>
              <div class="scenario-text">{{ currentDesignScenario }}</div>
            </div>

            <!-- 체크리스트 -->
            <div class="checklist-panel">
              <div class="checklist-header">✓ 평가 체크리스트</div>
              <div class="checklist-items">
                <div
                  v-for="check in checklistItems"
                  :key="check.id"
                  class="check-item"
                  :class="{ checked: completedChecks.includes(check.id) }"
                >
                  <span class="check-box">{{ completedChecks.includes(check.id) ? '✅' : '⬜' }}</span>
                  <span class="check-label">{{ check.label }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- 우측: 코드 에디터 -->
          <div class="game-right phase2-right">
            <div class="editor-panel neon-border">
              <div class="editor-header">
                <div class="editor-tabs">
                  <div class="tab active">design_solution.ps</div>
                </div>
                <div class="editor-meta">PSEUDOCODE DESIGN</div>
              </div>

              <div class="editor-body scrollbar">
                <textarea
                  ref="designEditor"
                  v-model="designCode"
                  class="design-textarea"
                  placeholder="핵심 의사코드를 입력하세요..."
                  spellcheck="false"
                ></textarea>
              </div>

              <div class="editor-footer">
                <div class="ef-left">UTF-8 | Pseudocode</div>
                <div class="ef-right">
                  <span class="err-msg" v-if="errorMsg">⚠️ {{ errorMsg }}</span>
                  <button class="btn-ide-submit" @click="submitDesign" :disabled="roundTimeout <= 0">SUBMIT ↵</button>
                </div>
              </div>
            </div>
          </div>
        </template>

        <!-- 대기 중인 상태 -->
        <template v-else-if="phase2Status === 'waiting'">
          <!-- 좌측: 내 평가 -->
          <div class="game-left phase2-left">
            <div class="scenario-box neon-border waiting-box">
              <div class="scenario-header">🎯 YOUR SUBMISSION</div>
              <div class="code-preview-container">
                <div class="code-preview">{{ myEvaluation?.code || '' }}</div>
                <div class="eval-summary">
                  <div class="eval-item">✅ Checks: {{ myEvaluation?.checkCount }}/{{ totalChecks }}</div>
                  <div class="eval-item">⭐ Points: {{ myEvaluation?.totalPoints }}</div>
                </div>
              </div>
            </div>
          </div>

          <!-- 우측: 상대 평가 (제출되었을 때) -->
          <div class="game-right phase2-right">
            <div v-if="opponentSubmitted" class="editor-panel neon-border opponent-box">
              <div class="editor-header">
                <div class="editor-tabs">
                  <div class="tab active">opponent_code.ps</div>
                </div>
                <div class="editor-meta">OPPONENT CODE</div>
              </div>

              <div class="editor-body scrollbar">
                <div class="code-preview">{{ opponentCode || 'Waiting...' }}</div>
              </div>

              <div class="editor-footer">
                <div class="ef-left">UTF-8 | Pseudocode</div>
              </div>
            </div>
            <div v-else class="waiting-panel">
              <div class="wait-icon">⏳</div>
              <div class="wait-text">상대 플레이어의 제출을 기다리는 중...</div>
              <div class="wait-timer">{{ phase2WaitingTimeout }}초 후 자동 완료</div>
            </div>
          </div>
        </template>

        <!-- 평가 완료 후 결과화면 로딩 -->
        <template v-else-if="phase2Status === 'evaluated'">
          <div class="game-area-loading">
            <div class="loading-spinner-box">
              <div class="spinner"></div>
              <div class="loading-text">게임 결과 계산 중...</div>
              <div class="loading-subtext">AI 평가가 진행되고 있습니다</div>
            </div>
          </div>
        </template>
      </div>
    </div>

    <!-- ===== RESULT ===== -->
    <transition name="zoom">
      <div v-if="phase === 'result'" class="overlay">
        <div class="result-box" :class="resultClass">
          <div class="r-icon">{{ resultIcon }}</div>
          <h1 class="r-title">{{ resultTitle }}</h1>
          <!-- 각 플레이어의 입장에서 자신이 좌측에 표시 (isP1 기반, 타이밍 이슈 없음) -->
          <div class="r-scores">
            <!-- 나 (좌측) -->
            <div class="score-item my-score" :class="isP1 ? 'p1' : 'p2'">
              <span class="p-name">🎮 나</span>
              <div class="score-breakdown">
                <div class="score-part">
                  Phase1: {{ myPhase1Score }} | Phase2: {{ myPhase2Score }}
                </div>
                <div class="score-total">{{ myTotalScore }}</div>
              </div>
            </div>
            <span class="vs">VS</span>
            <!-- 상대 (우측) -->
            <div class="score-item opponent-score" :class="isP1 ? 'p2' : 'p1'">
              <span class="p-name">👥 상대</span>
              <div class="score-breakdown">
                <div class="score-part">
                  Phase1: {{ oppPhase1Score }} | Phase2: {{ oppPhase2Score }}
                </div>
                <div class="score-total">{{ opponentTotalScore }}</div>
              </div>
            </div>
          </div>
          <div class="r-detail">{{ resultDetail }} | 등급: {{ resultGrade }}</div>

          <!-- ← 추가: LLM 평가 섹션 -->
          <div v-if="llmEvaluationP1 || llmEvaluationP2" class="llm-section">
            <div class="llm-header">🎓 AI 코드 평가</div>

            <!-- P1 평가 -->
            <div v-if="llmEvaluationP1" class="llm-item p1-eval">
              <div class="eval-player">{{ playerP1?.name }}</div>
              <div class="eval-score">
                <span class="score-badge">{{ llmEvaluationP1.llm_score }}/100</span>
                <span class="grade-badge" :class="'grade-' + llmEvaluationP1.grade">{{ llmEvaluationP1.grade }}</span>
              </div>
              <div class="eval-feedback">{{ llmEvaluationP1.feedback }}</div>
              <div v-if="llmEvaluationP1.strengths" class="eval-details">
                <div class="detail-row">✨ <strong>강점:</strong> {{ llmEvaluationP1.strengths.join(', ') }}</div>
              </div>
              <div v-if="llmEvaluationP1.weaknesses" class="eval-details">
                <div class="detail-row">⚠️ <strong>개선점:</strong> {{ llmEvaluationP1.weaknesses.join(', ') }}</div>
              </div>
            </div>

            <!-- P2 평가 -->
            <div v-if="llmEvaluationP2" class="llm-item p2-eval">
              <div class="eval-player">{{ playerP2?.name }}</div>
              <div class="eval-score">
                <span class="score-badge">{{ llmEvaluationP2.llm_score }}/100</span>
                <span class="grade-badge" :class="'grade-' + llmEvaluationP2.grade">{{ llmEvaluationP2.grade }}</span>
              </div>
              <div class="eval-feedback">{{ llmEvaluationP2.feedback }}</div>
              <div v-if="llmEvaluationP2.strengths" class="eval-details">
                <div class="detail-row">✨ <strong>강점:</strong> {{ llmEvaluationP2.strengths.join(', ') }}</div>
              </div>
              <div v-if="llmEvaluationP2.weaknesses" class="eval-details">
                <div class="detail-row">⚠️ <strong>개선점:</strong> {{ llmEvaluationP2.weaknesses.join(', ') }}</div>
              </div>
            </div>
          </div>

          <!-- [추가 2026-02-27] AI 포트폴리오 글 생성 -->
          <PortfolioWriter
            game-type="logic"
            :scenario="currentDesignScenario"
            :my-score="myTotalScore"
            :opponent-score="opponentTotalScore"
            :result-text="myTotalScore > opponentTotalScore ? 'WIN' : myTotalScore < opponentTotalScore ? 'LOSE' : 'DRAW'"
            :grade="resultGrade"
            :pseudocode="mySubmittedCode"
            :phase1-score="myPhase1Score"
            :phase2-score="myPhase2Score"
            :strengths="myLlmEval?.strengths || []"
            :weaknesses="myLlmEval?.weaknesses || []"
            :ai-review="myLlmEval?.feedback || ''"
          />

          <!-- 기존 export -->
          <div class="lr-portfolio">
            <div class="lr-pf-title">🎓 내 의사코드 경험을 포트폴리오로</div>
            <div class="lr-pf-preview" ref="logicPortfolioCard">
              <div class="lrpf-badge">📝 PSEUDOCODE DESIGN</div>
              <div class="lrpf-scenario">{{ currentDesignScenario || '실무 위기 시나리오 기반 의사코드 작성' }}</div>
              <div class="lrpf-code" v-if="mySubmittedCode">{{ mySubmittedCode.slice(0, 200) }}{{ mySubmittedCode.length > 200 ? '\n...' : '' }}</div>
              <div class="lrpf-scores">
                <span class="lrpf-sl">P1</span><span class="lrpf-sv neon-c">{{ myPhase1Score }}</span>
                <span class="lrpf-sl">P2</span><span class="lrpf-sv neon-y">{{ myPhase2Score }}</span>
                <span class="lrpf-sl">TOTAL</span><span class="lrpf-sv" style="color:#ffe600">{{ myTotalScore }}</span>
                <span class="lrpf-sl">GRADE</span><span class="lrpf-sv" :style="{ color: resultGrade === 'A' || resultGrade === 'S' ? '#00f0ff' : '#94a3b8' }">{{ resultGrade }}</span>
              </div>
              <div v-if="myLlmEval?.feedback" class="lrpf-ai">
                <span class="lrpf-ai-label">🤖 AI:</span>
                <span>{{ myLlmEval.feedback.slice(0, 80) }}{{ myLlmEval.feedback.length > 80 ? '...' : '' }}</span>
              </div>
              <div class="lrpf-footer">Wars · LogicRun · {{ lrTodayStr }}</div>
            </div>
            <div class="lr-pf-actions">
              <button class="go-pf-btn cyan" @click="lrExportImage">🖼️ 이미지 저장</button>
              <button class="go-pf-btn purple" @click="lrExportText">📋 클립보드 복사</button>
              <button class="go-pf-btn gray" @click="lrDownloadTxt">📄 텍스트 저장</button>
            </div>
            <div v-if="lrCopyToast" class="go-pf-toast">✅ 클립보드에 복사됐어요!</div>
          </div>

          <div class="go-btns">
            <button @click="startGame" class="btn-retry">🔄 다시하기</button>
            <button @click="$router.push('/practice/wars')" class="btn-exit">🏠 나가기</button>
          </div>
        </div>
      </div>
    </transition>

    <!-- 플로팅 팝업 -->
    <transition-group name="fpop" tag="div" class="fpop-layer">
      <div v-for="f in fpops" :key="f.id" class="fpop-item" :style="f.style">{{ f.text }}</div>
    </transition-group>
  </div>
</template>

<script setup>
// 수정일: 2026-02-25
// 수정내용: 2단계 하이브리드 게임 (Phase1: 빈칸 채우기 + Phase2: 설계 스프린트)
// 평가방식: 수도코드 평가방식(체크리스트 기반)

import { ref, computed, watch, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { logicQuests } from '../data/logicQuests.js'
import { addBattleRecord } from '../useBattleRecord.js'
import axios from 'axios'
import PortfolioWriter from '../components/PortfolioWriter.vue'

const router = useRouter()
const auth = useAuthStore()

// AICE 난이도 선택 추가
const selectedDifficulty = ref('Associate')
const difficultyOptions = [
  { id: 'Basic', label: 'Basic' },
  { id: 'Associate', label: 'Associate' },
  { id: 'Professional', label: 'Professional' }
]

// ─── 멀티플레이어 소켓 ───────────────────────────────
import { useRunSocket } from '../composables/useRunSocket'
const rs = useRunSocket()
const inputRoomId = ref('9999')
const roomId = ref('')

const isStarting = ref(false)

// 방 입장
// ========== [추가 2026-02-27] 포트폴리오 export ==========
const logicPortfolioCard = ref(null)
const lrCopyToast = ref(false)
const lrTodayStr = new Date().toISOString().slice(0, 10)

// 내가 제출한 코드 (phase2 waiting 상태에서 저장된것 또는 myEvaluation에서)
const mySubmittedCode = computed(() => myEvaluation.value?.code || designCode.value || '')

// 내 LLM 평가 (isP1 기반으로 llmEvaluationP1 또는 P2)
const myLlmEval = computed(() => isP1.value ? llmEvaluationP1.value : llmEvaluationP2.value)

const lrBuildText = () => {
  const scenario = currentDesignScenario.value || '실무 위기 시나리오 기반 의사코드 작성'
  const code = mySubmittedCode.value
  const llm = myLlmEval.value
  return [
    `🎓 [Wars 로직 런 포트폴리오]`,
    ``,
    `📋 시나리오: ${scenario}`,
    ``,
    `📝 내가 작성한 의사코드:`,
    code ? code.split('\n').map(l => `  ${l}`).join('\n') : '  (작성한 코드 없음)',
    ``,
    `📊 결과`,
    `  Phase1 (스피드 퀴즈): ${myPhase1Score.value}점 / 40점`,
    `  Phase2 (설계 스프린트): ${myPhase2Score.value}점 / 60점`,
    `  총점: ${myTotalScore.value}점 / 100점  |  등급: ${resultGrade.value}`,
    ``,
    llm ? [
      `🤖 AI 코드 평가 (${llm.llm_score}/100 · ${llm.grade})`,
      `  ${llm.feedback}`,
      llm.strengths?.length ? `  ✨ 강점: ${llm.strengths.join(', ')}` : '',
      llm.weaknesses?.length ? `  ⚠️ 개선점: ${llm.weaknesses.join(', ')}` : '',
    ].filter(Boolean).join('\n') : '',
    ``,
    `🔗 Powered by Wars — 실무 의사코드 AI 실습 플랫폼`,
    `📅 ${lrTodayStr}`
  ].filter(l => l !== '').join('\n')
}

const lrExportImage = () => {
  const card = logicPortfolioCard.value
  if (!card) return
  const canvas = document.createElement('canvas')
  const scale = 2
  const rect = card.getBoundingClientRect()
  canvas.width = rect.width * scale
  canvas.height = rect.height * scale
  const ctx = canvas.getContext('2d')
  ctx.scale(scale, scale)
  const W = rect.width, H = rect.height

  // 배경
  const bg = ctx.createLinearGradient(0, 0, W, H)
  bg.addColorStop(0, '#030712'); bg.addColorStop(1, '#0a0f1e')
  ctx.fillStyle = bg; ctx.roundRect(0, 0, W, H, 12); ctx.fill()
  ctx.strokeStyle = 'rgba(255,230,0,0.3)'; ctx.lineWidth = 1.5
  ctx.roundRect(0, 0, W, H, 12); ctx.stroke()

  // 배지
  ctx.fillStyle = 'rgba(255,230,0,0.08)'; ctx.roundRect(12, 12, 175, 22, 5); ctx.fill()
  ctx.fillStyle = '#ffe600'; ctx.font = 'bold 10px monospace'
  ctx.fillText('📝 PSEUDOCODE DESIGN', 20, 27)

  // 시나리오
  ctx.fillStyle = '#94a3b8'; ctx.font = '10px sans-serif'
  const scenario = currentDesignScenario.value || '실무 시나리오 기반 의사코드'
  const sl = scenario.length > 55 ? scenario.slice(0, 55) + '...' : scenario
  ctx.fillText(sl, 12, 48)

  // 코드 블록
  const code = mySubmittedCode.value
  if (code) {
    ctx.fillStyle = '#050a10'; ctx.roundRect(12, 56, W - 24, 100, 6); ctx.fill()
    ctx.strokeStyle = 'rgba(255,230,0,0.15)'; ctx.lineWidth = 0.8
    ctx.roundRect(12, 56, W - 24, 100, 6); ctx.stroke()
    ctx.fillStyle = '#e0f2fe'; ctx.font = '9px monospace'
    const lines = code.split('\n').slice(0, 8)
    lines.forEach((line, i) => {
      const truncated = line.length > 52 ? line.slice(0, 52) + '...' : line
      ctx.fillText(truncated, 20, 72 + i * 11)
    })
    if (code.split('\n').length > 8) {
      ctx.fillStyle = '#334155'; ctx.fillText('...', 20, 72 + 8 * 11)
    }
  }

  let y = code ? 168 : 64

  // 점수 그리기
  ctx.fillStyle = '#334155'; ctx.fillRect(12, y, W - 24, 1); y += 12
  ctx.font = '10px monospace'
  const scores = [
    { l: 'P1', v: String(myPhase1Score.value), c: '#00f0ff' },
    { l: 'P2', v: String(myPhase2Score.value), c: '#ffe600' },
    { l: 'TOTAL', v: String(myTotalScore.value), c: '#ffe600' },
    { l: 'GRADE', v: resultGrade.value, c: '#00f0ff' }
  ]
  let sx = 12
  scores.forEach(s => {
    ctx.fillStyle = '#475569'; ctx.font = '8px monospace'; ctx.fillText(s.l, sx, y)
    ctx.fillStyle = s.c; ctx.font = 'bold 12px monospace'; ctx.fillText(s.v, sx, y + 13)
    sx += 52
  })
  y += 28

  // AI 평가
  const llm = myLlmEval.value
  if (llm?.feedback) {
    ctx.fillStyle = '#334155'; ctx.fillRect(12, y, W - 24, 1); y += 10
    ctx.fillStyle = '#ffe600'; ctx.font = '8px monospace'
    ctx.fillText('🤖 AI ' + (llm.llm_score || '') + '/100', 12, y)
    ctx.fillStyle = '#64748b'; ctx.font = '9px sans-serif'
    const fb = llm.feedback.length > 65 ? llm.feedback.slice(0, 65) + '...' : llm.feedback
    ctx.fillText(fb, 12, y + 12); y += 24
  }

  // 푸터
  ctx.fillStyle = '#1e293b'; ctx.fillRect(0, H - 22, W, 1)
  ctx.fillStyle = '#334155'; ctx.font = '9px monospace'
  ctx.fillText('Wars · LogicRun', 12, H - 8)
  ctx.fillText(lrTodayStr, W - 68, H - 8)

  const link = document.createElement('a')
  link.download = `logic_portfolio_${lrTodayStr}.png`
  link.href = canvas.toDataURL('image/png')
  link.click()
}

const lrExportText = () => {
  const text = lrBuildText()
  try { navigator.clipboard.writeText(text) } catch {
    const ta = document.createElement('textarea')
    ta.value = text; document.body.appendChild(ta); ta.select()
    document.execCommand('copy'); document.body.removeChild(ta)
  }
  lrCopyToast.value = true
  setTimeout(() => { lrCopyToast.value = false }, 2500)
}

const lrDownloadTxt = () => {
  const text = lrBuildText()
  const blob = new Blob([text], { type: 'text/plain;charset=utf-8' })
  const link = document.createElement('a')
  link.download = `logic_portfolio_${lrTodayStr}.txt`
  link.href = URL.createObjectURL(blob)
  link.click()
  URL.revokeObjectURL(link.href)
}
// =========================================================

// 방 입장
function joinRoom() {
  if (!inputRoomId.value.trim()) return
  roomId.value = inputRoomId.value.trim()
  // [수정일: 2026-03-03] 유저 연동 복구: userId 추가 전달
  // [수정일: 2026-03-04] 같은 방에 입장하되 난이도는 별도 데이터로 전달하여 동기화
  rs.connect(roomId.value, auth.sessionNickname, auth.userAvatarUrl, auth.user?.id, selectedDifficulty.value)
}

// [2026-03-04] 로비에서 내 난이도를 변경했을 때 상대방에게 실시간 알림
watch(selectedDifficulty, (newVal) => {
  if (rs.connected.value && phase.value === 'intro') {
    rs.emitDifficultyChange(roomId.value, newVal)
  }
})

function requestStart() {
  if (!rs.connected.value) return

  const players = rs.roomPlayers.value
  if (players.length < 2) {
    errorMsg.value = '상대방이 입장해야 게임을 시작할 수 있습니다.'
    setTimeout(() => { errorMsg.value = '' }, 2500)
    shaking.value = true
    setTimeout(() => { shaking.value = false }, 400)
    return
  }

  // [2026-03-04] 등급 일치 여부 확인
  const p1Diff = players[0]?.difficulty
  const p2Diff = players[1]?.difficulty
  if (p1Diff !== p2Diff) {
    errorMsg.value = '상대방과 같은 등급을 선택해야 시작할 수 있습니다.'
    setTimeout(() => { errorMsg.value = '' }, 2500)
    shaking.value = true
    setTimeout(() => { shaking.value = false }, 400)
    return
  }

  if (!isStarting.value) {
    isStarting.value = true
    // 방 번호 그대로 시작 알림
    rs.emitStart(roomId.value)
    // 5초간 응답 없으면 다시 시도 가능하게 초기화 (안전장치)
    setTimeout(() => { if (phase.value === 'intro') isStarting.value = false }, 5000)
  }
}

// 소켓 리스너 등록
rs.onJoinError.value = (msg) => {
  alert(msg)
  roomId.value = ''
}

// [2026-03-04] AI 생성 퀘스트 저장소
const serverQuests = ref(null)

rs.onGenProgress.value = (data) => {
  console.log(`[LogicRun] AI 문제 생성: ${data.msg}`)
}

rs.onGameStart.value = (qIdx, quests) => {
  const roomPlayers = rs.roomPlayers.value
  playerP1.value = roomPlayers[0] || { name: 'P1', avatar_url: '/image/duck_idle.png', sid: '' }
  playerP2.value = roomPlayers[1] || { name: 'P2', avatar_url: '/image/duck_idle.png', sid: '' }
  // AI 생성 퀘스트가 있으면 사용
  if (quests && quests.length > 0) {
    serverQuests.value = quests
  }
  startGame(true, qIdx)
}

rs.onSync.value = (data) => {
  // ← 핵심: 게임 끝나면 점수 업데이트 금지 (버벅거림 원인)
  if (phase.value === 'result') return

  // ← ArchDrawQuiz 패턴: data.sid로 직접 상대 구분 (myIdx 인덱스 의존 제거)
  if (data.sid !== rs.socket.value?.id) {
        // Phase 1: speedFill
    if (data.phase === 'speedFill') {
      oppPhase1Score.value = data.score || 0

      // ← 상대 진행도 동기화 (오답 시에는 전진 안 함)
      if (data.correctBlanks !== undefined) {
        oppCorrectBlanks.value = data.correctBlanks
      }
    }
    // Phase 2: designSprint
    else if (data.phase === 'designSprint') {
      if (data.state === 'submitted') {
        // 상대가 제출함
        opponentSubmitted.value = true
        opponentCode.value = data.code || ''
        oppChecksCompleted.value = data.checksCompleted || 0
        oppPhase2Score.value = data.score || 0
      } else {
        // 일반 진행도 업데이트
        oppChecksCompleted.value = data.checksCompleted || 0
      }
    }
  }
}

// ← 추가: LLM 평가 결과 처리
rs.onDesignEvaluation.value = (data) => {
  // 평가는 게임 끝나기 전에 와야 함 (한 번만 처리)
  if (llmEvaluationP1.value || llmEvaluationP2.value) {
    console.log('🔒 LLM evaluation already received, ignoring duplicate')
    return
  }

  // P1 평가 결과
  if (data.player1_evaluation && data.player1_evaluation.status === 'success') {
    llmEvaluationP1.value = data.player1_evaluation
  }

  // P2 평가 결과
  if (data.player2_evaluation && data.player2_evaluation.status === 'success') {
    llmEvaluationP2.value = data.player2_evaluation
  }

  console.log('🎓 LLM Evaluation Results:', { p1: llmEvaluationP1.value, p2: llmEvaluationP2.value })
}

// ← run_end 이벤트 처리 (게임 종료 시 최종 점수 수신)
rs.onEnd.value = (data) => {
  // ← 핵심: 이미 결과 화면이라면 점수 업데이트 금지
  if (phase.value === 'result') {
    console.log('🔒 Game already ended, ignoring run_end event')
    return
  }

  // ← ArchDrawQuiz 패턴: 상대 점수를 oppPhase 변수에 직접 할당 (myIdx 불필요)
  if (data.opponent_phase1_score !== undefined) {
    oppPhase1Score.value = data.opponent_phase1_score
    oppPhase2Score.value = data.opponent_phase2_score || 0
    console.log(`✅ Opp Final Scores: Phase1=${oppPhase1Score.value}, Phase2=${oppPhase2Score.value}`)
  }
  endGame(data.result)
}

// ─── 게임 상태 ───────────────────────────────────────────
const phase = ref('intro')  // intro | play | result
const currentGamePhase = ref('speedFill')  // speedFill | designSprint
const errorMsg = ref('')
const shaking = ref(false)
const flashOk = ref(false)
const flashFail = ref(false)
const stumbling = ref(false)
const genProgressMsg = ref('')

// 플레이어 정보
const playerP1 = ref(null)
const playerP2 = ref(null)

// 점수 (my/opp 기준으로 직접 관리 - P1/P2 인덱스 의존 제거)
const myPhase1Score = ref(0)
const myPhase2Score = ref(0)
const oppPhase1Score = ref(0)
const oppPhase2Score = ref(0)

// 타임아웃
const roundTimeout = ref(0)
let roundTimeoutInterval = null
let phase2WaitingInterval = null  // Phase 2 대기 타이머

// UI
let fpopId = 0
const fpops = ref([])

// ────── PHASE 1: SPEED FILL ──────────
const totalRounds = 5
const currentRound = ref(0)
const currentRoundData = ref(null)
const currentBlankIdx = ref(0)
const currentCombo = ref(0)
const myChecksCompleted = ref(0)
const oppChecksCompleted = ref(0)

// ← 추가: 오리 위치 전진용 (맞춘 개수만)
const myCorrectBlanks = ref(0)
const oppCorrectBlanks = ref(0)

// ────── PHASE 2: DESIGN SPRINT ──────────
const designCode = ref('')
const currentDesignScenario = ref('')
const checklistItems = ref([])
const completedChecks = ref([])
const totalChecks = computed(() => checklistItems.value.length)
const designEditor = ref(null)
const phase2Status = ref('editing')  // editing | waiting | evaluated
const opponentSubmitted = ref(false)  // 상대 제출 여부
const opponentCode = ref('')  // 상대 코드

// ────── LLM 평가 결과 ──────────
const llmEvaluationP1 = ref(null)  // ← 추가: P1의 LLM 평가 결과
const llmEvaluationP2 = ref(null)  // ← 추가: P2의 LLM 평가 결과
const opponentEvaluation = ref(null)  // 상대 평가 결과
const myEvaluation = ref(null)  // 내 평가 결과
const phase2WaitingTimeout = ref(30)  // 30초 대기

// ────── 라운드 관리 ──────────
const currentQuest = ref(null)

// ────── 라운드 데이터 동적 생성 ──────────
function generateSpeedFillRounds() {
  if (!currentQuest.value) return []

  return currentQuest.value.speedRounds.map((roundData) => {
    return {
      id: roundData.round,
      context: roundData.context, // 문제 텍스트
      options: roundData.options,
      answerIdx: roundData.answerIdx,
      explanation: roundData.explanation
    }
  })
}

function generateCodeBlock(quest) {
  // blueprintSteps에서 코드 라인 추출 후 일부를 빈칸으로 변환
  const steps = quest.blueprintSteps || []
  const blocks = []

  // 제목 라인
  blocks.push({ text: quest.title + ':', type: 'fixed' })

  // 각 스텝을 2-3줄로 분해
  steps.forEach((step, stepIdx) => {
    const pseudo = step.pseudo || ''
    // Python 코드의 첫 줄을 주석으로
    blocks.push({ text: `  # ${pseudo}`, type: 'fixed' })
    const pyLine = step.python || ''
    if (pyLine.length < 80) {
      blocks.push({ text: `  ${pyLine}`, type: 'fixed' })
    }
  })

  return blocks.length > 0 ? blocks : [{ text: '# ' + quest.scenario, type: 'fixed' }]
}

function generateBlanks(quest) {
  const steps = quest.blueprintSteps || []
  const blanks = {}

  steps.slice(0, 3).forEach((step, idx) => {
    const blankId = 'b' + (idx + 1)
    // keywords에서 첫 번째를 답으로, 나머지를 옵션으로
    const keywords = step.keywords || [step.pseudo?.split(' ')[0] || '답']
    const answer = keywords[0]
    let options = [...new Set([answer, ...keywords.slice(1)])].slice(0, 4)

    // 부족한 옵션 채우기
    if (options.length < 4) {
      options = [...options, 'None', 'Pass', 'Skip'].slice(0, 4)
    }

    // ← 핵심: 옵션 순서 랜덤화 (항상 1번이 정답이던 문제 해결)
    options = shuffleArray(options)

    blanks[blankId] = {
      answer,
      options,
      hint: step.pseudo ? step.pseudo.substring(0, 50) : step.id
    }
  })

  return blanks
}

function generateBlanksOrder(quest) {
  const steps = quest.blueprintSteps || []
  return steps.slice(0, 3).map((_, idx) => 'b' + (idx + 1))
}

// ← 추가: 배열 순서 섞기 (Fisher-Yates shuffle)
function shuffleArray(array) {
  const shuffled = [...array]
  for (let i = shuffled.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]]
  }
  return shuffled
}

function getDefaultRounds() {
  return [
    {
      id: 1,
      context: '데이터 전처리 파이프라인',
      codeBlock: [
        { text: '함수 데이터_전처리(원본_데이터):', type: 'fixed' },
        { text: '  ________ 원본_데이터가 비어있으면:', type: 'blank', blankId: 'b1' },
        { text: '    반환 오류("데이터_없음")', type: 'fixed' },
      ],
      blanks: {
        b1: { answer: '만약', options: ['만약', '반복', '동안', '선택'], hint: '조건 분기 키워드' },
      },
      blanksOrder: ['b1']
    }
  ]
}

// 상단에서 이미 speedFillRounds 등을 선언해야 하므로 전역 대신 훅핑
let speedFillRounds = []

// Design Sprint 데이터 (동적 로드 함수)
function getDesignSprintData() {
  // [수정일: 2026-02-27] 후반전 데이터를 전반전에 사용한 currentQuest와 동일하게 유지
  if (!currentQuest.value) return null

  const quest = currentQuest.value

  // 체크리스트 패턴을 정규식으로 변환
  const checklist = (quest.designSprint.checklist || []).map(item => ({
    id: item.id,
    label: item.label,
    patterns: (item.patterns || []).map(p => {
      if (typeof p === 'string') {
        return new RegExp(p, 'i')
      }
      return p
    })
  }))

  return {
    scenario: quest.scenario,
    checklist,
    questId: quest.id,
    questTitle: quest.title
  }
}

let currentDesignSprintData = null

// 현재 빈칸 데이터
const currentBlankData = computed(() => {
  if (!currentRoundData.value) return null
  const blanksOrder = currentRoundData.value.blanksOrder
  const blankId = blanksOrder[currentBlankIdx.value]
  return currentRoundData.value.blanks[blankId]
})

// ← ArchDrawQuiz 패턴: socket.id로 자신이 P1인지 직접 판단 (roomPlayers 타이밍 이슈 해결)
const isP1 = computed(() => rs.socket.value?.id === playerP1.value?.sid)

// ← 플레이어별 진행도 (자신)
// 전체 빈칸 수 캐시 (이제는 객관식 1문제당 1개 진행이므로 라운드 수와 같음)
const totalSpeedFillBlanks = computed(() => {
  if (!speedFillRounds || speedFillRounds.length === 0) return 1
  return speedFillRounds.length || 1
})

// ← 0~80 범위로 제한 (출발선 정렬: 오리 너비 고려)
const myProgressPct = computed(() => {
  let raw = 0
  if (currentGamePhase.value === 'speedFill') {
    raw = (myCorrectBlanks.value / totalSpeedFillBlanks.value) * 100
  } else {
    raw = totalChecks.value === 0 ? 0 : (myChecksCompleted.value / totalChecks.value) * 100
  }
  return Math.min(80, raw)  // 최대 80%: 오리가 결승선을 넘지 않도록
})

// ← 플레이어별 진행도 (상대)
const opponentProgressPct = computed(() => {
  let raw = 0
  if (currentGamePhase.value === 'speedFill') {
    raw = (oppCorrectBlanks.value / totalSpeedFillBlanks.value) * 100
  } else {
    raw = totalChecks.value === 0 ? 0 : (oppChecksCompleted.value / totalChecks.value) * 100
  }
  return Math.min(80, raw)
})

// ← UI 렌더링용 진행도 (isP1 기반 - roomPlayers 타이밍 이슈 없음)
const p1ProgressPct = computed(() => isP1.value ? myProgressPct.value : opponentProgressPct.value)
const p2ProgressPct = computed(() => isP1.value ? opponentProgressPct.value : myProgressPct.value)

// 타임아웃 바 계산
const roundTimeoutPct = computed(() => {
  const maxTime = currentGamePhase.value === 'speedFill' ? 60 : 90
  return (roundTimeout.value / maxTime) * 100
})

// ← ArchDrawQuiz 패턴: my/opp 변수 직접 합산 (P1/P2 인덱스 불필요)
const myTotalScore = computed(() => myPhase1Score.value + myPhase2Score.value)
const opponentTotalScore = computed(() => oppPhase1Score.value + oppPhase2Score.value)

// ← HUD 표시용 P1/P2 총점 (isP1 기반)
const scoreP1 = computed(() => isP1.value ? myTotalScore.value : opponentTotalScore.value)
const scoreP2 = computed(() => isP1.value ? opponentTotalScore.value : myTotalScore.value)

// ← 각 플레이어의 이름
const myName = computed(() => (isP1.value ? playerP1.value?.name : playerP2.value?.name) || '나')
const opponentName = computed(() => (isP1.value ? playerP2.value?.name : playerP1.value?.name) || '상대')

// ← 수정: 각 플레이어 기준으로 결과 계산
const resultClass = computed(() => {
  if (myTotalScore.value > opponentTotalScore.value) return 'res-my-win'
  if (opponentTotalScore.value > myTotalScore.value) return 'res-opponent-win'
  return 'res-draw'
})

const resultIcon = computed(() => {
  if (myTotalScore.value > opponentTotalScore.value) return '🏆'
  if (opponentTotalScore.value > myTotalScore.value) return '🏆'
  return '🤝'
})

const resultTitle = computed(() => {
  if (myTotalScore.value > opponentTotalScore.value) return `🎉 나 승리!`
  if (opponentTotalScore.value > myTotalScore.value) return `😢 상대 승리`
  return '🤝 무승부!'
})

const resultDetail = computed(() => {
  return `나 ${myTotalScore.value}점 vs 상대 ${opponentTotalScore.value}점`
})

// [2026-03-04] 100점 만점 등급 기준
const resultGrade = computed(() => {
  const myScore = myTotalScore.value
  if (myScore >= 90) return 'S'
  if (myScore >= 75) return 'A'
  if (myScore >= 60) return 'B'
  if (myScore >= 40) return 'C'
  return 'F'
})

// ─── 게임 시작 ────────────────────────────────────────
function startGame(fromSocket = false, qIdx = null) {
  // [수정일: 2026-03-04] AI 생성 퀘스트 우선, 없으면 로컬 폴백 (난이도 필터링)
  if (serverQuests.value && serverQuests.value.length > 0) {
    const questIdx = typeof qIdx === 'number' ? qIdx % serverQuests.value.length : 0
    currentQuest.value = serverQuests.value[questIdx]
    console.log('[LogicRun] Using AI-generated quest:', currentQuest.value.title)
  } else if (logicQuests && logicQuests.length > 0) {
    // 선택한 AICE 등급에 맞는 문제만 필터링
    const filtered = logicQuests.filter(q => q.difficulty === selectedDifficulty.value)
    const pool = filtered.length > 0 ? filtered : logicQuests
    const questIdx = typeof qIdx === 'number' ? qIdx % pool.length
                   : Math.floor(Math.random() * pool.length)
    currentQuest.value = pool[questIdx]
    console.log(`[LogicRun] Using local quest (${selectedDifficulty.value}):`, currentQuest.value.title)
  }

  // 퀘스트가 정해지면 라운드 데이터 동기화
  speedFillRounds = generateSpeedFillRounds()

  currentGamePhase.value = 'speedFill'
  currentRound.value = 0
  currentBlankIdx.value = 0
  currentCombo.value = 0
  myCorrectBlanks.value = 0  // ← 맞춘 개수 초기화
  oppCorrectBlanks.value = 0  // ← 맞춘 개수 초기화
  myPhase1Score.value = 0
  myPhase2Score.value = 0
  oppPhase1Score.value = 0
  oppPhase2Score.value = 0
  myChecksCompleted.value = 0
  oppChecksCompleted.value = 0
  errorMsg.value = ''
  shaking.value = false
  flashOk.value = false
  flashFail.value = false
  fpops.value = []

  // Phase 2 상태 초기화
  phase2Status.value = 'editing'
  opponentSubmitted.value = false
  opponentCode.value = ''
  myEvaluation.value = null
  opponentEvaluation.value = null
  phase2WaitingTimeout.value = 30

  phase.value = 'play'
  isStarting.value = false // [수정일: 2026-03-03] 시작 완료 시점 초기화
  startPhase1Round()
}

// ─── PHASE 1: Speed Fill ──────────
function startPhase1Round() {
  if (currentRound.value >= speedFillRounds.length) {
    startPhase2()
    return
  }

  currentRoundData.value = speedFillRounds[currentRound.value]
  currentBlankIdx.value = 0
  // [2026-03-04] AICE 객관식 문제에는 시간 제한 ❌
  roundTimeout.value = 999 

  // [추가 2026-02-27] 새 라운드(타임아웃 포함)가 시작될 때 상대에게 내 진행도를 즉각 동기화
  rs.emitProgress(roomId.value, {
    phase: 'speedFill',
    correctBlanks: myCorrectBlanks.value,
    score: myPhase1Score.value,
    combo: currentCombo.value,
    sid: rs.socket.value?.id
  })

  nextTick(() => {
    // 첫 빈칸이 포커스 준비
  })
}

function selectOptionAnswer(oIdx) {
  if (!currentRoundData.value) return

  const correct = oIdx === currentRoundData.value.answerIdx

  if (correct) {
    handleBlankCorrect()
  } else {
    handleBlankWrong()
  }
}

function handleBlankCorrect() {
  // [2026-03-04] 100점 만점 체계: Phase1 = 40점 만점, 정답 +8점
  const points = 8

  currentCombo.value++
  myPhase1Score.value = Math.min(40, myPhase1Score.value + points)
  myCorrectBlanks.value++ // ← 오리 전진!

  flashOk.value = true
  setTimeout(() => { flashOk.value = false }, 300)
  // 인게임 표시는 큰 숫자로 유지 (쾌감)
  const displayPoints = 100 + (currentCombo.value > 1 ? 15 * (currentCombo.value - 1) : 0)
  spawnFpop('+' + displayPoints, '#34d399')

  // 객관식 1개 = 라운드 완료, 다음 라운드로
  currentRound.value++
  startPhase1Round()

  rs.emitProgress(roomId.value, {
    phase: 'speedFill',
    correctBlanks: myCorrectBlanks.value,
    score: myPhase1Score.value,
    combo: currentCombo.value,
    sid: rs.socket.value?.id
  })
}

// [2026-03-04] 바나나 장애물 상태
const bananaSlip = ref(false)
const bananaEmoji = ref('')

const OBSTACLE_POOL = [
  { emoji: '🍌', text: '바나나 미끔러짐!' },
  { emoji: '🪨', text: '돌에 걸려 넘어짐!' },
  { emoji: '💥', text: '장애물에 충돌!' },
  { emoji: '🌪️', text: '회오리에 휘말림!' },
  { emoji: '⚡', text: '감전! 잠시 멈춤!' },
]

function handleBlankWrong() {
  // [2026-03-04] 100점 만점 체계: 오답 -2점 (최저 0점)
  const penalty = 2
  myPhase1Score.value = Math.max(0, myPhase1Score.value - penalty)
  currentCombo.value = 0

  // [2026-03-05] 오답 시 오리 뒤로 밀림 (최소 0)
  myCorrectBlanks.value = Math.max(0, myCorrectBlanks.value - 1)

  // 오답 즉시 위치 동기화 (상대방이 오리 뒤로 가는 것 볼 수 있게)
  rs.emitProgress(roomId.value, {
    phase: 'speedFill',
    correctBlanks: myCorrectBlanks.value,
    score: myPhase1Score.value,
    combo: 0,
    sid: rs.socket.value?.id
  })

  // 바나나 장애물 연출
  const obstacle = OBSTACLE_POOL[Math.floor(Math.random() * OBSTACLE_POOL.length)]
  bananaEmoji.value = obstacle.emoji
  bananaSlip.value = true
  errorMsg.value = obstacle.text

  setTimeout(() => { errorMsg.value = '' }, 1200)
  setTimeout(() => { bananaSlip.value = false }, 1000)

  shaking.value = true
  flashFail.value = true
  setTimeout(() => {
    shaking.value = false
    flashFail.value = false
  }, 400)

  spawnFpop(`${obstacle.emoji} -${penalty}점!`, '#ef4444')
}

// ─── PHASE 2: Design Sprint ──────────
function startPhase2() {
  if (roundTimeoutInterval) clearInterval(roundTimeoutInterval)

  currentGamePhase.value = 'designSprint'

  // stages.js에서 데이터 가져오기
  currentDesignSprintData = getDesignSprintData()
  if (!currentDesignSprintData) {
    // 폴백: 기본 데이터
    currentDesignSprintData = {
      scenario: '주어진 시나리오에 따라 핵심 의사코드를 설계하세요.',
      checklist: [],
      questId: 0,
      questTitle: 'Design Sprint'
    }
  }

  currentDesignScenario.value = currentDesignSprintData.scenario
  checklistItems.value = currentDesignSprintData.checklist
  completedChecks.value = []
  designCode.value = ''
  roundTimeout.value = 90

  startRoundTimeout(90)
  nextTick(() => designEditor.value?.focus())
}

function submitDesign() {
  if (!designCode.value.trim() || roundTimeout.value <= 0) return

  evaluateDesign()
}

function evaluateDesign() {
  if (phase2Status.value === 'waiting') return  // 이미 제출됨

  const code = designCode.value

  // 체크리스트 기반 자동 평가
  // ← ArchDrawQuiz 패턴: 항상 내 점수(myPhase2Score)만 업데이트 (myIdx 불필요)
  const checkedItems = []

  for (const check of checklistItems.value) {
    for (const pattern of check.patterns) {
      if (pattern.test(code)) {
        if (!checkedItems.includes(check.id)) {
          checkedItems.push(check.id)
        }
        break
      }
    }
  }

  completedChecks.value = checkedItems

  // [2026-03-04] 100점 만점 체계: Phase2 = 60점 만점
  // 체크리스트: (통과 수 / 전체) × 45점
  // 시간 보너스: (남은 초 / 90) × 10점
  // 완료 보너스: 전부 통과 시 +5점
  const checkCount = checkedItems.length
  const checkScore = totalChecks.value > 0
    ? Math.round((checkCount / totalChecks.value) * 45)
    : 0
  const timeBonus = Math.round((Math.max(0, roundTimeout.value) / 90) * 10)
  const completionBonus = checkCount === totalChecks.value ? 5 : 0
  const totalPoints = Math.min(60, checkScore + timeBonus + completionBonus)

  myPhase2Score.value = totalPoints
  myChecksCompleted.value = checkCount

  // 내 평가 결과 저장 (로컬)
  myEvaluation.value = {
    code: code,
    checkCount: checkCount,
    totalPoints: totalPoints,
    checksCompleted: completedChecks.value
  }

  // 상태 변경: 대기 중
  phase2Status.value = 'waiting'
  phase2WaitingTimeout.value = 30

  // 동기화 및 상대 대기
  rs.emitProgress(roomId.value, {
    phase: 'designSprint',
    state: 'submitted',  // 제출됨 상태 추가
    checksCompleted: checkCount,
    totalChecks: totalChecks.value,
    score: totalPoints,
    code: code,  // 상대 코드 전달
    sid: rs.socket.value?.id
  })

  // 30초 대기 타이머 시작
  startPhase2WaitingTimeout()
}

function startPhase2WaitingTimeout() {
  if (phase2WaitingInterval) clearInterval(phase2WaitingInterval)

  phase2WaitingInterval = setInterval(() => {
    phase2WaitingTimeout.value--

    // [수정 2026-02-27] opponentCode 비어있어도 opponentSubmitted=true면 진행 (뽕힌 방지)
    const shouldFinalize = opponentSubmitted.value || phase2WaitingTimeout.value <= 0
    if (shouldFinalize) {
      clearInterval(phase2WaitingInterval)
      phase2WaitingInterval = null
      finalizePhase2()
    }
  }, 1000)
}

function finalizePhase2() {
  phase2Status.value = 'evaluated'

  setTimeout(() => {
    endGame('complete')
  }, 2000)
}

// ─── 타임아웃 관리 ────────────────────────────────
function startRoundTimeout(maxTime) {
  if (roundTimeoutInterval) clearInterval(roundTimeoutInterval)

  roundTimeoutInterval = setInterval(() => {
    roundTimeout.value--

    if (roundTimeout.value <= 0) {
      clearInterval(roundTimeoutInterval)
      if (currentGamePhase.value === 'speedFill') {
        // Phase1 타임아웃: 다음 라운드
        currentRound.value++
        startPhase1Round()
      } else {
        // Phase2 타임아웃: 평가 후 게임 종료
        evaluateDesign()
      }
    }
  }, 1000)
}

// ─── 게임 종료 ────────────────────────────────────────
function endGame(result) {
  if (roundTimeoutInterval) clearInterval(roundTimeoutInterval)
  if (phase2WaitingInterval) clearInterval(phase2WaitingInterval)
  phase.value = 'result'

  const myTotal = myTotalScore.value
  const oppTotal = opponentTotalScore.value
  const name = auth.sessionNickname || myName.value || 'Player'
  if (myTotal > oppTotal) addBattleRecord(name, 'win')
  else if (myTotal < oppTotal) addBattleRecord(name, 'lose')
  else addBattleRecord(name, 'draw')

  rs.emitLogicFinish(roomId.value, { totalScore: myTotal, result })

  // [2026-03-04] 명예의 전당 연동: Wars 점수 제출
  if (auth.isLoggedIn) {
    axios.post('/api/core/wars/submit-score/', {
      game_type: 'logic_run',
      score: myTotal,
      submitted_data: {
        difficulty: selectedDifficulty.value,
        phase1_score: myPhase1Score.value,
        phase2_score: myPhase2Score.value,
        grade: resultGrade.value,
        quest_title: currentQuest.value?.title || '',
      }
    }).catch(err => console.warn('[Wars] Score submit failed:', err.message))
  }
}

// ─── 유틸 ─────────────────────────────────────────────
function spawnFpop(text, color = '#fbbf24') {
  const id = ++fpopId
  fpops.value.push({
    id, text,
    style: { left: (30 + Math.random() * 40) + '%', color }
  })
  setTimeout(() => { fpops.value = fpops.value.filter(f => f.id !== id) }, 1200)
}

// [추가 2026-02-27] opponentSubmitted 변경 즉시 finalize 실행 (interval 타이밍 종속 방지)
watch(opponentSubmitted, (val) => {
  if (val && phase2Status.value === 'waiting') {
    if (phase2WaitingInterval) {
      clearInterval(phase2WaitingInterval)
      phase2WaitingInterval = null
    }
    finalizePhase2()
  }
})

onUnmounted(() => {
  if (roundTimeoutInterval) clearInterval(roundTimeoutInterval)
  if (phase2WaitingInterval) clearInterval(phase2WaitingInterval)
  rs.disconnect(roomId.value)
})
</script>

<style scoped>
@import './LogicRun.css';
</style>
