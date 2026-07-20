<template>
  <div class="task-control-panel">
    <div class="task-input">
      <el-input
        v-model="taskText"
        placeholder="输入自然语言任务，例如：清扫客厅"
        clearable
        @keyup.enter="sendTask"
      />
      <el-button type="primary" @click="sendTask" :loading="sendingTask">
        发送任务
      </el-button>
    </div>
    <div class="control-buttons">
      <el-button type="primary" @click="sendControl('power_on')">开机</el-button>
      <el-button type="danger" @click="sendControl('power_off')">关机</el-button>
      <el-button type="warning" @click="sendControl('pause')">暂停</el-button>
      <el-button type="info" @click="sendControl('resume')">恢复</el-button>
      <el-button type="danger" @click="sendControl('stop')">停止</el-button>
      <el-button type="warning" @click="sendControl('emergency_stop')">急停</el-button>
      <el-button type="info" @click="sendControl('reset')">重置急停</el-button>
      <el-button type="success" @click="sendControl('recharge')">充电</el-button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useRobotStore } from '@/stores/robot/robotStore.js'
import { ElMessage } from 'element-plus'

const robotStore = useRobotStore()
const { taskState, powerState } = storeToRefs(robotStore)   // 从 store 获取任务状态
const sendingTask = ref(false)

// 自然语言任务输入
const taskText = ref('')

// 发送任务 (调用 API)
async function sendTask() {
  if (!taskText.value.trim()) {
    ElMessage.warning('请输入任务内容')
    return
  }
  sendingTask.value = true
  try {
    // 调用后端 API (通过 api/robot/mission.js 中的方法)
    await robotStore.sendTask(taskText.value)
    ElMessage.success('任务已发送')
    taskText.value = ''
  } catch (e) {
    ElMessage.error('发送任务失败')
  } finally {
    sendingTask.value = false
  }
}

// 发送控制指令 (暂停/恢复/停止/急停/重置/充电)
async function sendControl(command) {
  try {
    await robotStore.sendControl(command)
    ElMessage.success(`已发送 ${command} 指令`)
  } catch (e) {
    ElMessage.error(`发送 ${command} 指令失败`)
  }
}
</script>

<style scoped>
.task-control-panel {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}
.task-input {
  display: flex;
  gap: 8px;
  flex: 2;
  min-width: 300px;
}
.control-buttons {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
</style>