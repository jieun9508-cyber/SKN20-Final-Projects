<template>
  <div class="bubble-game" :class="{ 'screen-shake': shaking, 'bubble-flash': bubbleFlash }">
    <div class="crt-lines"></div>

    <!-- ===== JOIN SCREEN ===== -->
    <div v-if="!bs.connected.value" class="center-screen">
      <div class="center-box">
        <h1 class="logo glitch" data-text="BUG BUBBLE">BUG BUBBLE</h1>
        <p class="sub-logo">버그를 잡아 버블에 가두고 상대에게 날려라</p>
        <div class="join-group">
          <input v-model="inputRoomId" placeholder="ROOM ID..." class="room-input" @keyup.enter="joinRoom" />
          <button class="btn-join" @click="joinRoom" :disabled="!inputRoomId.trim()">JOIN</button>
        </div>
        <button class="btn-back" @click="router.push('/practice/wars')">← BACK</button>
      </div>
    </div>

    <!-- ===== LOBBY ===== -->
    <div v-else-if="gamePhase === 'lobby'" class="center-screen">
      <div class="center-box">
        <h1 class="logo glitch" data-text="BUG BUBBLE">BUG BUBBLE</h1>
        <p class="sub-logo">실시간 버그 디버깅 서바이벌</p>

        <div class="lobby-players">
          <div class="lp me-lp">
            <img :src="auth.userAvatarUrl || '/image/duck_idle.png'" class="lp-avatar" />
            <span>{{ auth.sessionNickname || '나' }}</span>
          </div>
          <div class="lp-vs">VS</div>
          <div class="lp opp-lp" v-if="bs.opponentName.value">
            <img :src="bs.opponentAvatar.value || '/image/duck_idle.png'" class="lp-avatar" />
            <span>{{ bs.opponentName.value }}</span>
          </div>
          <div class="lp waiting-lp" v-else>
            <span class="blink">⏳</span><span>대기 중...</span>
          </div>
        </div>

        <div class="guide-grid">
          <div class="guide-item"><div class="gi-num">01</div><div class="gi-body"><strong>버그 발견</strong><p>에러 로그를 분석하세요</p></div></div>
          <div class="guide-item"><div class="gi-num">02</div><div class="gi-body"><strong>정답 선택</strong><p>4지선다 중 올바른 수정을 고르세요</p></div></div>
          <div class="guide-item"><div class="gi-num">03</div><div class="gi-body"><strong>버블 전송</strong><p>정답 → 버그 버블이 상대에게 날아갑니다</p></div></div>
          <div class="guide-item"><div class="gi-num">04</div><div class="gi-body"><strong>생존!</strong><p>버그 {{ maxMonsters }}개 쌓이면 패배</p></div></div>
        </div>

        <button class="btn-start blink-border" :disabled="!bs.isReady.value" @click="startGame">
          {{ bs.isReady.value ? '▶ GAME START' : '상대 대기 중...' }}
        </button>
        <button class="btn-back" @click="router.push('/practice/wars')">← 나가기</button>
      </div>
    </div>

    <!-- ===== GENERATING (AI 문제 생성 로딩) ===== -->
    <div v-else-if="gamePhase === 'generating'" class="center-screen">
      <div class="gen-box">
        <div class="gen-header">
          <div class="gen-icon-ring">
            <span class="gen-bug spin-slow">🐛</span>
          </div>
          <h2 class="gen-title neon-c">DEPLOYING BUGS...</h2>
        </div>

        <div class="gen-terminal">
          <div class="term-header">
            <span class="dot red"></span><span class="dot yellow"></span><span class="dot green"></span>
            <span class="term-title">bug_factory.sh</span>
          </div>
          <div class="term-body" ref="termBody">
            <div v-for="(log, i) in genLogs" :key="i" class="term-line" :class="{ 'term-latest': i === genLogs.length - 1 }">
              <span class="term-prefix">{{ log.prefix }}</span>
              <span class="term-msg">{{ log.msg }}</span>
              <span class="term-file" v-if="log.file">{{ log.file }}</span>
            </div>
            <div class="term-cursor blink">█</div>
          </div>
        </div>

        <div class="gen-progress">
          <div class="gen-bar">
            <div class="gen-fill" :style="{ width: genPct + '%' }"></div>
          </div>
          <span class="gen-pct">{{ genPct }}%</span>
        </div>
        <p class="gen-status">{{ genMsg }}</p>
      </div>
    </div>

    <!-- ===== PLAY SCREEN ===== -->
    <div v-else-if="gamePhase === 'playing'" class="play-screen">
      <div class="hud">
        <div class="hud-player">
          <img :src="auth.userAvatarUrl || '/image/duck_idle.png'" class="hud-avatar" />
          <div class="hud-info">
            <span class="hud-name neon-c">{{ auth.sessionNickname || 'ME' }}</span>
            <div class="monster-bar">
              <div class="monster-fill" :class="{ danger: activeMonsters.length > maxMonsters * 0.7 }" :style="{ width: (activeMonsters.length / maxMonsters * 100) + '%' }"></div>
              <span class="monster-count">👾 {{ activeMonsters.length }}/{{ maxMonsters }}</span>
            </div>
          </div>
        </div>
        <div class="hud-center">
          <div class="vs-pill">⚡ VS ⚡</div>
          <div v-if="combo > 1" class="combo-badge" :class="{ 'mega': combo >= 3 }">COMBO ×{{ combo }}</div>
          <div v-if="combo >= 3" class="fever-tag blink">🔥 FEVER</div>
        </div>
        <div class="hud-player opp-side">
          <div class="hud-info right">
            <span class="hud-name" style="color:#ff2d75">{{ bs.opponentName.value || 'OPP' }}</span>
            <div class="monster-bar opp-bar">
              <div class="monster-fill opp-fill" :class="{ danger: opponentMonsterCount > maxMonsters * 0.7 }" :style="{ width: (opponentMonsterCount / maxMonsters * 100) + '%' }"></div>
              <span class="monster-count">👾 {{ opponentMonsterCount }}/{{ maxMonsters }}</span>
            </div>
          </div>
          <img :src="bs.opponentAvatar.value || '/image/duck_idle.png'" class="hud-avatar opp-avatar" />
        </div>
      </div>

      <div class="arena">
        <div class="problem-panel" :class="{ 'pulse-warning': activeMonsters.length > maxMonsters * 0.7 }">
          <div class="prob-header">
            <span class="prob-badge">🐛 BUG #{{ currentProblemIndex + 1 }}</span>
            <span class="bug-type-badge">{{ currentProblem?.bug_type_name || 'BUG' }}</span>
            <span class="prob-file">{{ currentProblem?.file_name || 'unknown.py' }}</span>
          </div>
          <div class="error-log" v-if="currentProblem?.error_log">
            <div class="log-label">📋 ERROR LOG</div>
            <pre>{{ currentProblem.error_log }}</pre>
          </div>
          <div class="code-block">
            <div class="code-head">
              <span class="dot red"></span><span class="dot yellow"></span><span class="dot green"></span>
              <span class="code-fname">{{ currentProblem?.file_name }}</span>
            </div>
            <div class="code-body">
              <div v-for="(line, idx) in buggyCodeLines" :key="idx" class="code-line" :class="{ 'bug-line': idx + 1 === currentProblem?.bug_line }">
                <span class="ln">{{ idx + 1 }}</span>
                <span class="lc" :class="{ 'hl-bug': idx + 1 === currentProblem?.bug_line }">{{ line }}</span>
                <span class="bug-marker" v-if="idx + 1 === currentProblem?.bug_line">← BUG!</span>
              </div>
            </div>
          </div>
          <div class="hint-box" v-if="showHint">💡 {{ currentProblem?.hint }}</div>
          <button class="btn-hint" @click="showHint = !showHint" v-if="currentProblem?.hint">
            {{ showHint ? '힌트 숨기기' : '💡 힌트 보기' }}
          </button>
        </div>

        <div class="choices-panel">
          <div class="choices-label">올바른 수정 코드를 선택하세요</div>
          <div class="choices-list">
            <button v-for="(choice, idx) in currentProblem?.choices" :key="idx"
              class="choice-btn" :class="getChoiceClass(idx)"
              @click="selectChoice(idx)" :disabled="answerState !== 'idle'">
              <span class="choice-key">{{ ['A','B','C','D'][idx] }}</span>
              <code class="choice-code">{{ choice.label }}</code>
            </button>
          </div>
          <transition name="slide-up">
            <div class="answer-fb" v-if="answerState !== 'idle'" :class="answerState">
              <span v-if="answerState === 'correct'">✅ 정답! 버그를 가두고 상대에게 날렸습니다! 🫧</span>
              <span v-else>❌ 오답! 버그가 내 화면으로 침투합니다... 👾</span>
            </div>
          </transition>
        </div>
      </div>

      <transition name="alert-slide">
        <div v-if="incomingAlert" class="incoming-alert">
          <span class="alert-text">{{ incomingAlert }}</span>
        </div>
      </transition>

      <div class="monster-overlay">
        <!-- 수신 버블: 날아와서 터짐 -->
        <div v-for="b in incomingBubbles" :key="'ib'+b.id" class="incoming-bubble"
          :class="{ 'ib-flying': b.phase === 'flying', 'ib-pop': b.phase === 'pop' }"
          :style="{ '--target-x': b.targetX + 'px', '--target-y': b.targetY + 'px', '--start-y': b.y + 'px' }">
          <div class="bubble-sphere ib-sphere">
            <span class="bubble-monster">👾</span>
          </div>
        </div>
        <div v-for="m in activeMonsters" :key="m.id" class="monster-bug"
          :style="{ left: m.x + 'px', top: m.y + 'px', fontSize: m.size + 'rem' }">👾</div>
        <transition-group name="bubble-fly" tag="div">
          <div v-for="b in flyingBubbles" :key="b.id" class="fly-bubble"
            :style="{ left: b.x + 'px', top: b.y + 'px' }">
            <div class="bubble-sphere">
              <span class="bubble-monster">👾</span>
            </div>
          </div>
        </transition-group>
        <transition-group name="combo-pop" tag="div">
          <div v-for="p in comboPops" :key="p.id" class="combo-popup" :style="{ left: p.x, top: p.y }">{{ p.text }}</div>
        </transition-group>
      </div>
    </div>

    <!-- ===== GAME OVER ===== -->
    <div v-else-if="gamePhase === 'gameover'" class="center-screen overlay dark-ov">
      <div class="go-box">
        <h1 class="go-title glitch" :data-text="isWinner ? 'VICTORY' : 'DEFEATED'">{{ isWinner ? 'VICTORY' : 'DEFEATED' }}</h1>
        <div class="go-icon">{{ isWinner ? '🏆' : '💀' }}</div>
        <p class="go-sub">{{ isWinner ? '상대방의 화면이 버그로 가득 찼습니다!' : '나의 화면이 버그로 마비되었습니다.' }}</p>
        <div class="go-stats">
          <div class="stat"><span class="sl">맞힌 문제</span><span class="sv neon-c">{{ totalSolved }}</span></div>
          <div class="stat"><span class="sl">최대 콤보</span><span class="sv neon-y">{{ bestCombo }}×</span></div>
          <div class="stat"><span class="sl">보낸 버블</span><span class="sv" style="color:#ff2d75">{{ totalBubblesSent }}</span></div>
        </div>
        <div class="go-btns">
          <button class="btn-retry" @click="resetAndRestart">🔄 REMATCH</button>
          <button class="btn-exit" @click="router.push('/practice/wars')">🏠 EXIT</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useBubbleSocket } from '../composables/useBubbleSocket'
