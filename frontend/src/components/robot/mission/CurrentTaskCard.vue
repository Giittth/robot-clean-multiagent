<template>
  <el-card class="current-task-card" shadow="hover">
    <template #header>
      <div class="card-header">
        <span>当前任务</span>
        <el-tag :type="stateTag" size="small">{{ stateChinese }}</el-tag>
      </div>
    </template>

    <div class="task-info">
      <!-- 第一行：任务名称 + 阶段 -->
      <div class="info-row">
        <label>任务名称</label>
        <span>{{ taskName || '无' }}</span>
      </div>
      <div class="info-row">
        <label>当前阶段</label>
        <span>{{ currentPhase }}</span>
      </div>

      <!-- 进度条区域 -->
      <div class="progress-area">
        <div class="progress-stats">
          <span>任务进度</span>
          <span>{{ graphCompleted }} / {{ graphTotal }} 节点</span>
        </div>
        <el-progress :percentage="graphPercent" :stroke-width="8" :show-text="false" />
        <div class="progress-percent">{{ graphPercent }}%</div>
      </div>

      <!-- 时间信息 -->
      <div class="time-info">
        <div class="info-row">
          <label>预计剩余</label>
          <span>{{ estimatedRemaining || '--:--' }}</span>
        </div>
        <div class="info-row">
          <label>开始时间</label>
          <span>{{ startTimeFormatted || '--:--' }}</span>
        </div>
        <div class="info-row">
          <label>运行时长</label>
          <span>{{ elapsedTimeFormatted || '00:00' }}</span>
        </div>
      </div>

      <!-- 状态与控制权 -->
      <div class="info-row">
        <label>节点状态</label>
        <span>{{ nodeStatus }}</span>
      </div>
      <div class="info-row">
        <label>控制权</label>
        <span>{{ controlOwner }}</span>
      </div>

      <!-- 会话与图信息 -->
      <div class="ids-info">
        <div class="info-row">
          <label>Session ID</label>
          <span class="mono">{{ shortSessionId }}</span>
        </div>
        <div class="info-row">
          <label>Generation</label>
          <span>{{ generation }}</span>
        </div>
        <div class="info-row">
          <label>Graph ID</label>
          <span class="mono">{{ shortGraphId }}</span>
        </div>
      </div>
    </div>
  </el-card>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useMissionStore } from '@/stores/robot/missionStore'
import { useRobotStore } from '@/stores/robot/robotStore'

const missionStore = useMissionStore()
const robotStore = useRobotStore()

// 从 missionStore 获取任务相关数据
const { current, startedAt } = storeToRefs(missionStore)
// 从 robotStore 获取控制权和导航状态
const { navigation } = storeToRefs(robotStore)

// 计算属性
const taskName = computed(() => current.value.currentTaskDesc || current.value.taskId || '无')
const graphCompleted = computed(() => current.value.graphCompleted ?? 0)
const graphTotal = computed(() => current.value.graphTotal ?? 0)
const graphPercent = computed(() => {
  const total = graphTotal.value
  return total > 0 ? Math.round((graphCompleted.value / total) * 100) : 0
})

// 状态标签
const stateChinese = computed(() => missionStore.stateChinese)
const stateTag = computed(() => {
  const state = current.value.state
  if (state === 'running') return 'success'
  if (state === 'paused') return 'warning'
  if (state === 'emergency_stop') return 'danger'
  if (state === 'success') return 'success'
  if (state === 'failed') return 'danger'
  return 'info'
})

// 当前阶段（根据导航模式或任务状态）
const currentPhase = computed(() => {
  const navMode = navigation.value.mode
  const state = current.value.state
  if (state === 'charging') return '充电中'
  if (state === 'recharging') return '返回充电'
  if (navMode === 'NAVIGATE_TO_POINT') return '导航至目标点'
  if (navMode === 'NAVIGATE_TO_AREA') return '导航至区域'
  if (navMode === 'COVERAGE') return '覆盖清扫'
  if (navMode === 'GO_HOME') return '返回充电'
  if (state === 'running') return '执行中'
  return '空闲'
})

// 节点状态（当前正在执行的任务节点状态）
const nodeStatus = computed(() => {
  const state = current.value.state
  if (state === 'running') return '运行中'
  if (state === 'paused') return '已暂停'
  if (state === 'emergency_stop') return '急停'
  return '空闲'
})

// 控制权
const controlOwner = computed(() => navigation.value.controlOwner || 'IDLE')

// Session ID 缩短显示
const shortSessionId = computed(() => {
  const sid = current.value.sessionId
  return sid ? `${sid.slice(0, 8)}...` : '无'
})

// Graph ID 缩短显示
const shortGraphId = computed(() => {
  const gid = current.value.graphId
  return gid ? `${gid.slice(0, 8)}...` : '无'
})

// Generation（暂时使用导航路径索引作为示例）
const generation = computed(() => navigation.value.pathIndex ?? 0)

// 开始时间格式化
const startTimeFormatted = computed(() => {
  const ts = startedAt.value
  if (!ts) return null
  const date = new Date(ts)
  return date.toLocaleTimeString('zh-CN', { hour12: false })
})

// 运行时长（秒）实时更新
const elapsedSeconds = ref(0)
let timer = null

const updateElapsed = () => {
  if (startedAt.value && current.value.state === 'running') {
    const elapsed = Math.floor((Date.now() - startedAt.value) / 1000)
    elapsedSeconds.value = elapsed
  } else {
    elapsedSeconds.value = 0
  }
}

const elapsedTimeFormatted = computed(() => {
  const secs = elapsedSeconds.value
  if (secs <= 0) return '00:00'
  const hours = Math.floor(secs / 3600)
  const minutes = Math.floor((secs % 3600) / 60)
  const seconds = secs % 60
  if (hours > 0) {
    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`
  }
  return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`
})

// 预计剩余时间（简单估算：总节点数/已完成节点数 * 已用时间，不精准，仅作示例）
const estimatedRemaining = computed(() => {
  const completed = graphCompleted.value
  const total = graphTotal.value
  const elapsed = elapsedSeconds.value
  if (total === 0 || completed === 0 || elapsed === 0) return '--:--'
  const remainingSecs = Math.round((total - completed) / completed * elapsed)
  if (remainingSecs <= 0) return '00:00'
  const minutes = Math.floor(remainingSecs / 60)
  const seconds = remainingSecs % 60
  return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`
})

// 定时更新运行时长
onMounted(() => {
  updateElapsed()
  timer = setInterval(() => {
    updateElapsed()
  }, 1000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.current-task-card {
  margin-bottom: 16px;  /* 保持原有下边距 */
  overflow: visible;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.task-info {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.info-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  font-size: 14px;
  padding: 4px 0;
}

.info-row label {
  color: #6b7280;
  font-weight: 500;
  min-width: 80px;
}

.info-row span {
  font-weight: 500;
  color: #111827;
  text-align: right;
}

.progress-area {
  background: #f9fafb;
  padding: 10px 12px;
  border-radius: 8px;
  margin: 4px 0;
}

.progress-stats {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 6px;
}

.progress-percent {
  text-align: right;
  font-size: 12px;
  color: #6b7280;
  margin-top: 4px;
}

.time-info {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  background: #f9fafb;
  padding: 8px 12px;
  border-radius: 8px;
}

.ids-info {
  border-top: 1px solid #e4e7ed;
  margin-top: 4px;
  padding-top: 8px;
}

.mono {
  font-family: monospace;
  font-size: 12px;
}
</style>