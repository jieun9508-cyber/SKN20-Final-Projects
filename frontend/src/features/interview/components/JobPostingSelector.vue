<template>
  <div class="job-posting-selector">
    <div class="selector-header">
      <h2 class="selector-title">모의면접 시작</h2>
      <p class="selector-desc">채용공고를 선택하거나 파싱하여 맞춤 면접을 시작하세요.</p>
    </div>

    <div v-if="errorMessage" class="error-banner">{{ errorMessage }}</div>

    <div v-if="isLoading" class="loading-spinner">채용공고 불러오는 중...</div>

    <template v-else>
      <div class="two-col-layout">

        <!-- 왼쪽: 저장된 공고 목록 -->
        <div class="panel panel--left">
          <h3 class="panel-title">저장된 공고</h3>
          <div class="posting-list">

            <!-- 공고 없이 시작 -->
            <div
              class="posting-card posting-card--empty"
              :class="{ 'posting-card--selected': selectedId === null && !jobData }"
              @click="selectNone"
            >
              <div class="posting-card__info">
                <div class="posting-card__company">공고 없이 시작</div>
                <div class="posting-card__position">기본 면접 질문으로 진행합니다</div>
              </div>
            </div>

            <div
              v-for="posting in postings"
              :key="posting.id"
              class="posting-card"
              :class="{ 'posting-card--selected': selectedId === posting.id && !jobData }"
              @click="selectPosting(posting.id)"
            >
              <div class="posting-card__info">
                <div class="posting-card__company">{{ posting.company_name }}</div>
                <div class="posting-card__position">{{ posting.position }}</div>
                <div class="posting-card__meta">
                  <span v-if="posting.experience_range">{{ posting.experience_range }}</span>
                  <span v-if="posting.deadline">마감: {{ posting.deadline }}</span>
                </div>
              </div>
              <button class="btn-delete-posting" @click.stop="removePosting(posting.id)" title="삭제">✕</button>
            </div>

            <p v-if="!postings.length" class="empty-hint">
              저장된 채용공고가 없습니다.<br>
              오른쪽에서 공고를 파싱해보세요.
            </p>
          </div>
        </div>

        <!-- 오른쪽: 공고 파싱 -->
        <div class="panel panel--right">
          <div class="panel-header">
            <h3 class="panel-title" style="margin: 0;">공고 파싱</h3>
            <button class="btn-history-inline" @click="$emit('showHistory')">📋 면접 기록</button>
          </div>

          <!-- Step 1: URL 입력 (항상 표시) -->
          <div class="input-panel">
            <label class="input-label">채용공고 URL</label>
            <input
              v-model="urlInput"
              type="text"
              placeholder="https://www.jobkorea.co.kr/..."
              class="url-input"
            />
            <p class="input-hint">잡코리아, 사람인, 원티드 등의 채용공고 URL을 입력하세요</p>
            <button class="btn-parse" @click="parseUrl" :disabled="!urlInput || isParsing">
              {{ isParsing && !urlParsed ? '분석 중...' : '공고 분석' }}
            </button>
          </div>

          <!-- 파싱 결과 미리보기 -->
          <div v-if="jobData" class="job-preview">
            <div class="job-preview-header">
              <h4>파싱 완료</h4>
              <button class="btn-reset-parse" @click="resetParsing" title="새 공고 입력">↺ 초기화</button>
            </div>
            <div class="preview-grid">
              <div class="preview-item">
                <span class="preview-label">회사</span>
                <span class="preview-value">{{ jobData.company_name }}</span>
              </div>
              <div class="preview-item">
                <span class="preview-label">포지션</span>
                <span class="preview-value">{{ jobData.position }}</span>
              </div>
              <div class="preview-item">
                <span class="preview-label">경력</span>
                <span class="preview-value">{{ jobData.experience_range || '-' }}</span>
              </div>
            </div>
            <div v-if="jobData.required_skills?.length" class="preview-skills">
              <span class="preview-label">기술스택</span>
              <div class="skill-tags">
                <span v-for="skill in jobData.required_skills.slice(0, 8)" :key="skill" class="skill-tag">{{ skill }}</span>
              </div>
            </div>
          </div>

          <!-- 정보 충분도 표시 -->
          <div v-if="dataCompleteness" class="completeness-bar-wrap">
            <div class="completeness-bar-header">
              <span>{{ dataCompleteness.level === 'good' ? '✅' : dataCompleteness.level === 'fair' ? '⚠️' : '❌' }} 정보 충분도</span>
              <span>{{ Math.round(dataCompleteness.rate * 100) }}%</span>
            </div>
            <div class="completeness-bar-bg">
              <div
                class="completeness-bar-fill"
                :class="dataCompleteness.level"
                :style="{ width: (dataCompleteness.rate * 100) + '%' }"
              ></div>
            </div>
            <p v-if="dataCompleteness.missing?.length" class="completeness-missing">
              부족: {{ dataCompleteness.missing.join(', ') }}
            </p>
          </div>

          <!-- Step 2: URL 분석 후 정보 불충분 시 보완 입력 -->
          <template v-if="urlParsed && isInsufficient">
            <p class="supplement-hint">정보가 충분하지 않습니다. 이미지 또는 텍스트로 보완하세요.</p>

            <div class="input-method-tabs">
              <button :class="['method-tab', { active: supplementMethod === 'image' }]" @click="supplementMethod = 'image'">이미지</button>
              <button :class="['method-tab', { active: supplementMethod === 'text' }]" @click="supplementMethod = 'text'">텍스트</button>
            </div>

            <!-- 이미지 보완 -->
            <div v-if="supplementMethod === 'image'" class="input-panel">
              <label class="input-label">채용공고 이미지 (여러 장 가능)</label>
              <div class="image-upload-area" @click="$refs.imageInput.click()">
                <input
                  ref="imageInput"
                  type="file"
                  accept="image/*"
                  multiple
                  @change="handleImageUpload"
                  style="display: none"
                />
                <div v-if="imageFiles.length === 0" class="upload-placeholder">
                  <p>클릭하여 이미지 업로드</p>
                  <p class="upload-hint">PNG, JPG, JPEG 지원 · 여러 장 선택 가능</p>
                </div>
                <div v-else class="image-previews-grid">
                  <div v-for="(preview, index) in imagePreviews" :key="index" class="image-preview-item">
                    <img :src="preview" alt="미리보기" />
                    <button class="btn-remove-image" @click.stop="removeImage(index)">&times;</button>
                  </div>
                </div>
              </div>
              <button class="btn-parse" @click="parseSupplement" :disabled="imageFiles.length === 0 || isParsing">
                <span v-if="!isParsing">정보 보완 (Vision AI) {{ imageFiles.length > 0 ? `(${imageFiles.length}장)` : '' }}</span>
                <span v-else>AI 분석 중... ({{ currentParsingIndex + 1 }}/{{ imageFiles.length }})</span>
              </button>
            </div>

            <!-- 텍스트 보완 -->
            <div v-if="supplementMethod === 'text'" class="input-panel">
              <label class="input-label">채용공고 텍스트</label>
              <textarea
                v-model="textInput"
                rows="6"
                placeholder="채용공고 내용을 붙여넣으세요...

