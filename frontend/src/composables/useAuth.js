import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { register, login } from '@/api/auth'

export function useAuth() {
  const router = useRouter()
  const userStore = useUserStore()
  const loading = ref(false)

  // 注册
  const handleRegister = async (username, password) => {
    loading.value = true
    try {
      await register(username, password)
      ElMessage.success('注册成功，请登录')
      router.push('/login')
    } catch (error) {
      ElMessage.error(error.response?.data?.detail || '注册失败')
    } finally {
      loading.value = false
    }
  }

  // 登录
  const handleLogin = async (username, password) => {
    loading.value = true
    try {
      const res = await login(username, password)
      userStore.setUser(res.user_id, username)
      ElMessage.success('登录成功')
      router.push('/chat')
    } catch (error) {
      ElMessage.error(error.response?.data?.detail || '登录失败')
    } finally {
      loading.value = false
    }
  }

  // 退出登录
  const logout = () => {
    userStore.logout()
    router.push('/login')
    ElMessage.info('已退出登录')
  }

  return {
    loading,
    handleRegister,
    handleLogin,
    logout
  }
}