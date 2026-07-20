import request from '@/utils/request'

export function sendTask(text) {
  return request.post('/robot/task', { text })
}

export function getTaskHistory(userId = 0, limit = 30) {
  return request.get('/robot/tasks/recent', { params: { user_id: userId, limit } })
}

// ── Mission History ──
export function getMissions(userId = 0, limit = 30) {
  return request.get('/robot/missions', { params: { user_id: userId, limit } })
}

export function getMissionDetail(missionId) {
  return request.get(`/robot/missions/${missionId}`)
}

export function getMissionReplay(missionId) {
  return request.get(`/robot/missions/${missionId}/replay`)
}

// ── Delete / Clear ──
export function deleteTaskHistory(taskId) {
  return request.delete('/robot/tasks/' + taskId)
}

export function deleteMission(missionId) {
  return request.delete('/robot/missions/' + missionId)
}

export function getChatForTask(command) {
  return request.get('/robot/chat-for-task', { params: { command } })
}

export function clearAllHistory(userId = 0) {
  return request.delete('/robot/history', { params: { user_id: userId } })
}
