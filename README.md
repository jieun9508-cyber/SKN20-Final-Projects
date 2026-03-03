# AI-ARCADE — AI 엔지니어 역량 훈련 플랫폼

> **게임처럼 배우고, 실무처럼 평가받는다**

의사코드 작성, 디버깅, 시스템 설계, 실시간 대전, AI 코칭, 모의 면접까지 —
AI 엔지니어에게 필요한 역량을 **하나의 플랫폼**에서 훈련하고 평가받을 수 있습니다.

---

## 팀 소개

**TEAM. Silver_Valley**

|      | 이지은 | 권규리 | 김황현 | 박찬 | 최소영 | 황수현 |
| --- | --- | --- | --- | --- | --- | --- |
| 프로필 | <img src="frontend/public/image/member/lge.png" width="100"> | <img src="frontend/public/image/member/kkr.png" width="100"> | <img src="frontend/public/image/member/khh.png" width="100"> | <img src="frontend/public/image/member/pch.png" width="100"> | <img src="frontend/public/image/member/csy.png" width="100"> | <img src="frontend/public/image/member/hsh.png" width="100"> |
| 역할 | PM | 팀원 | 팀원 | 팀원 | 팀원 | 팀원 |

---

## 프로젝트 목표

> **단순 알고리즘 풀이를 넘어, 실전 파이프라인·디버깅·시스템 설계를 게이미피케이션으로 학습한다.**

### 핵심 목표

- **반복 훈련 루프**: 단계별 클리어 후 다음 진행, 실패 시 근거 기반 피드백 제공
- **AI 평가 고도화**: 단순 정답 채점이 아닌, 사고력·설계력·디버깅 과정을 다차원으로 평가
- **실무 관점 반영**: 기능 + 비기능 요구사항, 확장성·비용·보안 훈련, 면접·실무 실제 질문 반영

### 공통 차별화 요소

| 특징 | 설명 |
| --- | --- |
| **시니어 AI 엔지니어 페르소나** | 실무적 관점의 실시간 피드백 제공 |
| **사고력 평가** | 코드/아키텍처의 사고 과정 자체를 평가 (예: "어떤 논리로 작성하셨나요?") |
| **게이미피케이션** | 포인트·랭크·아바타·실시간 대전으로 즐거움을 느끼는 플레이그라운드 |

---

## 배경 및 문제 인식

### 폭발적으로 성장하는 글로벌 AI 교육 시장

- **CAGR 41.4%** 연평균 성장률 (2025-2029)
- 2025년 **76억 달러** → 2029년 **303억 달러** (약 4배 성장 예상)
- 출처: Research and Markets, AI in Education Market Report 2025

### 패러다임 전환: AI는 생존 스킬

| 과거 (2020년대 초반) | 현재 (2026+) |
| --- | --- |
| **선택 기술** (Optional Tech) | **생존 스킬** (Survival Skill) |
| 특정 직군만 필요 | 모든 산업에 필수 |
| 보조 도구 | 핵심 역량 |

### 기존 교육 방식의 한계점

| 기존 교육 방식 | AI-ARCADE의 해결 |
| --- | --- |
| 단순 알고리즘 반복 훈련 | 실무형 반복 훈련 (설계·디버깅·면접) |
| 느린 피드백 루프 | AI 기반 즉각 피드백 |
| 즉각적이고 일관된 평가 부재 | 다차원 AI 평가 시스템 |
| 프로덕션 환경 부재 | 실전 파이프라인 경험 |

### 기존 플랫폼과의 차별점

| | LeetCode / Codewars | Kaggle | DataCamp / MOOC | **AI-ARCADE** |
| --- | --- | --- | --- | --- |
| 강점 | 알고리즘 심화 | 실제 데이터 분석 | 체계적 커리큘럼 | **사고력 + 설계 + 디버깅 + 면접** |
| 한계 | 단편적 함수 구현 | 정제된 데이터만 | 수동적 학습 | — |
| 시스템 설계 | X | X | X | **O** |
| AI 맞춤 피드백 | X | X | X | **O** |
| 실시간 멀티플레이 | X | X | X | **O** |
| 모의 면접 (음성) | X | X | X | **O** |

---

## 주요 기능

### 1. Pseudocode Practice — 의사코드 훈련

> 사용 모델: `gpt-4o` (평가) · `gpt-4o-mini` (힌트 에이전트)

