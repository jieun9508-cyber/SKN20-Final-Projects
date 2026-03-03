<template>
  <transition name="fade">
    <div v-if="isOpen" class="modal-overlay" @click.self="closeModal">
      <div class="job-planner-modal">
        <!-- Header -->
        <header class="modal-header">
          <div class="title-section">
            <div class="planner-badge">💼 JOB PLANNER</div>
            <h2 class="modal-title">AI 채용공고 분석</h2>
          </div>
          <button class="close-btn" @click="closeModal">&times;</button>
        </header>

        <!-- Main Flow Tabs -->
        <div class="flow-tabs">
          <button
            :class="['flow-tab', { active: currentStep === 'input' }]"
            @click="currentStep = 'input'"
          >
            1. 공고 입력
          </button>
          <button
            :class="['flow-tab', { active: currentStep === 'profile' }]"
            @click="currentStep = 'profile'"
          >
            2. 내 정보
          </button>
          <button
            :class="['flow-tab', { active: currentStep === 'result' }]"
            @click="currentStep = 'result'"
            :disabled="!analysisResult"
          >
            3. 최종 결과
          </button>
        </div>

        <!-- Content Area -->
        <div class="modal-body">
          <!-- Step 1: 공고 입력 -->
          <div v-if="currentStep === 'input'" class="input-step">
            <h3 class="step-title">채용공고를 입력하세요</h3>

            <!-- URL Input -->
            <div class="input-panel">
              <label>채용공고 URL</label>
              <input
                v-model="urlInput"
                type="text"
                placeholder="https://www.jobkorea.co.kr/..."
                class="url-input"
              >
              <p class="input-hint">잡코리아, 사람인, 원티드 등의 채용공고 URL을 입력하세요</p>

              <label style="margin-top: 12px;">기업 URL <span class="optional">(선택)</span></label>
              <input
                v-model="companyUrl"
                type="text"
                placeholder="https://company.com 또는 https://www.wanted.co.kr/company/..."
                class="url-input"
              >
              <p class="input-hint">회사 홈페이지나 원티드 기업 페이지를 입력하면 기업분석도 함께 진행됩니다</p>

              <button
                class="btn-parse"
                @click="parseJobPosting"
                :disabled="!urlInput || isParsing"
              >
                <span v-if="!isParsing">🔍 분석 시작</span>
                <span v-else>⏳ 분석 중...</span>
              </button>
            </div>

            <!-- Parsed Job Data Preview -->
            <div v-if="jobData" class="job-preview">
              <h4>✅ 파싱 완료</h4>
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

              <!-- 주요 업무 -->
              <div v-if="jobData.job_responsibilities" class="preview-detail-section">
                <div class="preview-detail-title">📋 주요 업무</div>
                <div class="preview-detail-content">{{ jobData.job_responsibilities }}</div>
              </div>

              <!-- 필수 요건 -->
              <div v-if="jobData.required_qualifications" class="preview-detail-section">
                <div class="preview-detail-title">✅ 필수 요건</div>
                <div class="preview-detail-content">{{ jobData.required_qualifications }}</div>
                <div v-if="jobData.required_skills && jobData.required_skills.length > 0" class="preview-skill-tags">
                  <span v-for="(skill, idx) in jobData.required_skills" :key="'req-' + idx" class="skill-tag required">
                    {{ skill }}
                  </span>
                </div>
              </div>

              <!-- 우대 조건 -->
              <div v-if="jobData.preferred_qualifications" class="preview-detail-section">
                <div class="preview-detail-title">⭐ 우대 조건</div>
                <div class="preview-detail-content">{{ jobData.preferred_qualifications }}</div>
                <div v-if="jobData.preferred_skills && jobData.preferred_skills.length > 0" class="preview-skill-tags">
                  <span v-for="(skill, idx) in jobData.preferred_skills" :key="'pref-' + idx" class="skill-tag preferred">
                    {{ skill }}
                  </span>
                </div>
              </div>

              <!-- 정보 충분도 인디케이터 -->
              <div v-if="dataCompleteness" class="completeness-indicator">
                <div class="completeness-header">
                  <span class="completeness-icon">
                    {{ dataCompleteness.level === 'good' ? '✅' : dataCompleteness.level === 'fair' ? '⚠️' : '❌' }}
                  </span>
                  <span class="completeness-title">정보 충분도</span>
                  <span class="completeness-score">{{ Math.round(dataCompleteness.rate * 100) }}%</span>
                </div>
                <div class="completeness-bar">
                  <div
                    class="completeness-fill"
                    :class="dataCompleteness.level"
                    :style="{ width: (dataCompleteness.rate * 100) + '%' }"
                  ></div>
                </div>
                <div v-if="needsMoreInfo" class="completeness-warning">
                  <div class="warning-text">
                    ⚠️ 부족한 정보: <strong>{{ missingFields.join(', ') }}</strong>
                  </div>

                  <!-- 추가 입력 섹션 -->
                  <div class="supplement-input-section">
                    <p class="supplement-title">💡 이미지 또는 텍스트를 추가로 입력하면 더 정확하게 분석할 수 있어요</p>

                    <div class="supplement-method-tabs">
                      <button
                        :class="['supp-tab', { active: supplementMethod === 'image' }]"
                        @click="supplementMethod = 'image'"
                      >
                        📸 이미지 추가
                      </button>
                      <button
                        :class="['supp-tab', { active: supplementMethod === 'text' }]"
                        @click="supplementMethod = 'text'"
                      >
                        📝 텍스트 추가
                      </button>
                    </div>

                    <!-- 이미지 업로드 -->
                    <div v-if="supplementMethod === 'image'" class="supplement-panel">
                      <div class="supplement-upload-area" @click="$refs.supplementImageInput.click()">
                        <input
                          ref="supplementImageInput"
                          type="file"
                          accept="image/*"
                          multiple
                          @change="handleSupplementImageUpload"
                          style="display: none"
                        >
                        <div v-if="supplementImages.length === 0" class="upload-placeholder">
                          <div class="upload-icon">📸</div>
                          <p>채용공고 이미지를 추가로 업로드하세요</p>
                          <p class="upload-hint">PNG, JPG, JPEG 지원 • 여러 장 선택 가능</p>
                        </div>
                        <div v-else class="image-previews-grid">
                          <div
                            v-for="(preview, idx) in supplementImagePreviews"
                            :key="idx"
                            class="image-preview-item"
                          >
                            <img :src="preview" alt="미리보기">
                            <button class="btn-remove-image" @click.stop="removeSupplementImage(idx)">&times;</button>
                            <div class="image-number">{{ idx + 1 }}</div>
                          </div>
                        </div>
                      </div>
                      <button
                        class="btn-supplement-parse"
                        @click="parseSupplementData"
                        :disabled="supplementImages.length === 0 || isSupplementParsing"
                      >
                        <span v-if="!isSupplementParsing">🔍 추가 분석 {{ supplementImages.length > 0 ? `(${supplementImages.length}장)` : '' }}</span>
                        <span v-else>⏳ 분석 중...</span>
                      </button>
                    </div>

                    <!-- 텍스트 입력 -->
                    <div v-if="supplementMethod === 'text'" class="supplement-panel">
                      <textarea
                        v-model="supplementText"
                        rows="6"
                        placeholder="채용공고 내용을 붙여넣으세요...

