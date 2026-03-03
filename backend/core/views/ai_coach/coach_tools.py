"""AI Coach 도구 (최적화 버전) - 6개 도구 + 피드백 추출 + 학습 데이터"""

import json
from django.db.models import Avg, Max, Count
from core.models import UserSolvedProblem, Practice, PracticeDetail

# ─────────────────────────────────────────────
# 1. Tool 정의 (OpenAI function calling schema)
# ─────────────────────────────────────────────

COACH_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_user_scores",
            "description": "유저의 유닛별 평균 점수, 최고 점수, 풀이 수, 완료율을 조회합니다.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weak_points",
            "description": "특정 유닛에서 유저의 약점(70점 미만 메트릭)을 분석합니다. AI 피드백도 함께 반환합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "unit_id": {
                        "type": "string",
                        "enum": ["unit01", "unit02", "unit03"],
                        "description": "분석할 유닛 ID",
                    }
                },
                "required": ["unit_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_activity",
            "description": "유저의 최근 학습 활동(풀이 기록)을 조회합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "조회할 최근 기록 수 (기본값: 10)",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recommend_next_problem",
            "description": "아직 풀지 않았거나 점수가 낮은 문제를 추천합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "unit_id": {
                        "type": "string",
                        "enum": ["unit01", "unit02", "unit03"],
                        "description": "추천받을 유닛 ID",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_unit_curriculum",
            "description": "특정 유닛의 학습 목표, 핵심 개념, 훈련 스킬, 공부 팁을 조회합니다. 학습 방법이나 개념 관련 질문에 사용하세요.",
            "parameters": {
                "type": "object",
                "properties": {
                    "unit_id": {
                        "type": "string",
                        "enum": ["unit01", "unit02", "unit03"],
                        "description": "조회할 유닛 ID",
                    }
                },
                "required": ["unit_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_study_guide",
            "description": "유저의 약점 메트릭을 기반으로 맞춤 학습 가이드를 생성합니다. 무엇을 어떻게 공부해야 하는지 구체적 방향을 제시합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "unit_id": {
                        "type": "string",
                        "enum": ["unit01", "unit02", "unit03"],
                        "description": "학습 가이드를 생성할 유닛 ID",
                    }
                },
                "required": ["unit_id"],
            },
        },
    },
]

# ─────────────────────────────────────────────
# 2. Tool 실행 함수
# ─────────────────────────────────────────────

def tool_get_user_scores(profile):
    """유닛별 평균점수, 최고점수, 풀이수, 완료율 조회"""
    practices = Practice.objects.filter(is_active=True).order_by("unit_number")
    result = []

    for practice in practices:
        total_problems = PracticeDetail.objects.filter(
            practice=practice, is_active=True, detail_type="PROBLEM"
        ).count()

        solved = UserSolvedProblem.objects.filter(
            user=profile,
            practice_detail__practice=practice,
            is_best_score=True,
        )
        stats = solved.aggregate(
            avg_score=Avg("score"),
            max_score=Max("score"),
            solved_count=Count("practice_detail", distinct=True),
        )

        avg_score = round(stats["avg_score"] or 0, 1)
        solved_count = stats["solved_count"] or 0
        completion_rate = (
            min(round(solved_count / total_problems * 100, 1), 100)
            if total_problems > 0
            else 0
        )

        result.append({
            "unit_id": practice.id,
            "unit_title": practice.title,
            "avg_score": avg_score,
            "max_score": stats["max_score"] or 0,
            "solved_count": solved_count,
            "total_problems": total_problems,
            "completion_rate": completion_rate,
        })

    return result


def tool_get_weak_points(profile, unit_id):
    """특정 유닛의 약점 분석 (점수 + AI 피드백 통합)"""
    solved_records = UserSolvedProblem.objects.filter(
        user=profile,
        practice_detail__practice_id=unit_id,
        is_best_score=True,
    ).select_related("practice_detail")

    if not solved_records.exists():
        return {"unit_id": unit_id, "message": "풀이 기록이 없습니다.", "weak_areas": []}

    metric_scores = {}
    feedback_bank = {}  # ← 피드백 저장소

    for record in solved_records:
        data = record.submitted_data or {}
        _extract_metrics(data, metric_scores, unit_id)
        _extract_feedback(data, feedback_bank, unit_id)  # ← 피드백 추출

    weak_areas = []
    all_metrics = []
    for metric, scores in metric_scores.items():
        avg = round(sum(scores) / len(scores), 1) if scores else 0
        feedback_samples = feedback_bank.get(metric, [])[:3]  # 상위 3개
        entry = {
            "metric": metric,
            "avg_score": avg,
            "sample_count": len(scores),
            "feedback_samples": feedback_samples,
        }
        all_metrics.append(entry)
        if avg < 70:
            weak_areas.append(entry)

    return {
        "unit_id": unit_id,
        "total_solved": solved_records.count(),
        "weak_areas": weak_areas,
        "all_metrics": all_metrics,
    }