예시:
[회사명] 테크 스타트업
[포지션] 백엔드 개발자
[필수 스킬] Python, Django, PostgreSQL
[우대 스킬] Docker, Kubernetes
[경력] 2-4년
..."
                class="text-input"
              ></textarea>
              <button class="btn-parse" @click="parseSupplement" :disabled="!textInput || isParsing">
                {{ isParsing ? '분석 중...' : '정보 보완' }}
              </button>
            </div>
          </template>
        </div>

      </div>
    </template>

    <!-- 면접관 선택 -->
    <div class="avatar-select">
      <button
        class="avatar-btn"
        :class="{ 'avatar-btn--active': avatarType === 'woman' }"
        @click="avatarType = 'woman'"
      >여성 면접관</button>
      <button
        class="avatar-btn"
        :class="{ 'avatar-btn--active': avatarType === 'man' }"
        @click="avatarType = 'man'"
      >남성 면접관</button>
    </div>

    <!-- 시작 버튼 -->
    <button
      class="start-btn"
      :disabled="isStarting || isLoading || isParsing"
      @click="onStart"
    >
      {{ isStarting ? '면접 준비 중...' : '면접 시작' }}
    </button>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import axios from 'axios';
import { getJobPostings, createJobPosting, deleteJobPosting } from '../api/interviewApi';

const emit = defineEmits(['start', 'showHistory']);
const avatarType = ref('woman');

// ── 공통 상태 ──────────────────────────────────────────────
const postings = ref([]);
const selectedId = ref(null);   // null = 공고 없이 시작
const isLoading = ref(true);
const isStarting = ref(false);
const errorMessage = ref('');

