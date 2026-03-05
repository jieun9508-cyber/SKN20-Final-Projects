<template>
  <div class="pw-root">
    <!-- 트리거 버튼 -->
    <button v-if="!isOpen" class="pw-trigger" @click="isOpen = true">
      <span class="pw-trigger-icon">✨</span>
      <span>AI 포트폴리오 글 생성</span>
      <span class="pw-trigger-badge">NEW</span>
    </button>

    <!-- 패널 -->
    <transition name="pw-slide">
      <div v-if="isOpen" class="pw-panel">

        <!-- 헤더 -->
        <div class="pw-panel-header">
          <div class="pw-panel-title">
            <span>✨</span> AI 포트폴리오 글 생성
          </div>
          <button class="pw-close" @click="isOpen = false">✕</button>
        </div>

        <!-- Step 1: 형식 선택 -->
        <div v-if="!generated && !loading" class="pw-intro">
          <p class="pw-intro-desc">
            이 경험을 바탕으로 <strong>LinkedIn 포스팅</strong>과
            <strong>포트폴리오 설명</strong>을
            AI가 직접 써드려요.
          </p>
          <div class="pw-format-select">
            <div
              v-for="fmt in formats" :key="fmt.id"
              class="pw-fmt-card" :class="{ active: selectedFormats.includes(fmt.id) }"
              @click="toggleFormat(fmt.id)"
            >
              <span class="pw-fmt-icon">{{ fmt.icon }}</span>
              <div class="pw-fmt-info">
                <div class="pw-fmt-label">{{ fmt.label }}</div>
                <div class="pw-fmt-desc">{{ fmt.desc }}</div>
              </div>
              <span class="pw-fmt-check">{{ selectedFormats.includes(fmt.id) ? '✅' : '⬜' }}</span>
            </div>
          </div>
          <button class="pw-gen-btn" :disabled="selectedFormats.length === 0" @click="generate">
            🚀 글 생성하기
          </button>
        </div>

        <!-- 로딩 -->
        <div v-if="loading" class="pw-loading">
          <div class="pw-spinner"></div>
          <p class="pw-loading-text">AI가 포트폴리오 글을 작성 중...</p>
          <p class="pw-loading-sub">게임 경험을 분석해서 멋진 글로 만들고 있어요 ✍️</p>
        </div>

        <!-- 결과 -->
        <div v-if="generated && !loading" class="pw-results">
          <div class="pw-tabs">
            <button
              v-for="tab in resultTabs" :key="tab.id"
              class="pw-tab" :class="{ active: activeTab === tab.id }"
              @click="activeTab = tab.id"
            >{{ tab.icon }} {{ tab.label }}</button>
          </div>

          <div class="pw-content-area">
            <div v-for="tab in resultTabs" :key="tab.id" v-show="activeTab === tab.id">
              <div class="pw-content-box">
                <pre class="pw-content-text">{{ results[tab.id] }}</pre>
              </div>
              <div class="pw-content-actions">
                <button class="pw-copy-btn" @click="copyText(tab.id)">
                  {{ copiedTab === tab.id ? '✅ 복사됨!' : '📋 복사' }}
                </button>
                <button class="pw-regen-btn" @click="regenOne(tab.id)" :disabled="regenLoading === tab.id">
                  {{ regenLoading === tab.id ? '✍️...' : '🔄 다시 쓰기' }}
                </button>
              </div>
            </div>
          </div>

          <div class="pw-footer">
            <button class="pw-reset-btn" @click="reset">← 다시 설정</button>
            <button class="pw-all-copy-btn" @click="copyAll">📦 전체 복사</button>
          </div>
        </div>

        <!-- 에러 -->
        <div v-if="error" class="pw-error">
          ⚠️ {{ error }}
          <button @click="error = ''; generated = false; loading = false">다시 시도</button>
        </div>

      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  gameType:      { type: String,  required: true },   // 'arch' | 'logic'
  scenario:      { type: String,  default: '' },
  missionTitle:  { type: String,  default: '' },
  myScore:       { type: Number,  default: 0 },
  opponentScore: { type: Number,  default: 0 },
  resultText:    { type: String,  default: '' },
  grade:         { type: String,  default: '' },
  aiReview:      { type: String,  default: '' },
  // Arch 전용
  missions:      { type: Array,   default: () => [] },
  components:    { type: Array,   default: () => [] },
  arrowCount:    { type: Number,  default: 0 },
  // Logic 전용
  pseudocode:    { type: String,  default: '' },
  phase1Score:   { type: Number,  default: 0 },
  phase2Score:   { type: Number,  default: 0 },
  strengths:     { type: Array,   default: () => [] },
  weaknesses:    { type: Array,   default: () => [] },
})