def _extract_metrics(data, metric_scores, unit_id):
    """submitted_data에서 유닛별 평가 메트릭 추출"""
    if unit_id == "unit01":
        evaluation = data.get("evaluation", {})
        dimensions = evaluation.get("dimensions", {})
        for dim_name, dim_data in dimensions.items():
            if isinstance(dim_data, dict):
                score = dim_data.get("score", 0)
            else:
                score = dim_data if isinstance(dim_data, (int, float)) else 0
            normalized_dim = "edgeCase" if dim_name == "edge_case" else dim_name
            metric_scores.setdefault(normalized_dim, []).append(score)

    elif unit_id == "unit02":
        llm_eval = data.get("llm_evaluation") or {}
        for fb in llm_eval.get("step_feedbacks", []):
            step_score = fb.get("step_score")
            if isinstance(step_score, (int, float)):
                metric_scores.setdefault("디버깅_정확도", []).append(step_score)
        thinking = llm_eval.get("thinking_score")
        if isinstance(thinking, (int, float)):
            metric_scores.setdefault("사고력", []).append(thinking)
        risk = llm_eval.get("code_risk")
        if isinstance(risk, (int, float)):
            metric_scores.setdefault("코드_안전성", []).append(100 - risk)

    elif unit_id == "unit03":
        eval_result = data.get("evaluation_result", {})
        pillar_scores = eval_result.get("pillarScores", {})
        for pillar, score in pillar_scores.items():
            if isinstance(score, (int, float)):
                metric_scores.setdefault(pillar, []).append(score)


def _map_feedback_to_metric(feedback_text, unit_id):
    """
    피드백을 가장 적합한 메트릭 하나에 매핑
    중복을 방지하고 정확도를 높임
    """
    feedback_lower = feedback_text.lower()

    if unit_id == "unit01":
        # Priority order: 가장 구체적인 것부터 체크
        metric_keywords = {
            "design": ["설계", "구조", "아키텍처", "design", "flow", "step", "단계"],
            "edgeCase": ["예외", "엣지", "edge case", "corner case", "경계값", "특수"],
            "consistency": ["일관성", "누수", "데이터", "consistency", "fit", "transform", "분리"],
            "abstraction": ["추상화", "모듈", "abstraction", "개념", "개념화"],
            "implementation": ["구현", "코드", "implementation", "함수", "파라미터", "구체"],
        }
    elif unit_id == "unit02":
        metric_keywords = {
            "디버깅_정확도": ["버그", "에러", "디버그", "debug", "bug", "step", "trace"],
            "사고력": ["논리", "사고", "추론", "thinking", "reasoning", "approach"],
            "코드_안전성": ["안전", "영향", "부작용", "safe", "risk", "side effect"],
        }
    elif unit_id == "unit03":
        metric_keywords = {
            "security": ["보안", "인증", "암호", "security", "auth", "encryption"],
            "reliability": ["신뢰", "장애", "복구", "reliability", "failover", "redundancy"],
            "performance": ["성능", "캐시", "로드", "performance", "cache", "throughput"],
            "cost": ["비용", "최적", "스케일", "cost", "pricing", "resource"],
        }
    else:
        return None

    # 각 메트릭의 키워드 매치 점수 계산
    best_metric = None
    best_score = 0

    for metric, keywords in metric_keywords.items():
        score = sum(1 for kw in keywords if kw in feedback_lower)
        if score > best_score:
            best_score = score
            best_metric = metric

    return best_metric if best_score > 0 else None


