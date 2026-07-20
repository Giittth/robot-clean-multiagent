<template>
  <div class="map-container">
    <canvas ref="canvasRef" width="800" height="600" class="map-canvas" :class="{ editing: obstacleEditMode }"></canvas>
    <el-button
      class="obstacle-toggle-btn"
      :type="obstacleEditMode ? 'warning' : 'default'"
      size="small"
      @click="toggleEditMode"
    >{{ obstacleEditMode ? '\u9000\u51fa\u7f16\u8f91' : '\u7f16\u8f91\u969c\u788d\u7269' }}</el-button>
    <div v-if="obstacleEditMode" class="edit-hint">{{ '\u70b9\u51fb\u6dfb\u52a0\u969c\u788d\u7269\uff0c\u518d\u6b21\u70b9\u51fb\u53ef\u5220\u9664' }}</div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRobotStore } from '@/stores/robot/robotStore'
import { useMissionStore } from '@/stores/robot/missionStore'
import { ElMessage } from 'element-plus'

const props = defineProps({
  showCoverage: { type: Boolean, default: true },
  rooms: { type: Object, default: () => ({}) }
})

const robotStore = useRobotStore()
const missionStore = useMissionStore()
const { navigation, robot, laserData, obstacles, coverageGrid, mission, wsConnected } = storeToRefs(robotStore)

const pose = computed(() => robot.value?.pose ?? { x: 0, y: 0, theta: 0 })
const currentPath = computed(() => navigation.value?.path ?? [])
const pathIndex = computed(() => navigation.value?.pathIndex ?? 0)

const canvasRef = ref(null)
let ctx = null
let animationId = null

// 离屏 Canvas 用于缓存覆盖区域，避免每帧遍历全部栅格
let coverageCacheCanvas = null
let coverageCacheCtx = null
let coverageCacheValid = false

function ensureCoverageCache() {
  if (!coverageCacheCanvas) {
    coverageCacheCanvas = document.createElement('canvas')
    coverageCacheCanvas.width = 800
    coverageCacheCanvas.height = 600
    coverageCacheCtx = coverageCacheCanvas.getContext('2d')
    coverageCacheValid = false
  }
  return { canvas: coverageCacheCanvas, ctx: coverageCacheCtx }
}

// 高亮房间（悬浮效果）
const obstacleEditMode = ref(false)
let mouseWorldX = 0
let mouseWorldY = 0

const highlightedRoom = ref(null)

// 房间中英文映射（可后续改为动态加载）
const roomNameMap = {
  living_room: '客厅', bedroom: '卧室', kitchen: '厨房', bathroom: '卫生间',
  hallway: '走廊', stairs: '楼梯', toilet: '厕所',
  room_north_1: '北室1', room_north_2: '北室2', room_north_3: '北室3', room_north_4: '北室4',
  room_south_1: '南室1', room_south_2: '南室2', room_south_3: '南室3', room_south_4: '南室4',
  living_dining: '客餐厅', master_bedroom: '主卧', bedroom1: '卧室1', bedroom2: '卧室2',
  dining_room: '餐厅', foyer: '门厅',
  guest_bedroom: '客卧', study: '书房', garage: '车库',
  open_workspace: '开放工位', meeting_room_a: '会议室A', meeting_room_b: '会议室B',
  kitchenette: '茶水间', living_sleeping: '起居卧室',
  classroom_101: '101教室', classroom_102: '102教室',
  classroom_103: '103教室', classroom_104: '104教室',
  classroom_105: '105教室', classroom_106: '106教室',
  dining_hall: '餐厅大厅', storage: '储藏室', restroom: '洗手间',
  main_corridor: '主通道', food_court: '美食广场',
  shop_a: '店铺A', shop_b: '店铺B', shop_c: '店铺C',
  shop_d: '店铺D', shop_e: '店铺E', shop_f: '店铺F'
}

function worldToScreen(x, y) {
  const canvas = canvasRef.value
  if (!canvas) return [0, 0]
  const centerX = canvas.width / 2
  const centerY = canvas.height / 2
  return [centerX + x * 20, centerY - y * 20]
}

function drawGrid() {
  const canvas = canvasRef.value
  if (!canvas || !ctx) return
  const step = 50
  ctx.save()
  ctx.strokeStyle = '#e5e7eb'
  ctx.lineWidth = 0.5
  for (let x = 0; x < canvas.width; x += step) {
    ctx.beginPath()
    ctx.moveTo(x, 0)
    ctx.lineTo(x, canvas.height)
    ctx.stroke()
  }
  for (let y = 0; y < canvas.height; y += step) {
    ctx.beginPath()
    ctx.moveTo(0, y)
    ctx.lineTo(canvas.width, y)
    ctx.stroke()
  }
  ctx.restore()
}