예시:
[회사명] 테크 스타트업
[포지션] 백엔드 개발자
[필수 스킬] Python, Django, PostgreSQL
..."
                        class="supplement-textarea"
                      ></textarea>
                      <button
                        class="btn-supplement-parse"
                        @click="parseSupplementData"
                        :disabled="!supplementText.trim() || isSupplementParsing"
                      >
                        <span v-if="!isSupplementParsing">🔍 추가 분석</span>
                        <span v-else>⏳ 분석 중...</span>
                      </button>
                    </div>
                  </div>
                </div>
                <div v-else class="completeness-success">
                  ✅ 충분한 정보가 수집되었습니다
                </div>
              </div>

              <!-- 기업분석 상태 표시 -->
              <div v-if="isAnalyzingCompany || companyAnalysis" class="company-analysis-section">
                <div v-if="isAnalyzingCompany" class="company-analyzing-msg">
                  ⏳ 기업 분석 중...
                </div>
                <div v-if="companyAnalysis" class="company-analysis-preview">
                  <div class="preview-badge">✅ 기업분석 완료</div>
                  <div class="preview-score">
                    종합 점수: {{ (companyAnalysis.overall_score?.total_score * 100).toFixed(0) }}점
                  </div>
                </div>
              </div>

              <div class="job-preview-actions">
                <button class="btn-reset-job" @click="resetJobData">
                  🔄 공고 초기화
                </button>
              </div>
            </div>

            <div class="step-next-row">
              <button class="btn-next" @click="currentStep = 'profile'">
                <span v-if="isParsing">⏳ 분석 중... 내 정보 먼저 입력 →</span>
                <span v-else>다음: 내 정보 입력 →</span>
              </button>
            </div>
          </div>

          <!-- Step 2: 내 프로필 -->
          <div v-if="currentStep === 'profile'" class="profile-step">
            <h3 class="step-title">내 정보를 입력하세요</h3>
            <div v-if="isParsing" class="parsing-background-notice">
              ⏳ 채용공고 분석이 백그라운드에서 진행 중입니다. 완료되면 자동으로 반영됩니다.
            </div>

            <div class="profile-form">
              <!-- 서류 업로드 섹션 -->
              <div class="form-section document-upload-section">
                <h4 class="form-section-title">📄 서류 업로드 <span class="optional">(선택)</span></h4>
                <p class="input-hint">이력서, 자기소개서, 포트폴리오를 업로드하면 아래 정보를 자동으로 채워드립니다</p>

                <div class="document-upload-grid">
                  <div class="upload-item">
                    <span class="upload-label">이력서</span>
                    <div class="upload-row">
                      <label class="upload-btn" :class="{ uploaded: resumePdf }">
                        {{ resumeFileName || '+ PDF 업로드' }}
                        <input type="file" accept=".pdf" @change="handlePdfUpload($event, 'resume')" hidden>
                      </label>
                      <button v-if="resumePdf" class="upload-clear-btn" @click="clearPdf('resume')" title="삭제">×</button>
                    </div>
                  </div>
                  <div class="upload-item">
                    <span class="upload-label">경력기술서</span>
                    <div class="upload-row">
                      <label class="upload-btn" :class="{ uploaded: careerDescPdf }">
                        {{ careerDescFileName || '+ PDF 업로드' }}
                        <input type="file" accept=".pdf" @change="handlePdfUpload($event, 'career_description')" hidden>
                      </label>
                      <button v-if="careerDescPdf" class="upload-clear-btn" @click="clearPdf('career_description')" title="삭제">×</button>
                    </div>
                  </div>
                  <div class="upload-item">
                    <span class="upload-label">자기소개서</span>
                    <div class="upload-row">
                      <label class="upload-btn" :class="{ uploaded: coverLetterPdf }">
                        {{ coverLetterFileName || '+ PDF 업로드' }}
                        <input type="file" accept=".pdf" @change="handlePdfUpload($event, 'cover_letter')" hidden>
                      </label>
                      <button v-if="coverLetterPdf" class="upload-clear-btn" @click="clearPdf('cover_letter')" title="삭제">×</button>
                    </div>
                  </div>
                  <div class="upload-item">
                    <span class="upload-label">포트폴리오</span>
                    <div class="upload-row">
                      <label class="upload-btn" :class="{ uploaded: portfolioPdf }">
                        {{ portfolioFileName || '+ PDF 업로드' }}
                        <input type="file" accept=".pdf" @change="handlePdfUpload($event, 'portfolio')" hidden>
                      </label>
                      <button v-if="portfolioPdf" class="upload-clear-btn" @click="clearPdf('portfolio')" title="삭제">×</button>
                    </div>
                  </div>
                </div>

                <button
                  v-if="resumePdf || coverLetterPdf || portfolioPdf"
                  class="btn-parse-resume"
                  @click="parseResumeDocuments"
                  :disabled="isParsingDocuments"
                >
                  <span v-if="!isParsingDocuments">✨ 서류 분석하여 자동 입력</span>
                  <span v-else>⏳ 분석 중... (병렬 처리 중)</span>
                </button>

                <div v-if="documentParseSuccess" class="parse-success-msg">
                  ✅ 분석 완료! 아래 내용을 확인하고 수정하세요.
                </div>
              </div>

              <!-- 기본 정보 -->
              <div class="form-section">
                <h4 class="form-section-title">📝 기본 정보</h4>
                <div class="form-row-2col">
                  <div class="form-group">
                    <label>이름 <span class="optional">(선택)</span></label>
                    <input
                      v-model="name"
                      type="text"
                      placeholder="홍길동"
                    >
                  </div>
                  <div class="form-group">
                    <label>현재 직무 <span class="optional">(선택)</span></label>
                    <input
                      v-model="currentRole"
                      type="text"
                      placeholder="백엔드 개발자"
                    >
                  </div>
                </div>
                <div class="form-row">
                  <div class="form-group">
                    <label>경력 (년) <span class="required">*</span></label>
                    <input
                      v-model.number="experienceYears"
                      type="number"
                      min="0"
                      placeholder="2"
                    >
                  </div>
                </div>
              </div>

              <!-- 스킬 및 숙련도 -->
              <div class="form-section">
                <h4 class="form-section-title">💻 보유 스킬 및 숙련도 <span class="required">*</span></h4>
                <div class="form-row">
                  <div class="form-group">
                    <label>보유 스킬 (쉼표로 구분)</label>
                    <input
                      v-model="userSkillsInput"
                      type="text"
                      placeholder="Python, Django, MySQL, React"
                      @input="parseUserSkills"
                    >
                    <p class="input-hint">입력 후 아래에서 각 스킬의 숙련도를 선택하세요</p>
                  </div>
                </div>

                <!-- 스킬 레벨 입력 -->
                <div class="skill-levels-container">
                  <div
                    v-for="skill in userSkills"
                    :key="skill"
                    class="skill-level-item"
                  >
                    <div class="skill-name">{{ skill }}</div>
                    <div class="skill-level-selector">
                      <button
                        v-for="level in [1, 2, 3, 4, 5]"
                        :key="level"
                        :class="['level-btn', { active: skillLevels[skill] === level }]"
                        @click="skillLevels[skill] = level"
                      >
                        {{ level }}
                      </button>
                    </div>
                    <div class="skill-level-label">
                      {{ getLevelLabel(skillLevels[skill] || 3) }}
                    </div>
                    <button class="skill-delete-btn" @click="removeSkill(skill)" title="삭제">×</button>
                  </div>
                  <div class="skill-add-row">
                    <input
                      v-model="newSkillInput"
                      type="text"
                      placeholder="스킬 추가 (예: TypeScript)"
                      @keyup.enter="addSkill"
                    />
                    <button class="skill-add-btn" @click="addSkill">+ 추가</button>
                  </div>
                  <p v-if="userSkills.length > 0" class="level-guide">
                    1=입문 | 2=초급 | 3=중급 | 4=고급 | 5=전문가
                  </p>
                </div>
              </div>

              <!-- 추가 정보 -->
              <div class="form-section">
                <h4 class="form-section-title">🎓 추가 정보 <span class="optional">(선택)</span></h4>
                <div class="form-row">
                  <div class="form-group">
                    <label>학력</label>
                    <input
                      v-model="education"
                      type="text"
                      placeholder="예: 컴퓨터공학 학사"
                    >
                  </div>
                </div>
                <div class="form-row">
                  <div class="form-group">
                    <label>자격증 (쉼표로 구분)</label>
                    <input
                      v-model="certificationsInput"
                      type="text"
                      placeholder="정보처리기사, AWS Solutions Architect"
                      @input="parseCertifications"
                    >
                  </div>
                </div>
                <div class="form-row">
                  <div class="form-group">
                    <label>교육 이수 내역</label>
                    <div class="training-list">
                      <div v-for="(item, idx) in training" :key="idx" class="training-item">
                        <span class="training-name">{{ item.name }}</span>
                        <span v-if="item.institution" class="training-meta">{{ item.institution }}</span>
                        <span v-if="item.period" class="training-meta">{{ item.period }}</span>
                        <button class="training-delete-btn" @click="removeTraining(idx)">×</button>
                      </div>
                    </div>
                    <div class="training-add-row">
                      <input v-model="newTrainingName" type="text" placeholder="교육명 (예: SKN AI 부트캠프)" @keyup.enter="addTraining" />
                      <input v-model="newTrainingInstitution" type="text" placeholder="기관 (선택)" />
                      <input v-model="newTrainingPeriod" type="text" placeholder="기간 (선택)" />
                      <button class="skill-add-btn" @click="addTraining">+ 추가</button>
                    </div>
                  </div>
                </div>
                <div class="form-row">
                  <div class="form-group">
                    <label>커리어 목표</label>
                    <textarea
                      v-model="careerGoals"
                      rows="2"
                      placeholder="예: 대규모 트래픽을 처리하는 백엔드 시스템 개발 경험 쌓기"
                    ></textarea>
                  </div>
                </div>
                <div class="form-row">
                  <div class="form-group">
                    <label>준비 가능 일수</label>
                    <input
                      v-model.number="availablePrepDays"
                      type="number"
                      min="0"
                      placeholder="14"
                    >
                    <p class="input-hint">면접까지 준비할 수 있는 날짜 수</p>
                  </div>
                </div>
              </div>

              <button
                class="btn-analyze"
                @click="analyzeMatch"
                :disabled="!userSkills.length || isAnalyzing"
              >
                <span v-if="!isAnalyzing">🚀 매칭 분석 시작</span>
                <span v-else>⏳ 분석 중...</span>
              </button>
            </div>
          </div>

          <!-- Step 3: 분석 결과 -->
          <div v-if="currentStep === 'result' && analysisResult" class="result-step">
            <h3 class="step-title">분석 결과</h3>

            <!-- Score Overview -->
            <div class="score-overview">
              <div class="score-card">
                <div class="score-label">준비도</div>
                <div class="score-value" :class="getScoreClass(analysisResult.readiness_score)">
                  {{ (analysisResult.readiness_score * 100).toFixed(1) }}%
                </div>
              </div>
              <div class="score-card">
                <div class="score-label">스킬 갭</div>
                <div class="score-value" :class="getScoreClass(1 - analysisResult.skill_gap_score)">
                  {{ (analysisResult.skill_gap_score * 100).toFixed(1) }}%
                </div>
              </div>
              <div class="score-card">
                <div class="score-label">경력 적합도</div>
                <div class="score-value" :class="getScoreClass(analysisResult.experience_fit)">
                  {{ (analysisResult.experience_fit * 100).toFixed(1) }}%
                </div>
              </div>
              <div v-if="analysisResult.proficiency_score" class="score-card">
                <div class="score-label">숙련도</div>
                <div class="score-value" :class="getScoreClass(analysisResult.proficiency_score)">
                  {{ (analysisResult.proficiency_score * 100).toFixed(1) }}%
                </div>
              </div>
            </div>

            <!-- Insights -->
            <div v-if="analysisResult.insights && analysisResult.insights.length > 0" class="insights-section">
              <h4 class="section-subtitle">💡 인사이트</h4>
              <div class="insights-list">
                <div
                  v-for="(insight, idx) in analysisResult.insights"
                  :key="'insight-' + idx"
                  :class="['insight-item', insight.type]"
                >
                  <div class="insight-header">
                    <span class="insight-icon">
                      {{ insight.type === 'positive' ? '✅' : insight.type === 'warning' ? '⚠️' : 'ℹ️' }}
                    </span>
                    <span class="insight-title">{{ insight.title }}</span>
                  </div>
                  <div class="insight-message">{{ insight.message }}</div>
                </div>
              </div>
            </div>

            <!-- Matched Skills -->
            <div class="skill-section">
              <h4 class="section-subtitle">✅ 매칭된 스킬 ({{ analysisResult.matched_skills.length }}개)</h4>
              <div class="skill-list matched">
                <div
                  v-for="(match, idx) in analysisResult.matched_skills"
                  :key="'matched-' + idx"
                  class="skill-item"
                >
                  <span class="skill-required">{{ match.required }}</span>
                  <span class="skill-arrow">↔</span>
                  <span class="skill-user">{{ match.user_skill }}</span>
                  <span class="skill-similarity">{{ (match.similarity * 100).toFixed(0) }}%</span>
                </div>
              </div>
            </div>

            <!-- Missing Skills -->
            <div class="skill-section" v-if="analysisResult.missing_skills.length > 0">
              <h4 class="section-subtitle">❌ 부족한 스킬 ({{ analysisResult.missing_skills.length }}개)</h4>
              <div class="skill-list missing">
                <div
                  v-for="(miss, idx) in analysisResult.missing_skills"
                  :key="'missing-' + idx"
                  class="skill-item"
                >
                  <span class="skill-name">{{ miss.required }}</span>
                </div>
              </div>
            </div>

            <!-- Job Recommendations -->
            <div v-if="recommendations.length > 0" class="recommendations-section">
              <h3 class="recommendations-title">💡 추천 채용공고</h3>
              <p class="recommendations-subtitle">
                현재 스킬과 더 잘 맞는 공고들을 찾았습니다 ({{ recommendations.length }}개)
              </p>

              <div class="recommendations-list">
                <div
                  v-for="(rec, idx) in recommendations"
                  :key="'rec-' + idx"
                  class="recommendation-card"
                >
                  <div class="rec-header">
                    <div class="rec-main-info">
                      <h4 class="rec-title">{{ rec.title }}</h4>
                      <div class="rec-company">{{ rec.company_name }}</div>
                    </div>
                    <div class="rec-match">
                      <div class="rec-match-rate" :class="getScoreClass(rec.match_rate)">
                        {{ (rec.match_rate * 100).toFixed(0) }}%
                      </div>
                      <div class="rec-match-label">매칭률</div>
                    </div>
                  </div>

                  <div class="rec-details">
                    <div class="rec-info-row">
                      <span class="rec-label">📍 위치:</span>
                      <span class="rec-value">{{ rec.location || '정보 없음' }}</span>
                    </div>
                    <div class="rec-info-row">
                      <span class="rec-label">🔗 출처:</span>
                      <span class="rec-value">{{ rec.source }}</span>
                    </div>
                    <div class="rec-info-row">
                      <span class="rec-label">✅ 매칭:</span>
                      <span class="rec-value">{{ rec.matched_count }} / {{ rec.total_skills }}개 스킬</span>
                    </div>
                  </div>

                  <div class="rec-reason">
                    <span class="rec-reason-icon">💬</span>
                    <span class="rec-reason-text">{{ rec.reason }}</span>
                  </div>

                  <div class="rec-skills">
                    <span class="rec-skill-label">요구 스킬:</span>
                    <div class="rec-skill-tags">
                      <span
                        v-for="(skill, sidx) in rec.skills.slice(0, 6)"
                        :key="'skill-' + sidx"
                        class="rec-skill-tag"
                      >
                        {{ skill }}
                      </span>
                      <span v-if="rec.skills.length > 6" class="rec-skill-more">
                        +{{ rec.skills.length - 6 }}
                      </span>
                    </div>
                  </div>

                  <a
                    v-if="rec.url"
                    :href="rec.url"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="rec-link"
                  >
                    공고 보러가기 →
                  </a>
                </div>
              </div>
            </div>

            <!-- Loading Recommendations -->
            <div v-if="isLoadingRecommendations" class="loading-recommendations">
              <div class="loading-spinner"></div>
              <p v-if="isLoadingRecommendations">
                추천 공고를 찾고 있습니다... (사람인, 잡코리아 검색 중)
              </p>
              <p v-else>
                추천 공고를 준비 중입니다...
              </p>
            </div>

            <!-- Company Analysis Results -->
            <div v-if="companyAnalysis" class="company-analysis-results">
              <h3 class="analysis-title">🏢 기업 분석 결과</h3>

              <!-- Overall Scores -->
              <div class="company-score-grid">
                <div class="company-score-card">
                  <div class="score-label">기술력</div>
                  <div class="score-bar">
                    <div class="score-fill" :style="{ width: (companyAnalysis.overall_score.tech_score * 100) + '%' }"></div>
                  </div>
                  <div class="score-text">{{ (companyAnalysis.overall_score.tech_score * 100).toFixed(0) }}점</div>
                </div>
                <div class="company-score-card">
                  <div class="score-label">성장성</div>
                  <div class="score-bar">
                    <div class="score-fill" :style="{ width: (companyAnalysis.overall_score.growth_score * 100) + '%' }"></div>
                  </div>
                  <div class="score-text">{{ (companyAnalysis.overall_score.growth_score * 100).toFixed(0) }}점</div>
                </div>
                <div class="company-score-card">
                  <div class="score-label">복지</div>
                  <div class="score-bar">
                    <div class="score-fill" :style="{ width: (companyAnalysis.overall_score.welfare_score * 100) + '%' }"></div>
                  </div>
                  <div class="score-text">{{ (companyAnalysis.overall_score.welfare_score * 100).toFixed(0) }}점</div>
                </div>
              </div>

              <!-- Company Overview -->
              <div class="analysis-section">
                <h4 class="section-subtitle">📋 회사 개요</h4>
                <div class="analysis-content">
                  <p>{{ companyAnalysis.overview.description }}</p>
                  <div class="info-grid">
                    <div class="info-item" v-if="companyAnalysis.overview.industry">
                      <span class="info-label">산업:</span>
                      <span class="info-value">{{ companyAnalysis.overview.industry }}</span>
                    </div>
                    <div class="info-item" v-if="companyAnalysis.overview.size">
                      <span class="info-label">규모:</span>
                      <span class="info-value">{{ companyAnalysis.overview.size }}</span>
                    </div>
                    <div class="info-item" v-if="companyAnalysis.overview.founded_year">
                      <span class="info-label">설립:</span>
                      <span class="info-value">{{ companyAnalysis.overview.founded_year }}년</span>
                    </div>
                  </div>
                  <p v-if="companyAnalysis.overview.vision" class="vision-text">
                    <strong>비전:</strong> {{ companyAnalysis.overview.vision }}
                  </p>
                </div>
              </div>

              <!-- Tech Stack -->
              <div class="analysis-section">
                <h4 class="section-subtitle">💻 기술 스택 및 개발 문화</h4>
                <div class="analysis-content">
                  <div class="tech-tags" v-if="companyAnalysis.tech_stack.languages?.length">
                    <span class="tag-label">언어:</span>
                    <span v-for="(lang, idx) in companyAnalysis.tech_stack.languages" :key="'lang-' + idx" class="tech-tag">
                      {{ lang }}
                    </span>
                  </div>
                  <div class="tech-tags" v-if="companyAnalysis.tech_stack.frameworks?.length">
                    <span class="tag-label">프레임워크:</span>
                    <span v-for="(fw, idx) in companyAnalysis.tech_stack.frameworks" :key="'fw-' + idx" class="tech-tag">
                      {{ fw }}
                    </span>
                  </div>
                  <div class="tech-tags" v-if="companyAnalysis.tech_stack.tools?.length">
                    <span class="tag-label">도구:</span>
                    <span v-for="(tool, idx) in companyAnalysis.tech_stack.tools" :key="'tool-' + idx" class="tech-tag">
                      {{ tool }}
                    </span>
                  </div>
                  <p v-if="companyAnalysis.tech_stack.culture">{{ companyAnalysis.tech_stack.culture }}</p>
                  <p v-if="companyAnalysis.tech_stack.tech_blog" class="tech-blog-info">
                    📝 기술 블로그:
                    <a
                      v-if="companyAnalysis.tech_stack.tech_blog.startsWith('http')"
                      :href="companyAnalysis.tech_stack.tech_blog"
                      target="_blank"
                      rel="noopener noreferrer"
                      class="tech-blog-link"
                    >{{ companyAnalysis.tech_stack.tech_blog }}</a>
                    <span v-else>{{ companyAnalysis.tech_stack.tech_blog }}</span>
                  </p>
                </div>
              </div>

              <!-- Growth & Stability -->
              <div class="analysis-section">
                <h4 class="section-subtitle">📈 성장성 및 안정성</h4>
                <div class="analysis-content">
                  <div class="growth-grid">
                    <div class="growth-item">
                      <span class="growth-label">투자:</span>
                      <span class="growth-value">{{ companyAnalysis.growth.funding || '정보 없음' }}</span>
                    </div>
                    <div class="growth-item">
                      <span class="growth-label">시장 위치:</span>
                      <span class="growth-value">{{ companyAnalysis.growth.market_position || '정보 없음' }}</span>
                    </div>
                    <div class="growth-item">
                      <span class="growth-label">성장 가능성:</span>
                      <span :class="['growth-badge', companyAnalysis.growth.growth_potential]">
                        {{ companyAnalysis.growth.growth_potential }}
                      </span>
                    </div>
                    <div class="growth-item">
                      <span class="growth-label">안정성:</span>
                      <span :class="['growth-badge', companyAnalysis.growth.stability]">
                        {{ companyAnalysis.growth.stability }}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Welfare -->
              <div class="analysis-section">
                <h4 class="section-subtitle">🎁 복지 및 근무환경</h4>
                <div class="analysis-content">
                  <div class="welfare-item" v-if="companyAnalysis.welfare.salary_level">
                    <strong>연봉 수준:</strong> {{ companyAnalysis.welfare.salary_level }}
                  </div>
                  <div class="welfare-item" v-if="companyAnalysis.welfare.benefits?.length">
                    <strong>복지 혜택:</strong>
                    <ul class="benefits-list">
                      <li v-for="(benefit, idx) in companyAnalysis.welfare.benefits" :key="'benefit-' + idx">
                        {{ benefit }}
                      </li>
                    </ul>
                  </div>
                  <div class="welfare-item" v-if="companyAnalysis.welfare.work_life_balance">
                    <strong>워라밸:</strong> {{ companyAnalysis.welfare.work_life_balance }}
                  </div>
                  <div class="welfare-item" v-if="companyAnalysis.welfare.remote_work">
                    <strong>리모트:</strong> {{ companyAnalysis.welfare.remote_work }}
                  </div>
                </div>
              </div>

              <!-- Recommendation -->
              <div class="analysis-section recommendation-section">
                <h4 class="section-subtitle">💡 종합 평가</h4>
                <div class="recommendation-content">
                  {{ companyAnalysis.recommendation }}
                </div>
              </div>
            </div>

            <!-- Final Report -->
            <div v-if="finalReport" class="final-report-section">
              <h3 class="report-title">📊 종합 취업 전략 보고서</h3>

              <!-- SWOT Analysis -->
              <div class="swot-section">
                <h4 class="section-subtitle">🎯 SWOT 분석</h4>
                <div class="swot-grid">
                  <div class="swot-card strengths">
                    <div class="swot-header">💪 Strengths (강점)</div>
                    <ul class="swot-list">
                      <li v-for="(item, idx) in finalReport.swot.strengths" :key="'s-' + idx">
                        {{ item }}
                      </li>
                    </ul>
                  </div>
                  <div class="swot-card weaknesses">
                    <div class="swot-header">⚠️ Weaknesses (약점)</div>
                    <ul class="swot-list">
                      <li v-for="(item, idx) in finalReport.swot.weaknesses" :key="'w-' + idx">
                        {{ item }}
                      </li>
                    </ul>
                  </div>
                  <div class="swot-card opportunities">
                    <div class="swot-header">🌟 Opportunities (기회)</div>
                    <ul class="swot-list">
                      <li v-for="(item, idx) in finalReport.swot.opportunities" :key="'o-' + idx">
                        {{ item }}
                      </li>
                    </ul>
                  </div>
                  <div class="swot-card threats">
                    <div class="swot-header">🚨 Threats (위협)</div>
                    <ul class="swot-list">
                      <li v-for="(item, idx) in finalReport.swot.threats" :key="'t-' + idx">
                        {{ item }}
                      </li>
                    </ul>
                  </div>
                </div>
              </div>

              <!-- Interview Questions -->
              <div class="interview-section">
                <h4 class="section-subtitle">💬 예상 면접 질문 TOP 5</h4>
                <div class="interview-questions-list">
                  <div
                    v-for="(q, idx) in finalReport.interview_questions"
                    :key="'iq-' + idx"
                    class="interview-question-card"
                  >
                    <div class="question-number-badge">Q{{ idx + 1 }}</div>
                    <div class="question-content">
                      <div class="question-title">{{ q.question }}</div>
                      <div class="answer-guide">
                        <strong>답변 가이드:</strong> {{ q.answer_guide }}
                      </div>
                      <div v-if="q.tips" class="tips">
                        <strong>💡 Tip:</strong> {{ q.tips }}
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Experience Packaging -->
              <div class="packaging-section">
                <h4 class="section-subtitle">📦 경험 포장 가이드</h4>
                <div class="packaging-grid">
                  <div class="packaging-card">
                    <div class="packaging-title">📄 이력서 강조 포인트</div>
                    <ul class="packaging-list">
                      <li v-for="(item, idx) in finalReport.experience_packaging.resume_highlights" :key="'rh-' + idx">
                        {{ item }}
                      </li>
                    </ul>
                  </div>
                  <div class="packaging-card">
                    <div class="packaging-title">💼 포트폴리오 팁</div>
                    <ul class="packaging-list">
                      <li v-for="(item, idx) in finalReport.experience_packaging.portfolio_tips" :key="'pt-' + idx">
                        {{ item }}
                      </li>
                    </ul>
                  </div>
                  <div class="packaging-card">
                    <div class="packaging-title">🛠️ 스킬 보완 전략</div>
                    <ul class="packaging-list">
                      <li v-for="(item, idx) in finalReport.experience_packaging.skill_compensation" :key="'sc-' + idx">
                        {{ item }}
                      </li>
                    </ul>
                  </div>
                </div>
              </div>

              <!-- Execution Strategy -->
              <div class="execution-section">
                <h4 class="section-subtitle">🎯 실행 전략</h4>
                <div class="timeline">
                  <div class="timeline-item immediate">
                    <div class="timeline-badge">🔥 즉시</div>
                    <div class="timeline-content">
                      <ul class="timeline-list">
                        <li v-for="(item, idx) in finalReport.execution_strategy.immediate" :key="'im-' + idx">
                          {{ item }}
                        </li>
                      </ul>
                    </div>
                  </div>
                  <div class="timeline-item short-term">
                    <div class="timeline-badge">⚡ 1-2주</div>
                    <div class="timeline-content">
                      <ul class="timeline-list">
                        <li v-for="(item, idx) in finalReport.execution_strategy.short_term" :key="'st-' + idx">
                          {{ item }}
                        </li>
                      </ul>
                    </div>
                  </div>
                  <div class="timeline-item mid-term">
                    <div class="timeline-badge">📅 1개월</div>
                    <div class="timeline-content">
                      <ul class="timeline-list">
                        <li v-for="(item, idx) in finalReport.execution_strategy.mid_term" :key="'mt-' + idx">
                          {{ item }}
                        </li>
                      </ul>
                    </div>
                  </div>
                  <div class="timeline-item application">
                    <div class="timeline-badge">🎯 지원 시점</div>
                    <div class="timeline-content">
                      <p class="application-timing">{{ finalReport.execution_strategy.application_timing }}</p>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Final Message -->
              <div class="final-message-section">
                <div class="final-message">
                  {{ finalReport.final_message }}
                </div>
              </div>
            </div>

            <!-- AI 지원 도구 -->
            <div class="action-tools-section">
              <h3 class="action-tools-title">🛠️ AI 지원 도구</h3>
              <div class="action-tools-buttons">
                <button class="btn-tool" @click="reviewPortfolio" :disabled="isReviewingPortfolio">
                  <span v-if="isReviewingPortfolio">⏳ 분석 중...</span>
                  <span v-else>📊 포트폴리오 개선점 분석</span>
                </button>
              </div>

              <!-- 자기소개서: 기업 문항 기반 -->
              <div class="cover-letter-questions-section">
                <h4 class="result-subtitle">✍️ 기업 문항별 자기소개서</h4>
                <p class="questions-hint">기업의 자기소개서 항목을 입력하세요 (항목당 한 줄)</p>
                <textarea
                  v-model="coverLetterQuestions"
                  class="questions-textarea"
                  placeholder="예시)&#10;성장 과정을 서술하세요 (500자 이내)&#10;지원 동기를 써주세요 (700자 이내)&#10;입사 후 포부를 작성하세요 (500자 이내)"
                  rows="5"
                ></textarea>
                <button
                  class="btn-tool"
                  @click="generateCoverLetterByQuestions"
                  :disabled="isGeneratingCoverLetter || !coverLetterQuestions.trim()"
                >
                  <span v-if="isGeneratingCoverLetter">⏳ 작성 중...</span>
                  <span v-else>✍️ 문항별 자기소개서 작성</span>
                </button>
              </div>

              <!-- 생성된 자기소개서 -->
              <div v-if="generatedCoverLetter" class="cover-letter-result">
                <h4 class="result-subtitle">✍️ 자기소개서</h4>
                <div
                  v-for="(item, idx) in generatedCoverLetter"
                  :key="'cl-' + idx"
                  class="cover-letter-item"
                >
                  <div class="cl-question">Q{{ idx + 1 }}. {{ item.question }}</div>
                  <pre class="cover-letter-text">{{ item.answer }}</pre>
                </div>
              </div>

              <!-- 포트폴리오 분석 결과 -->
              <div v-if="portfolioReview" class="portfolio-review-result">
                <h4 class="result-subtitle">📊 포트폴리오 분석 결과</h4>
                <div class="review-section" v-if="portfolioReview.strengths?.length">
                  <div class="review-section-title">💪 강점</div>
                  <ul class="review-list">
                    <li v-for="(item, idx) in portfolioReview.strengths" :key="'ps-' + idx">{{ item }}</li>
                  </ul>
                </div>
                <div class="review-section" v-if="portfolioReview.improvements?.length">
                  <div class="review-section-title">🔧 개선 제안</div>
                  <div
                    class="improvement-card"
                    v-for="(imp, idx) in portfolioReview.improvements"
                    :key="'pi-' + idx"
                  >
                    <div class="imp-target">🎯 {{ imp.target }}</div>
                    <div class="imp-issue">⚠️ {{ imp.issue }}</div>
                    <div class="imp-suggestion">💡 {{ imp.suggestion }}</div>
                  </div>
                </div>
                <div class="review-section" v-if="portfolioReview.missing?.length">
                  <div class="review-section-title">❌ 부족한 부분</div>
                  <ul class="review-list missing">
                    <li v-for="(item, idx) in portfolioReview.missing" :key="'pm-' + idx">{{ item }}</li>
                  </ul>
                </div>
                <div class="review-section" v-if="portfolioReview.priority_actions?.length">
                  <div class="review-section-title">🚀 우선 실행 액션</div>
                  <ol class="review-list priority">
                    <li v-for="(item, idx) in portfolioReview.priority_actions" :key="'pp-' + idx">{{ item }}</li>
                  </ol>
                </div>
              </div>
            </div>

            <button class="btn-restart" @click="resetAll">
              🔄 새로운 공고 분석하기
            </button>
          </div>

          <!-- Error Display -->
          <div v-if="errorMessage" class="error-banner">
            ⚠️ {{ errorMessage }}
          </div>
        </div>
      </div>
    </div>
  </transition>
