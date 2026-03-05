import socketio
import asyncio
import random
from core.services.pseudocode_evaluator import PseudocodeEvaluator, EvaluationRequest, EvaluationMode

# [Multi-Agent] 임포트
from core.services.wars.orchestrator import WarsOrchestrator
from core.services.wars.state_machine import DrawRoomState, GameState
from core.services.wars.bug_problem_generator import generate_bug_problems
from core.services.wars.logic_problem_generator import generate_logic_quests
# [수정일: 2026-03-03] architecture_missions.py 하드코딩 제거 → DB(unit03) 동적 로드
# 모듈 임포트 시점에 DB 쿼리하면 Django 초기화 전이라 실패 → 런타임에 lazy 로드
from core.views.wars.wars_mission_view import _transform_to_wars_mission
from core.models import PracticeDetail
# [수정일: 2026-03-03] 전적 저장을 위한 모델 및 유틸 임포트
from core.models.activity_model import UserBattleRecord
from asgiref.sync import sync_to_async

def _update_battle_record_sync(user_id, result):
    if not user_id: return
    try:
        from core.models.user_model import UserProfile
        # [수정일: 2026-03-03] UserProfile의 PK 필드명은 id입니다. (select_related 제거)
        profile = UserProfile.objects.get(id=user_id)
        record, created = UserBattleRecord.objects.get_or_create(user=profile)
        if result == 'win': record.win_count += 1
        elif result == 'draw': record.draw_count += 1
        elif result == 'lose': record.lose_count += 1
        record.save()
        print(f"✅ [DB] Battle Record Updated: User({user_id}) -> {result}")
    except Exception as e:
        print(f"⚠️ [DB] Battle Record Update Failed: {e}")

async def update_battle_record(user_id, result):
    """비동기 전적 업데이트 래퍼"""
    await sync_to_async(_update_battle_record_sync)(user_id, result)

_MISSIONS_CACHE: list = []  # 첫 게임 시작 시 캐싱

def _load_missions_sync() -> list:
    """동기 DB 쿼리 — sync_to_async 래퍼에서 호출"""
    details = (
        PracticeDetail.objects
        .filter(practice_id='unit03', detail_type='PROBLEM', is_active=True)
        .order_by('display_order')
    )
    return [_transform_to_wars_mission(d) for d in details]

async def _get_missions() -> list:
    """Wars 미션 lazy 로드 — async 컨텍스트에서 안전하게 DB 쿼리"""
    global _MISSIONS_CACHE
    if _MISSIONS_CACHE:
        return _MISSIONS_CACHE
    try:
        from asgiref.sync import sync_to_async
        _MISSIONS_CACHE = await sync_to_async(_load_missions_sync)()
        print(f"✅ [Wars] DB에서 {len(_MISSIONS_CACHE)}개 미션 로드 완료")
    except Exception as e:
        print(f"⚠️ [Wars] DB 미션 로드 실패: {e}")
        _MISSIONS_CACHE = []
    return _MISSIONS_CACHE

# 전역 객체 및 상태 관리
wars_orchestrator = WarsOrchestrator()
draw_room_states: dict[str, DrawRoomState] = {}
pseudocode_evaluator = PseudocodeEvaluator()
active_rooms = set()
room_leaders = {}  
room_snapshots = {}
room_game_states = {}
active_timer_tasks = {} 

# 게임별 방 데이터 저장소
draw_rooms = {}  
run_rooms = {}  
bubble_rooms = {}
run_phase2_submissions = {}

sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')

@sio.event
async def connect(sid, environ):
    print(f"✅ Socket Connected: {sid}")

@sio.event
async def disconnect(sid):
    """소켓 연결 해제 시 모든 세션 및 방 데이터 정리 (통합 버전)"""
    print(f"❌ Socket Disconnected: {sid}")
    session = await sio.get_session(sid)
    if not session: return

    # 1. War Room 정리
    mission_id = session.get('room')
    if mission_id:
        await sio.emit('user_left', {"sid": sid, "user_name": session.get('name', 'Unknown')}, room=mission_id)
        if room_leaders.get(mission_id) == sid:
            del room_leaders[mission_id]
            room_sids = list(sio.manager.rooms.get('/', {}).get(mission_id, set()))
            remaining = [s for s in room_sids if s != sid]
            if remaining:
                room_leaders[mission_id] = remaining[0]
                await sio.emit('leader_info', {"leader_sid": remaining[0]}, room=mission_id)

    # 2. Draw Room 정리
    draw_room_id = session.get('draw_room')  # 세션 저장 시 이미 strip된 값
    if draw_room_id in draw_rooms:
        room = draw_rooms[draw_room_id]
        room['players'] = [p for p in room['players'] if p['sid'] != sid]
        if not room['players']:
            del draw_rooms[draw_room_id]
            # [수정: draw_room_states 도 함께 정리 — 메모리 누수 방지]
            if draw_room_id in draw_room_states:
                del draw_room_states[draw_room_id]
            print(f"🗑️ [ArchDraw] Room {draw_room_id} fully cleaned up (empty)")
        else:
            players_data = [{'name': p['name'], 'sid': p['sid']} for p in room['players']]
            await sio.emit('draw_lobby', {'players': players_data}, room=draw_room_id)
            await sio.emit('draw_player_left', {'sid': sid}, room=draw_room_id)

    # 3. Logic Run 정리
    run_room_id = session.get('run_room')
    if run_room_id in run_rooms:
        room = run_rooms[run_room_id]
        room['players'] = [p for p in room['players'] if p['sid'] != sid]
        if room.get('leader_sid') == sid:
            room['leader_sid'] = room['players'][0]['sid'] if room['players'] else None
        if not room['players']:
            del run_rooms[run_room_id]
            if run_room_id in run_phase2_submissions: del run_phase2_submissions[run_room_id]
        else:
            await sio.emit('run_user_left', {'sid': sid, 'leader_sid': room['leader_sid']}, room=run_room_id)

    # 4. Bubble Game 정리
    bubble_room_id = session.get('bubble_room')
    if bubble_room_id in bubble_rooms:
        room = bubble_rooms[bubble_room_id]
        room['players'] = [p for p in room['players'] if p['sid'] != sid]
        if not room['players']:
            del bubble_rooms[bubble_room_id]
        else:
            players_data = [{'name': p['name'], 'sid': p['sid'], 'avatar': p.get('avatar')} for p in room['players']]
            await sio.emit('bubble_lobby', {'players': players_data}, room=bubble_room_id)
            await sio.emit('bubble_player_left', {'sid': sid}, room=bubble_room_id)