def _extract_feedback(data, feedback_bank, unit_id):
    """submitted_data에서 AI 평가 피드백 추출 (중복 방지)"""
    if unit_id == "unit01":
        evaluation = data.get("evaluation", {})
        improvements = evaluation.get("improvements", [])
        if improvements:
            for improvement_text in improvements[:5]:
                if not improvement_text:
                    continue
                metric = _map_feedback_to_metric(improvement_text, unit_id)
                if metric:
                    # 이미 같은 피드백이 있는지 확인 (중복 방지)
                    if improvement_text not in feedback_bank.get(metric, []):
                        feedback_bank.setdefault(metric, []).append(improvement_text)

    elif unit_id == "unit02":
        llm_eval = data.get("llm_evaluation") or {}
        step_feedbacks = llm_eval.get("step_feedbacks", [])
        for step in step_feedbacks[:3]:
            comment = step.get("comment", "")
            if comment:
                metric = _map_feedback_to_metric(comment, unit_id)
                if metric:
                    formatted_comment = f"Step {step.get('step_number')}: {comment}"
                    if formatted_comment not in feedback_bank.get(metric, []):
                        feedback_bank.setdefault(metric, []).append(formatted_comment)

        thinking_feedback = llm_eval.get("thinking_feedback", "")
        if thinking_feedback:
            metric = _map_feedback_to_metric(thinking_feedback, unit_id)
            if metric:
                if thinking_feedback not in feedback_bank.get(metric, []):
                    feedback_bank.setdefault(metric, []).append(thinking_feedback)

    elif unit_id == "unit03":
        eval_result = data.get("evaluation_result", {})
        pillar_feedback = eval_result.get("pillarFeedback", {})
        for pillar, feedback_text in pillar_feedback.items():
            if isinstance(feedback_text, str) and feedback_text:
                if feedback_text not in feedback_bank.get(pillar, []):
                    feedback_bank.setdefault(pillar, []).append(feedback_text)


def tool_get_recent_activity(profile, limit=10):
    """최근 학습 활동 N건 조회"""
    records = (
        UserSolvedProblem.objects.filter(user=profile)
        .select_related("practice_detail__practice")
        .order_by("-solved_date")[:limit]
    )

    return [
        {
            "problem_id": r.practice_detail_id,
            "problem_title": r.practice_detail.detail_title,
            "unit_title": r.practice_detail.practice.title,
            "score": r.score,
            "is_perfect": r.is_perfect,
            "solved_date": r.solved_date.strftime("%Y-%m-%d %H:%M"),
            "attempt": r.attempt_number,
        }
        for r in records
    ]


def tool_recommend_next_problem(profile, unit_id=None):
    """안 풀었거나 낮은 점수 문제 추천"""
    details_qs = PracticeDetail.objects.filter(is_active=True, detail_type="PROBLEM")
    if unit_id:
        details_qs = details_qs.filter(practice_id=unit_id)

    mastered_ids = set(
        UserSolvedProblem.objects.filter(
            user=profile, is_best_score=True, score__gte=70
        ).values_list("practice_detail_id", flat=True)
    )

    # best score를 한 번에 조회 (N+1 → 1 쿼리)
    best_scores = dict(
        UserSolvedProblem.objects.filter(
            user=profile, is_best_score=True
        ).values_list("practice_detail_id", "score")
    )

    recommendations = []
    for detail in details_qs.select_related("practice").order_by("practice__unit_number", "display_order"):
        if detail.id in mastered_ids:
            continue
        best_score = best_scores.get(detail.id)
        recommendations.append({
            "problem_id": detail.id,
            "problem_title": detail.detail_title,
            "unit_id": detail.practice_id,
            "unit_title": detail.practice.title,
            "current_best_score": best_score,
            "status": "재도전 필요" if best_score is not None else "미풀이",
        })
        if len(recommendations) >= 5:
            break

    return recommendations if recommendations else [{"message": "모든 문제를 70점 이상으로 완료했습니다!"}]


# ─────────────────────────────────────────────
# 3. 학습 데이터 (Compare v2의 UNIT_CURRICULUM, STUDY_GUIDE_MAP)
# ─────────────────────────────────────────────

