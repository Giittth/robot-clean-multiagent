<template>
  <div class="memory-container">
    <div class="header">
      <h2>长期记忆管理</h2>
      <el-button type="danger" @click="clearAll">清空所有记忆</el-button>
    </div>
    <el-table :data="memoryList" v-loading="loading" style="width: 100%">
      <el-table-column prop="id" label="ID" width="200" />
      <el-table-column prop="text" label="记忆内容" />
      <el-table-column prop="timestamp" label="创建时间" width="180" />
      <el-table-column label="操作" width="100">
        <template #default="{ row }">
          <el-button size="small" type="danger" @click="deleteOne(row.id)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listMemories, deleteMemory, clearAllMemories } from '@/api/memory'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const memoryList = ref([])
const loading = ref(false)

const fetchMemories = async () => {
  if (!userStore.user_id || userStore.user_id === 0) return
  loading.value = true
  try {
    const res = await listMemories(userStore.user_id)
    memoryList.value = res
  } catch (err) {
    ElMessage.error('获取记忆失败')
  } finally {
    loading.value = false
  }
}

const deleteOne = (id) => {
  ElMessageBox.confirm('确定删除该条记忆？', '提示', { type: 'warning' }).then(async () => {
    await deleteMemory(userStore.user_id, id)
    ElMessage.success('删除成功')
    await fetchMemories()
  }).catch(() => {})
}

const clearAll = () => {
  ElMessageBox.confirm('确定清空所有长期记忆？不可恢复', '警告', { type: 'error' }).then(async () => {
    await clearAllMemories(userStore.user_id)
    ElMessage.success('已清空')
    await fetchMemories()
  }).catch(() => {})
}

onMounted(() => {
  fetchMemories()
})
</script>

<style scoped>
.memory-container {
  padding: 20px;
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
</style>