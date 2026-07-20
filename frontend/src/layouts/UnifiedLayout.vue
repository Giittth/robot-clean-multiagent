<template>
  <div class="unified-layout">
    <aside class="sidebar">
      <el-menu :default-active="route.path" @select="handleMenuSelect">
        <el-menu-item index="/chat">
          <el-icon><ChatDotRound /></el-icon>
          <span>聊天</span>
        </el-menu-item>
        <el-menu-item index="/knowledge">
          <el-icon><Document /></el-icon>
          <span>知识库</span>
        </el-menu-item>
        <el-menu-item index="/memory">
          <el-icon><Memo /></el-icon>
          <span>记忆</span>
        </el-menu-item>
        <el-menu-item index="/robot/mission">
          <el-icon><Monitor /></el-icon>
          <span>机器人监控</span>
        </el-menu-item>
        <el-menu-item index="/robot/history">
          <el-icon><Timer /></el-icon>
          <span>任务历史</span>
        </el-menu-item>
      </el-menu>
    </aside>

    <main class="main-content">
      <router-view :key="$route.fullPath" />
    </main>

    <aside v-if="showRightPanel" class="status-panel">
      <RobotStatusCard />
      <!-- 新增：机器人生命周期卡片 -->
      <RobotLifecycleCard />
      <CurrentTaskCard />
      <!-- 系统健康卡片（已注释） -->
      <!-- <SystemHealthCard /> -->
    </aside>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ChatDotRound, Document, Memo, Monitor, Timer } from '@element-plus/icons-vue'
import RobotStatusCard from '@/components/robot/dashboard/RobotStatusCard.vue'
import RobotLifecycleCard from '@/components/robot/dashboard/RobotLifecycleCard.vue'
import CurrentTaskCard from '@/components/robot/mission/CurrentTaskCard.vue'

const route = useRoute()
const router = useRouter()

const showRightPanel = computed(() => !route.path.startsWith('/robot'))

function handleMenuSelect(index) {
  if (route.path === index) return
  router.push(index).catch(err => {
    if (err.name !== 'NavigationDuplicated') console.error(err)
  })
}

</script>

<style scoped>
.unified-layout {
  display: flex;
  height: 100vh;
  background: #f5f7fa;
}

/* 左侧菜单 */
.sidebar {
  width: 240px;
  background: #fff;
  border-right: 1px solid #e4e7ed;
  overflow-y: auto;
}

/* 主工作区 */
.main-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

/* 右侧面板 */
.status-panel {
  width: 360px;
  background: #fff;
  border-left: 1px solid #e4e7ed;
  padding: 32px 16px 16px 16px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* 页面切换动画 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
