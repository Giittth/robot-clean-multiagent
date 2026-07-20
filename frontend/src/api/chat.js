import request from '@/utils/request';
import { fetchSSE } from '@/utils/sse';

export function sendMessage(userId, kbId, message) {
  return request.post('/chat', { user_id: userId, kb_id: kbId, message });
}

export function sendMessageStream(userId, kbId, message, onChunk, onDone, onError, model) {
    const base = import.meta.env.VITE_API_BASE_URL || "";
  const url = `${base}/api/chat/?stream=true`;
  const body = { user_id: userId, kb_id: kbId, message, model };
  fetchSSE(url, body, onChunk, onDone, onError);
}

export function getChatHistory(userId, kbId, limit = 15) {
  return request.get(`/chat/history/${userId}/${kbId}`, { params: { limit } });
}

export function clearChatHistory(userId, kbId) {
  return request.delete(`/chat/clear/${userId}/${kbId}`);
}
