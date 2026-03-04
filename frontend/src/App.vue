<!--
수정일: 2026-01-31
수정내용: 
1. 캐릭터 브랜딩 전면 교체: 'Lion' 명칭을 'Coduck'으로 변경하고 픽사 스타일 캐릭터 이미지 적용.
2. 유닛 2/3 로딩 문제 해결: displayProblems 계산 시 매번 최신 데이터를 매핑하도록 수정하여 캐시 및 캐스팅 이슈 해결.
3. 유닛 매칭 유연화: 유닛 제목 비교 시 대소문자 및 공백을 무시하도록 정규화 로직 도입.
-->
<template>
  <div id="app" v-cloak>
    <!-- [메인 페이지 배경 (맵)] -->
    <LandingView
      v-if="!isPracticePage"
      :isLoggedIn="auth.isLoggedIn"
      :userProteinShakes="auth.userProteinShakes"
      :chapters="game.chapters"
      :leaderboard="leaderboard"
      :leaderboardCurrentPage="leaderboardCurrentPage"
      :leaderboardTotalPages="leaderboardTotalPages"
      @change-page="fetchLeaderboard"
      @go-to-playground="handleGoToPlayground"
      @open-unit="openUnitPopup"
      @open-job-planner="handleOpenJobPlanner"
      @open-interview="handleOpenInterview"
      @open-coduck-wars="handleOpenCoduckWars"
    >
      <template #auth-buttons>
        <template v-if="!auth.isLoggedIn">
          <button class="btn-login-ref" @click="ui.openLogin">Login</button>
          <button class="btn-signup-ref" @click="ui.openSignUp">Sign Up</button>
        </template>
        <div v-else class="user-profile-v2">
          <div class="user-info-v2">
            <span class="user-name-v2">{{ auth.sessionNickname }}</span>
            <span class="user-rank-v2">{{ auth.userRank }}</span>
          </div>
          <AvatarFrame 
            :src="auth.userAvatarUrl" 
            :rank="auth.userRank" 
            size="40px" 
            class="user-avatar-header" 
            v-if="auth.isLoggedIn"
          />
          <button class="btn-history" @click="router.push('/my-records')">My Records</button>
          <button class="btn-coach" @click="router.push('/coach')">AI Coach</button>
          <button v-if="auth.user?.is_superuser" class="btn-mgmt" @click="router.push('/management/progress')">Management</button>
          <button class="btn-profile-settings" @click="ui.isProfileSettingsModalOpen = true">Setting</button>
          <button class="btn-logout-v2" @click="auth.logout">Logout</button>
        </div>
      </template>
    </LandingView>

    <!-- [라우터 뷰 - Practice 페이지 (HUD 오버레이 스타일)] -->
    <router-view v-if="isPracticePage" @close="handlePracticeClose"></router-view>

      <!-- [유닛 상세 팝업 모달] -->
      <transition name="fade">
        <div v-if="ui.isUnitModalOpen" class="modal-overlay" @click.self="ui.isUnitModalOpen = false">
          <div class="unit-detail-modal">
            <header class="unit-modal-header-v3">
              <div class="title-section-v3">
                <div class="unit-label-v3">
                  {{ game.activeUnit?.name === 'Debug Practice' ? 'DEBUG ARCADE' : 'UNIT ' + (game.activeUnit?.unit_number || game.chapters.indexOf(game.activeUnit) + 1) }}
                </div>
                <h2 class="unit-name-v3">
                  <template v-if="game.activeUnit?.name === 'Debug Practice'">
                    🐞 Bug Hunt
                  </template>
                  <template v-else-if="game.activeUnit?.name === 'Pseudo Practice'">
                    <!-- [수정일: 2026-01-31] 유닛 1 모드 통합: AI Detective, Pseudo Forest 등의 개별 타이틀을 제거하고 통합 타이틀로 표시 -->
                    💻 Pseudo Code Practice
                  </template>
                  <template v-else>
                    {{ game.activeUnit?.unitTitle || (game.activeUnit?.problems && game.activeUnit.problems[0]?.title) || game.activeUnit?.name || 'Loading...' }}
                  </template>
                </h2>
              </div>
              <div class="header-actions-v3">
                <button class="close-btn-v3" @click="ui.isUnitModalOpen = false">&times;</button>
              </div>
            </header>

            <div class="unit-modal-body-v3">
              <!-- [2026-02-19] path-container-v3 높이를 문제 개수에 맞춰 동적 계산 -->
              <div class="path-container-v3" :style="{ height: containerHeight + 'px' }">
                <!-- [2026-02-19] SVG 동적 생성 복구 (문제 개수에 따라 자동 조절) -->
                <svg class="path-svg-v3" :viewBox="`0 0 800 ${svgViewBoxHeight}`">
                  <line
                    v-for="(p, i) in pathPoints.slice(0, -1)"
                    :key="i"
                    :x1="p[0]" :y1="p[1]"
                    :x2="pathPoints[i+1][0]" :y2="pathPoints[i+1][1]"
                    class="path-line-v3"
                    :class="{ 'line-unlocked': isUnlocked(i + 1) }"
                  />
                </svg>

                <!-- [2026-02-19] pathPoints 동적 스타일 복구 (문제 개수에 따라 자동 배치) -->
                <div v-for="(problem, pIdx) in displayProblems" :key="problem.id" class="node-platform-v3"
                :class="{
                  active: problem.questIndex === currentMaxIdx,
                  unlocked: game.currentUnitProgress.includes(problem.questIndex)
                }"
                :style="{ left: pathPoints[pIdx][0] + 'px', top: pathPoints[pIdx][1] + 'px' }"
                @click="isUnlocked(problem.questIndex) && selectProblem(problem)">

                <div class="platform-glow-v3" v-if="problem.questIndex === currentMaxIdx"></div>

                <div class="platform-circle-v3">
                  <template v-if="game.currentUnitProgress.includes(problem.questIndex)">
                    <AvatarFrame 
                      v-if="problem.questIndex === currentMaxIdx"
                      :src="auth.userAvatarUrl" 
                      :rank="auth.userRank" 
                      size="120px" 
                      class="duck-on-node-v3 user-avatar-on-node"
                    />
                    <div style="width: 20px; height: 20px; background: #b6ff40; border-radius: 50%; box-shadow: 0 0 10px #b6ff40;"></div>
                  </template>
                  <template v-else>
                    <i data-lucide="lock" class="lock-icon-v3"></i>
                  </template>
                </div>

                <div class="node-label-premium">
                  {{ problem.displayNum || problem.title }} - {{ problem.title }}
                </div>
              </div>

              <!-- Decorative Locked Nodes -->
              <!-- [2026-02-19] pathPoints 동적 스타일 복구 -->
              <div v-for="i in displayLabelsCount" :key="'extra-' + i" class="node-platform-v3 locked"
                :style="{ left: pathPoints[displayProblems.length + i - 1][0] + 'px', top: pathPoints[displayProblems.length + i - 1][1] + 'px' }">
                <div class="platform-circle-v3">
                  <i data-lucide="lock" class="lock-icon-v3"></i>
                </div>
              </div>
            </div>
          </div>

            <footer class="unit-stats-bar-v3">
              <!-- [수정일: 2026-02-19] 모든 트랙에 동일한 stat-pill 스타일 적용 -->
              <div class="stat-pill-v3 active"><i data-lucide="check-circle" style="width: 16px;"></i>{{ game.currentUnitProgress.length }}개 활성화</div>
              <div class="stat-pill-v3 locked"><i data-lucide="lock" style="width: 16px;"></i>{{ displayProblems.length - game.currentUnitProgress.length }}개 잠금</div>
            </footer>
          </div>
        </div>
      </transition>

    <!-- [전역 모달 통합 컨테이너] -->
    <GlobalModals />
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUpdated, nextTick } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import axios from 'axios';
import { useAuthStore } from '@/stores/auth';
import { useGameStore } from '@/stores/game';
import { useUiStore } from '@/stores/ui';