UNIT_CURRICULUM = {
    "unit01": {
        "name": "의사코드(Pseudo Code) 연습",
        "goal": "ML 파이프라인을 코드 없이 논리적으로 설계하는 능력 훈련",
        "core_concepts": [
            "데이터 전처리 파이프라인 (fit/transform 분리, 데이터 누수 방지)",
            "과적합 방어 (Ridge/Lasso 정규화, 교차검증)",
            "불균형 데이터 처리 (SMOTE, 평가지표 선택)",
            "피처 엔지니어링 (특성 생성/변환/선택)",
            "하이퍼파라미터 튜닝 (GridSearch, 교차검증)",
            "모델 해석성 (SHAP, 공정성 검증)",
        ],
        "skills_trained": ["논리적 설계력", "ML 개념 이해", "추상화 능력"],
        "difficulty": "중급",
        "study_tips": [
            "문제를 읽고 바로 코드를 쓰지 말고, 단계별 흐름을 먼저 정리해봐",
            "fit과 transform의 분리가 왜 중요한지 이해하는 게 핵심",
            "점수가 낮다면 '설계력(design)'과 '일관성(consistency)' 차원을 집중 개선해봐",
        ],
    },
    "unit02": {
        "name": "디버깅(Bug Hunt) 연습",
        "goal": "버그가 있는 코드를 읽고, 원인을 분석하고, 수정하는 디버깅 사고력 훈련",
        "core_concepts": [
            "TypeError / ValueError 등 타입 관련 버그",
            "로직 에러 (off-by-one, 조건문 실수)",
            "데이터 처리 버그 (인덱싱, 슬라이싱, NaN 처리)",
            "ML 파이프라인 버그 (데이터 누수, 스케일링 순서)",
            "딥러닝 학습 버그 (gradient, loss, optimizer 설정)",
        ],
        "skills_trained": ["디버깅 사고력", "코드 분석력", "버그 패턴 인식"],
        "difficulty": "초급~중급",
        "study_tips": [
            "코드를 한 줄씩 따라가며 변수 값이 어떻게 변하는지 추적하는 습관을 들여봐",
            "에러 메시지를 먼저 읽고 타입과 위치를 파악하는 게 첫 번째 스텝",
            "틀렸을 때 왜 틀렸는지 설명하는 연습이 사고력 향상에 핵심이야",
        ],
    },
    "unit03": {
        "name": "시스템 아키텍처 설계 연습",
        "goal": "클라우드 기반 시스템 아키텍처를 설계하고 트레이드오프를 분석하는 능력 훈련",
        "core_concepts": [
            "보안 (Security) — 인증, 암호화, 접근 제어",
            "신뢰성 (Reliability) — 장애 복구, 이중화, 백업",
            "성능 (Performance) — 캐싱, 로드밸런싱, 최적화",
            "비용 최적화 (Cost) — 리소스 효율, 스케일링 전략",
            "운영 우수성 (Operational Excellence) — 모니터링, CI/CD",
            "지속가능성 (Sustainability) — 에너지 효율, 장기 유지보수",
        ],
        "skills_trained": ["시스템 설계력", "트레이드오프 분석", "아키텍처 패턴 이해"],
        "difficulty": "중급~고급",
        "study_tips": [
            "하나의 정답이 아니라 각 설계의 트레이드오프를 설명하는 게 핵심",
            "pillar(기둥) 점수가 낮은 영역을 집중적으로 학습해봐",
            "실제 클라우드 아키텍처 사례를 읽어보면 감이 빨리 잡혀",
        ],
    },
}

