import request from '@/utils/request'

/**
 * 发送控制指令
 * @param {string} command - 控制命令 (pause, resume, stop, emergency_stop, reset, recharge)
 * @returns {Promise}
 */
export function sendControl(command) {
  return request.post('/robot/control', { command })
}

/**
 * 重置机器人仿真环境
 * @returns {Promise}
 */
export function resetRobot() {
  return request.post('/robot/reset')
}

/**
 * 获取机器人状态 (HTTP 轮询用，WebSocket 已提供实时推送)
 * @returns {Promise}
 */
export function getRobotState() {
  return request.get('/robot/state')
}

/**
 * 获取世界模型数据
 * @returns {Promise}
 */
export function getWorldModel() {
  return request.get('/robot/world')
}

/**
 * 获取待用户确认的请求
 * @returns {Promise}
 */
export function getPendingConfirm() {
  return request.get('/robot/confirm/pending')
}

/**
 * 发送用户确认结果
 * @param {string} id - 确认请求 ID
 * @param {boolean} approved - 是否确认
 * @returns {Promise}
 */
export function sendConfirm(id, approved) {
  return request.post('/robot/confirm', { id, approved })
}