// ─── 상태 ───────────────────────────────────────────────
const isOpen      = ref(false)
const loading     = ref(false)
const generated   = ref(false)
const error       = ref('')
const results     = ref({})
const activeTab   = ref('linkedin')
const copiedTab   = ref('')
const regenLoading = ref('')

const formats = [
  { id: 'linkedin',  icon: '💼', label: 'LinkedIn',     desc: '200~300자 감성 포스팅 + 해시태그' },
  { id: 'portfolio', icon: '📂', label: '포트폴리오',   desc: '기술 중심 프로젝트 설명 3~5문장' },
]

const selectedFormats = ref(['linkedin', 'portfolio'])
const resultTabs = computed(() => formats.filter(f => selectedFormats.value.includes(f.id)))

function toggleFormat(id) {
  if (selectedFormats.value.includes(id)) {
    if (selectedFormats.value.length > 1) {
      selectedFormats.value = selectedFormats.value.filter(f => f !== id)
    }
  } else {
    selectedFormats.value.push(id)
  }
}

// ─── 템플릿 기반 포트폴리오 생성 (AI 없음) ──────────────
function buildPortfolio(formatId) {
  const comps = props.components.map(c => (typeof c === 'string' ? c : `${c.icon || ''} ${c.name}`).trim()).join(', ')
  const compCount = props.components.length
  const result = props.resultText === 'WIN' ? '승리' : props.resultText === 'DRAW' ? '무승부' : '도전'
  const aiOneLine = props.aiReview ? props.aiReview.split('.')[0].trim() + '.' : ''

  if (props.gameType === 'arch') {
    const missions = props.missions && props.missions.length
      ? props.missions.map(m => `- ${m}`).join('\n')
      : '- 제한 시간 내 아키텍처 설계'

    if (formatId === 'linkedin') {
      return [
        `🏗️ [${props.missionTitle}] 시스템 아키텍처를 설계했습니다.`,
        ``,
        `📌 과제 상황`,
        props.scenario || '실무 시나리오 기반 아키텍처 설계',
        ``,
        `🔧 해결 방향`,
        missions,
        ``,
        `⚙️ 설계한 구조`,
        comps ? `${comps}를 배치하고 ${props.arrowCount}개의 흐름으로 연결했습니다.` : '컴포넌트를 배치하고 흐름을 연결했습니다.',
        aiOneLine ? `\n💬 ${aiOneLine}` : '',
        ``,
        `#시스템설계 #아키텍처 #백엔드 #문제해결`,
      ].filter(l => l !== null).join('\n').trim()
    }

    if (formatId === 'portfolio') {
      return [
        `📂 ${props.missionTitle} — 시스템 아키텍처 설계`,
        ``,
        `[상황]`,
        props.scenario || '실무 시나리오 기반 아키텍처 설계 과제.',
        ``,
        `[해결 과제]`,
        missions,
        ``,
        `[설계한 구조]`,
        comps
          ? `${comps}(${compCount}개 컴포넌트)를 배치하고 ${props.arrowCount}개의 데이터 흐름으로 연결.`
          : `${compCount}개 컴포넌트를 배치하고 ${props.arrowCount}개의 데이터 흐름으로 연결.`,
        aiOneLine ? `\n[검토 결과]\n${aiOneLine}` : '',
      ].filter(l => l !== null).join('\n').trim()
    }
  }

  // Logic Run 포맷
  const gradeLabel = { S: '최상위', A: '우수', B: '양호', C: '기초', F: '도전' }[props.grade] || ''
  const p1 = props.phase1Score ?? 0
  const p2 = props.phase2Score ?? 0
  const total = props.myScore ?? 0
  const resultKo = props.resultText === 'WIN' ? '승리' : props.resultText === 'DRAW' ? '무승부' : '도전'

  const strengthLines = props.strengths?.length
    ? props.strengths.map(s => `- ${s}`).join('\n')
    : ''
  const weaknessLines = props.weaknesses?.length
    ? props.weaknesses.map(w => `- ${w}`).join('\n')
    : ''
  const pseudoPreview = props.pseudocode
    ? props.pseudocode.trim().split('\n').slice(0, 6).join('\n')
    : ''

  if (formatId === 'linkedin') {
    return [
      `💻 AICE 실전 대비 로직 설계 챌린지 — ${resultKo}!`,
      ``,
      `📌 과제 상황`,
      props.scenario || 'AICE 실전 시나리오 기반 의사코드 설계',
      ``,
      `📊 결과`,
      `Phase1 스피드 퀴즈: ${p1}점 / 40점`,
      `Phase2 설계 스프린트: ${p2}점 / 60점`,
      `총점 ${total}점 — 등급 ${props.grade}${gradeLabel ? ` (${gradeLabel})` : ''}`,
      aiOneLine ? `\n💬 ${aiOneLine}` : '',
      strengthLines ? `\n✨ 강점\n${strengthLines}` : '',
      ``,
      `#AICE #알고리즘 #의사코드 #문제해결 #개발역량`,
    ].filter(l => l !== '').join('\n').trim()
  }

  return [
    `📂 AICE 실전 대비 — 비즈니스 로직 설계`,
    ``,
    `[상황]`,
    props.scenario || 'AICE 실전 시나리오 기반 의사코드 설계 과제.',
    ``,
    pseudoPreview ? `[작성한 의사코드 (일부)]\n${pseudoPreview}` : '',
    ``,
    `[결과]`,
    `Phase1 ${p1}점 / Phase2 ${p2}점 → 총 ${total}점 (등급 ${props.grade})`,
    aiOneLine ? `\n[AI 피드백]\n${aiOneLine}` : '',
    strengthLines ? `\n[강점]\n${strengthLines}` : '',
    weaknessLines ? `\n[개선점]\n${weaknessLines}` : '',
  ].filter(l => l !== '').join('\n').trim()
}