import './style.css';
import LandingView from './features/home/LandingView.vue';
import AvatarFrame from '@/components/AvatarFrame.vue';
import GlobalModals from './components/GlobalModals.vue';

// Stores
const auth = useAuthStore();
const game = useGameStore();
const ui = useUiStore();

// Router
const route = useRoute();
const router = useRouter();

// Local State
const leaderboard = ref([]);
const leaderboardCurrentPage = ref(1);
const leaderboardTotalPages = ref(1);

// [수정일: 2026-02-09] 리더보드 페이징 연동
const fetchLeaderboard = async (page = 1) => {
    try {
        const response = await axios.get(`/api/core/activity/leaderboard/?page=${page}`);
        leaderboard.value = response.data.leaderboard;
        leaderboardCurrentPage.value = response.data.current_page;
        leaderboardTotalPages.value = response.data.total_pages;
    } catch (error) {
        console.error("Failed to fetch leaderboard:", error);
    }
};


// Computed
const isPracticePage = computed(() => {
  // PseudoCode는 페이지/모달 하이브리드로 동작 (isPracticePage에 포함하여 배경 제어)
  const practiceRoutes = [
    'PseudoCode',
    'SystemArchitecturePractice',
    'BugHunt',
    'Wars',
    'ArchDrawQuiz',
    'LogicRun',
    'BugBubbleMonster',
    'GrowthReport',
    'Management',
    'MyRecords',
    'AICoach',
    'MockInterview',
    'LogViewer'
  ];
  return practiceRoutes.includes(route?.name);

});

