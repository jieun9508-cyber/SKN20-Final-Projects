<template>
  <div class="wars-container">
    <div class="hero-scanline"></div>
    <div class="bg-decor decor-1"></div>
    <div class="bg-decor decor-2"></div>

    <header class="wars-header">
      <button class="exit-btn" @click="goTo('/dashboard')">← 나가기</button>
      <div class="header-badge">
        <span class="badge-dot"></span>
        BATTLE GAME
      </div>
      <h1 class="wars-title">
        <span class="title-white">당신의 </span><span class="title-green">실력,</span><br/>
        <span class="title-white">친구와 겨뤄보세요</span>
      </h1>
      <p class="wars-sub">1vs1 실시간 아키텍처 배틀 · 지금 바로 붙어보자</p>
    </header>

    <main class="wars-grid">

      <!-- 로직 런 -->
      <div class="game-card" @click="goTo('/practice/wars/logic-run')">
        <div class="card-border-glow glow-green"></div>

        <!-- 비주얼 영역 -->
        <div class="card-visual">
          <div class="visual-bg visual-bg-green"></div>
          <div class="visual-ring vr-outer vr-green"></div>
          <div class="visual-ring vr-inner vr-green" style="animation-direction:reverse"></div>
          <div class="visual-aura va-green"></div>
          <div class="visual-frame vf-green">
            <span class="visual-emoji">🏃</span>
          </div>
          <div class="visual-particles">
            <span class="vp vp-green" style="--d:0deg;--r:70px;--delay:0s"></span>
            <span class="vp vp-green" style="--d:72deg;--r:70px;--delay:0.4s"></span>
            <span class="vp vp-green" style="--d:144deg;--r:70px;--delay:0.8s"></span>
            <span class="vp vp-green" style="--d:216deg;--r:70px;--delay:1.2s"></span>
            <span class="vp vp-green" style="--d:288deg;--r:70px;--delay:1.6s"></span>
          </div>
        </div>

        <div class="card-body">
          <div class="card-tag tag-green">SPEED BATTLE</div>
          <h2 class="card-title">로직 런</h2>
          <p class="card-desc">빈칸 채우기 스피드전 + 설계 드로잉 대결.<br/>더 빠르고 정확한 엔지니어가 승리한다.</p>
          <div class="card-chips">
            <span class="chip chip-green">빈칸 채우기</span>
            <span class="chip chip-green">스피드</span>
            <span class="chip chip-green">의사코드</span>
          </div>
          <div class="card-footer">
            <div class="card-meta">
              <span>⏱ 10분</span><span>👥 1vs1</span><span>⭐ 중급</span>
            </div>
            <button class="btn-enter btn-green">시작하기 →</button>
          </div>
        </div>
      </div>

      <!-- 버그버블 몬스터 -->
      <div class="game-card card-featured" @click="goTo('/practice/wars/bug-bubble')">
        <div class="card-border-glow glow-pink"></div>
        <div class="featured-label">🔥 HOT</div>

        <div class="card-visual">
          <div class="visual-bg visual-bg-pink"></div>
          <div class="visual-ring vr-outer vr-pink"></div>
          <div class="visual-ring vr-inner vr-pink" style="animation-direction:reverse"></div>
          <div class="visual-aura va-pink"></div>
          <div class="visual-frame vf-pink">
            <span class="visual-emoji">🫧</span>
          </div>
          <div class="visual-particles">
            <span class="vp vp-pink" style="--d:0deg;--r:70px;--delay:0s"></span>
            <span class="vp vp-pink" style="--d:72deg;--r:70px;--delay:0.4s"></span>
            <span class="vp vp-pink" style="--d:144deg;--r:70px;--delay:0.8s"></span>
            <span class="vp vp-pink" style="--d:216deg;--r:70px;--delay:1.2s"></span>
            <span class="vp vp-pink" style="--d:288deg;--r:70px;--delay:1.6s"></span>
          </div>
        </div>

        <div class="card-body">
          <div class="card-tag tag-pink">DEFENSE BATTLE</div>
          <h2 class="card-title">버그버블 몬스터</h2>
          <p class="card-desc">문제를 풀고 버그를 가둬 상대에게 날려라.<br/>보글보글 1:1 디펜스 승부.</p>
          <div class="card-chips">
            <span class="chip chip-pink">디버깅</span>
            <span class="chip chip-pink">몬스터 어택</span>
            <span class="chip chip-pink">서바이벌</span>
          </div>
          <div class="card-footer">
            <div class="card-meta">
              <span>⏱ 무제한</span><span>👤 1vs1</span><span>🔥 버그 파티</span>
            </div>
            <button class="btn-enter btn-pink">시작하기 →</button>
          </div>
        </div>
      </div>

      <!-- 아키텍처 캐치마인드 -->
      <div class="game-card" @click="goTo('/practice/wars/draw-quiz')">
        <div class="card-border-glow glow-blue"></div>

        <div class="card-visual">
          <div class="visual-bg visual-bg-blue"></div>
          <div class="visual-ring vr-outer vr-blue"></div>
          <div class="visual-ring vr-inner vr-blue" style="animation-direction:reverse"></div>
          <div class="visual-aura va-blue"></div>
          <div class="visual-frame vf-blue">
            <span class="visual-emoji">🎨</span>
          </div>
          <div class="visual-particles">
            <span class="vp vp-blue" style="--d:0deg;--r:70px;--delay:0s"></span>
            <span class="vp vp-blue" style="--d:72deg;--r:70px;--delay:0.4s"></span>
            <span class="vp vp-blue" style="--d:144deg;--r:70px;--delay:0.8s"></span>
            <span class="vp vp-blue" style="--d:216deg;--r:70px;--delay:1.2s"></span>
            <span class="vp vp-blue" style="--d:288deg;--r:70px;--delay:1.6s"></span>
          </div>
        </div>

        <div class="card-body">
          <div class="card-tag tag-blue">AI DRAWING BATTLE</div>
          <h2 class="card-title">아키텍처 캐치마인드</h2>
          <p class="card-desc">제시된 아키텍처를 드래그&드롭으로 설계.<br/>AI가 실시간으로 평가하는 1vs1 배틀.</p>
          <div class="card-chips">
            <span class="chip chip-blue">시스템 설계</span>
            <span class="chip chip-blue">드로잉</span>
            <span class="chip chip-blue">AI 리뷰</span>
          </div>
          <div class="card-footer">
            <div class="card-meta">
              <span>⏱ 90초</span><span>👤 1vs1</span><span>⭐ 초급~중급</span>
            </div>
            <button class="btn-enter btn-blue">시작하기 →</button>
          </div>
        </div>
      </div>

    </main>

    <!-- 전적 -->
    <footer class="wars-footer">
      <div class="records-panel">
        <div class="records-header">
          <span>⚔️ BATTLE RECORDS</span>
          <button class="reset-btn" @click="resetRecords">↺ 초기화</button>
        </div>
        <div v-if="!records.length" class="records-empty">아직 전적이 없습니다. 첫 대전을 시작하세요!</div>
        <template v-else>
          <div class="records-col-header">
            <span class="col-name">플레이어</span>
            <span class="col-w">승</span><span class="col-d">무</span><span class="col-l">패</span>
            <span class="col-rate">승률</span>
          </div>
          <div class="records-row" v-for="(r, idx) in records" :key="r.name">
            <span class="rec-rank">{{ idx === 0 ? '👑' : '#' + (idx + 1) }}</span>
            <span class="col-name rec-name">{{ r.name }}</span>
            <span class="col-w stat-win">{{ r.win }}</span>
            <span class="col-d stat-draw">{{ r.draw }}</span>
            <span class="col-l stat-lose">{{ r.lose }}</span>
            <span class="col-rate">
              <span class="rate-bar-wrap"><span class="rate-bar" :style="{ width: winRate(r) + '%' }"></span></span>
              <span class="rate-txt">{{ winRate(r) }}%</span>
            </span>
          </div>
        </template>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { loadBattleRecords, clearBattleRecords } from './useBattleRecord.js';