사용자가 자연어 기반 의사코드를 작성하면, **gpt-4o**가 Chain of Thought 추론으로 5개 차원을 평가합니다.
LLM 평가(85점)와 Rule 기반 감점(15점)을 결합한 **뉴로심볼릭 하이브리드 채점** 방식입니다.

| 평가 항목 | 설명 | 배점 |
| --- | --- | --- |
| **설계력** | 단계별 연결성 및 아키텍처적 완성도 | 25점 |
| **정합성** | 문제 의도와 사용자 로직의 일치 여부 | 20점 |
| **추상화** | 핵심 로직의 간결한 표현력 | 15점 |
| **예외처리** | 예외 상황 대응 로직 포함 여부 | 15점 |
| **구현력** | 논리적 흐름의 구체성과 명확성 | 10점 |

- **Anti-Pattern 자동 감지**: Data Leakage, Hardcoding, Blind Spot, Fragility 패턴 탐지 시 Rule 기반 자동 감점
- **Tail Question**: 가장 약한 차원에 대한 꼬리질문 자동 생성
- **3단계 힌트 에이전트** (`gpt-4o-mini`): Light → Specific → Core 순으로 단계적 힌트 제공 + 유튜브 학습 영상 추천
- **저품질 입력 감지**: 복사-붙여넣기/무의미 입력 자동 탐지 → LowEffortError → 0점 처리
- **등급 기준**: EXCELLENT(88+) / GOOD(75+) / AVERAGE(50+) / POOR(50 미만)

### 2. Bug Hunt — 디버깅 훈련

> 사용 모델: `gpt-5.2` (인터뷰) · `gpt-5-mini` (종합평가)

실무 기반 디버깅 시나리오에서 버그를 찾고 수정한 뒤, **AI 인터뷰**를 통해 사고력을 심층 검증합니다.
**4단계 순차 파이프라인**으로 동작합니다.

**디버깅 시나리오 분류**:
- 데이터 관련: Data Leakage, Label Imbalance, Overfitting
- 코드 로직: Off-by-one Error, Null Pointer, Type Mismatch
- ML 특화: Gradient 누적, Train/Eval 모드, Padding Mask 오류

**4단계 평가 파이프라인**:

| Stage | 내용 | 기술 |
| --- | --- | --- |
| **Stage 1: 코드 검증** | Docker 샌드박스에서 수정 코드의 동작 정확성을 행동 기반으로 검증 | Docker + 행동 검증 (폴백: 문자열 매칭) |
| **Stage 2: 심층 인터뷰** | `gpt-5.2`가 3턴에 걸쳐 적응형 질문 — Turn 1: 핵심 이해 / Turn 2: 메커니즘 / Turn 3: 응용력 | SSE 스트리밍 (질문), JSON (평가) |
| **Stage 3: 스텝별 루브릭 채점** | 3-Tier 루브릭으로 각 스텝 개별 채점 — 핵심(40점) / 메커니즘(35점) / 응용(25점) | 스텝별 independent scoring |
| **Stage 4: 종합 평가** | `gpt-5-mini`가 전 스텝 인터뷰 결과 + 힌트 사용 횟수 + 실패 횟수를 종합하여 최종 점수 산출 | 보정 로직: 무힌트+무실패 +3, 힌트 3회+ -2, 전스텝 Deep +5 |

**적응형 인터뷰 전략**:
- 정답 → 인정 + 다음 개념으로 심화
- 부분 정답 → 부드러운 교정 + 힌트 제공
- 오답 → 난이도 하향 + 쉬운 질문으로 유도
- 이해도 등급: Excellent(90+) / Good(70+) / Surface(40+) / Poor(40 미만)

### 3. System Architecture — 시스템 설계 훈련

> 사용 모델: `gpt-4o-mini` (설계 평가) · `gpt-5-mini` (심화 질문 생성)

드래그 앤 드롭 캔버스에서 아키텍처를 설계하면 **Mermaid 다이어그램이 자동 생성**되고,
Canvas → JSON → Mermaid → LLM 평가 파이프라인으로 처리됩니다.

**설계 시나리오 3종**:
- Image Feed (반려 식물 성장 일기): Low Latency, 확장성, 모니터링
- Real-time Chat (1:1 멘토링 채팅): 대용량 처리, 확장성, 개인화
- Newsfeed (동아리 통합 공지): 대용량 처리, 확장성, A/B Testing

