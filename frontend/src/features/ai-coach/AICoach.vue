<template>
  <div class="coach-container">
    <!-- 사이드바 오버레이 -->
    <div v-if="sidebarOpen" class="sidebar-overlay" @click="sidebarOpen = false"></div>

    <!-- 대화 목록 사이드바 -->
    <aside class="sidebar" :class="{ open: sidebarOpen }">
      <div class="sidebar-header">
        <span class="sidebar-title">대화 목록</span>
        <button class="sidebar-close" @click="sidebarOpen = false">&times;</button>
      </div>
      <button class="sidebar-new-btn" @click="startNewConversation">+ 새 대화</button>
      <div class="sidebar-list">
        <div
          v-for="conv in conversations"
          :key="conv.id"
          class="sidebar-item"
          :class="{ active: conv.id === conversationId }"
          @click="selectConversation(conv.id)"
        >
          <!-- 이름 수정 모드 -->
          <template v-if="editingConvId === conv.id">
            <input
              class="sidebar-edit-input"
              v-model="editingTitle"
              @keyup.enter="confirmRename(conv.id)"
              @keyup.escape="cancelRename"
              @click.stop
              ref="renameInput"
              maxlength="100"
            />
            <div class="sidebar-edit-actions" @click.stop>
              <button class="edit-confirm" @click="confirmRename(conv.id)">&#10003;</button>
              <button class="edit-cancel" @click="cancelRename">&#10005;</button>
            </div>
          </template>
          <!-- 일반 모드 -->
          <template v-else>
            <span class="sidebar-item-title">{{ conv.title || '새 대화' }}</span>
            <span class="sidebar-item-date">{{ formatDate(conv.create_date) }}</span>
            <button class="sidebar-menu-btn" @click.stop="toggleMenu(conv.id)">&#8943;</button>
          </template>
          <!-- 드롭다운 메뉴 -->
          <div v-if="menuOpenId === conv.id" class="sidebar-dropdown" @click.stop>
            <button class="dropdown-item" @click.stop="startRename(conv)">
              <span class="dropdown-icon">&#9998;</span> 이름 수정
            </button>
            <button class="dropdown-item dropdown-danger" @click.stop="deleteConversation(conv.id)">
              <span class="dropdown-icon">&#128465;</span> 삭제
            </button>
          </div>
        </div>
        <div v-if="conversations.length === 0" class="sidebar-empty">
          아직 대화가 없습니다
        </div>
      </div>
    </aside>

    <header class="coach-header">
      <button class="header-icon-btn" @click="sidebarOpen = !sidebarOpen" title="대화 목록">&#9776;</button>
      <button class="header-icon-btn right" @click="$emit('close')" title="닫기">&times;</button>
      <div class="badge">AI COACH</div>
      <h1 class="title">Coduck Coach</h1>
      <p class="subtitle">AI 학습 코치가 당신의 성장을 도와드립니다</p>
    </header>

    <div class="chat-area" ref="chatArea">
      <!-- 프리셋 버튼 (대화 없을 때) -->
      <div v-if="messages.length === 0" class="preset-section">
        <p class="preset-label">무엇을 도와드릴까요?</p>
        <div class="preset-buttons">
          <button class="preset-btn" @click="sendPreset('내 약점을 분석해줘')">
            <span class="preset-icon">&#127919;</span>
            <span>내 약점 분석</span>
          </button>
          <button class="preset-btn" @click="sendPreset('다음에 어떤 문제를 풀면 좋을지 추천해줘')">
            <span class="preset-icon">&#128218;</span>
            <span>다음 학습 추천</span>
          </button>
          <button class="preset-btn" @click="sendPreset('내 전체 학습 현황을 리포트해줘')">
            <span class="preset-icon">&#128202;</span>
            <span>성장 리포트</span>
          </button>
          <button class="preset-btn" @click="sendPreset('유닛별 성적을 보여줘')">
            <span class="preset-icon">&#127942;</span>
            <span>유닛별 성적</span>
          </button>
        </div>
      </div>

      <!-- 채팅 메시지 -->
      <div v-for="(msg, idx) in messages" :key="idx" class="message-block">
        <!-- 의도 분석 결과 배지 (v2) [2026-02-23] -->
        <div v-if="msg.intentData" class="intent-badge">
          <span class="intent-type">{{ msg.intentData.intent_name }}</span>
          <span class="intent-confidence">(신뢰도: {{ (msg.intentData.confidence * 100).toFixed(0) }}%)</span>
          <span class="intent-reasoning">{{ msg.intentData.reasoning }}</span>
        </div>

        <!-- 유저 메시지 -->
        <div v-if="msg.role === 'user'" class="chat-bubble user">
          {{ msg.content }}
        </div>

        <!-- Agent Steps (실시간 스트리밍) -->
        <template v-if="msg.role === 'assistant'">
          <!-- Agent 사고 과정 + Tool 사용 -->
          <template v-for="(item, iIdx) in msg.timeline" :key="'t-' + iIdx">
            <!-- thinking -->
            <div v-if="item.type === 'thinking'" class="thinking-block">
              <span class="thinking-icon">&#129504;</span>
              <span class="thinking-text">{{ item.message }}</span>
              <span v-if="item.active" class="step-spinner"></span>
            </div>
            <!-- tool step -->
            <div v-if="item.type === 'step'" class="step-block">
              <div class="step-header" :class="{ 'no-result': !item.showResult }">
                <span class="step-icon">&#128295;</span>
                <span class="step-label">{{ item.label }}</span>
                <span v-if="Object.keys(item.args || {}).length" class="step-args">
                  ({{ formatArgs(item.args) }})
                </span>
                <span v-if="item.loading" class="step-spinner"></span>
              </div>
              <div v-if="item.showResult" class="step-result">
                <span class="result-icon">&#128202;</span>
                <pre class="result-json">{{ formatResult(item.result) }}</pre>
              </div>
            </div>
          </template>

          <!-- 차트 렌더링 [2026-02-24] 📊 (최종답변 위에 배치) -->
          <div v-if="msg.charts && msg.charts.length > 0" class="charts-section">
            <div v-for="(chart, cIdx) in msg.charts" :key="`chart-${cIdx}`" class="chart-wrapper">
              <div class="chart-header">
                <h4 class="chart-title">{{ chart.title }}</h4>
              </div>

              <!-- Bar / Line / Radar Chart -->
              <template v-if="['bar', 'line', 'radar'].includes(chart.chart_type)">
                <canvas
                  :id="chart._chartId || `chart-${cIdx}-${idx}`"
                  :data-chart-id="chart._chartId"
                  class="chart-canvas"
                  style="max-width: 100%; height: 300px;">
                </canvas>
              </template>

              <!-- Progress Chart -->
              <template v-else-if="chart.chart_type === 'progress'">
                <div class="progress-list">
                  <div v-for="(rate, pIdx) in chart.data.completion_rates" :key="pIdx" class="progress-item">
                    <span class="progress-label">{{ chart.data.units[pIdx] }}</span>
                    <div class="progress-bar">
                      <div class="progress-fill" :style="{ width: `${rate}%` }"></div>
                    </div>
                    <span class="progress-percent">{{ rate.toFixed(1) }}%</span>
                  </div>
                </div>
              </template>

              <!-- Table Chart -->
              <template v-else-if="chart.chart_type === 'table'">
                <div class="table-wrapper">
                  <table class="data-table">
                    <thead>
                      <tr>
                        <th v-for="col in chart.data.columns" :key="col">{{ col }}</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="(row, rIdx) in chart.data.rows" :key="rIdx">
                        <td v-for="(cell, cIdx) in row" :key="cIdx">{{ cell }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </template>
            </div>
          </div>

          <!-- 최종 답변 (스트리밍) -->
          <div v-if="msg.showAnswer" class="chat-bubble assistant" v-html="renderMarkdown(msg.displayedContent || '')">
          </div>
        </template>
      </div>

      <!-- 로딩 (첫 이벤트 도착 전까지만 표시) -->
      <div v-if="loading && !streaming" class="loading-indicator">
        <div class="loading-dots">
          <span></span><span></span><span></span>
        </div>
        <span class="loading-text">코치가 분석 중입니다...</span>
      </div>
    </div>

    <div class="input-area">
      <input
        v-model="inputText"
        class="chat-input"
        placeholder="학습에 대해 물어보세요..."
        @keyup.enter="sendMessage"
        :disabled="loading"
      />
      <button class="send-btn" @click="sendMessage" :disabled="loading || !inputText.trim()">
        전송
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted, onUnmounted } from 'vue';
import Chart from 'chart.js/auto';