import { useAuthStore } from '@/stores/auth';

const router = useRouter();
const auth = useAuthStore();
const rawRecords = ref([]);

onMounted(async () => {
  rawRecords.value = await loadBattleRecords(auth.sessionNickname);
});

const records = computed(() =>
  [...rawRecords.value]
    .map(r => ({ ...r, total: r.win + r.draw + r.lose }))
    .sort((a, b) => {
      const rA = a.total ? a.win / a.total : 0;
      const rB = b.total ? b.win / b.total : 0;
      return rB !== rA ? rB - rA : b.win - a.win;
    })
);

function winRate(r) {
  const total = r.win + r.draw + r.lose;
  return total ? Math.round((r.win / total) * 100) : 0;
}
function resetRecords() {
  if (!confirm('전적을 모두 삭제하시겠습니까?')) return;
  clearBattleRecords();
  rawRecords.value = [];
}
const goTo = (path) => router.push(path);
</script>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700;800;900&display=swap');

/* ===== 베이스 ===== */
.wars-container {
  min-height: 100vh;
  background-color: #0c0e14;
  color: #fff;
  font-family: 'Outfit', sans-serif;
  padding: 3rem 2rem 4rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3rem;
  position: relative;
  overflow: hidden;
}

.hero-scanline {
  position: fixed; inset: 0;
  background: linear-gradient(to bottom, transparent, rgba(182,255,64,0.04) 50%, transparent);
  background-size: 100% 4px;
  z-index: 0; pointer-events: none;
  animation: scan 10s linear infinite;
}
@keyframes scan {
  from { transform: translateY(-100%); }
  to   { transform: translateY(100%); }
}

