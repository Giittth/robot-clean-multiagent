import request from '@/utils/request';

export function getAvailableModels() {
  return request.get('/models/');
}