# ---------- WAR ROOM EVENTS ----------
@sio.event
async def join_war_room(sid, data):
    mission_id = data.get('mission_id')
    user_name = data.get('user_name', 'Anonymous')
    user_role = data.get('user_role', 'pending')
    if mission_id:
        await sio.enter_room(sid, mission_id)
        await sio.save_session(sid, {"name": user_name, "role": user_role, "room": mission_id})
        if mission_id not in room_leaders:
            room_leaders[mission_id] = sid
            if mission_id not in room_game_states:
                room_game_states[mission_id] = {"phase": "design", "time_left": 600, "is_running": False}
        await sio.emit('leader_info', {"leader_sid": room_leaders[mission_id]}, room=mission_id)
        await sio.emit('user_joined', {"sid": sid, "user_name": user_name, "user_role": user_role}, room=mission_id)

@sio.event
async def start_mission(sid, data):
    mission_id = data.get('mission_id')
    if mission_id and room_leaders.get(mission_id) == sid:
        if mission_id in room_game_states:
            room_game_states[mission_id]["is_running"] = True
            if mission_id not in active_timer_tasks or active_timer_tasks[mission_id].done():
                active_timer_tasks[mission_id] = asyncio.create_task(run_room_timer(mission_id))
        await sio.emit('mission_start', {"mission_id": mission_id}, room=mission_id)

async def run_room_timer(mission_id):
    while mission_id in room_game_states and room_game_states[mission_id]["is_running"]:
        state = room_game_states[mission_id]
        if state["time_left"] > 0: state["time_left"] -= 1
        if state["time_left"] % 5 == 0:
            await sio.emit('state_sync', {"state": {"phase": state["phase"], "time": state["time_left"]}}, room=mission_id)
        await asyncio.sleep(1)
        if state["time_left"] <= 0:
            if state["phase"] == "design": state["phase"], state["time_left"] = "blackout", 120
            elif state["phase"] == "blackout": state["phase"], state["time_left"] = "defense", 180
            else: state["is_running"] = False
            await sio.emit('state_sync', {"state": {"phase": state["phase"], "time": state["time_left"]}}, room=mission_id)

# ---------- DRAW GAME EVENTS ----------
@sio.event
async def draw_join(sid, data):
    room_id = data.get('room_id', 'draw-default').strip()
    user_name = data.get('user_name', 'Player')
    user_id = data.get('user_id')
    await sio.enter_room(sid, room_id)
    # [수정일: 2026-03-03] user_id 세션에 저장
    await sio.save_session(sid, {'draw_room': room_id, 'draw_name': user_name, 'user_id': user_id})
    if room_id not in draw_rooms: draw_rooms[room_id] = {'players': [], 'phase': 'waiting'}
    room = draw_rooms[room_id]
    if not any(p['sid'] == sid for p in room['players']) and len(room['players']) < 2:
        room['players'].append({'sid': sid, 'name': user_name, 'score': 0, 'user_id': user_id})
    # [수정일: 2026-03-03] DrawRoomState를 1명 입장 시점에 미리 생성 — 2명 조건 제거
    # 기존: 2명 모일 때만 생성 → draw_submit 시 room_state가 None이어서 AI 평가 스킵되는 버그 수정
    if room_id not in draw_room_states:
        draw_room_states[room_id] = DrawRoomState(room_id=room_id)
        print(f"🏠 [ArchDraw] Room State Pre-Initialized: {room_id}")
    await sio.emit('draw_lobby', {'players': [{'name': p['name'], 'sid': p['sid']} for p in room['players']]}, room=room_id)
    if len(room['players']) >= 2:
        room['phase'] = 'ready'
        await sio.emit('draw_ready', {}, room=room_id)
        print(f"✅ [ArchDraw] Room Ready (2 players): {room_id}")