// ─── 전체 생성 (동기, AI 없음) ──────────────────────────
async function generate() {
  loading.value  = true
  error.value    = ''
  results.value  = {}

  // 살짝 딜레이 줘서 로딩 UX 유지
  await new Promise(r => setTimeout(r, 400))

  try {
    selectedFormats.value.forEach(fmtId => {
      results.value[fmtId] = buildPortfolio(fmtId)
    })
    generated.value = true
    activeTab.value = selectedFormats.value[0]
  } catch (e) {
    error.value = '포트폴리오 생성에 실패했어요.'
  } finally {
    loading.value = false
  }
}

// ─── 개별 재생성 (동기라서 즉시 반영) ──────────────────────
async function regenOne(formatId) {
  regenLoading.value = formatId
  await new Promise(r => setTimeout(r, 200))
  results.value[formatId] = buildPortfolio(formatId)
  regenLoading.value = ''
}

// ─── 복사 ────────────────────────────────────────────────
function copyText(tabId) {
  const text = results.value[tabId] || ''
  navigator.clipboard.writeText(text).catch(() => {
    const ta = document.createElement('textarea')
    ta.value = text; document.body.appendChild(ta); ta.select()
    document.execCommand('copy'); document.body.removeChild(ta)
  })
  copiedTab.value = tabId
  setTimeout(() => { copiedTab.value = '' }, 2000)
}

function copyAll() {
  const all = resultTabs.value
    .map(t => `===== ${t.icon} ${t.label} =====\n${results.value[t.id] || ''}`)
    .join('\n\n')
  navigator.clipboard.writeText(all).catch(() => {
    const ta = document.createElement('textarea')
    ta.value = all; document.body.appendChild(ta); ta.select()
    document.execCommand('copy'); document.body.removeChild(ta)
  })
}

function reset() {
  generated.value = false
  results.value   = {}
  error.value     = ''
}
</script>