// ── 파싱 상태 ──────────────────────────────────────────────
const urlInput = ref('');
const urlParsed = ref(false);       // URL 분석 시도 여부
const supplementMethod = ref('image'); // 보완 입력 방식
const imageFiles = ref([]);
const imagePreviews = ref([]);
const textInput = ref('');
const isParsing = ref(false);
const currentParsingIndex = ref(0);
const jobData = ref(null);

// 잡 플래너와 동일한 7점 척도 정보 충분도 체크
const dataCompleteness = ref(null);

function checkDataCompleteness() {
  if (!jobData.value) { dataCompleteness.value = null; return; }
  const d = jobData.value;
  let score = 0;
  const missing = [];

  if (d.company_name && d.company_name !== '알 수 없음' && d.company_name.trim()) score += 1;
  else missing.push('회사명');

  if (d.position && d.position !== '개발자' && d.position.trim()) score += 1;
  else missing.push('포지션');

  if (d.required_skills?.length > 0) score += 2;
  else missing.push('필수 스킬');

  if (d.job_responsibilities?.length > 20) score += 1;
  else missing.push('주요 업무');

  if (d.required_qualifications && d.required_qualifications !== '정보 없음' && d.required_qualifications.length > 10) score += 1;
  else missing.push('필수 요건');

  if (d.preferred_qualifications && d.preferred_qualifications !== '정보 없음' && d.preferred_qualifications.length > 10) score += 1;

  const rate = score / 7;
  const level = rate >= 0.7 ? 'good' : rate >= 0.4 ? 'fair' : 'poor';
  dataCompleteness.value = { score, rate, level, missing };
}

const isInsufficient = computed(() => {
  if (!dataCompleteness.value) return true;
  return dataCompleteness.value.level !== 'good';
});

// 잡 플래너와 동일한 스마트 병합
function mergeJobData(newData) {
  const isValid = (v) => v && v !== '알 수 없음' && v !== '개발자' && v !== '정보 없음' && String(v).trim();
  const mergeText = (a, b) => {
    if (!a || a === '정보 없음') return b || '';
    if (!b || b === '정보 없음') return a;
    if (a.includes(b)) return a;
    if (b.includes(a)) return b;
    return `${a}\n\n${b}`;
  };

  if (jobData.value) {
    jobData.value = {
      ...jobData.value,
      company_name: isValid(newData.company_name) ? newData.company_name : jobData.value.company_name,
      position: isValid(newData.position) ? newData.position : jobData.value.position,
      required_skills: [...new Set([...(jobData.value.required_skills || []), ...(newData.required_skills || [])])],
      preferred_skills: [...new Set([...(jobData.value.preferred_skills || []), ...(newData.preferred_skills || [])])],
      job_responsibilities: mergeText(jobData.value.job_responsibilities, newData.job_responsibilities),
      required_qualifications: mergeText(jobData.value.required_qualifications, newData.required_qualifications),
      preferred_qualifications: mergeText(jobData.value.preferred_qualifications, newData.preferred_qualifications),
      experience_range: isValid(newData.experience_range) ? newData.experience_range : jobData.value.experience_range,
      deadline: newData.deadline || jobData.value.deadline,
    };
  } else {
    jobData.value = newData;
  }
  checkDataCompleteness();
}

// ── 초기 로드 ──────────────────────────────────────────────
onMounted(async () => {
  try {
    postings.value = await getJobPostings();
  } catch {
    // 조용히 실패
  } finally {
    isLoading.value = false;
  }
});

// ── 왼쪽 패널 선택 ─────────────────────────────────────────
function selectNone() {
  selectedId.value = null;
  jobData.value = null;
}

function selectPosting(id) {
  selectedId.value = id;
  jobData.value = null;
}

// ── 이미지 처리 ────────────────────────────────────────────
function handleImageUpload(event) {
  const files = Array.from(event.target.files);
  imageFiles.value = [...imageFiles.value, ...files];
  files.forEach(file => {
    const reader = new FileReader();
    reader.onload = (e) => imagePreviews.value.push(e.target.result);
    reader.readAsDataURL(file);
  });
}

function removeImage(index) {
  imageFiles.value.splice(index, 1);
  imagePreviews.value.splice(index, 1);
}

// ── 파싱 초기화 ────────────────────────────────────────────
function resetParsing() {
  jobData.value = null;
  urlInput.value = '';
  urlParsed.value = false;
  dataCompleteness.value = null;
  imageFiles.value = [];
  imagePreviews.value = [];
  textInput.value = '';
}