**2-Phase 평가**:

| Phase | 모델 | 평가 내용 |
| --- | --- | --- |
| **Phase 1: 설계 평가** | `gpt-4o-mini` | Well-Architected 6-Pillar (신뢰성/성능/운영/비용/보안/지속가능성) 각 0~100점 + 필수 컴포넌트·연결 관계 검증 |
| **Phase 2: Deep Dive** | `gpt-5-mini` | 약점 기반 심화 질문 3개 자동 생성 (설계 의도 / 확장성·성능 / 장애 대응) |

- **Anti-Pattern 자동 감지**: SPOF, 이중화 부재, 캐싱 전략 미흡, 보안 노출, Auto-scaling 부재
- **2인 대전 비교 분석**: `gpt-4o-mini`가 양측 설계의 전략 차이를 분석하여 `my_analysis`(자기 분석) + `versus`(상대 비교) 제공
- **등급 기준**: 우수(90+) / 양호(72+) / 보통(55+) / 미흡(40+) / 부족(40 미만)

### 4. Coduck Wars — 실시간 멀티플레이

> 사용 모델: `gpt-4o-mini` (ChaosAgent · EvalAgent) · **Rule Engine** (CoachAgent)

**"압박 속에서 실력이 드러난다"** — Socket.IO 기반 실시간 대전 + AI 방해 + 협동

**3-Agent 오케스트레이션**:

| Agent | 모델 | 역할 |
| --- | --- | --- |
| **ChaosAgent** | `gpt-4o-mini` | 배치된 노드를 분석하여 동적 장애 이벤트 생성 (LOW/MEDIUM/HIGH/CRITICAL). LLM 실패 시 5개 사전 정의 이벤트로 폴백 |
| **CoachAgent** | Rule Engine (LLM 없음) | 미션 필수 컴포넌트 vs 배치 노드를 비교하여 우선순위 기반 힌트 제공. 비용 0 |
| **EvalAgent** | `gpt-4o-mini` | ArchEvaluator를 래핑하여 라운드별 설계 비교 평가 |

**현재 제공 미니게임 (프론트 라우팅 기준 3종)**:
- **Arch Draw Quiz**: 아키텍처 드래그앤드롭 대전 (실시간 캔버스 동기화)
- **Logic Run**: 로직 릴레이 퍼즐
- **Bug Bubble Monster**: 1:1 버그 디펜스 대전

참고: `pressure-question` 관련 백엔드 API는 존재하지만, 전용 프론트 라우트는 현재 제거된 상태입니다.

**기술 포인트**:
- Socket.IO 기반 20+ 이벤트 타입 실시간 동기화
- 룸 기반 상태 관리 + 연결 끊김 시 자동 정리 + 리더 자동 승계

### 5. AI Coach (Coduck Coach) — AI 학습 코칭

> 사용 모델: `gpt-4o-mini` (Intent 분류) · `gpt-5-mini` (Agent Loop + Function Calling)

단순 챗봇이 아닌 **ReAct Agent 기반** 코칭 시스템입니다.
3단계 파이프라인으로 동작하며, LLM이 필요한 데이터를 자율적으로 판단·수집하여 맞춤형 코칭을 제공합니다.

```
Guardrail (Python regex) → Intent Analysis (gpt-4o-mini) → Agent Loop (gpt-5-mini)
   비용: 0                    의도 분류 (A~G)                 6개 도구 자율 호출 (max 5회)
```

- **Intent별 응답 전략**: 7가지 유형(데이터 조회/학습 방법/동기부여/범위 밖/문제 풀이/개념 설명/의사결정)마다 다른 시스템 프롬프트 + 허용 도구 세트
- **6개 도구**: 성적 조회 / 약점 분석 / 최근 활동 / 문제 추천 / 커리큘럼 / 학습 가이드
- **대화 히스토리**: 최근 5턴(10메시지)을 LLM 컨텍스트에 포함하여 연속 대화 지원. 사용자별 대화 세션을 DB에 저장하고, 사이드바에서 이전 대화 조회/이어가기/이름수정/삭제 가능
- **차트 자동 생성**: Bar/Line/Radar/Progress/Table 5종 (Intent와 키워드에 따라 동적 판단)
- **비용 최적화 4중 구조**: Guardrail(토큰 0) → 경량 모델 분류 → Intent별 도구 필터링(환각 방지) → 도구 결과 캐싱
- **SSE 스트리밍**: Agent 사고과정(thinking) → 도구 호출(step) → 차트 데이터 → 토큰 단위 답변을 실시간 전달

