<template>
  <div class="scene-selector">
    <div class="scene-label">
      <el-icon><Location /></el-icon>
      <span>当前场景</span>
    </div>
    <el-select
      v-model="currentScene"
      placeholder="选择户型"
      @change="handleSceneChange"
      size="default"
      style="width: 104px;"
    >
      <el-option label="标准" value="standard"></el-option>
      <el-option label="开放式" value="open_plan"></el-option>
      <el-option label="公寓" value="apartment"></el-option>
      <el-option label="别墅" value="villa"></el-option>
      <el-option label="大别墅" value="mansion"></el-option>
      <el-option label="办公室" value="office"></el-option>
      <el-option label="单间公寓" value="studio"></el-option>
      <el-option label="学校教室" value="school_floor"></el-option>
      <el-option label="餐厅" value="restaurant"></el-option>
      <el-option label="商场" value="mall_floor"></el-option>
      <!-- 未来扩展：用户自定义场景可动态添加 -->
    </el-select>
    <!-- 预留扩展：管理场景按钮 -->
    <el-button
      v-if="showManageButton"
      text
      @click="openSceneManager"
      class="manage-btn"
    >
      <el-icon><Setting /></el-icon> 管理
    </el-button>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Location, Setting } from '@element-plus/icons-vue'
import axios from 'axios'

const currentScene = ref('standard')
const showManageButton = ref(false)  // 未来可开启，实现自定义场景对话框

// 切换场景时调用后端 API
async function handleSceneChange(sceneName) {
  try {
    await axios.post(`/api/robot/scenario?scenario_name=${sceneName}`)
    ElMessage.success(`已切换至「${sceneName}」户型`)
    // 可选：触发全局事件，通知其他组件重新加载房间数据（如果需要）
  } catch (error) {
    console.error('切换场景失败', error)
    ElMessage.error('切换户型失败，请稍后重试')
    // 恢复下拉框的值
    currentScene.value = 'standard'
  }
}

// 预留：打开场景管理对话框（未来实现）
function openSceneManager() {
  ElMessage.info('场景管理功能开发中')
}
</script>

<style scoped>
.scene-selector {
  display: flex;
  align-items: center;
  gap: 12px;
  background: #f9fafb;
  padding: 6px 8px;
  border-radius: 8px;
  margin: 16px 0;
}
.scene-label {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #1f2937;
  font-weight: 500;
  font-size: 14px;
}
.manage-btn {
  margin-left: auto;
}
</style>