function drawRooms() {
  if (!ctx) return
  const roomsData = props.rooms
  for (const [name, room] of Object.entries(roomsData)) {
    const polygon = room.polygon
    if (!polygon || polygon.length < 3) continue
    const points = polygon.map(p => worldToScreen(p[0], p[1]))
    ctx.beginPath()
    ctx.moveTo(points[0][0], points[0][1])
    for (let i = 1; i < points.length; i++) {
      ctx.lineTo(points[i][0], points[i][1])
    }
    ctx.closePath()
    const isHighlight = (name === highlightedRoom.value)
    ctx.fillStyle = isHighlight ? 'rgba(0, 123, 255, 0.4)' : 'rgba(0, 123, 255, 0.15)'
    ctx.strokeStyle = isHighlight ? '#0056b3' : '#007bff'
    ctx.fill()
    ctx.stroke()
    // 房间名
    const displayName = roomNameMap[name] || name
    let center = room.center
    if (!center && polygon.length >= 2) {
      const xs = polygon.map(p => p[0])
      const ys = polygon.map(p => p[1])
      center = [(Math.min(...xs) + Math.max(...xs)) / 2, (Math.min(...ys) + Math.max(...ys)) / 2]
    }
    if (center) {
      const [cx, cy] = worldToScreen(center[0], center[1])
      ctx.font = '14px "Microsoft YaHei"'
      ctx.fillStyle = '#333'
      ctx.fillText(displayName, cx - 20, cy - 10)
    }
  }
}

function drawObstacles() {
  if (!obstacles.value || !Array.isArray(obstacles.value) || obstacles.value.length === 0) return
  ctx.save()
  for (const obs of obstacles.value) {
    const pos = obs.position || obs.center
    if (!pos) continue
    if (obs.type === 'circle') {
      const [x, y] = pos
      const radius = obs.radius || 0.2
      const [sx, sy] = worldToScreen(x, y)
      ctx.beginPath()
      ctx.arc(sx, sy, radius * 20, 0, 2 * Math.PI)
      ctx.fillStyle = '#cbd5e1'
      ctx.fill()
      ctx.strokeStyle = '#64748b'
      ctx.stroke()
    } else if (obs.type === 'rect') {
      const [cx, cy] = pos
      const w = obs.width || 0.4
      const h = obs.height || 0.4
      const left = cx - w / 2
      const right = cx + w / 2
      const bottom = cy - h / 2
      const top = cy + h / 2
      const [sx1, sy1] = worldToScreen(left, top)
      const [sx2, sy2] = worldToScreen(right, bottom)
      const width = sx2 - sx1
      const height = sy2 - sy1
      ctx.fillStyle = '#cbd5e1'
      ctx.fillRect(sx1, sy1, width, height)
      ctx.strokeStyle = '#64748b'
      ctx.strokeRect(sx1, sy1, width, height)
    }
  }
  ctx.restore()
}

function drawCoverage() {
  if (!props.showCoverage) return
  const grid = coverageGrid.value
  if (!grid || !Array.isArray(grid) || grid.length === 0) return

  // 如果缓存失效，重建离屏 Canvas
  if (!coverageCacheValid) {
    const { canvas, ctx: offCtx } = ensureCoverageCache()
    offCtx.clearRect(0, 0, canvas.width, canvas.height)
    const rows = grid.length
    const cols = grid[0]?.length || 0
    // 根据 grid 尺寸自适应 origin（假设 grid 中心对齐世界原点）
    const originX = Math.floor(cols / 2)
    const originY = Math.floor(rows / 2)
    const resolution = 0.2
    let coveredCount = 0
    for (let row = 0; row < rows; row++) {
      const line = grid[row]
      if (!line) continue
      for (let col = 0; col < line.length; col++) {
        if (line[col] > 0) {
          coveredCount++
          const wx = (col - originX) * resolution
          const wy = (row - originY) * resolution
          const [sx, sy] = worldToScreen(wx, wy)
          offCtx.fillStyle = 'rgba(16, 185, 129, 0.35)'
          offCtx.fillRect(sx, sy + 1, 4, 4)
        }
      }
    }
    coverageCacheValid = true
  }

  // 将缓存绘制到主 Canvas 上
  if (ctx && coverageCacheCanvas) {
    ctx.drawImage(coverageCacheCanvas, 0, 0)
  }
}

