import request from '@/utils/request'


// 知识库操作
/**
 * 获取公共知识库
 * @returns {Promise}
 */
export function getPublicKnowledgeBase() {
  return request.get('/knowledge/public')
}

/**
 * 获取用户的所有知识库列表
 * @param {number} userId
 * @returns {Promise<Array>}
 */
export function listUserKnowledgeBases(userId) {
  return request.get('/knowledge/list', { params: { user_id: userId } })
}

/**
 * 创建知识库
 * @param {number} userId
 * @param {string} name
 * @param {string} description
 * @returns {Promise}
 */
export function createKnowledgeBase(userId, name, description) {
  return request.post('/knowledge/create', null, { params: { user_id: userId, name, description } })
}

/**
 * 获取知识库详情
 * @param {number} kbId
 * @param {number} userId
 * @returns {Promise}
 */
export function getKnowledgeBaseDetail(kbId, userId) {
  return request.get(`/knowledge/${kbId}`, { params: { user_id: userId } })
}

/**
 * 更新知识库
 * @param {number} kbId
 * @param {number} userId
 * @param {string} name
 * @param {string} description
 * @returns {Promise}
 */
export function updateKnowledgeBase(kbId, userId, name, description) {
  return request.put(`/knowledge/${kbId}`, null, { params: { user_id: userId, name, description } })
}

/**
 * 删除知识库
 * @param {number} kbId
 * @param {number} userId
 * @returns {Promise}
 */
export function deleteKnowledgeBase(kbId, userId) {
  return request.delete(`/knowledge/${kbId}`, { params: { user_id: userId } })
}

// 文档操作

/**
 * 创建文档（上传）
 * @param {number} kbId
 * @param {number} userId
 * @param {string} title
 * @param {string} content
 * @param {object|null} meta
 * @returns {Promise}
 */
export function createDocument(kbId, userId, title, content, meta = null) {
  return request.post('/knowledge/doc/create', { kb_id: kbId, title, content, meta }, { params: { user_id: userId } })
}

/**
 * 获取知识库下的所有文档列表
 * @param {number} kbId
 * @param {number} userId
 * @returns {Promise<Array>}
 */
export async function listDocuments(kbId, userId) {
  const baseUrl = import.meta.env.VITE_API_BASE_URL
  const url = `${baseUrl}/knowledge/${kbId}/docs?user_id=${userId}`
  try {
    const response = await fetch(url)
    if (!response.ok) {
      console.error(`获取文档列表失败: ${response.status}`)
      return []
    }
    const data = await response.json()
    return data
  } catch (err) {
    console.error('获取文档列表网络错误', err)
    return []
  }
}

/**
 * 获取文档详情
 * @param {number} docId
 * @param {number} userId
 * @returns {Promise}
 */
export function getDocumentDetail(docId, userId) {
  return request.get(`/knowledge/doc/${docId}`, { params: { user_id: userId } })
}

/**
 * 更新文档
 * @param {number} docId
 * @param {number} userId
 * @param {string} title
 * @param {string} content
 * @param {object|null} meta
 * @returns {Promise}
 */
export function updateDocument(docId, userId, title, content, meta = null) {
  return request.put(`/knowledge/doc/${docId}`, { title, content, meta }, { params: { user_id: userId } })
}

/**
 * 删除文档
 * @param {number} docId
 * @param {number} userId
 * @returns {Promise}
 */
export function deleteDocument(docId, userId) {
  return request.delete(`/knowledge/doc/${docId}`, { params: { user_id: userId } })
}

//统计
/**
 * 获取知识库文档总数
 * @param {number} kbId
 * @param {number} userId
 * @returns {Promise<{total: number}>}
 */
export function countDocuments(kbId, userId) {
  return request.get(`/knowledge/${kbId}/count`, { params: { user_id: userId } })
}