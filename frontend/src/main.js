import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import App from './App.vue'
import router from './router'
import { useUserStore } from './stores/user'

const app = createApp(App)
const pinia = createPinia()
app.use(pinia)

// 必须在 router 注册前初始化用户状态
const userStore = useUserStore()
userStore.initFromStorage()
if (!userStore.isLoggedIn) {
  userStore.setGuest()   // 默认游客模式，user_id = 0, isLoggedIn = true
}

app.use(ElementPlus)
app.use(router)
app.mount('#app')