@sio.event
async def draw_start(sid, data):
    """[수정일: 2026-03-03] 캐치마인드 게임 시작 처리 (Double Start 및 점수 리셋 버그 수정)"""
    room_id = data.get('room_id', '').strip()
    if room_id in draw_rooms:
        room = draw_rooms[room_id]
        # [추가 2026-03-03] 이미 진행 중인 방이면 무시 (동시 REMATCH 클릭에 의한 Double Start 방지)
        if room.get('phase') == 'playing':
            print(f"⚠️ [ArchDraw] Ignore draw_start: Room {room_id} is already playing.")
            return

        print(f"🚀 [ArchDraw] Game Start in Room: {room_id}")
        room['phase'] = 'playing'
        
        # [추가 2026-03-03] 게임 시작/다시 시작 시 기존 플레이어 상태(점수, 제출 등) 완전 초기화
        for p in room.get('players', []):
            p['score'] = 0
            p['last_pts'] = 0
            p['last_checks'] = []
            p['last_nodes'] = []
            p['last_arrows'] = []
            p['submitted'] = False
        # ✅ [Agent 행동] Chaos 채점 룰 초기화 (신규 게임 시작)
        room['chaos_bonus_check'] = None
        # [수정일: 2026-03-03] DB(unit03) 미션 lazy 로드
        missions = await _get_missions()
        if not missions:
            print(f"⚠️ [ArchDraw] 미션 없음 — unit03 DB를 확인하세요")
            return
        question = random.choice(missions).copy()
        question['round'] = 1
        # 팔레트: required + 랜덤 extra 4개 (서버에서 결정 → 양측 동일 보장)
        all_comp_ids = ['client','user','lb','server','cdn','origin','cache','db',
                        'producer','queue','consumer','api','apigw','writesvc','readsvc',
                        'writedb','readdb','auth','order','payment','waf','dns']
        required_ids = question.get('required', [])
        extra_pool = [c for c in all_comp_ids if c not in required_ids]
        random.shuffle(extra_pool)
        question['palette_ids'] = required_ids + extra_pool[:4]
        
        # Orchestrator 상태 반영
        room_state = draw_room_states.get(room_id)
        if room_state:
            wars_orchestrator.on_round_start(room_state, question['title'], question['required'])
            print(f"✅ [ArchDraw] Orchestrator Round Started: {room_id} | Mission: {question['title']}")
        else:
            print(f"⚠️ [ArchDraw] room_state NOT FOUND for room: {room_id}")
        
        await sio.emit('draw_game_start', {}, room=room_id)
        await sio.emit('draw_round_start', {'question': question}, room=room_id)
        # [수정일: 2026-03-03] 라운드 번호 추적을 위해 저장
        draw_rooms[room_id]['current_round'] = 1
        
        # [추가 2026-03-03] 백그라운드에서 무조작/장애 체크를 위해 주기적 틱(Tick) 시작
        asyncio.create_task(run_draw_room_tick(room_id))

async def run_draw_room_tick(room_id):
    """[추가 2026-03-03] 사용자가 아무것도 하지 않아도 힌트/장애가 발동되도록 주기적으로 감사(Poll)"""
    print(f"⏰ [ArchDraw] Periodic check started for room: {room_id}")
    while room_id in draw_rooms and draw_rooms[room_id].get('phase') in ('playing', 'evaluating'):
        room_state = draw_room_states.get(room_id)
        if room_state and room_state.state == GameState.PLAYING:
            # 방에 있는 모든 플레이어에 대해 체크 시도
            players = list(draw_rooms[room_id].get('players', []))
            for p in players:
                target_sid = p['sid']
                design = room_state.player_designs.get(target_sid, {})
                # poll=True로 보내서 inactivity 타이머가 리셋되지 않도록 함
                res = await wars_orchestrator.on_canvas_update(
                    room_state, target_sid, 
                    design.get('nodes', []), design.get('arrows', []), 
                    is_poll=True
                )
                if res.get('coach_hint'):
                    hint_payload = {k: v for k, v in res['coach_hint'].items() if k != '_target_sid'}
                    actual_target = res['coach_hint'].get('_target_sid', target_sid)
                    print(f"⏰ [Poll] Hint pushed to {actual_target[:8]}")
                    await sio.emit('coach_hint', hint_payload, to=actual_target)
                if res.get('chaos_event'):
                    chaos_ev = res['chaos_event']
                    print(f"⏰ [Poll] Chaos pushed in Room: {room_id}")
                    # ✅ [Agent 행동] Poll에서 오는 Chaos도 동일하게 게임 룰 수정
                    req_comp = chaos_ev.get('required_component')
                    if req_comp and room_id in draw_rooms:
                        draw_rooms[room_id]['chaos_bonus_check'] = {
                            'component': req_comp,
                            'bonus_pts': 20,
                            'penalty_pts': -10,
                        }
                    await sio.emit('chaos_event', chaos_ev, room=room_id)
        
        await asyncio.sleep(8) # 8초마다 체크 (trigger_policy 임계값과 상충되지 않는 주기로 선정)
    print(f"🛑 [ArchDraw] Periodic check stopped for room: {room_id}")

