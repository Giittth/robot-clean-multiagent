<template>
  <div :class="['message', role]">
    <div class="avatar">
      <el-icon v-if="role === 'user'"><User /></el-icon>
      <el-icon v-else><Cpu /></el-icon>
    </div>
    <div class="content">
      <div class="role">{{ role === 'user' ? '我' : 'AI' }}</div>
      <div class="text">{{ content }}</div>
    </div>
  </div>
</template>

<script setup>
import { User, Cpu } from '@element-plus/icons-vue'

defineProps({
  role: {
    type: String,
    required: true,
    validator: (val) => ['user', 'assistant'].includes(val)
  },
  content: {
    type: String,
    default: ''
  }
})
</script>

<style scoped>
.message {
  display: flex;
  margin-bottom: 20px;
}
.message.user {
  flex-direction: row-reverse;
}
.message.user .content {
  background-color: #95ec69;
  margin-right: 12px;
}
.message.assistant .content {
  background-color: white;
  margin-left: 12px;
}
.avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: #e4e7ed;
  display: flex;
  align-items: center;
  justify-content: center;
}
.content {
  max-width: 70%;
  padding: 10px 15px;
  border-radius: 10px;
  box-shadow: 0 1px 2px rgba(0,0,0,0.1);
}
.role {
  font-weight: bold;
  margin-bottom: 4px;
  font-size: 12px;
  color: #606266;
}
.text {
  word-wrap: break-word;
}
</style>