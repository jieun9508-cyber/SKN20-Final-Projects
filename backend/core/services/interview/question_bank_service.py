"""
question_bank_service.py -- 면접 질문 뱅크 검색 서비스

생성일: 2026-03-01
수정일: 2026-03-02
설명: InterviewQuestion DB(13,169건)에서 기업/직무/슬롯별 질문을 검색하여
      plan_generator(면접 계획 수립)와 interviewer(면접 진행)에 주입하는 서비스 모듈.

[2026-03-02] 성능 최적화: order_by('?') → Python random.sample()
  - 변경 전: PostgreSQL RANDOM()으로 전체 테이블 정렬 (O(n log n), 13K건 × 11회 = ~5.5초)
  - 변경 후: 인덱스 필터 → ID만 조회 → Python에서 랜덤 선택 → PK 조회 (~0.1초)
  - 결과 품질: 동일 (균등 분포 랜덤, 기업 우선순위 유지)

사용처:
  1. plan_generator.py  -- generate_plan() 호출 시 기출 질문을 프롬프트에 주입
  2. session_view.py    -- 세션 생성 시 슬롯별 질문 묶음(bank_questions)을 interview_plan에 저장
  3. interviewer.py     -- L4 Interviewer 시스템 프롬프트에 현재 슬롯의 기출 질문 주입
  4. question_bank_view.py -- 질문 검색 REST API 엔드포인트

주요 함수:
  - search_questions()          : 범용 질문 검색 (API 및 내부 공통)
  - get_questions_for_session() : 세션 시작 시 슬롯별 질문 묶음 반환
  - get_questions_for_plan()    : 면접 계획 생성용 기출 질문 요약 반환
  - map_slot_to_type()          : interview_plan 슬롯명 → DB slot_type 매핑
"""
import random

from django.db.models import Q

from core.models import InterviewQuestion


# ============================================================================
# 유틸리티
# ============================================================================

def map_slot_to_type(slot_name: str) -> str:
    """interview_plan의 slot명을 InterviewQuestion.slot_type으로 매핑한다.

    plan_generator가 생성하는 슬롯명(예: technical_depth, technical_depth_2)을
    DB의 slot_type 값(technical)으로 변환한다.
    motivation, collaboration, problem_solving, growth는 그대로 반환.

    Args:
        slot_name: interview_plan에서의 슬롯명
                   예: "technical_depth", "motivation", "collaboration"

    Returns:
        DB slot_type 문자열
        예: "technical", "motivation", "collaboration"
    """
    if slot_name.startswith("technical"):
        return "technical"
    return slot_name


# ============================================================================
# 질문 검색 (공통)
# ============================================================================

def search_questions(slot_type=None, company="", job="", limit=10) -> list:
    """조건에 맞는 면접 질문을 DB에서 검색한다.

    [2026-03-02] 성능 최적화: order_by('?') → Python random.sample()
      - 변경 전: RANDOM()으로 전체 테이블 정렬 (13K건 풀스캔, ~500ms/회)
      - 변경 후: 인덱스 필터 → ID+company만 조회 → Python 랜덤 → PK 조회 (~10ms/회)

    검색 우선순위:
      1) company가 지정되면 해당 기업 질문 우선 → 부족하면 범용(company='') 질문으로 보충
      2) job이 지정되면 직무명 부분 매치(icontains) 또는 범용(job='') 질문 포함
      3) Python random.sample()로 같은 조건이라도 매번 다른 질문 제공

    DB 인덱스 활용:
      - idx_company_slot_job (company, slot_type, job) 복합 인덱스
      - values_list('id', 'company')로 최소 데이터만 조회하여 인덱스 커버링 극대화

    Args:
        slot_type: InterviewQuestion.SlotType 값
                   (technical, motivation, collaboration, problem_solving, growth, general)
                   None이면 전체 슬롯 대상
        company: 기업명 (정확 매치 우선). 빈 문자열이면 기업 필터 없음.
        job: 직무명 (부분 매치). 빈 문자열이면 직무 필터 없음.
        limit: 최대 반환 개수 (기본 10)

    Returns:
        질문 dict 리스트:
        [
            {
                "id": int,              # DB PK
                "question_text": str,   # 질문 텍스트
                "slot_type": str,       # 슬롯 유형
                "company": str,         # 기업명 (빈 문자열이면 범용)
                "job": str,             # 직무
                "source": str,          # 데이터 소스 (aihub_ict, jobkorea, github, youtube)
                "answer_summary": str,  # 답변 요약 (AI Hub 데이터만 존재)
            },
            ...
        ]
    """
    qs = InterviewQuestion.objects.all()

    # 슬롯 필터 (인덱스: idx_company_slot_job의 slot_type 컬럼)
    if slot_type:
        qs = qs.filter(slot_type=slot_type)

    # 직무 필터: 부분 매치 또는 범용
    if job:
        qs = qs.filter(Q(job__icontains=job) | Q(job=''))

    # ── [2026-03-02] Python 랜덤 샘플링 (기업 우선순위 유지) ────────────
    # 1단계: ID + company만 가져옴 (인덱스 커버링, 전체 행 로드 안 함)
    if company:
        qs = qs.filter(Q(company=company) | Q(company=''))
        id_pairs = list(qs.values_list('id', 'company'))

        # 기업 매치 ID와 범용 ID를 분리
        company_ids = [pk for pk, c in id_pairs if c == company]
        general_ids = [pk for pk, c in id_pairs if c != company]

        # 기업 질문 우선 선택 → 부족하면 범용으로 보충
        selected = random.sample(company_ids, min(limit, len(company_ids)))
        remaining = limit - len(selected)
        if remaining > 0 and general_ids:
            selected += random.sample(general_ids, min(remaining, len(general_ids)))
    else:
        id_list = list(qs.values_list('id', flat=True))
        selected = random.sample(id_list, min(limit, len(id_list)))

    if not selected:
        return []

    # 2단계: 선택된 ID로 전체 데이터 조회 (PK 인덱스, 즉시 반환)
    results = InterviewQuestion.objects.filter(id__in=selected)

    # 선택 순서 유지 (기업 우선순위 반영)
    id_order = {pk: idx for idx, pk in enumerate(selected)}
    results = sorted(results, key=lambda q: id_order.get(q.id, 0))

    return [
        {
            "id": q.id,
            "question_text": q.question_text,
            "slot_type": q.slot_type,
            "company": q.company,
            "job": q.job,
            "source": q.source,
            "answer_summary": q.answer_summary or "",
        }
        for q in results
    ]


