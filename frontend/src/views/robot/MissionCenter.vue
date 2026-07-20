<template>
  <div class="mission-center">
    <TaskControlPanel />

    <div class="dashboard">
      <!-- 左侧列：地图及控制 -->
      <div class="left-column">
        <div class="map-controls">
          <FeatureSelector />
          <SceneSelector />
          <RobotLifecycleBar />
          <div class="coverage-toggle">
            <span>显示覆盖区域</span>
            <el-switch v-model="showCoverage" />
          </div>
        </div>
        <MapView :show-coverage="showCoverage" :rooms="rooms" />
        <div class="ws-status-float">
          <el-tag :type="wsConnected ? 'success' : 'danger'" size="small">
            wsConnected: {{ wsConnected ? '已连接' : '断开' }}
          </el-tag>
        </div>
      </div>

      <!-- 右侧列：机器人状态 + 标签页 -->
      <div class="right-column">
        <RobotStatusCard />
        <el-tabs v-model="activeTab" type="border-card" class="mission-tabs">
          <el-tab-pane label="当前任务" name="current">
            <CurrentTaskCard />
          </el-tab-pane>
          <el-tab-pane label="日程管理" name="schedule">
            <SchedulePanel />
          </el-tab-pane>
          <el-tab-pane label="任务流程图" name="graph">
            <TaskGraphPanel />
          </el-tab-pane>
        </el-tabs>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useRobotStore } from '@/stores/robot/robotStore'
import TaskControlPanel from '@/components/robot/mission/TaskControlPanel.vue'
import FeatureSelector from '@/components/robot/navigation/FeatureSelector.vue'
import SceneSelector from '@/components/robot/navigation/SceneSelector.vue'
import RobotLifecycleBar from '@/components/robot/dashboard/RobotLifecycleBar.vue'
import MapView from '@/components/robot/navigation/MapView.vue'
import RobotStatusCard from '@/components/robot/dashboard/RobotStatusCard.vue'
import CurrentTaskCard from '@/components/robot/mission/CurrentTaskCard.vue'
import SchedulePanel from '@/components/robot/mission/SchedulePanel.vue'
import TaskGraphPanel from '@/components/robot/mission/TaskGraphPanel.vue'
import useRobotSSE from '@/composables/robot/useRobotSSE'
import { useMissionStore } from '@/stores/robot/missionStore'

const activeTab = ref('current')
const showCoverage = ref(true)

const robotStore = useRobotStore()
const { wsConnected, rooms } = storeToRefs(robotStore)

const missionStore = useMissionStore()

useRobotSSE()

onMounted(() => {
  missionStore.loadHistoryFromLocal()
})
</script>

<style scoped>
.mission-center {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
}

.dashboard {
  display: flex;
  gap: 16px;
  flex: 1;
  min-height: 0;
}

.left-column {
  flex: 2.2;
  display: flex;
  flex-direction: column;
  gap: 12px;
  position: relative;
}
.left-column .map-container {
  flex: 1;
  min-height: 0;
  margin-top: -15px;
}

.map-controls {
  display: flex;
  align-items: center;
  gap: 1px;
  flex-wrap: nowrap;
  margin-bottom: 12px;
  min-height: 40px;
  overflow: visible;
}

.map-controls :deep(.el-select),
.map-controls :deep(.el-input) {
  font-size: 12px;
}
.map-controls .coverage-toggle {
  margin-left: -10px;
}

.map-controls :deep(.el-button--small) {
  padding: 5px 10px;
  font-size: 10px;
}
.map-controls :deep(.lifecycle-bar) {
  margin-left: -6px !important;
  gap: 2px !important;
}
.map-controls :deep(.lifecycle-item) {
  margin-right: 10px;
}
.map-controls :deep(.lifecycle-item:last-child) {
  margin-right: 0;
}

.lifecycle-bar {
  padding: 4px 10px;
  gap: 8px;
  font-size: 12px;
}

.coverage-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  white-space: nowrap;
}

.right-column {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-top: -15px;
}

.mission-tabs {
  flex: 1;
  min-height: 0;
}

.mission-tabs :deep(.el-tabs__content) {
  overflow-y: auto;
}

.ws-status-float {
  position: absolute;
  top: 60px;
  right: 2px;
  z-index: 10;
  background: #f5f7fa;
  border-radius: 4px;
  padding: 2px 8px;
  pointer-events: none;
  white-space: nowrap;
  font-size: 12px;
}
</style>
