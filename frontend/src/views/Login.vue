<template>
  <div class="login-container">
    <el-card class="login-card" shadow="hover">
      <div class="login-header">
        <el-icon class="logo-icon"><ChatDotRound /></el-icon>
        <h2>欢迎登录</h2>
        <p>扫拖机器人 智能助手</p>
      </div>

      <el-form :model="form" :rules="rules" ref="formRef" label-position="top" @submit.prevent>
        <el-form-item label="用户名" prop="username">
          <el-input
            v-model="form.username"
            placeholder="请输入用户名"
            prefix-icon="User"
            size="large"
          />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            type="password"
            v-model="form.password"
            placeholder="请输入密码"
            prefix-icon="Lock"
            size="large"
            show-password
            @keyup.enter="() => handleLogin(form.username, form.password)"
          />
        </el-form-item>
        <el-form-item>
          <div class="button-group">
            <el-button type="primary" :loading="loading" @click="() => handleLogin(form.username, form.password)" class="btn-login">登录</el-button>
            <el-button @click="goRegister" class="btn-register">注册</el-button>
          </div>
        </el-form-item>
        <el-form-item>
          <el-button text type="info" @click="goBack" class="back-btn">
            <el-icon><Back /></el-icon> 返回
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '@/composables/useAuth'
import { ChatDotRound, Back } from '@element-plus/icons-vue'

const router = useRouter()
const { loading, handleLogin } = useAuth()
const form = reactive({ username: '', password: '' })
const formRef = ref(null)
const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

const goRegister = () => router.push('/register')
const goBack = () => router.push('/chat') // 返回聊天主页（游客模式）
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  background: linear-gradient(135deg, #f5f7fa 0%, #e9edf2 100%);
}
.login-card {
  width: 420px;
  border-radius: 16px;
  padding: 20px 30px 30px;
}
.login-header {
  text-align: center;
  margin-bottom: 28px;
}
.logo-icon {
  font-size: 48px;
  color: #409eff;
}
.login-header h2 {
  margin: 10px 0 0;
  font-size: 26px;
  font-weight: 500;
}
.login-header p {
  margin: 6px 0 0;
  color: #909399;
  font-size: 14px;
}
.button-group {
  display: flex;
  gap: 12px;
  width: 100%;
}
.btn-login,
.btn-register {
  flex: 1;
}
.back-btn {
  width: 100%;
  margin-top: 10px;
}
/* 让登录注册按钮行和返回按钮整体下移 */
.login-card .el-form-item:nth-child(3) {
  margin-top: 30px;  /* 登录+注册行 */
}
.login-card .el-form-item:last-child {
  margin-top: 16px;  /* 返回按钮行 */
}
</style>