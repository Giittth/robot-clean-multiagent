<template>
  <el-card class="health-card" shadow="hover">
    <template #header>系统健康</template>
    <div class="info-row">
      <label>Bus 队列</label>
      <span>{{ systemHealth.busQueue }}</span>
    </div>
    <div class="info-row">
      <label>Event 队列</label>
      <span>{{ systemHealth.eventQueue }}</span>
    </div>
    <div class="info-row">
      <label>会话不匹配</label>
      <span>{{ systemHealth.sessionMismatch }}</span>
    </div>
    <div class="info-row">
      <label>Generation 放弃</label>
      <span>{{ systemHealth.generationAbort }}</span>
    </div>
  </el-card>
</template>

<script setup>
import { storeToRefs } from 'pinia'
import { useRobotStore } from '@/stores/robot/robotStore'

const robotStore = useRobotStore()
const { systemHealth } = storeToRefs(robotStore)
</script>

<style scoped>
.health-card .info-row {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}
</style>