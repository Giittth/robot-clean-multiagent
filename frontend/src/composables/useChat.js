import { ref } from 'vue';
import { ElMessage } from 'element-plus';
import { useUserStore } from '@/stores/user';
import { useKnowledgeStore } from '@/stores/knowledge';
import { useChatStore } from '@/stores/chat';
import { useModelStore } from '@/stores/models';
import { sendMessageStream, getChatHistory, clearChatHistory } from '@/api/chat';

export function useChat() {
  const userStore = useUserStore();
  const knowledgeStore = useKnowledgeStore();
  const chatStore = useChatStore();
  const modelStore = useModelStore();

  const sending = ref(false);
  const currentAnswer = ref('');

  const sendMessage = async (messageText) => {
    let userId = userStore.user_id;
    let kbId = knowledgeStore.current_kb_id;
    let modelId = modelStore.currentModelId;

    if (userId === null || userId === undefined) {
      ElMessage.warning('请先登录');
      return;
    }
    if (!kbId) {
      kbId = 1;
      knowledgeStore.setCurrentKbId(1);
    }
    if (!messageText.trim()) return;

    chatStore.addMessage('user', messageText);
    chatStore.addMessage('assistant', '');
    sending.value = true;
    currentAnswer.value = '';

    const onChunk = (chunk) => {
      currentAnswer.value += chunk;
      chatStore.updateLastMessage(currentAnswer.value);
    };

    const onDone = () => {
      sending.value = false;
      currentAnswer.value = '';
    };

    const onError = (err) => {
      console.error(err);
      ElMessage.error('发送消息失败');
      if (chatStore.messages.length && chatStore.messages[chatStore.messages.length - 1].content === '') {
        chatStore.messages.pop();
      }
      sending.value = false;
    };

    sendMessageStream(userId, kbId, messageText, onChunk, onDone, onError, modelId);
  };

  const loadHistory = async (limit = 15) => {
    const userId = userStore.user_id;
    const kbId = knowledgeStore.current_kb_id;
    if (!userId || !kbId) return;
    try {
      const history = await getChatHistory(userId, kbId, limit);
      chatStore.setMessages(history);
    } catch (err) {
      ElMessage.error('加载历史失败');
    }
  };

  const clearHistory = async () => {
    const userId = userStore.user_id;
    const kbId = knowledgeStore.current_kb_id;
    if (!userId || !kbId) return;
    try {
      await clearChatHistory(userId, kbId);
      chatStore.clearMessages();
      ElMessage.success('历史已清空');
    } catch (err) {
      ElMessage.error('清空失败');
    }
  };

  const onKnowledgeChange = async () => {
    chatStore.clearMessages();
    await loadHistory();
  };

  return {
    sending,
    currentAnswer,
    sendMessage,
    loadHistory,
    clearHistory,
    onKnowledgeChange,
  };
}
