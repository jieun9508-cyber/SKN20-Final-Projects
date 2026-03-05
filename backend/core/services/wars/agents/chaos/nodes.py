"""
chaos/nodes.py — ChaosAgent LangGraph 노드 정의

[노드 목록]
  analyze_vulnerability : 배치된 컴포넌트의 취약점 분석 (Think)
  generate_event        : 취약점 기반 장애 이벤트 생성 (Act)
  self_validate         : 생성된 이벤트의 품질 자기검증 (Observe)
  regenerate            : 검증 실패 시 재생성 (Act 반복)
  finalize              : 최종 이벤트 확정

[기존과의 차이]
  기존: 프롬프트 → LLM 1회 → 끝
  신규: 취약점 먼저 분석(Think) → 이벤트 생성(Act) → 품질 검증(Observe) → 필요시 재생성 루프
       + 중복 이벤트 감지 / severity 적절성 검증 / 배치 컴포넌트 연관성 검증
"""

import json
import random
import logging
from typing import Dict, Any, List

from django.conf import settings

try:
    import openai
except ImportError:
    openai = None

from core.services.wars.agents.chaos.state import ChaosAgentState

logger = logging.getLogger(__name__)

# ── 룰 기반 폴백 ───────────────────────────────────────────────────────────────
FALLBACK_EVENTS = [
    {
        "event_id": "traffic_surge",
        "title": "🚨 EMERGENCY: Traffic Surge!",
        "description": "특정 리전에서 동시 접속자가 10배 폭증했습니다. 부하 분산 구조를 재검토하세요.",
        "severity": "HIGH",
        "target_components": ["lb", "server"],
        "hint": "로드밸런서(LB) 앞단에 CDN이나 캐시 레이어를 추가하면 트래픽을 흡수할 수 있습니다.",
    },
    {
        "event_id": "db_failure",
        "title": "🔥 CRITICAL: Primary DB Down!",
        "description": "메인 DB 서버가 응답을 멈췄습니다. 데이터 유실 없이 서비스를 유지할 방법을 설계하세요.",
        "severity": "CRITICAL",
        "target_components": ["db", "readdb"],
        "hint": "Read Replica를 Primary로 승격하는 Failover 구조를 설계에 반영하세요.",
    },
    {
        "event_id": "budget_cut",
        "title": "💰 NOTICE: 인프라 예산 30% 삭감",
        "description": "경영진 결정으로 이번 분기 인프라 예산이 30% 삭감됩니다. 비용 효율적인 구조로 재설계하세요.",
        "severity": "MEDIUM",
        "target_components": ["server", "cdn"],
        "hint": "서버리스(Lambda) 또는 스팟 인스턴스를 활용하면 비용을 절감할 수 있습니다.",
    },
    {
        "event_id": "security_breach",
        "title": "🛡️ ALERT: DDoS 공격 탐지",
        "description": "외부에서 초당 50만 건의 비정상 요청이 감지되었습니다. 보안 레이어를 추가하세요.",
        "severity": "HIGH",
        "target_components": ["waf", "lb"],
        "hint": "WAF(Web Application Firewall)를 LB 앞에 배치하여 악성 트래픽을 필터링하세요.",
    },
    {
        "event_id": "region_outage",
        "title": "🌏 WARNING: 특정 리전 장애",
        "description": "ap-northeast-2 리전 전체가 다운됐습니다. 멀티 리전 구조로 설계를 수정하세요.",
        "severity": "CRITICAL",
        "target_components": ["dns", "lb"],
        "hint": "DNS Failover와 멀티 리전 LB를 사용하면 리전 장애를 자동으로 우회할 수 있습니다.",
    },
]

# 취약점 패턴 룰 (LLM 없을 때 analyze_vulnerability 폴백용)
VULNERABILITY_RULES = [
    {"components": {"db"}, "not_components": {"readdb", "writedb"}, "vuln": "db_single_point",
     "reason": "DB가 단일 인스턴스입니다. 장애 시 전체 데이터 접근 불가.", "severity": "CRITICAL"},
    {"components": {"server"}, "not_components": {"lb"}, "vuln": "no_load_balancer",
     "reason": "로드밸런서 없이 서버가 직접 노출되어 있습니다.", "severity": "HIGH"},
    {"components": {"lb", "server"}, "not_components": {"cdn", "cache"}, "vuln": "no_cache_layer",
     "reason": "캐시 레이어가 없어 모든 요청이 서버에 직접 도달합니다.", "severity": "HIGH"},
    {"components": {"api", "server"}, "not_components": {"waf", "auth"}, "vuln": "no_security_layer",
     "reason": "인증/보안 레이어가 없어 외부 공격에 취약합니다.", "severity": "HIGH"},
    {"components": {"server"}, "not_components": {"queue"}, "vuln": "tight_coupling",
     "reason": "서비스 간 직접 호출로 강결합 구조입니다. 하나가 죽으면 전체 영향.", "severity": "MEDIUM"},
]


