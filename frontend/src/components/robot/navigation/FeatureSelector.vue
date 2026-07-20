<template>
  <div class="feature-selector">
    <div class="feature-label">
      <el-icon><Grid /></el-icon>
      <span>更多功能</span>
    </div>
    <el-select
      v-model="selected"
      placeholder="选择功能"
      @change="handleSelect"
      size="default"
      style="width: 104px;"
    >
      <el-option label="定时任务" value="schedule"></el-option>
      <el-option label="定位功能" value="position"></el-option>
      <el-option label="语音播报" value="tts"></el-option>
    </el-select>

    <el-dialog v-model="showSchedule" title="定时任务" width="520px" append-to-body :close-on-click-modal="false" class="draggable-dialog" @opened="onDialogOpened">
      <SchedulePanel />
    </el-dialog>

    <el-dialog v-model="showPosition" title="定位功能" width="380px" append-to-body :close-on-click-modal="false" class="draggable-dialog">
      <PositionDialog />
    </el-dialog>

  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Grid, ChatDotRound } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import SchedulePanel from '@/components/robot/mission/SchedulePanel.vue'
import PositionDialog from '@/components/robot/navigation/PositionDialog.vue'

const selected = ref('')
const showSchedule = ref(false)
const showPosition = ref(false)

function handleSelect(val) {
  if (val === 'schedule') {
    showSchedule.value = true
  } else if (val === 'position') {
    showPosition.value = true
  } else if (val === 'tts') {
    ttsEnabled.value = !ttsEnabled.value
    handleTTSChange(ttsEnabled.value)
  }
  selected.value = ''
}

// TTS toggle: stored in localStorage for cross-component access
const ttsEnabled = ref(localStorage.getItem('tts_enabled') === 'true')

function handleTTSChange(val) {
  localStorage.setItem('tts_enabled', val ? 'true' : 'false')
  ElMessage({
    message: val ? '自动语音播报已开启' : '已关闭自动语音播报',
    type: val ? 'success' : 'info',
    duration: 2000,
  })
}

function onDialogOpened() {
  const dialog = document.querySelector('.draggable-dialog')
  if (!dialog) return
  const header = dialog.querySelector('.el-dialog__header')
  if (!header) return
  header.style.cursor = 'move'

  let dragging = false, startX, startY, left, top
  header.onmousedown = (e) => {
    dragging = true
    startX = e.clientX; startY = e.clientY
    left = dialog.offsetLeft; top = dialog.offsetTop
    document.onmousemove = (e) => {
      if (!dragging) return
      dialog.style.left = (left + e.clientX - startX) + 'px'
      dialog.style.top = (top + e.clientY - startY) + 'px'
      dialog.style.margin = '0'
    }
    document.onmouseup = () => { dragging = false; document.onmousemove = null }
  }
}
</script>

<style scoped>
.feature-selector {
  display: flex;
  align-items: center;
  gap: 12px;
  background: #f9fafb;
  padding: 6px 8px;
  border-radius: 8px;
}
.feature-label {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #1f2937;
  font-weight: 500;
  font-size: 14px;
}
</style>

<style>
/* 拖拽 dialog 全局样式（不能 scoped，因为 dialog append-to-body） */
.draggable-dialog { position: relative !important; }
.draggable-dialog .el-dialog__header { user-select: none; }
.draggable-inner-dialog { position: relative !important; }
.draggable-inner-dialog .el-dialog__header { user-select: none; }
</style>