// ── URL 파싱 ───────────────────────────────────────────────
async function parseUrl() {
  isParsing.value = true;
  errorMessage.value = '';
  jobData.value = null;
  urlParsed.value = false;
  try {
    const response = await axios.post('/api/core/job-planner/parse/', {
      type: 'url',
      url: urlInput.value,
    }, { withCredentials: true });
    mergeJobData(response.data);
  } catch (error) {
    errorMessage.value = error.response?.data?.error || '공고 파싱 중 오류가 발생했습니다.';
  } finally {
    isParsing.value = false;
    urlParsed.value = true;
  }
}

// ── 이미지/텍스트 보완 파싱 (기존 jobData에 병합) ──────────
async function parseSupplement() {
  isParsing.value = true;
  errorMessage.value = '';
  try {
    if (supplementMethod.value === 'image') {
      for (let i = 0; i < imageFiles.value.length; i++) {
        currentParsingIndex.value = i;
        const imageData = await new Promise((resolve) => {
          const reader = new FileReader();
          reader.onload = (e) => resolve(e.target.result);
          reader.readAsDataURL(imageFiles.value[i]);
        });
        const response = await axios.post('/api/core/job-planner/parse/', {
          type: 'image',
          image: imageData,
        }, { withCredentials: true });
        mergeJobData(response.data);
      }
    } else {
      const response = await axios.post('/api/core/job-planner/parse/', {
        type: 'text',
        text: textInput.value,
      }, { withCredentials: true });
      mergeJobData(response.data);
    }
  } catch (error) {
    errorMessage.value = error.response?.data?.error || '공고 파싱 중 오류가 발생했습니다.';
  } finally {
    isParsing.value = false;
    currentParsingIndex.value = 0;
  }
}

// ── 공고 삭제 ──────────────────────────────────────────────
async function removePosting(id) {
  try {
    await deleteJobPosting(id);
    postings.value = postings.value.filter(p => p.id !== id);
    if (selectedId.value === id) selectedId.value = null;
  } catch {
    errorMessage.value = '공고 삭제에 실패했습니다.';
  }
}

// ── 면접 시작 ──────────────────────────────────────────────
async function onStart() {
  isStarting.value = true;
  errorMessage.value = '';

  try {
    if (jobData.value) {
      // 파싱된 공고로 시작
      const postingId = jobData.value.saved_posting_id || null;
      if (!postingId) {
        const saved = await createJobPosting({
          company_name: jobData.value.company_name || '',
          position: jobData.value.position || '',
          job_responsibilities: jobData.value.job_responsibilities || '',
          required_qualifications: jobData.value.required_qualifications || '',
          preferred_qualifications: jobData.value.preferred_qualifications || '',
          required_skills: jobData.value.required_skills || [],
          preferred_skills: jobData.value.preferred_skills || [],
          experience_range: jobData.value.experience_range || '',
          source: 'url',
        });
        emit('start', { jobPostingId: saved.id, avatarType: avatarType.value });
      } else {
        emit('start', { jobPostingId: postingId, avatarType: avatarType.value });
      }
    } else {
      // 저장된 공고 또는 공고 없이 시작
      emit('start', { jobPostingId: selectedId.value, avatarType: avatarType.value });
    }
  } catch (err) {
    errorMessage.value = err.response?.data?.error || '시작에 실패했습니다. 다시 시도해주세요.';
    isStarting.value = false;
  }
}
</script>

<style scoped>
/* ── 전체 컨테이너 ─────────────────────────────────────── */
.job-posting-selector {
  max-width: 1200px;
  margin: 0 auto;
  padding: 48px 40px 40px;
  display: flex;
  flex-direction: column;
  gap: 24px;
  min-height: 100%;
  box-sizing: border-box;
}

/* ── 헤더 ──────────────────────────────────────────────── */
.selector-header { }

.selector-title {
  font-size: 26px;
  font-weight: 700;
  color: #ffffff;
  margin: 0 0 8px;
  letter-spacing: -0.02em;
}

.selector-desc {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.45);
  margin: 0;
}

/* ── 오류 배너 ─────────────────────────────────────────── */
.error-banner {
  background: rgba(239, 68, 68, 0.15);
  color: #fca5a5;
  border: 1px solid rgba(239, 68, 68, 0.3);
  padding: 12px 16px;
  border-radius: 8px;
  font-size: 13px;
}