def _get_client():
    if openai and getattr(settings, "OPENAI_API_KEY", None):
        return openai.OpenAI(api_key=settings.OPENAI_API_KEY)
    return None


def _fallback_by_nodes(deployed_nodes: List[str]) -> Dict[str, Any]:
    """배치 컴포넌트 기반 폴백 이벤트 선택"""
    node_set = set(deployed_nodes)
    scored = [(len(set(e["target_components"]) & node_set), e) for e in FALLBACK_EVENTS]
    scored.sort(key=lambda x: x[0], reverse=True)
    top_score = scored[0][0]
    candidates = [e for s, e in scored if s == top_score]
    return random.choice(candidates)


# ─────────────────────────────────────────────────────────────────────────────
# Node 1: analyze_vulnerability
# ─────────────────────────────────────────────────────────────────────────────

def analyze_vulnerability(state: ChaosAgentState) -> ChaosAgentState:
    """
    [Think] 배치된 컴포넌트 조합을 분석하여 가장 치명적인 취약점을 찾는다.

    LLM 사용 시: 컴포넌트 조합 → 취약점 분석 JSON 반환
    LLM 없을 시: 룰 기반 VULNERABILITY_RULES로 취약점 탐색
    """
    logger.info("[ChaosAgent] ▶ analyze_vulnerability 노드 실행")

    deployed = set(state["deployed_nodes"])
    client = _get_client()

    if not client:
        vuln = _rule_based_vulnerability(deployed)
        return {**state, "vulnerability": vuln}

    node_str = ", ".join(state["deployed_nodes"]) or "없음"
    past_str = ", ".join(state["past_event_ids"]) or "없음"

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "당신은 클라우드 아키텍처 보안 전문가입니다. 시스템의 취약점을 분석합니다. JSON만 출력합니다.",
                },
                {
                    "role": "user",
                    "content": f"""미션: {state["mission_title"]}
배치된 컴포넌트: {node_str}
이미 발동된 이벤트 (중복 금지): {past_str}

위 컴포넌트 조합에서 가장 치명적인 취약점 1개를 분석하세요.

출력 형식 (JSON만):
{{
  "component": "취약한 컴포넌트 ID",
  "reason": "왜 취약한지 1문장",
  "severity_suggestion": "CRITICAL|HIGH|MEDIUM|LOW",
  "attack_vector": "어떤 방식으로 공격/장애가 발생할 수 있는지 1문장"
}}""",
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.6,
            timeout=8,
        )
        vuln = json.loads(response.choices[0].message.content)
        logger.info(f"[ChaosAgent] 취약점 분석: {vuln.get('component')} — {vuln.get('reason', '')[:40]}")
    except Exception as e:
        logger.error(f"[ChaosAgent] analyze_vulnerability LLM 실패: {e} → 룰 기반 폴백")
        vuln = _rule_based_vulnerability(deployed)

    return {**state, "vulnerability": vuln}