const displayProblems = computed(() => {
  const activeUnit = game.activeUnit;
  if (!activeUnit) return [];

  // [수정일: 2026-02-19] initGame에서 이미 계산된 problems 직접 사용
  // (activeUnit은 이미 변환된 chapters 객체이므로 mapDetailsToProblems 재호출 불필요)
  return activeUnit.problems || [];
});

const displayLabelsCount = computed(() => {
  const currentCount = displayProblems.value?.length || 0;
  const targetCount = game.activeUnit?.name === 'Debug Practice' ? 9 : 10;
  return Math.max(0, targetCount - currentCount);
});

// [2026-02-19] 징검다리 노드 위치 좌표 계산 (지그재그 패턴, Y축 +40px 조정)
const pathPoints = computed(() => {
  // [수정일: 2026-02-19] displayProblems의 실제 길이 사용 (Math.max 제거)
  const count = (displayProblems.value?.length || 10) + displayLabelsCount.value;
  const points = [];
  for (let i = 0; i < count; i++) {
    const y = 100 + i * 150 + 40;  // Y축 +40px (노드와 정렬)
    let x;
    const mod = i % 5;
    if (mod === 0) x = 400;
    else if (mod === 1) x = 560;
    else if (mod === 2) x = 280;
    else if (mod === 3) x = 520;
    else x = 360;
    points.push([x, y]);
  }
  return points;
});

// [2026-02-19] SVG viewBox 높이 동적 계산 (문제 개수에 정확히 맞춤)
const svgViewBoxHeight = computed(() => {
  const count = (displayProblems.value?.length || 10) + displayLabelsCount.value;
  return 140 + (count - 1) * 150;
});

// [2026-02-19] path-container-v3 높이 동적 계산 (문제 개수에 따라)
const containerHeight = computed(() => {
  const count = (displayProblems.value?.length || 10) + displayLabelsCount.value;
  return 140 + (count - 1) * 150 + 100;  // 마지막 노드 아래 여유 공간
});

const currentMaxIdx = computed(() => {
  const progress = game.currentUnitProgress;
  const displayedIndices = displayProblems.value.map(p => p.questIndex);
  if (displayedIndices.length === 0) return 0;

  // [수정일: 2026-01-28] 현재 화면에 표시된 문제들 중 '해금된 마지막' 문제를 선택하여 오리 위치 고정
  // 이렇게 하면 항상 해금된 노드에 오리가 앉게 되어 즉시 클릭(선택)이 가능해집니다.
  const unlockedIndices = displayedIndices.filter(idx => progress.includes(idx));
  
  if (unlockedIndices.length > 0) {
    return Math.max(...unlockedIndices);
  }
  
  // 만약 현재 난이도에서 아무것도 해금되지 않았다면(이론상 불가) 첫 번째 노드 반환
  return displayedIndices[0];
});

// [수정일: 2026-01-28] 라우트 감시: 연습 페이지에서 홈으로 돌아올 때 유닛 상세 모달 자동 재개
watch(() => route.name, async (newNav, oldNav) => {
  const practiceRoutes = ['PseudoCode', 'SystemArchitecturePractice', 'BugHunt'];
  // 연습 페이지에서 홈('/')으로 돌아오는 경우
  if (newNav === 'Home' && practiceRoutes.includes(oldNav)) {
    if (game.activeUnit) {
      // [2026-02-24 수정] 연습 완료 후 최신 진행도를 서버에서 다시 불러와 스테이지 맵 반영
      if (auth.isLoggedIn) {
        const { useProgressStore } = await import('@/stores/progress');
        const progressStore = useProgressStore();
        await progressStore.fetchAllProgress();
      }
      ui.isUnitModalOpen = true;
      nextTick(() => { if (window.lucide) window.lucide.createIcons(); });
    }
  }
});

// Methods

function isUnlocked(pIdx) {
  return game.currentUnitProgress.includes(pIdx);
}

function openUnitPopup(unit) {
  if (!auth.isLoggedIn) {
    ui.isAuthRequiredModalOpen = true;
    return;
  }
  game.setActiveUnit(unit);
  if (unit?.name === 'Debug Practice') {
    game.currentDebugMode = 'bug-hunt';
  }
  ui.isUnitModalOpen = true;
  nextTick(() => {
    if (window.lucide) window.lucide.createIcons();
  });
}

