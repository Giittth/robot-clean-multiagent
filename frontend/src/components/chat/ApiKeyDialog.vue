<template>
  <el-dialog v-model="visible" title="API 密钥管理" width="540px" :close-on-click-modal="false">
    <div class="dialog-scroll-body">
    <div class="dialog-model-section">
      <div class="dialog-model-label">选择模型</div>
      <el-select
        v-model="selectedModel"
        placeholder="选择大模型"
        class="dialog-model-select"
        :teleported="false"
        popper-class="dialog-model-popper"
      >
        <el-option
          v-for="model in modelStore.modelList"
          :key="model.id"
          :label="model.label"
          :value="model.id"
        />
      </el-select>
    </div>
    <p class="dialog-desc">
      配置 API Key 后即可使用对应的大模型。所有密钥保存在本地服务器，不会泄露。
    </p>
    <el-form label-width="145px" label-position="left" size="small">
      <el-form-item
        v-for="item in providers"
        :key="item.env"
        :label="item.label"
      >
        <el-input
          v-model="form[item.env]"
          type="password"
          show-password
          :placeholder="item.status ? '已配置，输入新值覆盖' : '请输入 API Key'"
          clearable
        />
        <div class="provider-hint">{{ item.models }}</div>
      </el-form-item>
    </el-form>
    </div>
    <template #footer>
      <div class="dialog-footer">
        <el-button @click="visible = false" size="small">取消</el-button>
        <el-button type="primary" @click="handleSave" :loading="saving" size="small">保存</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from "vue"
import { ElMessage } from "element-plus"
import { getApiKeyStatus, saveApiKeys } from "@/api/apikeys"
import { useModelStore } from "@/stores/models"

const props = defineProps({ modelValue: Boolean })
const emit = defineEmits(["update:modelValue", "saved"])

const modelStore = useModelStore()
const visible = ref(false)
const saving = ref(false)
const form = ref({})
const keyStatus = ref({})
const selectedModel = ref(modelStore.currentModelId)

watch(() => props.modelValue, async (val) => {
  visible.value = val
  if (val) {
    selectedModel.value = modelStore.currentModelId
    await loadStatus()
  }
})

watch(visible, (val) => {
  if (!val) emit("update:modelValue", false)
})

const providers = [
  { env: "OPENAI_API_KEY",    label: "OpenAI",         models: "GPT-4.1 / 4o / o3-mini / o4-mini" },
  { env: "ANTHROPIC_API_KEY", label: "Anthropic",      models: "Claude Sonnet 4 / 3.5 Sonnet / 3 Opus" },
  { env: "GEMINI_API_KEY",    label: "Google Gemini",  models: "Gemini 2.5 Pro / 2.5 Flash / 2.0 Flash" },
  { env: "DEEPSEEK_API_KEY",  label: "DeepSeek",       models: "DeepSeek V3 / R1" },
  { env: "GLM_API_KEY",       label: "智谱 GLM",       models: "GLM-4-Flash / Plus / Air" },
  { env: "QWEN_API_KEY",      label: "阿里通义千问",    models: "Qwen Turbo / Max / Max+" },
  { env: "ARK_API_KEY",       label: "字节跳动豆包",    models: "豆包 Lite / Pro" },
  { env: "BAIDU_API_KEY",     label: "百度文心",        models: "ERNIE Speed / 4.5" },
  { env: "HUNYUAN_API_KEY",   label: "腾讯混元",        models: "混元 Lite / Pro" },
  { env: "MOONSHOT_API_KEY",  label: "月之暗面",        models: "Moonshot v1" },
  { env: "YI_API_KEY",        label: "零一万物",        models: "Yi-Lightning" },
  { env: "MINIMAX_API_KEY",   label: "MiniMax",        models: "MiniMax-Text-01" },
  { env: "BAICHUAN_API_KEY",  label: "百川智能",        models: "Baichuan 4" },
  { env: "MISTRAL_API_KEY",   label: "Mistral AI",     models: "Mistral Large" },
  { env: "XAI_API_KEY",       label: "xAI Grok",       models: "Grok 2" },
]

async function loadStatus() {
  try {
    const res = await getApiKeyStatus()
    keyStatus.value = res.status || {}
    const st = res.status || {}
    providers.forEach((p) => {
      p.status = !!st[p.env]
    })
    // reset form to empty (dont prefill existing values for security)
    form.value = {}
  } catch {
    ElMessage.error("加载密钥状态失败")
  }
}

async function handleSave() {
  const selectedModelObj = modelStore.modelList.find(m => m.id === selectedModel.value)
  const isLocal = selectedModelObj?.category === 'local'

  const keys = {}
  for (const [k, v] of Object.entries(form.value)) {
    if (v && v.trim()) keys[k] = v.trim()
  }
  if (Object.keys(keys).length === 0 && !isLocal) {
    ElMessage.warning("请至少输入一个 API Key，或选择本地模型")
    return
  }

  // 本地模型无需 API Key，直接切换
  if (Object.keys(keys).length === 0 && isLocal) {
    if (selectedModel.value && selectedModel.value !== modelStore.currentModelId) {
      modelStore.selectModel(selectedModel.value)
    }
    visible.value = false
    emit("saved")
    return
  }

  saving.value = true
  try {
    await saveApiKeys(keys)
    if (selectedModel.value && selectedModel.value !== modelStore.currentModelId) {
      modelStore.selectModel(selectedModel.value)
    }
    ElMessage.success("API Key 已保存")
    visible.value = false
    emit("saved")
  } catch {
    ElMessage.error("保存失败")
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.dialog-model-section {
  margin-bottom: 12px;
}
.dialog-model-label {
  font-size: 13px;
  font-weight: 500;
  color: #5a6d86;
  margin-bottom: 6px;
}
.dialog-model-select {
  width: 100%;
}
.dialog-model-select :deep(.el-select__wrapper) {
  border-radius: 8px;
}
.dialog-desc {
  font-size: 13px;
  color: #6b7a8f;
  margin-bottom: 16px;
  line-height: 1.5;
}
.provider-hint {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 2px;
}
.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
:deep(.el-form-item) {
  margin-bottom: 8px;
}
</style>

<style>
.dialog-model-popper {
  /* Element Plus 自带滚动条，无需额外设置 */
}
.dialog-scroll-body {
  max-height: 55vh;
  overflow-y: auto;
  padding-right: 6px;
}
.dialog-scroll-body::-webkit-scrollbar {
  width: 5px;
}
.dialog-scroll-body::-webkit-scrollbar-thumb {
  background: #cbd5e0;
  border-radius: 4px;
}
.dialog-scroll-body::-webkit-scrollbar-track {
  background: transparent;
}
</style>
