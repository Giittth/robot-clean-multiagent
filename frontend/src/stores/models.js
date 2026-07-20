import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getAvailableModels } from '@/api/models'

export const useModelStore = defineStore('models', () => {
  // 模型列表
  const modelList = ref([])
  // 当前选中的模型 ID（从 localStorage 恢复）
  const currentModelId = ref(localStorage.getItem('selectedModel') || 'default')
  // 默认模型 ID（来自后端）
  const defaultModelId = ref('default')

  // 按分类分组的模型
  const modelsByCategory = computed(() => {
    const groups = { local: [], free: [], paid: [] }
    for (const m of modelList.value) {
      if (groups[m.category]) {
        groups[m.category].push(m)
      }
    }
    return groups
  })

  // 当前选中模型的显示信息
  const currentModelInfo = computed(() => {
    return modelList.value.find(m => m.id === currentModelId.value)
  })

  // 从后端加载模型列表
  // 后端不可用时的回退列表（仅 4 个本地模型）
  const FALLBACK_MODELS = [
    { id: 'default',       label: 'Qwen3:8B (本地 Ollama)',      category: 'local', is_default: true,  available: true },
    { id: 'qwen2.5:7b',    label: 'Qwen2.5:7B (本地 Ollama)',   category: 'local', is_default: false, available: true },
    { id: 'llama3.1:8b',   label: 'Llama 3.1:8B (本地 Ollama)', category: 'local', is_default: false, available: true },
    { id: 'glm4:9b',       label: 'GLM-4:9B (本地 Ollama)',      category: 'local', is_default: false, available: true },
  ]

  async function fetchModels() {
    try {
      const res = await getAvailableModels()
      if (res.models && res.models.length > 0) {
        modelList.value = res.models
        defaultModelId.value = res.default_model_id || 'default'
      } else {
        modelList.value = [...FALLBACK_MODELS]
        defaultModelId.value = 'default'
      }
    } catch (err) {
      console.error('Backend not available, using fallback local models')
      modelList.value = [...FALLBACK_MODELS]
      defaultModelId.value = 'default'
    }
    // 验证当前选择有效
    const ids = modelList.value.map(m => m.id)
    if (!ids.includes(currentModelId.value)) {
      currentModelId.value = defaultModelId.value
    }
  }

  // 选择模型
  function selectModel(modelId) {
    currentModelId.value = modelId
    localStorage.setItem('selectedModel', modelId)
  }

  return {
    modelList,
    currentModelId,
    defaultModelId,
    modelsByCategory,
    currentModelInfo,
    fetchModels,
    selectModel,
  }
})