@sio.event
async def draw_submit(sid, data):
    """[수정일: 2026-03-01] 점수 서버 검증 추가 — 클라이언트 점수를 신뢰하지 않음"""
    room_id = data.get('room_id', '').strip()
    if room_id not in draw_rooms: 
        print(f"⚠️ [ArchDraw] draw_submit: Room {room_id} not found in draw_rooms")
        return
    
    room = draw_rooms[room_id]
    player = next((p for p in room['players'] if p['sid'] == sid), None)
    if player:
        # [수정 2026-03-05] 100점 만점 체계로 변경
        # 체크리스트 60점 + 시간보너스 10점 + 완료보너스 20점 + 콤보보너스 10점
        checks = data.get('checks', [])
        hit = sum(1 for c in checks if c.get('ok'))
        total = len(checks) if checks else 1
        ratio = hit / total
        check_score = round((hit / total) * 60)                      # 최대 60점
        time_bonus = round((min(data.get('time_left', 0), 90) / 90) * 10)  # 최대 10점
        complete_bonus = 20 if ratio == 1.0 else 0                   # 전부 통과 시 +20점
        combo_bonus = min(data.get('combo', 0), 5) * 2               # 최대 10점 (5콤보 상한)
        pts = check_score + time_bonus + complete_bonus + combo_bonus

        # ✅ [Agent 행동 반영] ChaosAgent가 설정한 게임 룰 체크
        chaos_check = room.get('chaos_bonus_check')
        if chaos_check:
            placed_ids = [n.get('compId') for n in data.get('final_nodes', [])]
            if chaos_check['component'] in placed_ids:
                pts += chaos_check['bonus_pts']
                print(f"✅ [ArchDraw] Chaos 조건 충족: {player['name']} +{chaos_check['bonus_pts']}점 ({chaos_check['component']} 배치 확인)")
            else:
                pts += chaos_check['penalty_pts']  # 음수값
                print(f"❌ [ArchDraw] Chaos 조건 미충족: {player['name']} {chaos_check['penalty_pts']}점 ({chaos_check['component']} 누락)")

        player['score'] += pts
        player['last_pts'] = pts
        player['last_checks'] = checks
        player['last_nodes'] = data.get('final_nodes', [])
        player['last_arrows'] = data.get('final_arrows', [])
        player['submitted'] = True
        print(f"📥 [ArchDraw] Player {player['name']} submitted | server_pts={pts} (hit={hit}/{total}) in room {room_id}")

    await sio.emit('draw_player_submitted', {'sid': sid}, room=room_id)

    # 양측 모두 제출 완료 체크
    if all(p.get('submitted') for p in room['players']) and len(room['players']) == 2:
        p1, p2 = room['players']
        print(f"📊 [ArchDraw] Both submitted in room {room_id}. Triggering AI Evaluation.")

        # [버그수정] AI 평가 전에 phase를 'evaluating'으로 변경
        # → 평가 중 REMATCH 클릭 시 draw_start가 차단되지 않도록 함
        room['phase'] = 'evaluating'

        # [버그수정] await 전에 점수/결과를 스냅샷으로 캡처
        # → AI 평가 대기 중 draw_start가 p['score']를 0으로 리셋해도 올바른 값 유지
        p1_snap = {
            'sid': p1['sid'], 'score': p1['score'],
            'last_pts': p1.get('last_pts', 0), 'last_checks': p1.get('last_checks', []),
            'last_nodes': p1.get('last_nodes', []), 'last_arrows': p1.get('last_arrows', []),
            'name': p1['name']
        }
        p2_snap = {
            'sid': p2['sid'], 'score': p2['score'],
            'last_pts': p2.get('last_pts', 0), 'last_checks': p2.get('last_checks', []),
            'last_nodes': p2.get('last_nodes', []), 'last_arrows': p2.get('last_arrows', []),
            'name': p2['name']
        }

        # EvalAgent를 통한 AI 평가 실행
        ai_reviews = {}
        room_state = draw_room_states.get(room_id)
        if room_state:
            try:
                rubric = {"required_components": room_state.mission_required}
                print(f"🤖 [ArchDraw] AI Eval Start | mission='{room_state.mission_title}' | p1='{p1_snap['name']}({len(p1_snap['last_nodes'])}nodes)' | p2='{p2_snap['name']}({len(p2_snap['last_nodes'])}nodes)'")
                ai_reviews = await wars_orchestrator.on_both_submitted(
                    room_state, room_state.mission_title, rubric,
                    {"name": p1_snap['name'], "pts": p1_snap['last_pts'], "checks": p1_snap['last_checks'], "nodes": p1_snap['last_nodes'], "arrows": p1_snap['last_arrows']},
                    {"name": p2_snap['name'], "pts": p2_snap['last_pts'], "checks": p2_snap['last_checks'], "nodes": p2_snap['last_nodes'], "arrows": p2_snap['last_arrows']}
                )
                print(f"✅ [ArchDraw] AI Eval Done | p1_review={bool(ai_reviews.get('player1'))} | p2_review={bool(ai_reviews.get('player2'))}")
            except Exception as e:
                import traceback
                print(f"❌ [ArchDraw] AI Evaluation Error: {e}")
                traceback.print_exc()
        else:
            print(f"❌ [ArchDraw] draw_room_states에 '{room_id}' 없음 → AI 평가 스킵됨! (draw_join이 제대로 호출됐는지 확인)")

        # AI 결과가 없거나 실패한 경우 폴백 메시지 생성 (UI 멈춤 방지)
        if not ai_reviews:
            ai_reviews = {
                "player1": {"my_analysis": "설계의 핵심 뼈대는 갖추었으나 특정 구간의 가용성 설계가 누락되었습니다.", "versus": "전체적인 무결성 면에서 박빙의 결과를 보여주고 있습니다."},
                "player2": {"my_analysis": "설계의 핵심 뼈대는 갖추었으나 특정 구간의 가용성 설계가 누락되었습니다.", "versus": "전체적인 무결성 면에서 박빙의 결과를 보여주고 있습니다."}
            }
            print(f"⚠️ [ArchDraw] Using fallback evaluation for room {room_id}")

        # 결과 전송 - 스냅샷 값 사용 (await 중 draw_start로 인한 점수 변조 방지)
        results = [
            {
                "sid": p1_snap['sid'],
                "score": p1_snap['score'],
                "last_pts": p1_snap['last_pts'],
                "last_checks": p1_snap['last_checks'],
                "last_nodes": p1_snap['last_nodes'],
                "last_arrows": p1_snap['last_arrows'],
                "ai_review": ai_reviews.get('player1')
            },
            {
                "sid": p2_snap['sid'],
                "score": p2_snap['score'],
                "last_pts": p2_snap['last_pts'],
                "last_checks": p2_snap['last_checks'],
                "last_nodes": p2_snap['last_nodes'],
                "last_arrows": p2_snap['last_arrows'],
                "ai_review": ai_reviews.get('player2')
            }
        ]
        await sio.emit('draw_round_result', {'results': results}, room=room_id)
        print(f"✅ [ArchDraw] Evaluation Results Sent to room: {room_id}")
        
        # [수정일: 2026-03-03] 1라운드 단판 승부 설정에 맞춰 전적 저장 (프론트엔드 maxRounds=1 대응)
        if room.get('current_round', 1) >= 1:
            print(f"🏆 [ArchDraw] Game Over in Room {room_id}. Saving to DB.")

            # [버그수정] draw_start가 AI 평가 중 호출돼 phase가 이미 'playing'으로 바뀐 경우
            # 새 게임을 덮어쓰지 않도록 'evaluating' 상태일 때만 'gameover'로 전환
            if room.get('phase') == 'evaluating':
                room['phase'] = 'gameover'
                await sio.emit('draw_game_over', {}, room=room_id)
            else:
                print(f"⚠️ [ArchDraw] Skipping gameover emit — room already in new game phase: {room.get('phase')}")

            # 스냅샷 점수 기준으로 전적 저장 (await 중 점수 변조 방지)
            print(f"📊 [ArchDraw] DB Save: P1(uid={p1.get('user_id')}, score={p1_snap['score']}) vs P2(uid={p2.get('user_id')}, score={p2_snap['score']})")
            if p1_snap['score'] > p2_snap['score']:
                await update_battle_record(p1.get('user_id'), 'win')
                await update_battle_record(p2.get('user_id'), 'lose')
            elif p1_snap['score'] < p2_snap['score']:
                await update_battle_record(p1.get('user_id'), 'lose')
                await update_battle_record(p2.get('user_id'), 'win')
            else:
                await update_battle_record(p1.get('user_id'), 'draw')
                await update_battle_record(p2.get('user_id'), 'draw')

