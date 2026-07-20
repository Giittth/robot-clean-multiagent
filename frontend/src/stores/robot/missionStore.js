import { defineStore } from 'pinia'





export const useMissionStore = defineStore('mission', {

  state: () => ({

    // 褰撳墠浠诲姟淇℃伅

    current: {

      taskId: null,           // 褰撳墠浠诲姟 ID

      state: 'idle',          // idle, running, paused, recharging, charging, success, failed, emergency_stop

      progress: 0,            // 鏁翠綋杩涘害 0-1

      graphId: null,          // 浠诲姟鍥?ID

      sessionId: null,        // 浼氳瘽 ID

      currentTaskDesc: '',    // 褰撳墠鎵ц鐨勪换鍔℃弿杩帮紙浠?GraphExecutor 鑾峰彇锛?

      graphCompleted: 0,      // 宸插畬鎴愬浘鑺傜偣鏁?

      graphTotal: 0           // 鎬诲浘鑺傜偣鏁?

    },

    // 浠诲姟鏃堕棿杞达紙鐢ㄤ簬灞曠ず浠诲姟鍥炬墽琛岄『搴忥級

    timeline: [],             // 瀛樺偍浠诲姟鑺傜偣 { id, name, status, startedAt, finishedAt, error }

    // 浠诲姟鍘嗗彶锛堝凡瀹屾垚鐨勪换鍔★級

    history: [],              // 鏈€澶氬瓨鍌?50 鏉★紝姣忔潯鍖呭惈 { taskId, graphId, sessionId, success, duration, timestamp, error }

    // 当前任务开始时间（用于计算耗时）

    startedAt: null,

    // 任务规划可视化

    graphStructure: null,

    taskStatusMap: {},        // { task_id: "pending" | "running" | "success" | "failed" | ... }

  }),



  getters: {

    // 浠诲姟鐘舵€佷腑鏂?

    stateChinese: (state) => {

      const map = {

        idle: '空闲',

        running: '运行中',

        paused: '已暂停',

        recharging: '回充中',

        charging: '充电中',

        stopped: '已停止',

        success: '成功',

        failed: '失败',

        emergency_stop: '紧急停止',

      }



      return map[state.current.state] || state.current.state

    },

  },

  actions: {
    // 更新任务状态（来自 task_state_changed 或 task_progress 消息）
    updateCurrent(payload) {
      if (payload.state !== undefined) this.current.state = payload.state

      if (payload.progress !== undefined) this.current.progress = payload.progress

      if (payload.task_id !== undefined) this.current.taskId = payload.task_id

      if (payload.graph_id !== undefined) this.current.graphId = payload.graph_id

      if (payload.session_id !== undefined) this.current.sessionId = payload.session_id

      if (payload.mission_id !== undefined) this.current.missionId = payload.mission_id

      if (payload.current_task_desc !== undefined) this.current.currentTaskDesc = payload.current_task_desc

      if (payload.graph_completed !== undefined) this.current.graphCompleted = payload.graph_completed

      if (payload.graph_total !== undefined) this.current.graphTotal = payload.graph_total

      // 濡傛灉鐘舵€佸彉涓?running 涓斾箣鍓嶆湭璁板綍寮€濮嬫椂闂达紝鍒欒褰?

      if (payload.state === 'running' && this.startedAt === null) {

        this.startedAt = Date.now()

      }

      // 濡傛灉浠诲姟缁撴潫锛坰uccess/failed/stopped锛夛紝璁板綍鍘嗗彶

      if (['success', 'failed', 'stopped'].includes(payload.state)) {
        const terminalState = payload.state === 'success' ? 'success'
          : payload.state === 'failed' ? 'failed' : 'stopped'
        // 将 taskStatusMap 中所有仍在进行中的节点标记为终止态
        const updatedMap = { ...this.taskStatusMap }
        for (const [id, status] of Object.entries(updatedMap)) {
          if (['pending', 'ready', 'dispatched', 'running'].includes(status)) {
            updatedMap[id] = terminalState
          }
        }
        this.taskStatusMap = updatedMap


        this.addToHistory(payload)

        this.startedAt = null
        // terminal states: auto-reset to idle so UI stays responsive
        setTimeout(() => { this.current.state = 'idle' }, 200)

      }

    },



    // 鏇存柊鏃堕棿杞达紙浠诲姟鍥炬墽琛岃繃绋嬩腑鐨勮妭鐐瑰彉鍖栵級

    updateTimeline(tasks) {

      // tasks 鏍煎紡: [{ id, name, status }]

      this.timeline = tasks

    },

    // 鏇存柊鍥剧粨鏋勶紙鏉ヨ嚜 graph_structure 娑堟伅锛?

    updateGraphStructure(payload) {

      if (!payload) return

      this.graphStructure = {

        tasks: payload.tasks || [],

        edges: payload.edges || [],

      }

      // 閲嶇疆 taskStatusMap锛堟柊鍥惧紑濮嬶級

      this.taskStatusMap = {}

      if (payload.graph_id) {

        this.current.graphId = payload.graph_id

      }

    },

    // 鏇存柊閫愯妭鐐圭姸鎬侊紙鏉ヨ嚜 task_node_status 娑堟伅锛?

    updateTaskStatusMap(statusMap) {

      if (!statusMap) return

      this.taskStatusMap = { ...statusMap }

    },



    // 娣诲姞鍒板巻鍙茶褰?

    addToHistory(result) {

      const record = {

        taskId: this.current.taskId,

        graphId: this.current.graphId,

        sessionId: this.current.sessionId,

        success: result.state === 'success',

        duration: this.startedAt ? (Date.now() - this.startedAt) / 1000 : 0,

        timestamp: Date.now(),

        error: result.error || null

      }

      this.history.unshift(record)

      // 淇濈暀鏈€杩?50 鏉?

      if (this.history.length > 50) this.history.pop()

      // 鍙€夛細鎸佷箙鍖栧埌 localStorage

      this.saveHistoryToLocal()

    },



    // 娓呯┖鍘嗗彶

    async clearHistory() {

      this.history = []

      localStorage.removeItem('robot_task_history')

      try {

        const { clearAllHistory } = await import('@/api/robot/mission')

        await clearAllHistory(0)

      } catch (e) {

        console.error('Clear history API failed:', e)

      }

    },



    // 淇濆瓨鍘嗗彶鍒版湰鍦板瓨鍌?

    saveHistoryToLocal() {

      try {

        localStorage.setItem('robot_task_history', JSON.stringify(this.history))

      } catch (e) {}

    },



    // 鍔犺浇鍘嗗彶璁板綍锛堥〉闈㈠垵濮嬪寲鏃惰皟鐢級

    loadHistoryFromLocal() {

      try {

        const stored = localStorage.getItem('robot_task_history')

        if (stored) {

          this.history = JSON.parse(stored)

        }

      } catch (e) {}

    },



    async deleteRecord(record) {

      try {

        if (record.source === 'mission' && record.missionId) {

          const { deleteMission } = await import('@/api/robot/mission')

          await deleteMission(record.missionId)

        } else if (record.source === 'chat' && record.id) {

          const { deleteTaskHistory } = await import('@/api/robot/mission')

          await deleteTaskHistory(record.id)

        }

      } catch (e) {

        console.error('Delete record failed:', e)

        throw e

      }

      this.history = this.history.filter(r => r !== record)

      this.saveHistoryToLocal()

    },



    // 浠庡悗绔?API 鍔犺浇浠诲姟鍘嗗彶

    async loadHistoryFromAPI() {

      try {

        const { getMissions, getTaskHistory } = await import('@/api/robot/mission')



        // 1. Load from mission_history table (robot task system)

        const missions = await getMissions(0, 50)

        const missionList = Array.isArray(missions) ? missions : []



        // 2. Load from task_history table (chat system / legacy save)

        let taskList = []

        try {

          const taskResp = await getTaskHistory(0, 50)

          taskList = taskResp?.tasks || []

        } catch (e2) {

          // task_history API may not exist or fail silently

        }



        // 3. Build mission entries first (they are authoritative 鈥?have missionId + replay data)

        const combined = []

        const missionCmdSet = new Set()  // Track commands already seen from missions



        for (const m of missionList) {

          const cmd = (m.command || '').trim()

          if (cmd) missionCmdSet.add(cmd)

          combined.push({

            id: m.id,

            taskId: m.command || '-',

            graphId: m.graph_id || '-',

            sessionId: m.session_id || '-',

            status: m.status || 'unknown',

            success: m.status === 'completed',

            duration: m.duration || 0,

            timestamp: m.started_at || m.created_at,

            error: m.error_info || null,

            coverage: m.coverage_percent || 0,

            missionId: m.id,

            source: 'mission',

          })

        }



        for (const t of taskList) {

          const cmd = (t.command || '').trim()



          // Deduplicate: skip task_history entries that match a mission command

          // (SupervisorAgent saves to BOTH tables, so we prefer the mission entry)

          if (cmd && missionCmdSet.has(cmd)) {

            continue

          }



          // Classify source based on actual task_type

          const isRealChat = t.task_type === 'chat'

          combined.push({

            id: t.id,

            taskId: cmd || '-',

            graphId: '-',

            sessionId: '-',

            status: (t.result === 'completed' ? 'success' : t.result) || 'unknown',

            success: (t.result === 'completed' || t.result === 'success'),

            duration: 0,

            timestamp: t.created_at,

            error: t.error_info || null,

            coverage: 0,

            missionId: null,

            source: isRealChat ? 'chat' : 'mission',

            answer: t.answer || '',

          })

        }



        // 4. Sort by timestamp descending, most recent first

        combined.sort((a, b) => {

          const ta = a.timestamp ? new Date(a.timestamp).getTime() : 0

          const tb = b.timestamp ? new Date(b.timestamp).getTime() : 0

          return tb - ta

        })



        // 5. Update store if we have data

        if (combined.length > 0) {

          this.history = combined.slice(0, 50)

          this.saveHistoryToLocal()

        }

      } catch (e) {
        console.error('Load missions failed:', e)
      }
    },
  },
      // 如果任务结束（success/failed/stopped），更新 taskStatusMap 并更新 taskStatusMap 并记录历史