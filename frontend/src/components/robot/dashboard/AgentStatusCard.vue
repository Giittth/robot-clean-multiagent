<template>
  <el-card class="agent-status-card" shadow="hover">
    <template #header>
      <div class="card-header">
        <span>Agent 状态</span>
        <el-tag size="small" type="info">控制权: {{ controlOwner }}</el-tag>
      </div>
    </template>
    <div class="agent-list">
      <div v-for="agent in agentsList" :key="agent.name" class="agent-item">
        <div class="agent-name">
          <span class="status-dot" :class="agent.alive ? 'alive' : 'dead'"></span>
          {{ agent.name }}
        </div>
        <div class="agent-detail">
          <span v-if="agent.extra">{{ agent.extra }}</span>
        </div>
      </div>
    </div>
  </el-card>
</template>

<script setup>
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useRobotStore } from '@/stores/robot/robotStore.js'

const robotStore = useRobotStore()
const { agentsHeartbeat, controlOwner } = storeToRefs(robotStore)

// 定义需要监控的 Agent 列表
const agentsList = computed(() => [
  { name: 'Supervisor', alive: agentsHeartbeat.value.supervisor ?? false },
  { name: 'Planner', alive: agentsHeartbeat.value.planner ?? false },
  { name: 'Dispatcher', alive: agentsHeartbeat.value.dispatcher ?? false },
  { name: 'Navigation', alive: agentsHeartbeat.value.navigation ?? false },
  { name: 'Execution', alive: agentsHeartbeat.value.execution ?? false },
  { name: 'WorldModel', alive: agentsHeartbeat.value.worldModel ?? false },
  { name: 'Perception', alive: agentsHeartbeat.value.perception ?? false }
])
</script>

<style scoped>
.agent-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.agent-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 0;
  border-bottom: 1px solid #f0f0f0;
}
.agent-name {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 500;
}
.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: inline-block;
}
.status-dot.alive {
  background-color: #10b981;
  box-shadow: 0 0 4px #10b981;
}
.status-dot.dead {
  background-color: #ef4444;
}
.agent-detail {
  font-size: 12px;
  color: #888;
}
</style>