import { addBattleRecord } from '../useBattleRecord.js'

const router = useRouter()
const auth = useAuthStore()
const bs = useBubbleSocket()

const inputRoomId = ref('')
const currentRoomId = ref('')
const gamePhase = ref('lobby')
const genPct = ref(0)
const genMsg = ref('준비 중...')
const genLogs = ref([])
const termBody = ref(null)

const activeMonsters = ref([])
const flyingBubbles = ref([])
const comboPops = ref([])
const maxMonsters = 12
const opponentMonsterCount = ref(0)
const isWinner = ref(false)
const combo = ref(0)
const bestCombo = ref(0)
const totalSolved = ref(0)
const totalBubblesSent = ref(0)
const shaking = ref(false)
const incomingAlert = ref('')
const bubbleFlash = ref(false)
let alertTimer = null
let flyBubbleId = 0
let combPopId = 0
let animFrameId = null
let _monsterSyncTimer = null
let _initialSyncDone = false

const allProblems = ref([])
const currentProblemIndex = ref(0)
const answerState = ref('idle')
const showHint = ref(false)
const selectedChoiceIdx = ref(-1)
const incomingBubbles = ref([])
let incomingBubbleId = 0

const currentProblem = computed(() => allProblems.value[currentProblemIndex.value] || null)
const buggyCodeLines = computed(() => {
  if (!currentProblem.value?.buggy_code) return []
  return currentProblem.value.buggy_code.split('\n')
})