<style scoped>
/* ── 트리거 버튼 ── */
.pw-trigger {
  display: flex; align-items: center; justify-content: center; gap: .5rem;
  width: 100%; padding: .7rem 1.2rem;
  background: linear-gradient(135deg, rgba(168,85,247,.12), rgba(0,240,255,.07));
  border: 1.5px solid rgba(168,85,247,.35);
  border-radius: .65rem; color: #a855f7;
  font-size: .8rem; font-weight: 700; cursor: pointer;
  font-family: 'Orbitron', sans-serif; letter-spacing: 1px;
  transition: all .25s; margin: .6rem 0;
}
.pw-trigger:hover {
  background: linear-gradient(135deg, rgba(168,85,247,.22), rgba(0,240,255,.12));
  box-shadow: 0 0 20px rgba(168,85,247,.2); transform: translateY(-2px);
}
.pw-trigger-icon { font-size: 1.1rem; }
.pw-trigger-badge {
  font-size: .48rem; padding: 2px 6px; letter-spacing: 1px;
  background: #a855f7; color: #fff; border-radius: 3px;
}

/* ── 패널 ── */
.pw-panel {
  background: linear-gradient(135deg, #050b18, #080d1c);
  border: 1.5px solid rgba(168,85,247,.28);
  border-radius: 1rem; padding: 1.2rem;
  margin: .5rem 0;
  box-shadow: 0 4px 30px rgba(168,85,247,.08);
}
.pw-panel-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: .9rem;
}
.pw-panel-title {
  display: flex; align-items: center; gap: .4rem;
  font-family: 'Orbitron', sans-serif; font-size: .7rem;
  font-weight: 700; color: #a855f7; letter-spacing: 1.5px;
}
.pw-close {
  background: none; border: none; color: #334155;
  font-size: .85rem; cursor: pointer; padding: 3px 7px;
  border-radius: 4px; transition: all .15s;
}
.pw-close:hover { color: #64748b; background: rgba(255,255,255,.05); }

/* ── 인트로 ── */
.pw-intro-desc {
  font-size: .78rem; color: #64748b; line-height: 1.65;
  margin-bottom: .9rem;
}
.pw-intro-desc strong { color: #c084fc; }

.pw-format-select { display: flex; flex-direction: column; gap: .35rem; margin-bottom: .9rem; }
.pw-fmt-card {
  display: flex; align-items: center; gap: .6rem;
  padding: .55rem .75rem;
  background: rgba(255,255,255,.02); border: 1px solid rgba(255,255,255,.06);
  border-radius: .5rem; cursor: pointer; transition: all .18s;
}
.pw-fmt-card:hover { background: rgba(168,85,247,.07); border-color: rgba(168,85,247,.2); }
.pw-fmt-card.active {
  background: rgba(168,85,247,.1); border-color: rgba(168,85,247,.38);
}
.pw-fmt-icon { font-size: .95rem; flex-shrink: 0; }
.pw-fmt-info { flex: 1; }
.pw-fmt-label { font-size: .78rem; font-weight: 700; color: #94a3b8; }
.pw-fmt-desc  { font-size: .65rem; color: #475569; margin-top: 1px; }
.pw-fmt-check { font-size: .7rem; }

.pw-gen-btn {
  width: 100%; padding: .68rem;
  background: linear-gradient(135deg, rgba(168,85,247,.18), rgba(0,240,255,.08));
  border: 1.5px solid rgba(168,85,247,.45);
  border-radius: .6rem; color: #a855f7;
  font-size: .8rem; font-weight: 700; cursor: pointer;
  font-family: 'Orbitron', sans-serif; letter-spacing: 1px;
  transition: all .2s;
}
.pw-gen-btn:hover:not(:disabled) {
  background: linear-gradient(135deg, rgba(168,85,247,.28), rgba(0,240,255,.12));
  box-shadow: 0 0 18px rgba(168,85,247,.22); transform: translateY(-1px);
}
.pw-gen-btn:disabled { opacity: .38; cursor: not-allowed; }

/* ── 로딩 ── */
.pw-loading {
  display: flex; flex-direction: column;
  align-items: center; gap: .65rem; padding: 1.5rem 0;
}
.pw-spinner {
  width: 30px; height: 30px;
  border: 3px solid rgba(168,85,247,.18); border-top-color: #a855f7;
  border-radius: 50%; animation: spin .75s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg) } }
.pw-loading-text { font-size: .82rem; color: #a855f7; font-weight: 600; }
.pw-loading-sub  { font-size: .7rem; color: #475569; }

/* ── 결과 ── */
.pw-tabs {
  display: flex; gap: .3rem; margin-bottom: .65rem;
}
.pw-tab {
  flex: 1; padding: .42rem;
  background: rgba(255,255,255,.03); border: 1px solid rgba(255,255,255,.07);
  border-radius: .4rem; color: #475569;
  font-size: .68rem; font-weight: 700; cursor: pointer;
  transition: all .15s; font-family: inherit;
}
.pw-tab.active {
  background: rgba(168,85,247,.12); border-color: rgba(168,85,247,.35);
  color: #c084fc;
}

.pw-content-box {
  background: #020810; border: 1px solid rgba(168,85,247,.13);
  border-radius: .5rem; padding: .85rem;
  max-height: 210px; overflow-y: auto; margin-bottom: .5rem;
}
.pw-content-box::-webkit-scrollbar { width: 4px; }
.pw-content-box::-webkit-scrollbar-thumb { background: rgba(168,85,247,.25); border-radius: 2px; }
.pw-content-text {
  font-family: 'Rajdhani', 'Space Grotesk', sans-serif;
  font-size: .78rem; color: #cbd5e1; line-height: 1.75;
  white-space: pre-wrap; word-break: break-word; margin: 0;
}

.pw-content-actions { display: flex; gap: .35rem; }
.pw-copy-btn, .pw-regen-btn {
  flex: 1; padding: .42rem; border-radius: .4rem;
  font-size: .7rem; font-weight: 700; cursor: pointer;
  font-family: inherit; transition: all .15s;
}
.pw-copy-btn {
  background: rgba(0,240,255,.07); border: 1px solid rgba(0,240,255,.22); color: #00f0ff;
}
.pw-copy-btn:hover { background: rgba(0,240,255,.14); }
.pw-regen-btn {
  background: rgba(100,116,139,.07); border: 1px solid rgba(100,116,139,.18); color: #64748b;
}
.pw-regen-btn:hover:not(:disabled) { background: rgba(100,116,139,.14); color: #94a3b8; }
.pw-regen-btn:disabled { opacity: .5; cursor: not-allowed; }

/* ── 푸터 ── */
.pw-footer {
  display: flex; gap: .35rem;
  padding-top: .7rem; border-top: 1px solid rgba(255,255,255,.04);
  margin-top: .7rem;
}
.pw-reset-btn {
  padding: .4rem .75rem; background: none;
  border: 1px solid rgba(100,116,139,.18); border-radius: .4rem;
  color: #475569; font-size: .7rem; cursor: pointer; font-family: inherit;
  transition: all .15s;
}
.pw-reset-btn:hover { color: #64748b; border-color: rgba(100,116,139,.3); }
.pw-all-copy-btn {
  flex: 1; padding: .4rem;
  background: rgba(168,85,247,.07); border: 1px solid rgba(168,85,247,.22);
  border-radius: .4rem; color: #a855f7;
  font-size: .7rem; font-weight: 700; cursor: pointer; font-family: inherit;
  transition: all .15s;
}
.pw-all-copy-btn:hover { background: rgba(168,85,247,.14); }

/* ── 에러 ── */
.pw-error {
  font-size: .76rem; color: #f87171;
  padding: .7rem; background: rgba(248,113,113,.06);
  border: 1px solid rgba(248,113,113,.18); border-radius: .5rem;
  display: flex; flex-direction: column; gap: .4rem; align-items: flex-start;
}
.pw-error button {
  font-size: .7rem; padding: .28rem .65rem;
  background: rgba(248,113,113,.1); border: 1px solid rgba(248,113,113,.25);
  border-radius: .35rem; color: #f87171; cursor: pointer; font-family: inherit;
}

/* ── 트랜지션 ── */
.pw-slide-enter-active, .pw-slide-leave-active { transition: all .28s ease; }
.pw-slide-enter-from, .pw-slide-leave-to { opacity: 0; transform: translateY(-6px); }
</style>