function selectProblem(problem) {
  if (!auth.isLoggedIn) {
    ui.isAuthRequiredModalOpen = true;
    return;
  }

  game.activeProblem = problem;
  game.activeChapter = game.activeUnit;
  ui.isUnitModalOpen = false;

  const rawName = game.activeUnit?.name || '';
  const chapterName = rawName.toLowerCase().replace(/\s+/g, '');

  if (chapterName.includes('pseudo')) {
    game.selectedQuestIndex = problem.questIndex || 0;
    // [수정일: 2026-02-06] 의사코드(Pseudocode) 관련 파일들은 이제 pseudocode 폴더에서 관리됩니다.
    router.push('/practice/pseudo-code');
  } else if (chapterName.includes('system')) {
    game.selectedSystemProblemIndex = problem.problemIndex || 0;
    router.push({ path: '/practice/system-architecture', query: { problem: problem.problemIndex || 0 } });
  } else if (chapterName.includes('debug')) {
    // Bug Hunt 미션으로 이동
    router.push({
      path: '/practice/bug-hunt',
      query: { missionId: problem.id, mapMode: 'true' }
    });
  } else if (chapterName.includes('agent')) {
    ui.isAgentModalOpen = true;
    nextTick(() => {
      if (window.lucide) window.lucide.createIcons();
    });
  } else {
    ui.isConstructionModalOpen = true;
  }
}

function handlePracticeClose() {
    // [2026-02-08] 기록 조회나 관리 화면에서 나갈 때는 유닛 모달을 띄우지 않음
    const noModalRoutes = ['Management', 'MyRecords', 'AICoach'];
    const currentRouteName = route.name;

    ui.isPseudoCodeOpen = false;
    router.push('/');

    // 일반 실습(퀘스트 등) 종료 시에만 유닛 선택 팝업을 다시 보여주어 연속성 유지
    if (!noModalRoutes.includes(currentRouteName)) {
        ui.isUnitModalOpen = true;
    }
}

function selectGameMode(mode) {
  game.currentDebugMode = mode;

  nextTick(() => {
    if (window.lucide) window.lucide.createIcons();
  });
}

function handleGoToPlayground() {
  if (auth.isLoggedIn) {
    document.getElementById('chapters')?.scrollIntoView({ behavior: 'smooth' });
  } else {
    ui.isAuthRequiredModalOpen = true;
  }
}

function handleOpenJobPlanner() {
  ui.isJobPlannerModalOpen = true;
}

function handleOpenInterview() {
  router.push('/interview');
}

function handleOpenCoduckWars() {
  router.push('/practice/wars');
}

// Lifecycle
onMounted(async () => {
  await auth.checkSession();
  
  // 로그인 검증 후 전역 진행도(DB) 동기화
  if (auth.isLoggedIn) {
    const { useProgressStore } = await import('@/stores/progress');
    const progressStore = useProgressStore();
    await progressStore.fetchAllProgress();
  }

  game.initGame();
  fetchLeaderboard(); // [수정일: 2026-02-06] 리더보드 데이터 호출
  nextTick(() => {
    if (window.lucide) window.lucide.createIcons();
  });
});

// [2026-01-24] 라우트 설정을 감시하여 Unit 1 모달 강제 제어 (필요 시 URL 직접 접근 대응)
// [2026-01-27] 데이터 로드 완료 시 라우트에 따른 activeUnit 자동 복구
watch(() => game.chapters, (newChapters) => {
    if (newChapters.length > 0 && route.name === 'PseudoCode' && !game.activeUnit) {
        const pseudoUnit = newChapters.find(c => c.name === 'Pseudo Practice');
        if (pseudoUnit) game.activeUnit = pseudoUnit;
    }
}, { deep: true });

// [2026-01-24] 라우트 설정을 감시하여 Unit 1 모달 강제 제어 (필요 시 URL 직접 접근 대응)
watch(() => route.name, (newName) => {
    // 1. URL이 변경될 때마다 모달 상태를 동기화합니다.
    // [수정일: 2026-01-31] 비활성 라우트 체크 간소화
    if (newName === 'PseudoCode') {
        ui.isPseudoCodeOpen = true; // 관련 라우트 접속 시 상태 활성화
        
        // [2026-01-27] 직접 URL 접근이나 새로고침 시 activeUnit이 상실되는 문제 해결
        if (game.chapters.length > 0 && !game.activeUnit) {
            const pseudoUnit = game.chapters.find(c => c.name === 'Pseudo Practice');
            if (pseudoUnit) game.activeUnit = pseudoUnit;
        }
    } else if (!isPracticePage.value) {
        // 2. 다른 일반 페이지(Landing 드)로 이동 시 모든 실습 모달을 명시적으로 닫습니다.
        ui.isPseudoCodeOpen = false;
    }
}, { immediate: true });

onUpdated(() => {
  nextTick(() => {
    if (window.lucide) window.lucide.createIcons();
  });
});
</script>

<style scoped src="./App.css"></style>
