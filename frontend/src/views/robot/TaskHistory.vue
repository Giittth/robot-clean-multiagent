<template>
  <div class="task-history-container">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>任务历史</span>
          <el-button type="danger" size="small" @click="clearHistory" :disabled="history.length === 0">清空所有</el-button>
        </div>
      </template>

      <!-- 加载中 -->
      <div v-if="loading" style="text-align:center;padding:40px;">
        <span>加载中...</span>
      </div>

      <!-- 加载失败 -->
      <div v-else-if="loadError" style="text-align:center;padding:40px;">
        <p style="color:#f56c6c;">{{ loadError }}</p>
        <el-button @click="retryLoad">重试</el-button>
      </div>

      <!-- 数据表格 -->
      <template v-else>
        <el-table :data="history" stripe style="width: 100%">
          <el-table-column prop="taskId" label="任务指令" width="140" show-overflow-tooltip></el-table-column>
          <el-table-column prop="graphId" label="来源" width="180" show-overflow-tooltip>
            <template #default="{ row }">
              <el-tag v-if="row.source === 'chat'" type="info" size="small">远程对话</el-tag>
              <el-tag v-else-if="row.missionId || row.source === 'mission'" type="primary" size="small">机器人任务</el-tag>
              <span v-else>{{ row.graphId || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="timestamp" label="时间" width="160">
            <template #default="{ row }">
              {{ formatTime(row.timestamp) }}
            </template>
          </el-table-column>
          <el-table-column prop="success" label="状态" width="70">
            <template #default="{ row }">
              <el-tag :type="row.status === 'completed' || row.status === 'success' ? 'success' : row.status === 'running' ? 'warning' : 'danger'" size="small">
                {{ row.status === 'completed' || row.status === 'success' ? '成功' : row.status === 'running' ? '进行中' : '失败' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="180">
            <template #default="{ row }">
              <el-button link type="primary" @click="showDetail(row)">详情</el-button>
              <el-button link type="primary" @click="startReplay(row)" >回放</el-button>
              <el-button link type="danger" @click="confirmDelete(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="history.length === 0" description="暂无任务历史" />
      </template>
    </el-card>

    <!-- 详情对话框 -->
    <el-dialog v-model="detailVisible" title="任务详情" width="500px">
      <div v-if="selectedTask">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="任务指令">{{ selectedTask.taskId || '-' }}</el-descriptions-item>
          <el-descriptions-item label="来源">
            <el-tag v-if="selectedTask.source === 'chat'" type="info" size="small">远程对话</el-tag>
            <el-tag v-else-if="selectedTask.missionId || selectedTask.source === 'mission'" type="primary" size="small">机器人任务</el-tag>
            <span v-else>未知</span>
          </el-descriptions-item>
          <el-descriptions-item label="状态">{{ selectedTask.status === 'completed' || selectedTask.status === 'success' ? '成功' : selectedTask.status === 'running' ? '进行中' : '失败' }}</el-descriptions-item>
          <el-descriptions-item label="耗时">
            {{ selectedTask.duration ? (selectedTask.duration).toFixed(1) : '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="时间">{{ formatTime(selectedTask.timestamp) }}</el-descriptions-item>
          <el-descriptions-item label="错误信息" v-if="selectedTask.error">{{ selectedTask.error }}</el-descriptions-item>
        </el-descriptions>
      </div>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 回放对话框 -->
    <el-dialog v-model="replayVisible" :title="replayTitle" width="880px"
      @opened="onReplayOpened" @closed="onReplayClosed">
      <div v-if="replayLoading" style="text-align:center;padding:60px;">加载轨迹数据...</div>
      <div v-else-if="replayError" style="text-align:center;padding:40px;color:#f56c6c;">{{ replayError }}</div>
      <div v-else>
        <!-- Trajectory replay mode (robot tasks with missionId) -->
        <template v-if="replayMode === 'trajectory'">
          <div style="margin-bottom:8px;font-size:13px;color:#555;">
            指令：<b>{{ replayTask?.taskId || '-' }}</b>&nbsp;&nbsp;
            轨迹点：<b>{{ replayPoints.length }}</b>
          </div>
          <canvas ref="replayCanvasRef" width="800" height="450"
            style="border:1px solid #e5e7eb;border-radius:8px;background:#fafafa;width:100%;height:auto;"></canvas>
          <div style="display:flex;align-items:center;gap:8px;margin-top:8px;">
            <el-button :type="replayPlaying ? 'warning' : 'primary'" size="small" @click="togglePlay">
              {{ replayPlaying ? '暂停' : '播放' }}
            </el-button>
            <el-button size="small" @click="resetReplay">重置</el-button>
            <span style="font-size:13px;color:#888;">{{ replayProgress }} / {{ replayMax }}</span>
          </div>
        </template>
        <!-- Text replay mode (chat entries without missionId) -->
        <template v-else>
          <div style="padding:20px;">
            <el-descriptions :column="1" border>
              <el-descriptions-item label="指令内容">
                {{ replayTask?.taskId || '-' }}
              </el-descriptions-item>
              <el-descriptions-item label="执行结果">
                <el-tag :type="replayTask?.status === 'completed' || replayTask?.status === 'success' ? 'success' : replayTask?.status === 'running' ? 'warning' : 'danger'" size="small">
                  {{ replayTask?.status === 'completed' || replayTask?.status === 'success' ? '成功' : replayTask?.status === 'running' ? '进行中' : '失败' }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="时间">
                {{ formatTime(replayTask?.timestamp) }}
              </el-descriptions-item>
              <el-descriptions-item label="耗时" v-if="replayTask?.duration">
                {{ replayTask.duration.toFixed(1) }} 秒
              </el-descriptions-item>
              <el-descriptions-item label="错误信息" v-if="replayTask?.error">
                {{ replayTask.error }}
              </el-descriptions-item>
              <el-descriptions-item label="来源">
                <el-tag v-if="replayTask?.source === 'chat'" type="info" size="small">远程对话</el-tag>
                <el-tag v-else-if="replayTask?.missionId || replayTask?.source === 'mission'" type="primary" size="small">机器人任务</el-tag>
              <span v-else>未知</span>
              </el-descriptions-item>
            </el-descriptions>
          </div>
        </template>
      </div>
      <template #footer>
        <el-button @click="replayVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { storeToRefs } from 'pinia'
import { useMissionStore } from '@/stores/robot/missionStore'
import { getMissionReplay } from '@/api/robot/mission'
import { ElMessage, ElMessageBox } from 'element-plus'

const missionStore = useMissionStore()
const { history } = storeToRefs(missionStore)

const loading = ref(true)
const loadError = ref('')
const detailVisible = ref(false)
const selectedTask = ref(null)

// 回放
const replayVisible = ref(false)
const replayLoading = ref(false)
const replayError = ref('')
const replayTask = ref(null)
const replayPoints = ref([])
const replayProgress = ref(0)
const replayPlaying = ref(false)
const replayCanvasRef = ref(null)
let replayCtx = null
let replayTimer = null

const replayMax = ref(0)
const replayChatResponse = ref('')

function formatTime(ts) {
  if (!ts) return '-'
  // Handle both ISO strings and "YYYY-MM-DD HH:mm:ss" format from MySQL
  let d
  if (typeof ts === 'string' && ts.includes('-') && !ts.includes('T')) {
    d = new Date(ts.replace(' ', 'T') + 'Z')
  } else {
    d = new Date(ts)
  }
  if (isNaN(d.getTime())) {
    d = new Date(Number(ts))
    if (isNaN(d.getTime())) return String(ts)
  }
  return d.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

async function loadData() {
  loading.value = true
  loadError.value = ''
  try {
    // 先加载本地缓存
    missionStore.loadHistoryFromLocal()
    // 再从 API 刷新
    await missionStore.loadHistoryFromAPI()
    console.log('[TaskHistory] Loaded', missionStore.history.length, 'records')
  } catch (e) {
    console.error('[TaskHistory] Load failed:', e)
    loadError.value = '加载失败：' + (e.message || '网络错误')
    // 回退到本地
    missionStore.loadHistoryFromLocal()
  } finally {
    loading.value = false
  }
}

function retryLoad() { loadData() }

function clearHistory() {
  missionStore.clearHistory()
  ElMessage.success('已清空')
}

function showDetail(row) {
  selectedTask.value = row
  detailVisible.value = true
}

// ── 回放 ──
const replayMode = ref('trajectory')
const replayTitle = computed(() => {
  return replayMode.value === 'trajectory' ? '任务轨迹回放' : '任务详情回放'
})

async function startReplay(row) {
  replayTask.value = row
  replayVisible.value = true

  if (row.missionId) {
    // Trajectory replay for robot tasks
    replayMode.value = 'trajectory'
    replayLoading.value = true
    replayError.value = ''
    replayPoints.value = []
    replayProgress.value = 0
    replayPlaying.value = false

    try {
      const data = await getMissionReplay(row.missionId)
      const pts = Array.isArray(data) ? data : (data?.points || [])
      replayPoints.value = pts
      replayMax.value = Math.max(0, pts.length - 1)
      if (pts.length === 0) replayError.value = '该任务无轨迹记录'
    } catch (e) {
      console.error('[Replay] load error:', e)
      replayError.value = '加载轨迹失败'
    } finally {
      replayLoading.value = false
    }
  } else {
    // Text replay for chat entries
    replayMode.value = 'text'
    replayLoading.value = false
    replayError.value = ''
    replayChatResponse.value = row.answer || ''
  }
}

function onReplayOpened() {
  nextTick(() => {
    if (replayCanvasRef.value) {
      replayCtx = replayCanvasRef.value.getContext('2d')
      drawFrame()
    }
  })
}

function onReplayClosed() {
  stopTimer()
  replayCtx = null
}

function world2screen(wx, wy) {
  const c = replayCanvasRef.value
  if (!c) return [0, 0]
  return [c.width / 2 + wx * 25, c.height / 2 - wy * 25]
}

function drawFrame() {
  if (!replayCtx || !replayCanvasRef.value) return
  const c = replayCanvasRef.value
  const ctx = replayCtx
  ctx.clearRect(0, 0, c.width, c.height)
  const pts = replayPoints.value
  if (!pts.length) return

  const idx = replayProgress.value

  // 已走过的轨迹
  ctx.strokeStyle = '#10b981'; ctx.lineWidth = 3; ctx.beginPath()
  for (let i = 0; i <= Math.min(idx, pts.length - 1); i++) {
    const [sx, sy] = world2screen(pts[i].x, pts[i].y)
    i === 0 ? ctx.moveTo(sx, sy) : ctx.lineTo(sx, sy)
  }
  ctx.stroke()

  // 剩余轨迹
  if (idx < pts.length - 1) {
    ctx.strokeStyle = '#d1d5db'; ctx.lineWidth = 1.5; ctx.setLineDash([6, 4]); ctx.beginPath()
    for (let i = idx; i < pts.length; i++) {
      const [sx, sy] = world2screen(pts[i].x, pts[i].y)
      i === idx ? ctx.moveTo(sx, sy) : ctx.lineTo(sx, sy)
    }
    ctx.stroke(); ctx.setLineDash([])
  }

  // 当前位置
  if (idx < pts.length) {
    const [cx, cy] = world2screen(pts[idx].x, pts[idx].y)
    ctx.fillStyle = '#f59e0b'; ctx.beginPath(); ctx.arc(cx, cy, 6, 0, Math.PI * 2); ctx.fill()
  }
}

function tick() {
  if (!replayPlaying.value) return
  if (replayProgress.value < replayMax.value) {
    replayProgress.value++
    drawFrame()
    replayTimer = setTimeout(tick, 200)
  } else {
    replayPlaying.value = false
  }
}

function togglePlay() {
  if (replayPlaying.value) { replayPlaying.value = false; stopTimer() }
  else {
    if (replayProgress.value >= replayMax.value) replayProgress.value = 0
    replayPlaying.value = true
    tick()
  }
}

function resetReplay() {
  stopTimer()
  replayPlaying.value = false
  replayProgress.value = 0
  drawFrame()
}

function stopTimer() { if (replayTimer) { clearTimeout(replayTimer); replayTimer = null } }

function confirmDelete(row) {
  ElMessageBox.confirm('确定要删除这条记录吗？', '确认删除', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(async () => {
    try {
      await missionStore.deleteRecord(row)
      ElMessage.success('已删除')
    } catch (e) {
      ElMessage.error('删除失败')
    }
  }).catch(() => {})
}

onMounted(() => { loadData() })
</script>

<style scoped>
.task-history-container { padding: 20px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
</style>