### 6. Job Planner — 채용공고 분석

> 사용 모델:
> - `gpt-4o`: 이미지 OCR 및 고정밀 파싱
> - `gpt-4o-mini`: 텍스트 기반 분석/추천
> - `text-embedding-3-small`: 스킬 매칭

채용공고를 3가지 소스에서 입력받아 파싱하고, 임베딩 기반으로 사용자 역량과 매칭합니다.
분석 결과는 **Mock Interview의 면접 계획 자동 생성으로 직접 연계**됩니다.

```
채용공고 입력 → 파싱 → 스킬 추출/매칭 → 갭 분석 → Action 추천
                                                   ↓
                                          Mock Interview Plan Generator
                                          (채용공고 + 사용자 약점 → 맞춤 면접 계획)
```

| 입력 소스 | 처리 방식 |
| --- | --- |
| **URL** | BeautifulSoup 웹 크롤링 (원티드/사람인 등) |
| **이미지** | OpenAI Vision(`gpt-4o`) OCR로 텍스트 추출 |
| **텍스트** | 직접 파싱 |

- **스킬 매칭**: `text-embedding-3-small`로 스킬 임베딩 → L2 정규화 → 코사인 유사도 계산 → readiness_score(0~1.0) 산출
- **Action 결정**: 스킬 갭 + 시간 압박도 분석 → `learn_skill` / `apply_now` / `pivot_role` / `wait_and_prepare` 등 상태 기반 추천
- **면접 연계**: 파싱된 채용공고의 required_skills + 사용자 학습 약점 데이터를 Mock Interview Plan Generator에 전달 → 기술 심층 슬롯의 증거 키가 해당 공고의 기술 스택으로 동적 생성

### 7. Mock Interview — AI 모의 면접

> 사용 모델: `gpt-4o` (면접관 · 면접 계획 생성) · `gpt-4o-mini` (증거 추출) · **Rule Engine** (상태 관리)

Job Planner에서 분석한 채용공고를 기반으로 **맞춤형 면접 시뮬레이션**을 진행합니다.
일반적인 질문 리스트가 아닌, **증거 기반 슬롯 필링** 방식의 **4-Layer 아키텍처**로 동작합니다.

| Layer | 모듈 | 모델 | 역할 |
| --- | --- | --- | --- |
| **L1 증거 추출** | Analyst | `gpt-4o-mini` | 답변에서 증거 키 충족 여부를 True/False로 추출 (temperature: 0) |
| **L2 상태 관리** | State Engine | Rule Engine | 슬롯 상태 전이 (UNKNOWN → PARTIAL → CLEAR), 이동 조건 판단 |
| **L3 질문 생성** | Interviewer | `gpt-4o` | 누락 증거를 채우기 위한 적응형 질문 SSE 스트리밍 생성 |
| **L4 면접 설계** | Plan Generator | `gpt-4o` | Job Planner 분석 결과 + 사용자 약점 → 4~6개 슬롯의 맞춤 면접 계획 생성 |

**평가 슬롯 (증거 기반, 4~6개 동적 구성)**:

| 슬롯 | 증거 키 예시 |
| --- | --- |
| 동기(Motivation) | reason, research, alignment, aspiration |
| 기술 심층(Technical) | **Job Planner가 추출한 채용공고 기술 스택에서 동적 생성** |
| 협업(Collaboration) | role, action, result, conflict, reflection |
| 문제 해결(Problem Solving) | situation, analysis, approach, learning |
| 성장(Growth) | challenge, effort, change |

- **슬롯 이동 조건**: CLEAR 달성 / 최대 3회 시도 / 연속 2회 새 증거 없음
- **멀티모달**: STT(faster-whisper 기반 파이프라인, RunPod/로컬) · TTS(음성 옵션 alloy/nova/onyx/shimmer) · Vision(비언어 분석)

### 기타

- **Nano Banana 아바타**: 활동 포인트로 AI 생성 커스텀 아바타를 만들고 장착
- **리더보드 / 랭크**: 포인트 기반 전체 유저 랭킹과 등급(BRONZE/SILVER/GOLD/ENGINEER) 시스템
- **관리자 대시보드**: 유저 진행률 조회, 제출 이력 필터링, 서버 상태 모니터링, 운영 로그 관리

