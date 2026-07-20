import { onMounted, onUnmounted } from 'vue'
import { useRobotStore } from '@/stores/robot/robotStore'
import { useMissionStore } from '@/stores/robot/missionStore'
import { useEventStore } from '@/stores/robot/eventStore'
import { ElNotification } from 'element-plus'

export default function useRobotSSE() {
  const robotStore = useRobotStore()
  const missionStore = useMissionStore()
  const eventStore = useEventStore()
  let ws = null
  let reconnectTimer = null

  function connect() {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
      return
    }
    const wsUrl = `ws://localhost:8000/ws/robot`
    ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      robotStore.setWsConnected(true)
      eventStore.addEvent({ timestamp: Date.now(), level: 'INFO', type: 'WebSocket', message: 'Connected' })
      if (reconnectTimer) clearTimeout(reconnectTimer)
      reconnectTimer = null
      // Start confirm polling
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'robot_state') {
          robotStore.updateRobotState(data)
        } else if (data.type === 'task_state_changed') {
          missionStore.updateCurrent(data)
        } else if (data.type === 'navigation_state') {
          robotStore.updateNavigationState(data)
        } else if (data.type === 'ui.task_progress') {
          if (data.task_id === 'recharge') {
            missionStore.updateCurrent({ state: 'charging', progress: data.payload.progress })
            if (data.payload.voltage) robotStore.robot.batteryVoltage = data.payload.voltage
            if (data.payload.percent) robotStore.robot.batteryPercent = data.payload.percent
          }
        } else if (data.type === 'ui.task_result') {
          if (data.task_id === 'recharge_complete') {
            missionStore.updateCurrent({ state: 'idle' })
          }
        } else if (data.type === 'graph_structure') {
          missionStore.updateGraphStructure(data.payload)
        } else if (data.type === 'task_node_status') {
          missionStore.updateTaskStatusMap(data.payload.task_status_map)
          if (data.payload.graph_id) {
            missionStore.current.graphId = data.payload.graph_id
          }
          if (data.payload.graph_completed !== undefined) {
            missionStore.current.graphCompleted = data.payload.graph_completed
          }
          if (data.payload.graph_total !== undefined) {
            missionStore.current.graphTotal = data.payload.graph_total
          }
        } else if (data.type === 'heartbeat') {
          robotStore.updateAgentHeartbeat(data.agent_id, true)
        } else if (data.type === 'system_health') {
          robotStore.updateSystemHealth(data.payload)
        } else if (data.type === 'world_model') {
          if (data.coverage_grid) robotStore.updateCoverageGrid(data.coverage_grid)
        } else if (data.type === 'rooms_update') {
          robotStore.updateRooms(data.payload.rooms)
        } else if (data.type === 'ui.notification') {
          const p = data.payload || {}
          if (p.notification_type === 'tts' && p.audio_url) {
            ElNotification({
              title: '语音播报',
              message: '<div style="display:flex;align-items:center;gap:8px;max-width:360px"><span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + (p.text || p.message || '') + '</span><audio controls src="' + p.audio_url + '" style="width:140px;height:36px"></audio></div>',
              dangerouslyUseHTMLString: true,
              type: 'success',
              duration: 0,
            })
          } else {
            ElNotification({
              title: p.notification_type === 'phone_push' ? '手机推送' : '通知',
              message: p.message || '',
              type: p.notification_type === 'phone_push' ? 'success' : 'info',
              duration: 4000,
            })
          }
        }
        eventStore.addEvent({ timestamp: Date.now(), level: 'INFO', type: data.type, message: JSON.stringify(data).slice(0, 200) })

        // Auto TTS: speak notification events when toggle is on
        if (localStorage.getItem('tts_enabled') === 'true') {
          const evType = data.type
          const payload = data.payload || {}
          // Only speak human-facing events, skip TTS-originated events to avoid loops
          if (
            (evType === 'ui.notification' && payload.notification_type !== 'tts' && payload.notification_type !== 'phone_push') ||
            evType === 'ui.task_result'
          ) {
            const text = payload.message || payload.answer || ''
            if (text && text.length > 3) {
              fetch(location.origin + '/api/robot/tts', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: text.slice(0, 200) }),
              }).catch(function() {})
            }
          }
        }
      } catch (e) {
        console.error('Parse WebSocket message error', e)
      }
    }

    ws.onclose = () => {
      ws = null
      robotStore.setWsConnected(false)
      if (reconnectTimer) clearTimeout(reconnectTimer)
      reconnectTimer = setTimeout(() => { connect() }, 5000)
    }

    ws.onerror = (err) => console.error('WebSocket error', err)
  }

  function disconnect() {
    try {
    if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null }
    if (ws) {
      ws.onclose = null
      ws.close()
      ws = null
    }
    } catch (e) {
      console.warn('WS disconnect error:', e)
    }
  }

  onMounted(() => { connect() })
  onUnmounted(() => {
    disconnect()
  })
}