function getFallbackProblems() {
  return [
    {
      title: '서버 응답 점수 합산 에러', bug_type_name: 'TypeError', file_name: 'score_api.py', bug_line: 4,
      buggy_code: 'import json\nresponse = \'{"score": "100", "bonus": 50}\'\ndata = json.loads(response)\ntotal = data["score"] + data["bonus"]\nprint(total)',
      error_log: 'TypeError: can only concatenate str (not "int") to str\nFile "score_api.py", line 4',
      hint: 'JSON에서 파싱한 score의 타입을 확인해보세요.',
      choices: [
        { label: 'total = int(data["score"]) + data["bonus"]', correct: true },
        { label: 'total = data["score"] + str(data["bonus"])', correct: false },
        { label: 'total = str(data["score"] + data["bonus"])', correct: false },
        { label: 'total = data["score"].add(data["bonus"])', correct: false },
      ]
    },
    {
      title: '리스트 마지막 원소 접근 실패', bug_type_name: 'IndexError', file_name: 'data_loader.py', bug_line: 2,
      buggy_code: 'batch = ["img1.png", "img2.png", "img3.png"]\nlast = batch[3]\nprint(f"마지막 배치: {last}")',
      error_log: 'IndexError: list index out of range\nFile "data_loader.py", line 2',
      hint: '리스트 인덱스는 0부터 시작합니다.',
      choices: [
        { label: 'last = batch[2]', correct: true },
        { label: 'last = batch[4]', correct: false },
        { label: 'last = batch.last()', correct: false },
        { label: 'last = batch[-0]', correct: false },
      ]
    },
    {
      title: '딕셔너리 키 누락 처리', bug_type_name: 'KeyError', file_name: 'config.py', bug_line: 3,
      buggy_code: 'config = {"host": "localhost", "port": 8080}\nhost = config["host"]\ndb = config["database"]',
      error_log: "KeyError: 'database'\nFile \"config.py\", line 3",
      hint: '존재하지 않는 키에 안전하게 접근하는 방법은?',
      choices: [
        { label: 'db = config.get("database", "default_db")', correct: true },
        { label: 'db = config["db"]', correct: false },
        { label: 'db = config.database', correct: false },
        { label: 'db = config or "default_db"', correct: false },
      ]
    },
  ].map(p => ({ ...p, choices: shuffleArray([...p.choices]) }))
}

function shuffleArray(arr) {
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]]
  }
  return arr
}

function joinRoom() {
  if (!inputRoomId.value.trim()) return
  currentRoomId.value = inputRoomId.value.trim()
  bs.connect(currentRoomId.value, auth.sessionNickname || 'Anonymous', auth.userAvatarUrl, auth.user?.id)
}

// [2026-03-05] 서버에 시작 신호만 보냄. 화면 전환은 bubble_gen_progress 첫 수신 시 처리
// → 한 명이 눌러도 서버가 room 전체에 broadcast → 양쪽 모두 로딩 화면으로 전환
function startGame() {
  bs.emitStart(currentRoomId.value)
}

function addGenLog(msg, file = '') {
  const prefixes = ['$', '>', '>>', '✓', '⚙', '→']
  const prefix = prefixes[Math.floor(Math.random() * prefixes.length)]
  genLogs.value.push({ prefix, msg, file })
  nextTick(() => {
    if (termBody.value) termBody.value.scrollTop = termBody.value.scrollHeight
  })
}

function getChoiceClass(idx) {
  if (answerState.value === 'idle') return ''
  const choice = currentProblem.value?.choices?.[idx]
  if (!choice) return ''
  if (choice.correct) return 'correct-choice'
  if (idx === selectedChoiceIdx.value && !choice.correct) return 'wrong-choice'
  return 'dim-choice'
}

function selectChoice(idx) {
  if (answerState.value !== 'idle' || gamePhase.value !== 'playing') return
  selectedChoiceIdx.value = idx
  const choice = currentProblem.value?.choices?.[idx]
  if (!choice) return

  if (choice.correct) {
    answerState.value = 'correct'
    combo.value++
    if (combo.value > bestCombo.value) bestCombo.value = combo.value
    totalSolved.value++
    spawnComboPopup()
    if (activeMonsters.value.length > 0) activeMonsters.value.pop()
    if (combo.value > 0 && combo.value % 3 === 0) {
      // 3콤보 달성 시 버블 3개 연속 (1개 대신 교체)
      spawnComboPopup('🔥 3COMBO! ×3')
      for (let i = 0; i < 3; i++) {
        setTimeout(() => {
          launchBubble()
          bs.emitSendMonster(currentRoomId.value, 'normal')
        }, i * 300)
      }
    } else {
      bs.emitSendMonster(currentRoomId.value, 'normal')
    }
  } else {
    answerState.value = 'wrong'
    combo.value = 0
    shaking.value = true
    setTimeout(() => shaking.value = false, 500)
    spawnMonsters(1)
  }

  setTimeout(() => {
    answerState.value = 'idle'
    selectedChoiceIdx.value = -1
    showHint.value = false
    nextProblem()
  }, 1200)
}

function spawnIncomingBubble(monsterCount) {
  const id = ++incomingBubbleId
  // 아바타 HUD 근처 우측 위에서 터짐
  const targetX = window.innerWidth * 0.75 + (Math.random() - 0.5) * 60
  const targetY = 60 + Math.random() * 40
  incomingBubbles.value.push({ id, targetX, targetY, phase: 'flying' })

  setTimeout(() => {
    const b = incomingBubbles.value.find(b => b.id === id)
    if (b) b.phase = 'pop'
    bubbleFlash.value = true
    setTimeout(() => { bubbleFlash.value = false }, 400)

    // 버블 터진 자리에서 몬스터가 사방으로 튀쳐나오는 효과
    for (let i = 0; i < monsterCount; i++) {
      const angle = (2 * Math.PI / monsterCount) * i + Math.random() * 0.5
      const speed = 4 + Math.random() * 3
      const m = {
        id: Date.now() + Math.random() + i,
        x: targetX,
        y: targetY,
        dx: Math.cos(angle) * speed,
        dy: Math.sin(angle) * speed,
        size: 1.5 + Math.random() * 0.8,
        // 스폰 직후 바람저항 있게 (0.5초 후 슬로우다운)
        spawnTime: Date.now()
      }
      activeMonsters.value.push(m)
    }

    if (activeMonsters.value.length >= maxMonsters && gamePhase.value === 'playing') {
      gamePhase.value = 'gameover-pending'
      bs.emitGameOver(currentRoomId.value)
    }
    setTimeout(() => {
      incomingBubbles.value = incomingBubbles.value.filter(b => b.id !== id)
    }, 600)
  }, 700)
}

