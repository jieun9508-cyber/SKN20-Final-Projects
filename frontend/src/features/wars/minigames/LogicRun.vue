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
        <div class="intro-badge">1 vs 1 HYBRID MODE</div>
        <h1 class="intro-title glitch" data-text="LOGIC RUN">LOGIC RUN</h1>
        <p class="intro-sub">2단계 의사코드 경쟁: 속도전 + 설계전!</p>
        <div class="intro-rules">
          <div class="rule-item">⚡ Phase 1: 빈칸 채우기 (5라운드, 15초/라운드)</div>
          <div class="rule-item">🎨 Phase 2: 설계 스프린트 (핵심 의사코드 작성, 90초)</div>
          <div class="rule-item">🏆 총점으로 승리 (Phase1 60% + Phase2 40%)</div>
          <div class="rule-item">📊 수도코드 평가방식: 체크리스트 기반 채점</div>
        </div>
        <div class="team-select">
          <p class="team-label">방 관리 (1대1 경쟁)</p>
          <div class="room-input-group">
            <input v-model="inputRoomId" placeholder="방 번호 입력..." class="room-input" @keyup.enter="joinRoom" />
            <button @click="joinRoom" class="btn-join">입장/변경</button>
          </div>
          <div v-if="roomId" class="current-room-info">
            접속 중인 방: <span class="neon-c">{{ roomId }}</span>
            <div class="room-players">
              선수: <span v-for="p in rs.roomPlayers.value" :key="p.sid" class="p-tag">{{ p.name }} </span>
            </div>
          </div>
          <div v-if="rs.connected.value && !rs.isReady.value" class="lobby-info">상대방을 기다리는 중...</div>
        </div>
        <button 
          @click="requestStart" 
          class="btn-start blink-border" 
          :disabled="!rs.connected.value || rs.roomPlayers.value.length < 2 || isStarting"
        >
          {{ isStarting ? '⌛ STARTING...' : '▶ START GAME' }}
        </button>
      </div>
    </div>

    <!-- ===== PLAY: PHASE 1 (SPEED FILL) ===== -->
    <div v-if="phase === 'play' && currentGamePhase === 'speedFill'" class="game-screen phase1">
      <!-- 상단 HUD: 점수 & 라운드 & 타이머 -->
      <div class="hud">
        <div class="hud-cell">
          <span class="hud-lbl">P1 SCORE</span>
          <span class="hud-val neon-c">{{ scoreP1 }}pt</span>
        </div>
        <div class="hud-cell timer-cell" :class="{ danger: roundTimeout <= 5 }">
          <div class="timer-bar-track">
            <div class="timer-bar-fill" :style="{ width: roundTimeoutPct + '%' }" :class="{ danger: roundTimeout <= 5 }"></div>
          </div>
          <span class="timer-num">{{ roundTimeout }}s</span>
        </div>
        <div class="hud-cell">
          <span class="hud-lbl">R{{ currentRound + 1 }}/{{ totalRounds }}</span>
          <span class="hud-badge">SPEED FILL</span>
        </div>
        <div class="hud-cell timer-cell" :class="{ danger: roundTimeout <= 5 }">
          <div class="timer-bar-track">
            <div class="timer-bar-fill" :style="{ width: roundTimeoutPct + '%' }" :class="{ danger: roundTimeout <= 5 }"></div>
          </div>
          <span class="timer-num">{{ roundTimeout }}s</span>
        </div>
        <div class="hud-cell">
          <span class="hud-lbl">P2 SCORE</span>
          <span class="hud-val neon-y">{{ scoreP2 }}pt</span>
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
              <div class="runner-char" :style="{ left: opponentProgressPct + '%' }">
                <img :src="(isP1 ? playerP2?.avatarUrl : playerP1?.avatarUrl) || '/image/duck_idle.png'" class="main-avatar" />
              </div>
            </div>

            <!-- 하단: 내 레인 -->
            <div class="lane my-lane" :class="isP1 ? 'p1-lane' : 'p2-lane'">
              <div class="runner-char" :style="{ left: myProgressPct + '%' }" :class="{ running: true, stumble: stumbling }">
                <img :src="(isP1 ? playerP1?.avatarUrl : playerP2?.avatarUrl) || '/image/duck_idle.png'" class="main-avatar" />
                <div class="dust-effect"></div>
              </div>
              <div class="lane-label">🎮 나</div>
            </div>

            <!-- 결승선 -->
            <div class="finish-line">
              <div class="finish-icon">🏁</div>
            </div>
          </div>

          <!-- 컨텍스트 정보 -->
          <div class="line-info">
            <span class="line-badge">{{ currentRound + 1 }} / {{ totalRounds }}</span>
            <span class="context-text">📋 {{ currentRoundData?.context }}</span>
          </div>
        </div>

        <!-- 우측: 빈칸 채우기 패널 -->
        <div class="game-right">
          <!-- 코드 블록 -->
          <div class="code-block-panel neon-border">
            <div class="editor-header">
              <div class="editor-tabs">
                <div class="tab active">pseudocode.ps</div>
              </div>
              <div class="editor-meta">BLANK FILL</div>
            </div>

            <div class="code-display">
              <div v-for="(line, idx) in currentRoundData?.codeBlock" :key="idx" class="code-line-display">
                <span v-if="line.type === 'fixed'" class="code-text">{{ line.text }}</span>
                <!-- [수정 2026-03-04] ________를 제거하고 앞 텍스트 + 빈칸 표시 -->
                <template v-else>
                  <span class="code-text">{{ line.text.replace(/_{4,}/, '').trimEnd() }}</span>
                  <span class="code-blank-box">　　　</span>
                </template>
              </div>
            </div>

            <!-- 빈칸 정보 & 힌트 -->
            <div v-if="currentBlankData" class="blank-info">
              <div class="hint-bubble">
                <span class="hb-ico">💡</span> {{ currentBlankData.hint }}
              </div>
              <div class="option-buttons">
                <button
                  v-for="opt in currentBlankData.options"
                  :key="opt"
                  @click="selectBlankAnswer(opt)"
                  class="btn-option"
                  :disabled="roundTimeout <= 0"
                >
                  <!-- [수정 2026-03-04] 빈 문자열({}, [] 등) 방어: 김표로 대체 -->
                  {{ (opt === '' || opt === null || opt === undefined) ? '(empty)' : opt }}
                </button>
              </div>
            </div>

            <div class="editor-footer">
              <div class="ef-left">UTF-8 | Pseudocode</div>
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
import PortfolioWriter from '../components/PortfolioWriter.vue'