</template>

<script>
import axios from 'axios';
import { useGameStore } from '@/stores/game';

export default {
  name: 'JobPlannerModal',
  props: {
    isOpen: Boolean
  },
  data() {
    return {
      currentStep: 'input',

      // Input data
      urlInput: '',

      // Parsed job data
      jobData: null,
      dataCompleteness: null,  // 정보 충분도 평가
      needsMoreInfo: false,    // 추가 정보 필요 여부
      missingFields: [],       // 부족한 필드 목록

      // 추가 입력 (URL 파싱 후 정보 부족 시)
      supplementMethod: 'image',     // 'image' | 'text'
      supplementImages: [],
      supplementImagePreviews: [],
      supplementText: '',
      isSupplementParsing: false,

      // 서류 업로드
      resumePdf: null,
      coverLetterPdf: null,
      portfolioPdf: null,
      careerDescPdf: null,
      resumeFileName: '',
      coverLetterFileName: '',
      portfolioFileName: '',
      careerDescFileName: '',
      isParsingDocuments: false,
      documentParseSuccess: false,
      // 서류 파싱 추가 데이터
      parsedEmail: null,
      parsedPhone: null,
      parsedLanguages: [],
      parsedAwards: [],
      parsedStrengths: [],
      parsedWorkExperience: [],
      parsedKeyAchievements: [],
      parsedProjects: [],
      parsedGithubUrl: null,
      parsedPortfolioUrl: null,
      parsedTeamworkExperience: null,
      parsedGrowthStory: null,

      // User data
      name: '',
      currentRole: '',
      experienceYears: 0,
      userSkills: [],
      userSkillsInput: '',
      skillLevels: {},  // {"Python": 4, "Django": 3}
      newSkillInput: '',
      education: '',
      certifications: [],
      certificationsInput: '',
      training: [],
      newTrainingName: '',
      newTrainingInstitution: '',
      newTrainingPeriod: '',
      careerGoals: '',
      availablePrepDays: null,

      // Company Analysis
      companyUrl: '',
      companyAnalysis: null,
      isAnalyzingCompany: false,

      // Analysis result
      analysisResult: null,

      // Agent Report
      finalReport: null,
      isGeneratingReport: false,

      // Recommendations
      recommendations: [],
      isLoadingRecommendations: false,

      // Cover Letter & Portfolio Review
      coverLetterQuestions: '',
      generatedCoverLetter: null,
      portfolioReview: null,
      isGeneratingCoverLetter: false,
      isReviewingPortfolio: false,

      // Status
      isParsing: false,
      isAnalyzing: false,
      errorMessage: ''
    };
  },
  methods: {
    closeModal() {
      this.$emit('close');
    },

    clearPdf(type) {
      if (type === 'resume') { this.resumePdf = null; this.resumeFileName = ''; }
      else if (type === 'cover_letter') { this.coverLetterPdf = null; this.coverLetterFileName = ''; }
      else if (type === 'portfolio') { this.portfolioPdf = null; this.portfolioFileName = ''; }
      else if (type === 'career_description') { this.careerDescPdf = null; this.careerDescFileName = ''; }
    },

    handlePdfUpload(event, type) {
      const file = event.target.files[0];
      if (!file) return;

      const reader = new FileReader();
      reader.onload = (e) => {
        if (type === 'resume') {
          this.resumePdf = e.target.result;
          this.resumeFileName = file.name;
        } else if (type === 'cover_letter') {
          this.coverLetterPdf = e.target.result;
          this.coverLetterFileName = file.name;
        } else if (type === 'portfolio') {
          this.portfolioPdf = e.target.result;
          this.portfolioFileName = file.name;
        } else if (type === 'career_description') {
          this.careerDescPdf = e.target.result;
          this.careerDescFileName = file.name;
        }
      };
      reader.readAsDataURL(file);
    },

    async parseResumeDocuments() {
      this.isParsingDocuments = true;
      this.documentParseSuccess = false;
      this.errorMessage = '';

      try {
        const payload = {};
        if (this.resumePdf) payload.resume = this.resumePdf;
        if (this.coverLetterPdf) payload.cover_letter = this.coverLetterPdf;
        if (this.portfolioPdf) payload.portfolio = this.portfolioPdf;
        if (this.careerDescPdf) payload.career_description = this.careerDescPdf;

        const response = await axios.post('/api/core/job-planner/parse-resume/', payload);
        const data = response.data;

        // 기본 폼 자동 채우기
        if (data.name) this.name = data.name;
        if (data.current_role) this.currentRole = data.current_role;
        if (data.education) this.education = data.education;
        if (data.certifications?.length) {
          this.certifications = data.certifications;
          this.certificationsInput = data.certifications.join(', ');
        }
        if (data.training?.length) {
          this.training = data.training;
        }
        if (data.career_goals) this.careerGoals = data.career_goals;
        if (data.experience_years) this.experienceYears = data.experience_years;
        if (data.user_skills?.length) {
          this.userSkills = data.user_skills;
          this.userSkillsInput = data.user_skills.join(', ');
        }
        if (data.skill_levels && Object.keys(data.skill_levels).length) {
          this.skillLevels = data.skill_levels;
        }

        // 추가 데이터 저장
        this.parsedEmail = data.email || null;
        this.parsedPhone = data.phone || null;
        this.parsedLanguages = data.languages || [];
        this.parsedAwards = data.awards || [];
        this.parsedStrengths = data.strengths || [];
        this.parsedWorkExperience = data.work_experience || [];
        this.parsedKeyAchievements = data.key_achievements || [];
        this.parsedProjects = data.projects || [];
        this.parsedGithubUrl = data.github_url || null;
        this.parsedPortfolioUrl = data.portfolio_url || null;
        this.parsedTeamworkExperience = data.teamwork_experience || null;
        this.parsedGrowthStory = data.growth_story || null;

        this.documentParseSuccess = true;
      } catch (error) {
        console.error('서류 분석 실패:', error);
        this.errorMessage = error.response?.data?.error || '서류 분석 중 오류가 발생했습니다.';
      } finally {
        this.isParsingDocuments = false;
      }
    },

    async parseJobPosting() {
      this.isParsing = true;
      this.errorMessage = '';

      try {
        const requestData = { type: 'url', url: this.urlInput };
        const response = await axios.post('/api/core/job-planner/parse/', requestData);
        this.mergeJobData(response.data);

      } catch (error) {
        console.error('파싱 실패:', error);
        this.errorMessage = error.response?.data?.error || '공고 파싱 중 오류가 발생했습니다.';
      } finally {
        this.isParsing = false;

        if (this.jobData) {
          this.checkDataCompleteness();
          const gameStore = useGameStore();
          gameStore.setLastParsedJob(this.jobData);
          // 기업 URL이 있으면 기업분석 백그라운드 실행
          if (this.companyUrl) {
            this.analyzeCompany(this.companyUrl);
          }
        }
      }
    },

    checkDataCompleteness() {
      // 정보 충분도 평가
      const missing = [];
      let score = 0;
      const maxScore = 7;

      // 1. 회사명 (필수)
      if (this.jobData.company_name &&
          this.jobData.company_name !== '알 수 없음' &&
          this.jobData.company_name.trim() !== '') {
        score += 1;
      } else {
        missing.push('회사명');
      }

      // 2. 포지션 (필수)
      if (this.jobData.position &&
          this.jobData.position !== '개발자' &&
          this.jobData.position.trim() !== '') {
        score += 1;
      } else {
        missing.push('포지션');
      }

      // 3. 필수 스킬 (중요)
      if (this.jobData.required_skills && this.jobData.required_skills.length > 0) {
        score += 2;  // 가중치 높음
      } else {
        missing.push('필수 스킬');
      }

      // 4. 주요 업무
      if (this.jobData.job_responsibilities &&
          this.jobData.job_responsibilities.length > 20) {
        score += 1;
      } else {
        missing.push('주요 업무');
      }

      // 5. 필수 요건
      if (this.jobData.required_qualifications &&
          this.jobData.required_qualifications !== '정보 없음' &&
          this.jobData.required_qualifications.length > 10) {
        score += 1;
      } else {
        missing.push('필수 요건');
      }

      // 6. 우대 조건 (선택)
      if (this.jobData.preferred_qualifications &&
          this.jobData.preferred_qualifications !== '정보 없음' &&
          this.jobData.preferred_qualifications.length > 10) {
        score += 1;
      }

      const completenessRate = score / maxScore;

      this.dataCompleteness = {
        score: score,
        maxScore: maxScore,
        rate: completenessRate,
        level: completenessRate >= 0.7 ? 'good' : completenessRate >= 0.4 ? 'fair' : 'poor'
      };

      this.missingFields = missing;
      this.needsMoreInfo = completenessRate < 0.7;
    },

    handleSupplementImageUpload(event) {
      const files = Array.from(event.target.files);
      files.forEach(file => {
        this.supplementImages.push(file);
        const reader = new FileReader();
        reader.onload = (e) => {
          this.supplementImagePreviews.push(e.target.result);
        };
        reader.readAsDataURL(file);
      });
    },

    removeSupplementImage(index) {
      this.supplementImages.splice(index, 1);
      this.supplementImagePreviews.splice(index, 1);
    },

    async parseSupplementData() {
      this.isSupplementParsing = true;
      this.errorMessage = '';

      try {
        if (this.supplementMethod === 'image') {
          for (let i = 0; i < this.supplementImages.length; i++) {
            const file = this.supplementImages[i];
            const reader = new FileReader();
            const base64Promise = new Promise((resolve) => {
              reader.onload = (e) => resolve(e.target.result);
              reader.readAsDataURL(file);
            });
            const imageData = await base64Promise;
            const response = await axios.post('/api/core/job-planner/parse/', { type: 'image', image: imageData });
            this.mergeJobData(response.data);
          }
          // 업로드한 이미지 초기화
          this.supplementImages = [];
          this.supplementImagePreviews = [];
        } else if (this.supplementMethod === 'text') {
          const response = await axios.post('/api/core/job-planner/parse/', { type: 'text', text: this.supplementText });
          this.mergeJobData(response.data);
          this.supplementText = '';
        }
      } catch (error) {
        console.error('추가 파싱 실패:', error);
        this.errorMessage = error.response?.data?.error || '추가 분석 중 오류가 발생했습니다.';
      } finally {
        this.isSupplementParsing = false;
        if (this.jobData) {
          this.checkDataCompleteness();
        }
      }
    },

    mergeJobData(newData) {
      // 유효한 값인지 체크 (빈 값이나 기본값이 아닌지)
      const isValidValue = (value) => {
        if (!value) return false;
        if (typeof value === 'string') {
          const normalized = value.trim().toLowerCase();
          return normalized !== '' &&
                 normalized !== '알 수 없음' &&
                 normalized !== '정보 없음' &&
                 normalized !== 'unknown';
        }
        return true;
      };

      // 텍스트 필드 병합 함수 (중복 내용 체크)
      const mergeText = (oldText, newText) => {
        // 타입 체크 및 문자열 변환
        if (typeof oldText !== 'string') {
          oldText = oldText ? String(oldText) : '';
        }
        if (typeof newText !== 'string') {
          newText = newText ? String(newText) : '';
        }

        // 빈 값 체크
        if (!oldText || oldText.trim() === '') return newText || '';
        if (!newText || newText.trim() === '') return oldText;

        // 정확히 같은 내용이면 중복 추가 안함
        if (oldText.trim() === newText.trim()) return oldText;

        // 새로운 텍스트가 이미 포함되어 있으면 추가 안함
        if (oldText.includes(newText.trim())) return oldText;

        // 기존 텍스트가 새로운 텍스트에 포함되어 있으면 새로운 것으로 대체
        if (newText.includes(oldText.trim())) return newText;

        return `${oldText}\n\n${newText}`;
      };

      if (this.jobData) {
        this.jobData = {
          // 회사명과 포지션은 유효한 값일 때만 업데이트
          company_name: isValidValue(newData.company_name) ? newData.company_name : this.jobData.company_name,
          position: isValidValue(newData.position) ? newData.position : this.jobData.position,

          // 스킬 배열 병합 (중복 제거)
          required_skills: [...new Set([
            ...(this.jobData.required_skills || []),
            ...(newData.required_skills || [])
          ])],
          preferred_skills: [...new Set([
            ...(this.jobData.preferred_skills || []),
            ...(newData.preferred_skills || [])
          ])],

          // 텍스트 필드 병합 (중복 체크)
          job_responsibilities: mergeText(this.jobData.job_responsibilities, newData.job_responsibilities),
          required_qualifications: mergeText(this.jobData.required_qualifications, newData.required_qualifications),
          preferred_qualifications: mergeText(this.jobData.preferred_qualifications, newData.preferred_qualifications),

          experience_range: isValidValue(newData.experience_range) ? newData.experience_range : this.jobData.experience_range,
          deadline: newData.deadline || this.jobData.deadline,
          source: this.jobData.source.includes(newData.source) ? this.jobData.source : this.jobData.source + ' + ' + newData.source,
          raw_text: this.jobData.raw_text + '\n\n---\n\n' + newData.raw_text
        };
      } else {
        this.jobData = newData;
      }
    },

    async analyzeMatch() {
      this.isAnalyzing = true;
      this.errorMessage = '';

      try {
        // 스킬 레벨 기본값 설정 (입력 안한 스킬은 3으로)
        const completedSkillLevels = {};
        this.userSkills.forEach(skill => {
          completedSkillLevels[skill] = this.skillLevels[skill] || 3;
        });

        const response = await axios.post('/api/core/job-planner/analyze/', {
          // 기본 프로필
          user_skills: this.userSkills,
          skill_levels: completedSkillLevels,
          experience_years: this.experienceYears,

          // 상세 프로필
          name: this.name,
          current_role: this.currentRole,
          education: this.education,
          certifications: this.certifications,
          training: this.training,
          career_goals: this.careerGoals,
          available_prep_days: this.availablePrepDays,

          // 채용공고 정보
          required_skills: this.jobData.required_skills,
          preferred_skills: this.jobData.preferred_skills,
          experience_range: this.jobData.experience_range,

          // 필수/우대 요건 전체 텍스트 (추가 역량 추출용)
          required_qualifications: this.jobData.required_qualifications || '',
          preferred_qualifications: this.jobData.preferred_qualifications || '',
          job_responsibilities: this.jobData.job_responsibilities || ''
        });

        this.analysisResult = response.data;

        this.currentStep = 'result';
        this.fetchRecommendations();
        this.generateFinalReport();

      } catch (error) {
        console.error('분석 실패:', error);
        this.errorMessage = error.response?.data?.error || '분석 중 오류가 발생했습니다.';
      } finally {
        this.isAnalyzing = false;
      }
    },

    async generateFinalReport() {
      this.isGeneratingReport = true;
      this.errorMessage = '';

      try {
        const response = await axios.post('/api/core/job-planner/agent-report/', {
          job_data: this.jobData,
          analysis_result: this.analysisResult,
          company_analysis: this.companyAnalysis,
        });

        this.finalReport = response.data;

      } catch (error) {
        console.error('보고서 생성 실패:', error);
        this.errorMessage = error.response?.data?.error || '보고서 생성 중 오류가 발생했습니다.';
      } finally {
        this.isGeneratingReport = false;
      }
    },

    async fetchRecommendations() {
      this.isLoadingRecommendations = true;
      this.errorMessage = '';

      try {
        // 스킬 레벨 기본값 설정
        const completedSkillLevels = {};
        this.userSkills.forEach(skill => {
          completedSkillLevels[skill] = this.skillLevels[skill] || 3;
        });

        const response = await axios.post('/api/core/job-planner/recommend/', {
          user_skills: this.userSkills,
          skill_levels: completedSkillLevels,
          readiness_score: this.analysisResult.readiness_score,
          job_position: this.jobData?.position || '개발자',
          // 원래 공고 정보 (유사도 기준 + 검색 키워드)
          current_required_skills: this.jobData?.required_skills || [],
          current_required_qualifications: this.jobData?.required_qualifications || '',
          current_job_responsibilities: this.jobData?.job_responsibilities || '',
          // 현재 분석 중인 공고 정보 (중복 제거용)
          current_job_url: this.urlInput || '',
          current_job_company: this.jobData?.company_name || '',
          current_job_title: this.jobData?.position || ''
        });

        this.recommendations = response.data.recommendations || [];

      } catch (error) {
        console.error('추천 공고 로드 실패:', error);
        // 실패해도 에러 메시지 표시하지 않음 (선택 기능)
        this.recommendations = [];
      } finally {
        this.isLoadingRecommendations = false;
      }
    },

    async analyzeCompany(url) {
      this.isAnalyzingCompany = true;

      try {
        const response = await axios.post('/api/core/job-planner/company-analyze/', {
          type: 'url',
          url: url,
          company_name: this.jobData?.company_name || '회사'
        });
        this.companyAnalysis = response.data;

      } catch (error) {
        console.error('기업분석 실패:', error);
      } finally {
        this.isAnalyzingCompany = false;
      }
    },

    parseUserSkills() {
      this.userSkills = this.userSkillsInput
        .split(',')
        .map(s => s.trim())
        .filter(s => s.length > 0);

      // 새로 추가된 스킬에 기본 레벨 3 설정
      this.userSkills.forEach(skill => {
        if (!(skill in this.skillLevels)) {
          this.skillLevels[skill] = 3;
        }
      });
    },

    removeSkill(skill) {
      this.userSkills = this.userSkills.filter(s => s !== skill);
      this.userSkillsInput = this.userSkills.join(', ');
      delete this.skillLevels[skill];
    },

    addSkill() {
      const skill = this.newSkillInput.trim();
      if (!skill || this.userSkills.includes(skill)) return;
      this.userSkills.push(skill);
      this.skillLevels[skill] = 3;
      this.userSkillsInput = this.userSkills.join(', ');
      this.newSkillInput = '';
    },

    addTraining() {
      const name = this.newTrainingName.trim();
      if (!name) return;
      this.training.push({
        name,
        institution: this.newTrainingInstitution.trim() || null,
        period: this.newTrainingPeriod.trim() || null,
      });
      this.newTrainingName = '';
      this.newTrainingInstitution = '';
      this.newTrainingPeriod = '';
    },

    removeTraining(idx) {
      this.training.splice(idx, 1);
    },

    parseCertifications() {
      this.certifications = this.certificationsInput
        .split(',')
        .map(s => s.trim())
        .filter(s => s.length > 0);
    },

    getLevelLabel(level) {
      const labels = {
        1: '입문',
        2: '초급',
        3: '중급',
        4: '고급',
        5: '전문가'
      };
      return labels[level] || '중급';
    },

    getScoreClass(score) {
      if (score >= 0.8) return 'excellent';
      if (score >= 0.6) return 'good';
      if (score >= 0.4) return 'fair';
      return 'poor';
    },

    resetJobData() {
      this.urlInput = '';
      this.jobData = null;
      this.dataCompleteness = null;
      this.needsMoreInfo = false;
      this.missingFields = [];
      this.supplementMethod = 'image';
      this.supplementImages = [];
      this.supplementImagePreviews = [];
      this.supplementText = '';
      this.isSupplementParsing = false;
      this.analysisResult = null;
      this.finalReport = null;
      this.recommendations = [];
      this.errorMessage = '';
      this.currentStep = 'input';
    },

    async generateCoverLetterByQuestions() {
      this.isGeneratingCoverLetter = true;
      this.generatedCoverLetter = null;
      const questions = this.coverLetterQuestions
        .split('\n')
        .map(q => q.trim())
        .filter(q => q.length > 0);
      try {
        const response = await axios.post('/api/core/job-planner/generate-cover-letter-by-questions/', {
          user_profile: this.analysisResult?.profile_summary || {},
          job_data: this.jobData,
          company_analysis: this.companyAnalysis,
          questions,
        });
        this.generatedCoverLetter = response.data.answers;
      } catch (error) {
        this.errorMessage = error.response?.data?.error || '자기소개서 생성 중 오류가 발생했습니다.';
      } finally {
        this.isGeneratingCoverLetter = false;
      }
    },

    async reviewPortfolio() {
      this.isReviewingPortfolio = true;
      this.portfolioReview = null;
      try {
        const response = await axios.post('/api/core/job-planner/review-portfolio/', {
          user_profile: this.analysisResult?.profile_summary || {},
          job_data: this.jobData,
        });
        this.portfolioReview = response.data;
      } catch (error) {
        this.errorMessage = error.response?.data?.error || '포트폴리오 분석 중 오류가 발생했습니다.';
      } finally {
        this.isReviewingPortfolio = false;
      }
    },

    resetAll() {
      this.currentStep = 'input';
      this.urlInput = '';
      this.jobData = null;
      this.dataCompleteness = null;
      this.needsMoreInfo = false;
      this.missingFields = [];
      this.supplementMethod = 'image';
      this.supplementImages = [];
      this.supplementImagePreviews = [];
      this.supplementText = '';
      this.isSupplementParsing = false;

      // 서류 업로드 초기화
      this.resumePdf = null;
      this.coverLetterPdf = null;
      this.portfolioPdf = null;
      this.careerDescPdf = null;
      this.resumeFileName = '';
      this.coverLetterFileName = '';
      this.portfolioFileName = '';
      this.careerDescFileName = '';
      this.isParsingDocuments = false;
      this.documentParseSuccess = false;
      this.parsedEmail = null;
      this.parsedPhone = null;
      this.parsedLanguages = [];
      this.parsedAwards = [];
      this.parsedStrengths = [];
      this.parsedWorkExperience = [];
      this.parsedKeyAchievements = [];
      this.parsedProjects = [];
      this.parsedGithubUrl = null;
      this.parsedPortfolioUrl = null;
      this.parsedTeamworkExperience = null;
      this.parsedGrowthStory = null;

      // 프로필 초기화
      this.name = '';
      this.currentRole = '';
      this.experienceYears = 0;
      this.userSkills = [];
      this.userSkillsInput = '';
      this.skillLevels = {};
      this.education = '';
      this.certifications = [];
      this.certificationsInput = '';
      this.training = [];
      this.careerGoals = '';
      this.availablePrepDays = null;

      // 기업분석 초기화
      this.companyUrl = '';
      this.companyAnalysis = null;

      // 결과 초기화
      this.analysisResult = null;
      this.finalReport = null;
      this.recommendations = [];
      this.coverLetterQuestions = '';
      this.generatedCoverLetter = null;
      this.portfolioReview = null;
      this.isGeneratingCoverLetter = false;
      this.isReviewingPortfolio = false;
      this.errorMessage = '';
    }
  }
};
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  backdrop-filter: blur(4px);
}

