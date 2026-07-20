<template>
  <el-card class="lifecycle-card" shadow="hover">
    <template #header>
      <div class="card-title">
        <el-icon><Connection /></el-icon>
        <span>机器人生命周期</span>
      </div>
    </template>
    <div class="states">
      <div
        v-for="state in states"
        :key="state.value"
        class="state-item"
        :class="{
          active: powerState === state.value,
          error: powerState === 'EMERGENCY_STOP' && state.value === 'EMERGENCY_STOP'
        }"
      >
        <span class="dot"></span>
        <span class="state-name">{{ state.label }}</span>
      </div>
    </div>
  </el-card>
</template>

<script setup>
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useRobotStore } from '@/stores/robot/robotStore'
import { Connection } from '@element-plus/icons-vue'

const robotStore = useRobotStore()
const { powerState } = storeToRefs(robotStore)

// 状态顺序（按生命周期流转顺序排列）
const states = [
  { value: 'OFF', label: '关机' },
  { value: 'BOOTING', label: '启动中' },
  { value: 'IDLE', label: '空闲' },
  { value: 'WORKING', label: '工作' },
  { value: 'CHARGING', label: '充电' },
  { value: 'PAUSED', label: '暂停' },
  { value: 'EMERGENCY_STOP', label: '急停' }
]

// 判断前置状态是否已完成（用于高亮已走过的状态，可选）
function isCompleted(stateValue) {
  const order = states.map(s => s.value)
  const currentIndex = order.indexOf(powerState.value)
  const stateIndex = order.indexOf(stateValue)
  // 如果当前状态之后的状态，不算完成；之前的不做标记，只高亮当前
  return false // 简单实现只高亮当前状态，不处理已完成
}
</script>

<style scoped>
.lifecycle-card {
  margin-bottom: 0;
  overflow: visible;
}
.card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 500;
}
.states {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 8px;
}
.state-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  padding: 4px 8px;
  border-radius: 20px;
  background-color: #f5f7fa;
  color: #909399;
  transition: all 0.2s;
}
.state-item.active {
  background-color: #ecf5ff;
  color: #409eff;
  font-weight: 500;
}
.state-item.active .dot {
  background-color: #409eff;
  box-shadow: 0 0 4px #409eff;
}
.state-item.error {
  background-color: #fef0f0;
  color: #f56c6c;
}
.state-item.error .dot {
  background-color: #f56c6c;
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #dcdfe6;
  display: inline-block;
}
.state-name {
  line-height: 1;
}
</style>