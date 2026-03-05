"""
orchestrator/nodes.py — OrchestratorAgent LangGraph 노드 정의

[수정 이력]
  2026-03-02  전면 개선
    - observe_game_state: 화살표 연결 정보 + 아키텍처 이슈 패턴 감지 추가
    - decide_action: 하드가드 기준을 trigger_policy 상수와 일치
    - _llm_decide: 프롬프트에 아키텍처 맥락 + 교육 철학 추가
    - _rule_based_action_plan: trigger_policy 함수로 교체 (중복 로직 제거)
"""

import json
import logging
import time
from typing import Dict, Any, List

from django.conf import settings

try:
    import openai
except ImportError:
    openai = None

from core.services.wars.agents.orchestrator.state import OrchestratorState
from core.services.wars.trigger_policy import (
    can_trigger_coach,
    can_trigger_chaos,
    _ROUND_START_GRACE,
    _CHAOS_MIN_NODES,
)

logger = logging.getLogger(__name__)


def _get_client():
    if openai and getattr(settings, "OPENAI_API_KEY", None):
        return openai.OpenAI(api_key=settings.OPENAI_API_KEY)
    return None


# ─────────────────────────────────────────────────────────────────────────────
# 아키텍처 취약점 패턴 — observe 단계에서 룰 기반으로 사전 감지
# ─────────────────────────────────────────────────────────────────────────────

_ARCH_PATTERNS = [
    {"need": {"db"}, "missing": {"readdb", "writedb", "cache"},
     "label": "DB 단일 장애점(SPOF) — Read Replica 또는 Cache 없음"},
    {"need": {"server"}, "missing": {"lb"},
     "label": "LB 없음 — 서버 직접 노출, 트래픽 분산 불가"},
    {"need": {"lb", "server"}, "missing": {"cdn", "cache"},
     "label": "캐시 레이어 없음 — 모든 요청이 서버 직접 도달"},
    {"need": {"server", "api"}, "missing": {"waf", "auth"},
     "label": "보안 레이어(WAF/Auth) 없음 — 외부 공격 취약"},
    {"need": {"server"}, "missing": {"queue", "consumer"},
     "label": "비동기 처리 없음 — 서비스 강결합 구조"},
    {"need": {"writedb"}, "missing": {"readdb"},
     "label": "ReadDB 없음 — 읽기/쓰기 부하 미분리"},
]


def _detect_arch_issues(deployed_ids: set) -> list:
    """배치된 컴포넌트 기반 아키텍처 이슈 감지 (룰 기반, LLM 없음)"""
    issues = []
    for p in _ARCH_PATTERNS:
        if p["need"].issubset(deployed_ids) and not p["missing"].intersection(deployed_ids):
            issues.append(p["label"])
    return issues


# ─────────────────────────────────────────────────────────────────────────────
# Node 1: observe_game_state
# ─────────────────────────────────────────────────────────────────────────────