function drawPath() {
  const points = currentPath.value
  if (!Array.isArray(points) || points.length === 0) return
  const idx = pathIndex.value
  for (let i = 0; i < points.length; i++) {
    const p = points[i]
    if (!p || typeof p.x !== 'number' || typeof p.y !== 'number') continue
    const [sx, sy] = worldToScreen(p.x, p.y)
    ctx.fillStyle = i < idx ? '#10b981' : (i === idx ? '#f59e0b' : '#94a3b8')
    ctx.beginPath()
    ctx.arc(sx, sy, 4, 0, 2 * Math.PI)
    ctx.fill()
    if (i > 0) {
      const prev = points[i-1]
      if (!prev) continue
      const [px, py] = worldToScreen(prev.x, prev.y)
      ctx.beginPath()
      ctx.moveTo(px, py)
      ctx.lineTo(sx, sy)
      ctx.strokeStyle = '#cbd5e1'
      ctx.lineWidth = 2
      ctx.stroke()
    }
  }
}

function drawLaserPoints() {
  const laser = laserData.value
  if (!laser || !Array.isArray(laser) || laser.length === 0) return
  const p = pose.value
  if (typeof p.x !== 'number' || typeof p.y !== 'number') return
  ctx.save()
  ctx.fillStyle = '#ff4d4f'
  const angleStep = (Math.PI * 2) / laser.length
  for (let i = 0; i < laser.length; i++) {
    const dist = laser[i]
    if (dist > 5.0) continue
    const angle = i * angleStep
    const wx = p.x + dist * Math.cos(angle)
    const wy = p.y + dist * Math.sin(angle)
    const [sx, sy] = worldToScreen(wx, wy)
    ctx.beginPath()
    ctx.arc(sx, sy, 2, 0, 2 * Math.PI)
    ctx.fill()
  }
  ctx.restore()
}

function drawRobot() {
  const p = pose.value
  if (!p || typeof p.x !== 'number' || typeof p.y !== 'number') return
  const [cx, cy] = worldToScreen(p.x, p.y)
  const size = 16
  const angle = p.theta
  const tipX = cx + size * Math.cos(angle)
  const tipY = cy - size * Math.sin(angle)
  const leftX = cx + size * Math.cos(angle + 2.2)
  const leftY = cy - size * Math.sin(angle + 2.2)
  const rightX = cx + size * Math.cos(angle - 2.2)
  const rightY = cy - size * Math.sin(angle - 2.2)
  ctx.save()
  ctx.fillStyle = '#1989fa'
  ctx.shadowBlur = 10
  ctx.shadowColor = '#1989fa'
  ctx.beginPath()
  ctx.moveTo(tipX, tipY)
  ctx.lineTo(leftX, leftY)
  ctx.lineTo(rightX, rightY)
  ctx.fill()
  ctx.restore()
}

function draw() {
  try {
    if (!canvasRef.value || !ctx) return
    ctx.clearRect(0, 0, canvasRef.value.width, canvasRef.value.height)
    drawGrid()
    drawRooms()
    drawObstacles()
    drawCoverage()
    drawPath()
    drawLaserPoints()
    drawRobot()
  } catch (e) {
    console.error('Draw error:', e)
  }
  animationId = requestAnimationFrame(draw)
}

// 射线法判断点是否在多边形内
function isPointInPolygon(px, py, vertices) {
  let inside = false
  for (let i = 0, j = vertices.length - 1; i < vertices.length; j = i++) {
    const xi = vertices[i][0], yi = vertices[i][1]
    const xj = vertices[j][0], yj = vertices[j][1]
    const intersect = ((yi > py) != (yj > py)) &&
      (px < (xj - xi) * (py - yi) / (yj - yi) + xi)
    if (intersect) inside = !inside
  }
  return inside
}

// 鼠标移动时更新高亮房间
function onCanvasMousemove(e) {
  const canvas = canvasRef.value
  if (!canvas) return
  const rect = canvas.getBoundingClientRect()
  const scaleX = canvas.width / rect.width
  const scaleY = canvas.height / rect.height
  const mouseX = (e.clientX - rect.left) * scaleX
  const mouseY = (e.clientY - rect.top) * scaleY
  const worldX = (mouseX - canvas.width / 2) / 20
  const worldY = (canvas.height / 2 - mouseY) / 20
  mouseWorldX = worldX
  mouseWorldY = worldY
  let hoverRoom = null
  for (const [name, room] of Object.entries(props.rooms)) {
    const polygon = room.polygon
    if (polygon && isPointInPolygon(worldX, worldY, polygon)) {
      hoverRoom = name
      break
    }
  }
  highlightedRoom.value = hoverRoom
}

