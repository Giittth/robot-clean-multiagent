<template>
  <div class="task-graph-panel">
    <div v-if="!graphStructure || !graphStructure.tasks || !graphStructure.tasks.length" class="empty-state">
      <el-empty description="暂无任务图数据" :image-size="80" />
    </div>
    <div v-else class="graph-container">
      <svg :width="svgWidth" :height="svgHeight" :viewBox="'0 0' + svgWidth + ' ' + svgHeight" class="graph-svg">
        <defs>
          <marker id="arrowhead" viewBox="0 0 10 10" refX="28" refY="5" markerWidth="8" markerHeight="8" orient="auto">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#94a3b8" />
          </marker>
        </defs>
        <g class="edges">
          <path v-for="(e, i) in edgeLines" :key="'edge-' + i" :d="e.path" :stroke="e.color" stroke-width="2" fill="none" stroke-linejoin="round" marker-end="url(#arrowhead)" />
        </g>
        <g class="nodes">
          <g v-for="node in nodes" :key="node.id" :transform="'translate(' + node.x + ', ' + node.y + ')'" class="task-node">
            <rect :width="nodeWidth" :height="nodeHeight" rx="8" ry="8" :fill="node.bg" :stroke="node.border" stroke-width="2" />
            <text :x="nodeWidth / 2" :y="nodeHeight / 2" text-anchor="middle" dominant-baseline="central" :fill="node.text" font-size="13" font-weight="600">{{ node.label }}</text>
            <text :x="nodeWidth / 2" :y="nodeHeight + 14" text-anchor="middle" fill="#6b7280" font-size="11">{{ node.statusText }}</text>
          </g>
        </g>
      </svg>
    </div>
    <div v-if="graphStructure" class="graph-legend">
      <span class="legend-item"><span class="dot dot-blue"></span>执行中</span>
      <span class="legend-item"><span class="dot dot-green"></span>已完成</span>
      <span class="legend-item"><span class="dot dot-red"></span>失败</span>
      <span class="legend-item"><span class="dot dot-gray"></span>等待中</span>
      <span class="legend-item"><span class="dot dot-amber"></span>已跳过</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue"
import { storeToRefs } from "pinia"
import { useMissionStore } from "@/stores/robot/missionStore"

const missionStore = useMissionStore()
const { graphStructure, taskStatusMap } = storeToRefs(missionStore)

const nodeWidth = 140
const nodeHeight = 44
const hGap = 32
const vGap = 28
const paddingX = 20
const paddingY = 24

const statusColors = {
  pending:   { bg: "#f3f4f6", border: "#d1d5db", text: "#6b7280", label: "等待中" },
  ready:     { bg: "#eff6ff", border: "#93c5fd", text: "#2563eb", label: "就绪" },
  dispatched:{ bg: "#eef2ff", border: "#a5b4fc", text: "#4338ca", label: "已调度" },
  running:   { bg: "#eff6ff", border: "#3b82f6", text: "#1e40af", label: "执行中" },
  success:   { bg: "#f0fdf4", border: "#22c55e", text: "#166534", label: "成功" },
  skipped:   { bg: "#fffbeb", border: "#f59e0b", text: "#92400e", label: "跳过" },
  failed:    { bg: "#fef2f2", border: "#ef4444", text: "#991b1b", label: "失败" },
  stopped:   { bg: "#f5f5f4", border: "#a8a29e", text: "#44403c", label: "已停止" },
}
const defaultColor = { bg: "#f9fafb", border: "#e5e7eb", text: "#4b5563", label: "未知" }

