<template>
  <el-card class="robot-status-card" shadow="hover">
    <template #header>
      <div class="card-title">
        <el-icon><UserFilled /></el-icon> 机器人状态
      </div>
    </template>
    <div class="info-grid">
      <div class="info-item">
        <label>位置</label>
        <span>({{ robot.pose.x.toFixed(2) }}, {{ robot.pose.y.toFixed(2) }})</span>
      </div>
      <div class="info-item">
        <label>朝向</label>
        <span>{{ robot.pose.theta.toFixed(2) }} rad</span>
      </div>
      <div class="info-item">
        <label>线速度</label>
        <span>{{ robot.action.linear.toFixed(2) }} m/s</span>
      </div>
      <div class="info-item">
        <label>角速度</label>
        <span>{{ robot.action.angular.toFixed(2) }} rad/s</span>
      </div>
      <div class="info-item">
        <label>电池</label>
        <span :class="batteryClass" style="white-space: nowrap;">
          {{ robot.batteryVoltage.toFixed(2) }} V
          ({{ robot.batteryPercent.toFixed(0) }}%)
          <el-icon v-if="taskState === 'charging'" class="charging-icon"><Lightning /></el-icon>
        </span>
      </div>
      <div class="info-item">
        <label>预计续航</label>
        <span>{{ estimatedRuntime }} min</span>
      </div>
      <div class="info-item">
        <label>碰撞</label>
        <span>{{ robot.collision ? '是' : '否' }}</span>
      </div>
      <div class="info-item">
        <label>清扫面积</label>
        <span>{{ robot.cleanedArea.toFixed(2) }} m²</span>
      </div>
    </div>
  </el-card>
</template>

<script setup>
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useRobotStore } from '@/stores/robot/robotStore'
import { useMissionStore } from '@/stores/robot/missionStore'
import { UserFilled, Lightning } from '@element-plus/icons-vue'

const robotStore = useRobotStore()
const missionStore = useMissionStore()

const { robot } = storeToRefs(robotStore)
const { taskState } = storeToRefs(missionStore)

const batteryClass = computed(() => {
  if (robot.value.batteryVoltage < 11) return 'danger'
  if (robot.value.batteryVoltage < 11.5) return 'warning'
  return 'normal'
})

// 预计续航（分钟）：基于当前电量估算，初始为0
const estimatedRuntime = computed(() => {
  const percent = robot.value.batteryPercent ?? 0
  if (percent <= 0) return 0
  // 假设满电可工作30分钟，按比例计算
  const maxRuntime = 30
  return Math.floor((percent / 100) * maxRuntime)
})
</script>

<style scoped>
.robot-status-card {
  margin-bottom: 0;
  overflow: visible;
}

.card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 500;
  margin-bottom: 4px;
}

.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px 16px;
}

.info-item {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  font-size: 14px;
  padding: 8px 0;    /* 增加上下内边距 */
}

.info-item label {
  color: #6b7280;
  font-weight: 500;
  flex-shrink: 0;
  margin-right: 8px;
}

.info-item span {
  font-weight: 500;
  color: #111827;
  text-align: right;
  word-break: keep-all;
}

.normal { color: #10b981; }
.warning { color: #f59e0b; }
.danger { color: #ef4444; }

.charging-icon {
  margin-left: 4px;
  animation: rotate 1s linear infinite;
}

@keyframes rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>