---

## 서비스 이점 및 차별성

| 항목 | 기존 코딩 테스트 | 기존 화상/면접 서비스 | **AI-ARCADE** |
| --- | --- | --- | --- |
| **평가 범위** | 정답 여부, 실행 시간 | 대면 면접관 중심 | 사고력 + 코드 품질 + 디버깅 + 설계 |
| **인터랙션** | 코드만 제출 | 화상/음성 위주 | 코드 + AI 피드백 + 자동 질문/힌트 |
| **평가 방식** | 제출 시 한 번 평가 | 수동 리뷰 | AI 기반 즉각 평가 + 다차원 피드백 |
| **학습 경험** | 단순 반복 | 일회성 면접 | 게이미피케이션 + 반복 훈련 루프 |

---

## 시스템 아키텍처

```
┌──────────────────────────────────────────────────────────┐
│  Frontend (Vue 3 + Vite)                                  │
│  Pinia · Vue Router · Chart.js · Monaco Editor · Mermaid │
│  Socket.IO Client · MediaPipe                             │
└──────────────┬──────────────────────┬────────────────────┘
               │ REST API (Axios)     │ WebSocket (Socket.IO)
               ▼                      ▼
┌──────────────────────────┐  ┌────────────────────────────┐
│  Django + DRF            │  │  Socket.IO ASGI Server     │
│  Async Views + SSE       │  │  (Coduck Wars 실시간 동기화) │
│  sync_to_async (ORM)     │  │  20+ 이벤트 타입             │
└──────────┬───────────────┘  └────────────────────────────┘
           │
     ┌─────┴─────┐
     ▼           ▼
┌─────────┐  ┌──────────────────────────────────┐
│PostgreSQL│  │  OpenAI API                       │
│(JSONField│  │  gpt-4o-mini (Intent 분류)         │
│ 활용)    │  │  gpt-5-mini  (Agent Loop/평가)     │
│          │  │  faster-whisper 기반 STT · TTS · Vision │
└─────────┘  └──────────────────────────────────┘
```

---

## 기술 스택

| 계층 | 기술 |
|------|------|
| **Frontend** | Vue 3, Vite, Pinia, Vue Router, Axios, Chart.js, Monaco Editor, Mermaid, Socket.IO Client, MediaPipe |
| **Backend** | Django, Django REST Framework, Python-SocketIO, Uvicorn, OpenAI SDK |
| **AI/LLM** | gpt-4o (의사코드 평가 · 면접관 · Job Planner OCR/분석 일부), gpt-4o-mini (Intent 분류 · 증거 추출 · 설계 평가 · Chaos 이벤트 · Job Planner 분석 일부), gpt-5-mini (Coach Agent Loop · 종합평가 · 심화질문), gpt-5.2 (BugHunt 인터뷰), text-embedding-3-small (스킬 매칭), faster-whisper 기반 STT 파이프라인, TTS(`tts-1`), Vision |
| **Database** | PostgreSQL (JSONField 기반 유연 스키마) |
| **Infra** | Docker, Docker Compose, Uvicorn(ASGI), Python-SocketIO, (배포 환경) AWS EC2/Nginx 연동 |

---

## 핵심 기술 포인트

| 패턴 | 적용 | 설명 |
|------|------|------|
| **ReAct Agent + Function Calling** | AI Coach | gpt-5-mini가 6개 도구 호출 필요성을 자율 판단, 최대 5회 반복 |
| **4단계 순차 파이프라인** | Bug Hunt | Docker 검증 → gpt-5.2 인터뷰(SSE) → 3-Tier 루브릭 채점 → gpt-5-mini 종합평가 |
| **뉴로심볼릭 AI** | Pseudocode | gpt-4o CoT 평가(85점) + Rule 기반 Anti-Pattern 감점(15점) 결합 |
| **3-Agent 오케스트레이션** | Coduck Wars | ChaosAgent(LLM) + CoachAgent(Rule) + EvalAgent(LLM) 역할 분리 |
| **4-Layer 면접 엔진** | Mock Interview | gpt-4o-mini 증거추출 → Rule 상태관리 → gpt-4o 질문생성 → gpt-4o 면접설계 |
| **SSE 스트리밍** | Coach, BugHunt, Interview | 토큰 단위 실시간 응답 + Agent 사고과정 공개 |
| **증거 기반 슬롯 필링** | Mock Interview | NLU 연구 개념 실용화: UNKNOWN → PARTIAL → CLEAR 상태 전이 |
| **임베딩 스킬 매칭** | Job Planner | text-embedding-3-small + L2 정규화 + 코사인 유사도 |
| **비용 최적화 4중 구조** | AI Coach | Guardrail(토큰 0) → 경량 모델 분류 → Intent별 도구 필터링 → 캐싱 |