STUDY_GUIDE_MAP = {
    "unit01": {
        "design": {
            "concept": "논리적 설계 순서",
            "guide": "문제를 읽고 바로 답을 쓰지 말고, '입력→처리→출력' 순서로 단계를 먼저 나눠봐. 각 단계에서 어떤 함수/도구를 쓸지 명시하면 설계력 점수가 올라가.",
        },
        "consistency": {
            "concept": "데이터 일관성 유지",
            "guide": "fit은 train에만, transform은 train+test 모두에 적용하는 원칙을 외워. 이 원칙만 지켜도 일관성 점수가 크게 올라.",
        },
        "abstraction": {
            "concept": "추상화 능력",
            "guide": "구현 디테일보다 '무엇을 하는지'를 먼저 서술해봐. '데이터를 정규화한다'가 아니라 '스케일 차이를 제거하여 모델 수렴 속도를 높인다'처럼 목적 중심으로 써봐.",
        },
        "edgeCase": {
            "concept": "예외 상황 처리",
            "guide": "결측값, 이상치, 클래스 불균형 같은 예외 상황을 항상 고려해봐. '만약 ~라면?' 질문을 스스로 던지는 습관이 중요해.",
        },
        "implementation": {
            "concept": "구현 구체성",
            "guide": "의사코드에서 구체적인 함수명이나 파라미터를 명시해봐. 'StandardScaler().fit(X_train)'처럼 실행 가능한 수준으로 적으면 구현력 점수가 올라.",
        },
    },
    "unit02": {
        "디버깅_정확도": {
            "concept": "버그 위치 정확히 짚기",
            "guide": "에러 메시지의 타입과 라인 번호를 먼저 확인하고, 해당 줄의 변수 타입을 추적해봐. print() 디버깅도 좋은 습관이야.",
        },
        "사고력": {
            "concept": "디버깅 논리적 사고",
            "guide": "버그를 찾을 때 '이 코드가 의도한 동작'과 '실제 동작'을 비교하는 습관을 들여봐. 왜 다른지를 설명할 수 있으면 사고력이 올라가.",
        },
        "코드_안전성": {
            "concept": "안전한 코드 수정",
            "guide": "버그를 고칠 때 다른 부분에 영향이 없는지 항상 확인해봐. 하나를 고치면서 다른 버그를 만들지 않는 게 핵심이야.",
        },
    },
    "unit03": {
        "security": {
            "concept": "보안 설계",
            "guide": "인증(Authentication)과 인가(Authorization)를 구분하고, 데이터 암호화(at rest / in transit)를 항상 고려해봐.",
        },
        "reliability": {
            "concept": "신뢰성 설계",
            "guide": "단일 장애 지점(SPOF)을 찾아 이중화/페일오버를 설계해봐. 장애가 나면 어떻게 복구할지 시나리오를 항상 생각해.",
        },
        "performance": {
            "concept": "성능 최적화",
            "guide": "캐싱, 로드밸런싱, 비동기 처리를 적절히 배치해봐. 병목 지점을 먼저 파악하는 게 핵심이야.",
        },
        "cost": {
            "concept": "비용 최적화",
            "guide": "오토스케일링, 예약 인스턴스, 서버리스 활용 등으로 비용을 줄이는 방법을 고려해봐.",
        },
    },
}

UNIT_OVERALL_TIPS = {
    "unit01": "의사코드는 '생각의 설계도'야. 코드를 쓰기 전에 논리를 정리하는 습관이 핵심이야.",
    "unit02": "디버깅은 양이 중요해. 다양한 버그 패턴을 많이 접해봐야 실력이 늘어.",
    "unit03": "시스템 설계는 정답이 없어. 각 설계의 트레이드오프를 설명하는 능력이 실력이야.",
}


def tool_get_unit_curriculum(unit_id):
    """유닛별 커리큘럼 조회"""
    curriculum = UNIT_CURRICULUM.get(unit_id)
    if not curriculum:
        return {"error": f"알 수 없는 유닛: {unit_id}"}
    return curriculum


def tool_get_study_guide(profile, unit_id):
    """약점 기반 맞춤 학습 가이드 생성"""
    weak_data = tool_get_weak_points(profile, unit_id)
    guide_map = STUDY_GUIDE_MAP.get(unit_id, {})
    weak_areas = weak_data.get("weak_areas", [])

    guides = []
    for area in weak_areas:
        metric = area["metric"]
        mapping = guide_map.get(metric)
        if mapping:
            guides.append({
                "metric": metric,
                "avg_score": area["avg_score"],
                "concept": mapping["concept"],
                "guide": mapping["guide"],
            })
        else:
            guides.append({
                "metric": metric,
                "avg_score": area["avg_score"],
                "concept": metric,
                "guide": f"{metric} 영역의 점수가 낮아. 관련 문제를 더 풀어보면서 감을 잡아보자.",
            })

    guides.sort(key=lambda g: g["avg_score"])

    return {
        "unit_id": unit_id,
        "weak_metrics": [g["metric"] for g in guides],
        "guides": guides,
        "overall_tip": UNIT_OVERALL_TIPS.get(unit_id, "꾸준히 연습하면 반드시 늘어!"),
    }


# ─────────────────────────────────────────────
# 4. Tool 디스패처 및 라벨
# ─────────────────────────────────────────────

TOOL_DISPATCH = {
    "get_user_scores": lambda profile, args: tool_get_user_scores(profile),
    "get_weak_points": lambda profile, args: tool_get_weak_points(profile, args.get("unit_id")),
    "get_recent_activity": lambda profile, args: tool_get_recent_activity(profile, args.get("limit", 10)),
    "recommend_next_problem": lambda profile, args: tool_recommend_next_problem(profile, args.get("unit_id")),
    "get_unit_curriculum": lambda profile, args: tool_get_unit_curriculum(args.get("unit_id")),
    "get_study_guide": lambda profile, args: tool_get_study_guide(profile, args.get("unit_id")),
}

