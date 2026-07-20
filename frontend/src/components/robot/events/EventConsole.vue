<template>
  <div class="event-console">
    <div class="console-header">
      <span>事件流监控</span>
      <div class="filters">
        <el-check-tag v-for="level in levels" :key="level" :checked="activeLevels.includes(level)" @click="toggleLevel(level)">
          {{ level }}
        </el-check-tag>
        <el-button size="small" @click="clearEvents">清空</el-button>
      </div>
    </div>
    <div class="console-body" ref="consoleBody">
      <div v-for="evt in filteredEvents" :key="evt.id" class="event-item" :class="evt.level">
        <span class="event-time">{{ formatTime(evt.timestamp) }}</span>
        <span class="event-type">{{ evt.type }}</span>
        <span class="event-message">{{ evt.message }}</span>
      </div>
      <div v-if="filteredEvents.length === 0" class="empty">无事件</div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { storeToRefs } from 'pinia'
import { useEventStore } from '@/stores/robot/eventStore.js'   // 专门存储事件流

const eventStore = useEventStore()
const { events } = storeToRefs(eventStore)

const levels = ['INFO', 'WARNING', 'ERROR']
const activeLevels = ref(['INFO', 'WARNING', 'ERROR'])

const toggleLevel = (level) => {
  const idx = activeLevels.value.indexOf(level)
  if (idx === -1) activeLevels.value.push(level)
  else activeLevels.value.splice(idx, 1)
}

const filteredEvents = computed(() => {
  return events.value.filter(e => activeLevels.value.includes(e.level))
})

const clearEvents = () => eventStore.clearEvents()

const consoleBody = ref(null)
// 自动滚动到底部
watch(filteredEvents, () => {
  nextTick(() => {
    if (consoleBody.value) consoleBody.value.scrollTop = consoleBody.value.scrollHeight
  })
}, { deep: true })

function formatTime(timestamp) {
  const date = new Date(timestamp)
  return date.toLocaleTimeString('zh-CN', { hour12: false })
}
</script>

<style scoped>
.event-console {
  background: #ffffff;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  margin-top: 20px;
  overflow: hidden;
  font-family: 'Courier New', monospace;
  font-size: 12px;
}

.console-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  background: #f5f7fa;
  border-bottom: 1px solid #e4e7ed;
  font-weight: 500;
  color: #1f2f3d;
}

.filters {
  display: flex;
  gap: 8px;
  align-items: center;
}

.console-body {
  height: 250px;
  overflow-y: auto;
  background: #fafbfc;
}

.event-item {
  display: flex;
  gap: 16px;
  padding: 6px 16px;
  border-bottom: 1px solid #f0f0f0;
  font-size: 12px;
  transition: background 0.1s;
}

.event-item:hover {
  background: #f5f7fa;
}

.event-time {
  width: 80px;
  color: #6b7280;
  font-family: monospace;
}

.event-type {
  width: 140px;
  font-weight: 500;
  word-break: keep-all;
}

.event-message {
  flex: 1;
  color: #374151;
  word-break: break-all;
}

/* 级别颜色 */
.event-item.INFO .event-type {
  color: #3b82f6;   /* 蓝色 */
}
.event-item.WARNING .event-type {
  color: #f59e0b;   /* 橙色 */
}
.event-item.ERROR .event-type {
  color: #ef4444;   /* 红色 */
}

.empty {
  text-align: center;
  padding: 24px;
  color: #9ca3af;
}
</style>