/* ── 로딩 ──────────────────────────────────────────────── */
.loading-spinner {
  text-align: center;
  color: rgba(255, 255, 255, 0.4);
  padding: 48px;
  font-size: 14px;
}

/* ── 2컬럼 레이아웃 ────────────────────────────────────── */
.two-col-layout {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

/* ── 패널 공통 ─────────────────────────────────────────── */
.panel {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.btn-history-inline {
  padding: 6px 12px;
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  color: rgba(255,255,255,0.7);
  cursor: pointer;
  transition: all 0.2s;
}

.btn-history-inline:hover {
  background: rgba(99, 102, 241, 0.15);
  border-color: #6366f1;
  color: #a5b4fc;
}

.panel-title {
  font-size: 11px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.4);
  letter-spacing: 0.1em;
  text-transform: uppercase;
  margin: 0;
}

/* ── 저장된 공고 목록 ──────────────────────────────────── */
.posting-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 420px;
  overflow-y: auto;
}

.posting-list::-webkit-scrollbar { width: 4px; }
.posting-list::-webkit-scrollbar-track { background: transparent; }
.posting-list::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.12); border-radius: 99px; }

.posting-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 16px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
  background: rgba(255, 255, 255, 0.03);
}

.posting-card:hover {
  border-color: rgba(99, 102, 241, 0.6);
  background: rgba(99, 102, 241, 0.08);
}

.posting-card--selected {
  border-color: #6366f1;
  background: rgba(99, 102, 241, 0.15);
}

.posting-card__info { flex: 1; min-width: 0; }
.posting-card__company { font-weight: 600; font-size: 14px; color: #e5e7eb; }
.posting-card__position { font-size: 13px; color: rgba(255, 255, 255, 0.45); margin-top: 2px; }
.posting-card__meta {
  display: flex;
  gap: 12px;
  margin-top: 4px;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.25);
}

.btn-delete-posting {
  flex-shrink: 0;
  width: 26px;
  height: 26px;
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  color: rgba(255, 255, 255, 0.3);
  font-size: 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
  opacity: 0;
}

.posting-card:hover .btn-delete-posting { opacity: 1; }
.btn-delete-posting:hover {
  background: rgba(239, 68, 68, 0.2);
  border-color: rgba(239, 68, 68, 0.5);
  color: #fca5a5;
}

.empty-hint {
  text-align: center;
  color: rgba(255, 255, 255, 0.25);
  font-size: 13px;
  padding: 24px 16px;
  line-height: 1.7;
}

/* ── 파싱 섹션 ─────────────────────────────────────────── */
.input-method-tabs {
  display: flex;
  gap: 8px;
}

.method-tab {
  padding: 7px 16px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  background: transparent;
  font-size: 13px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.45);
  cursor: pointer;
  transition: all 0.15s;
}

.method-tab:hover {
  border-color: rgba(255, 255, 255, 0.25);
  color: rgba(255, 255, 255, 0.7);
}

.method-tab.active {
  border-color: #6366f1;
  background: rgba(99, 102, 241, 0.15);
  color: #a5b4fc;
  font-weight: 600;
}

.input-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.input-label {
  font-size: 12px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.5);
}

.url-input, .text-input {
  width: 100%;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 14px;
  font-family: inherit;
  color: #e5e7eb;
  background: rgba(255, 255, 255, 0.06);
  transition: border-color 0.15s;
  box-sizing: border-box;
}

.url-input::placeholder, .text-input::placeholder {
  color: rgba(255, 255, 255, 0.2);
}

.url-input:focus, .text-input:focus {
  outline: none;
  border-color: #6366f1;
  background: rgba(255, 255, 255, 0.08);
}

.text-input { resize: vertical; line-height: 1.5; }
.input-hint { font-size: 12px; color: rgba(255, 255, 255, 0.25); margin: 0; }

.btn-parse {
  padding: 10px 20px;
  background: rgba(99, 102, 241, 0.8);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  align-self: flex-start;
  transition: background 0.15s;
}

