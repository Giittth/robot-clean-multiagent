<template>
  <div class="knowledge-container">
    <div class="header">
      <h2>知识库管理</h2>
    </div>

    <!-- 公共知识库（只读，始终显示一行） -->
    <div class="public-section">
      <h3>公共知识库</h3>
      <el-table :data="publicKb ? [publicKb] : []" style="width: 100%" v-loading="loading">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="description" label="描述" />
        <el-table-column prop="create_time" label="创建时间" width="180" />
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button size="small" type="info" @click="viewDocs(row.id)">查看文档</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 私有知识库（可管理） -->
    <div class="private-section" style="margin-top: 30px;">
      <div class="section-header">
        <h3>我的知识库</h3>
        <el-button type="primary" @click="openCreateDialog" v-if="userStore.isLoggedIn && userStore.user_id !== 0">新建知识库</el-button>
      </div>
      <el-table :data="privateKbList" style="width: 100%" v-loading="loading">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="description" label="描述" />
        <el-table-column prop="create_time" label="创建时间" width="180" />
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <template v-if="userStore.isLoggedIn && userStore.user_id !== 0 && row.id !== 1">
              <el-button size="small" @click="openEditDialog(row)">编辑</el-button>
              <el-button size="small" type="danger" @click="confirmDelete(row.id)">删除</el-button>
            </template>
            <el-button size="small" type="info" @click="viewDocs(row.id)">文档</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 文档管理对话框 -->
    <el-dialog v-model="docDialogVisible" :title="`知识库文档 - ${currentKbName}`" width="70%">
      <div class="doc-actions" v-if="userStore.isLoggedIn && userStore.user_id !== 0 && currentKbId !== 1">
        <el-button type="primary" size="small" @click="openCreateDocDialog">上传文档</el-button>
      </div>
      <el-table :data="docList" v-loading="docLoading">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="title" label="标题" />
        <el-table-column prop="create_time" label="上传时间" width="180" />
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button size="small" type="danger" @click="confirmDeleteDoc(row.id)" :disabled="!(userStore.isLoggedIn && userStore.user_id !== 0 && currentKbId !== 1)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <!-- 新建/编辑知识库对话框 -->
    <el-dialog v-model="kbDialogVisible" :title="kbDialogTitle" width="30%">
      <el-form :model="kbForm" label-width="80px">
        <el-form-item label="名称">
          <el-input v-model="kbForm.name" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input type="textarea" v-model="kbForm.description" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="kbDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitKbForm">确定</el-button>
      </template>
    </el-dialog>

    <!-- 上传文档对话框 -->
    <el-dialog v-model="docFormVisible" title="上传文档" width="50%">
      <el-form :model="docForm" label-width="80px">
        <el-form-item label="标题">
          <el-input v-model="docForm.title" />
        </el-form-item>
        <el-form-item label="内容">
          <el-input type="textarea" :rows="10" v-model="docForm.content" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="docFormVisible = false">取消</el-button>
        <el-button type="primary" @click="submitDocForm">上传</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { useKnowledgeStore } from '@/stores/knowledge'
import { useKnowledge } from '@/composables/useKnowledge'

const userStore = useUserStore()
const knowledgeStore = useKnowledgeStore()
const {
  loading,
  docLoading,
  fetchKnowledgeBases,
  createKb,
  updateKb,
  deleteKb,
  fetchDocuments,
  createDoc,
  deleteDoc
} = useKnowledge()

// 公共知识库（单独存储，若后端无数据则构造默认对象）
const publicKb = ref({ id: 1, name: '公共知识库', description: '默认', create_time: '' })

// 私有知识库（排除 id=1）
const privateKbList = computed(() => knowledgeStore.kb_list.filter(kb => kb.id !== 1))

// 加载公共知识库（静默失败，保证至少有一个占位对象）
const loadPublicKb = async () => {
  try {
    const baseUrl = import.meta.env.VITE_API_BASE_URL
    const response = await fetch(`${baseUrl}/knowledge/public`)
    if (response.ok) {
      const data = await response.json()
      publicKb.value = data
    } else {
      // 保持已有虚拟对象，或替换为默认值
      publicKb.value = { id: 1, name: '公共知识库', description: '默认', create_time: '' }
    }
  } catch (err) {
    console.error('加载公共知识库失败', err)
    publicKb.value = { id: 1, name: '公共知识库', description: '默认', create_time: '' }
  }
}