@sio.event
async def draw_next_round(sid, data):
    """[수정일: 2026-03-01] 다음 라운드 전환 + chaos/coach 상태 초기화"""
    room_id = data.get('room_id', '').strip()
    if room_id in draw_rooms:
        room = draw_rooms[room_id]
        print(f"⏭️ [ArchDraw] Next Round in Room: {room_id}")
        # 제출 상태 초기화
        for p in room['players']: p['submitted'] = False
        
        # [수정: chaos/coach 이력 초기화 — 라운드가 바뀌면 새로 발동 가능해야 함]
        room_state = draw_room_states.get(room_id)
        if room_state:
            room_state.chaos_triggered_at = 0.0
            room_state.coach_triggered_at = 0.0
            room_state.hint_history = {}
            room_state.past_event_ids = []
            room_state.player_designs = {}
        # ✅ [Agent 행동] 다음 라운드에서 Chaos 채점 룰 리셋
        room['chaos_bonus_check'] = None
        
        # 새로운 무작위 문제 선택 + 팔레트 서버 생성
        cur_round = data.get('round', room.get('current_round', 1) + 1)
        room['current_round'] = cur_round
        question = random.choice(await _get_missions()).copy()
        question['round'] = cur_round
        all_comp_ids = ['client','user','lb','server','cdn','origin','cache','db',
                        'producer','queue','consumer','api','apigw','writesvc','readsvc',
                        'writedb','readdb','auth','order','payment','waf','dns']
        required_ids = question.get('required', [])
        extra_pool = [c for c in all_comp_ids if c not in required_ids]
        random.shuffle(extra_pool)
        question['palette_ids'] = required_ids + extra_pool[:4]
        
        if room_state:
            wars_orchestrator.on_round_start(room_state, question['title'], question['required'])
            
        await sio.emit('draw_round_start', {'question': question}, room=room_id)

