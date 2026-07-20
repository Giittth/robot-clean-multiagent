import request from '@/utils/request'

/** 获取定时任务列表 */
export function getSchedules(userId = 0) {
  return request.get('/schedules', { params: { user_id: userId } })
}

/** 创建定时任务 */
export function createSchedule({ command, cron_expression, description = '', user_id = 0 }) {
  return request.post('/schedules', { command, cron_expression, description, user_id })
}

/** 删除定时任务 */
export function deleteSchedule(id) {
  return request.delete(`/schedules/${id}`)
}

/** 启用/禁用定时任务 */
export function toggleSchedule(id, enabled) {
  return request.put(`/schedules/${id}/toggle`, { enabled })
}
