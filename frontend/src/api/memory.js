import request from '@/utils/request'

/**
 * 获取用户的所有长期记忆
 * @param {number} userId
 * @returns {Promise<Array>} 记忆列表 [{id, text, timestamp, ...}]
 */
export function listMemories(userId) {
  return request.get(`/memory/${userId}`)
}

/**
 * 删除单条记忆
 * @param {number} userId
 * @param {string} memoryId
 * @returns {Promise}
 */
export function deleteMemory(userId, memoryId) {
  return request.delete(`/memory/${userId}/${memoryId}`)
}

/**
 * 清空用户所有长期记忆
 * @param {number} userId
 * @returns {Promise}
 */
export function clearAllMemories(userId) {
  return request.delete(`/memory/${userId}`)
}