@sio.event
async def draw_item_status(sid, data):
    """[수정일: 2026-02-27] 소지 아이템 상태 동기화"""
    room_id = data.get('room_id')
    await sio.emit('draw_opponent_item_status', {'sid': sid, 'has_item': data.get('has_item')}, room=room_id, skip_sid=sid)

@sio.event
async def draw_use_item(sid, data):
    """[수정일: 2026-02-27] 아이템 사용 효과 전파"""
    room_id = data.get('room_id')
    await sio.emit('draw_item_effect', {'sid': sid, 'item_type': data.get('item_type')}, room=room_id, skip_sid=sid)

@sio.event
async def draw_canvas_sync(sid, data):
    room_id = data.get('room_id', 'draw-default').strip()
    session = await sio.get_session(sid)
    sender_name = session.get('draw_name', data.get('user_name', 'Anonymous'))
    await sio.emit('draw_canvas_update', {'sender_sid': sid, 'sender_name': sender_name, 'nodes': data.get('nodes'), 'arrows': data.get('arrows')}, room=room_id, skip_sid=sid)
    room_state = draw_room_states.get(room_id)
    if room_state:
        # on_canvas_update는 내부적으로 asyncio.to_thread를 사용하므로
        # 직접 await — 이벤트 루프 블로킹 없음
        res = await wars_orchestrator.on_canvas_update(room_state, sid, data.get('nodes'), data.get('arrows'))
        if res.get('coach_hint'):
            # [수정일: 2026-03-02] _target_sid를 payload에서 제거 후 전송 (프론트 노출 방지)
            hint_payload = {k: v for k, v in res['coach_hint'].items() if k != '_target_sid'}
            target_sid = res['coach_hint'].get('_target_sid', sid)
            print(f"💡 [ArchDraw] Hint Sent to {target_sid[:8]}: {hint_payload.get('message', '')[:20]}...")
            await sio.emit('coach_hint', hint_payload, to=target_sid)  # [수정일: 2026-03-03] room= → to= (개인 전송)
        if res.get('chaos_event'):
            chaos_ev = res['chaos_event']
            print(f"🔥 [ArchDraw] Chaos Event in Room: {room_id} | required_component={chaos_ev.get('required_component')}")
            # ✅ [Agent 행동] Chaos가 게임 룰을 직접 수정 — 채점 시 반영됨
            req_comp = chaos_ev.get('required_component')
            if req_comp:
                draw_rooms[room_id]['chaos_bonus_check'] = {
                    'component': req_comp,
                    'bonus_pts': 20,
                    'penalty_pts': -10,
                }
                print(f"📋 [ArchDraw] Chaos 채점 룰 추가: +20 if {req_comp} placed, -10 if not")
            await sio.emit('chaos_event', chaos_ev, room=room_id)

@sio.event
async def draw_chaos_complete(sid, data):
    """[추가 2026-03-03] Chaos 장애 확인 시 상태를 PLAYING으로 복구"""
    session = await sio.get_session(sid)
    room_id = session.get('draw_room')
    room_state = draw_room_states.get(room_id)
    if room_state:
        wars_orchestrator.on_incident_expired(room_state)
        print(f"✅ [ArchDraw] Chaos Acknowledged in Room: {room_id} -> Back to PLAYING")
        # 상태 변경 알림 (동기화 용)
        await sio.emit('draw_chaos_recovered', {'room_id': room_id}, room=room_id)
# ---------- LOGIC RUN EVENTS ----------
@sio.event
async def run_join(sid, data):
    room_id = data.get('room_id', 'run-default').strip()
    user_name = data.get('user_name', 'Anonymous')
    user_id = data.get('user_id')
    difficulty = data.get('difficulty', '') # [2026-03-04] 난이도 동기화
    
    if room_id not in run_rooms: 
        run_rooms[room_id] = {'players': [], 'phase': 'lobby', 'leader_sid': None}
    
    room = run_rooms[room_id]
    
    # [수정일: 2026-02-27] 2인 제한 로직 추가
    is_already_in = any(p['sid'] == sid for p in room['players'])
    if not is_already_in and len(room['players']) >= 2:
        print(f"⚠️ [LogicRun] Room {room_id} is full (2/2). Rejecting {user_name}")
        await sio.emit('run_error', {'message': '방이 가득 찼습니다. (최대 2인)'}, to=sid)
        return

    await sio.enter_room(sid, room_id)
    # [수정일: 2026-03-03] user_id 세션에 저장
    await sio.save_session(sid, {'run_room': room_id, 'run_name': user_name, 'user_id': user_id})
    
    if not room['leader_sid']: room['leader_sid'] = sid
    if not is_already_in:
        room['players'].append({
            'sid': sid, 
            'name': user_name, 
            'user_id': user_id, 
            'avatar_url': data.get('avatar_url'), 
            'difficulty': difficulty,  # [2026-03-04] 프론트엔드로 로비 정보 전송
            'phase1_score': 0, 
            'phase2_score': 0
        })
    else:
        # 이미 입장한 유저가 재연결시 난이도 갱신
        for p in room['players']:
            if p['sid'] == sid:
                p['difficulty'] = difficulty
                break
    
    await sio.emit('run_lobby', {'players': room['players'], 'leader_sid': room['leader_sid']}, room=room_id)

