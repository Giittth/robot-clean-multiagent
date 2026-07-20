<template>
  <div class="register-container">
    <el-card class="register-card" shadow="hover">
      <div class="register-header">
        <el-icon class="logo-icon"><Edit /></el-icon>
        <h2>注册新账号</h2>
        <p>扫拖机器人 智能助手</p>
      </div>

      <el-form :model="form" :rules="rules" ref="formRef" label-position="top">
        <el-form-item label="用户名" prop="username">
          <el-input
            v-model="form.username"
            placeholder="请输入用户名（3-20个字符）"
            prefix-icon="User"
            size="large"
          />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            type="password"
            v-model="form.password"
            placeholder="请输入密码（至少6位）"
            prefix-icon="Lock"
            size="large"
            show-password
          />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input
            type="password"
            v-model="form.confirmPassword"
            placeholder="请再次输入密码"
            prefix-icon="Lock"
            size="large"
            show-password
          />
        </el-form-item>
        <el-form-item>
          <div class="button-group">
            <el-button type="primary" :loading="loading" @click="() => handleRegister(form.username, form.password)" class="btn-register">注册</el-button>
            <el-button @click="goLogin" class="btn-login">返回登录</el-button>
          </div>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '@/composables/useAuth'
import { Edit } from '@element-plus/icons-vue'

const router = useRouter()
const { loading, handleRegister } = useAuth()
const form = reactive({ username: '', password: '', confirmPassword: '' })
const formRef = ref(null)

// 自定义校验：密码长度至少6位
const validatePassword = (rule, value, callback) => {
  if (value.length < 6) {
    callback(new Error('密码长度不能少于6位'))
  } else {
    callback()
  }
}
// 确认密码校验
const validateConfirm = (rule, value, callback) => {
  if (value !== form.password) {
    callback(new Error('两次输入密码不一致'))
  } else {
    callback()
  }
}

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 20, message: '用户名长度 3-20 个字符', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { validator: validatePassword, trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    { validator: validateConfirm, trigger: 'blur' }
  ]
}

const goLogin = () => router.push('/login')
</script>

<style scoped>
.register-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  background: linear-gradient(135deg, #f5f7fa 0%, #e9edf2 100%);
}
.register-card {
  width: 460px;
  border-radius: 20px;
  padding: 20px 30px 30px;
  backdrop-filter: blur(4px);
  background: rgba(255, 255, 255, 0.85);
}
.register-header {
  text-align: center;
  margin-bottom: 28px;
}
.logo-icon {
  font-size: 48px;
  color: #409eff;
}
.register-header h2 {
  margin: 10px 0 0;
  font-size: 26px;
  font-weight: 500;
}
.register-header p {
  margin: 6px 0 0;
  color: #909399;
  font-size: 14px;
}
.button-group {
  display: flex;
  gap: 12px;
  width: 100%;
  margin-top: 16px;
}
.btn-register,
.btn-login {
  flex: 1;
}
</style>