.job-planner-modal {
  background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
  border-radius: 16px;
  width: 90%;
  max-width: 900px;
  max-height: 90vh;
  overflow: hidden;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
  border: 1px solid rgba(148, 163, 184, 0.2);
  display: flex;
  flex-direction: column;
}

.modal-header {
  padding: 24px 32px;
  background: linear-gradient(135deg, #334155 0%, #1e293b 100%);
  border-bottom: 1px solid rgba(148, 163, 184, 0.2);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.title-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.planner-badge {
  font-size: 12px;
  font-weight: 600;
  color: #60a5fa;
  letter-spacing: 1px;
}

.modal-title {
  font-size: 24px;
  font-weight: 700;
  color: #f1f5f9;
  margin: 0;
}

.close-btn {
  background: none;
  border: none;
  font-size: 32px;
  color: #94a3b8;
  cursor: pointer;
  transition: color 0.2s;
}

.close-btn:hover {
  color: #f1f5f9;
}

.flow-tabs {
  display: flex;
  gap: 0;
  padding: 0 32px;
  background: #0f172a;
  border-bottom: 1px solid rgba(148, 163, 184, 0.2);
}

.flow-tab {
  flex: 1;
  padding: 16px 24px;
  background: none;
  border: none;
  color: #64748b;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  position: relative;
  transition: all 0.3s;
}

.flow-tab:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.flow-tab.active {
  color: #60a5fa;
}

.flow-tab.active::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: #60a5fa;
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 32px;
}

.step-title {
  font-size: 20px;
  font-weight: 700;
  color: #f1f5f9;
  margin: 0 0 24px 0;
}

.input-method-tabs {
  display: flex;
  gap: 12px;
  margin-bottom: 24px;
}

.method-tab {
  flex: 1;
  padding: 12px 16px;
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 8px;
  color: #cbd5e1;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.method-tab.active {
  background: rgba(59, 130, 246, 0.2);
  border-color: #60a5fa;
  color: #60a5fa;
}

.input-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.input-panel label {
  font-size: 14px;
  font-weight: 600;
  color: #cbd5e1;
}

.url-input,
.text-input {
  padding: 12px 16px;
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(148, 163, 184, 0.3);
  border-radius: 8px;
  color: #f1f5f9;
  font-size: 14px;
  font-family: inherit;
  transition: all 0.2s;
}

.url-input:focus,
.text-input:focus {
  outline: none;
  border-color: #60a5fa;
  box-shadow: 0 0 0 3px rgba(96, 165, 250, 0.1);
}

.text-input {
  resize: vertical;
  line-height: 1.6;
}

.input-hint {
  font-size: 13px;
  color: #64748b;
  margin: -8px 0 0 0;
}

.image-upload-area {
  min-height: 300px;
  background: rgba(15, 23, 42, 0.6);
  border: 2px dashed rgba(148, 163, 184, 0.3);
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
}

.image-upload-area:hover {
  border-color: #60a5fa;
  background: rgba(59, 130, 246, 0.05);
}

.upload-placeholder {
  text-align: center;
}

.upload-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.upload-placeholder p {
  color: #cbd5e1;
  margin: 8px 0;
}

.upload-hint {
  font-size: 13px;
  color: #64748b;
}

.image-previews-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 12px;
  width: 100%;
  padding: 8px;
}

