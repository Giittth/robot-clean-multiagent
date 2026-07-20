<template>
  <div class="chat-container">
    <div class="message-list" ref="messageListRef">
      <MessageBubble
        v-for="(msg, idx) in chatStore.messages"
        :key="idx"
        :role="msg.role"
        :content="msg.content"
      />
      <div v-if="sending" class="message assistant typing-message">
        <div class="avatar"><el-icon><Cpu /></el-icon></div>
        <div class="content">
          <div class="role">AI</div>
          <div class="text typing">思考中</div>
        </div>
      </div>
    </div>

    <div class="input-area">
    <div class="model-bar">
      <span class="model-bar-label">模型</span>
      <div class="model-trigger" @click="keyDialogVisible = true">
        <span class="model-trigger-text">{{ modelStore.currentModelInfo?.label || '选择模型' }}</span>
        <el-icon class="model-trigger-icon"><ArrowDown /></el-icon>
      </div>
    </div>
      <el-input
        v-model="inputText"
        type="textarea"
        :rows="2"
        placeholder="输入消息，按 Ctrl+Enter 发送"
        @keydown.ctrl.enter="send"
        class="chat-input"
      />
      <el-button type="primary" :loading="sending" @click="send" class="send-btn">发送</el-button>
    </div>
    <ApiKeyDialog v-model="keyDialogVisible" @saved="modelStore.fetchModels()" />
  </div>
</template>

<script setup>
import { ref, nextTick, watch, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Cpu, ArrowDown } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { useKnowledgeStore } from '@/stores/knowledge'
import { useChatStore } from '@/stores/chat'
import { useModelStore } from '@/stores/models'

import { useChat } from '@/composables/useChat'
import MessageBubble from '@/components/chat/MessageBubble.vue'
import ApiKeyDialog from '@/components/chat/ApiKeyDialog.vue'

const userStore = useUserStore()
const knowledgeStore = useKnowledgeStore()
const chatStore = useChatStore()
const modelStore = useModelStore()
const { sending, sendMessage, loadHistory, onKnowledgeChange } = useChat()

const inputText = ref('')
const messageListRef = ref(null)
const keyDialogVisible = ref(false)

const send = () => {
  if (!inputText.value.trim()) return
  if (!knowledgeStore.current_kb_id) {
    ElMessage.warning('请先在左侧选择知识库')
    return
  }
  sendMessage(inputText.value)
  inputText.value = ''
  scrollToBottom()
}

const scrollToBottom = () => {
  nextTick(() => {
    if (messageListRef.value) {
      messageListRef.value.scrollTop = messageListRef.value.scrollHeight
    }
  })
}

watch(() => chatStore.messages.length, () => scrollToBottom())
watch(sending, () => scrollToBottom())

const onKbChangeHandler = () => {
  onKnowledgeChange()
  scrollToBottom()
}

onMounted(async () => {
  if (userStore.user_id && userStore.user_id !== 0) {
    await loadHistory()
  }
  await modelStore.fetchModels()
  scrollToBottom()
  window.addEventListener('kb-change', onKbChangeHandler)
})

onUnmounted(() => {
  window.removeEventListener('kb-change', onKbChangeHandler)
})
</script>

<style scoped>
.chat-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  background-color: #f8f9fc;
}
.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 24px 20px;
  background: #f8f9fc;
  scroll-behavior: smooth;
}
/* 自定义滚动条 */
.message-list::-webkit-scrollbar {
  width: 6px;
}
.message-list::-webkit-scrollbar-track {
  background: #e9ecef;
  border-radius: 3px;
}
.message-list::-webkit-scrollbar-thumb {
  background: #cbd5e0;
  border-radius: 3px;
}
.message-list::-webkit-scrollbar-thumb:hover {
  background: #9aa9b7;
}
.model-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 2px 10px 2px;
  position: relative;
}
.model-bar-label {
  font-size: 12px;
  color: #6b7a8f;
  font-weight: 500;
  white-space: nowrap;
}
.model-trigger {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 12px;
  background: #eef2f6;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  cursor: pointer;
  transition: all 0.2s;
  user-select: none;
  max-width: 380px;
}
.model-trigger:hover {
  background: #e2e8f0;
  border-color: #cbd5e0;
}
.model-trigger-text {
  font-size: 12px;
  color: #2c3e50;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.model-trigger-icon {
  font-size: 12px;
  color: #94a3b8;
  flex-shrink: 0;
}
.input-area {
  padding: 16px 24px;
  background: white;
  border-top: 1px solid #e9ecef;
  display: flex;
  gap: 12px;
  align-items: flex-end;
  box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.02);
}
.chat-input :deep(.el-textarea__inner) {
  border-radius: 20px;
  border-color: #e2e8f0;
  transition: all 0.2s;
  font-size: 14px;
  resize: none;
}
.chat-input :deep(.el-textarea__inner):focus {
  border-color: #409eff;
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.1);
}
.send-btn {
  border-radius: 24px;
  padding: 12px 24px;
  background: linear-gradient(135deg, #409eff, #36a1ff);
  border: none;
  font-weight: 500;
  transition: transform 0.1s;
}
.send-btn:active {
  transform: scale(0.96);
}
/* 消息气泡额外样式（MessageBubble 已有基本样式，这里覆盖一些细节） */
.message {
  margin-bottom: 20px;
}
.message .avatar {
  width: 44px;
  height: 44px;
  background: #eef2f6;
  box-shadow: 0 2px 6px rgba(0,0,0,0.05);
}
.message.user .avatar {
  background: #e6f7ff;
}
.message.user .content {
  background-color: #ecf5fe;
  color: #2c3e50;
}
.message.assistant .content {
  background-color: white;
  border: 1px solid #eef2f6;
}
.content {
  border-radius: 18px;
  padding: 12px 18px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
  transition: all 0.2s;
}
.role {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.3px;
  margin-bottom: 6px;
  color: #5a6d86;
}
.text {
  line-height: 1.5;
  font-size: 14px;
}
/* “思考中”动画增强 */
.typing {
  display: inline-block;
}
.typing::after {
  content: '...';
  display: inline-block;
  width: 1.2em;
  text-align: left;
  animation: dots 1.2s steps(4, end) infinite;
}
@keyframes dots {
  0%, 20% { content: ''; }
  40% { content: '.'; }
  60% { content: '..'; }
  80%, 100% { content: '...'; }
}
/* 折叠思考中消息与普通消息保持一致 */
.typing-message .content {
  background-color: #f0f2f5;
}
</style>
