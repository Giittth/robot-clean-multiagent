import request from '@/utils/request'

/**
 * 用户注册
 * @param {string} username
 * @param {string} password
 * @returns {Promise} 用户信息
 */
export function register(username, password) {
  return request.post('/users/register', { username, password })
}

/**
 * 用户登录
 * @param {string} username
 * @param {string} password
 * @returns {Promise<{msg: string, user_id: number}>}
 */
export function login(username, password) {
  return request.post('/users/login', { username, password })
}