TOOL_LABELS = {
    "get_user_scores": "성적 데이터 조회",
    "get_weak_points": "약점 분석",
    "get_recent_activity": "최근 활동 조회",
    "recommend_next_problem": "문제 추천",
    "get_unit_curriculum": "유닛 커리큘럼 조회",
    "get_study_guide": "맞춤 학습 가이드 생성",
}

# ─────────────────────────────────────────────
# 5. Tool 인자 검증
# ─────────────────────────────────────────────

TOOL_ARG_SCHEMA = {
    "get_user_scores": {},
    "get_weak_points": {
        "unit_id": {"required": True, "allowed": ["unit01", "unit02", "unit03"]},
    },
    "get_recent_activity": {
        "limit": {"required": False, "default": 10},
    },
    "recommend_next_problem": {
        "unit_id": {"required": False, "allowed": ["unit01", "unit02", "unit03"]},
    },
    "get_unit_curriculum": {
        "unit_id": {"required": True, "allowed": ["unit01", "unit02", "unit03"]},
    },
    "get_study_guide": {
        "unit_id": {"required": True, "allowed": ["unit01", "unit02", "unit03"]},
    },
}


def validate_and_normalize_args(fn_name, fn_args):
    """도구 인자 검증 및 기본값 적용"""
    schema = TOOL_ARG_SCHEMA.get(fn_name, {})
    normalized = dict(fn_args)
    for arg_name, rules in schema.items():
        if rules.get("required") and arg_name not in normalized:
            raise ValueError(f"[{fn_name}] 필수 인자 누락: {arg_name}")
        if arg_name in normalized and "allowed" in rules:
            if normalized[arg_name] not in rules["allowed"]:
                raise ValueError(f"[{fn_name}] 잘못된 {arg_name}: '{normalized[arg_name]}'")
        if arg_name not in normalized and "default" in rules:
            normalized[arg_name] = rules["default"]
    return normalized


# ─────────────────────────────────────────────
# 6. Intent-Tool Mapping (의도별 허용 도구)
# ─────────────────────────────────────────────

# ─────────────────────────────────────────────
# 7. 차트 데이터 생성 함수 (하이브리드: SSE 요약 + API 상세)
# ─────────────────────────────────────────────

def _determine_data_type(message):
    """사용자 메시지에서 원하는 데이터 유형 결정"""
    msg_lower = message.lower()

    # 메트릭별 (약점 분석)
    metric_keywords = {"약점", "분석", "능력", "강점", "메트릭", "문제점", "부족"}
    if any(kw in msg_lower for kw in metric_keywords):
        return "metric"

    # 시간순 (성장 추이)
    chrono_keywords = {"최근", "추이", "성장", "향상", "변화", "시간", "진행", "발전"}
    if any(kw in msg_lower for kw in chrono_keywords):
        return "chronological"

    # 문제별 (풀이 기록)
    problem_keywords = {"문제", "풀이", "실패", "도전", "시도"}
    if any(kw in msg_lower for kw in problem_keywords):
        return "problem"

    # 기본값: 단위별
    return "unit"


def _cached_call(fn, args, cache):
    """캐시가 있으면 재사용, 없으면 실행 후 저장"""
    key = f"{fn.__name__}:{json.dumps(args, sort_keys=True, ensure_ascii=False, default=str)}"
    if cache is not None and key in cache:
        return cache[key]
    result = fn(*args)
    if cache is not None:
        cache[key] = result
    return result


def _generate_metric_chart(profile, cache=None):
    """메트릭별 차트 생성 (약점 분석)"""
    try:
        # 첫 번째 약점이 있는 유닛 찾기
        for unit_id in ["unit01", "unit02", "unit03"]:
            weak_data = _cached_call(tool_get_weak_points, (profile, unit_id), cache)
            all_metrics = weak_data.get("all_metrics", [])
            if all_metrics:
                labels = [m["metric"] for m in all_metrics]
                values = [m["avg_score"] for m in all_metrics]

                return {
                    "chart_type": "radar",
                    "title": f"메트릭 분석 ({weak_data.get('unit_id', 'Unit')})",
                    "data": {
                        "labels": labels,
                        "datasets": [{
                            "label": "현재 점수",
                            "data": values,
                            "borderColor": "#4ECDC4",
                            "backgroundColor": "rgba(78, 205, 196, 0.1)",
                        }, {
                            "label": "목표 (70점)",
                            "data": [70] * len(labels),
                            "borderColor": "#FF6B6B",
                            "borderDash": [5, 5],
                        }],
                    }
                }
    except Exception as e:
        logger.warning(f"Failed to generate metric chart: {e}")

    return None


