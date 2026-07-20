import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useKnowledgeStore = defineStore('knowledge', () => {
  const current_kb_id = ref(null)   // 当前选中的知识库ID
  const kb_list = ref([])            // 用户的所有知识库列表

  function setCurrentKbId(kbId) {
    current_kb_id.value = kbId
    // 可选持久化
    localStorage.setItem('current_kb_id', kbId)
  }

  function setKbList(list) {
    kb_list.value = list
  }

  function initFromStorage() {
    const stored = localStorage.getItem('current_kb_id')
    if (stored) {
      current_kb_id.value = parseInt(stored)
    }
  }

  return {
    current_kb_id,
    kb_list,
    setCurrentKbId,
    setKbList,
    initFromStorage
  }
})