const emit = defineEmits(['close']);

const messages = ref([]);
const inputText = ref('');
const loading = ref(false);
const streaming = ref(false);
const chatArea = ref(null);
const conversationId = ref(null);
const historyLoaded = ref(false);
const sidebarOpen = ref(false);
const conversations = ref([]);
const menuOpenId = ref(null);
const editingConvId = ref(null);
const editingTitle = ref('');
const renameInput = ref(null);

function getCsrfToken() {
  const m = document.cookie.match(/csrftoken=([^;]+)/);
  return m ? m[1] : '';
}

// 토큰 디스플레이 큐 — 네트워크 버퍼링과 무관하게 부드러운 출력
let tokenBuffer = '';
let displayPos = 0;
let displayTimer = null;

function startTokenDisplay(msg) {
  if (displayTimer) return;
  displayTimer = setInterval(() => {
    if (displayPos >= tokenBuffer.length) return; // 버퍼 따라잡음 — 대기
    const end = Math.min(displayPos + 3, tokenBuffer.length);
    msg.displayedContent += tokenBuffer.slice(displayPos, end);
    displayPos = end;
    scrollToBottom();
  }, 20);
}

function flushTokenDisplay(msg) {
  if (displayTimer) { clearInterval(displayTimer); displayTimer = null; }
  // 남은 토큰 즉시 표시
  if (displayPos < tokenBuffer.length) {
    msg.displayedContent += tokenBuffer.slice(displayPos);
    displayPos = tokenBuffer.length;
  }
  tokenBuffer = '';
  displayPos = 0;
}