// 鼠标离开画布时清除高亮
function toggleEditMode() {
    if (!obstacleEditMode.value && (mission.value.state === 'running' || mission.value.state === 'working')) {
      ElMessage.warning('机器人工作中，无法进入编辑模式')
      return
    }
    obstacleEditMode.value = !obstacleEditMode.value
  }

  function onCanvasMouseleave() {
  highlightedRoom.value = null
}

// 点击房间发送任务
function onCanvasClick(e) {
  const canvas = canvasRef.value
  if (!canvas) return
  const rect = canvas.getBoundingClientRect()
  const scaleX = canvas.width / rect.width
  const scaleY = canvas.height / rect.height
  const mouseX = (e.clientX - rect.left) * scaleX
  const mouseY = (e.clientY - rect.top) * scaleY
  const worldX = (mouseX - canvas.width / 2) / 20
  const worldY = (canvas.height / 2 - mouseY) / 20
  mouseWorldX = worldX
  mouseWorldY = worldY
  // Edit mode: add/remove obstacle
  if (obstacleEditMode.value) {
    const nearObs = obstacles.value.some(function(o) {
      var cx = o.center?.[0] ?? o.center?.x ?? 0
      var cy = o.center?.[1] ?? o.center?.y ?? 0
      return Math.hypot(worldX - cx, worldY - cy) < 0.5
    })
    if (nearObs) {
      fetch('/api/robot/obstacles', { method: 'DELETE',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({positions: [[worldX, worldY]]}) })
    } else {
      fetch('/api/robot/obstacles', { method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({positions: [[worldX, worldY]], radius: 0.3}) })
    }
    return
  }

  // State checks
  if (robot.value.powerState === "OFF" || !wsConnected.value) {
    ElMessage.warning("机器人已关机，请先开机")
    return
  }
  // terminal states (failed/stopped/success) 视为已结束，允许发送新任务
  if (!['idle', 'failed', 'stopped', 'success'].includes(missionStore.current.state)) {
    ElMessage.warning('机器人当前状态: ' + missionStore.current.state + '，请先停止当前任务')
    return
  }

  let clickedRoom = null
  for (const [name, room] of Object.entries(props.rooms)) {
    const polygon = room.polygon
    if (polygon && isPointInPolygon(worldX, worldY, polygon)) {
      clickedRoom = name
      break
    }
  }
  if (clickedRoom) {
    const displayName = roomNameMap[clickedRoom] || clickedRoom
    robotStore.sendTask(`清扫${displayName}`)
    ElMessage.success(`已发送清扫${displayName}任务`)
  }
}

watch(() => props.rooms, () => {}, { deep: true })

// 覆盖栅格变化时失效缓存（下次绘制时重建离屏 Canvas）
watch(coverageGrid, () => {
  coverageCacheValid = false
}, { deep: true })

// showCoverage 开关变化时也失效缓存
watch(() => props.showCoverage, () => {
  coverageCacheValid = false
})

onMounted(() => {
  if (canvasRef.value) ctx = canvasRef.value.getContext('2d')
  draw()
  canvasRef.value.addEventListener('click', onCanvasClick)
  canvasRef.value.addEventListener('mousemove', onCanvasMousemove)
  canvasRef.value.addEventListener('mouseleave', onCanvasMouseleave)
})

onUnmounted(() => {
  if (animationId) cancelAnimationFrame(animationId)
  if (canvasRef.value) {
    canvasRef.value.removeEventListener('click', onCanvasClick)
    canvasRef.value.removeEventListener('mousemove', onCanvasMousemove)
    canvasRef.value.removeEventListener('mouseleave', onCanvasMouseleave)
  }
})
</script>

<style scoped>
.map-container {
  background: #ffffff;
  border-radius: 12px;
  padding: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}
.map-canvas {
  width: 100%;
  height: auto;
  background-color: #fafafa;
  border-radius: 8px;
}
.map-canvas.editing { cursor: crosshair; }
.map-container { position: relative; }
.obstacle-toggle-btn {
  position: absolute !important;
  top: 8px;
  right: 8px;
  z-index: 10;
}
.edit-hint {
  position: absolute;
  bottom: 8px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(0,0,0,0.7);
  color: white;
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 12px;
  z-index: 10;
  white-space: nowrap;
}
</style>