const layout = computed(() => {
  const gs = graphStructure.value
  if (!gs || !gs.tasks || !gs.tasks.length) return { nodes: [], edges: [], width: 400, height: 100 }

  const tasks = gs.tasks
  const edges = gs.edges || []
  const statusMap = taskStatusMap.value || {}

  const inDeg = {}
  const adj = {}
  const allIds = new Set()
  tasks.forEach(t => { allIds.add(t.id); inDeg[t.id] = 0; adj[t.id] = [] })
  edges.forEach(e => {
    if (allIds.has(e.source) && allIds.has(e.target)) {
      adj[e.source].push(e.target)
      inDeg[e.target] = (inDeg[e.target] || 0) + 1
    }
  })

  let queue = []
  const layer = {}
  allIds.forEach(id => {
    if (inDeg[id] === 0) { queue.push(id); layer[id] = 0 }
  })
  let visited = new Set(queue)
  while (queue.length) {
    const next = []
    for (const id of queue) {
      for (const tgt of adj[id]) {
        if (!visited.has(tgt)) {
          visited.add(tgt); layer[tgt] = (layer[id] || 0) + 1; next.push(tgt)
        }
      }
    }
    queue = next
  }
  allIds.forEach(id => { if (layer[id] === undefined) layer[id] = 0 })

  const layers = {}
  allIds.forEach(id => {
    const l = layer[id]
    if (!layers[l]) layers[l] = []
    layers[l].push(id)
  })
  const sortedLayers = Object.keys(layers).sort((a, b) => a - b)

  const nodePos = {}
  sortedLayers.forEach(l => {
    const ids = layers[l]
    const count = ids.length
    ids.forEach((id, i) => {
      nodePos[id] = {
        x: paddingX + i * (nodeWidth + hGap),
        y: paddingY + parseInt(l) * (nodeHeight + vGap)
      }
    })
  })

  let maxX = 0, maxY = 0
  allIds.forEach(id => {
    const p = nodePos[id]
    if (p.x + nodeWidth > maxX) maxX = p.x + nodeWidth
    if (p.y + nodeHeight > maxY) maxY = p.y + nodeHeight
  })
  const containerW = maxX + paddingX

  const resultNodes = []
  allIds.forEach(id => {
    const task = tasks.find(t => t.id === id)
    const status = statusMap[id] || "pending"
    const colors = statusColors[status] || defaultColor
    const label = (task && task.name) ? task.name.slice(0, 16) : id.slice(0, 8)
    resultNodes.push({
      id, label, x: nodePos[id].x, y: nodePos[id].y,
      ...colors, statusText: colors.label,
    })
  })

  const resultEdges = edges.map(e => {
    const src = nodePos[e.source]; const tgt = nodePos[e.target]
    if (!src || !tgt) return null
    const x1 = src.x + nodeWidth / 2; const y1 = src.y + nodeHeight
    const x2 = tgt.x + nodeWidth / 2; const y2 = tgt.y
    const cy = (y1 + y2) / 2
    return { path: "M " + x1 + " " + y1 + " C " + x1 + " " + cy + ", " + x2 + " " + cy + ", " + x2 + " " + y2, color: "#94a3b8" }
  }).filter(Boolean)

  return { nodes: resultNodes, edges: resultEdges, width: containerW, height: maxY + paddingY }
})

const nodes = computed(() => layout.value.nodes || [])
const edgeLines = computed(() => layout.value.edges || [])
const svgWidth = computed(() => Math.max(layout.value.width || 400, 400))
const svgHeight = computed(() => Math.max(layout.value.height || 100, 100))
</script>

<style scoped>
.task-graph-panel { width: 100%; overflow: visible; }
.empty-state { padding: 24px 0; display: flex; justify-content: center; }
.graph-container { overflow-x: auto; padding: 8px 0; width: 100%; }
.graph-svg { display: block; margin: 0 auto; }
.task-node { cursor: default; transition: opacity 0.2s; }
.task-node:hover { opacity: 0.85; }
.graph-legend { display: flex; justify-content: center; gap: 16px; padding: 8px 0 4px; flex-wrap: wrap; }
.legend-item { display: inline-flex; align-items: center; gap: 4px; font-size: 12px; color: #6b7280; }
.dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; }
.dot-blue { background: #3b82f6; }
.dot-green { background: #22c55e; }
.dot-red { background: #ef4444; }
.dot-gray { background: #9ca3af; }
.dot-amber { background: #f59e0b; }
</style>

