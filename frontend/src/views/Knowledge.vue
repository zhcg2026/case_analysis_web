<template>
  <div class="knowledge-page">
    <div class="page-header">
      <h1 class="page-title">知识库</h1>
      <p class="page-desc">上传文档到向量库，支持智能问答和知识检索</p>
    </div>

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
            <input type="file" ref="fileInput" @change="handleFileUpload" accept=".txt,.md,.docx" hidden />
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
        </div>

        <!-- 文档列表 -->
        <div class="documents-list">
          <div class="section-header">
            <h3>已上传文档</h3>
            <button class="refresh-btn" @click="loadDocuments">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8"/>
                <path d="M21 3v5h-5"/>
              </svg>
              刷新
            </button>
          </div>

          <div class="documents-table" v-if="documents.length">
            <div class="doc-item" v-for="doc in documents" :key="doc.doc_id">
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
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useUserStore } from '../stores/user'

const userStore = useUserStore()

// 状态
const stats = ref({ exists: false, count: 0 })
const documents = ref([])
const selectedFile = ref(null)
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

// 初始化
onMounted(() => {
  loadStats()
  loadDocuments()
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

.documents-list {
  margin-top: var(--space-6);
  padding-top: var(--space-4);
  border-top: 1px solid var(--border-lighter);
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

.documents-table {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
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

@media (max-width: 900px) {
  .main-content {
    grid-template-columns: 1fr;
  }
}
</style>