<template>
  <div class="lifecycle-bar">
    <div
      v-for="state in states"
      :key="state.value"
      class="lifecycle-item"
      :class="{
        active: powerState === state.value,
        completed: isCompleted(state.value)
      }"
    >
      <span class="dot"></span>
      <span class="label">{{ state.label }}</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useRobotStore } from '@/stores/robot/robotStore'

const robotStore = useRobotStore()
const { powerState } = storeToRefs(robotStore)

// 状态顺序（按生命周期流转顺序，可根据需要调整）
const states = [
  { value: 'OFF', label: '关机' },
  { value: 'BOOTING', label: '启动中' },
  { value: 'IDLE', label: '空闲' },
  { value: 'WORKING', label: '工作' },
  { value: 'CHARGING', label: '充电' },
  { value: 'PAUSED', label: '暂停' },
  { value: 'EMERGENCY_STOP', label: '急停' }
]

// 判断前置状态是否已完成（可用来高亮已走过的步骤，当前仅简单比较）
function isCompleted(stateValue) {
  const order = states.map(s => s.value)
  const currentIndex = order.indexOf(powerState.value)
  const stateIndex = order.indexOf(stateValue)
  // 如果当前状态之后的状态，不算完成；之前的不做特殊处理，这里只高亮当前状态
  return false
}
</script>

<style scoped>
.lifecycle-bar {
  display: flex;
  align-items: center;
  gap: 14px;
  background: #f5f7fa;
  padding: 8px 16px;
  border-radius: 24px;
  margin-left: 16px;        /* 原 margin: 0 16px，现改为左侧无外边距 */
  margin-right: 16px;
}
.lifecycle-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  color: #909399;
  transition: all 0.2s;
}
.lifecycle-item .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #dcdfe6;
}
.lifecycle-item.active {
  color: #409eff;
  font-weight: 500;
}
.lifecycle-item.active .dot {
  background-color: #409eff;
  box-shadow: 0 0 4px #409eff;
}
.lifecycle-item.completed {
  color: #67c23a;
}
.lifecycle-item.completed .dot {
  background-color: #67c23a;
}
</style>