function showAlert(msg) {
  incomingAlert.value = msg
  if (alertTimer) clearTimeout(alertTimer)
  alertTimer = setTimeout(() => { incomingAlert.value = '' }, 1500)
}

function nextProblem() {
  if (allProblems.value.length === 0) return
  const next = currentProblemIndex.value + 1
  if (next >= allProblems.value.length) {
    // 다 풀면 셔플 후 재시작 (같은 순서로 반복 안 되게)
    allProblems.value = shuffleArray([...allProblems.value])
    currentProblemIndex.value = 0
  } else {
    currentProblemIndex.value = next
  }
}

function launchBubble() {
  const id = ++flyBubbleId
  totalBubblesSent.value++
  flyingBubbles.value.push({ id, x: window.innerWidth * 0.15, y: window.innerHeight * 0.5 })
  setTimeout(() => { flyingBubbles.value = flyingBubbles.value.filter(b => b.id !== id) }, 800)
}

function spawnComboPopup(text) {
  const id = ++combPopId
  const txt = text || (combo.value > 1 ? `COMBO ×${combo.value}! 🔥` : '정답! ✅')
  comboPops.value.push({ id, text: txt, x: 30 + Math.random() * 40 + '%', y: 30 + Math.random() * 30 + '%' })
  setTimeout(() => { comboPops.value = comboPops.value.filter(p => p.id !== id) }, 1000)
}

function spawnMonsters(count) {
  for (let i = 0; i < count; i++) {
    activeMonsters.value.push({
      id: Date.now() + Math.random(),
      x: 20 + Math.random() * (window.innerWidth * 0.85 - 60),
      y: 100 + Math.random() * (window.innerHeight * 0.6),
      dx: (Math.random() - 0.5) * 3, dy: (Math.random() - 0.5) * 3,
      size: 1.5 + Math.random() * 0.8
    })
  }
  if (activeMonsters.value.length >= maxMonsters && gamePhase.value === 'playing') {
    gamePhase.value = 'gameover-pending'
    bs.emitGameOver(currentRoomId.value)
  }
}

function startGameLoop() {
  function loop() {
    if (gamePhase.value !== 'playing') return
    const W = window.innerWidth * 0.9, H = window.innerHeight * 0.75
    const now = Date.now()
    activeMonsters.value.forEach(m => {
      // 스폰 직후 0.6초동안 바람저항으로 감속, 그 후 일반 방황전환
      if (m.spawnTime) {
        const elapsed = now - m.spawnTime
        if (elapsed < 600) {
          m.dx *= 0.93
          m.dy *= 0.93
        } else {
          // 속도가 일반 순항 수준으로 떨어지면 spawnTime 제거
          if (Math.abs(m.dx) < 2.5) m.dx = (Math.random() - 0.5) * 3
          if (Math.abs(m.dy) < 2.5) m.dy = (Math.random() - 0.5) * 3
          delete m.spawnTime
        }
      } else {
        if (Math.random() < 0.015) { m.dx = (Math.random() - 0.5) * 3; m.dy = (Math.random() - 0.5) * 3 }
      }
      m.x += m.dx; m.y += m.dy
      if (m.x < 0 || m.x > W) m.dx *= -1
      if (m.y < 80 || m.y > H) m.dy *= -1
    })
    animFrameId = requestAnimationFrame(loop)
  }
  loop()
}

function resetAndRestart() {
  gamePhase.value = 'lobby'
  bs.gameOver.value = false
  bs.isPlaying.value = false
  activeMonsters.value = []
  opponentMonsterCount.value = 0
  combo.value = 0; bestCombo.value = 0; totalSolved.value = 0; totalBubblesSent.value = 0
  currentProblemIndex.value = 0; answerState.value = 'idle'
}

onMounted(() => {
  // [2026-03-05] bubble_gen_progress 첫 수신 시 양쪽 화면 전환
  // 버튼 누른 사람 = 서버로 emit → 서버가 room broadcast → 상대도 여기서 수신 → 둘 다 generating 화면으로
  bs.onGenProgress.value = (data) => {
    if (gamePhase.value === 'lobby') {
      gamePhase.value = 'generating'
      genPct.value = 0
      genMsg.value = '버그 배치 중...'
      genLogs.value = [{ prefix: '$', msg: 'connecting to bug_factory...', file: '' }]
    }
    genPct.value = data.pct || genPct.value
    genMsg.value = data.msg || genMsg.value
    addGenLog(data.msg, data.file || '')
  }

  bs.onGameStart.value = (data) => {
    if (data?.problems && data.problems.length > 0) {
      allProblems.value = data.problems.map(p => ({ ...p, choices: shuffleArray([...p.choices]) }))
      currentProblemIndex.value = 0
      addGenLog(`${data.problems.length}개 버그 배치 완료!`, 'READY')
    } else {
      allProblems.value = getFallbackProblems()
      addGenLog('폴백 문제 로드 완료', 'fallback.json')
    }
    genPct.value = 100
    genMsg.value = '버그 배치 완료 — 전투 시작!'

    setTimeout(() => {
      gamePhase.value = 'playing'
      _initialSyncDone = false
      spawnMonsters(3)
      opponentMonsterCount.value = 0
      setTimeout(() => { _initialSyncDone = true }, 1500)
      startGameLoop()
    }, 800)
  }

  bs.onReceiveMonster.value = () => {
    showAlert('⚠️ 상대 공격!')
    spawnIncomingBubble(1)
  }

  bs.onMonsterSync.value = (data) => {
    if (!_initialSyncDone) return
    if (!data?.counts || !bs.socket.value) return
    const myId = bs.socket.value.id
    for (const [sid, count] of Object.entries(data.counts)) {
      if (sid !== myId) opponentMonsterCount.value = count
    }
  }

  bs.onGameEnd.value = (result) => {
    cancelAnimationFrame(animFrameId)
    isWinner.value = result.isWinner
    gamePhase.value = 'gameover'
    addBattleRecord(auth.sessionNickname || 'Player', result.isWinner ? 'win' : 'lose')
  }
})