def _generate_chronological_chart(profile, cache=None):
    """시간순 차트 생성 (성장 추이)"""
    try:
        activities = _cached_call(tool_get_recent_activity, (profile,), cache)
        if activities:
            # 최근 5-10개 풀이의 점수 추이
            labels = [a["problem_title"][:15] for a in activities[-5:]]
            values = [a["score"] for a in activities[-5:]]

            return {
                "chart_type": "line",
                "title": "최근 풀이 점수 추이",
                "data": {
                    "labels": labels,
                    "datasets": [{
                        "label": "점수",
                        "data": values,
                        "borderColor": "#95E1D3",
                        "backgroundColor": "rgba(149, 225, 211, 0.1)",
                        "fill": True,
                        "tension": 0.4,
                    }],
                }
            }
    except Exception as e:
        logger.warning(f"Failed to generate chronological chart: {e}")

    return None


def _generate_problem_chart(profile, cache=None):
    """문제별 차트 생성 (풀이 기록)"""
    try:
        activities = _cached_call(tool_get_recent_activity, (profile,), cache)
        if activities:
            labels = [a["problem_title"][:12] for a in activities[-10:]]
            values = [a["score"] for a in activities[-10:]]
            colors = [
                "#FF6B6B" if v < 60 else "#FFA500" if v < 70 else "#4ECDC4" if v < 85 else "#95E1D3"
                for v in values
            ]

            return {
                "chart_type": "bar",
                "title": "풀이 기록 및 점수",
                "data": {
                    "labels": labels,
                    "datasets": [{
                        "label": "점수",
                        "data": values,
                        "backgroundColor": colors,
                        "borderColor": colors,
                        "borderWidth": 1,
                    }],
                }
            }
    except Exception as e:
        logger.warning(f"Failed to generate problem chart: {e}")

    return None


def _generate_unit_chart(profile, cache=None):
    """단위별 차트 생성 (기본값)"""
    charts = []

    try:
        scores = _cached_call(tool_get_user_scores, (profile,), cache)
        if scores:
            labels = [s["unit_title"] for s in scores]
            values = [s["avg_score"] for s in scores]
            colors = [
                "#FF6B6B" if v < 60 else "#FFA500" if v < 70 else "#4ECDC4" if v < 85 else "#95E1D3"
                for v in values
            ]

            charts.append({
                "chart_type": "bar",
                "title": "유닛별 평균 점수",
                "data": {
                    "labels": labels,
                    "datasets": [{
                        "label": "평균 점수",
                        "data": values,
                        "backgroundColor": colors,
                        "borderColor": colors,
                        "borderWidth": 1,
                    }],
                    "options": {
                        "max_value": 100,
                        "show_value": True
                    }
                }
            })

            # 완료율
            completion_rates = [s["completion_rate"] for s in scores]
            charts.append({
                "chart_type": "progress",
                "title": "유닛별 완료율",
                "data": {
                    "units": labels,
                    "completion_rates": completion_rates,
                }
            })
    except Exception as e:
        logger.warning(f"Failed to generate unit charts: {e}")

    return charts if charts else None


