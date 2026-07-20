import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/stores/user'

import Login from '@/views/Login.vue'
import Register from '@/views/Register.vue'
import UnifiedLayout from '@/layouts/UnifiedLayout.vue'      // 统一布局

import Chat from '@/views/Chat.vue'
import KnowledgeBase from '@/views/KnowledgeBase.vue'
import Memory from '@/views/Memory.vue'
import MissionCenter from '@/views/robot/MissionCenter.vue'
import TaskHistory from '@/views/robot/TaskHistory.vue'

const routes = [
  { path: '/login', component: Login, meta: { requiresAuth: false } },
  { path: '/register', component: Register, meta: { requiresAuth: false } },
  {
    path: '/',
    component: UnifiedLayout,
    meta: { requiresAuth: false },
    children: [
      { path: '', redirect: '/chat' },
      { path: 'chat', component: Chat },
      { path: 'knowledge', component: KnowledgeBase },
      { path: 'memory', component: Memory },
      { path: 'robot/mission', component: MissionCenter },
      { path: 'robot/history', component: TaskHistory }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  const userStore = useUserStore()
  if (to.meta.requiresAuth && !userStore.isLoggedIn) {
    next('/login')
  } else {
    next()
  }
})

export default router