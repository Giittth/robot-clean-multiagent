import { defineStore } from 'pinia'
import { sendTask } from '@/api/robot/mission'
import { sendControl } from '@/api/robot/robot'

export const useRobotStore = defineStore('robot', {
  state: () => ({
    // ========== 机器人基本状态（对应 robot_state） ==========
    robot: {
      pose: { x: 0, y: 0, theta: 0 },
      batteryVoltage: 12.0,
      batteryPercent: 100,
      collision: false,
      cleanedArea: 0,
      action: { linear: 0, angular: 0 },
      ragAdvice: ''
    },
    // 激光点云（用于地图绘制）
    laserData: [],
    // 静态障碍物列表
    obstacles: [],
    // 覆盖地图（栅格，用于绘制清扫区域）
    coverageGrid: [],

    // ========== 任务状态 ==========
    mission: {
      taskId: null,
      state: 'idle',
      progress: 0,
      graphId: null,
      sessionId: null,
      currentTaskDesc: '',
      graphCompleted: 0,
      graphTotal: 0
    },

    // ========== 导航状态 ==========
    navigation: {
      mode: 'IDLE',
      path: [],
      pathIndex: 0,
      finalGoal: null,
      controlOwner: 'IDLE'
    },

    // ========== 各 Agent 心跳 ==========
    agentsHeartbeat: {
      supervisor: false,
      planner: false,
      dispatcher: false,
      navigation: false,
      execution: false,
      worldModel: false,
      perception: false
    },

    // ========== 系统健康指标 ==========
    systemHealth: {
      busQueue: 0,
      eventQueue: 0,
      memoryUsage: 0,
      cpuPercent: 0,
      staleEvents: 0,
      droppedResults: 0,
      sessionMismatch: 0,
      generationAbort: 0
    },

    // ========== 其他辅助 ==========
    wsConnected: false,
    powerState: 'OFF',   // 电源状态，从后端接收
    rooms: {}            // 新增：房间数据，格式 { roomName: { polygon, center, entry_point } }
  }),

  getters: {
    batteryClass: (state) => {
      if (state.robot.batteryVoltage < 11) return 'danger'
      if (state.robot.batteryVoltage < 11.5) return 'warning'
      return 'normal'
    },
    taskStateChinese: (state) => {
      const map = {
        idle: '空闲',
        running: '运行中',
        paused: '已暂停',
        recharging: '回充中',
        charging: '充电中',
        stopped: '已停止',
        success: '成功',
        failed: '失败',
        emergency_stop: '紧急停止'
      }
      return map[state.mission.state] || state.mission.state
    },
    shortSessionId: (state) => {
      const sid = state.mission.sessionId
      return sid ? `${sid.slice(0, 8)}...` : '无'
    },
    navigationGeneration: (state) => state.navigation.pathIndex,
    powerStateChinese: (state) => {
      const map = {
        OFF: '关机',
        BOOTING: '启动中',
        IDLE: '空闲',
        WORKING: '工作中',
        CHARGING: '充电中',
        PAUSED: '已暂停',
        EMERGENCY_STOP: '急停',
        ERROR: '错误'
      }
      return map[state.powerState] || state.powerState
    }
  },

  actions: {
    setWsConnected(connected) {
      this.wsConnected = connected
    },

    updateRobotState(data) {
      if (data.pose) this.robot.pose = data.pose
      // ??????????????
      if (data.power_state && data.power_state.toUpperCase() === 'OFF') {
        this.coverageGrid = []
      }
      if (data.sensor?.battery_voltage !== undefined) {
        this.robot.batteryVoltage = data.sensor.battery_voltage
        this.robot.batteryPercent = (this.robot.batteryVoltage - 10) / 2 * 100
        this.robot.batteryPercent = Math.min(100, Math.max(0, this.robot.batteryPercent))
      }
      if (data.sensor?.collision !== undefined) this.robot.collision = data.sensor.collision
      if (data.cleaned_area !== undefined) this.robot.cleanedArea = data.cleaned_area
      if (data.action) this.robot.action = data.action
      if (data.rag_advice) this.robot.ragAdvice = data.rag_advice
      if (data.sensor?.laser) this.laserData = data.sensor.laser
      if (data.obstacles) this.obstacles = data.obstacles
      // 修改：将 power_state 转为大写存储，与组件中的状态值一致
      if (data.power_state) this.powerState = data.power_state.toUpperCase()
      if (data.coverage_grid) this.coverageGrid = data.coverage_grid
    },

    // 单独更新电源状态（可用于其他来源）
    updatePowerState(state) {
      this.powerState = state
    },

    // 更新覆盖地图（来自 world_model 消息）
    updateCoverageGrid(grid) {
      this.coverageGrid = grid || []
    },
    clearCoverageGrid() {
      this.coverageGrid = []
    },

    // 新增：更新房间数据（来自 rooms_update 消息）
    updateRooms(rooms) {
      this.rooms = rooms || {}
    },

    updateMissionState(payload) {
      if (payload.state !== undefined) this.mission.state = payload.state
      if (payload.progress !== undefined) this.mission.progress = payload.progress
      if (payload.task_id !== undefined) this.mission.taskId = payload.task_id
      if (payload.graph_id !== undefined) this.mission.graphId = payload.graph_id
      if (payload.session_id !== undefined) this.mission.sessionId = payload.session_id
      if (payload.current_task_desc !== undefined) this.mission.currentTaskDesc = payload.current_task_desc
      if (payload.graph_completed !== undefined) this.mission.graphCompleted = payload.graph_completed
      if (payload.graph_total !== undefined) this.mission.graphTotal = payload.graph_total
    },

    updateNavigationState(data) {
      if (data.mode !== undefined) this.navigation.mode = data.mode
      if (data.path !== undefined) this.navigation.path = data.path
      if (data.path_index !== undefined) this.navigation.pathIndex = data.path_index
      if (data.final_goal !== undefined) this.navigation.finalGoal = data.final_goal
      if (data.control_owner !== undefined) this.navigation.controlOwner = data.control_owner
    },

    updateAgentHeartbeat(agentName, alive) {
      if (this.agentsHeartbeat.hasOwnProperty(agentName)) {
        this.agentsHeartbeat[agentName] = alive
      }
    },

    updateAgentsHeartbeat(heartbeatMap) {
      Object.assign(this.agentsHeartbeat, heartbeatMap)
    },

    updateSystemHealth(healthData) {
      if (healthData.busQueue !== undefined) this.systemHealth.busQueue = healthData.busQueue
      if (healthData.eventQueue !== undefined) this.systemHealth.eventQueue = healthData.eventQueue
      if (healthData.memoryUsage !== undefined) this.systemHealth.memoryUsage = healthData.memoryUsage
      if (healthData.cpuPercent !== undefined) this.systemHealth.cpuPercent = healthData.cpuPercent
      if (healthData.staleEvents !== undefined) this.systemHealth.staleEvents = healthData.staleEvents
      if (healthData.droppedResults !== undefined) this.systemHealth.droppedResults = healthData.droppedResults
      if (healthData.sessionMismatch !== undefined) this.systemHealth.sessionMismatch = healthData.sessionMismatch
      if (healthData.generationAbort !== undefined) this.systemHealth.generationAbort = healthData.generationAbort
    },

    // ========== 控制指令 ==========
    async sendTask(text) {
      return sendTask(text)
    },

    async sendControl(command) {
      return sendControl(command)
    },

    resetAll() {
      this.$reset()
      this.mission = { ...this.$state.mission }
      this.navigation = { ...this.$state.navigation }
      this.agentsHeartbeat = { ...this.$state.agentsHeartbeat }
      this.systemHealth = { ...this.$state.systemHealth }
      this.coverageGrid = []
      this.powerState = 'OFF'
      this.rooms = {}   // 重置房间的数据
    }
  }
})