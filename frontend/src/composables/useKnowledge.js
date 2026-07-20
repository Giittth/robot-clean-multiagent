import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { useKnowledgeStore } from '@/stores/knowledge'
import {
  listUserKnowledgeBases,
  createKnowledgeBase,
  updateKnowledgeBase,
  deleteKnowledgeBase,
  getKnowledgeBaseDetail,
  listDocuments,
  createDocument,
  updateDocument,
  deleteDocument,
  countDocuments
} from '@/api/knowledge'


export function useKnowledge() {
  const userStore = useUserStore()
  const knowledgeStore = useKnowledgeStore()

  const loading = ref(false)
  const docLoading = ref(false)

  // 知识库
  const fetchKnowledgeBases = async () => {
    const userId = userStore.user_id
    if (!userId || userId === 0) return []
    loading.value = true
    try {
      const list = await listUserKnowledgeBases(userId)
      knowledgeStore.setKbList(list)
      // 如果当前没有选中知识库且有列表，默认选中第一个
      if (!knowledgeStore.current_kb_id && list.length > 0) {
        knowledgeStore.setCurrentKbId(list[0].id)
      }
      return list
    } catch (err) {
      ElMessage.error('获取知识库列表失败')
      return []
    } finally {
      loading.value = false
    }
  }

  const createKb = async (name, description) => {
    const userId = userStore.user_id
    if (!userId) {
      ElMessage.warning('请先登录')
      return false
    }
    loading.value = true
    try {
      await createKnowledgeBase(userId, name, description)
      ElMessage.success('创建成功')
      await fetchKnowledgeBases() // 刷新列表
      return true
    } catch (err) {
      ElMessage.error(err.response?.data?.detail || '创建失败')
      return false
    } finally {
      loading.value = false
    }
  }

  const updateKb = async (kbId, name, description) => {
    const userId = userStore.user_id
    if (!userId) return false
    loading.value = true
    try {
      await updateKnowledgeBase(kbId, userId, name, description)
      ElMessage.success('更新成功')
      await fetchKnowledgeBases()
      return true
    } catch (err) {
      ElMessage.error('更新失败')
      return false
    } finally {
      loading.value = false
    }
  }

  const deleteKb = async (kbId) => {
    const userId = userStore.user_id
    if (!userId) return false
    loading.value = true
    try {
      await deleteKnowledgeBase(kbId, userId)
      ElMessage.success('删除成功')
      await fetchKnowledgeBases()
      // 如果删除的是当前选中的知识库，选中另一个
      if (knowledgeStore.current_kb_id === kbId) {
        const newKb = knowledgeStore.kb_list[0]?.id || null
        knowledgeStore.setCurrentKbId(newKb)
      }
      return true
    } catch (err) {
      ElMessage.error('删除失败')
      return false
    } finally {
      loading.value = false
    }
  }

  // 文档
  const fetchDocuments = async (kbId) => {
  const userId = userStore.user_id
  if (!userId) return []
  try {
    const docs = await listDocuments(kbId, userId)
    return docs
  } catch (err) {
    console.error('获取文档列表失败', err)   // 只打印到控制台，不弹框
    return []
    } finally {
      docLoading.value = false
    }
  }

  const createDoc = async (kbId, title, content, meta = null) => {
    const userId = userStore.user_id
    if (!userId) return false
    docLoading.value = true
    try {
      await createDocument(kbId, userId, title, content, meta)
      ElMessage.success('文档上传成功')
      return true
    } catch (err) {
      ElMessage.error(err.response?.data?.detail || '上传失败')
      return false
    } finally {
      docLoading.value = false
    }
  }

  const updateDoc = async (docId, title, content, meta = null) => {
    const userId = userStore.user_id
    if (!userId) return false
    docLoading.value = true
    try {
      await updateDocument(docId, userId, title, content, meta)
      ElMessage.success('文档更新成功')
      return true
    } catch (err) {
      ElMessage.error('更新失败')
      return false
    } finally {
      docLoading.value = false
    }
  }

  const deleteDoc = async (docId) => {
    const userId = userStore.user_id
    if (!userId) return false
    docLoading.value = true
    try {
      await deleteDocument(docId, userId)
      ElMessage.success('文档删除成功')
      return true
    } catch (err) {
      ElMessage.error('删除失败')
      return false
    } finally {
      docLoading.value = false
    }
  }

  const getDocCount = async (kbId) => {
    const userId = userStore.user_id
    if (!userId) return 0
    try {
      const res = await countDocuments(kbId, userId)
      return res.total
    } catch {
      return 0
    }
  }

  return {
    loading,
    docLoading,
    fetchKnowledgeBases,
    createKb,
    updateKb,
    deleteKb,
    fetchDocuments,
    createDoc,
    updateDoc,
    deleteDoc,
    getDocCount
  }
}