watch(() => activeMonsters.value.length, (newLen) => {
  if (gamePhase.value !== 'playing' || !currentRoomId.value) return
  if (_monsterSyncTimer) clearTimeout(_monsterSyncTimer)
  _monsterSyncTimer = setTimeout(() => bs.emitMonsterUpdate(currentRoomId.value, newLen), 300)
})

onUnmounted(() => {
  cancelAnimationFrame(animFrameId)
  bs.disconnect()
})
</script>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700;900&family=Rajdhani:wght@400;600;700&display=swap');

.bubble-game { min-height:100vh; background:#030712; color:#e0f2fe; font-family:'Rajdhani',sans-serif; position:relative; overflow:hidden }
.crt-lines { pointer-events:none; position:fixed; inset:0; z-index:9999; background:repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,240,255,.012) 2px,rgba(0,240,255,.012) 4px) }
.screen-shake { animation: shake .3s ease infinite }
@keyframes shake{0%,100%{transform:translateX(0)}20%{transform:translate(-5px,2px)}40%{transform:translate(5px,-2px)}60%{transform:translate(-5px,-2px)}80%{transform:translate(5px,2px)}}

.glitch { position:relative; font-family:'Orbitron',sans-serif; color:#00f0ff; font-size:3rem; letter-spacing:4px; font-weight:900 }
.glitch::before,.glitch::after { content:attr(data-text); position:absolute; top:0; left:0; width:100%; height:100% }
.glitch::before { color:#ff2d75; clip-path:inset(0 0 65% 0); animation:g1 2s infinite linear alternate-reverse }
.glitch::after { color:#39ff14; clip-path:inset(65% 0 0 0); animation:g2 2s infinite linear alternate-reverse }
@keyframes g1{0%{transform:translate(0)}50%{transform:translate(-3px,2px)}100%{transform:translate(0)}}
@keyframes g2{0%{transform:translate(0)}50%{transform:translate(3px,-2px)}100%{transform:translate(0)}}

.neon-c { color:#00f0ff; text-shadow:0 0 10px rgba(0,240,255,.5) }
.neon-y { color:#ffe600; text-shadow:0 0 10px rgba(255,230,0,.5) }
.blink { animation: bla 1s infinite } @keyframes bla{50%{opacity:.3}}
.blink-border { animation: bb 1.5s infinite } @keyframes bb{0%,100%{border-color:#ffe600}50%{border-color:rgba(255,230,0,.3)}}

.center-screen { display:flex; align-items:center; justify-content:center; min-height:100vh; padding:2rem }
.center-box { text-align:center; background:rgba(8,12,30,.85); border:2px solid #00f0ff; border-radius:1.5rem; padding:2.5rem 3.5rem; box-shadow:0 0 40px rgba(0,240,255,.12); max-width:550px; width:100% }
.logo { margin-bottom:.2rem }
.sub-logo { color:#94a3b8; letter-spacing:3px; font-size:.85rem; margin-bottom:1.5rem }
.overlay { position:fixed; inset:0; z-index:100 }
.dark-ov { background:rgba(0,0,0,.9) }

.join-group { display:flex; gap:.5rem; justify-content:center; margin-bottom:1rem }
.room-input { background:#0a0f1e; border:1px solid #1e293b; color:#fff; padding:.5rem 1rem; border-radius:4px; font-family:'Orbitron',sans-serif; font-size:.8rem; width:180px; text-align:center }
.room-input:focus { border-color:#00f0ff; outline:none; box-shadow:0 0 10px rgba(0,240,255,.2) }
.btn-join { background:#1e293b; border:1px solid #334155; color:#00f0ff; padding:.5rem 1.2rem; border-radius:4px; font-family:'Orbitron',sans-serif; font-size:.75rem; font-weight:700; cursor:pointer; transition:all .2s }
.btn-join:hover:not(:disabled) { background:#00f0ff; color:#030712 }
.btn-join:disabled { opacity:.4; cursor:not-allowed }
.btn-back { background:transparent; border:1px solid #334155; color:#64748b; padding:.4rem 1rem; border-radius:4px; font-size:.7rem; cursor:pointer; margin-top:.5rem }

.lobby-players { display:flex; align-items:center; justify-content:center; gap:1.5rem; margin:1.5rem 0; padding:1rem; background:rgba(0,0,0,.3); border-radius:12px; border:1px solid rgba(0,240,255,.1) }
.lp { display:flex; flex-direction:column; align-items:center; gap:.4rem; font-family:'Orbitron',sans-serif; font-size:.85rem; font-weight:700 }
.me-lp { color:#00f0ff } .opp-lp { color:#ff2d75 } .waiting-lp { color:#334155 }
.lp-avatar { width:64px; height:64px; border-radius:50%; object-fit:cover; border:3px solid rgba(0,240,255,.3); box-shadow:0 0 15px rgba(0,240,255,.2) }
.opp-lp .lp-avatar { border-color:rgba(255,45,117,.3); box-shadow:0 0 15px rgba(255,45,117,.2) }
.lp-vs { font-family:'Orbitron',sans-serif; font-size:1.2rem; color:#334155; font-weight:900 }

.guide-grid { display:grid; grid-template-columns:1fr 1fr; gap:.6rem; margin-bottom:1.5rem; text-align:left }
.guide-item { display:flex; gap:.6rem; background:rgba(0,240,255,.05); padding:.6rem; border-radius:8px; border:1px solid rgba(0,240,255,.1); transition:all .3s }
.guide-item:hover { background:rgba(0,240,255,.1); border-color:#00f0ff }
.gi-num { font-family:'Orbitron',sans-serif; font-size:1rem; color:#00f0ff; font-weight:700; opacity:.6 }
.gi-body strong { display:block; font-size:.85rem; color:#fff; margin-bottom:2px }
.gi-body p { font-size:.72rem; color:#94a3b8; margin:0; line-height:1.3 }

.btn-start { width:100%; padding:.8rem; font-family:'Orbitron',sans-serif; font-size:.85rem; font-weight:700; background:transparent; border:2px solid #ffe600; color:#ffe600; border-radius:.5rem; cursor:pointer; letter-spacing:3px; transition:all .2s }
.btn-start:hover:not(:disabled) { background:rgba(255,230,0,.08); box-shadow:0 0 25px rgba(255,230,0,.3); transform:scale(1.03) }
.btn-start:disabled { border-color:#334155; color:#334155; cursor:not-allowed; animation:none }

.gen-box { max-width:500px; width:100%; text-align:center }
.gen-header { display:flex; flex-direction:column; align-items:center; gap:.75rem; margin-bottom:1.5rem }
.gen-icon-ring { width:80px; height:80px; border-radius:50%; border:3px solid #00f0ff; display:flex; align-items:center; justify-content:center; box-shadow:0 0 30px rgba(0,240,255,.3); animation: ring-pulse 2s infinite }
@keyframes ring-pulse { 0%,100%{box-shadow:0 0 15px rgba(0,240,255,.2)} 50%{box-shadow:0 0 40px rgba(0,240,255,.5)} }
.gen-bug { font-size:2.5rem }
.spin-slow { display:inline-block; animation: spin-s 3s linear infinite }
@keyframes spin-s { to { transform: rotate(360deg) } }
.gen-title { font-family:'Orbitron',sans-serif; font-size:1.3rem; font-weight:900; letter-spacing:3px }

.gen-terminal { background:#0a0f1e; border:1px solid #1e293b; border-radius:10px; overflow:hidden; text-align:left; margin-bottom:1rem }
.term-header { background:#0f172a; padding:.4rem .75rem; display:flex; align-items:center; gap:6px; border-bottom:1px solid #1e293b }
.dot { width:10px; height:10px; border-radius:50% } .dot.red{background:#ff5f56} .dot.yellow{background:#ffbd2e} .dot.green{background:#27c93f}
.term-title { color:#64748b; font-size:.65rem; margin-left:6px; font-family:monospace }
.term-body { padding:.75rem; max-height:180px; overflow-y:auto; font-family:monospace; font-size:.72rem; line-height:1.6 }
.term-line { display:flex; gap:.5rem; color:#94a3b8 }
.term-latest { color:#00f0ff }
.term-prefix { color:#39ff14; font-weight:bold; flex-shrink:0 }
.term-file { color:#475569; margin-left:auto; font-size:.6rem }
.term-cursor { color:#00f0ff; font-size:.8rem }

.gen-progress { display:flex; align-items:center; gap:.75rem; margin-bottom:.5rem }
.gen-bar { flex:1; height:8px; background:#0f172a; border-radius:4px; overflow:hidden; border:1px solid rgba(0,240,255,.1) }
.gen-fill { height:100%; background:linear-gradient(90deg,#00f0ff,#38bdf8); border-radius:4px; transition:width .5s ease-out; box-shadow:0 0 10px rgba(0,240,255,.4) }
.gen-pct { font-family:'Orbitron',sans-serif; font-size:.8rem; font-weight:700; color:#00f0ff; min-width:40px; text-align:right }
.gen-status { color:#64748b; font-size:.75rem; letter-spacing:.5px }

.hud { display:flex; align-items:center; justify-content:space-between; padding:.6rem 1.2rem; margin:.5rem 1rem 0; background:rgba(8,12,30,.85); border:1px solid rgba(0,240,255,.1); border-radius:.75rem }
.hud-player { display:flex; align-items:center; gap:.6rem }
.hud-player.opp-side { flex-direction:row-reverse }
.hud-avatar { width:40px; height:40px; border-radius:50%; object-fit:cover; border:2px solid #00f0ff; box-shadow:0 0 10px rgba(0,240,255,.3) }
.opp-avatar { border-color:#ff2d75; box-shadow:0 0 10px rgba(255,45,117,.3) }
.hud-info { display:flex; flex-direction:column; gap:3px }
.hud-info.right { align-items:flex-end }
.hud-name { font-family:'Orbitron',sans-serif; font-size:.7rem; font-weight:700 }

.monster-bar { width:140px; height:8px; background:#0f172a; border-radius:4px; overflow:hidden; border:1px solid rgba(0,240,255,.1); position:relative }
.monster-fill { height:100%; background:linear-gradient(90deg,#00f0ff,#38bdf8); border-radius:4px; transition:width .3s }
.monster-fill.danger { background:linear-gradient(90deg,#ff2d75,#ef4444); animation: pulse-bar .5s infinite alternate }
.opp-fill { background:linear-gradient(90deg,#ff2d75,#f87171) }
.opp-fill.danger { background:linear-gradient(90deg,#ff0000,#dc2626) }
@keyframes pulse-bar { from{opacity:.7} to{opacity:1;box-shadow:0 0 8px rgba(255,45,117,.6)} }
.monster-count { position:absolute; top:50%; left:50%; transform:translate(-50%,-50%); font-size:.5rem; font-weight:bold; color:#fff; font-family:'Orbitron',sans-serif; white-space:nowrap }
.opp-bar .monster-fill { background:linear-gradient(90deg,#ff2d75,#f87171) }

.hud-center { display:flex; flex-direction:column; align-items:center; gap:3px }
.vs-pill { background:linear-gradient(135deg,#00f0ff,#38bdf8); color:#030712; padding:2px 14px; border-radius:20px; font-weight:900; font-size:.75rem; font-family:'Orbitron',sans-serif; letter-spacing:2px }
.combo-badge { font-family:'Orbitron',sans-serif; font-size:.75rem; font-weight:900; color:#fbbf24; text-shadow:0 0 10px rgba(251,191,36,.5) }
.combo-badge.mega { color:#ff2d75; animation: combo-flash .4s infinite alternate }
@keyframes combo-flash { from{transform:scale(1)} to{transform:scale(1.2)} }
.fever-tag { font-size:.6rem; color:#ff2d75; font-weight:bold; font-family:'Orbitron',sans-serif }

.arena { display:grid; grid-template-columns:1.2fr 1fr; gap:1rem; padding:.75rem 1.2rem; flex:1; position:relative; z-index:5 }
.play-screen { min-height:100vh; display:flex; flex-direction:column; position:relative }

.problem-panel { background:rgba(8,12,30,.8); border-radius:12px; border:1px solid rgba(0,240,255,.12); display:flex; flex-direction:column; gap:.6rem; padding:.8rem; transition:border-color .3s }
.problem-panel.pulse-warning { border-color:#ff2d75; box-shadow:0 0 20px rgba(255,45,117,.2) }
.prob-header { display:flex; align-items:center; gap:.4rem; flex-wrap:wrap }
.prob-badge { background:rgba(0,240,255,.08); color:#00f0ff; border:1px solid rgba(0,240,255,.3); padding:2px 10px; border-radius:20px; font-size:.6rem; font-weight:bold; font-family:'Orbitron',sans-serif; letter-spacing:1px }
.bug-type-badge { background:rgba(139,92,246,.12); color:#a78bfa; border:1px solid rgba(139,92,246,.4); padding:2px 8px; border-radius:20px; font-size:.6rem; font-weight:bold; font-family:'Orbitron',sans-serif }
.prob-file { color:#64748b; font-size:.7rem; margin-left:auto; font-family:monospace }

.error-log { background:rgba(0,0,0,.4); border:1px solid rgba(251,146,60,.25); border-radius:8px; padding:.4rem .6rem }
.log-label { color:#ffffff; font-size:.55rem; font-weight:bold; margin-bottom:4px; font-family:'Orbitron',sans-serif; letter-spacing:1px; background:rgba(251,146,60,.3); display:inline-block; padding:1px 6px; border-radius:3px }
.error-log pre { font-size:.68rem; color:#94a3b8; margin:0; white-space:pre-wrap; line-height:1.5 }

.code-block { border-radius:8px; overflow:hidden }
.code-head { background:#0a0f1e; padding:.35rem .65rem; display:flex; align-items:center; gap:6px; border-bottom:1px solid rgba(0,240,255,.06) }
.code-fname { color:#64748b; font-size:.65rem; margin-left:6px; font-family:monospace }
.code-body { background:#050a10; padding:.6rem; max-height:200px; overflow-y:auto }
.code-line { display:flex; align-items:baseline; gap:.6rem; padding:1px 0; border-radius:3px }
.code-line.bug-line { background:rgba(255,45,117,.08) }
.ln { color:#334155; font-size:.7rem; width:18px; text-align:right; flex-shrink:0; font-family:monospace }
.lc { color:#e0f2fe; font-size:.75rem; font-family:monospace; white-space:pre }
.lc.hl-bug { color:#ff2d75; text-decoration:underline wavy #ff2d75 }
.bug-marker { color:#ff2d75; font-size:.55rem; font-weight:bold; margin-left:auto; flex-shrink:0; font-family:'Orbitron',sans-serif }

.hint-box { background:rgba(0,240,255,.06); border:1px solid rgba(0,240,255,.2); border-radius:8px; padding:.4rem .6rem; font-size:.75rem; color:#a5f3fc }
.btn-hint { background:transparent; border:1px solid #1e293b; color:#64748b; padding:3px 10px; border-radius:6px; cursor:pointer; font-size:.65rem; font-family:'Orbitron',sans-serif; transition:all .2s }
.btn-hint:hover { border-color:#00f0ff; color:#00f0ff }

.choices-panel { background:rgba(8,12,30,.8); border-radius:12px; border:1px solid rgba(0,240,255,.12); padding:.8rem; display:flex; flex-direction:column; gap:.6rem }
.choices-label { font-size:.6rem; color:#64748b; font-weight:bold; font-family:'Orbitron',sans-serif; letter-spacing:1.5px }
.choices-list { display:flex; flex-direction:column; gap:.4rem }
.choice-btn { display:flex; align-items:center; gap:.6rem; background:#0a0f1e; border:1px solid #1e293b; border-radius:8px; padding:.6rem .8rem; cursor:pointer; color:#e0f2fe; text-align:left; transition:all .2s; width:100% }
.choice-btn:hover:not(:disabled) { border-color:#00f0ff; background:rgba(0,240,255,.06) }
.choice-btn:disabled { cursor:not-allowed }
.choice-key { width:22px; height:22px; border-radius:50%; border:1px solid #1e293b; display:flex; align-items:center; justify-content:center; font-size:.6rem; font-weight:bold; flex-shrink:0; color:#64748b; font-family:'Orbitron',sans-serif }
.choice-code { font-family:monospace; font-size:.73rem; color:#e0f2fe }
.choice-btn.correct-choice { border-color:#00f0ff; background:rgba(0,240,255,.08) }
.choice-btn.correct-choice .choice-key { border-color:#00f0ff; color:#00f0ff; background:rgba(0,240,255,.1) }
.choice-btn.wrong-choice { border-color:#ff2d75; background:rgba(255,45,117,.08) }
.choice-btn.wrong-choice .choice-key { border-color:#ff2d75; color:#ff2d75 }
.choice-btn.dim-choice { opacity:.35 }

.answer-fb { border-radius:8px; padding:.5rem .8rem; font-size:.8rem; font-weight:bold; font-family:'Orbitron',sans-serif; letter-spacing:.5px }
.answer-fb.correct { background:rgba(0,240,255,.08); border:1px solid rgba(0,240,255,.4); color:#00f0ff }
.answer-fb.wrong { background:rgba(255,45,117,.08); border:1px solid rgba(255,45,117,.4); color:#ff2d75 }

.monster-overlay { position:fixed; inset:0; pointer-events:none; z-index:30; overflow:hidden }
.monster-bug { position:absolute; user-select:none; filter:drop-shadow(0 0 8px rgba(255,123,114,.6)); animation:monster-wobble 2s infinite }
@keyframes monster-wobble { 0%,100%{transform:rotate(-5deg)} 50%{transform:rotate(5deg)} }

/* ── 유리 구슬 버블 ── */
.bubble-sphere {
  position: relative;
  width: 56px; height: 56px;
  border-radius: 50%;
  background: radial-gradient(
    circle at 35% 30%,
    rgba(255,255,255,0.55) 0%,
    rgba(0,240,255,0.18) 40%,
    rgba(0,180,255,0.08) 70%,
    transparent 100%
  );
  border: 1.5px solid rgba(0,240,255,0.5);
  box-shadow:
    0 0 12px rgba(0,240,255,0.5),
    0 0 28px rgba(0,240,255,0.25),
    inset 0 0 10px rgba(0,240,255,0.15);
  display: flex; align-items: center; justify-content: center;
  animation: bubble-float 1.8s ease-in-out infinite;
}
.bubble-sphere::before {
  content: '';
  position: absolute;
  top: 10%; left: 18%;
  width: 28%; height: 18%;
  background: rgba(255,255,255,0.6);
  border-radius: 50%;
  filter: blur(2px);
  transform: rotate(-30deg);
}
.bubble-monster {
  font-size: 1.5rem;
  filter: drop-shadow(0 0 4px rgba(0,0,0,0.6));
  animation: monster-trapped 1.6s ease-in-out infinite;
}
@keyframes bubble-float {
  0%,100% { transform: translateY(0) scale(1); }
  50% { transform: translateY(-5px) scale(1.04); }
}
@keyframes monster-trapped {
  0%,100% { transform: scale(1) rotate(-5deg); }
  50% { transform: scale(0.9) rotate(5deg); }
}

/* 날아가는 버블 */
.fly-bubble { position: absolute; }
.fly-bubble .bubble-sphere { width: 52px; height: 52px; }
.bubble-fly-enter-active { animation: fly-right .8s cubic-bezier(.4,0,.2,1) forwards; }
@keyframes fly-right {
  0%   { transform: translate(0,0) scale(1); opacity: 1; }
  50%  { transform: translate(250px,-80px) scale(.9); opacity: .9; }
  100% { transform: translate(600px,-30px) scale(.5); opacity: 0; }
}

.combo-popup { position:absolute; font-size:1.1rem; font-weight:900; color:#fbbf24; text-shadow:0 0 10px rgba(251,191,36,.8); white-space:nowrap; pointer-events:none }
.combo-pop-enter-active { animation: pop-up 1s ease-out forwards }
@keyframes pop-up { 0%{opacity:1;transform:translateY(0) scale(1)} 100%{opacity:0;transform:translateY(-60px) scale(1.3)} }

.slide-up-enter-active { transition:all .2s ease-out }
.slide-up-enter-from { opacity:0; transform:translateY(8px) }

.go-box { text-align:center; padding:2rem }
.go-title { font-family:'Orbitron',sans-serif; font-size:2.5rem; font-weight:900; color:#00f0ff; letter-spacing:4px }
.go-icon { font-size:3rem; margin:.5rem 0 }
.go-sub { color:#94a3b8; font-size:.85rem; margin-bottom:1.5rem }
.go-stats { display:flex; gap:2rem; justify-content:center; background:rgba(8,12,30,.8); padding:1.2rem 2.5rem; border-radius:12px; border:1px solid rgba(0,240,255,.15); margin-bottom:1.5rem }
.stat { display:flex; flex-direction:column; align-items:center; gap:.2rem }
.sl { font-size:.5rem; color:#64748b; font-family:'Orbitron',sans-serif; letter-spacing:1.5px }
.sv { font-size:1.8rem; font-weight:bold; font-family:'Orbitron',sans-serif }
.go-btns { display:flex; gap:1rem; justify-content:center }
.btn-retry { flex:1; max-width:180px; padding:.6rem; font-family:'Orbitron',sans-serif; font-size:.75rem; font-weight:700; background:transparent; border:2px solid #00f0ff; color:#00f0ff; border-radius:.6rem; cursor:pointer; transition:all .2s }
.btn-retry:hover { background:rgba(0,240,255,.1) }
.btn-exit { flex:1; max-width:180px; padding:.6rem; font-family:'Orbitron',sans-serif; font-size:.75rem; font-weight:700; background:transparent; border:1px solid #334155; color:#64748b; border-radius:.6rem; cursor:pointer }

/* 수신 버블 */
.incoming-bubble { position:absolute; z-index:35; pointer-events:none; }
.ib-sphere { width: 72px; height: 72px; }
.ib-sphere .bubble-monster { font-size: 2rem; }
.ib-flying { animation: ib-fly .7s cubic-bezier(.2,.8,.3,1) forwards }
.ib-pop .ib-sphere { animation: ib-burst-shell .6s ease-out forwards }
.ib-pop .bubble-monster { animation: ib-burst-monster .6s ease-out forwards }
.ib-pop::after { content:''; position:absolute; top:50%; left:50%; width:200px; height:200px; transform:translate(-50%,-50%); border-radius:50%; background:radial-gradient(circle, rgba(255,45,117,.5) 0%, rgba(255,45,117,0) 70%); animation: ib-shockwave .6s ease-out forwards; pointer-events:none }
@keyframes ib-fly {
  0% { right:-80px; top:var(--start-y); opacity:0; transform:scale(.5) }
  20% { opacity:1; transform:scale(1.1) }
  100% { left:var(--target-x); top:var(--target-y); opacity:1; transform:scale(1) }
}
@keyframes ib-burst-shell {
  0% { transform:scale(1); opacity:1 }
  30% { transform:scale(2.2); opacity:1; filter:brightness(3) drop-shadow(0 0 40px rgba(255,45,117,1)) }
  100% { transform:scale(3); opacity:0 }
}
@keyframes ib-burst-monster {
  0% { transform:translate(-50%,-50%) scale(1); opacity:1 }
  30% { transform:translate(-50%,-50%) scale(1.8); opacity:1 }
  100% { transform:translate(-50%,-50%) scale(.5); opacity:0 }
}
@keyframes ib-shockwave {
  0% { width:0; height:0; opacity:1 }
  100% { width:300px; height:300px; opacity:0 }
}
.bubble-flash::after { content:''; position:fixed; inset:0; background:rgba(255,45,117,.15); z-index:9000; pointer-events:none; animation:bflash .4s ease-out forwards }
@keyframes bflash { 0%{opacity:1} 100%{opacity:0} }

.incoming-alert { position:fixed; top:80px; left:50%; transform:translateX(-50%); z-index:50; background:rgba(255,45,117,.15); border:2px solid #ff2d75; border-radius:12px; padding:.5rem 1.5rem; backdrop-filter:blur(8px); box-shadow:0 0 30px rgba(255,45,117,.3); animation:alert-pulse .4s ease infinite alternate }
.alert-text { font-family:'Orbitron',sans-serif; font-size:.85rem; font-weight:700; color:#ff2d75; letter-spacing:1px; text-shadow:0 0 10px rgba(255,45,117,.6) }
@keyframes alert-pulse { from{box-shadow:0 0 15px rgba(255,45,117,.2)} to{box-shadow:0 0 40px rgba(255,45,117,.5)} }
.alert-slide-enter-active { transition:all .3s ease-out }
.alert-slide-leave-active { transition:all .4s ease-in }
.alert-slide-enter-from { opacity:0; transform:translateX(-50%) translateY(-20px) }
.alert-slide-leave-to { opacity:0; transform:translateX(-50%) translateY(-10px) }
</style>
