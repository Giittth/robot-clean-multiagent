<template>
  <div class="position-dialog">
    <div class="section">
      <div class="section-title">Current Position</div>
      <div class="pose-grid">
        <div class="pose-item">
          <span class="label">X</span>
          <span class="value">{{ (robot.pose.x).toFixed(2) }}</span>
        </div>
        <div class="pose-item">
          <span class="label">Y</span>
          <span class="value">{{ (robot.pose.y).toFixed(2) }}</span>
        </div>
        <div class="pose-item">
          <span class="label">Theta</span>
          <span class="value">{{ (robot.pose.theta * 180 / Math.PI).toFixed(1) }}&deg;</span>
        </div>
      </div>
    </div>
    <div class="section">
      <div class="section-title">Navigation</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:13px">
        <div>Mode: <el-tag size="small">{{ navigation.mode }}</el-tag></div>
        <div>Path index: {{ navigation.pathIndex }}</div>
        <div>Path length: {{ navigation.path.length }}</div>
        <div>Control: {{ navigation.controlOwner }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useRobotStore } from '@/stores/robot/robotStore'

const robotStore = useRobotStore()
const { robot, navigation } = storeToRefs(robotStore)
</script>

<style scoped>
.position-dialog {
  min-height: 120px;
}
.section {
  margin-bottom: 16px;
}
.section-title {
  font-weight: 600;
  font-size: 14px;
  color: #303133;
  margin-bottom: 10px;
  padding-bottom: 6px;
  border-bottom: 1px solid #ebeef5;
}
.pose-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}
.pose-item {
  text-align: center;
  background: #f5f7fa;
  border-radius: 8px;
  padding: 12px;
}
.pose-item .label {
  display: block;
  font-size: 11px;
  color: #909399;
  margin-bottom: 4px;
}
.pose-item .value {
  font-size: 20px;
  font-weight: 700;
  color: #409eff;
  font-family: 'Courier New', monospace;
}
</style>