.btn-parse:hover:not(:disabled) { background: #6366f1; }
.btn-parse:disabled { opacity: 0.4; cursor: not-allowed; }

/* ── 정보 보완 안내 ─────────────────────────────────────── */
.completeness-bar-wrap {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.completeness-bar-header {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.55);
}

.completeness-bar-bg {
  height: 6px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 99px;
  overflow: hidden;
}

.completeness-bar-fill {
  height: 100%;
  border-radius: 99px;
  transition: width 0.4s;
}

.completeness-bar-fill.good { background: #22c55e; }
.completeness-bar-fill.fair { background: #f59e0b; }
.completeness-bar-fill.poor { background: #ef4444; }

.completeness-missing {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.35);
  margin: 0;
}

.supplement-hint {
  font-size: 12px;
  color: #fbbf24;
  background: rgba(251, 191, 36, 0.08);
  border: 1px solid rgba(251, 191, 36, 0.2);
  border-radius: 8px;
  padding: 8px 12px;
  margin: 0;
}

/* ── 이미지 업로드 ─────────────────────────────────────── */
.image-upload-area {
  border: 2px dashed rgba(255, 255, 255, 0.15);
  border-radius: 10px;
  padding: 20px;
  cursor: pointer;
  min-height: 110px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: border-color 0.15s;
}

.image-upload-area:hover { border-color: rgba(99, 102, 241, 0.5); }

.upload-placeholder {
  text-align: center;
  color: rgba(255, 255, 255, 0.3);
}

.upload-placeholder p { margin: 4px 0; font-size: 13px; }
.upload-hint { font-size: 11px !important; color: rgba(255, 255, 255, 0.2) !important; }

.image-previews-grid { display: flex; flex-wrap: wrap; gap: 8px; }
.image-preview-item { position: relative; width: 80px; height: 80px; }
.image-preview-item img { width: 100%; height: 100%; object-fit: cover; border-radius: 6px; }

.btn-remove-image {
  position: absolute;
  top: -6px;
  right: -6px;
  width: 20px;
  height: 20px;
  background: #ef4444;
  color: white;
  border: none;
  border-radius: 50%;
  font-size: 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
}

/* ── 파싱 결과 ─────────────────────────────────────────── */
.job-preview {
  border: 1px solid rgba(99, 102, 241, 0.35);
  background: rgba(99, 102, 241, 0.08);
  border-radius: 10px;
  padding: 14px 16px;
}

.job-preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.job-preview h4 {
  font-size: 12px;
  font-weight: 700;
  color: #a5b4fc;
  margin: 0;
}

.btn-reset-parse {
  padding: 4px 10px;
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 6px;
  font-size: 11px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.4);
  cursor: pointer;
  transition: all 0.15s;
}

.btn-reset-parse:hover {
  border-color: rgba(239, 68, 68, 0.5);
  color: #fca5a5;
  background: rgba(239, 68, 68, 0.1);
}

.preview-grid { display: flex; flex-direction: column; gap: 5px; margin-bottom: 8px; }
.preview-item { display: flex; gap: 10px; font-size: 13px; }
.preview-label { font-weight: 600; color: rgba(255, 255, 255, 0.45); min-width: 44px; flex-shrink: 0; }
.preview-value { color: #e5e7eb; }

.preview-skills { margin-top: 8px; display: flex; gap: 8px; align-items: flex-start; flex-wrap: wrap; }
.skill-tags { display: flex; flex-wrap: wrap; gap: 4px; }
.skill-tag {
  font-size: 11px;
  background: rgba(99, 102, 241, 0.2);
  color: #a5b4fc;
  border: 1px solid rgba(99, 102, 241, 0.3);
  padding: 2px 8px;
  border-radius: 99px;
}

/* ── 면접관 선택 ────────────────────────────────────────── */
.avatar-select {
  display: flex;
  gap: 10px;
  margin-bottom: 12px;
}
.avatar-btn {
  flex: 1;
  padding: 10px;
  border: 2px solid #444;
  border-radius: 8px;
  background: transparent;
  color: #ccc;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s;
}
.avatar-btn--active {
  border-color: #6366f1;
  background: rgba(99, 102, 241, 0.15);
  color: #a5b4fc;
}

/* ── 시작 버튼 ─────────────────────────────────────────── */
.start-btn {
  width: 100%;
  padding: 15px;
  background: #6366f1;
  color: white;
  border: none;
  border-radius: 12px;
  font-size: 16px;
  font-weight: 700;
  cursor: pointer;
  transition: background 0.15s, transform 0.1s;
  letter-spacing: 0.02em;
}

.start-btn:hover:not(:disabled) {
  background: #4f46e5;
}

.start-btn:active:not(:disabled) {
  transform: scale(0.99);
}

.start-btn:disabled { opacity: 0.35; cursor: not-allowed; }
</style>