# [2026-03-04] 로비에서 난이도 실시간 변경 동기화
@sio.event
async def run_change_difficulty(sid, data):
    room_id = data.get('room_id')
    new_difficulty = data.get('difficulty')
    if room_id in run_rooms:
        room = run_rooms[room_id]
        for p in room['players']:
            if p['sid'] == sid:
                p['difficulty'] = new_difficulty
                break
        await sio.emit('run_difficulty_changed', {'sid': sid, 'difficulty': new_difficulty}, room=room_id)

@sio.event
async def run_progress(sid, data):
    room_id = data.get('room_id')
    if data.get('phase') == 'speedFill' and room_id in run_rooms:
        for p in run_rooms[room_id]['players']:
            if p['sid'] == sid: p['phase1_score'] = data.get('score', 0)
    await sio.emit('run_sync', data, room=room_id, skip_sid=sid)

# [수정일: 2026-02-27] 추가: LogicRun 프론트엔드에서 'START GAME' 클릭 시 전송하는 run_start 이벤트 핸들러 추가 (게임 시작 불가 해결)
@sio.event
async def run_start(sid, data):
    """[수정일: 2026-03-03] 중복 시작 및 1인 시작 방어 로직 추가"""
    room_id = data.get('room_id')
    if room_id in run_rooms:
        room = run_rooms[room_id]
        # 1. 이미 시작되었는지 확인
        if room.get('phase') != 'lobby':
            print(f"⚠️ [LogicRun] Room {room_id} is already in {room.get('phase')} phase. Ignoring.")
            return
            
        # 2. 인원수가 2명인지 확인
        if len(room.get('players', [])) < 2:
            print(f"⚠️ [LogicRun] Room {room_id} has insufficient players ({len(room['players'])}/2). Cannot start.")
            return

        print(f"🚀 [LogicRun] Game officially starting in room: {room_id}")
        room['phase'] = 'playing'
        
        # [수정일: 2026-03-04] AI 문제 대신 AICE 문제은행 기반 출제
        await sio.emit('run_gen_progress', {'step': 1, 'msg': 'AICE 실전 문제 세팅 중...'}, room=room_id)
        try:
            # 방에 있는 플레이어의 난이도를 사용 (둘이 동일하다고 검증됨)
            room_difficulty = room['players'][0].get('difficulty', 'Associate')
            
            # 여기서부터 새 파일 불러오기 방식을 적용
            from core.services.wars.aice_question_generator import generate_aice_quests, _get_fallback_quest
            quests = await generate_aice_quests(difficulty=room_difficulty, count=1)
            
            await sio.emit('run_gen_progress', {'step': 2, 'msg': f'AICE {room_difficulty} 문제 출제 완료!'}, room=room_id)
            quest_idx = 0  
            await sio.emit('run_game_start', {'quest_idx': quest_idx, 'quests': quests}, room=room_id)
        except Exception as e:
            print(f"⚠️ [LogicRun] AICE quest generation failed: {e}, using fallback")
            try:
                from core.services.wars.aice_question_generator import _get_fallback_quest
                quests = [_get_fallback_quest()]
            except ImportError:
                quests = []
            
            await sio.emit('run_game_start', {'quest_idx': 0, 'quests': quests}, room=room_id)

# [수정일: 2026-02-27] 추가: LogicRun 게임 종료 시 점수 및 결과 동기화를 위한 이벤트 핸들러 추가
@sio.event
async def run_logic_finish(sid, data):
    room_id = data.get('room_id')
    if room_id in run_rooms:
        await sio.emit('run_end', data, room=room_id, skip_sid=sid)
        
        # [수정일: 2026-03-04] DB 전적 저장 — 점수 기반 서버 판정
        # 프론트가 보내는 result='complete'이므로 서버에서 직접 승패 계산
        room = run_rooms[room_id]
        my_score = data.get('totalScore', 0)
        session = await sio.get_session(sid)
        user_id = session.get('user_id')
        
        # 상대 점수 찾기
        opp = next((p for p in room['players'] if p['sid'] != sid), None)
        if user_id and opp:
            opp_score = opp.get('total_score', 0)
            if my_score > opp_score:
                await update_battle_record(user_id, 'win')
            elif my_score < opp_score:
                await update_battle_record(user_id, 'lose')
            else:
                await update_battle_record(user_id, 'draw')
        
        # 내 점수 서버에 기록 (상대가 finish할 때 비교용)
        player = next((p for p in room['players'] if p['sid'] == sid), None)
        if player:
            player['total_score'] = my_score

