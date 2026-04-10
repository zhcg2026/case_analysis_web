<template>
  <div class="knowledge-page">
    <div class="page-header">
      <h1 class="page-title">知识库</h1>
      <p class="page-desc">上传文档到向量库，支持智能问答和知识检索</p>
    </div>

    <!-- Tab切换 -->
    <div class="tab-nav">
      <button class="tab-btn" :class="{ active: activeTab === 'general' }" @click="activeTab = 'general'">
        通用知识库
      </button>
      <button class="tab-btn" :class="{ active: activeTab === 'standards' }" @click="activeTab = 'standards'">
        立结案标准库
      </button>
    </div>

    <!-- 通用知识库 -->
    <div v-show="activeTab === 'general'">
      <!-- 统计卡片 -->
      <div class="stats-card" v-if="stats.exists">
        <div class="stat-item">
          <span class="stat-label">向量数量</span>
          <span class="stat-value">{{ stats.count }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">文档数</span>
          <span class="stat-value">{{ documents.length }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">模型</span>
          <span class="stat-value">{{ stats.ollama_model }}</span>
        </div>
      </div>

    <!-- 两个主要功能区 -->
    <div class="main-content">
      <!-- 左侧：文档上传 -->
      <div class="upload-section">
        <div class="section-header">
          <h3>上传文档</h3>
        </div>

        <div class="upload-area">
          <div class="file-upload">
            <input type="file" ref="fileInput" @change="handleFileUpload" accept=".txt,.md,.docx,.xlsx" hidden />
            <button class="upload-btn" @click="$refs.fileInput.click()">
              <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                <polyline points="17 8 12 3 7 8"/>
                <line x1="12" y1="3" x2="12" y2="15"/>
              </svg>
              选择文件
            </button>
            <span class="file-info" v-if="selectedFile">{{ selectedFile.name }}</span>
          </div>

          <div class="file-upload">
            <input type="file" ref="zipInput" @change="handleZipUpload" accept=".zip" hidden />
            <button class="upload-btn batch-btn" @click="$refs.zipInput.click()">
              <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
              </svg>
              批量上传(zip)
            </button>
            <span class="file-info" v-if="selectedZip">{{ selectedZip.name }}</span>
          </div>

          <div class="text-upload">
            <textarea v-model="textContent" placeholder="或直接输入文本内容..." rows="6"></textarea>
            <input v-model="textSource" placeholder="来源名称（可选）" class="source-input" />
          </div>

          <button class="submit-btn" @click="uploadDocument" :disabled="uploading">
            {{ uploading ? '上传中...' : '提交到知识库' }}
          </button>

          <div class="upload-result" v-if="uploadResult">
            <span :class="uploadResult.success ? 'success' : 'error'">
              {{ uploadResult.message }}
            </span>
          </div>

          <!-- 批量上传进度 -->
          <div class="batch-progress" v-if="batchProgress">
            <div class="progress-bar">
              <div class="progress-fill" :style="{ width: (batchProgress.processed / batchProgress.total * 100) + '%' }"></div>
            </div>
            <div class="progress-text">
              处理中: {{ batchProgress.processed }} / {{ batchProgress.total }}
              (成功: {{ batchProgress.success }}, 失败: {{ batchProgress.failed }})
            </div>
          </div>
        </div>

        <!-- 文档列表 -->
        <div class="documents-list">
          <div class="section-header">
            <h3>已上传文档</h3>
            <div class="header-actions">
              <button class="batch-delete-btn" @click="batchDeleteDocuments" v-if="selectedDocs.length > 0">
                删除选中 ({{ selectedDocs.length }})
              </button>
              <button class="refresh-btn" @click="loadDocuments">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8"/>
                  <path d="M21 3v5h-5"/>
                </svg>
                刷新
              </button>
            </div>
          </div>

          <div class="documents-table" v-if="documents.length">
            <div class="doc-header">
              <label class="select-all">
                <input type="checkbox" :checked="selectedDocs.length === documents.length" @change="toggleSelectAll">
                全选
              </label>
              <span class="doc-count">共 {{ documents.length }} 个文档</span>
            </div>
            <div class="doc-item" v-for="doc in documents" :key="doc.doc_id">
              <input type="checkbox" :value="doc.doc_id" v-model="selectedDocs" class="doc-checkbox">
              <div class="doc-info">
                <span class="doc-id">{{ doc.doc_id }}</span>
                <span class="doc-chunks">{{ doc.chunks }} 个片段</span>
              </div>
              <div class="doc-sources">
                {{ doc.sources.join(', ') }}
              </div>
              <button class="delete-btn" @click="deleteDocument(doc.doc_id)">
                删除
              </button>
            </div>
          </div>
          <div class="empty-state" v-else>
            暂无文档
          </div>
        </div>
      </div>

      <!-- 右侧：问答区 -->
      <div class="qa-section">
        <div class="section-header">
          <h3>智能问答</h3>
        </div>

        <div class="qa-input">
          <textarea v-model="question" placeholder="输入问题，从知识库中检索答案..." rows="3"></textarea>
          <button class="ask-btn" @click="askQuestion" :disabled="asking || !question.trim()">
            {{ asking ? '思考中...' : '提问' }}
          </button>
        </div>

        <!-- 回答结果 -->
        <div class="qa-result" v-if="answer">
          <div class="answer-box">
            <div class="answer-header">
              <span class="answer-label">回答</span>
              <span class="answer-status" :class="answer.success ? 'success' : 'error'">
                {{ answer.success ? '成功' : '失败' }}
              </span>
            </div>
            <div class="answer-content">{{ answer.answer }}</div>
          </div>

          <div class="sources-box" v-if="answer.sources && answer.sources.length">
            <div class="sources-header">
              <span class="sources-label">参考来源</span>
            </div>
            <div class="sources-list">
              <div class="source-item" v-for="source in answer.sources" :key="source">
                {{ source }}
              </div>
            </div>
          </div>
        </div>

        <!-- 搜索结果 -->
        <div class="search-section">
          <div class="section-header">
            <h3>知识检索</h3>
          </div>

          <div class="search-input">
            <input v-model="searchQuery" placeholder="搜索关键词..." />
            <button class="search-btn" @click="searchKnowledge" :disabled="searching">
              {{ searching ? '搜索中...' : '搜索' }}
            </button>
          </div>

          <div class="search-results" v-if="searchResults.length">
            <div class="result-item" v-for="(result, index) in searchResults" :key="index">
              <div class="result-header">
                <span class="result-source">{{ result.source }}</span>
                <span class="result-score">相似度: {{ (result.score * 100).toFixed(1) }}%</span>
              </div>
              <div class="result-content">{{ result.content }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

    <!-- 立结案标准库 -->
    <div v-show="activeTab === 'standards'" class="standards-section">
      <!-- 统计卡片 -->
      <div class="stats-card" v-if="standardsStats.exists">
        <div class="stat-item">
          <span class="stat-label">父文档</span>
          <span class="stat-value">{{ standardsStats.parents || 0 }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">子文档</span>
          <span class="stat-value">{{ standardsStats.children || 0 }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">模式</span>
          <span class="stat-value">{{ standardsStats.mode || '未知' }}</span>
        </div>
      </div>

      <!-- 索引管理 -->
      <div class="index-section">
        <div class="section-header">
          <h3>索引管理</h3>
        </div>
        <div class="index-actions">
          <div class="index-input-row">
            <input v-model="standardsDirectory" placeholder="标准文件目录（如：D:/常用/立案结案标准）" class="directory-input" />
            <button class="index-btn" @click="indexStandards" :disabled="indexingStandards">
              {{ indexingStandards ? '索引中...' : '开始索引' }}
            </button>
          </div>
          <div class="index-result" v-if="indexResult">
            <div class="index-summary">
              成功: {{ indexResult.success }} | 失败: {{ indexResult.failed }} | 子文档: {{ indexResult.total_children }}
            </div>
            <div class="index-details" v-if="indexResult.details">
              <div class="detail-item" v-for="(d, i) in indexResult.details.slice(0, 10)" :key="i">
                <span :class="d.success ? 'success' : 'failed'">{{ d.file }}</span>
                <span class="detail-msg">{{ d.message }}</span>
              </div>
              <div class="more-details" v-if="indexResult.details.length > 10">
                ...共 {{ indexResult.details.length }} 个文件
              </div>
            </div>
          </div>
          <button class="clear-btn" @click="clearStandards" v-if="standardsStats.exists">
            清空标准库
          </button>
        </div>
      </div>

      <!-- 标准问答 -->
      <div class="standards-qa">
        <div class="section-header">
          <h3>立结案标准问答</h3>
        </div>
        <div class="qa-input">
          <textarea v-model="standardsQuestion" placeholder="输入问题，如：井盖破损的处置时限是多少？" rows="3"></textarea>
          <button class="ask-btn" @click="askStandards" :disabled="askingStandards || !standardsQuestion.trim()">
            {{ askingStandards ? '查询中...' : '提问' }}
          </button>
        </div>
        <div class="qa-result" v-if="standardsAnswer">
          <div class="answer-box">
            <div class="answer-header">
              <span class="answer-label">回答</span>
              <span class="answer-status" :class="standardsAnswer.success ? 'success' : 'error'">
                {{ standardsAnswer.success ? '成功' : '失败' }}
              </span>
            </div>
            <div class="answer-content">{{ standardsAnswer.answer }}</div>
          </div>
          <div class="sources-box" v-if="standardsAnswer.sources && standardsAnswer.sources.length">
            <div class="sources-header">参考案件类型</div>
            <div class="sources-list">
              <span class="source-tag" v-for="s in standardsAnswer.sources" :key="s">{{ s }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 标准搜索 -->
      <div class="standards-search">
        <div class="section-header">
          <h3>标准检索</h3>
        </div>
        <div class="search-input">
          <input v-model="standardsSearchQuery" placeholder="搜索关键词..." />
          <button class="search-btn" @click="searchStandards" :disabled="searchingStandards">
            {{ searchingStandards ? '搜索中...' : '搜索' }}
          </button>
        </div>
        <div class="search-results" v-if="standardsSearchResults.length">
          <div class="result-item" v-for="(r, i) in standardsSearchResults" :key="i">
            <div class="result-header">
              <span class="result-type">{{ r.case_type }}</span>
              <span class="result-score">相似度: {{ ((r.score || 0) * 100).toFixed(1) }}%</span>
            </div>
            <div class="result-child">{{ r.child_text }}</div>
            <div class="result-meta" v-if="r.meta_info">
              <span v-if="r.meta_info.time_limit">处置时限: {{ r.meta_info.time_limit }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useUserStore } from '../stores/user'

const userStore = useUserStore()

// 状态
const stats = ref({ exists: false, count: 0 })
const documents = ref([])
const selectedDocs = ref([])
const selectedFile = ref(null)
const selectedZip = ref(null)
const textContent = ref('')
const textSource = ref('')
const uploading = ref(false)
const uploadResult = ref(null)
const question = ref('')
const asking = ref(false)
const answer = ref(null)
const searchQuery = ref('')
const searching = ref(false)
const searchResults = ref([])

// Tab切换
const activeTab = ref('general')

// 立结案标准相关状态
const standardsStats = ref({ exists: false })
const standardsDirectory = ref('D:/常用/立案结案标准')
const indexingStandards = ref(false)
const indexResult = ref(null)
const standardsQuestion = ref('')
const askingStandards = ref(false)
const standardsAnswer = ref(null)
const standardsSearchQuery = ref('')
const searchingStandards = ref(false)
const standardsSearchResults = ref([])

// API基础URL
const apiBase = '/api/knowledge'

// 获取token
function getAuthHeaders() {
  const token = localStorage.getItem('token')
  return {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`
  }
}

// 加载统计信息
async function loadStats() {
  try {
    const res = await fetch(`${apiBase}/stats`, {
      headers: getAuthHeaders()
    })
    const data = await res.json()
    stats.value = data
  } catch (e) {
    console.error('加载统计失败:', e)
  }
}

// 加载文档列表
async function loadDocuments() {
  try {
    const res = await fetch(`${apiBase}/documents`, {
      headers: getAuthHeaders()
    })
    const data = await res.json()
    documents.value = data.documents || []
  } catch (e) {
    console.error('加载文档失败:', e)
  }
}

// 处理文件选择
function handleFileUpload(e) {
  selectedFile.value = e.target.files[0]
  textContent.value = ''
  uploadResult.value = null
}

// 处理zip文件选择
function handleZipUpload(e) {
  selectedZip.value = e.target.files[0]
  uploadResult.value = null
  if (selectedZip.value) {
    uploadZip()
  }
}

// 批量上传进度
const batchProgress = ref(null)

// 批量上传zip
async function uploadZip() {
  if (!selectedZip.value) {
    return
  }

  uploading.value = true
  uploadResult.value = null
  batchProgress.value = null

  try {
    const formData = new FormData()
    formData.append('file', selectedZip.value)

    const res = await fetch(`${apiBase}/batch-upload`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      },
      body: formData
    })
    const data = await res.json()
    uploadResult.value = data

    if (data.success && data.task_id) {
      selectedZip.value = null
      // 开始轮询进度
      pollProgress(data.task_id, data.total_files)
    }
  } catch (e) {
    uploadResult.value = { success: false, message: '批量上传失败: ' + e.message }
    uploading.value = false
  }
}

// 轮询上传进度
async function pollProgress(taskId, totalFiles) {
  batchProgress.value = { total: totalFiles, processed: 0, success: 0, failed: 0 }

  const poll = async () => {
    try {
      const res = await fetch(`${apiBase}/batch-upload/progress/${taskId}`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      })
      const data = await res.json()

      if (data.status === 'completed') {
        batchProgress.value = data
        uploading.value = false
        uploadResult.value = {
          success: true,
          message: `处理完成！成功 ${data.success} 个，失败 ${data.failed} 个`
        }
        loadStats()
        loadDocuments()
      } else {
        batchProgress.value = data
        // 继续轮询
        setTimeout(poll, 2000)
      }
    } catch (e) {
      console.error('获取进度失败:', e)
      setTimeout(poll, 2000)
    }
  }

  poll()
}

// 上传文档
async function uploadDocument() {
  if (!selectedFile.value && !textContent.value.trim()) {
    uploadResult.value = { success: false, message: '请选择文件或输入内容' }
    return
  }

  uploading.value = true
  uploadResult.value = null

  try {
    if (selectedFile.value) {
      // 文件上传
      const formData = new FormData()
      formData.append('file', selectedFile.value)

      const res = await fetch(`${apiBase}/upload`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: formData
      })
      const data = await res.json()
      uploadResult.value = data

      if (data.success) {
        selectedFile.value = null
        loadStats()
        loadDocuments()
      }
    } else {
      // 文本上传
      const res = await fetch(`${apiBase}/upload`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          content: textContent.value,
          source: textSource.value || '手动输入'
        })
      })
      const data = await res.json()
      uploadResult.value = data

      if (data.success) {
        textContent.value = ''
        textSource.value = ''
        loadStats()
        loadDocuments()
      }
    }
  } catch (e) {
    uploadResult.value = { success: false, message: '上传失败: ' + e.message }
  } finally {
    uploading.value = false
  }
}

// 全选/取消全选
function toggleSelectAll() {
  if (selectedDocs.value.length === documents.value.length) {
    selectedDocs.value = []
  } else {
    selectedDocs.value = documents.value.map(d => d.doc_id)
  }
}

// 批量删除
async function batchDeleteDocuments() {
  if (selectedDocs.value.length === 0) return
  if (!confirm(`确定删除选中的 ${selectedDocs.value.length} 个文档？`)) return

  try {
    const res = await fetch(`${apiBase}/documents/batch-delete`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ doc_ids: selectedDocs.value })
    })
    const data = await res.json()
    if (data.success) {
      alert(data.message)
      selectedDocs.value = []
      loadStats()
      loadDocuments()
    } else {
      alert('删除失败: ' + data.error)
    }
  } catch (e) {
    alert('删除失败: ' + e.message)
  }
}

// 删除文档
async function deleteDocument(docId) {
  if (!confirm('确定删除该文档？')) return

  try {
    const res = await fetch(`${apiBase}/documents/${docId}`, {
      method: 'DELETE',
      headers: getAuthHeaders()
    })
    const data = await res.json()
    if (data.success) {
      loadStats()
      loadDocuments()
    } else {
      alert('删除失败: ' + data.message)
    }
  } catch (e) {
    alert('删除失败: ' + e.message)
  }
}

// 提问
async function askQuestion() {
  if (!question.value.trim()) return

  asking.value = true
  answer.value = null

  try {
    const res = await fetch(`${apiBase}/ask`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ question: question.value })
    })
    const data = await res.json()
    answer.value = data
  } catch (e) {
    answer.value = { success: false, answer: '问答失败: ' + e.message }
  } finally {
    asking.value = false
  }
}

// 搜索
async function searchKnowledge() {
  if (!searchQuery.value.trim()) return

  searching.value = true
  searchResults.value = []

  try {
    const res = await fetch(`${apiBase}/search`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ query: searchQuery.value })
    })
    const data = await res.json()
    searchResults.value = data.results || []
  } catch (e) {
    console.error('搜索失败:', e)
  } finally {
    searching.value = false
  }
}

// ================= 立结案标准相关方法 =================

// 加载立结案标准统计
async function loadStandardsStats() {
  try {
    const res = await fetch('/api/case-standards/stats', {
      headers: getAuthHeaders()
    })
    const data = await res.json()
    standardsStats.value = data
  } catch (e) {
    console.error('加载标准统计失败:', e)
  }
}

// 索引立结案标准
async function indexStandards() {
  if (!standardsDirectory.value.trim()) {
    alert('请输入标准文件目录')
    return
  }

  indexingStandards.value = true
  indexResult.value = null

  try {
    const res = await fetch('/api/case-standards/index', {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ directory: standardsDirectory.value })
    })
    const data = await res.json()
    indexResult.value = data
    loadStandardsStats()
  } catch (e) {
    indexResult.value = { success: 0, failed: 1, total_children: 0, details: [{ file: '错误', message: e.message }] }
  } finally {
    indexingStandards.value = false
  }
}

// 清空立结案标准库
async function clearStandards() {
  if (!confirm('确定清空立结案标准库？')) return

  try {
    const res = await fetch('/api/case-standards/clear', {
      method: 'POST',
      headers: getAuthHeaders()
    })
    const data = await res.json()
    if (data.success) {
      alert(data.message)
      standardsStats.value = { exists: false }
      indexResult.value = null
    } else {
      alert('清空失败: ' + data.message)
    }
  } catch (e) {
    alert('清空失败: ' + e.message)
  }
}

// 立结案标准问答
async function askStandards() {
  if (!standardsQuestion.value.trim()) return

  askingStandards.value = true
  standardsAnswer.value = null

  try {
    const res = await fetch('/api/case-standards/ask', {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ question: standardsQuestion.value })
    })
    const data = await res.json()
    standardsAnswer.value = data
  } catch (e) {
    standardsAnswer.value = { success: false, answer: '查询失败: ' + e.message }
  } finally {
    askingStandards.value = false
  }
}

// 搜索立结案标准
async function searchStandards() {
  if (!standardsSearchQuery.value.trim()) return

  searchingStandards.value = true
  standardsSearchResults.value = []

  try {
    const res = await fetch('/api/case-standards/search', {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ query: standardsSearchQuery.value })
    })
    const data = await res.json()
    standardsSearchResults.value = data.results || []
  } catch (e) {
    console.error('标准搜索失败:', e)
  } finally {
    searchingStandards.value = false
  }
}

// 初始化
onMounted(() => {
  loadStats()
  loadDocuments()
  loadStandardsStats()
})
</script>

<style scoped>
.knowledge-page {
  padding: var(--space-6);
  max-width: 1400px;
}

.page-header {
  margin-bottom: var(--space-6);
}

.page-title {
  font-size: 28px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: var(--space-2);
}

.page-desc {
  color: var(--text-secondary);
  font-size: 14px;
}

.stats-card {
  display: flex;
  gap: var(--space-4);
  padding: var(--space-4);
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-lighter);
  margin-bottom: var(--space-6);
}

.stat-item {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.stat-label {
  font-size: 12px;
  color: var(--text-tertiary);
}

.stat-value {
  font-size: 18px;
  font-weight: 600;
  color: var(--primary-500);
}

.main-content {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-6);
}

.upload-section,
.qa-section {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-lighter);
  padding: var(--space-4);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-4);
}

.section-header h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.upload-area {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.file-upload {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.upload-btn {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-4);
  background: var(--primary-500);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  font-size: 14px;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.upload-btn:hover {
  background: var(--primary-600);
}

.upload-btn.batch-btn {
  background: var(--success, #10b981);
}

.upload-btn.batch-btn:hover {
  background: var(--success-dark, #059669);
}

.file-info {
  color: var(--text-secondary);
  font-size: 13px;
}

.text-upload textarea {
  width: 100%;
  padding: var(--space-3);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  font-size: 14px;
  resize: vertical;
  background: var(--bg-base);
  color: var(--text-primary);
}

.source-input {
  width: 100%;
  padding: var(--space-2);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  font-size: 14px;
  background: var(--bg-base);
  color: var(--text-primary);
}

.submit-btn {
  padding: var(--space-3);
  background: var(--success);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.submit-btn:hover:not(:disabled) {
  background: #16a34a;
}

.submit-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.upload-result {
  padding: var(--space-2);
  border-radius: var(--radius-md);
  font-size: 13px;
}

.upload-result .success {
  color: var(--success);
}

.upload-result .error {
  color: var(--danger);
}

.batch-progress {
  margin-top: var(--space-3);
}

.batch-progress .progress-bar {
  width: 100%;
  height: 8px;
  background: var(--fill-light);
  border-radius: 4px;
  overflow: hidden;
}

.batch-progress .progress-fill {
  height: 100%;
  background: var(--primary-500);
  transition: width 0.3s ease;
}

.batch-progress .progress-text {
  margin-top: var(--space-1);
  font-size: 13px;
  color: var(--text-secondary);
}

.documents-list {
  margin-top: var(--space-6);
  padding-top: var(--space-4);
  border-top: 1px solid var(--border-lighter);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.refresh-btn {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-2);
  background: var(--fill-light);
  border: none;
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
}

.batch-delete-btn {
  padding: var(--space-1) var(--space-3);
  background: var(--danger, #ef4444);
  color: white;
  border: none;
  border-radius: var(--radius-sm);
  font-size: 12px;
  cursor: pointer;
}

.batch-delete-btn:hover {
  opacity: 0.9;
}

.documents-table {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.doc-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-2);
  background: var(--fill-light);
  border-radius: var(--radius-sm);
}

.select-all {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: 13px;
  cursor: pointer;
}

.doc-count {
  font-size: 12px;
  color: var(--text-secondary);
}

.doc-checkbox {
  margin-right: var(--space-2);
  cursor: pointer;
}

.doc-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  background: var(--fill-light);
  border-radius: var(--radius-md);
}

.doc-info {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex: 1;
}

.doc-id {
  font-size: 13px;
  color: var(--text-primary);
  font-weight: 500;
}

.doc-chunks {
  font-size: 12px;
  color: var(--text-tertiary);
}

.doc-sources {
  flex: 1;
  font-size: 12px;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
}

.delete-btn {
  padding: var(--space-1) var(--space-2);
  background: var(--danger-light);
  color: var(--danger);
  border: none;
  border-radius: var(--radius-sm);
  font-size: 12px;
  cursor: pointer;
}

.empty-state {
  text-align: center;
  color: var(--text-tertiary);
  padding: var(--space-4);
}

/* 问答区样式 */
.qa-input textarea {
  width: 100%;
  padding: var(--space-3);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  font-size: 14px;
  resize: vertical;
  background: var(--bg-base);
  color: var(--text-primary);
}

.ask-btn {
  margin-top: var(--space-2);
  padding: var(--space-2) var(--space-4);
  background: var(--primary-500);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  font-size: 14px;
  cursor: pointer;
}

.ask-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.qa-result {
  margin-top: var(--space-4);
}

.answer-box {
  padding: var(--space-3);
  background: var(--primary-50);
  border-radius: var(--radius-md);
  margin-bottom: var(--space-3);
}

[data-theme="dark"] .answer-box {
  background: rgba(64, 158, 255, 0.1);
}

.answer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-2);
}

.answer-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--primary-500);
}

.answer-status {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
}

.answer-status.success {
  background: var(--success-light);
  color: var(--success);
}

.answer-status.error {
  background: var(--danger-light);
  color: var(--danger);
}

.answer-content {
  font-size: 14px;
  color: var(--text-primary);
  line-height: 1.6;
}

.sources-box {
  padding: var(--space-3);
  background: var(--fill-light);
  border-radius: var(--radius-md);
}

.sources-header {
  margin-bottom: var(--space-2);
}

.sources-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
}

.sources-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.source-item {
  padding: var(--space-1) var(--space-2);
  background: var(--bg-card);
  border-radius: var(--radius-sm);
  font-size: 12px;
  color: var(--text-secondary);
}

/* 搜索区样式 */
.search-section {
  margin-top: var(--space-6);
  padding-top: var(--space-4);
  border-top: 1px solid var(--border-lighter);
}

.search-input {
  display: flex;
  gap: var(--space-2);
}

.search-input input {
  flex: 1;
  padding: var(--space-2);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  font-size: 14px;
  background: var(--bg-base);
  color: var(--text-primary);
}

.search-btn {
  padding: var(--space-2) var(--space-3);
  background: var(--fill-light);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  font-size: 14px;
  cursor: pointer;
}

.search-btn:disabled {
  opacity: 0.5;
}

.search-results {
  margin-top: var(--space-3);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.result-item {
  padding: var(--space-3);
  background: var(--fill-light);
  border-radius: var(--radius-md);
}

.result-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: var(--space-2);
}

.result-source {
  font-size: 12px;
  color: var(--text-secondary);
}

.result-score {
  font-size: 12px;
  color: var(--success);
}

.result-content {
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.5;
}

/* Tab导航样式 */
.tab-nav {
  display: flex;
  gap: var(--space-2);
  margin-bottom: var(--space-4);
}

.tab-btn {
  padding: var(--space-2) var(--space-4);
  background: var(--fill-light);
  border: 1px solid var(--border-lighter);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  font-size: 14px;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.tab-btn.active {
  background: var(--primary-500);
  color: white;
  border-color: var(--primary-500);
}

.tab-btn:hover:not(.active) {
  background: var(--fill-dark);
}

/* 立结案标准模块样式 */
.standards-section {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-lighter);
  padding: var(--space-4);
}

.index-section {
  margin-bottom: var(--space-6);
}

.index-actions {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.index-input-row {
  display: flex;
  gap: var(--space-3);
}

.directory-input {
  flex: 1;
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  font-size: 14px;
  background: var(--bg-base);
  color: var(--text-primary);
}

.index-btn {
  padding: var(--space-2) var(--space-4);
  background: var(--primary-500);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  font-size: 14px;
  cursor: pointer;
}

.index-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.index-result {
  padding: var(--space-3);
  background: var(--fill-light);
  border-radius: var(--radius-md);
}

.index-summary {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: var(--space-2);
}

.index-details {
  font-size: 12px;
}

.detail-item {
  display: flex;
  gap: var(--space-2);
  padding: var(--space-1) 0;
}

.detail-item .success {
  color: var(--success);
}

.detail-item .failed {
  color: var(--danger);
}

.detail-msg {
  color: var(--text-secondary);
}

.more-details {
  color: var(--text-tertiary);
  font-size: 12px;
}

.clear-btn {
  padding: var(--space-2) var(--space-3);
  background: var(--danger-light);
  color: var(--danger);
  border: none;
  border-radius: var(--radius-md);
  font-size: 13px;
  cursor: pointer;
}

.standards-qa {
  margin-bottom: var(--space-6);
  padding-top: var(--space-4);
  border-top: 1px solid var(--border-lighter);
}

.standards-search {
  padding-top: var(--space-4);
  border-top: 1px solid var(--border-lighter);
}

.source-tag {
  padding: var(--space-1) var(--space-2);
  background: var(--primary-50);
  color: var(--primary-500);
  border-radius: var(--radius-sm);
  font-size: 12px;
}

.result-type {
  font-size: 12px;
  color: var(--primary-500);
  font-weight: 500;
}

.result-child {
  font-size: 13px;
  color: var(--text-primary);
  margin: var(--space-1) 0;
}

.result-meta {
  font-size: 12px;
  color: var(--text-secondary);
}

@media (max-width: 900px) {
  .main-content {
    grid-template-columns: 1fr;
  }

  .index-input-row {
    flex-direction: column;
  }
}
</style>