// 知识库相关状态
const kbDialogVisible = ref(false)
const kbDialogTitle = ref('新建知识库')
const kbForm = reactive({ id: null, name: '', description: '' })

// 文档相关状态
const docDialogVisible = ref(false)
const currentKbId = ref(null)
const currentKbName = ref('')
const docList = ref([])

const docFormVisible = ref(false)
const docForm = reactive({ title: '', content: '' })

// 新建知识库
const openCreateDialog = () => {
  if (!userStore.isLoggedIn || userStore.user_id === 0) {
    ElMessage.warning('请先登录')
    return
  }
  kbDialogTitle.value = '新建知识库'
  kbForm.id = null
  kbForm.name = ''
  kbForm.description = ''
  kbDialogVisible.value = true
}

// 编辑知识库（仅私有库）
const openEditDialog = (row) => {
  if (row.id === 1) {
    ElMessage.warning('公共知识库不可编辑')
    return
  }
  kbDialogTitle.value = '编辑知识库'
  kbForm.id = row.id
  kbForm.name = row.name
  kbForm.description = row.description
  kbDialogVisible.value = true
}

const submitKbForm = async () => {
  if (!kbForm.name.trim()) {
    ElMessage.warning('请输入名称')
    return
  }
  if (kbForm.id) {
    await updateKb(kbForm.id, kbForm.name, kbForm.description)
  } else {
    await createKb(kbForm.name, kbForm.description)
  }
  kbDialogVisible.value = false
}

// 删除知识库（仅私有库）
const confirmDelete = (id) => {
  if (id === 1) {
    ElMessage.warning('公共知识库不可删除')
    return
  }
  ElMessageBox.confirm('确定删除该知识库吗？所有文档将被删除', '警告', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(async () => {
    await deleteKb(id)
  }).catch(() => {})
}

// 查看文档（公共/私有均可）
const viewDocs = async (kbId) => {
  currentKbId.value = kbId
  const kb = knowledgeStore.kb_list.find(k => k.id === kbId) || publicKb.value
  currentKbName.value = kb ? kb.name : '知识库'
  try {
    docList.value = await fetchDocuments(kbId)
  } catch (err) {
    console.error('获取文档列表失败', err)
    docList.value = []  // 静默失败，不弹出用户提示
  }
  docDialogVisible.value = true
}

// 上传文档
const openCreateDocDialog = () => {
  if (!userStore.isLoggedIn || userStore.user_id === 0) {
    ElMessage.warning('请先登录')
    return
  }
  if (currentKbId.value === 1) {
    ElMessage.warning('公共知识库只读，不能上传文档')
    return
  }
  docForm.title = ''
  docForm.content = ''
  docFormVisible.value = true
}

const submitDocForm = async () => {
  if (!docForm.title.trim() || !docForm.content.trim()) {
    ElMessage.warning('请填写标题和内容')
    return
  }
  const success = await createDoc(currentKbId.value, docForm.title, docForm.content)
  if (success) {
    docFormVisible.value = false
    docList.value = await fetchDocuments(currentKbId.value)
  }
}

// 删除文档
const confirmDeleteDoc = (docId) => {
  if (!userStore.isLoggedIn || userStore.user_id === 0 || currentKbId.value === 1) {
    ElMessage.warning('无权限删除')
    return
  }
  ElMessageBox.confirm('确定删除该文档吗？', '警告', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(async () => {
    await deleteDoc(docId)
    docList.value = await fetchDocuments(currentKbId.value)
  }).catch(() => {})
}

onMounted(() => {
  fetchKnowledgeBases()
  loadPublicKb()
})
</script>

<style scoped>
.knowledge-container {
  padding: 20px;
}
.header {
  margin-bottom: 20px;
}
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.doc-actions {
  margin-bottom: 16px;
}
</style>