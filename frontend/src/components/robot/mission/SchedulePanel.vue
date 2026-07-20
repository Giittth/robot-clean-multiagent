<template>
  <div class="schedule-panel">
    <div class="schedule-header">
      <el-button type="primary" size="small" @click="showAdd = true">
        <el-icon><Plus /></el-icon> 新建
      </el-button>
    </div>

    <!-- 任务列表 -->
    <div class="schedule-list" v-if="schedules.length > 0">
      <div v-for="s in schedules" :key="s.id" class="schedule-item" :class="{ disabled: !s.enabled }">
        <div class="item-main">
          <div class="item-command">{{ s.command }}</div>
          <div class="item-meta">
            <el-tag size="small" :type="s.enabled ? 'success' : 'info'">
              {{ s.enabled ? '启用' : '停用' }}
            </el-tag>
            <span class="cron-text">{{ formatCron(s.cron_expression) }}</span>
            <span v-if="s.next_run" class="next-run">下次: {{ formatTime(s.next_run) }}</span>
          </div>
        </div>
        <div class="item-actions">
          <el-switch :model-value="!!s.enabled" @change="toggle(s)" size="small" />
          <el-button text type="danger" size="small" @click="remove(s.id)">
            <el-icon><Delete /></el-icon>
          </el-button>
        </div>
      </div>
    </div>
    <el-empty v-else description="暂无定时任务" :image-size="60" />

    <!-- 新建对话框 -->
    <el-dialog
      v-model="showAdd"
      title="新建定时任务"
      width="420px"
      append-to-body
      :close-on-click-modal="false"
      class="draggable-inner-dialog"
      @opened="onInnerDialogOpened"
    >
      <el-form :model="form" label-width="80px" size="default">
        <el-form-item label="任务指令">
          <el-input v-model="form.command" placeholder="如：清扫客厅" />
        </el-form-item>
        <el-form-item label="Cron 表达式">
          <el-input v-model="form.cron" placeholder="0 10 * * * (每天10:00)" />
        </el-form-item>
        <el-form-item label="快捷设置">
          <el-select v-model="preset" placeholder="选择预设" @change="applyPreset" style="width:100%">
            <el-option label="每天 10:00" value="0 10 * * *" />
            <el-option label="每天 18:00" value="0 18 * * *" />
            <el-option label="每周一三五 9:00" value="0 9 * * 1,3,5" />
            <el-option label="每周六日 14:00" value="0 14 * * 6,0" />
            <el-option label="每 30 分钟" value="*/30 * * * *" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.desc" placeholder="可选描述" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAdd = false">取消</el-button>
        <el-button type="primary" @click="create" :disabled="!form.command || !form.cron" :loading="creating">
          创建
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Timer, Plus, Delete } from '@element-plus/icons-vue'
import { getSchedules, createSchedule, deleteSchedule, toggleSchedule } from '@/api/robot/schedule'

const schedules = ref([])
const showAdd = ref(false)
const creating = ref(false)
const preset = ref('')
const form = reactive({ command: '', cron: '', desc: '' })

const CRON_LABELS = {
  '0 10 * * *': '每天 10:00',
  '0 18 * * *': '每天 18:00',
  '0 9 * * 1,3,5': '每周一三五 9:00',
  '0 14 * * 6,0': '每周六日 14:00',
}

async function load() {
  try {
    const result = await getSchedules(0)
    console.log('Schedules loaded:', result)
    schedules.value = Array.isArray(result) ? result : []
  } catch (e) {
    console.error('Schedule load error:', e)
    schedules.value = []
  }
}

function applyPreset(val) {
  form.cron = val
}

function formatCron(expr) {
  return CRON_LABELS[expr] || expr
}

function formatTime(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

async function create() {
  if (creating.value) return
  creating.value = true
  try {
    const result = await createSchedule({ command: form.command, cron_expression: form.cron, description: form.desc })
    console.log('Schedule created:', result)
    ElMessage.success('定时任务已创建')
    showAdd.value = false
    form.command = ''; form.cron = ''; form.desc = ''
    await load()
  } catch (e) {
    console.error('Schedule create error:', e)
    const msg = e?.response?.data?.detail || e?.message || '创建失败'
    ElMessage.error(msg)
  } finally {
    creating.value = false
  }
}

async function remove(id) {
  try {
    await ElMessageBox.confirm('确定删除该定时任务？', '提示', { type: 'warning' })
    await deleteSchedule(id)
    ElMessage.success('已删除')
    await load()
  } catch { /* cancelled */ }
}

async function toggle(s) {
  const enabled = !s.enabled
  try {
    await toggleSchedule(s.id, enabled)
    s.enabled = enabled
    ElMessage.success(enabled ? '已启用' : '已停用')
  } catch { /* ignore */ }
}

onMounted(load)

function onInnerDialogOpened() {
  const dialog = document.querySelector('.draggable-inner-dialog')
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
.schedule-panel { padding: 8px 0; }
.schedule-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 12px;
}
.panel-title {
  display: flex; align-items: center; gap: 6px;
  font-weight: 600; font-size: 15px; color: #1f2937;
}
.schedule-list {
  display: flex; flex-direction: column; gap: 8px;
  max-height: 320px; overflow-y: auto;
}
.schedule-item {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 12px; background: #f9fafb; border-radius: 8px;
  border: 1px solid #e5e7eb;
}
.schedule-item.disabled { opacity: 0.5; }
.item-command { font-weight: 500; color: #1f2937; font-size: 14px; }
.item-meta { display: flex; align-items: center; gap: 10px; margin-top: 4px; }
.cron-text { font-size: 12px; color: #6b7280; }
.next-run { font-size: 12px; color: #3b82f6; }
.item-actions { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
</style>