---

## 프로젝트 구조

```
SKN20-FINAL-5TEAM/
├── backend/
│   ├── config/                  # Django 설정 (settings, urls, asgi)
│   ├── core/
│   │   ├── models/              # Django 모델 (user, practice, interview, activity, coach)
│   │   ├── views/
│   │   │   ├── ai_coach/        # AI Coach (3단계 파이프라인)
│   │   │   ├── interview/       # Mock Interview (슬롯 필링)
│   │   │   ├── job_planner/     # Job Planner (채용공고 파싱/분석)
│   │   │   ├── architecture/    # System Architecture 평가
│   │   │   ├── bughunt/         # Bug Hunt 평가 + 인터뷰
│   │   │   ├── pseudocode/      # Pseudocode 평가
│   │   │   ├── auth_view.py     # 인증 (로그인/가입/세션)
│   │   │   ├── admin_views.py   # 관리자 API
│   │   │   └── ...
│   │   ├── services/
│   │   │   ├── interview/       # 면접 엔진 (슬롯/증거맵/플래너)
│   │   │   ├── wars/            # Wars Agent (Chaos/Coach/Eval)
│   │   │   ├── pseudocode_evaluator.py
│   │   │   ├── arch_evaluator.py
│   │   │   └── ...
│   │   └── socket_server.py     # Socket.IO 실시간 서버
│   └── manage.py
├── frontend/
│   └── src/
│       ├── features/
│       │   ├── practice/        # Pseudocode / BugHunt / Architecture
│       │   ├── wars/            # Coduck Wars (로비/배틀/미니게임)
│       │   ├── ai-coach/        # AI Coach 채팅
│       │   ├── interview/       # Mock Interview
│       │   ├── job_planner/     # Job Planner
│       │   ├── my-records/      # 학습 기록/리포트
│       │   ├── admin/           # 관리자 대시보드
│       │   └── home/            # 랜딩 페이지
│       ├── stores/              # Pinia 상태 관리 (auth 등)
│       ├── App.vue
│       └── main.js              # 라우터 설정
├── docs/
│   ├── requirements/            # 요구사항 정의서
│   └── specs/                   # 기술 명세 문서
└── docker-compose.yml
```

---

## 설치 및 실행

### Docker 배포 (권장)

이 프로젝트는 Docker Compose 기준으로 실행하도록 구성되어 있습니다.
`backend/requirements.txt` 설치, DB 기동, frontend 의존성 설치를 컨테이너가 처리합니다.

1. 루트 경로에 `.env` 파일 준비  
   최소 권장 키:
   - `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DATABASE_URL`
   - `OPENAI_API_KEY`
   - (선택) `GOOGLE_API_KEY`, `GROQ_API_KEY`, `AWS_*`, `STT_RUNPOD_URL`
2. 컨테이너 실행

```bash
docker-compose up --build
```

3. 접속
   - Frontend: `http://localhost:5173`
   - Backend API: `http://localhost:8000`
   - Swagger: `http://localhost:8000/api/docs/`

### 로컬 개발 (선택)

Docker 없이 개별 실행할 경우:
- Backend 의존성: `backend/requirements.txt`
- Frontend 의존성: `frontend/package.json`

---

## 문서

- [요구사항 정의서](docs/requirements/REQUIREMENTS.md)
- [AI Coach 기술 상세](docs/specs/AI_COACH_TECHNICAL_OVERVIEW.md)
- [AI Coach 설계 근거](docs/specs/AI_COACH_DESIGN_RATIONALE.md)
- [AI Coach 종합 평가](docs/specs/AI_COACH_EVALUATION.md)
- [발표 초안](docs/specs/FINAL_PRESENTATION_DRAFT.md)

---

## 참고 자료

- Research and Markets, AI in Education Market Report 2025
- The Korea Herald (2024-2025), Ministry of Education, South Korea
- Korea Economic Institute (2024), Ministry of Science and ICT, South Korea