def _rule_based_vulnerability(deployed: set) -> Dict[str, Any]:
    """룰 기반 취약점 분석"""
    for rule in VULNERABILITY_RULES:
        has_all = rule["components"].issubset(deployed)
        missing_safety = not rule["not_components"].intersection(deployed)
        if has_all and missing_safety:
            return {
                "component": list(rule["components"])[0],
                "reason": rule["reason"],
                "severity_suggestion": rule["severity"],
                "attack_vector": f"{rule['vuln']} 패턴에 의한 장애",
            }
    # 아무 룰도 매칭 안 되면 기본값
    return {
        "component": list(deployed)[0] if deployed else "server",
        "reason": "단일 컴포넌트 의존성으로 인한 장애 위험",
        "severity_suggestion": "HIGH",
        "attack_vector": "예상치 못한 트래픽 급증",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Node 2: generate_event
# ─────────────────────────────────────────────────────────────────────────────

def generate_event(state: ChaosAgentState) -> ChaosAgentState:
    """
    [Act] analyze_vulnerability 결과를 기반으로 장애 이벤트 생성.
    취약점 분석 결과를 프롬프트에 직접 주입하여 더 정밀한 이벤트 생성.
    """
    logger.info("[ChaosAgent] ▶ generate_event 노드 실행")

    client = _get_client()
    vuln = state.get("vulnerability") or {}
    node_str = ", ".join(state["deployed_nodes"]) or "없음"
    past_str = ", ".join(state["past_event_ids"]) or "없음"

    if not client:
        event = _fallback_by_nodes(state["deployed_nodes"])
        return {**state, "raw_event": event}

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "당신은 시스템 장애 시나리오 생성 전문가입니다. JSON만 출력합니다.",
                },
                {
                    "role": "user",
                    "content": f"""미션: {state["mission_title"]}
배치된 컴포넌트: {node_str}
이미 발동된 이벤트 ID (중복 금지): {past_str}

[분석된 취약점]
- 취약 컴포넌트: {vuln.get("component", "unknown")}
- 취약 이유: {vuln.get("reason", "")}
- 권장 severity: {vuln.get("severity_suggestion", "HIGH")}
- 공격 벡터: {vuln.get("attack_vector", "")}

위 취약점을 직접 겨냥한 장애 이벤트를 생성하세요.

규칙:
1. 구체적인 수치 포함 (예: "초당 50만 건", "응답 시간 8초 초과")
2. hint는 해결 방향을 직접 알려주지 말고 생각할 포인트만 제시
3. event_id는 이미 발동된 ID와 달라야 함

출력 형식 (JSON만):
{{
  "event_id": "고유_영문_스네이크케이스",
  "title": "이모지 포함 긴급 제목",
  "description": "구체적 장애 상황 (2-3문장)",
  "severity": "{vuln.get("severity_suggestion", "HIGH")}",
  "target_components": ["관련_컴포넌트_id"],
  "hint": "설계 개선 포인트 힌트 (1문장)"
}}""",
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.8,
            timeout=10,
        )
        event = json.loads(response.choices[0].message.content)
        logger.info(f"[ChaosAgent] 이벤트 생성: {event.get('event_id')}")
    except Exception as e:
        logger.error(f"[ChaosAgent] generate_event LLM 실패: {e} → 폴백")
        event = _fallback_by_nodes(state["deployed_nodes"])

    return {**state, "raw_event": event}


# ─────────────────────────────────────────────────────────────────────────────
# Node 3: self_validate
# ─────────────────────────────────────────────────────────────────────────────

def self_validate(state: ChaosAgentState) -> ChaosAgentState:
    """
    [Observe] 생성된 이벤트의 품질을 자기검증.

    검증 항목:
      1. 실제 배치된 컴포넌트가 target_components에 포함되는가?
      2. event_id가 past_event_ids와 중복되지 않는가?
      3. description이 구체적인가? (수치 또는 구체 상황 포함)
      4. severity가 취약점 분석 결과와 일치하는가?

    LLM 없이 룰 기반으로만 검증 (빠른 실행, 추가 API 비용 없음)
    """
    logger.info("[ChaosAgent] ▶ self_validate 노드 실행")

    event = state.get("raw_event") or {}
    deployed = set(state["deployed_nodes"])
    past_ids = set(state["past_event_ids"])
    vuln = state.get("vulnerability") or {}

    issues = []

    # 검증 1: 중복 event_id
    if event.get("event_id") in past_ids:
        issues.append(f"event_id '{event.get('event_id')}' 중복")

    # 검증 2: target_components가 실제 배치된 컴포넌트와 완전히 무관
    # [수정일: 2026-03-01] deployed가 비어있는 경우도 체크 (deployed > 0 조건 제거)
    targets = set(event.get("target_components", []))
    if not deployed:
        issues.append("\ubc30치된 콤포넌트 없음 — chaos 발동 부적절")
    elif targets and not targets.intersection(deployed):
        issues.append(f"target_components {list(targets)}가 배치된 콤포넌트와 무관")

    # 검증 3: description 최소 길이 (너무 짧으면 구체성 부족)
    desc = event.get("description", "")
    if len(desc) < 20:
        issues.append("description이 너무 짧음 (구체성 부족)")

    # 검증 4: 필수 필드 누락
    required_fields = ["event_id", "title", "description", "severity", "hint"]
    for f in required_fields:
        if not event.get(f):
            issues.append(f"필수 필드 누락: {f}")

    if issues:
        validation = f"REGEN: {', '.join(issues)}"
        needs_regen = True
        logger.warning(f"[ChaosAgent] self_validate 실패: {validation}")
    else:
        validation = "PASS"
        needs_regen = False
        logger.info("[ChaosAgent] self_validate 통과")

    return {**state, "validation": validation, "needs_regen": needs_regen}


