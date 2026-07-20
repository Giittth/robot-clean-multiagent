import { defineStore } from 'pinia'

export const useMissionStore = defineStore('mission', {

  state: () => ({

    // 閻熸粎澧楅幐鍛婃櫠閻樺磭顩烽悹鍥ㄥ絻椤倕菐閸ワ絽澧插ù?

    current: {

      taskId: null,           // 閻熸粎澧楅幐鍛婃櫠閻樺磭顩烽悹鍥ㄥ絻椤?ID

      state: 'idle',          // idle, running, paused, recharging, charging, success, failed, emergency_stop

      progress: 0,            // 闂佽桨鑳剁换婵堢礊鐎ｎ偅浜ゆ繛鎴灻?0-1

      graphId: null,          // 婵炲濮鹃褎鎱ㄩ悢鐓庣倞?ID

      sessionId: null,        // 婵炴潙鍚嬫穱娲儊?ID

      currentTaskDesc: '',    // 閻熸粎澧楅幐鍛婃櫠閻樿绠ョ憸鎴︺€侀幋锔藉剭闁告洦浜濆畷鏌ユ煕閺傚搫澧茬€殿喗瀵у鑽ゆ暜椤斿墽顦╂繛?GraphExecutor 闂佸吋鍎抽崲鑼躲亹閸ヮ剚鏅?

      graphCompleted: 0,      // 閻庣懓鎲¤ぐ鍐偩椤掑嫬绠ｉ柟閭﹀墯缁傚牓鏌ら崫鍕偓濠氬磻閿濆鏋?

      graphTotal: 0           // 闂佽鍓濋褍霉濮椻偓閹崇偤宕掑鍐у寲闂?

    },

    // 婵炲濮鹃褎鎱ㄩ悢鐓庣睄闁割偅娲橀敍鐔煎级閻愯埖褰х紒杈ㄧ懇閹粙濡搁妶鍥闁诲繒鍋炲ú婊堝Φ濮橆厾顩烽悹鍥ㄥ絻椤倝鏌涢妷褍浜惧褏鏅幃鏉跨暆閸曗斁鍋撴惔銏″劅闊洢鍎崇粈?

    timeline: [],             // 闁诲孩绋掗敋闁稿绉电粋鎺旀嫚閹绘帩娼抽梺鐓庢惈閸婂宕?{ id, name, status, startedAt, finishedAt, error }

    // 婵炲濮鹃褎鎱ㄩ悢鐓庡偍闁糕剝顨呴拺澶愭煥濞戞澧曢柛鎴磿閳ь剛鎳撻張顒勫垂濮樿埖鍎嶉柛鏇ㄤ簼瀹曟煡鏌涢弬鐑橆潐缂?

    history: [],              // 闂佸搫鐗冮崑鎾愁熆閼镐絻澹橀柣掳鍔戝畷?50 闂佸搫顦Σ鍕濠靛柊鎺曠疀閺冣偓閽傚鏌涢弽褎鍣归柟?{ taskId, graphId, sessionId, success, duration, timestamp, error }

    // 鐟滅増鎸告晶鐘崇鐠囨彃顫ょ€殿喒鍋撳┑顔碱儐濡炲倿姊绘潏鍓х闁活潿鍔嬬花顒傛媼閿涘嫮鏆柤鐗堫殕濡炲倿鏁?

    startedAt: null,

    // 濞寸姾顕ф慨鐔烘喆閸曨偄鐏婇柛娆樺灥椤宕?

    graphStructure: null,

    taskStatusMap: {},        // { task_id: "pending" | "running" | "success" | "failed" | ... }

  }),



  getters: {

    // 婵炲濮鹃褎鎱ㄩ悢鍏煎亹闁煎摜顣介崑鎾存媴閻ゎ垰骞€闂?

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
    // 闁哄洤鐡ㄩ弻濠冪鐠囨彃顫ら柣妯垮煐閳ь兛绶ょ槐娆撳级閵夈劌娈?task_state_changed 闁?task_progress 婵炴垵鐗婃导鍛存晬?
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

      // 婵犵鈧啿鈧綊鎮樻径鎰亹闁煎摜顣介崑鎾存媴缁嬭法绉繛?running 婵炴垶鎸婚弻褏绮婚敐澶婄鐎广儱妫欏鎾绘偣娴ｈ绶茬紓宥呯Т椤曪綁鍩€椤掍焦鍙忛悗锝庡亝椤ρ囨⒒閸屾繃褰х紒杈ㄧ箞瀹曟艾鈻庨幒婵嗘暪閻?

      if (payload.state === 'running' && this.startedAt === null) {

        this.startedAt = Date.now()

      }

      // 婵犵鈧啿鈧綊鎮樻径瀣浄閻犲洦褰冮～銈囩磽娴ｈ灏版繛纰卞亰閺佸秹宕搁惃宄渃ess/failed/stopped闂佹寧绋戦¨鈧紒杈ㄧ箘閹峰寮剁捄銊梺鍛娒Λ妤勩亹?

      if (['success', 'failed', 'stopped'].includes(payload.state)) {
        const terminalState = payload.state === 'success' ? 'success'
          : payload.state === 'failed' ? 'failed' : 'stopped'
        // 閻?taskStatusMap 濞戞搩鍘芥晶宥夊嫉婢跺鐭濋柛锔哄姀缁绘鎮扮仦鑹板幀闁汇劌瀚俊顓㈡倷鐟欏嫮鍨奸悹渚€顣︾拹鐔虹磼閸噥鍓鹃柟?
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



    // 闂佸搫娲ら悺銊╁蓟婵犲洤绫嶉柛顐ｆ礃閿涚喖寮堕悙鑸靛涧缂佽鲸鐟︾粋鎺旀嫚閹绘帩娼抽梺鎼炲劤閸嬫挻鏅堕悾灞惧仒鐎光偓閸愵亞鐣虹紓浣割儏椤戝嫰鎳欓幋锔藉剭闁告洦鍠栬灐闂佺粯鍔楅幊鎾广亹婢舵劕绀岄柡宥囨暩缁€?

    updateTimeline(tasks) {

      // tasks 闂佸搫绉堕崢褏妲? [{ id, name, status }]

      this.timeline = tasks

    },

    // 闂佸搫娲ら悺銊╁蓟婵犲洤鐐婇柛鎾楀懏灏濋梺鍝勵儏鐎氬摜妲愬▎鎾崇骇闁靛鍔屽▓?graph_structure 濠电偞鍨甸悧濠冨閸涘瓨鏅?

    updateGraphStructure(payload) {

      if (!payload) return

      this.graphStructure = {

        tasks: payload.tasks || [],

        edges: payload.edges || [],

      }

      // 闂備焦褰冪粔鍫曟偪?taskStatusMap闂佹寧绋戦悧濠囧蓟婵犲洤鐐婇柟顖嗗懐锛涙繝娈垮枛椤戞垹妲?

      this.taskStatusMap = {}

      if (payload.graph_id) {

        this.current.graphId = payload.graph_id

      }

    },

    // 闂佸搫娲ら悺銊╁蓟婵犲洦鐒婚柟閭﹀灠铻￠梺缁樺姇濠€杈ㄦ叏閹间礁绠戝〒姘功缁€鍕煛婢跺牆鍔ラ柛?task_node_status 濠电偞鍨甸悧濠冨閸涘瓨鏅?

    updateTaskStatusMap(statusMap) {

      if (!statusMap) return

      this.taskStatusMap = { ...statusMap }

    },



    // 濠电儑缍€椤曆勬叏閻愬搫绀嗛柡澶婄仢閸у﹪鏌涘▎鎺戣敿妞ゆ柨娲╅妵?

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

      // 婵烇絽娲︾换鍕汲閳ь剟鏌￠崼姘壕闁?50 闂?

      if (this.history.length > 50) this.history.pop()

      // 闂佸憡鐟崹鍫曞焵椤掆偓椤р偓缂佸彉鍗抽獮鎰媴妞嬪海鏆梺鍛婄墬閻楁洟宕?localStorage

      this.saveHistoryToLocal()

    },



    // 濠电偞鎸搁幊鎰板煘閺嶎厼鍌ㄩ柛鈩冾殔閽?

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



    // 婵烇絽娲︾换鍌炴偤閵娾晛鍌ㄩ柛鈩冾殔閽戝鏌涢幒鏂款暭婵犫偓娴兼潙鎹堕柡澶庢硶閹界娀鏌?

    saveHistoryToLocal() {

      try {

        localStorage.setItem('robot_task_history', JSON.stringify(this.history))

      } catch (e) {}

    },



    // 闂佸憡姊绘慨鎯归崶顒€鍌ㄩ柛鈩冾殔閽戝鎮规担瑙勭凡缂傚秴绉归弫宥夊醇閵夛絺鍋撴径鎰棃闁靛繒濮撮悘銉モ攽椤旂⒈鍎忛悗鍨叀瀵噣骞嗛幍顔筋啀闂佹眹鍩勯悡澶屾?

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



    // 婵炲濮存鎼佸箖濡ゅ啰鍗?API 闂佸憡姊绘慨鎯归崶銊ь浄閻犲洦褰冮～銈夋煕濡儤顥滅憸?

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



        // 3. Build mission entries first (they are authoritative 闂?have missionId + replay data)

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
})
