<template>
  <div class="knowledge-selector">
    <div class="label">当前知识库</div>
    <el-select
      :model-value="modelValue"
      :loading="loading"
      placeholder="选择知识库"
      @update:model-value="handleChange"
      clearable
    >
      <el-option
        v-for="kb in list"
        :key="kb.id"
        :label="kb.name"
        :value="kb.id"
      />
    </el-select>
  </div>
</template>

<script setup>
const props = defineProps({
  modelValue: { type: Number, default: null },
  list: { type: Array, required: true },
  loading: { type: Boolean, default: false }
})
const emit = defineEmits(['update:modelValue', 'change'])

const handleChange = (val) => {
  emit('update:modelValue', val)
  emit('change', val)
}
</script>

<style scoped>
.knowledge-selector {
  padding: 20px;
  border-top: 1px solid #e4e7ed;
}
.knowledge-selector .label {
  font-size: 14px;
  color: #606266;
  margin-bottom: 8px;
}
</style>