.image-preview-item {
  position: relative;
  aspect-ratio: 1;
  border-radius: 8px;
  overflow: hidden;
  border: 2px solid #e5e7eb;
  background: #f9fafb;
}

.image-preview-item img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.image-number {
  position: absolute;
  bottom: 8px;
  left: 8px;
  background: rgba(59, 130, 246, 0.9);
  color: white;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
}

.image-preview {
  width: 100%;
  height: 100%;
  position: relative;
}

.image-preview img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  border-radius: 8px;
}

.btn-remove-image {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 32px;
  height: 32px;
  background: rgba(239, 68, 68, 0.9);
  border: none;
  border-radius: 50%;
  color: white;
  font-size: 20px;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-remove-image:hover {
  background: #ef4444;
  transform: scale(1.1);
}

.job-preview-actions {
  display: flex;
  gap: 12px;
  margin-top: 16px;
}

.step-next-row {
  margin-top: 16px;
}

.step-next-row .btn-next {
  width: 100%;
}

.parsing-background-notice {
  margin-bottom: 16px;
  padding: 12px 16px;
  background: rgba(251, 191, 36, 0.1);
  border: 1px solid rgba(251, 191, 36, 0.3);
  border-radius: 8px;
  color: #fbbf24;
  font-size: 14px;
}

.btn-reset-job {
  padding: 14px 24px;
  background: transparent;
  border: 2px solid #6b7280;
  border-radius: 10px;
  color: #9ca3af;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s;
}

.btn-reset-job:hover {
  border-color: #ef4444;
  color: #ef4444;
  transform: translateY(-2px);
}

.btn-parse,
.btn-analyze,
.btn-next,
.btn-restart {
  padding: 14px 32px;
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  border: none;
  border-radius: 10px;
  color: white;
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.3s;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
}

.btn-parse:hover:not(:disabled),
.btn-analyze:hover:not(:disabled),
.btn-next:hover,
.btn-restart:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(59, 130, 246, 0.5);
}