def generate_chart_data_summary(profile, intent_type, user_message="", cache=None):
    """
    Intent + 사용자 메시지 기반으로 동적 차트 데이터 생성 (SSE로 전달)
    cache: Agent Loop의 called_tools_cache를 받아 중복 DB 조회 방지
    """
    charts = []

    if intent_type == "A":  # 데이터 조회형
        # 사용자가 원하는 데이터 유형 결정
        data_type = _determine_data_type(user_message)

        if data_type == "metric":
            chart = _generate_metric_chart(profile, cache)
            if chart:
                charts.append(chart)
        elif data_type == "chronological":
            chart = _generate_chronological_chart(profile, cache)
            if chart:
                charts.append(chart)
        elif data_type == "problem":
            chart = _generate_problem_chart(profile, cache)
            if chart:
                charts.append(chart)
        else:
            unit_charts = _generate_unit_chart(profile, cache)
            if unit_charts:
                charts.extend(unit_charts)

    elif intent_type == "B":  # 학습 방법형
        chart = _generate_metric_chart(profile, cache)
        if chart:
            charts.append(chart)

    elif intent_type == "C":  # 동기부여형
        chart = _generate_chronological_chart(profile, cache)
        if chart:
            charts.append(chart)

    elif intent_type == "G":  # 의사결정형
        scores = _cached_call(tool_get_user_scores, (profile,), cache)
        if scores:
            charts.append({
                "chart_type": "table",
                "title": "유닛별 상세 통계",
                "data": {
                    "columns": ["유닛", "평균", "최고", "풀이수", "완료율"],
                    "rows": [
                        [
                            s["unit_title"],
                            f"{s['avg_score']:.1f}",
                            s["max_score"],
                            s["solved_count"],
                            f"{s['completion_rate']:.1f}%"
                        ]
                        for s in scores
                    ]
                }
            })

    return charts


def get_chart_details(profile, intent_type, unit_id=None):
    """
    상세 차트 데이터 (별도 API에서 호출)
    """
    details = {}

    if intent_type == "A":
        # 상세 약점 분석
        if unit_id:
            weak_data = tool_get_weak_points(profile, unit_id)
            details["weak_areas"] = weak_data.get("weak_areas", [])
            details["all_metrics"] = weak_data.get("all_metrics", [])
        else:
            # 모든 유닛의 약점 통합
            all_weak = {}
            for uid in ["unit01", "unit02", "unit03"]:
                weak_data = tool_get_weak_points(profile, uid)
                all_weak[uid] = weak_data.get("weak_areas", [])
            details["weak_by_unit"] = all_weak

    elif intent_type == "B":
        # 학습 가이드 상세
        if unit_id:
            guide_data = tool_get_study_guide(profile, unit_id)
            details["guides"] = guide_data.get("guides", [])
            details["overall_tip"] = guide_data.get("overall_tip", "")
        else:
            # 모든 유닛의 가이드
            all_guides = {}
            for uid in ["unit01", "unit02", "unit03"]:
                guide_data = tool_get_study_guide(profile, uid)
                all_guides[uid] = {
                    "guides": guide_data.get("guides", []),
                    "overall_tip": guide_data.get("overall_tip", "")
                }
            details["guides_by_unit"] = all_guides

    elif intent_type == "C":
        # 최근 활동 상세
        activities = tool_get_recent_activity(profile, limit=20)
        details["recent_activities"] = activities

    elif intent_type == "G":
        # 추천 문제 상세
        if unit_id:
            recommendations = tool_recommend_next_problem(profile, unit_id)
            details["recommendations"] = recommendations
        else:
            # 모든 유닛의 추천
            all_recs = {}
            for uid in ["unit01", "unit02", "unit03"]:
                recs = tool_recommend_next_problem(profile, uid)
                all_recs[uid] = recs
            details["recommendations_by_unit"] = all_recs

    return details


INTENT_TOOL_MAPPING = {
    "A": {
        "allowed": ["get_user_scores", "get_weak_points", "get_recent_activity"],
        "description": "데이터 조회형 - 성적, 약점 조회"
    },
    "B": {
        "allowed": ["get_weak_points", "get_study_guide", "get_unit_curriculum", "recommend_next_problem"],
        "description": "학습 방법형 - 학습 경로 및 전략 제시"
    },
    "C": {
        "allowed": ["get_recent_activity", "get_user_scores"],
        "description": "동기부여형 - 성장 데이터 및 활동 기록"
    },
    "D": {
        "allowed": [],
        "description": "범위 밖 질문 - 도구 호출 불필요"
    },
    "E": {
        "allowed": ["get_weak_points", "recommend_next_problem"],
        "description": "문제 풀이 지원형 - 약점 분석 및 다음 문제"
    },
    "F": {
        "allowed": ["get_unit_curriculum", "get_weak_points"],
        "description": "개념 설명형 - 커리큘럼 및 약점 분석"
    },
    "G": {
        "allowed": ["get_user_scores", "get_recent_activity", "recommend_next_problem"],
        "description": "의사결정형 - 성적, 활동, 추천 기반 의사결정"
    },
}