# ============================================================================
# 세션용 질문 묶음
# ============================================================================

def get_questions_for_session(company="", job="", slot_types=None) -> dict:
    """세션 시작 시 슬롯별로 질문 묶음을 가져온다.

    session_view.py의 세션 생성(POST) 시 호출.
    반환된 dict는 interview_plan["bank_questions"]에 저장되어
    면접 진행 중 humanizer → interviewer로 전달된다.

    Args:
        company: 기업명 (SavedJobPosting.company_name)
        job: 직무명 (SavedJobPosting.position)
        slot_types: interview_plan의 슬롯 이름 리스트
                    예: ["motivation", "technical_depth", "collaboration", "growth"]

    Returns:
        슬롯별 질문 묶음 dict:
        {
            "motivation": [{"id", "question_text", "slot_type", ...}, ...],
            "technical":  [{"id", "question_text", "slot_type", ...}, ...],
            "collaboration": [...],
            ...
        }
        각 슬롯당 최대 5개 질문.
        technical_depth, technical_depth_2 등은 모두 "technical" 키로 통합.
    """
    if not slot_types:
        return {}

    result = {}
    seen_ids = set()  # 슬롯 간 질문 중복 방지

    for slot_name in slot_types:
        db_type = map_slot_to_type(slot_name)

        # 이미 같은 DB 타입으로 가져온 적 있으면 스킵
        # (technical_depth와 technical_depth_2가 모두 "technical"이므로)
        if db_type in result:
            continue

        questions = search_questions(
            slot_type=db_type,
            company=company,
            job=job,
            limit=5,
        )

        # 중복 질문 제거
        unique = []
        for q in questions:
            if q["id"] not in seen_ids:
                seen_ids.add(q["id"])
                unique.append(q)

        result[db_type] = unique

    return result


# ============================================================================
# 면접 계획 생성용
# ============================================================================

def get_questions_for_plan(company="", job="") -> list:
    """면접 계획 생성(plan_generator) 프롬프트에 주입할 기출 질문을 반환한다.

    [2026-03-02] 성능 최적화: order_by('?') → Python random.sample()
      - 변경 전: 슬롯 6종류 × 각각 order_by('?') = 6회 풀 테이블 랜덤 정렬
      - 변경 후: 슬롯별 ID만 조회 → Python 랜덤 → PK 조회 (1회 배치)

    plan_generator.py의 _build_plan_prompt()에서 호출.
    LLM이 허구의 토픽을 만들지 않고 실제 면접 데이터를 참고하여
    슬롯 구성과 토픽을 결정하도록 한다.

    Args:
        company: 기업명
        job: 직무명

    Returns:
        질문 요약 리스트 (최대 20개, 슬롯별 고르게 분배):
        [
            {"slot_type": "technical", "question_text": "...", "source": "jobkorea"},
            {"slot_type": "motivation", "question_text": "...", "source": "aihub_ict"},
            ...
        ]
    """
    # ── 기본 필터 (기업 + 직무) ──────────────────────────────────────────
    qs = InterviewQuestion.objects.all()

    if company:
        qs = qs.filter(Q(company=company) | Q(company=''))
    if job:
        qs = qs.filter(Q(job__icontains=job) | Q(job=''))

    # ── [2026-03-02] 슬롯별 Python 랜덤 샘플링 (기업 우선) ─────────────
    slot_types = ['technical', 'motivation', 'collaboration', 'problem_solving', 'growth', 'general']
    selected_ids = []

    for st in slot_types:
        # ID + company만 조회 (인덱스 커버링)
        id_pairs = list(
            qs.filter(slot_type=st).values_list('id', 'company')
        )

        if company:
            # 기업 매치 우선 → 부족하면 범용 보충
            company_ids = [pk for pk, c in id_pairs if c == company]
            general_ids = [pk for pk, c in id_pairs if c != company]
            picked = random.sample(company_ids, min(4, len(company_ids)))
            remaining = 4 - len(picked)
            if remaining > 0 and general_ids:
                picked += random.sample(general_ids, min(remaining, len(general_ids)))
        else:
            all_ids = [pk for pk, _ in id_pairs]
            picked = random.sample(all_ids, min(4, len(all_ids)))

        selected_ids.extend(picked)

    if not selected_ids:
        return []

    # PK 배치 조회 (1회 쿼리로 전체 가져옴)
    questions = InterviewQuestion.objects.filter(id__in=selected_ids)
    q_map = {q.id: q for q in questions}

    result = []
    for pk in selected_ids:
        q = q_map.get(pk)
        if q:
            result.append({
                "slot_type": q.slot_type,
                "question_text": q.question_text,
                "source": q.source,
            })

    return result[:20]