.bg-decor {
  position: absolute;
  background: rgba(182,255,64,0.08);
  border: 1px solid rgba(182,255,64,0.15);
  border-radius: 50%;
  filter: blur(40px);
  z-index: 0; pointer-events: none;
}
.decor-1 { width: 500px; height: 500px; top: -150px; left: -150px; animation: float-decor 20s infinite alternate; }
.decor-2 { width: 350px; height: 350px; bottom: 0; right: -80px; animation: float-decor 25s infinite alternate-reverse; }
@keyframes float-decor {
  from { transform: translate(0,0); }
  to   { transform: translate(80px,80px); }
}

/* ===== 헤더 ===== */
.wars-header {
  position: relative; z-index: 10;
  text-align: center; max-width: 700px;
}

.exit-btn {
  position: fixed; top: 1.5rem; right: 1.5rem;
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.1);
  color: #94a3b8;
  padding: 0.5rem 1rem; border-radius: 12px;
  font-family: 'Outfit', sans-serif; font-size: 0.9rem; font-weight: 600;
  cursor: pointer; transition: all 0.3s; z-index: 100;
}
.exit-btn:hover { background: rgba(255,255,255,0.08); color: #fff; border-color: rgba(255,255,255,0.2); }

.header-badge {
  display: inline-flex; align-items: center; gap: 10px;
  background: rgba(255,255,255,0.03); backdrop-filter: blur(10px);
  padding: 0.6rem 1.5rem; border-radius: 99px;
  font-weight: 800; font-size: 0.85rem; letter-spacing: 2px;
  margin-bottom: 1.5rem;
  border: 1px solid rgba(255,255,255,0.1); color: #fff;
}

.badge-dot {
  width: 8px; height: 8px;
  background: #b6ff40; border-radius: 50%;
  box-shadow: 0 0 10px #b6ff40;
  animation: pulse-dot 1s infinite; flex-shrink: 0;
}
@keyframes pulse-dot {
  0%,100% { transform: scale(1); opacity: 1; }
  50%      { transform: scale(1.5); opacity: 0.5; }
}

.wars-title {
  font-size: clamp(2.5rem, 6vw, 4.5rem);
  font-weight: 950; line-height: 1.1;
  margin-bottom: 1rem; letter-spacing: -0.02em;
}
.title-white { color: #fff; text-shadow: 0 0 30px rgba(255,255,255,0.3); }
.title-green {
  background: linear-gradient(90deg, #b6ff40, #34d399, #b6ff40);
  background-size: 200% auto;
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  filter: drop-shadow(0 0 15px rgba(182,255,64,0.4));
  animation: shine 3s linear infinite;
}
@keyframes shine { to { background-position: 200% center; } }

.wars-sub { color: #94a3b8; font-size: 1.1rem; font-weight: 400; }

/* ===== 카드 그리드 ===== */
.wars-grid {
  position: relative; z-index: 10;
  display: grid; grid-template-columns: repeat(3, 1fr);
  gap: 1.5rem; max-width: 1200px; width: 100%;
}

.game-card {
  position: relative;
  background: rgba(255,255,255,0.03);
  backdrop-filter: blur(20px);
  border-radius: 32px;
  border: 1px solid rgba(255,255,255,0.08);
  cursor: pointer;
  transition: all 0.4s cubic-bezier(0.23, 1, 0.32, 1);
  overflow: hidden;
}
.game-card:hover {
  transform: translateY(-8px) scale(1.02);
  border-color: rgba(255,255,255,0.15);
  box-shadow: 0 30px 60px rgba(0,0,0,0.5);
  background: rgba(255,255,255,0.06);
}

.card-featured {
  border-color: rgba(255,45,117,0.25);
  background: rgba(255,45,117,0.03);
}
.card-featured:hover {
  border-color: rgba(255,45,117,0.5);
  box-shadow: 0 30px 60px rgba(255,45,117,0.15);
}

.featured-label {
  position: absolute; top: 1.25rem; right: 1.25rem;
  background: rgba(255,45,117,0.15);
  border: 1px solid rgba(255,45,117,0.3);
  color: #ff2d75;
  font-size: 0.7rem; font-weight: 800; letter-spacing: 1px;
  padding: 4px 10px; border-radius: 99px; z-index: 10;
}

/* 테두리 글로우 */
.card-border-glow {
  position: absolute; inset: -1px; border-radius: 32px; padding: 1px;
  -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor; mask-composite: exclude;
  opacity: 0; transition: opacity 0.4s; pointer-events: none;
}
.glow-green { background: linear-gradient(135deg, rgba(182,255,64,0.6), transparent, rgba(52,211,153,0.4)); }
.glow-pink  { background: linear-gradient(135deg, rgba(255,45,117,0.6), transparent, rgba(168,85,247,0.4)); }
.glow-blue  { background: linear-gradient(135deg, rgba(56,189,248,0.6), transparent, rgba(99,102,241,0.4)); }
.game-card:hover .card-border-glow { opacity: 1; }

/* ===== 카드 비주얼 영역 (이미지 대신 이모지 + 이펙트) ===== */
.card-visual {
  position: relative;
  width: 100%;
  height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

/* 배경 그라디언트 */
.visual-bg {
  position: absolute; inset: 0;
  opacity: 0.25;
}
.visual-bg-green { background: radial-gradient(circle at 50% 60%, rgba(182,255,64,0.5) 0%, transparent 70%); }
.visual-bg-pink  { background: radial-gradient(circle at 50% 60%, rgba(255,45,117,0.5) 0%, transparent 70%); }
.visual-bg-blue  { background: radial-gradient(circle at 50% 60%, rgba(56,189,248,0.5) 0%, transparent 70%); }
.game-card:hover .visual-bg { opacity: 0.45; }

/* 회전 링 */
.visual-ring {
  position: absolute;
  border-radius: 50%;
  border-style: dashed;
  border-width: 1px;
}
.vr-outer { width: 160px; height: 160px; animation: spin-ring 8s linear infinite; }
.vr-inner { width: 110px; height: 110px; animation: spin-ring 5s linear infinite; }
.vr-green { border-color: rgba(182,255,64,0.3); }
.vr-pink  { border-color: rgba(255,45,117,0.3); }
.vr-blue  { border-color: rgba(56,189,248,0.3); }
@keyframes spin-ring {
  from { transform: rotate(0deg); }
  to   { transform: rotate(360deg); }
}

/* 내부 광원 */
.visual-aura {
  position: absolute;
  width: 100px; height: 100px;
  border-radius: 50%;
  filter: blur(20px);
  animation: aura-pulse 2s ease-in-out infinite;
}
.va-green { background: rgba(182,255,64,0.3); }
.va-pink  { background: rgba(255,45,117,0.3); }
.va-blue  { background: rgba(56,189,248,0.3); }
@keyframes aura-pulse {
  0%,100% { transform: scale(1); opacity: 0.6; }
  50%      { transform: scale(1.3); opacity: 1; }
}

/* 이모지 프레임 — 메인 LP판 스타일 */
.visual-frame {
  position: relative; z-index: 5;
  width: 100px; height: 100px;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  background: rgba(0,0,0,0.6);
  box-shadow: 0 20px 50px rgba(0,0,0,0.8), inset 0 0 20px rgba(255,255,255,0.05);
  transition: transform 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}
.game-card:hover .visual-frame { transform: scale(1.12); }

.vf-green { border: 2px solid rgba(182,255,64,0.5); box-shadow: 0 0 30px rgba(182,255,64,0.3), inset 0 0 20px rgba(0,0,0,0.5); }
.vf-pink  { border: 2px solid rgba(255,45,117,0.5); box-shadow: 0 0 30px rgba(255,45,117,0.3), inset 0 0 20px rgba(0,0,0,0.5); }
.vf-blue  { border: 2px solid rgba(56,189,248,0.5); box-shadow: 0 0 30px rgba(56,189,248,0.3), inset 0 0 20px rgba(0,0,0,0.5); }

.visual-emoji {
  font-size: 2.8rem;
  line-height: 1;
  filter: drop-shadow(0 4px 12px rgba(0,0,0,0.5));
  transition: transform 0.3s;
}
.game-card:hover .visual-emoji { transform: scale(1.1) rotate(-5deg); }

/* 궤도 파티클 */
.visual-particles {
  position: absolute; inset: 0;
  pointer-events: none;
}
.vp {
  position: absolute;
  top: 50%; left: 50%;
  width: 5px; height: 5px;
  border-radius: 50%;
  transform:
    translate(-50%, -50%)
    rotate(var(--d))
    translateX(var(--r));
  animation: orbit 4s linear infinite;
  animation-delay: var(--delay);
}
.vp-green { background: #b6ff40; box-shadow: 0 0 6px #b6ff40; }
.vp-pink  { background: #ff2d75; box-shadow: 0 0 6px #ff2d75; }
.vp-blue  { background: #38bdf8; box-shadow: 0 0 6px #38bdf8; }
@keyframes orbit {
  0%   { opacity: 0; transform: translate(-50%,-50%) rotate(var(--d)) translateX(var(--r)) scale(0); }
  20%  { opacity: 1; }
  80%  { opacity: 1; }
  100% { opacity: 0; transform: translate(-50%,-50%) rotate(calc(var(--d) + 360deg)) translateX(var(--r)) scale(0); }
}

/* ===== 카드 바디 ===== */
.card-body {
  padding: 1.5rem 2rem 2rem;
  display: flex; flex-direction: column;
  position: relative; z-index: 1;
}

.card-tag {
  font-weight: 900; font-size: 0.7rem; letter-spacing: 2px;
  padding: 4px 12px; border-radius: 6px;
  display: inline-block; margin-bottom: 1rem; width: fit-content;
}
.tag-green { color: #b6ff40; background: rgba(182,255,64,0.1); border: 1px solid rgba(182,255,64,0.2); }
.tag-pink  { color: #ff2d75; background: rgba(255,45,117,0.1); border: 1px solid rgba(255,45,117,0.2); }
.tag-blue  { color: #38bdf8; background: rgba(56,189,248,0.1); border: 1px solid rgba(56,189,248,0.2); }

.card-title {
  font-size: 1.5rem; font-weight: 950;
  color: #fff; margin-bottom: 0.5rem; line-height: 1.2;
}

.card-desc {
  color: #94a3b8; font-size: 0.9rem;
  line-height: 1.6; margin-bottom: 1.25rem; flex: 1;
}

.card-chips {
  display: flex; flex-wrap: wrap; gap: 0.4rem; margin-bottom: 1.25rem;
}
.chip {
  font-size: 0.72rem; font-weight: 700;
  padding: 4px 10px; border-radius: 8px;
}
.chip-green { color: #b6ff40; background: rgba(182,255,64,0.08); border: 1px solid rgba(182,255,64,0.15); }
.chip-pink  { color: #ff2d75; background: rgba(255,45,117,0.08); border: 1px solid rgba(255,45,117,0.15); }
.chip-blue  { color: #38bdf8; background: rgba(56,189,248,0.08); border: 1px solid rgba(56,189,248,0.15); }

.card-footer {
  display: flex; align-items: center; justify-content: space-between;
  padding-top: 1.25rem;
  border-top: 1px solid rgba(255,255,255,0.05);
  margin-top: auto;
}

.card-meta {
  display: flex; gap: 0.75rem;
  font-size: 0.78rem; color: #475569; font-weight: 600;
}

.btn-enter {
  border: none; padding: 10px 22px; border-radius: 12px;
  font-family: 'Outfit', sans-serif; font-weight: 950; font-size: 0.9rem;
  cursor: pointer; transition: all 0.4s cubic-bezier(0.23,1,0.32,1);
}
.btn-green { background: #b6ff40; color: #0c0e14; box-shadow: 0 4px 15px rgba(182,255,64,0.2); }
.btn-green:hover { transform: scale(1.05) translateY(-2px); box-shadow: 0 10px 25px rgba(182,255,64,0.4); }
.btn-pink  { background: #ff2d75; color: #fff; box-shadow: 0 4px 15px rgba(255,45,117,0.2); }
.btn-pink:hover  { transform: scale(1.05) translateY(-2px); box-shadow: 0 10px 25px rgba(255,45,117,0.4); }
.btn-blue  { background: #38bdf8; color: #0c0e14; box-shadow: 0 4px 15px rgba(56,189,248,0.2); }
.btn-blue:hover  { transform: scale(1.05) translateY(-2px); box-shadow: 0 10px 25px rgba(56,189,248,0.4); }

/* ===== 전적 ===== */
.wars-footer { position: relative; z-index: 10; width: 100%; max-width: 700px; }

.records-panel {
  background: rgba(255,255,255,0.02);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 24px; padding: 1.5rem 2rem;
}
.records-header {
  display: flex; align-items: center; justify-content: space-between;
  font-size: 0.8rem; font-weight: 800; color: #64748b;
  letter-spacing: 2px; margin-bottom: 1rem;
}
.reset-btn {
  background: transparent; border: 1px solid rgba(255,255,255,0.08);
  color: #475569; padding: 3px 10px; border-radius: 8px;
  font-size: 0.75rem; cursor: pointer; font-family: 'Outfit', sans-serif; transition: all 0.2s;
}
.reset-btn:hover { color: #ff2d75; border-color: rgba(255,45,117,0.3); }
.records-empty { text-align: center; color: #334155; font-size: 0.9rem; padding: 1rem 0; }
.records-col-header {
  display: flex; align-items: center; gap: 0.5rem;
  padding: 0.25rem 0.5rem; font-size: 0.65rem; font-weight: 700;
  letter-spacing: 1px; color: #334155;
  border-bottom: 1px solid rgba(255,255,255,0.04); margin-bottom: 0.4rem;
}
.records-row {
  display: flex; align-items: center; gap: 0.5rem;
  padding: 0.5rem; border-radius: 10px; transition: background 0.2s;
}
.records-row:hover { background: rgba(255,255,255,0.03); }
.rec-rank { width: 24px; text-align: center; font-size: 0.85rem; flex-shrink: 0; }
.rec-name { font-weight: 700; font-size: 0.85rem; color: #e2e8f0; }
.col-name { flex: 1; }
.col-w, .col-d, .col-l { width: 28px; text-align: center; flex-shrink: 0; }
.col-rate { width: 100px; display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
.stat-win  { font-weight: 700; font-size: 0.85rem; color: #b6ff40; }
.stat-draw { font-weight: 700; font-size: 0.85rem; color: #94a3b8; }
.stat-lose { font-weight: 700; font-size: 0.85rem; color: #f87171; }
.rate-bar-wrap { flex: 1; height: 4px; background: rgba(255,255,255,0.05); border-radius: 2px; overflow: hidden; }
.rate-bar { height: 100%; background: linear-gradient(90deg,#b6ff40,#34d399); border-radius: 2px; transition: width 0.5s; }
.rate-txt { font-size: 0.7rem; color: #64748b; font-weight: 600; white-space: nowrap; }

/* ===== 반응형 ===== */
@media (max-width: 1024px) {
  .wars-grid { grid-template-columns: 1fr; max-width: 500px; }
}
@media (max-width: 768px) {
  .wars-title { font-size: 2.5rem; }
  .card-visual { height: 160px; }
}
</style>