const router = useRouter()
const auth = useAuthStore()

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
    `  Phase1 (빠른 빈칸): ${myPhase1Score.value}pt`,
    `  Phase2 (설계 스프린트): ${myPhase2Score.value}pt`,
    `  총점: ${myTotalScore.value}  |  등급: ${resultGrade.value}`,
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

function joinRoom() {
  if (!inputRoomId.value.trim()) return
  roomId.value = inputRoomId.value.trim()
  // [수정일: 2026-03-03] 유저 연동 복구: userId 추가 전달
  rs.connect(roomId.value, auth.sessionNickname, auth.userAvatarUrl, auth.user?.id)
}

function requestStart() {
  if (rs.connected.value && rs.roomPlayers.value.length >= 2 && !isStarting.value) {
    isStarting.value = true
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
  if (!currentQuest.value) return getDefaultRounds()

  return currentQuest.value.speedRounds.map((roundData) => {
    const blanksObj = {}
    const blanksOrderInfo = []
    
    roundData.codeLines.forEach((line, lIdx) => {
      if (line.type === 'blank') {
        const bId = 'b' + (lIdx + 1)
        blanksObj[bId] = {
          answer: line.answer,
          options: shuffleArray(line.options),
          hint: '힌트'
        }
        blanksOrderInfo.push(bId)
      }
    })

    return {
      id: roundData.round,
      context: roundData.context,
      codeBlock: roundData.codeLines,
      blanks: blanksObj,
      blanksOrder: blanksOrderInfo
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
// 전체 빈칸 수 캐시 (계산 반복 방지)
const totalSpeedFillBlanks = computed(() => {
  if (!speedFillRounds || speedFillRounds.length === 0) return 1
  return speedFillRounds.reduce((sum, r) => sum + (r.blanksOrder?.length || 1), 0) || 1
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
  const maxTime = currentGamePhase.value === 'speedFill' ? 15 : 90
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
  return `나 ${myTotalScore.value}pt vs 상대 ${opponentTotalScore.value}pt`
})

const resultGrade = computed(() => {
  const myScore = myTotalScore.value
  if (myScore >= 2000) return 'S'
  if (myScore >= 1500) return 'A'
  if (myScore >= 1000) return 'B'
  if (myScore >= 500) return 'C'
  return 'F'
})

// ─── 게임 시작 ────────────────────────────────────────
function startGame(fromSocket = false, qIdx = null) {
  // [수정일: 2026-03-04] AI 생성 퀘스트 우선, 없으면 로컬 폴백
  if (serverQuests.value && serverQuests.value.length > 0) {
    const questIdx = typeof qIdx === 'number' ? qIdx % serverQuests.value.length : 0
    currentQuest.value = serverQuests.value[questIdx]
    console.log('[LogicRun] Using AI-generated quest:', currentQuest.value.title)
  } else if (logicQuests && logicQuests.length > 0) {
    const questIdx = typeof qIdx === 'number' ? qIdx % logicQuests.length 
                   : (roomId.value ? roomId.value.charCodeAt(0) % logicQuests.length 
                   : Math.floor(Math.random() * logicQuests.length));
    currentQuest.value = logicQuests[questIdx]
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
  roundTimeout.value = 15

  // [추가 2026-02-27] 새 라운드(타임아웃 포함)가 시작될 때 상대에게 내 진행도를 즉각 동기화
  rs.emitProgress(roomId.value, {
    phase: 'speedFill',
    correctBlanks: myCorrectBlanks.value,
    score: myPhase1Score.value,
    combo: currentCombo.value,
    sid: rs.socket.value?.id
  })

  startRoundTimeout(15)
  nextTick(() => {
    // 첫 빈칸이 포커스 준비
  })
}

function selectBlankAnswer(answer) {
  if (roundTimeout.value <= 0 || !currentBlankData.value) return

  const correct = answer === currentBlankData.value.answer

  if (correct) {
    handleBlankCorrect()
  } else {
    handleBlankWrong()
  }
}

function handleBlankCorrect() {
  // ← ArchDrawQuiz 패턴: 항상 내 점수(myPhase1Score)만 업데이트
  const pointsBase = 100
  const comboBonus = currentCombo.value > 0 ? 15 * currentCombo.value : 0
  const points = pointsBase + comboBonus

  currentCombo.value++
  myPhase1Score.value += points
  myCorrectBlanks.value++ // ← 오리 전진!

  flashOk.value = true
  setTimeout(() => { flashOk.value = false }, 300)
  spawnFpop('+' + points, '#34d399')

  // 다음 빈칸으로
  currentBlankIdx.value++
  const blanksOrder = currentRoundData.value.blanksOrder

  if (currentBlankIdx.value >= blanksOrder.length) {
    // 라운드 완료, 다음 라운드
    currentRound.value++
    startPhase1Round()
  }

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
  currentCombo.value = 0
  
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

  spawnFpop(`${obstacle.emoji} 오답!`, '#ef4444')
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

  // 점수 계산
  const checkCount = checkedItems.length
  const basePoints = checkCount * 100
  const completionBonus = checkedItems.length === totalChecks.value ? 200 : 0
  const timeBonus = Math.max(0, roundTimeout.value) * 3
  const totalPoints = basePoints + completionBonus + timeBonus

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
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700;900&family=Rajdhani:wght@400;600;700&family=Space+Grotesk:wght@400;600&display=swap');

/* ── 기본 ─────────────────────────────────── */
.logic-run {
  min-height: 100vh;
  background: #03070f;
  color: #e0f2fe;
  font-family: 'Rajdhani', sans-serif;
  position: relative;
  overflow: hidden;
}
.crt-lines {
  pointer-events: none;
  position: fixed; inset: 0; z-index: 9999;
  background: repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,240,255,0.01) 2px, rgba(0,240,255,0.01) 4px);
}
.shake { animation: shake .3s ease; }
.flash-ok::after { content:''; position:fixed; inset:0; background:rgba(57,255,20,.1); z-index:9000; pointer-events:none; animation:flashOut .3s forwards; }
.flash-fail::after { content:''; position:fixed; inset:0; background:rgba(255,45,117,.1); z-index:9000; pointer-events:none; animation:flashOut .3s forwards; }
@keyframes shake { 0%,100%{transform:translateX(0)} 25%{transform:translateX(-6px)} 75%{transform:translateX(6px)} }
@keyframes flashOut { from{opacity:1} to{opacity:0} }
.glitch { position:relative; font-family:'Orbitron',sans-serif; }
.glitch::before,.glitch::after { content:attr(data-text); position:absolute; top:0; left:0; width:100%; height:100%; }
.glitch::before { color:#ff2d75; clip-path:inset(0 0 65% 0); animation:g1 2s infinite linear alternate-reverse; }
.glitch::after  { color:#39ff14; clip-path:inset(65% 0 0 0);  animation:g2 2s infinite linear alternate-reverse; }
@keyframes g1 { 50%{transform:translate(-3px,2px)} }
@keyframes g2 { 50%{transform:translate(3px,-2px)} }
.neon-c { color:#00f0ff; text-shadow:0 0 8px #00f0ff; }
.neon-y { color:#ffe600; text-shadow:0 0 8px rgba(255,230,0,.5); }

/* ── INTRO ────────────────────────────────── */
.intro-screen { display:flex; align-items:center; justify-content:center; min-height:100vh; padding:2rem; }
.intro-box {
  text-align:center; max-width:580px; width:100%;
  background:rgba(8,12,30,.9); border:2px solid #00f0ff;
  border-radius:1.5rem; padding:3rem 2.5rem;
  box-shadow:0 0 60px rgba(0,240,255,.12);
}
.intro-badge { display:inline-block; font-size:.6rem; letter-spacing:3px; font-weight:700; padding:4px 14px; background:rgba(0,240,255,.08); border:1px solid rgba(0,240,255,.25); border-radius:4px; color:#00f0ff; margin-bottom:1.5rem; }
.intro-title { font-size:3rem; font-weight:900; color:#00f0ff; letter-spacing:6px; text-shadow:0 0 30px #00f0ff; margin-bottom:.5rem; }
.intro-sub { color:#64748b; letter-spacing:1px; margin-bottom:1.5rem; font-size:.95rem; }
.intro-rules { text-align:left; margin-bottom:1.5rem; }
.rule-item { font-size:.85rem; color:#94a3b8; padding:.3rem 0; border-bottom:1px solid rgba(255,255,255,.04); }
.team-select { margin-bottom:1.5rem; }
.team-label { font-size:.7rem; font-weight:700; color:#475569; letter-spacing:2px; margin-bottom:.6rem; }
.room-input-group { display: flex; gap: 8px; justify-content: center; margin-bottom: 12px; }
.room-input { background: rgba(0, 0, 0, 0.4); border: 1px solid #1e293b; color: #fff; padding: 8px 12px; border-radius: 6px; font-family: 'Orbitron', sans-serif; font-size: 0.9rem; width: 140px; text-align: center; outline: none; }
.room-input:focus { border-color: #00f0ff; box-shadow: 0 0 10px rgba(0, 240, 255, 0.2); }
.btn-join { background: rgba(0, 240, 255, 0.1); border: 1px solid rgba(0, 240, 255, 0.3); color: #00f0ff; padding: 8px 16px; border-radius: 6px; font-family: 'Orbitron', sans-serif; font-size: 0.8rem; font-weight: 700; cursor: pointer; transition: all 0.2s; }
.btn-join:hover { background: #00f0ff; color: #030712; }
.current-room-info { font-size: 0.8rem; color: #64748b; margin-top: 8px; }
.room-players { margin-top: 6px; display: flex; flex-wrap: wrap; justify-content: center; gap: 6px; }
.p-tag { font-size: 0.7rem; background: rgba(0, 240, 255, 0.05); border: 1px solid rgba(0, 240, 255, 0.1); padding: 2px 8px; border-radius: 4px; color: #38bdf8; }
.lobby-info { font-size: 0.8rem; color: #ffe600; margin-top: 10px; animation: blinkB 2s infinite; }

.btn-start { margin-top:1rem; padding:.9rem 3rem; font-family:'Orbitron',sans-serif; font-size:1rem; font-weight:900; background:transparent; border:2px solid #ffe600; color:#ffe600; border-radius:.75rem; cursor:pointer; letter-spacing:3px; transition:all .2s; }
.btn-start:hover { background:rgba(255,230,0,.08); box-shadow:0 0 30px rgba(255,230,0,.3); transform:scale(1.04); }
.blink-border { animation:blinkB 1.5s infinite; }
@keyframes blinkB { 50%{border-color:rgba(255,230,0,.3)} }

/* ── HUD ──────────────────────────────────── */
.hud {
  display:flex; align-items:center; gap:1rem;
  padding:.6rem 1.5rem; margin:.75rem 1rem 0;
  background:rgba(8,12,30,.85); border:1px solid rgba(0,240,255,.1);
  border-radius:1rem;
}
.hud-cell { display:flex; flex-direction:column; align-items:center; }
.hud-cell.flex-grow { flex:1; }
.hud-lbl { font-size:.5rem; font-weight:700; color:#475569; letter-spacing:2px; }
.hud-val { font-family:'Orbitron',sans-serif; font-size:1.1rem; font-weight:900; }
.hud-badge { font-family:'Orbitron',sans-serif; font-size:.6rem; color:#ffe600; }
.timer-cell { flex:1; }
.timer-bar-track { width:100%; height:8px; background:#0f172a; border-radius:4px; overflow:hidden; border:1px solid rgba(0,240,255,.1); }
.timer-bar-fill { height:100%; background:linear-gradient(90deg,#00f0ff,#38bdf8); border-radius:4px; transition:width 1s linear; }
.timer-bar-fill.danger { background:linear-gradient(90deg,#ff2d75,#ef4444); }
.timer-cell.danger .timer-bar-fill { background:linear-gradient(90deg,#ff2d75,#ef4444); }
.timer-num { font-family:'Orbitron',sans-serif; font-size:.75rem; color:#94a3b8; margin-top:2px; }
.timer-cell.danger .timer-num { color:#ff2d75; animation:blinkA .5s infinite; }
@keyframes blinkA { 50%{opacity:.3} }

/* ── GAME AREA ────────────────────────────── */
.game-screen { display:flex; flex-direction:column; height:calc(100vh - 80px); }
.game-area { display:grid; gap:1rem; padding:1rem; flex:1; min-height:0; overflow:hidden; }
.game-area.phase1-layout { grid-template-columns:1fr 380px; }
.game-area.phase2-layout { grid-template-columns:1fr 1fr; }

/* 좌측 */
.game-left { display:flex; flex-direction:column; gap:.75rem; }
.line-info { display:flex; align-items:center; gap:.5rem; padding:.5rem 1rem; background:rgba(8,12,30,.6); border:1px solid rgba(0,240,255,.1); border-radius:.5rem; }
.line-badge { font-family:'Orbitron',sans-serif; font-size:.7rem; font-weight:700; color:#00f0ff; }
.hint-text { font-size:.8rem; color:#64748b; flex:1; }
.context-text { font-size:.8rem; color:#94a3b8; flex:1; }

/* 달리기 스테이지 */
.runner-stage.dual-track {
  flex:1; position:relative; background:rgba(8,12,30,.8);
  border:1.5px solid rgba(0,240,255,.1); border-radius:1rem;
  overflow:hidden; min-height:220px; display: flex; flex-direction: column;
}
.lane {
  flex: 1; position: relative; display: flex; align-items: flex-end;
  padding-bottom: 8px; border-bottom: 1px dashed rgba(255,255,255,0.05);
  background: linear-gradient(0deg, rgba(255,255,255,0.02) 0%, transparent 100%);
}
.lane:last-child { border-bottom: none; }

/* ← 추가: 각 플레이어 입장 반영 */
.lane.my-lane {
  background: linear-gradient(0deg, rgba(0,240,255,0.05) 0%, transparent 100%);
  border-left: 2px solid rgba(0,240,255,0.3);
}
.lane.opponent-lane {
  background: linear-gradient(0deg, rgba(255,100,100,0.05) 0%, transparent 100%);
  border-left: 2px solid rgba(255,100,100,0.3);
}

.lane-label {
  position: absolute; top: 10px; left: 15px; font-family: 'Orbitron', sans-serif;
  font-size: 0.6rem; font-weight: 700; color: rgba(255,255,255,0.2);
  letter-spacing: 2px; pointer-events: none;
}
.p1-lane { background: rgba(0,240,255,0.03); }
.p2-lane { background: rgba(255,45,117,0.03); }

.runner-char {
  position:absolute; bottom:8px; transition:left .5s ease;
  width: 64px; height: 64px; display: flex; align-items: flex-end;
  justify-content: center;
  /* translateX(-50%) 제거: left:0% 출발선에서 양쪽 오리가 동일 위치에서 시작 */
}
/* ← 수정: 오리가 달리는 방향(오른쪽)을 바라보도록 반전 추가 */
.main-avatar { width: 56px; height: 56px; object-fit: contain; filter: drop-shadow(0 0 10px rgba(0,240,255,0.3)); transform: scaleX(-1); }
.runner-char.running { animation:runBounce .4s infinite ease-in-out; }
.runner-char.stumble { animation:stumbleAnim .3s ease; }

.finish-line {
  position: absolute; right: 20px; top: 0; bottom: 0; width: 40px;
  background: repeating-linear-gradient(45deg, #eee 0, #eee 5px, #222 5px, #222 10px);
  opacity: 0.15; display: flex; align-items: center; justify-content: center;
}
.finish-icon { font-size: 1.5rem; transform: rotate(-10deg); filter: grayscale(1); }

.dust-effect {
  position: absolute; bottom: 0; left: 0;
  width: 12px; height: 8px; background: rgba(255,255,255,0.3);
  border-radius: 50%; filter: blur(2px);
  animation: dustAnim 0.4s infinite;
}
@keyframes dustAnim {
  0% { transform: scale(1) translateX(0); opacity: 0.6; }
  100% { transform: scale(3) translateX(-40px); opacity: 0; }
}

@keyframes runBounce {
  0%,100%{transform:translateY(0) rotate(5deg) scaleX(1)}
  50%{transform:translateY(-10px) rotate(-5deg) scaleX(1.05)}
}
@keyframes stumbleAnim { 0%,100%{transform:rotate(0)} 50%{transform:rotate(-20deg)} }

/* 우측 */
.game-right { display:flex; flex-direction:column; gap:.75rem; overflow-y:auto; }

/* IDE 에디터 */
.editor-panel { background:rgba(8,12,30,.8); border:1px solid rgba(0,240,255,.15); border-radius:.75rem; overflow:hidden; display:flex; flex-direction:column; height:100%; }
.editor-header { background:#0a0f1e; padding:.75rem; border-bottom:1px solid #1e293b; display:flex; align-items:center; justify-content:space-between; }
.editor-tabs { display:flex; gap:.5rem; }
.tab { font-size:.65rem; color:#64748b; padding:.4rem .75rem; border-bottom:2px solid transparent; cursor:pointer; }
.tab.active { color:#00f0ff; border-bottom-color:#00f0ff; }
.editor-meta { font-size:.6rem; color:#475569; }
.editor-body { flex:1; background:#0f1419; overflow-y:auto; padding:.75rem; font-family:'Courier New',monospace; }
.code-line { margin-bottom:.5rem; }
.code-line.active-line { }
.hint-bubble { display:flex; align-items:center; gap:.4rem; background:rgba(59,182,254,.1); border:1px solid rgba(59,182,254,.3); border-radius:.4rem; padding:.4rem .6rem; margin-bottom:.4rem; font-size:.75rem; color:#93c5fd; }
.hb-ico { font-size:.9rem; }
.input-row { display:flex; align-items:center; gap:.4rem; }
.input-cursor { color:#00f0ff; font-weight:700; }
.editor-input { flex:1; background:transparent; border:none; color:#e0f2fe; font-family:'Courier New',monospace; font-size:.85rem; outline:none; }
.editor-footer { background:#161b22; padding:.6rem .75rem; border-top:1px solid #30363d; display:flex; justify-content:space-between; align-items:center; font-size:.65rem; color:#8b949e; }
.ef-left { }
.ef-right { display:flex; align-items:center; gap:.75rem; }
.err-msg { color:#f85149; font-weight:700; }
.btn-ide-submit { background:#238636; color:#fff; border:none; padding:4px 16px; border-radius:4px; font-family:'Orbitron',sans-serif; font-size:.65rem; font-weight:900; cursor:pointer; transition:all .2s; }
.btn-ide-submit:hover:not(:disabled) { background:#2ea043; }
.btn-ide-submit:disabled { background:#21262d; color:#484f58; cursor:not-allowed; }

.neon-border { border:1px solid rgba(0,240,255,.15) !important; }

/* ── PHASE 1: SPEED FILL ────────────────────────── */
.code-block-panel { background:rgba(8,12,30,.8); border:1px solid rgba(0,240,255,.15); border-radius:.75rem; overflow:hidden; display:flex; flex-direction:column; height:100%; }
.code-display { flex:1; background:#0f1419; overflow-y:auto; padding:1rem; font-family:'Courier New',monospace; font-size:.9rem; line-height:1.6; }
.code-line-display { margin-bottom:.4rem; }
.code-text { color:#e0f2fe; }
.code-blank { color:#fbbf24; background:rgba(251,191,36,.1); padding:0.2rem 0.4rem; border-radius:0.2rem; border-bottom:2px dashed #fbbf24; }
.code-blank-box { display:inline-block; min-width:80px; border-bottom:2px dashed #fbbf24; background:rgba(251,191,36,.08); color:#fbbf24; padding:0 0.4rem; border-radius:0.2rem; margin-left:4px; vertical-align:middle; }

.blank-info { padding:1rem; background:rgba(8,12,30,.9); border-top:1px solid rgba(0,240,255,.1); }
.option-buttons { display:grid; grid-template-columns:1fr 1fr; gap:.5rem; margin-top:.5rem; }
.btn-option { background:rgba(0,240,255,.05); border:1px solid rgba(0,240,255,.3); color:#00f0ff; padding:.6rem .8rem; border-radius:.4rem; font-family:'Orbitron',sans-serif; font-size:.75rem; font-weight:700; cursor:pointer; transition:all .2s; }
.btn-option:hover:not(:disabled) { background:rgba(0,240,255,.2); }
.btn-option:disabled { opacity:.5; cursor:not-allowed; }
.combo-display { font-family:'Orbitron',sans-serif; font-size:.8rem; color:#fbbf24; font-weight:900; }

/* ── PHASE 2: DESIGN SPRINT ────────────────────────── */
.phase2-left { display:flex; flex-direction:column; gap:1rem; }
.phase2-right { display:flex; flex-direction:column; gap:.75rem; overflow-y:auto; }

.scenario-box { background:rgba(8,12,30,.8); border:1px solid rgba(0,240,255,.15); border-radius:.75rem; padding:1.2rem; }
.scenario-header { font-size:.8rem; font-weight:700; color:#00f0ff; margin-bottom:.5rem; letter-spacing:1px; }
.scenario-text { font-size:.9rem; color:#cbd5e1; line-height:1.6; }

.checklist-panel { background:rgba(8,12,30,.8); border:1px solid rgba(0,240,255,.15); border-radius:.75rem; padding:1rem; flex:1; overflow-y:auto; }
.checklist-header { font-size:.8rem; font-weight:700; color:#34d399; margin-bottom:.75rem; letter-spacing:1px; }
.checklist-items { display:flex; flex-direction:column; gap:.5rem; }
.check-item { display:flex; align-items:center; gap:.5rem; padding:.4rem; background:rgba(255,255,255,.02); border-radius:.4rem; transition:all .2s; }
.check-item.checked { background:rgba(52,211,153,.08); }
.check-box { font-size:1rem; min-width:1.5rem; }
.check-label { font-size:.8rem; color:#94a3b8; flex:1; }
.check-item.checked .check-label { color:#34d399; font-weight:600; }

.design-textarea { width:100%; height:100%; padding:1rem; background:#0f1419; border:none; color:#e0f2fe; font-family:'Courier New',monospace; font-size:.85rem; line-height:1.6; outline:none; resize:none; }
.design-textarea::placeholder { color:#64748b; }

.score-breakdown { display:flex; flex-direction:column; gap:.2rem; margin-top:.3rem; }
.score-part { font-size:.7rem; color:#94a3b8; }
.score-total { font-family:'Orbitron',sans-serif; font-size:1.3rem; font-weight:900; margin-top:.3rem; }

/* ── 평가 완료 로딩 ────────────────────────────── */
.game-area-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  min-height: 400px;
}

.loading-spinner-box {
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2rem;
}

.spinner {
  width: 80px;
  height: 80px;
  border: 4px solid rgba(0, 240, 255, 0.2);
  border-top: 4px solid #00f0ff;
  border-right: 4px solid #fbbf24;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  box-shadow: 0 0 30px rgba(0, 240, 255, 0.3);
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.loading-text {
  font-size: 1.1rem;
  color: #00f0ff;
  font-weight: 600;
  letter-spacing: 1px;
}

.loading-subtext {
  font-size: 0.85rem;
  color: #64b5f6;
  opacity: 0.8;
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 1; }
}

/* ── RESULT ────────────────────────────────── */
.overlay { position:fixed; inset:0; background:rgba(0,0,0,.85); display:flex; align-items:center; justify-content:center; z-index:8000; }
.result-box {
  text-align:center; max-width:520px; width:90%;
  background:rgba(8,12,30,.95); border:2px solid #00f0ff;
  border-radius:1.5rem; padding:3rem 2.5rem;
  box-shadow:0 0 60px rgba(0,240,255,.2);
}
/* ← 수정: 각 플레이어 입장 반영 */
.result-box.res-my-win { border-color:#38bdf8; }
.result-box.res-opponent-win { border-color:#ff2d75; }
.result-box.res-draw { border-color:#ffe600; }

.r-icon { font-size:3.5rem; margin-bottom:1rem; }
.r-title { font-size:2rem; font-weight:900; color:#00f0ff; margin-bottom:1.5rem; letter-spacing:2px; }
.r-scores {
  display:flex; align-items:center; justify-content:center; gap:1.5rem;
  margin-bottom:1.5rem;
}
.score-item {
  display:flex; flex-direction:column; align-items:center; gap:.4rem;
  padding: 1rem; border-radius: 0.5rem; background: rgba(0, 0, 0, 0.3);
}

/* ← 수정: 각 플레이어 입장 반영 */
.score-item.my-score { border-left: 4px solid #38bdf8; }
.score-item.opponent-score { border-left: 4px solid #ff2d75; }
.score-item.p1 { }
.score-item.p2 { }

.p-name { font-size: 1rem; font-weight: bold; color: #00f0ff; }
.score-item.opponent-score .p-name { color: #ffaa00; }
.p-score { font-family:'Orbitron',sans-serif; font-size:2rem; font-weight:900; color:#38bdf8; }
.score-item.p2 .p-score { color:#ff2d75; }

.score-breakdown { text-align: center; }
.score-part { font-size: 0.9rem; color: #b0b0b0; margin: 0.2rem 0; }
.score-total { font-size: 1.3rem; font-weight: bold; color: #00ff00; margin-top: 0.5rem; }
.vs { font-size:1.2rem; color:#475569; font-weight:700; }
.r-detail { font-size:.85rem; color:#94a3b8; margin-bottom:1.5rem; }

.go-btns { display:flex; gap:1rem; justify-content:center; }
.btn-retry { padding:.75rem 2rem; background:transparent; border:2px solid #00f0ff; color:#00f0ff; border-radius:.5rem; font-family:'Orbitron',sans-serif; font-weight:700; cursor:pointer; transition:all .2s; }
.btn-retry:hover { background:rgba(0,240,255,.1); }
.btn-exit { padding:.75rem 2rem; background:transparent; border:2px solid #64748b; color:#64748b; border-radius:.5rem; font-family:'Orbitron',sans-serif; font-weight:700; cursor:pointer; transition:all .2s; }
.btn-exit:hover { color:#94a3b8; border-color:#94a3b8; }

/* ── FLOAT POP ─────────────────────────────── */
.fpop-layer { position:fixed; inset:0; pointer-events:none; z-index:7000; }
.fpop-item { position:absolute; font-family:'Orbitron',sans-serif; font-size:1rem; font-weight:700; animation:popUp 1.2s ease-out forwards; }
@keyframes popUp {
  0% { transform:translateY(0) scale(1); opacity:1; }
  100% { transform:translateY(-60px) scale(0.8); opacity:0; }
}

/* ── Phase 2 대기 상태 스타일 ─────────────────────────────── */
.waiting-hud {
  background: rgba(8, 12, 30, 0.95);
  border: 1px solid rgba(255, 230, 0, 0.2);
  box-shadow: 0 0 20px rgba(255, 230, 0, 0.1);
}

.waiting-box {
  background: rgba(8, 12, 30, 0.9);
  border: 1px solid rgba(0, 240, 255, 0.2);
}

.code-preview-container {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.code-preview {
  background: #0f1419;
  border: 1px solid rgba(0, 240, 255, 0.1);
  border-radius: 0.5rem;
  padding: 1rem;
  font-family: 'Courier New', monospace;
  font-size: 0.8rem;
  color: #e0f2fe;
  max-height: 200px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-wrap: break-word;
  line-height: 1.4;
}

.eval-summary {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.eval-item {
  font-size: 0.85rem;
  color: #34d399;
  padding: 0.5rem;
  background: rgba(52, 211, 153, 0.05);
  border-left: 2px solid #34d399;
  border-radius: 0.25rem;
}

.opponent-box {
  background: rgba(8, 12, 30, 0.9);
  border: 1px solid rgba(255, 45, 117, 0.2);
}

.waiting-panel {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(8, 12, 30, 0.8);
  border: 1px dashed rgba(255, 230, 0, 0.3);
  border-radius: 0.75rem;
  padding: 3rem;
  height: 100%;
  min-height: 300px;
}

.wait-icon {
  font-size: 3rem;
  margin-bottom: 1rem;
  animation: waitingPulse 1.5s ease-in-out infinite;
}

.wait-text {
  font-size: 1rem;
  color: #ffe600;
  margin-bottom: 1rem;
  text-align: center;
}

.wait-timer {
  font-size: 0.85rem;
  color: #64748b;
  text-align: center;
}

@keyframes waitingPulse {
  0%, 100% { opacity: 0.6; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.1); }
}

/* ── LLM 평가 섹션 ──────────────────────────────── */
.llm-section {
  margin-top: 2rem;
  padding: 1.5rem;
  background: linear-gradient(135deg, rgba(100, 200, 255, 0.1), rgba(150, 100, 255, 0.1));
  border: 2px solid #64c8ff;
  border-radius: 8px;
  font-size: 0.9rem;
}

.llm-header {
  font-weight: bold;
  font-size: 1rem;
  color: #64c8ff;
  margin-bottom: 1rem;
  text-align: center;
}

.llm-item {
  background: rgba(0, 0, 0, 0.3);
  padding: 1rem;
  margin-bottom: 1rem;
  border-radius: 6px;
  border-left: 4px solid;
}

.llm-item.p1-eval {
  border-left-color: #00d4ff;
}

.llm-item.p2-eval {
  border-left-color: #ffaa00;
}

.eval-player {
  font-weight: bold;
  color: #fff;
  margin-bottom: 0.5rem;
}

.eval-score {
  display: flex;
  gap: 1rem;
  margin-bottom: 0.8rem;
  align-items: center;
}

.score-badge {
  background: rgba(100, 200, 255, 0.2);
  color: #64c8ff;
  padding: 0.4rem 0.8rem;
  border-radius: 4px;
  font-weight: bold;
  font-size: 0.95rem;
}

.grade-badge {
  padding: 0.4rem 0.8rem;
  border-radius: 4px;
  font-weight: bold;
  font-size: 0.85rem;
}

.grade-badge.grade-A {
  background: rgba(0, 255, 0, 0.2);
  color: #00ff00;
}

.grade-badge.grade-B {
  background: rgba(100, 200, 255, 0.2);
  color: #64c8ff;
}

.grade-badge.grade-C {
  background: rgba(255, 200, 0, 0.2);
  color: #ffc800;
}

.grade-badge.grade-D {
  background: rgba(255, 100, 100, 0.2);
  color: #ff6464;
}

.grade-badge.grade-F {
  background: rgba(255, 0, 0, 0.2);
  color: #ff0000;
}

.eval-feedback {
  color: #e0e0e0;
  margin-bottom: 0.8rem;
  line-height: 1.4;
  font-style: italic;
}

.eval-details {
  margin-top: 0.6rem;
}

.detail-row {
  color: #b0b0b0;
  margin-bottom: 0.4rem;
  font-size: 0.85rem;
}

/* ── 트랜지션 ──────────────────────────────── */
/* ── 포트폴리오 export ── */
.lr-portfolio { margin: 1rem 0 0.5rem; text-align: left; }
.lr-pf-title { font-family: 'Orbitron', sans-serif; font-size: .65rem; color: #ffe600; letter-spacing: 2px; margin-bottom: .6rem; text-align: center; }
.lr-pf-preview { background: linear-gradient(135deg, #030712, #0a0f1e); border: 1px solid rgba(255,230,0,0.25); border-radius: .75rem; padding: 1rem; display: flex; flex-direction: column; gap: .6rem; margin-bottom: .75rem; }
.lrpf-badge { font-size: .55rem; font-weight: 700; letter-spacing: 1px; padding: 3px 10px; border-radius: 4px; background: rgba(255,230,0,.08); color: #ffe600; border: 1px solid rgba(255,230,0,.2); display: inline-block; }
.lrpf-scenario { font-size: .75rem; color: #64748b; line-height: 1.4; border-left: 2px solid rgba(255,230,0,.2); padding-left: .5rem; }
.lrpf-code { background: #050a10; border: 1px solid rgba(255,230,0,.12); border-radius: .4rem; padding: .6rem .75rem; font-family: monospace; font-size: .65rem; color: #e0f2fe; white-space: pre-wrap; word-break: break-all; max-height: 120px; overflow-y: auto; line-height: 1.4; }
.lrpf-scores { display: flex; gap: .6rem; align-items: center; flex-wrap: wrap; }
.lrpf-sl { font-size: .5rem; color: #475569; font-family: 'Orbitron', monospace; letter-spacing: 1px; }
.lrpf-sv { font-size: .8rem; font-weight: 700; font-family: 'Orbitron', monospace; }
.lrpf-ai { font-size: .65rem; color: #64748b; }
.lrpf-ai-label { color: #ffe600; font-weight: 700; margin-right: .3rem; }
.lrpf-footer { font-size: .55rem; color: #1e293b; font-family: monospace; padding-top: .5rem; border-top: 1px solid rgba(255,255,255,.04); }
.lr-pf-actions { display: flex; gap: .5rem; margin-bottom: .5rem; flex-wrap: wrap; }
.go-pf-btn { padding: .45rem 1rem; border-radius: .5rem; font-size: .7rem; font-weight: 700; cursor: pointer; transition: all .2s; }
.go-pf-btn.cyan { background: rgba(0,240,255,.1); border: 1px solid rgba(0,240,255,.3); color: #00f0ff; }
.go-pf-btn.cyan:hover { background: rgba(0,240,255,.18); }
.go-pf-btn.purple { background: rgba(168,85,247,.1); border: 1px solid rgba(168,85,247,.3); color: #a855f7; }
.go-pf-btn.purple:hover { background: rgba(168,85,247,.18); }
.go-pf-btn.gray { background: rgba(100,116,139,.1); border: 1px solid rgba(100,116,139,.3); color: #64748b; }
.go-pf-btn.gray:hover { background: rgba(100,116,139,.18); }
.go-pf-toast { font-size: .7rem; color: #22c55e; padding: .3rem .7rem; background: rgba(34,197,94,.1); border: 1px solid rgba(34,197,94,.25); border-radius: .4rem; display: inline-block; }

.zoom-enter-active, .zoom-leave-active { transition: transform 0.3s ease, opacity 0.3s ease; }
.zoom-enter-from, .zoom-leave-to { transform: scale(0.9); opacity: 0; }

.fpop-enter-active { transition: all 0.3s ease; }
.fpop-leave-active { transition: all 0.2s ease; }
.fpop-enter-from { opacity: 0; transform: translateY(20px); }
.fpop-leave-to { opacity: 0; transform: translateY(-30px); }

/* [2026-03-04] 바나나 장애물 시각효과 */
.obstacle-overlay {
  position: fixed; inset: 0; z-index: 9500;
  display: flex; align-items: center; justify-content: center;
  pointer-events: none;
}
.obstacle-emoji {
  font-size: 120px;
  animation: bananaFall 1s ease-out forwards;
  filter: drop-shadow(0 0 30px rgba(255,200,0,.6));
}
@keyframes bananaFall {
  0% { transform: translateY(-200px) rotate(0deg) scale(0.3); opacity: 0; }
  30% { transform: translateY(0) rotate(30deg) scale(1.2); opacity: 1; }
  50% { transform: translateY(20px) rotate(-15deg) scale(1); opacity: 1; }
  100% { transform: translateY(100px) rotate(45deg) scale(0.5); opacity: 0; }
}
.banana-slip {
  animation: slipShake 0.6s ease-in-out;
}
@keyframes slipShake {
  0%, 100% { transform: rotate(0deg); }
  15% { transform: rotate(-8deg) translateX(-10px); }
  30% { transform: rotate(6deg) translateX(8px); }
  45% { transform: rotate(-4deg) translateX(-5px); }
  60% { transform: rotate(3deg) translateX(3px); }
  75% { transform: rotate(-1deg); }
}
.obstacle-pop-enter-active { transition: all 0.2s ease; }
.obstacle-pop-leave-active { transition: all 0.5s ease; }
.obstacle-pop-enter-from { opacity: 0; transform: scale(0); }
.obstacle-pop-leave-to { opacity: 0; }
</style>