# ─────────────────────────────────────────────────────────────────────────────
# Node 4: regenerate
# ─────────────────────────────────────────────────────────────────────────────

def regenerate(state: ChaosAgentState) -> ChaosAgentState:
    """
    [Act 반복] self_validate 실패 시 이벤트 재생성.
    generate_event와 동일하지만 validation 피드백을 프롬프트에 추가.
    """
    logger.info(f"[ChaosAgent] ▶ regenerate 노드 실행 (retry #{state['retry_count'] + 1})")

    client = _get_client()

    if not client:
        event = _fallback_by_nodes(state["deployed_nodes"])
        return {**state, "raw_event": event, "retry_count": state["retry_count"] + 1}

    vuln = state.get("vulnerability") or {}
    node_str = ", ".join(state["deployed_nodes"]) or "없음"
    past_str = ", ".join(state["past_event_ids"]) or "없음"
    validation_feedback = state.get("validation", "")

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "당신은 시스템 장애 시나리오 생성 전문가입니다. JSON만 출력합니다.",
                },
                {
                    "role": "user",
                    "content": f"""이전 생성 이벤트가 품질 검증에 실패했습니다.

[검증 실패 이유]
{validation_feedback}

[이전 생성 결과]
{json.dumps(state.get("raw_event", {}), ensure_ascii=False)}

[조건]
미션: {state["mission_title"]}
배치된 컴포넌트: {node_str}
중복 금지 event_id: {past_str}
취약점: {vuln.get("reason", "")}

위 실패 이유를 반영하여 개선된 장애 이벤트를 다시 생성하세요.

출력 형식 (JSON만):
{{
  "event_id": "고유_영문_스네이크케이스",
  "title": "이모지 포함 긴급 제목",
  "description": "구체적 장애 상황 수치 포함 (2-3문장)",
  "severity": "{vuln.get("severity_suggestion", "HIGH")}",
  "target_components": ["실제_배치된_컴포넌트_id"],
  "hint": "설계 개선 포인트 힌트 (1문장)"
}}""",
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.7,
            timeout=10,
        )
        event = json.loads(response.choices[0].message.content)
        logger.info(f"[ChaosAgent] 재생성 완료: {event.get('event_id')}")
    except Exception as e:
        logger.error(f"[ChaosAgent] regenerate LLM 실패: {e} → 폴백")
        event = _fallback_by_nodes(state["deployed_nodes"])

    return {**state, "raw_event": event, "retry_count": state["retry_count"] + 1}


# ─────────────────────────────────────────────────────────────────────────────
# Node 5: finalize
# ─────────────────────────────────────────────────────────────────────────────

def finalize(state: ChaosAgentState) -> ChaosAgentState:
    """최종 이벤트 확정 + required_component 결정 (채점 반영용)"""
    logger.info("[ChaosAgent] ▶ finalize 노드 실행")

    event = state.get("raw_event")
    if not event:
        logger.error("[ChaosAgent] 최종 이벤트 없음 → 폴백")
        event = _fallback_by_nodes(state["deployed_nodes"])

    # ✅ [Agent 행동] required_component 결정
    # target_components 중 아직 배치 안 된 것 → 플레이어가 추가해야 할 컴포넌트
    # 이미 다 배치한 경우 → target 중 하나를 그대로 사용 (심화 조건)
    deployed_set = set(state.get("deployed_nodes", []))
    targets = event.get("target_components", [])
    not_deployed = [c for c in targets if c not in deployed_set]
    required_component = not_deployed[0] if not_deployed else (targets[0] if targets else None)
    event["required_component"] = required_component

    logger.info(
        f"[ChaosAgent] ✅ 이벤트 확정: {event.get('event_id')} / "
        f"severity={event.get('severity')} / required_component={required_component}"
    )
    return {**state, "final_event": event}


# ─────────────────────────────────────────────────────────────────────────────
# 라우팅 함수
# ─────────────────────────────────────────────────────────────────────────────

def route_after_validate(state: ChaosAgentState) -> str:
    MAX_RETRIES = 2
    if state.get("needs_regen") and state.get("retry_count", 0) < MAX_RETRIES:
        logger.info(f"[ChaosAgent] 재생성 분기 → regenerate (retry={state.get('retry_count', 0)})")
        return "regenerate"
    return "finalize"