def observe_game_state(state: OrchestratorState) -> OrchestratorState:
    """
    [Observe] 현재 게임 상태를 인간이 읽기 쉬운 상황 요약으로 변환.
    LLM 없음 — 룰 기반으로 빠르게 요약 생성.
    """
    logger.info(
        f"[Orchestrator] ▶ observe_game_state "
        f"(room={state['room_id']}, elapsed={state['elapsed_seconds']:.0f}s)"
    )

    snapshots = state.get("player_snapshots", {})
    required = set(state.get("mission_required", []))
    hint_history = state.get("hint_history", {})

    lines = [
        f"미션: {state['mission_title']}",
        f"게임 상태: {state['game_state_name']}",
        f"경과 시간: {state['elapsed_seconds']:.0f}초",
        f"ChaosAgent 발동 여부: {'발동됨 (이번 라운드 재발동 불가)' if state.get('chaos_triggered') else '미발동'}",
        f"필수 컴포넌트 목록: {list(required)}",
    ]

    for sid, snap in snapshots.items():
        deployed = set(snap.get("deployed_nodes", []))
        missing = list(required - deployed)
        history = hint_history.get(sid, [])
        last_hint_level = history[-1].get("level", 0) if history else 0
        last_hint_time = history[-1].get("_time", 0) if history else 0
        seconds_since_hint = round(time.time() - last_hint_time) if last_hint_time else 9999
        inactive = snap.get("seconds_inactive", 0)
        arrow_count = snap.get("arrow_count", 0)
        node_count = snap.get("node_count", 0)
        completion_pct = int(
            (len(required) - len(missing)) / max(len(required), 1) * 100
        )
        arch_issues = _detect_arch_issues(deployed)
        arrow_density = f"{arrow_count}/{node_count}" if node_count > 0 else "0/0"

        player_line = (
            f"플레이어 {sid[:8]}: "
            f"노드={node_count}개, 화살표={arrow_count}개(밀도={arrow_density}), "
            f"필수완성도={completion_pct}%, 누락={missing[:5]}, "
            f"배치된컴포넌트={list(deployed)}, "
            f"무조작={inactive:.0f}s, "
            f"힌트횟수={len(history)}, 마지막힌트레벨={last_hint_level}, "
            f"마지막힌트후={seconds_since_hint}s"
        )
        if arch_issues:
            player_line += f", ⚠️감지된아키이슈={arch_issues}"
        lines.append(player_line)

    # ✅ [Agent 행동] 두 플레이어 비교 분석 — Orchestrator가 게임 밸런싱 판단
    leading_sid = None
    trailing_sid = None
    node_gap = 0

    if len(snapshots) == 2:
        sids = list(snapshots.keys())
        n0 = snapshots[sids[0]]['node_count']
        n1 = snapshots[sids[1]]['node_count']
        node_gap = abs(n0 - n1)

        if node_gap >= 2:  # 2개 이상 차이 나면 격차 감지
            leading_sid = sids[0] if n0 > n1 else sids[1]
            trailing_sid = sids[1] if n0 > n1 else sids[0]
            lines.append(
                f"⚠️ 설계 격차 감지: {node_gap}개 차이 — "
                f"선두={leading_sid[:8]}, 지연={trailing_sid[:8]}"
            )

    summary = "\n".join(lines)
    logger.info(f"[Orchestrator] 상황 요약:\n{summary}")
    return {
        **state,
        "situation_summary": summary,
        "leading_sid": leading_sid,
        "trailing_sid": trailing_sid,
        "node_gap": node_gap,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Node 2: decide_action
# ─────────────────────────────────────────────────────────────────────────────

def decide_action(state: OrchestratorState) -> OrchestratorState:
    """
    [Think] 상황 요약을 보고 최적 행동 결정.

    하드가드는 trigger_policy 상수(_ROUND_START_GRACE, _CHAOS_MIN_NODES)와 동기화.
    LLM 있을 때: 전체 맥락 분석 후 행동 계획 JSON 반환
    LLM 없을 때: trigger_policy 함수로 폴백
    """
    logger.info("[Orchestrator] ▶ decide_action 노드 실행")

    client = _get_client()

    # ── 하드 가드 1: 게임 상태 체크 ──────────────────────────────────────────
    if state["game_state_name"] != "playing":
        logger.info(f"[Orchestrator] 게임 상태 {state['game_state_name']} → 행동 없음")
        return {**state, "action_plan": [
            {"agent": "none", "sid": None, "reason": f"게임 상태가 {state['game_state_name']}"}
        ]}

    # ── 하드 가드 2: 초반 자유 탐색 보장 ────────────────────────────────────
    if state["elapsed_seconds"] < _ROUND_START_GRACE:
        logger.info(f"[Orchestrator] {state['elapsed_seconds']:.0f}초 미경과 → 자유 탐색 중")
        return {**state, "action_plan": [
            {"agent": "none", "sid": None, "reason": f"초반 {_ROUND_START_GRACE}초 자유 탐색 보장"}
        ]}

    if not client:
        plan = _rule_based_action_plan(state)
        return {**state, "action_plan": plan}

    try:
        plan = _llm_decide(state)
    except Exception as e:
        logger.error(f"[Orchestrator] decide_action LLM 실패: {e} → 룰 기반 폴백")
        plan = _rule_based_action_plan(state)

    logger.info(f"[Orchestrator] 행동 계획: {plan}")
    return {**state, "action_plan": plan}


def _llm_decide(state: OrchestratorState) -> List[Dict[str, Any]]:
    """LLM 기반 행동 결정."""
    snapshots = state.get("player_snapshots", {})
    hint_history = state.get("hint_history", {})

    player_info = []
    total_nodes = 0
    for sid, snap in snapshots.items():
        history = hint_history.get(sid, [])
        last_hint_time = history[-1].get("_time", 0) if history else 0
        seconds_since_hint = round(time.time() - last_hint_time) if last_hint_time else 9999
        node_count = snap.get("node_count", 0)
        total_nodes += node_count
        deployed = set(snap.get("deployed_nodes", []))
        arch_issues = _detect_arch_issues(deployed)

        player_info.append({
            "sid": sid[:8],
            "full_sid": sid,
            "node_count": node_count,
            "arrow_count": snap.get("arrow_count", 0),
            "deployed_components": snap.get("deployed_nodes", []),
            "seconds_inactive": snap.get("seconds_inactive", 0),
            "hint_count": len(history),
            "last_hint_level": history[-1].get("level", 0) if history else 0,
            "seconds_since_last_hint": seconds_since_hint,
            "arch_issues_detected": arch_issues,
        })

    # ✅ 격차 정보 추출
    leading_sid = state.get('leading_sid')
    trailing_sid = state.get('trailing_sid')
    node_gap = state.get('node_gap', 0)
    gap_context = ""
    if leading_sid and trailing_sid:
        gap_context = f"""
[실시간 격차 감지]
{leading_sid[:8]}가 {trailing_sid[:8]}보다 {node_gap}개 앞서있습니다.
→ 뒤캘지는 플레이어({trailing_sid[:8]})에게 Coach 우선 개입을 고려하세요.
→ 앞선 플레이어({leading_sid[:8]})에게는 Chaos 발동으로 역전 기회를 부여하는 것을 고려하세요.
"""

    response = _get_client().chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": f"""당신은 아키텍처 교육 게임의 Orchestrator AI입니다.
플레이어의 실시간 설계 과정을 관찰하고, 언제 어떤 에이전트를 개입시킬지 판단합니다.

## 교육 철학
- CoachAgent(힌트)는 플레이어가 진짜로 헤매고 있을 때만 개입합니다.
  단순히 '아직 다 안 했다'는 이유로 바로 힌트를 주면 스스로 생각할 기회를 빼앗습니다.
- ChaosAgent(장애 이벤트)는 플레이어가 어느 정도 설계를 완성한 상태에서 발동합니다.
  아무것도 없는 캔버스에 장애를 내보내는 건 의미가 없습니다.

## 각 에이전트 선택 기준
- coach:
  * 25초 이상 아무 조작 없이 멈춰있을 때 (무조작 기준)
  * 30초 이상 지났는데 노드가 1개 이하일 때
  * 35초 이상 지났는데 필수 컴포넌트 절반 이상 누락일 때
  * ⚠️ 해당 플레이어 본인이 힌트를 받은 지 45초 미만인 경우만 금지 (플레이어별 개별 쿨다운)

- chaos:
  * 총 배치 노드(두 플레이어 합계)가 {_CHAOS_MIN_NODES}개 이상일 때 발동 가능
  * 게임의 긴장감을 위해 조건 충족 시 가급적 적절한 시점에 발동시킵니다.
  * chaos_triggered가 True이면 절대 선택 불가

- none: 위 조건 미충족 시.

JSON 배열로만 응답합니다.""",
            },
            {
                "role": "user",
                "content": f"""[현재 게임 상황]
{state.get('situation_summary', '')}

[플레이어 상세 데이터]
{json.dumps(player_info, ensure_ascii=False, indent=2)}
{gap_context}
[핵심 제약]
- chaos_triggered: {state.get('chaos_triggered')} → True면 chaos 절대 불가
- 전체 배치 노드 합계: {total_nodes}개 → {_CHAOS_MIN_NODES}개 미만이면 chaos 불가
- 경과 시간: {state['elapsed_seconds']:.0f}초

출력 형식 (JSON만):
{{
  "actions": [
    {{"agent": "coach", "sid": "full_sid값", "reason": "판단 근거"}},
    {{"agent": "chaos", "sid": null, "reason": "판단 근거"}}
  ]
}}

아무것도 안 할 경우:
{{
  "actions": [{{"agent": "none", "sid": null, "reason": "이유"}}]
}}""",
            },
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
        timeout=8,
    )

    content = response.choices[0].message.content
    parsed = json.loads(content)

    if isinstance(parsed, dict):
        plan = parsed.get("actions", parsed.get("plan", []))
        if not plan and parsed:
            first_val = list(parsed.values())[0]
            plan = first_val if isinstance(first_val, list) else []
        if not plan:
            plan = [parsed] if parsed.get("agent") else [
                {"agent": "none", "sid": None, "reason": "LLM 응답 파싱 불가"}
            ]
    else:
        plan = parsed if isinstance(parsed, list) else [
            {"agent": "none", "sid": None, "reason": "LLM 응답 형식 오류"}
        ]

    # ── 하드 가드 재적용 (LLM이 틀릴 경우 방어) ─────────────────────────────
    if state.get("chaos_triggered"):
        plan = [a for a in plan if a.get("agent") != "chaos"] or [
            {"agent": "none", "sid": None, "reason": "chaos 이미 발동됨"}
        ]

    if total_nodes < _CHAOS_MIN_NODES:
        plan = [a for a in plan if a.get("agent") != "chaos"] or [
            {"agent": "none", "sid": None, "reason": f"총 노드 {total_nodes}개 — chaos 최소 {_CHAOS_MIN_NODES}개 필요"}
        ]

    logger.info(f"[Orchestrator] LLM 판단 결과: {plan}")
    return plan


def _rule_based_action_plan(state: OrchestratorState) -> List[Dict[str, Any]]:
    """
    LLM 없을 때 폴백 — trigger_policy 함수 직접 사용.
    기존의 StateMachine 임시 객체 생성 우회 코드를 제거하고,
    trigger_policy가 노출하는 함수를 직접 호출한다.
    """
    from core.services.wars.state_machine import DrawRoomState as _DrawRoomState, GameState

    trigger_sid = state.get("trigger_sid", "")
    snapshots = state.get("player_snapshots", {})
    hint_history = state.get("hint_history", {})
    elapsed = state["elapsed_seconds"]

    # trigger_policy 함수가 DrawRoomState를 요구하므로 최소 임시 객체 생성
    # (StateMachine 메서드 직접 호출 제거 — trigger_policy만 의존)
    tmp_room = _DrawRoomState(room_id=state.get("room_id", ""))
    try:
        tmp_room.state = GameState(state["game_state_name"])
    except ValueError:
        tmp_room.state = GameState.PLAYING

    tmp_room.entered_at = time.time() - elapsed
    tmp_room.mission_required = state.get("mission_required", [])
    tmp_room.hint_history = hint_history
    tmp_room.chaos_triggered_at = 1.0 if state.get("chaos_triggered") else 0.0

    all_hints = [h for hs in hint_history.values() for h in hs]
    tmp_room.coach_triggered_at = max(
        (h.get("_time", 0) for h in all_hints), default=0.0
    )

    tmp_room.player_designs = {}
    for sid, snap in snapshots.items():
        deployed = snap.get("deployed_nodes", [])
        last_inactive = snap.get("seconds_inactive", 0)
        tmp_room.player_designs[sid] = {
            "node_count": snap.get("node_count", 0),
            "last_updated": time.time() - last_inactive,
            "nodes": [{"compId": c} for c in deployed],
        }

    plan = []

    if can_trigger_coach(tmp_room, trigger_sid):
        # ✅ [격차 반영] 뒤쳌지는 플레이어에게 Coach 우선
        target_coach_sid = state.get('trailing_sid') or trigger_sid
        plan.append({
            "agent": "coach", "sid": target_coach_sid,
            "reason": "룰 기반: 헤매는 상황 감지" + (
                f" (압도적 격차로 인한 Coach 우선)" if state.get('node_gap', 0) >= 2 else ""
            )
        })

    if can_trigger_chaos(tmp_room):
        plan.append({
            "agent": "chaos", "sid": None,
            "reason": "룰 기반: 설계 시작됨 + chaos 발동 조건 충족" + (
                f" (앞선 플레이어 {state.get('leading_sid', '')[:8]}에게 펕디쿥제)"
                if state.get('node_gap', 0) >= 2 else ""
            )
        })

    if not plan:
        plan.append({
            "agent": "none", "sid": None,
            "reason": "룰 기반: 개입 조건 미충족"
        })

    return plan


# ─────────────────────────────────────────────────────────────────────────────
# Node 3: dispatch
# ─────────────────────────────────────────────────────────────────────────────

def dispatch(state: OrchestratorState) -> OrchestratorState:
    """
    [Act] action_plan에 따라 실제 에이전트를 호출한다.
    [수정일: 2026-03-03] Coach / Chaos 동시 호출 시 병렬 실행으로 변경
    기존: Coach → Chaos 직렬 (최대 20초)
    개선: concurrent.futures.ThreadPoolExecutor로 병렬 실행 (최대 10초)
    """
    logger.info("[Orchestrator] ▶ dispatch 노드 실행")

    import concurrent.futures
    from core.services.wars.coach_agent import CoachAgent
    from core.services.wars.chaos_agent import ChaosAgent

    coach_agent = CoachAgent()
    chaos_agent = ChaosAgent()

    plan = state.get("action_plan", [])
    snapshots = state.get("player_snapshots", {})
    hint_history = state.get("hint_history", {})

    coach_hint = None
    chaos_event = None
    actions_taken = []

    # 실행할 작업 분류
    coach_action = next((a for a in plan if a.get("agent") == "coach"), None)
    chaos_action = next((a for a in plan if a.get("agent") == "chaos"), None)
    none_actions = [a for a in plan if a.get("agent") == "none"]

    for a in none_actions:
        logger.info(f"[Orchestrator] 개입 없음: {a.get('reason', '')}")

    def _run_coach(action):
        sid = action.get("sid") or state.get("trigger_sid", "")
        snap = snapshots.get(sid, {})
        history = hint_history.get(sid, [])
        hint = coach_agent.generate(
            mission_required=state["mission_required"],
            deployed_nodes=snap.get("deployed_nodes", []),
            arrow_count=snap.get("arrow_count", 0),
            node_count=snap.get("node_count", 0),
            hint_history=history,
        )
        return sid, hint, action.get("reason", "")

    def _run_chaos(action):
        all_nodes: set = set()
        for snap in snapshots.values():
            all_nodes.update(snap.get("deployed_nodes", []))
        event = chaos_agent.generate(
            mission_title=state["mission_title"],
            deployed_nodes=list(all_nodes),
            round_num=1,
            past_event_ids=state.get("past_event_ids", []),
        )
        return event, action.get("reason", "")

    # Coach 와 Chaos 를 병렬로 실행
    futures = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        if coach_action:
            futures["coach"] = executor.submit(_run_coach, coach_action)
        if chaos_action:
            futures["chaos"] = executor.submit(_run_chaos, chaos_action)

    # 결과 수집
    if "coach" in futures:
        try:
            sid, hint, reason = futures["coach"].result()
            if hint.get("message"):
                coach_hint = {**hint, "_target_sid": sid}
                actions_taken.append(f"coach→{sid[:8]} (level={hint.get('level')})")
                logger.info(
                    f"[Orchestrator] CoachAgent 완료: "
                    f"sid={sid[:8]}, level={hint.get('level')}, reason={reason}"
                )
        except Exception as e:
            logger.error(f"[Orchestrator] CoachAgent 실패: {e}")

    if "chaos" in futures:
        try:
            event, reason = futures["chaos"].result()
            chaos_event = event
            actions_taken.append(
                f"chaos: {event.get('event_id')} (severity={event.get('severity')})"
            )
            logger.info(
                f"[Orchestrator] ChaosAgent 완료: "
                f"event_id={event.get('event_id')}, reason={reason}"
            )
        except Exception as e:
            logger.error(f"[Orchestrator] ChaosAgent 실패: {e}")

    return {
        **state,
        "coach_hint": coach_hint,
        "chaos_event": chaos_event,
        "actions_taken": actions_taken,
        "dispatched": True,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Node 4: done
# ─────────────────────────────────────────────────────────────────────────────

def done(state: OrchestratorState) -> OrchestratorState:
    """결과 정리 및 로깅"""
    logger.info(
        f"[Orchestrator] ✅ 완료: room={state['room_id']}, "
        f"actions={state.get('actions_taken', [])}"
    )
    return state