.btn-parse:disabled,
.btn-analyze:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.job-preview {
  margin-top: 32px;
  padding: 24px;
  background: rgba(34, 197, 94, 0.1);
  border: 1px solid rgba(34, 197, 94, 0.3);
  border-radius: 12px;
}

.job-preview h4 {
  font-size: 16px;
  font-weight: 700;
  color: #22c55e;
  margin: 0 0 16px 0;
}

.preview-grid {
  display: grid;
  gap: 12px;
  margin-bottom: 20px;
}

.preview-item {
  display: flex;
  gap: 12px;
}

.preview-label {
  font-weight: 600;
  color: #94a3b8;
  min-width: 80px;
}

.preview-value {
  color: #f1f5f9;
}

/* 새로운 상세 정보 섹션 */
.preview-detail-section {
  margin-top: 20px;
  padding: 16px;
  background: rgba(30, 41, 59, 0.5);
  border-radius: 8px;
  border-left: 3px solid rgba(59, 130, 246, 0.5);
}

.preview-detail-title {
  font-size: 14px;
  font-weight: 600;
  color: #60a5fa;
  margin-bottom: 8px;
}

.preview-detail-content {
  color: #e2e8f0;
  font-size: 14px;
  line-height: 1.6;
  white-space: pre-wrap;
}

.preview-skill-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 12px;
}

.skill-tag {
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
}

.skill-tag.required {
  background: rgba(239, 68, 68, 0.2);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: #fca5a5;
}

.skill-tag.preferred {
  background: rgba(59, 130, 246, 0.2);
  border: 1px solid rgba(59, 130, 246, 0.3);
  color: #93c5fd;
}

/* 정보 충분도 인디케이터 */
.completeness-indicator {
  margin-top: 24px;
  padding: 16px;
  background: rgba(30, 41, 59, 0.6);
  border-radius: 12px;
  border: 1px solid rgba(148, 163, 184, 0.2);
}

.completeness-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.completeness-icon {
  font-size: 20px;
}

.completeness-title {
  font-size: 14px;
  font-weight: 600;
  color: #cbd5e1;
  flex: 1;
}

.completeness-score {
  font-size: 16px;
  font-weight: 700;
  color: #60a5fa;
}

.completeness-bar {
  width: 100%;
  height: 8px;
  background: rgba(30, 41, 59, 0.8);
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 12px;
}

.completeness-fill {
  height: 100%;
  transition: width 0.5s ease;
  border-radius: 4px;
}