function formatArgs(args) {
  return Object.entries(args).map(([k, v]) => `${k}: ${v}`).join(', ');
}

function formatResult(result) {
  if (!result) return '(데이터 없음)';
  if (result.message) return result.message;

  if (Array.isArray(result)) {
    if (result.length === 0) return '(데이터 없음)';
    if (result.length === 1 && result[0].message) return result[0].message;
    if (result[0].avg_score !== undefined) {
      return result.map(r =>
        `${r.unit_title}: 평균 ${r.avg_score}점, 최고 ${r.max_score}점, ${r.solved_count}/${r.total_problems}문제 (${r.completion_rate}%)`
      ).join('\n');
    }
    if (result[0].solved_date !== undefined) {
      return result.map(r =>
        `${r.problem_title} — ${r.score}점 (${r.solved_date})`
      ).join('\n');
    }
    if (result[0].status !== undefined) {
      return result.map(r =>
        `${r.problem_title} [${r.status}]${r.current_best_score != null ? ` 현재 ${r.current_best_score}점` : ''}`
      ).join('\n');
    }
    return result.map(r => r.message || JSON.stringify(r)).join('\n');
  }

  if (result.weak_areas !== undefined) {
    if (result.weak_areas.length === 0) return `풀이 ${result.total_solved}건 — 약점 없음 (모두 70점 이상)`;
    const weakList = result.weak_areas.map(w => `${w.metric} ${w.avg_score}점`).join(', ');
    return `풀이 ${result.total_solved}건 — 약점: ${weakList}`;
  }

  return String(result);
}

