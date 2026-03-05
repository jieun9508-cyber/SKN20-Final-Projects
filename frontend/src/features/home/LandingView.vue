<!-- 
수정일: 2026-01-23
수정내용: AI 엔지니어들을 위한 'Architecture Playground' 테마의 랜딩 페이지 구현.
          game_duck.mp4 배경, 운동하는 오리 GIF 및 플로팅 애니메이션 적용.
-->
<template>
  <div class="landing-container" ref="landingContainer" @scroll="handleScroll">
    <!-- [Hero Section] -->
    <header class="hero-playground-premium">
      <video id="hero-video" src="/image/game_duck.mp4" autoplay muted loop playsinline></video>
      <div class="hero-overlay-refined"></div>
      <div class="hero-scanline"></div>
      
      <div class="hero-content-premium">
        <div class="playground-badge-v2">
          <span class="badge-dot"></span>
          OPEN BETA v1.2
        </div>
        <h1 class="playground-title-v2">
          <span class="text-glow-premium">AI-Engineer</span><br>
          <span class="text-neon-ultimate">Playground!</span>
        </h1>
        <p class="playground-subtitle-v2">
          단순한 실습을 넘어선 압도적 AI 엔지니어링 경험.<br>
          이제 오리들과 함께 당신의 한계를 돌파하세요.
        </p>
        
        <div class="hero-action-group-v2">
          <button @click="$emit('go-to-playground')" class="btn-play-premium">
            <span>입장하기!</span>
            <ArrowRight class="btn-arrow" />
          </button>
          <!-- [2026-02-24] Job Planner 버튼: 로그인한 사용자에게만 노출되도록 v-if 추가 및 아이콘 적용 -->
          <button v-if="isLoggedIn" @click="$emit('open-job-planner')" class="btn-job-planner btn-planner-color">
            <span>Job Planner</span>
          </button>
          <!-- [2026-02-24] Interview 버튼: 로그인한 사용자에게만 노출되도록 v-if 추가 및 아이콘 적용 -->
          <button v-if="isLoggedIn" @click="$emit('open-interview')" class="btn-job-planner btn-interview-color">
            <span>Interview</span>
          </button>
          <!-- [수정일: 2026-02-24] Coduck Wars 버튼 제거 (Arcade Unit 카드로 이동됨) -->
        </div>
      </div>

      <!-- [Decorative Elements] -->
      <div class="hero-decor decor-1"></div>
      <div class="hero-decor decor-2"></div>
    </header>

    <!-- [Navigation Bar - Glassmorphism] -->
    <nav class="navbar-v2" :class="{ 'is-hidden': isScrolled }">
      <div class="logo-playground">
        <Gamepad2 class="logo-icon" />
        <span class="logo-text">AI-Arcade</span>
      </div>
      <div class="nav-links-v2">
        <a href="#chapters" class="nav-item" @click.prevent="scrollToSection('chapters')">
          <LayoutGrid class="nav-icon" />
          <span class="nav-label">Stages</span>
        </a>
        <a href="#leaderboard" class="nav-item" @click.prevent="scrollToSection('leaderboard')">
          <Trophy class="nav-icon" />
          <span class="nav-label">Ranking</span>
        </a>

        <div class="protein-status">
          <Zap class="icon-protein" />
          <span class="protein-count">{{ userProteinShakes }}</span>
        </div>
        <slot name="auth-buttons"></slot>
      </div>
    </nav>

    <nav class="navbar-v2 bookmark-mode" :class="{ 'is-visible': isScrolled }">
      <div class="logo-playground">
        <Gamepad2 class="logo-icon" />
      </div>
      <div class="nav-links-v2">
        <a href="#chapters" class="nav-item" @click.prevent="scrollToSection('chapters')">
          <LayoutGrid class="nav-icon" />
          <span class="nav-label">Stages</span>
        </a>
        <a href="#leaderboard" class="nav-item" @click.prevent="scrollToSection('leaderboard')">
          <Trophy class="nav-icon" />
          <span class="nav-label">Ranking</span>
        </a>

        <div class="protein-status">
          <Zap class="icon-protein" />
          <span class="protein-count">{{ userProteinShakes }}</span>
        </div>
        <slot name="auth-buttons"></slot>
      </div>
    </nav>

    <!-- [Chapters Section] -->
    <section id="chapters" class="playground-section-premium">
      <div class="background-grid-pattern"></div>
      <div class="section-header">
        <h2 class="title-with-mascot">
          Engineer's Arcade <Gamepad2 />
        </h2>
        <p>원하는 게임을 선택하고 당신의 실력을 증명하세요!</p>
      </div>

      <div class="playground-slider-container">
        <button class="slider-nav prev" @click="prevSlide">
          <ChevronLeft />
        </button>

        <div
          class="slider-wrapper"
          :class="{ dragging: isDragging }"
          @pointerdown="onDragStart"
          @pointermove="onDragMove"
          @pointerup="onDragEnd"
          @pointerleave="onDragEnd"
        >
          <div class="slider-track" :style="trackStyle">
            <div v-for="(chapter, idx) in chapters" :key="chapter.id" 
                 class="gym-card-premium" 
                 :style="{ '--unit-color': chapter.color }"
                 :class="[
                   'card-color-' + (idx % 5),
                   { 'active': idx === currentIdx, 
                     'prev': idx === getPrevIdx, 
                     'next': idx === getNextIdx,
                     'hidden': !isIndexVisible(idx)
                   }
                 ]">
              <div class="card-inner-v2">
                <div class="card-image-wrap-v2">
                  <div class="energy-rings">
                    <span class="ring-1"></span>
                    <span class="ring-2"></span>
                    <span class="ring-3"></span>
                  </div>
                  <img :src="chapter.image" :alt="chapter.name" class="premium-icon">
                  <div class="card-aura-premium"></div>
                </div>
                <div class="card-text-v2">
                  <!-- [2026-01-25] 유닛 정보 영역: DB(PracticeUnit) 필드 연동 -->
                  <div class="unit-badge-row">
                    <!-- 1. 유닛 번호 표시 (최소 2자리 숫자로 포맷팅, 예: UNIT 01) -->
                    <span class="unit-tag-v2">
                      <component :is="chapter.icon" style="width: 14px; height: 14px; margin-right: 4px;" />
                      UNIT {{ String(chapter.unit_number).padStart(2, '0') }}
                    </span>
                    <!-- 2. 권장 레벨 표시 (예: LV.10) -->
                    <span class="level-indicator">LV.{{ chapter.level }}</span>
                  </div>
                  <!-- 3. 유닛 제목 및 부제목(설명) 표시 -->
                  <h3>{{ chapter.name }}</h3>
                  <p>{{ chapter.description }}</p>
                  
                  <div class="card-footer-v2">
                    <!-- 4. 참여 인원 데이터 표시 (예: 85+ Training) -->
                    <span class="engineer-count">
                      <Users style="width: 14px; height: 14px; display: inline-block; vertical-align: middle; margin-right: 4px;" /> 
                      {{ chapter.participant_count }}+ Played
                    </span>
                    <button class="btn-enter-mini" @click="handleCardClick(chapter, idx)">START</button>
                  </div>
                </div>
              </div>
              <div class="card-border-glow"></div>
            </div>
          </div>
        </div>


        <button class="slider-nav next" @click="nextSlide">
          <ChevronRight />
        </button>

        <!-- Pagination Dots (chapters + Coduck Wars) -->
        <div class="slider-pagination">
          <span v-for="(_, idx) in chapters" :key="'dot-'+idx"
                class="dot" :class="{ 'active': idx === currentIdx }"
                @click="goToSlide(idx)"></span>

        </div>
      </div>
    </section>

    <!-- [Leaderboard Section Premium] -->
    <section id="leaderboard" class="lb-section-premium">
      <div class="background-grid-pattern"></div>
      <div class="lb-energy-pulse"></div>
      <div class="lb-header-v2">
        <span class="lb-subtitle">ENGINEER RANKING</span>
        <div class="title-row-with-btn">
          <h2>오늘의 명예 전당 🏆</h2>
          <button @click="showBadgeGuide = !showBadgeGuide" class="btn-guide-toggle" :class="{ 'active': showBadgeGuide }">
            <Info class="icon-info" v-if="!showBadgeGuide" />
            <span v-if="!showBadgeGuide">배지 등급 가이드</span>
            <span v-else>가이드 닫기</span>
          </button>
        </div>
        <p>아키텍처 마스터들이 아케이드를 빛내고 있습니다. (Page {{ leaderboardCurrentPage }} / {{ leaderboardTotalPages }})</p>
      </div>

      <!-- [2026-02-19 추가] 배지 등급 가이드 (Guide) - 토글식으로 변경 -->
      <transition name="guide-slide">
        <div v-if="showBadgeGuide" class="lb-badge-guide">
          <div class="guide-title">BADGE PROGRESS GUIDE</div>
          <div class="guide-items">
            <div class="guide-item locked">
              <div class="unit-badge-mini locked">U0</div>
              <span>Locked (0%)</span>
            </div>
            <div class="guide-item started">
              <div class="unit-badge-mini started unit-color-1">U1</div>
              <span>Started (1-49%)</span>
            </div>
            <div class="guide-item advanced">
              <div class="unit-badge-mini advanced unit-color-1">U1</div>
              <span>Advanced (50-99%)</span>
            </div>
            <div class="guide-item completed">
              <div class="unit-badge-mini completed unit-color-1">U1</div>
              <span>Completed (100%)</span>
            </div>
            <div class="guide-item mastered">
              <div class="unit-badge-mini mastered">U1</div>
              <span>Mastered (Perfect)</span>
            </div>
          </div>
        </div>
      </transition>
      
      <div class="lb-glass-table-v2" :class="{ 'lb-locked': !isLoggedIn }">
          <div class="lb-table-head">
            <span class="col-rank">Rank</span>
            <span class="col-user">Engineer</span>
            <span class="col-solved">Stages Mastered</span>
            <span class="col-shakes">Arcade Points</span>
          </div>
          <div v-for="(user, index) in leaderboard" :key="user.id"
               class="lb-row-v2" :class="'row-rank-' + user.rank">
            <div class="col-rank">
              <div class="rank-box">
                <span class="rank-num">#{{ user.rank }}</span>
                <Crown v-if="user.rank === 1" class="crown-icon" />
              </div>
            </div>
            <div class="col-user">
              <AvatarFrame
                :src="user.avatar_url"
                :rank="user.current_grade || 'BRONZE'"
                size="50px"
                hoverZoom
                class="user-avatar-mini"
              />
              <span class="username-premium">{{ user.nickname }}</span>
            </div>
            <div class="col-solved">
              <div class="unit-badges-container">
                <div v-for="unit in (user.mastered_units || [])"
                     :key="unit.unit_id"
                     class="unit-badge-mini"
                     :class="[
                       'unit-color-' + unit.unit_number,
                       (unit.unit_status || 'LOCKED').toLowerCase(),
                       { 'locked': !unit.is_completed, 'mastered': unit.is_perfect }
                     ]"
                     :title="getUnitTooltip(unit)"
                >
                  U{{ unit.unit_number }}
                </div>
              </div>
            </div>
            <div class="col-shakes">
              <div class="shake-badge-v2">
                <Zap class="milk-icon-v2" />
                <span>{{ user.points.toLocaleString() }}</span>
              </div>
            </div>
          </div>

          <!-- [수정일: 2026-02-09] 페이징 컨트롤 UI 추가 -->
          <div class="lb-pagination" v-if="leaderboardTotalPages > 1">
            <button
              class="btn-pg prev"
              :disabled="leaderboardCurrentPage === 1"
              @click="$emit('change-page', leaderboardCurrentPage - 1)"
            >
              <ChevronLeft style="width: 20px;" />
            </button>

            <div class="pg-numbers">
              <span
                v-for="p in leaderboardTotalPages"
                :key="'pg-'+p"
                class="pg-num"
                :class="{ active: p === leaderboardCurrentPage }"
                @click="$emit('change-page', p)"
              >
                {{ p }}
              </span>
            </div>

            <button
              class="btn-pg next"
              :disabled="leaderboardCurrentPage === leaderboardTotalPages"
              @click="$emit('change-page', leaderboardCurrentPage + 1)"
            >
              <ChevronRight style="width: 20px;" />
            </button>
          </div>

          <!-- [수정일: 2026-02-26] 비로그인 시 블러 잠금 오버레이 -->
          <div v-if="!isLoggedIn" class="lb-lock-overlay">
            <div class="lb-lock-content">
              <div class="lb-lock-icon-wrap">
                <svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
              </div>
              <p class="lb-lock-title">로그인 후 확인할 수 있습니다</p>
              <p class="lb-lock-desc">명예의 전당은 로그인한 엔지니어만 열람 가능합니다</p>
            </div>
          </div>
      </div>
    </section>

    <footer class="playground-footer">
      <p>&copy; 2026 AI-ARCADE. Crafted with ❤️ by Final 5 Team</p>
    </footer>

    <!-- [2026-01-24] 최상단 복귀용 프리미엄 Home 버튼 추가 -->
    <transition name="home-pop">
      <button v-if="isScrolled" @click="scrollToTop" class="btn-floating-home" aria-label="Scroll to top">
        <Home class="home-icon" />
        <div class="home-glow"></div>
      </button>
    </transition>
  </div>