.completeness-fill.good {
  background: linear-gradient(90deg, #10b981 0%, #34d399 100%);
}

.completeness-fill.fair {
  background: linear-gradient(90deg, #f59e0b 0%, #fbbf24 100%);
}

.completeness-fill.poor {
  background: linear-gradient(90deg, #ef4444 0%, #f87171 100%);
}

.completeness-warning {
  padding: 12px;
  background: rgba(245, 158, 11, 0.1);
  border-left: 3px solid #f59e0b;
  border-radius: 6px;
}

.warning-text {
  font-size: 13px;
  color: #fbbf24;
  margin-bottom: 6px;
}

.warning-text strong {
  color: #fcd34d;
}

.supplement-input-section {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.supplement-title {
  font-size: 12px;
  color: #cbd5e1;
  margin-bottom: 10px;
}

.supplement-method-tabs {
  display: flex;
  gap: 6px;
  margin-bottom: 10px;
}

.supp-tab {
  padding: 6px 14px;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: transparent;
  color: #94a3b8;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.supp-tab.active {
  background: rgba(99, 102, 241, 0.25);
  border-color: #6366f1;
  color: #a5b4fc;
}

.supplement-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.supplement-upload-area {
  border: 2px dashed rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  padding: 16px;
  cursor: pointer;
  min-height: 80px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: border-color 0.2s;
}

.supplement-upload-area:hover {
  border-color: #6366f1;
}

.supplement-textarea {
  width: 100%;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 8px;
  color: #e2e8f0;
  font-size: 13px;
  padding: 10px;
  resize: vertical;
  box-sizing: border-box;
}

.supplement-textarea::placeholder {
  color: #64748b;
}

.btn-supplement-parse {
  padding: 8px 16px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.2s;
  align-self: flex-start;
}

.btn-supplement-parse:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.completeness-success {
  padding: 12px;
  background: rgba(16, 185, 129, 0.1);
  border-left: 3px solid #10b981;
  border-radius: 6px;
  font-size: 13px;
  color: #34d399;
}

.profile-form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.form-row {
  display: flex;
  gap: 16px;
}

.form-group {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-group label {
  font-size: 13px;
  font-weight: 600;
  color: #cbd5e1;
}

.form-group input {
  padding: 12px 16px;
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(148, 163, 184, 0.3);
  border-radius: 8px;
  color: #f1f5f9;
  font-size: 14px;
  transition: all 0.2s;
}

.form-group input:focus {
  outline: none;
  border-color: #60a5fa;
  box-shadow: 0 0 0 3px rgba(96, 165, 250, 0.1);
}

.score-overview {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 32px;
}

.score-card {
  padding: 24px;
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 12px;
  text-align: center;
}

.score-label {
  font-size: 13px;
  font-weight: 600;
  color: #94a3b8;
  margin-bottom: 8px;
}

.score-value {
  font-size: 32px;
  font-weight: 700;
}

.score-value.excellent {
  color: #22c55e;
}

.score-value.good {
  color: #3b82f6;
}

.score-value.fair {
  color: #f59e0b;
}

.score-value.poor {
  color: #ef4444;
}

.skill-section {
  margin-bottom: 24px;
}

.section-subtitle {
  font-size: 16px;
  font-weight: 700;
  color: #f1f5f9;
  margin: 0 0 12px 0;
}

.skill-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.skill-item {
  padding: 12px 16px;
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 8px;
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 14px;
}

.skill-list.matched .skill-item {
  border-left: 3px solid #22c55e;
}

.skill-list.missing .skill-item {
  border-left: 3px solid #ef4444;
}

.skill-required {
  font-weight: 700;
  color: #f1f5f9;
  flex: 1;
}

.skill-arrow {
  color: #64748b;
}

.skill-user,
.skill-closest {
  color: #cbd5e1;
  flex: 1;
}

.skill-similarity {
  padding: 4px 12px;
  background: rgba(34, 197, 94, 0.2);
  border-radius: 6px;
  color: #22c55e;
  font-weight: 600;
  font-size: 12px;
}

.skill-similarity.weak {
  background: rgba(239, 68, 68, 0.2);
  color: #ef4444;
}

.error-banner {
  padding: 16px;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 8px;
  color: #fca5a5;
  text-align: center;
  margin-top: 16px;
}

/* Profile Form Styles */
.form-section {
  margin-bottom: 32px;
  padding: 24px;
  background: rgba(15, 23, 42, 0.4);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 12px;
}

.document-upload-section {
  border-color: rgba(99, 102, 241, 0.4);
  background: rgba(99, 102, 241, 0.05);
}

.document-upload-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}

.upload-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}

.upload-row {
  display: flex;
  align-items: stretch;
  gap: 6px;
  min-width: 0;
}

.upload-row .upload-btn {
  flex: 1;
  min-width: 0;
}

.upload-clear-btn {
  flex-shrink: 0;
  width: 28px;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 6px;
  color: #f87171;
  font-size: 16px;
  cursor: pointer;
  transition: all 0.2s;
  line-height: 1;
}

.upload-clear-btn:hover {
  background: rgba(239, 68, 68, 0.25);
  border-color: #f87171;
}

.upload-label {
  font-size: 13px;
  color: #94a3b8;
  font-weight: 600;
}

.upload-btn {
  display: block;
  width: 100%;
  box-sizing: border-box;
  padding: 12px 8px;
  background: rgba(15, 23, 42, 0.6);
  border: 2px dashed rgba(148, 163, 184, 0.3);
  border-radius: 8px;
  color: #94a3b8;
  font-size: 13px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}

.upload-btn:hover {
  border-color: rgba(99, 102, 241, 0.6);
  color: #a5b4fc;
}

.upload-btn.uploaded {
  border-color: rgba(34, 197, 94, 0.6);
  color: #86efac;
  background: rgba(34, 197, 94, 0.05);
}

.btn-parse-resume {
  width: 100%;
  padding: 12px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.2s;
}

.btn-parse-resume:hover:not(:disabled) {
  opacity: 0.9;
}

.btn-parse-resume:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.parse-success-msg {
  margin-top: 12px;
  padding: 10px 14px;
  background: rgba(34, 197, 94, 0.1);
  border: 1px solid rgba(34, 197, 94, 0.3);
  border-radius: 8px;
  color: #86efac;
  font-size: 13px;
}

.form-section-title {
  font-size: 16px;
  font-weight: 700;
  color: #f1f5f9;
  margin: 0 0 20px 0;
}

.form-row {
  margin-bottom: 20px;
}

.form-row-2col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 20px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-group label {
  font-size: 14px;
  font-weight: 600;
  color: #cbd5e1;
}

.form-group input,
.form-group textarea {
  padding: 12px 16px;
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(148, 163, 184, 0.3);
  border-radius: 8px;
  color: #f1f5f9;
  font-size: 14px;
  font-family: inherit;
  transition: all 0.2s;
}

.form-group input:focus,
.form-group textarea:focus {
  outline: none;
  border-color: #60a5fa;
  box-shadow: 0 0 0 3px rgba(96, 165, 250, 0.1);
}

.form-group textarea {
  resize: vertical;
  line-height: 1.6;
}

.required {
  color: #ef4444;
}

.optional {
  color: #64748b;
  font-weight: 400;
  font-size: 12px;
}

/* Skill Levels */
.skill-levels-container {
  margin-top: 16px;
  padding: 16px;
  background: rgba(59, 130, 246, 0.05);
  border: 1px solid rgba(96, 165, 250, 0.2);
  border-radius: 8px;
}

.skill-level-item {
  display: grid;
  grid-template-columns: 150px 1fr auto auto;
  align-items: center;
  gap: 16px;
  padding: 12px 0;
  border-bottom: 1px solid rgba(148, 163, 184, 0.1);
}

.skill-delete-btn {
  width: 28px;
  height: 28px;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 6px;
  color: #f87171;
  font-size: 16px;
  cursor: pointer;
  line-height: 1;
  transition: all 0.2s;
}

.skill-delete-btn:hover {
  background: rgba(239, 68, 68, 0.25);
  border-color: #f87171;
}

.skill-add-row {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}

.skill-add-row input {
  flex: 1;
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 8px;
  color: #f1f5f9;
  padding: 8px 12px;
  font-size: 14px;
}

.skill-add-row input:focus {
  outline: none;
  border-color: #60a5fa;
}

.skill-add-btn {
  padding: 8px 16px;
  background: rgba(59, 130, 246, 0.15);
  border: 1px solid rgba(59, 130, 246, 0.4);
  border-radius: 8px;
  color: #60a5fa;
  font-size: 14px;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.2s;
}

.skill-add-btn:hover {
  background: rgba(59, 130, 246, 0.3);
}

.training-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 8px;
}

.training-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: rgba(15, 23, 42, 0.5);
  border: 1px solid rgba(148, 163, 184, 0.15);
  border-radius: 8px;
}

.training-name {
  font-weight: 600;
  color: #f1f5f9;
  font-size: 14px;
}

.training-meta {
  font-size: 12px;
  color: #94a3b8;
}

.training-meta + .training-meta::before {
  content: '·';
  margin-right: 4px;
}

.training-delete-btn {
  margin-left: auto;
  width: 24px;
  height: 24px;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 4px;
  color: #f87171;
  font-size: 14px;
  cursor: pointer;
  line-height: 1;
  transition: all 0.2s;
  flex-shrink: 0;
}

.training-delete-btn:hover {
  background: rgba(239, 68, 68, 0.25);
}

.training-add-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.training-add-row input {
  flex: 1;
  min-width: 120px;
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 8px;
  color: #f1f5f9;
  padding: 8px 12px;
  font-size: 14px;
}

.training-add-row input:focus {
  outline: none;
  border-color: #60a5fa;
}

.skill-level-item:last-child {
  border-bottom: none;
}

.skill-name {
  font-weight: 600;
  color: #f1f5f9;
}

.skill-level-selector {
  display: flex;
  gap: 8px;
}

.level-btn {
  width: 40px;
  height: 40px;
  background: rgba(15, 23, 42, 0.6);
  border: 2px solid rgba(148, 163, 184, 0.2);
  border-radius: 8px;
  color: #cbd5e1;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.2s;
}

.level-btn:hover {
  border-color: #60a5fa;
  background: rgba(59, 130, 246, 0.1);
}

.level-btn.active {
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  border-color: #60a5fa;
  color: white;
  transform: scale(1.1);
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
}

.skill-level-label {
  font-size: 13px;
  color: #94a3b8;
  min-width: 60px;
  text-align: right;
}

.level-guide {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid rgba(148, 163, 184, 0.1);
  font-size: 12px;
  color: #64748b;
  text-align: center;
}

/* Insights */
.insights-section {
  margin-bottom: 24px;
}

.insights-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.insight-item {
  padding: 16px;
  border-radius: 8px;
  border-left: 4px solid;
}

.insight-item.positive {
  background: rgba(34, 197, 94, 0.1);
  border-color: #22c55e;
}

.insight-item.warning {
  background: rgba(245, 158, 11, 0.1);
  border-color: #f59e0b;
}

.insight-item.neutral {
  background: rgba(59, 130, 246, 0.1);
  border-color: #3b82f6;
}

.insight-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.insight-icon {
  font-size: 16px;
}

.insight-title {
  font-weight: 700;
  color: #f1f5f9;
  font-size: 14px;
}

.insight-message {
  color: #cbd5e1;
  font-size: 13px;
  line-height: 1.6;
  margin-left: 24px;
}

/* Company Analysis Styles */
.company-analysis-section {
  margin-top: 32px;
  padding-top: 32px;
  border-top: 1px solid rgba(148, 163, 184, 0.2);
}

.section-hint {
  font-size: 13px;
  color: #94a3b8;
  margin: -8px 0 16px 0;
}

.company-input-tabs {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.company-tab {
  flex: 1;
  padding: 10px 16px;
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 6px;
  color: #cbd5e1;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.company-tab.active {
  background: rgba(139, 92, 246, 0.2);
  border-color: #a78bfa;
  color: #a78bfa;
}

.company-input-panel {
  margin-bottom: 16px;
}

.company-input,
.company-textarea {
  width: 100%;
  padding: 12px 16px;
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(148, 163, 184, 0.3);
  border-radius: 8px;
  color: #f1f5f9;
  font-size: 14px;
  font-family: inherit;
  transition: all 0.2s;
}

.company-input:focus,
.company-textarea:focus {
  outline: none;
  border-color: #a78bfa;
  box-shadow: 0 0 0 3px rgba(167, 139, 250, 0.1);
}

.company-textarea {
  resize: vertical;
  line-height: 1.6;
}

.btn-company-analyze {
  padding: 12px 24px;
  background: linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%);
  border: none;
  border-radius: 8px;
  color: white;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.3s;
  box-shadow: 0 4px 12px rgba(139, 92, 246, 0.3);
}

.btn-company-analyze:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(139, 92, 246, 0.4);
}

.btn-company-analyze:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.company-analysis-preview {
  margin-top: 16px;
  padding: 12px 16px;
  background: rgba(139, 92, 246, 0.1);
  border: 1px solid rgba(167, 139, 250, 0.3);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.preview-badge {
  font-size: 14px;
  font-weight: 600;
  color: #a78bfa;
}

.preview-score {
  font-size: 14px;
  font-weight: 700;
  color: #f1f5f9;
}

.company-analysis-results {
  margin-top: 32px;
  padding-top: 32px;
  border-top: 2px solid rgba(139, 92, 246, 0.3);
}

.analysis-title {
  font-size: 20px;
  font-weight: 700;
  color: #f1f5f9;
  margin: 0 0 24px 0;
}

.company-score-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 32px;
}

.company-score-card {
  padding: 16px;
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 12px;
}

.company-score-card .score-label {
  font-size: 14px;
  color: #94a3b8;
  margin-bottom: 8px;
}

.score-bar {
  height: 8px;
  background: rgba(100, 116, 139, 0.3);
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 8px;
}

.score-fill {
  height: 100%;
  background: linear-gradient(90deg, #8b5cf6 0%, #a78bfa 100%);
  transition: width 0.6s ease;
}

.score-text {
  font-size: 16px;
  font-weight: 700;
  color: #a78bfa;
}

.analysis-section {
  margin-bottom: 24px;
  padding: 20px;
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 12px;
}

.analysis-content {
  color: #cbd5e1;
  line-height: 1.7;
}

.analysis-content p {
  margin: 0 0 12px 0;
}

.info-grid,
.growth-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
  margin: 16px 0;
}

.info-item,
.growth-item,
.welfare-item {
  margin-bottom: 8px;
}

.info-label,
.growth-label {
  font-weight: 600;
  color: #94a3b8;
  margin-right: 8px;
}

.info-value,
.growth-value {
  color: #f1f5f9;
}

.vision-text {
  padding: 12px;
  background: rgba(139, 92, 246, 0.1);
  border-left: 3px solid #a78bfa;
  border-radius: 6px;
  margin-top: 12px;
}

