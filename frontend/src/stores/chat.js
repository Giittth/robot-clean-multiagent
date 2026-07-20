import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useChatStore = defineStore('chat', () => {
  // 消息列表结构: { role: 'user' | 'assistant', content: string, timestamp?: Date }
  const messages = ref([])

  // 追加一条消息
  function addMessage(role, content, timestamp = new Date()) {
    messages.value.push({ role, content, timestamp })
  }

  // 更新最后一条消息的内容（用于流式追加）
  function updateLastMessage(content) {
    if (messages.value.length > 0 && messages.value[messages.value.length - 1].role === 'assistant') {
      messages.value[messages.value.length - 1].content = content
    } else {
      // 如果没有助手消息，则新建一条
      addMessage('assistant', content)
    }
  }

  // 清空当前对话（例如切换知识库时）
  function clearMessages() {
    messages.value = []
  }

  // 从后端历史记录初始化
  function setMessages(historyList) {
    // historyList 格式: [{ role, content, create_time }, ...]
    messages.value = historyList.map(item => ({
      role: item.role,
      content: item.content,
      timestamp: new Date(item.create_time)
    }))
  }

  return {
    messages,
    addMessage,
    updateLastMessage,
    clearMessages,
    setMessages
  }
})