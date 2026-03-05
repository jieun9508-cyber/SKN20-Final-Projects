import { ref, onUnmounted } from 'vue'
import { io } from 'socket.io-client'

/**
 * 캐치마인드(Arch Draw) 전용 소켓 composable
 * [수정일: 2026-02-24] 2vs2 팀 모드 지원: myTeam, teammate, onTeamSync 추가
 */
export function useDrawSocket() {
  const socket = ref(null)
  const connected = ref(false)
  const roomPlayers = ref([])
  const opponentCanvas = ref({ nodes: [], arrows: [] })
  const opponentName = ref('')
  const opponentHasItem = ref(false)
  const isReady = ref(false)
  const roundQuestion = ref(null)
  const opponentSubmitted = ref(false)
  const roundResults = ref(null)

  // 이벤트 콜백
  const onGameStart = ref(null)    // [추가 2026-02-27] 게임 시작 콜백 (누락되어 있었음)
  const onRoundStart = ref(null)
  const onRoundResult = ref(null)
  const onItemEffect = ref(null)
  const onCoachHint = ref(null)    // [추가 2026-03-03] CoachAgent 힌트 수신
  const onChaosEvent = ref(null)   // [추가 2026-02-27] ChaosAgent 주도 장애 이벤트 
  const onChaosRecovered = ref(null) // [추가 2026-03-03] 장애 복구 알림
  const onGameOver = ref(null)

  function connect(roomId, userName, userId, avatarUrl) {
    if (socket.value) return

    // [수정일: 2026-03-01] 소켓 URL 결정 로직 수정
    // 기존: HTTPS이면 "" → io("")가 프론트 도메인으로 연결해서 AWS 배포 시 항상 실패
    // 수정: VITE_SOCKET_URL이 있으면 무조건 사용, 없을 때만 빈 문자열(로컬 프록시)
    const envSocketUrl = import.meta.env.VITE_SOCKET_URL;
    const socketUrl = envSocketUrl || "";

    console.log(`[Socket Debug] Protocol: ${window.location.protocol}`);
    console.log(`[Socket Debug] Env Variable VITE_SOCKET_URL: "${envSocketUrl}"`);
    console.log(`[Socket Debug] Final Connection URL: "${socketUrl || window.location.origin}"`);

    socket.value = io(socketUrl, {
      // [수정일: 2026-02-26] AWS ALB 및 Nginx의 /socket.io/ 라우팅 누락 문제 해결을 위해 /api/socket.io 로 경로 변경
      path: '/api/socket.io',
      transports: ['polling', 'websocket'],
      forceNew: true
    })

    socket.value.on('connect', () => {
      connected.value = true
      // [수정일: 2026-03-03] DB 연동을 위해 user_id 포함하여 전송
      socket.value.emit('draw_join', { room_id: roomId, user_name: userName, user_id: userId, avatar_url: avatarUrl || '' })
    })

    socket.value.on('disconnect', () => { connected.value = false })

    socket.value.on('draw_lobby', (data) => {
      roomPlayers.value = data.players || []
      isReady.value = roomPlayers.value.length === 2 // 딱 2명일 때만 준비 완료
    })

    // 2명 이상 모임 → ready
    socket.value.on('draw_ready', (data) => {
      isReady.value = data?.ready ?? true
    })

    // [추가 2026-02-27] 게임 시작 신호 수신
    socket.value.on('draw_game_start', (data) => {
      if (onGameStart.value) onGameStart.value(data)
    })

    // 라운드 시작
    socket.value.on('draw_round_start', (data) => {
      roundQuestion.value = data.question
      opponentCanvas.value = { nodes: [], arrows: [] }
      opponentSubmitted.value = false
      roundResults.value = null
      if (onRoundStart.value) onRoundStart.value(data)
    })


    // 상대 캔버스 실시간 업데이트 (관전용)
    socket.value.on('draw_canvas_update', (data) => {
      opponentName.value = data.sender_name || ''
      opponentCanvas.value = { nodes: data.nodes || [], arrows: data.arrows || [] }
    })

    // 아이템 효과 수신
    socket.value.on('draw_item_effect', (data) => {
      if (onItemEffect.value) onItemEffect.value(data.item_type)
    })

    // 상대방 아이템 보유 상태 수신
    socket.value.on('draw_opponent_item_status', (data) => {
      opponentHasItem.value = data.has_item
    })

    // 상대가 제출함
    socket.value.on('draw_player_submitted', (data) => {
      if (data.sid !== socket.value.id) {
        opponentSubmitted.value = true
      }
    })

    // 양쪽 모두 제출 → 라운드 결과
    socket.value.on('draw_round_result', (data) => {
      roundResults.value = data.results
      if (onRoundResult.value) onRoundResult.value(data.results)
    })

    // [추가 2026-03-03] CoachAgent 힌트 수신
    socket.value.on('coach_hint', (data) => {
      console.log('💡 [ArchDraw] Coach Hint Received:', data)
      if (onCoachHint.value) onCoachHint.value(data)
    })

    // [추가 2026-02-27] ChaosAgent 주도 장애 이벤트 수신
    socket.value.on('chaos_event', (data) => {
      console.log('🔥 [ArchDraw] Chaos Event Received:', data)
      if (onChaosEvent.value) onChaosEvent.value(data)
    })

    // [추가 2026-03-03] 장애 복구 알림 수신
    socket.value.on('draw_chaos_recovered', (data) => {
      if (onChaosRecovered.value) onChaosRecovered.value(data)
    })

    // [추가] 5라운드 종료 → 게임 오버
    socket.value.on('draw_game_over', () => {
      if (onGameOver.value) onGameOver.value()
    })

    // 상대 퇴장
    socket.value.on('draw_player_left', (data) => {
      roomPlayers.value = roomPlayers.value.filter(p => p.sid !== data.sid)
      isReady.value = roomPlayers.value.length >= 2
    })
  }

  // 게임 시작
  function emitStart(roomId, question) {
    socket.value?.emit('draw_start', { room_id: roomId, question })
  }

  // 내 캔버스 실시간 동기화
  function emitCanvasSync(roomId, userName, nodes, arrows) {
    socket.value?.emit('draw_canvas_sync', {
      room_id: roomId,
      user_name: userName,
      nodes: nodes.map(n => ({ compId: n.compId, name: n.name, icon: n.icon, x: n.x, y: n.y })),
      arrows: arrows.map(a => ({ fc: a.fc, tc: a.tc, x1: a.x1, y1: a.y1, x2: a.x2, y2: a.y2 }))
    })
  }

  // 제출 — time_left, combo 추가 (서버 점수 검증에 필요)
  function emitSubmit(roomId, score, checks, finalData, timeLeft = 0, combo = 0) {
    socket.value?.emit('draw_submit', {
      room_id: roomId,
      score,       // 참고용 (서버는 직접 재계산)
      checks,
      final_nodes: finalData?.nodes || [],
      final_arrows: finalData?.arrows || [],
      time_left: timeLeft,
      combo: combo
    })
  }

  // 아이템 사용
  function emitUseItem(roomId, itemType) {
    socket.value?.emit('draw_use_item', { room_id: roomId, item_type: itemType })
  }

  // 아이템 보유 상태 전송
  function emitItemStatus(roomId, hasItem) {
    socket.value?.emit('draw_item_status', { room_id: roomId, has_item: hasItem })
  }

  // 다음 라운드
  function emitNextRound(roomId, question) {
    socket.value?.emit('draw_next_round', { room_id: roomId, question })
  }

  // [추가 2026-03-03] Chaos 장애 확인
  function emitChaosComplete(roomId) {
    socket.value?.emit('draw_chaos_complete', { room_id: roomId })
  }

  function disconnect(roomId) {
    socket.value?.emit('draw_leave', { room_id: roomId })
    socket.value?.disconnect()
    socket.value = null
  }

  onUnmounted(() => { if (socket.value) socket.value.disconnect() })

  return {
    socket, connected, roomPlayers, isReady,
    opponentCanvas, opponentName, opponentHasItem,
    roundQuestion, opponentSubmitted, roundResults,
    onGameStart, onRoundStart, onRoundResult, onItemEffect, onCoachHint, onChaosEvent, onChaosRecovered, onGameOver,
    connect, emitStart, emitCanvasSync, emitUseItem,
    emitItemStatus, emitSubmit, emitNextRound, emitChaosComplete, disconnect
  }
}