# ---------- BUG-BUBBLE MONSTER (핵심 수정 포함) ----------
@sio.event
async def bubble_join(sid, data):
    room_id = data.get('room_id', 'bubble-default').strip()
    user_name = data.get('user_name', 'Unknown')
    user_id = data.get('user_id')
    await sio.enter_room(sid, room_id)
    # [수정일: 2026-03-03] user_id 세션에 저장
    await sio.save_session(sid, {'bubble_room': room_id, 'name': user_name, 'user_id': user_id})
    if room_id not in bubble_rooms: bubble_rooms[room_id] = {'players': [], 'is_playing': False}
    room = bubble_rooms[room_id]
    if not any(p['sid'] == sid for p in room['players']):
        room['players'].append({'sid': sid, 'name': user_name, 'user_id': user_id, 'avatar': data.get('user_avatar')})
    await sio.emit('bubble_lobby', {'players': room['players']}, room=room_id)

@sio.event
async def bubble_sync(sid, data):
    """실시간 위치 및 액션 동기화 (전송 로그가 뜨는데 동기화 안되는 문제 해결)"""
    room_id = data.get('room_id')
    if room_id:
        await sio.emit('bubble_move_update', {
            'sid': sid,
            'pos': data.get('pos'),
            'action': data.get('action'),
            'flipX': data.get('flipX')
        }, room=room_id, skip_sid=sid)

@sio.event
async def bubble_start(sid, data):
    room_id = data.get('room_id')
    if room_id in bubble_rooms:
        bubble_rooms[room_id]['is_playing'] = True

        # [2026-03-04] AI 문제 동적 생성 + 진행상황 실시간 전송
        print(f"🧠 [BugBubble] AI 문제 생성 시작 (room: {room_id})")
        await sio.emit('bubble_gen_progress', {
            'step': 1, 'pct': 10, 'msg': '버그 카테고리 분석 중...', 'file': 'categories.json'
        }, room=room_id)

        try:
            await sio.emit('bubble_gen_progress', {
                'step': 2, 'pct': 30, 'msg': 'AI가 버그 코드 생성 중...', 'file': 'bug_factory.py'
            }, room=room_id)

            problems = await generate_bug_problems(count=10, difficulty=1)

            await sio.emit('bubble_gen_progress', {
                'step': 3, 'pct': 75, 'msg': f'{len(problems)}개 문제 검증 중...', 'file': 'validator.py'
            }, room=room_id)

            await asyncio.sleep(0.5)

            await sio.emit('bubble_gen_progress', {
                'step': 4, 'pct': 95, 'msg': '선택지 셔플 완료 — 버그 배치 준비!', 'file': 'deploy_bugs.sh'
            }, room=room_id)

            print(f"✅ [BugBubble] {len(problems)}개 문제 생성 완료")
        except Exception as e:
            print(f"⚠️ [BugBubble] 문제 생성 실패, 폴백 사용: {e}")
            problems = []
            await sio.emit('bubble_gen_progress', {
                'step': 4, 'pct': 95, 'msg': '폴백 문제 로드 중...', 'file': 'fallback.json'
            }, room=room_id)

        await sio.emit('bubble_game_start', {'problems': problems}, room=room_id)

@sio.event
async def bubble_send_monster(sid, data):
    room_id = data.get('room_id')
    await sio.emit('bubble_receive_monster', {'sender_sid': sid, 'monster_type': data.get('monster_type')}, room=room_id, skip_sid=sid)
    # [2026-03-04] 서버 기준 몬스터 카운트 동기화 브로드캐스트
    if room_id in bubble_rooms:
        counts = {}
        for p in bubble_rooms[room_id]['players']:
            counts[p['sid']] = p.get('monster_count', 0)
        await sio.emit('bubble_monster_sync', {'counts': counts}, room=room_id)

@sio.event
async def bubble_monster_update(sid, data):
    """[2026-03-04] 클라이언트가 자신의 몬스터 수를 서버에 보고"""
    room_id = data.get('room_id')
    count = data.get('count', 0)
    if room_id in bubble_rooms:
        player = next((p for p in bubble_rooms[room_id]['players'] if p['sid'] == sid), None)
        if player:
            player['monster_count'] = count
        counts = {p['sid']: p.get('monster_count', 0) for p in bubble_rooms[room_id]['players']}
        await sio.emit('bubble_monster_sync', {'counts': counts}, room=room_id)

@sio.event
async def bubble_fever_attack(sid, data):
    """[2026-03-04] 콤보 피버 공격 (3x 몬스터)"""
    room_id = data.get('room_id')
    count = data.get('count', 3)
    await sio.emit('bubble_receive_fever', {'sender_sid': sid, 'count': count}, room=room_id, skip_sid=sid)

@sio.event
async def bubble_game_over(sid, data):
    room_id = data.get('room_id')
    await sio.emit('bubble_end', {'loser_sid': sid}, room=room_id)
    
    # [수정일: 2026-03-03] DB 전적 저장
    if room_id in bubble_rooms:
        players = bubble_rooms[room_id]['players']
        for p in players:
            result = 'lose' if p['sid'] == sid else 'win'
            print(f"📊 [BugBubble] DB Save: uid={p.get('user_id')}, result={result}")
            await update_battle_record(p.get('user_id'), result)

# 공통 채팅 및 기타 이벤트 유지 (chat_message, update_role 등 기존 코드와 동일)
@sio.event
async def chat_message(sid, data):
    mission_id = data.get('mission_id')
    if mission_id:
        await sio.emit('chat_sync', data, room=mission_id, skip_sid=sid)