</template>

<script>
import {
  Gamepad2,
  LayoutGrid,
  Trophy,
  Zap,
  ArrowRight,
  ChevronLeft,
  ChevronRight,
  Users,
  Crown,
  Home,
  Play,
  Settings,
  LogOut,
  Info,
  Briefcase,
  Swords
} from 'lucide-vue-next';
import AvatarFrame from '@/components/AvatarFrame.vue';

export default {
  name: 'LandingView',
  components: {
    AvatarFrame,
    Users,
    Crown,
    Zap,
    ChevronLeft,
    ChevronRight,
    Play,
    Settings,
    History,
    LogOut,
    Home,
    Gamepad2,
    LayoutGrid,
    Trophy,
    ArrowRight,
    Info,
    Briefcase,
    Swords
  },
  props: {
    isLoggedIn: Boolean,
    userProteinShakes: Number,
    chapters: Array,
    leaderboard: Array,
    leaderboardCurrentPage: Number,
    leaderboardTotalPages: Number
  },
  data() {
    return {
      currentIdx: 0,
      isScrolled: false,
      scrollTicking: false,
      hoverTimer: null,
      isDragging: false,
      dragMoved: false,
      dragStartX: 0,
      dragThreshold: 120,
      showBadgeGuide: false
    };
  },
  computed: {
    // 1. 이전 카드 인덱스 계산 (방어 로직 포함)
    getPrevIdx() {
      if (!this.chapters || this.chapters.length === 0) return 0;
      return (this.currentIdx - 1 + this.totalSlides) % this.totalSlides;
    },
    // 2. 다음 카드 인덱스 계산 (방어 로직 포함)
    getNextIdx() {
      if (!this.chapters || this.chapters.length === 0) return 0;
      return (this.currentIdx + 1) % this.totalSlides;
    },
    totalSlides() {
      return this.chapters ? this.chapters.length : 0;
    },
    trackStyle() {
      // 슬라이더 트랙 커스텀 스타일 (필요 시 확장)
      return {};
    }
  },
  methods: {
    /**
     * [아이콘 새로고침]
     * - Lucide 라이브러리를 사용하여 DOM 내의 data-lucide 아이콘들을 렌더링합니다.
     */
    refreshIcons() {
      this.$nextTick(() => {
        if (window.lucide) {
          window.lucide.createIcons();
        }
      });
    },
    /**
     * [스크롤 이벤트 핸들러]
     * - 일정 높이 이상 스크롤 시 상단 바의 디자인을 변경(isScrolled)합니다.
     */
    handleScroll() {
      if (this.scrollTicking) return;
      this.scrollTicking = true;
      requestAnimationFrame(() => {
        const container = this.$refs.landingContainer;
        if (container) {
          this.isScrolled = container.scrollTop > 100;
        }
        this.scrollTicking = false;
      });
    },
    scrollToSection(sectionId) {
      const container = this.$refs.landingContainer;
      const section = document.getElementById(sectionId);
      if (!container || !section) return;
      container.scrollTo({ top: section.offsetTop, behavior: 'smooth' });
    },
    scrollToLeaderboard() {
      this.scrollToSection('leaderboard');
    },
    /**
     * [최상단 복귀]
     * - 버튼 클릭 시 히어로 영역으로 부드럽게 스크롤합니다.
     */
    scrollToTop() {
      const container = this.$refs.landingContainer;
      if (container) {
        container.scrollTo({ top: 0, behavior: 'smooth' });
      }
    },
    nextSlide() {
      this.currentIdx = (this.currentIdx + 1) % this.totalSlides;
    },
    prevSlide() {
      this.currentIdx = (this.currentIdx - 1 + this.totalSlides) % this.totalSlides;
    },
    goToSlide(idx) {
      this.currentIdx = Math.min(idx, this.totalSlides - 1);
    },

    /**
     * [수정일: 2026-02-24] 콤덕 워즈 포함 전체 totalSlides 기준으로 래핑
     * - Coduck Wars(chapters.length)가 활성일 때 첫 번째 카드도 올바르게 주변에 나타납니다.
     */
    isIndexVisible(idx) {
      if (!this.chapters || this.chapters.length === 0) return false;
      const diff = Math.abs(idx - this.currentIdx);
      return diff <= 1 || diff === this.totalSlides - 1;
    },
    /**
     * [카드 호버 핸들러]
     * - 마우스가 근처 카드에 상주할 때만 전환되도록 지연(250ms)을 둡니다.
     * - 빠른 마우스 이동으로 인한 오작동을 방지합니다.
     */
    handleCardHover(idx) {
      if (this.currentIdx === idx) return;
      
      clearTimeout(this.hoverTimer);
      this.hoverTimer = setTimeout(() => {
        this.currentIdx = idx;
      }, 250); // 0.25초 이상 머물렀을 때만 전환
    },
    /**
     * [호버 타이머 초기화]
     * - 마우스가 카드를 벗어나면 전환 예약을 취소합니다.
     */
    clearHoverTimer() {
      clearTimeout(this.hoverTimer);
    },
    onDragStart(event) {
      if (event.button !== 0) return;
      if (event.target.closest('button') || event.target.closest('a')) return;
      this.isDragging = true;
      this.dragMoved = false;
      this.dragStartX = event.clientX;
      event.currentTarget.setPointerCapture?.(event.pointerId);
    },
    onDragMove(event) {
      if (!this.isDragging) return;
      const deltaX = event.clientX - this.dragStartX;
      if (Math.abs(deltaX) < this.dragThreshold) return;
      this.dragMoved = true;
      const direction = deltaX > 0 ? -1 : 1;
      // [수정일: 2026-02-24] chapters.length → totalSlides: Coduck Wars 포함 전체 슬라이드 기준으로 드래그 이동
      if (this.totalSlides > 0) {
        this.currentIdx = (this.currentIdx + direction + this.totalSlides) % this.totalSlides;
      }
      this.dragStartX = event.clientX;
    },
    onDragEnd(event) {
      if (!this.isDragging) return;
      this.isDragging = false;
      event.currentTarget.releasePointerCapture?.(event.pointerId);
    },
    /**
     * [카드 클릭 핸들러]
     * - 이미 선택된 카드 클릭 시 상세 팝업을 열고, 아니면 해당 카드를 중앙으로 이동시킵니다.
     */
    handleCardClick(chapter, idx) {
      if (this.dragMoved) {
        this.dragMoved = false;
        return;
      }
      if (idx === this.currentIdx) {
        if (chapter.name === 'Coduck Wars' || chapter.name === 'Battle Game') {
          this.$emit('open-coduck-wars');
        } else {
          this.$emit('open-unit', chapter);
        }
      } else {
        this.currentIdx = idx;
      }
    },
    /**
     * [배지 툴팁 텍스트 생성]
     * - 유닛의 진행 상태(미션 완료 수, 완벽 정복 수)를 기반으로 상세 정보를 제공합니다.
     */
    getUnitTooltip(unit) {
      if (!unit) return '';
      const { unit_number, unit_status, solved_count, total_count, perfect_count } = unit;
      
      const header = `UNIT ${unit_number}: `;
      const statusLabel = unit_status || 'LOCKED';

      if (statusLabel === 'MASTERED') {
        return `${header}완벽 정복! (${perfect_count}/${total_count} 미션 마스터 🏆)`;
      } else if (statusLabel === 'COMPLETED') {
        return `${header}모든 미션 완료 (${solved_count}/${total_count} 미션 통과 ✅)`;
      } else if (statusLabel === 'ADVANCED') {
        const progressPercent = total_count > 0 ? Math.round((solved_count / total_count) * 100) : 0;
        return `${header}심화 진행 중 (${progressPercent}%, ${solved_count}/${total_count} 완료 🚀)`;
      } else if (statusLabel === 'STARTED') {
        const progressPercent = total_count > 0 ? Math.round((solved_count / total_count) * 100) : 0;
        return `${header}기초 진행 중 (${progressPercent}%, ${solved_count}/${total_count} 완료 🏃)`;
      } else {
        return `${header}데이터 없음 (학습 전 🔒)`;
      }
    }
  },
  mounted() {
    this.$nextTick(() => {
      this.refreshIcons();
    });
    window.addEventListener('scroll', this.handleScroll);
  },
  unmounted() {
    window.removeEventListener('scroll', this.handleScroll);
    clearTimeout(this.hoverTimer);
  },
  updated() {
    this.$nextTick(() => {
      this.refreshIcons();
    });
  }
}
</script>

<style scoped src="./LandingView.css"></style>