.tech-tags {
  margin-bottom: 16px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.tag-label {
  font-weight: 600;
  color: #94a3b8;
}

.tech-tag {
  padding: 6px 12px;
  background: rgba(59, 130, 246, 0.2);
  border: 1px solid rgba(96, 165, 250, 0.3);
  border-radius: 6px;
  color: #60a5fa;
  font-size: 13px;
  font-weight: 600;
}

.tech-blog-info {
  padding: 10px;
  background: rgba(59, 130, 246, 0.1);
  border-radius: 6px;
  font-size: 13px;
  color: #93c5fd;
}

.tech-blog-link {
  color: #60a5fa;
  text-decoration: underline;
  word-break: break-all;
}

.tech-blog-link:hover {
  color: #93c5fd;
}

.growth-badge {
  padding: 4px 12px;
  background: rgba(100, 116, 139, 0.3);
  border-radius: 6px;
  font-weight: 600;
  font-size: 13px;
  color: #cbd5e1;
}

.growth-badge.상 {
  background: rgba(34, 197, 94, 0.2);
  color: #22c55e;
}

.growth-badge.중 {
  background: rgba(59, 130, 246, 0.2);
  color: #60a5fa;
}

.growth-badge.하 {
  background: rgba(239, 68, 68, 0.2);
  color: #ef4444;
}

.benefits-list {
  margin: 8px 0;
  padding-left: 24px;
  color: #cbd5e1;
}

.benefits-list li {
  margin: 4px 0;
}

.recommendation-section {
  background: rgba(139, 92, 246, 0.1);
  border: 1px solid rgba(167, 139, 250, 0.3);
}

.recommendation-content {
  font-size: 15px;
  line-height: 1.8;
  color: #f1f5f9;
  font-weight: 500;
}

/* Final Report Styles */
.final-report-section {
  margin-top: 48px;
  padding-top: 48px;
  border-top: 3px solid rgba(16, 185, 129, 0.3);
}

.report-title {
  font-size: 24px;
  font-weight: 700;
  color: #10b981;
  margin: 0 0 32px 0;
  text-align: center;
}

/* SWOT */
.swot-section {
  margin-bottom: 40px;
}

.swot-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.swot-card {
  padding: 20px;
  border-radius: 12px;
  border: 2px solid;
}

.swot-card.strengths {
  background: rgba(34, 197, 94, 0.1);
  border-color: #22c55e;
}

.swot-card.weaknesses {
  background: rgba(239, 68, 68, 0.1);
  border-color: #ef4444;
}

.swot-card.opportunities {
  background: rgba(59, 130, 246, 0.1);
  border-color: #3b82f6;
}

.swot-card.threats {
  background: rgba(245, 158, 11, 0.1);
  border-color: #f59e0b;
}

.swot-header {
  font-size: 16px;
  font-weight: 700;
  margin-bottom: 12px;
}

.swot-card.strengths .swot-header {
  color: #22c55e;
}

.swot-card.weaknesses .swot-header {
  color: #ef4444;
}

.swot-card.opportunities .swot-header {
  color: #3b82f6;
}

.swot-card.threats .swot-header {
  color: #f59e0b;
}

.swot-list {
  margin: 0;
  padding-left: 20px;
  color: #cbd5e1;
}

.swot-list li {
  margin: 8px 0;
  line-height: 1.6;
}

/* Interview Questions */
.interview-section {
  margin-bottom: 40px;
}

.interview-questions-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.interview-question-card {
  padding: 20px;
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 12px;
  display: flex;
  gap: 16px;
}

.question-number-badge {
  flex-shrink: 0;
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%);
  border-radius: 12px;
  color: white;
  font-weight: 700;
  font-size: 16px;
}

.question-content {
  flex: 1;
}

.question-title {
  font-size: 16px;
  font-weight: 700;
  color: #f1f5f9;
  margin-bottom: 12px;
}

.answer-guide {
  font-size: 14px;
  color: #cbd5e1;
  line-height: 1.7;
  margin-bottom: 8px;
  padding: 12px;
  background: rgba(139, 92, 246, 0.1);
  border-radius: 8px;
}

.tips {
  font-size: 13px;
  color: #a78bfa;
  line-height: 1.6;
  padding: 8px 12px;
  background: rgba(167, 139, 250, 0.1);
  border-radius: 6px;
}

/* Experience Packaging */
.packaging-section {
  margin-bottom: 40px;
}

.packaging-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.packaging-card {
  padding: 20px;
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 12px;
}

.packaging-title {
  font-size: 15px;
  font-weight: 700;
  color: #60a5fa;
  margin-bottom: 12px;
}

.packaging-list {
  margin: 0;
  padding-left: 20px;
  color: #cbd5e1;
}

.packaging-list li {
  margin: 8px 0;
  line-height: 1.6;
  font-size: 14px;
}

/* Execution Strategy */
.execution-section {
  margin-bottom: 40px;
}

.timeline {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.timeline-item {
  padding: 20px;
  border-radius: 12px;
  border-left: 4px solid;
  display: flex;
  gap: 16px;
}

.timeline-item.immediate {
  background: rgba(239, 68, 68, 0.1);
  border-color: #ef4444;
}

.timeline-item.short-term {
  background: rgba(245, 158, 11, 0.1);
  border-color: #f59e0b;
}

.timeline-item.mid-term {
  background: rgba(59, 130, 246, 0.1);
  border-color: #3b82f6;
}

.timeline-item.application {
  background: rgba(34, 197, 94, 0.1);
  border-color: #22c55e;
}

.timeline-badge {
  flex-shrink: 0;
  padding: 8px 16px;
  border-radius: 8px;
  color: white;
  font-weight: 700;
  font-size: 14px;
  height: fit-content;
}

.timeline-item.immediate .timeline-badge {
  background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
}

.timeline-item.short-term .timeline-badge {
  background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
}

.timeline-item.mid-term .timeline-badge {
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
}

.timeline-item.application .timeline-badge {
  background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
}

.timeline-content {
  flex: 1;
}

.timeline-list {
  margin: 0;
  padding-left: 20px;
  color: #cbd5e1;
}

.timeline-list li {
  margin: 8px 0;
  line-height: 1.6;
  font-size: 14px;
}

.application-timing {
  margin: 0;
  color: #f1f5f9;
  font-size: 15px;
  line-height: 1.7;
  font-weight: 500;
}

/* Final Message */
.final-message-section {
  margin-bottom: 32px;
}

.final-message {
  padding: 24px;
  background: linear-gradient(135deg, rgba(16, 185, 129, 0.2) 0%, rgba(5, 150, 105, 0.1) 100%);
  border: 2px solid #10b981;
  border-radius: 16px;
  color: #f1f5f9;
  font-size: 16px;
  line-height: 1.8;
  text-align: center;
  font-weight: 500;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* Recommendations Section */
.recommendations-section {
  margin: 32px 0;
  padding: 24px;
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.15) 0%, rgba(37, 99, 235, 0.05) 100%);
  border: 2px solid rgba(59, 130, 246, 0.3);
  border-radius: 16px;
}

.recommendations-title {
  font-size: 24px;
  font-weight: 700;
  color: #60a5fa;
  margin-bottom: 8px;
}

.recommendations-subtitle {
  color: #cbd5e1;
  font-size: 14px;
  margin-bottom: 20px;
}

.recommendations-list {
  display: grid;
  gap: 16px;
  max-height: 600px;
  overflow-y: auto;
  padding-right: 8px;
}

.recommendations-list::-webkit-scrollbar {
  width: 6px;
}

.recommendations-list::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 10px;
}

.recommendations-list::-webkit-scrollbar-thumb {
  background: rgba(59, 130, 246, 0.5);
  border-radius: 10px;
}

.recommendation-card {
  background: rgba(30, 41, 59, 0.6);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 12px;
  padding: 20px;
  transition: all 0.3s ease;
}

.recommendation-card:hover {
  border-color: rgba(59, 130, 246, 0.5);
  transform: translateY(-2px);
  box-shadow: 0 8px 16px rgba(59, 130, 246, 0.15);
}

.rec-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
  gap: 16px;
}

.rec-main-info {
  flex: 1;
}

.rec-title {
  font-size: 18px;
  font-weight: 600;
  color: #f1f5f9;
  margin: 0 0 8px 0;
  line-height: 1.4;
}

.rec-company {
  color: #94a3b8;
  font-size: 14px;
}

.rec-match {
  text-align: center;
  min-width: 80px;
}

.rec-match-rate {
  font-size: 28px;
  font-weight: 700;
  margin-bottom: 4px;
}

.rec-match-rate.excellent {
  color: #10b981;
}

.rec-match-rate.good {
  color: #3b82f6;
}

.rec-match-rate.fair {
  color: #f59e0b;
}

.rec-match-rate.poor {
  color: #ef4444;
}

.rec-match-label {
  color: #94a3b8;
  font-size: 12px;
}

.rec-details {
  display: grid;
  gap: 8px;
  margin-bottom: 12px;
}

.rec-info-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
}

.rec-label {
  color: #94a3b8;
  min-width: 80px;
}

.rec-value {
  color: #cbd5e1;
}

.rec-reason {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 12px;
  background: rgba(59, 130, 246, 0.1);
  border-left: 3px solid #3b82f6;
  border-radius: 8px;
  margin-bottom: 12px;
}

.rec-reason-icon {
  font-size: 18px;
  flex-shrink: 0;
}

.rec-reason-text {
  color: #e2e8f0;
  font-size: 14px;
  line-height: 1.6;
}

.rec-skills {
  margin-bottom: 16px;
}

.rec-skill-label {
  display: block;
  color: #94a3b8;
  font-size: 12px;
  margin-bottom: 8px;
  font-weight: 500;
}

.rec-skill-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.rec-skill-tag {
  padding: 4px 12px;
  background: rgba(59, 130, 246, 0.2);
  border: 1px solid rgba(59, 130, 246, 0.3);
  border-radius: 12px;
  color: #93c5fd;
  font-size: 12px;
  font-weight: 500;
}

.rec-skill-more {
  padding: 4px 12px;
  background: rgba(148, 163, 184, 0.2);
  border-radius: 12px;
  color: #cbd5e1;
  font-size: 12px;
}

.rec-link {
  display: inline-block;
  padding: 10px 20px;
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  color: white;
  text-decoration: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  transition: all 0.3s ease;
}

.rec-link:hover {
  background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
  transform: translateX(4px);
}

.loading-recommendations {
  padding: 40px;
  text-align: center;
  color: #94a3b8;
}

.loading-spinner {
  width: 40px;
  height: 40px;
  margin: 0 auto 16px;
  border: 4px solid rgba(59, 130, 246, 0.2);
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* AI 지원 도구 섹션 */
.action-tools-section {
  margin-top: 32px;
  padding: 24px;
  background: rgba(139, 92, 246, 0.08);
  border: 1px solid rgba(139, 92, 246, 0.25);
  border-radius: 12px;
}

.action-tools-title {
  font-size: 18px;
  font-weight: 700;
  color: #a78bfa;
  margin: 0 0 16px 0;
}

.action-tools-buttons {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 20px;
}

.btn-tool {
  padding: 10px 20px;
  background: linear-gradient(135deg, #7c3aed, #6d28d9);
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-tool:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(124, 58, 237, 0.45);
}

.btn-tool:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

/* 자기소개서 문항 입력 */
.cover-letter-questions-section {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid rgba(139, 92, 246, 0.2);
}

.questions-hint {
  font-size: 12px;
  color: #94a3b8;
  margin: 6px 0 10px;
}

.questions-textarea {
  width: 100%;
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(139, 92, 246, 0.3);
  border-radius: 8px;
  color: #e2e8f0;
  font-size: 13px;
  padding: 10px 12px;
  resize: vertical;
  margin-bottom: 10px;
  font-family: inherit;
  line-height: 1.6;
}

.questions-textarea:focus {
  outline: none;
  border-color: #7c3aed;
}

/* 자기소개서 결과 */
.cover-letter-result {
  margin-top: 20px;
}

.result-subtitle {
  font-size: 15px;
  font-weight: 700;
  color: #c4b5fd;
  margin: 0 0 12px 0;
}

.cover-letter-item {
  margin-bottom: 20px;
}

.cl-question {
  font-size: 13px;
  font-weight: 700;
  color: #c4b5fd;
  margin-bottom: 8px;
  padding: 6px 10px;
  background: rgba(124, 58, 237, 0.15);
  border-left: 3px solid #7c3aed;
  border-radius: 0 6px 6px 0;
}

.cover-letter-text {
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
  font-size: 13px;
  line-height: 1.7;
  color: #e2e8f0;
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(139, 92, 246, 0.2);
  border-radius: 8px;
  padding: 16px;
  margin: 0;
}

/* 포트폴리오 분석 결과 */
.portfolio-review-result {
  margin-top: 20px;
}

.review-section {
  margin-bottom: 16px;
}

.review-section-title {
  font-size: 13px;
  font-weight: 700;
  color: #a78bfa;
  margin-bottom: 8px;
}

.review-list {
  padding-left: 20px;
  margin: 0;
}

.review-list li {
  font-size: 13px;
  color: #cbd5e1;
  margin-bottom: 4px;
  line-height: 1.5;
}

.review-list.missing li {
  color: #fca5a5;
}

.review-list.priority li {
  color: #86efac;
}

.improvement-card {
  background: rgba(15, 23, 42, 0.5);
  border: 1px solid rgba(139, 92, 246, 0.15);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 8px;
  font-size: 13px;
  line-height: 1.5;
}

.imp-target {
  font-weight: 700;
  color: #c4b5fd;
  margin-bottom: 4px;
}

.imp-issue {
  color: #fbbf24;
  margin-bottom: 4px;
}

.imp-suggestion {
  color: #86efac;
}
</style>