function renderMarkdown(text) {
  if (!text) return '';
  let html = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/^### (.+)$/gm, '<h4>$1</h4>');
  html = html.replace(/^## (.+)$/gm, '<h3>$1</h3>');
  html = html.replace(/^- (.+)$/gm, '<li>$1</li>');
  html = html.replace(/(<li>.*<\/li>\n?)+/g, (m) => `<ul>${m}</ul>`);
  html = html.replace(/\n/g, '<br>');
  return html;
}

function scrollToBottom() {
  nextTick(() => {
    if (chatArea.value) {
      chatArea.value.scrollTop = chatArea.value.scrollHeight;
    }
  });
}

// ── onMounted: 대화 목록 + active 대화 복원 ──
onMounted(async () => {
  try {
    const resp = await fetch('/api/core/ai-coach/conversations/', {
      headers: { 'X-CSRFToken': getCsrfToken() },
    });
    if (!resp.ok) return;
    const data = await resp.json();

    // 대화 목록만 로드 (프리셋 버튼이 보이는 초기 화면 유지)
    conversations.value = data.conversations || [];
  } catch (e) {
    // 히스토리 로드 실패해도 무시 — 새 대화로 시작
  } finally {
    historyLoaded.value = true;
  }

  // 메뉴 바깥 클릭 시 닫기
  document.addEventListener('click', handleGlobalClick);
});

function handleGlobalClick() {
  menuOpenId.value = null;
}

onUnmounted(() => {
  document.removeEventListener('click', handleGlobalClick);
  // 차트 인스턴스 정리 (메모리 릭 방지)
  chartInstances.forEach(c => c.destroy());
  chartInstances.clear();
});

function restoreMessages(msgList) {
  messages.value = [];
  for (const msg of msgList) {
    if (msg.role === 'user') {
      messages.value.push({ role: 'user', content: msg.content });
    } else if (msg.role === 'assistant') {
      messages.value.push({
        role: 'assistant',
        content: msg.content,
        timeline: [],
        showAnswer: true,
        displayedContent: msg.content,
        intentData: null,
        charts: [],
      });
    }
  }
}

async function selectConversation(id) {
  if (loading.value || id === conversationId.value) {
    sidebarOpen.value = false;
    return;
  }
  try {
    const resp = await fetch(`/api/core/ai-coach/conversations/${id}/`, {
      headers: { 'X-CSRFToken': getCsrfToken() },
    });
    if (!resp.ok) return;
    const data = await resp.json();
    conversationId.value = data.conversation.id;
    // 차트 정리
    chartInstances.forEach(c => c.destroy());
    chartInstances.clear();
    // 메시지 복원
    restoreMessages(data.conversation.messages);
    scrollToBottom();
  } catch (e) { /* ignore */ }
  sidebarOpen.value = false;
}

function formatDate(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  const now = new Date();
  const diffMs = now - d;
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return '방금';
  if (diffMin < 60) return `${diffMin}분 전`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}시간 전`;
  const diffDay = Math.floor(diffHr / 24);
  if (diffDay < 7) return `${diffDay}일 전`;
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

async function startNewConversation() {
  if (loading.value) return;
  try {
    await fetch('/api/core/ai-coach/conversations/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken(),
      },
    });
    // 대화 목록 갱신 (기존 active → closed 반영)
    await refreshConversationList();
  } catch (e) { /* ignore */ }
  conversationId.value = null;
  messages.value = [];
  // 기존 차트 인스턴스 정리
  chartInstances.forEach(c => c.destroy());
  chartInstances.clear();
  sidebarOpen.value = false;
}

async function refreshConversationList() {
  try {
    const resp = await fetch('/api/core/ai-coach/conversations/', {
      headers: { 'X-CSRFToken': getCsrfToken() },
    });
    if (!resp.ok) return;
    const data = await resp.json();
    conversations.value = data.conversations || [];
  } catch (e) { /* ignore */ }
}

function toggleMenu(convId) {
  menuOpenId.value = menuOpenId.value === convId ? null : convId;
}

function closeMenu() {
  menuOpenId.value = null;
}

function startRename(conv) {
  menuOpenId.value = null;
  editingConvId.value = conv.id;
  editingTitle.value = conv.title || '';
  nextTick(() => {
    const input = document.querySelector('.sidebar-edit-input');
    if (input) { input.focus(); input.select(); }
  });
}

function cancelRename() {
  editingConvId.value = null;
  editingTitle.value = '';
}

async function confirmRename(convId) {
  const title = editingTitle.value.trim();
  if (!title) { cancelRename(); return; }
  try {
    const resp = await fetch(`/api/core/ai-coach/conversations/${convId}/`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken(),
      },
      body: JSON.stringify({ title }),
    });
    if (resp.ok) {
      const conv = conversations.value.find(c => c.id === convId);
      if (conv) conv.title = title;
    }
  } catch (e) { /* ignore */ }
  cancelRename();
}

async function deleteConversation(convId) {
  menuOpenId.value = null;
  try {
    const resp = await fetch(`/api/core/ai-coach/conversations/${convId}/`, {
      method: 'DELETE',
      headers: { 'X-CSRFToken': getCsrfToken() },
    });
    if (resp.ok) {
      conversations.value = conversations.value.filter(c => c.id !== convId);
      // 현재 보고 있던 대화가 삭제된 경우 → 초기화
      if (conversationId.value === convId) {
        conversationId.value = null;
        messages.value = [];
        chartInstances.forEach(c => c.destroy());
        chartInstances.clear();
      }
    }
  } catch (e) { /* ignore */ }
}

function sendPreset(text) {
  inputText.value = text;
  sendMessage();
}

async function sendMessage() {
  const text = inputText.value.trim();
  if (!text || loading.value) return;

  messages.value.push({ role: 'user', content: text });
  inputText.value = '';
  loading.value = true;
  streaming.value = false;
  scrollToBottom();

  messages.value.push({
    role: 'assistant',
    content: '',
    timeline: [],
    showAnswer: false,
    displayedContent: '',
    intentData: null, // [2026-02-23] 의도 분석 데이터
    charts: [], // [2026-02-24] 차트 데이터
  });
  const assistantMsg = messages.value[messages.value.length - 1];

  try {
    // AI Coach 엔드포인트
    const endpoint = '/api/core/ai-coach/chat/';

    const response = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken(),
      },
      body: JSON.stringify({ message: text, conversation_id: conversationId.value }),
    });

    if (!response.ok || !response.body) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(errData.error || `HTTP ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';
    let done = false;

    while (!done) {
      const chunk = await reader.read();
      if (chunk.done) break;
      buffer += decoder.decode(chunk.value, { stream: true });

      let boundary = buffer.indexOf('\n\n');
      while (boundary !== -1) {
        const eventChunk = buffer.slice(0, boundary).trim();
        buffer = buffer.slice(boundary + 2);

        if (eventChunk.startsWith('data:')) {
          const payload = eventChunk
            .split('\n')
            .filter(l => l.startsWith('data:'))
            .map(l => l.slice(5).trim())
            .join('');

          if (payload === '[DONE]') {
            done = true;
            break;
          }

          try {
            const data = JSON.parse(payload);
            streaming.value = true;

            // [2026-03-01] Conversation ID
            if (data.type === 'conversation_id') {
              conversationId.value = data.conversation_id;
              refreshConversationList();
            }
            // [2026-02-24] Intent Detected (v2, v3)
            else if (data.type === 'intent_detected') {
              assistantMsg.intentData = {
                intent_name: data.intent_name,
                confidence: data.confidence,
                reasoning: data.reasoning,
              };
              scrollToBottom();
            }
            // [2026-02-24] Chart Data 📊 (동적 차트 표시)
            else if (data.type === 'chart_data') {
              // 각 차트에 unique ID 추가
              const chartWithId = {
                ...data.chart,
                _chartId: `chart-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
              };
              assistantMsg.charts.push(chartWithId);

              // DOM 렌더링 후 차트 렌더링
              nextTick(() => {
                setTimeout(() => {
                  renderChartByDataId(chartWithId);
                }, 150);
              });
              scrollToBottom();
            }
            else if (data.type === 'thinking') {
              // 이전 thinking 비활성화
              const prevThinking = [...assistantMsg.timeline].reverse().find(i => i.type === 'thinking');
              if (prevThinking) prevThinking.active = false;
              // 새 thinking 추가
              assistantMsg.timeline.push({
                type: 'thinking',
                message: data.message,
                active: true,
              });
              scrollToBottom();
            }
            else if (data.type === 'step_start') {
              // thinking 비활성화
              const curThinking = [...assistantMsg.timeline].reverse().find(i => i.type === 'thinking');
              if (curThinking) curThinking.active = false;
              // step 추가
              assistantMsg.timeline.push({
                type: 'step',
                tool: data.tool,
                label: data.label,
                args: data.args || {},
                result: null,
                showResult: false,
                loading: true,
              });
              scrollToBottom();
            }
            else if (data.type === 'step_result') {
              const lastStep = [...assistantMsg.timeline].reverse().find(i => i.type === 'step');
              if (lastStep) {
                lastStep.result = data.result;
                lastStep.showResult = true;
                lastStep.loading = false;
              }
              scrollToBottom();
            }
            else if (data.type === 'token') {
              if (!assistantMsg.showAnswer) {
                // thinking 비활성화 + 답변 생성 대기 해제
                const curThinking = [...assistantMsg.timeline].reverse().find(i => i.type === 'thinking');
                if (curThinking) curThinking.active = false;
                assistantMsg.showAnswer = true;
              }
              assistantMsg.content += data.token;
              tokenBuffer += data.token;
              startTokenDisplay(assistantMsg);
            }
            else if (data.type === 'error') {
              assistantMsg.content = data.message;
              assistantMsg.displayedContent = data.message;
              assistantMsg.showAnswer = true;
              scrollToBottom();
            }
          } catch (e) { /* JSON parse error — skip */ }
        }

        boundary = buffer.indexOf('\n\n');
      }
    }

    // 스트림 종료 — 남은 토큰을 부드럽게 마저 출력
    await new Promise(resolve => {
      const check = setInterval(() => {
        if (displayPos >= tokenBuffer.length) {
          clearInterval(check);
          flushTokenDisplay(assistantMsg);
          resolve();
        }
      }, 50);
    });

  } catch (err) {
    const errorMsg = err.message || '오류가 발생했습니다. 다시 시도해주세요.';
    flushTokenDisplay(assistantMsg);
    if (!assistantMsg.displayedContent) {
      assistantMsg.content = errorMsg;
      assistantMsg.displayedContent = errorMsg;
      assistantMsg.showAnswer = true;
    }
    scrollToBottom();
  } finally {
    loading.value = false;
    streaming.value = false;
  }
}

// ── Chart Rendering Functions [2026-02-24] ──
const chartInstances = new Map(); // 차트 인스턴스 관리

function renderChartByDataId(chartData) {
  if (!chartData || !chartData._chartId || !chartData.chart_type) return;

  const chartId = chartData._chartId;

  // 여러 번 시도해서 canvas 찾기 (DOM 렌더링 대기)
  let attempts = 0;
  const tryRender = () => {
    const canvas = document.getElementById(chartId);

    if (!canvas) {
      attempts++;
      if (attempts < 10) {
        // 최대 1000ms까지 대기
        setTimeout(tryRender, 100);
      } else {
        console.error(`❌ Canvas not found after retries: ${chartId}`);
      }
      return;
    }

    // 기존 차트 인스턴스 제거
    const existingChart = chartInstances.get(chartId);
    if (existingChart) existingChart.destroy();

    try {
      const ctx = canvas.getContext('2d');
      const config = buildChartConfig(chartData);

      if (config) {
        const chartInstance = new Chart(ctx, config);
        chartInstances.set(chartId, chartInstance);
        console.log(`✅ Chart rendered successfully: ${chartData.chart_type}`, chartData.title);
      }
    } catch (err) {
      console.error(`❌ Error rendering chart ${chartId}:`, err);
    }
  };

  tryRender();
}

function buildChartConfig(chartData) {
  const { chart_type, data } = chartData;

  switch (chart_type) {
    case 'bar':
      return {
        type: 'bar',
        data: {
          labels: data.labels,
          datasets: data.datasets,
        },
        options: {
          responsive: true,
          maintainAspectRatio: true,
          plugins: {
            legend: { display: true },
          },
          scales: {
            y: { max: 100, beginAtZero: true },
          },
        },
      };

    case 'line':
      return {
        type: 'line',
        data: {
          labels: data.labels,
          datasets: data.datasets,
        },
        options: {
          responsive: true,
          maintainAspectRatio: true,
          plugins: { legend: { display: true } },
          scales: { y: { max: 100, beginAtZero: true } },
        },
      };

    case 'radar':
      return {
        type: 'radar',
        data: {
          labels: data.labels,
          datasets: data.datasets,
        },
        options: {
          responsive: true,
          maintainAspectRatio: true,
          scales: { r: { max: 100, beginAtZero: true } },
        },
      };

    default:
      return null;
  }
}
</script>

<style scoped>
.coach-container {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background: var(--dark);
  display: flex;
  flex-direction: column;
  color: var(--text);
  font-family: 'Outfit', sans-serif;
  z-index: 1000;
}

/* ===== Sidebar ===== */
.sidebar-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 1100;
}

.sidebar {
  position: fixed;
  top: 0;
  left: 0;
  width: 280px;
  height: 100vh;
  background: var(--dark);
  border-right: 1px solid var(--glass-border);
  z-index: 1200;
  display: flex;
  flex-direction: column;
  transform: translateX(-100%);
  transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}
.sidebar.open {
  transform: translateX(0);
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--glass-border);
  flex-shrink: 0;
}

.sidebar-title {
  font-weight: 700;
  font-size: 1rem;
  color: #f8fafc;
}

.sidebar-close {
  background: none;
  border: none;
  color: #64748b;
  font-size: 1.5rem;
  cursor: pointer;
  line-height: 1;
  padding: 0;
}
.sidebar-close:hover {
  color: #f8fafc;
}

.sidebar-new-btn {
  margin: 0.75rem 1rem;
  padding: 0.6rem 1rem;
  background: var(--glass);
  border: 1px dashed var(--glass-border);
  border-radius: 8px;
  color: var(--text-muted);
  font-size: 0.85rem;
  font-weight: 600;
  font-family: 'Outfit', sans-serif;
  cursor: pointer;
  transition: all 0.2s;
  flex-shrink: 0;
}
.sidebar-new-btn:hover {
  background: rgba(99, 102, 241, 0.1);
  border-color: var(--primary);
  color: #f8fafc;
}

.sidebar-list {
  flex: 1;
  overflow-y: auto;
  padding: 0.25rem 0.75rem;
}
.sidebar-list::-webkit-scrollbar {
  width: 4px;
}
.sidebar-list::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 2px;
}

.sidebar-item {
  padding: 0.65rem 0.75rem;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;
  margin-bottom: 2px;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}
.sidebar-item:hover {
  background: rgba(255, 255, 255, 0.05);
}
.sidebar-item.active {
  background: rgba(99, 102, 241, 0.15);
  border-left: 3px solid var(--primary);
}

.sidebar-item-title {
  font-size: 0.85rem;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-weight: 500;
}

.sidebar-item-date {
  font-size: 0.7rem;
  color: var(--text-muted);
}

.sidebar-empty {
  padding: 2rem 1rem;
  text-align: center;
  font-size: 0.85rem;
  color: var(--text-muted);
}

/* ===== Sidebar Item Menu ===== */
.sidebar-item {
  position: relative;
}

.sidebar-menu-btn {
  position: absolute;
  right: 6px;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  color: transparent;
  font-size: 1.1rem;
  width: 26px;
  height: 26px;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
  line-height: 1;
}
.sidebar-item:hover .sidebar-menu-btn {
  color: var(--text-muted);
}
.sidebar-menu-btn:hover {
  background: rgba(255, 255, 255, 0.1);
  color: #f8fafc !important;
}

.sidebar-dropdown {
  position: absolute;
  right: 6px;
  top: 100%;
  background: var(--dark-light);
  border: 1px solid var(--glass-border);
  border-radius: 8px;
  padding: 4px;
  z-index: 10;
  min-width: 120px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
}

.dropdown-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  width: 100%;
  padding: 0.5rem 0.75rem;
  background: none;
  border: none;
  color: var(--text);
  font-size: 0.8rem;
  font-family: 'Outfit', sans-serif;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s;
}
.dropdown-item:hover {
  background: rgba(255, 255, 255, 0.08);
}
.dropdown-item.dropdown-danger:hover {
  background: rgba(239, 68, 68, 0.15);
  color: #f87171;
}

.dropdown-icon {
  font-size: 0.85rem;
  width: 18px;
  text-align: center;
}

/* ===== Inline Rename ===== */
.sidebar-edit-input {
  width: 100%;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid var(--primary);
  border-radius: 6px;
  padding: 0.35rem 0.5rem;
  color: #f8fafc;
  font-size: 0.85rem;
  font-family: 'Outfit', sans-serif;
  outline: none;
}

.sidebar-edit-actions {
  display: flex;
  gap: 4px;
  margin-top: 4px;
}

.edit-confirm,
.edit-cancel {
  background: none;
  border: 1px solid var(--glass-border);
  border-radius: 4px;
  padding: 2px 8px;
  font-size: 0.75rem;
  cursor: pointer;
  transition: all 0.15s;
}
.edit-confirm {
  color: #4ade80;
}
.edit-confirm:hover {
  background: rgba(74, 222, 128, 0.15);
  border-color: #4ade80;
}
.edit-cancel {
  color: var(--text-muted);
}
.edit-cancel:hover {
  background: rgba(255, 255, 255, 0.08);
}

/* ===== Header (MyRecordsView 패턴) ===== */
.coach-header {
  text-align: center;
  padding: 2rem 2rem 1.5rem;
  position: relative;
  flex-shrink: 0;
}

.header-icon-btn {
  position: absolute;
  top: 1rem;
  left: 1.5rem;
  background: var(--glass);
  border: 1px solid var(--glass-border);
  color: var(--text-muted);
  font-size: 1.2rem;
  width: 36px;
  height: 36px;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  line-height: 1;
}
.header-icon-btn:hover {
  background: rgba(99, 102, 241, 0.15);
  border-color: var(--primary);
  color: #f8fafc;
}
.header-icon-btn.right {
  left: auto;
  right: 1.5rem;
}

.badge {
  background: var(--primary);
  color: #fff;
  display: inline-block;
  padding: 4px 12px;
  border-radius: 4px;
  font-weight: 800;
  font-size: 0.75rem;
  margin-bottom: 0.5rem;
  letter-spacing: 1px;
}

.title {
  font-size: 2.5rem;
  font-weight: 900;
  color: #f8fafc;
  margin: 0;
}

.subtitle {
  color: var(--text-muted);
  font-size: 1.1rem;
  margin: 0;
}

/* ===== Chat Area ===== */
.chat-area {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem 2rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.chat-area::-webkit-scrollbar {
  width: 6px;
}
.chat-area::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 3px;
}
.chat-area::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.2);
}

/* ===== Preset Buttons ===== */
.preset-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  gap: 1.5rem;
}

.preset-label {
  font-size: 1.1rem;
  color: var(--text-muted);
  margin: 0;
  font-weight: 500;
}

.preset-buttons {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
  max-width: 480px;
  width: 100%;
}

.preset-btn {
  background: var(--glass);
  border: 1px solid var(--glass-border);
  color: var(--text);
  padding: 1rem 1.25rem;
  border-radius: 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-size: 0.95rem;
  font-weight: 600;
  font-family: 'Outfit', sans-serif;
  transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}
.preset-btn:hover {
  background: rgba(99, 102, 241, 0.1);
  border-color: var(--primary);
  transform: translateY(-3px);
  box-shadow: 0 8px 25px rgba(99, 102, 241, 0.15);
}

.preset-icon {
  font-size: 1.25rem;
}

/* ===== Chat Bubbles (style.css 패턴) ===== */
.message-block {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.chat-bubble {
  max-width: 85%;
  padding: 0.8rem 1.2rem;
  border-radius: 12px;
  font-size: 0.95rem;
  line-height: 1.6;
  word-break: break-word;
}

.chat-bubble.user {
  align-self: flex-end;
  background: var(--primary);
  color: white;
  border-bottom-right-radius: 2px;
  box-shadow: 0 4px 15px rgba(99, 102, 241, 0.3);
}

.chat-bubble.assistant {
  align-self: flex-start;
  background: rgba(255, 255, 255, 0.05);
  color: var(--text);
  border-bottom-left-radius: 2px;
  border: 1px solid var(--glass-border);
}

.chat-bubble.assistant :deep(h3),
.chat-bubble.assistant :deep(h4) {
  color: var(--secondary);
  margin: 0.5rem 0 0.25rem;
  font-family: 'Outfit', sans-serif;
}
.chat-bubble.assistant :deep(strong) {
  color: #fff;
}
.chat-bubble.assistant :deep(ul) {
  padding-left: 1.25rem;
  margin: 0.25rem 0;
}
.chat-bubble.assistant :deep(li) {
  margin: 0.15rem 0;
}

/* ===== Agent Thinking ===== */
.thinking-block {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  align-self: flex-start;
  padding: 0.45rem 0.85rem;
  background: rgba(255, 255, 255, 0.03);
  border-left: 3px solid rgba(99, 102, 241, 0.4);
  border-radius: 0 8px 8px 0;
  animation: stepSlideIn 0.35s cubic-bezier(0.16, 1, 0.3, 1);
}

.thinking-icon {
  font-size: 0.9rem;
}

.thinking-text {
  font-size: 0.8rem;
  color: var(--text-muted);
  font-style: italic;
}

/* ===== Agent Steps ===== */
.step-block {
  align-self: flex-start;
  max-width: 85%;
  animation: stepSlideIn 0.35s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes stepSlideIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.step-header {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.5rem 0.75rem;
  background: rgba(99, 102, 241, 0.08);
  border: 1px solid rgba(99, 102, 241, 0.2);
  border-radius: 8px 8px 0 0;
  font-size: 0.8rem;
  color: var(--primary);
}
.step-header.no-result {
  border-radius: 8px;
}

.step-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(99, 102, 241, 0.3);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin-left: auto;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.step-icon {
  font-size: 0.85rem;
}

.step-label {
  font-weight: 700;
  letter-spacing: 0.3px;
}

.step-args {
  color: var(--text-muted);
  font-size: 0.75rem;
}

.step-result {
  display: flex;
  gap: 0.4rem;
  padding: 0.5rem 0.75rem;
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid var(--glass-border);
  border-top: none;
  border-radius: 0 0 8px 8px;
  font-size: 0.75rem;
  animation: resultExpand 0.3s ease-out;
}

@keyframes resultExpand {
  from {
    opacity: 0;
    max-height: 0;
  }
  to {
    opacity: 1;
    max-height: 500px;
  }
}

.result-icon {
  font-size: 0.8rem;
  flex-shrink: 0;
  margin-top: 1px;
}

.result-json {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--text-muted);
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 0.7rem;
  max-height: 200px;
  overflow-y: auto;
}

/* ===== Loading ===== */
.loading-indicator {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  align-self: flex-start;
  padding: 0.6rem 1rem;
  background: var(--glass);
  border: 1px solid var(--glass-border);
  border-radius: 12px;
}

.loading-dots {
  display: flex;
  gap: 4px;
}
.loading-dots span {
  width: 6px;
  height: 6px;
  background: var(--primary);
  border-radius: 50%;
  animation: dotPulse 1.2s infinite;
}
.loading-dots span:nth-child(2) { animation-delay: 0.2s; }
.loading-dots span:nth-child(3) { animation-delay: 0.4s; }

@keyframes dotPulse {
  0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
  40% { opacity: 1; transform: scale(1.2); }
}

.loading-text {
  font-size: 0.8rem;
  color: var(--text-muted);
}

/* ===== Input Area (style.css chat-input-wrapper 패턴) ===== */
.input-area {
  display: flex;
  gap: 0.75rem;
  padding: 1rem 2rem;
  background: rgba(0, 0, 0, 0.2);
  border-top: 1px solid var(--glass-border);
  flex-shrink: 0;
}

.chat-input {
  flex: 1;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--glass-border);
  border-radius: 8px;
  padding: 0.75rem 1rem;
  color: white;
  font-size: 0.9rem;
  font-family: 'Outfit', sans-serif;
  outline: none;
  transition: border-color 0.3s;
}
.chat-input:focus {
  border-color: var(--primary);
}
.chat-input::placeholder {
  color: var(--text-muted);
}
.chat-input:disabled {
  opacity: 0.5;
}

.send-btn {
  background: var(--primary);
  color: #fff;
  border: none;
  padding: 0.75rem 1.5rem;
  border-radius: 8px;
  font-size: 0.9rem;
  font-weight: 700;
  font-family: 'Outfit', sans-serif;
  cursor: pointer;
  transition: all 0.3s;
  white-space: nowrap;
}
.send-btn:hover:not(:disabled) {
  background: var(--primary-hover);
  transform: translateY(-1px);
  box-shadow: 0 4px 15px rgba(99, 102, 241, 0.4);
}
.send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ===== Intent Badge [2026-02-23] ===== */
.intent-badge {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding: 0.75rem 1rem;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.15), rgba(139, 92, 246, 0.1));
  border-left: 3px solid var(--primary);
  border-radius: 8px;
  align-self: flex-start;
  max-width: 85%;
  animation: intentSlideIn 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes intentSlideIn {
  from {
    opacity: 0;
    transform: translateX(-20px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.intent-type {
  font-weight: 700;
  color: var(--primary);
  font-size: 0.9rem;
}

.intent-confidence {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.intent-reasoning {
  font-size: 0.85rem;
  color: var(--text);
  font-style: italic;
}

/* ===== Charts [2026-02-24] ===== */
.charts-section {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  align-self: flex-start;
  max-width: 600px;
  width: 100%;
}

.chart-wrapper {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--glass-border);
  border-radius: 12px;
  padding: 1rem;
  animation: chartSlideIn 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes chartSlideIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.chart-header {
  margin-bottom: 1rem;
}

.chart-title {
  font-size: 0.95rem;
  font-weight: 700;
  color: var(--secondary);
  margin: 0;
}

.chart-canvas {
  max-width: 100%;
  height: auto;
}

/* Progress Bar */
.progress-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.progress-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.progress-label {
  min-width: 80px;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text);
}

.progress-bar {
  flex: 1;
  height: 6px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 3px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--primary), var(--secondary));
  transition: width 0.3s ease;
}

.progress-percent {
  min-width: 45px;
  text-align: right;
  font-size: 0.8rem;
  color: var(--text-muted);
}

/* Table */
.table-wrapper {
  overflow-x: auto;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}

.data-table th {
  background: rgba(99, 102, 241, 0.1);
  padding: 0.5rem 0.75rem;
  text-align: left;
  font-weight: 600;
  color: var(--primary);
  border-bottom: 1px solid rgba(99, 102, 241, 0.2);
}

.data-table td {
  padding: 0.5rem 0.75rem;
  color: var(--text);
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.data-table tbody tr:hover {
  background: rgba(255, 255, 255, 0.03);
}
</style>
