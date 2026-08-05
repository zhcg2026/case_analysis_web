<template>
  <div class="page-container">
    <div class="article-detail" v-if="article">
      <div class="article-header">
        <router-link to="/" class="back-link">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="15 18 9 12 15 6"/>
          </svg>
          返回首页
        </router-link>
        <h1 class="article-title">{{ article.title }}</h1>
        <div class="article-meta">
          <span class="meta-item">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M4 6h16M4 12h16M4 18h16"/>
            </svg>
            {{ categoryName }}
          </span>
          <span class="meta-item">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
              <line x1="16" y1="2" x2="16" y2="6"/>
              <line x1="8" y1="2" x2="8" y2="6"/>
              <line x1="3" y1="10" x2="21" y2="10"/>
            </svg>
            {{ formatDate(article.created_at) }}
          </span>
          <span class="meta-item">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
              <circle cx="12" cy="12" r="3"/>
            </svg>
            {{ article.view_count || 0 }} 次阅读
          </span>
        </div>
      </div>

      <div class="article-summary" v-if="article.summary">
        <p>{{ article.summary }}</p>
      </div>

      <div class="article-content" v-html="formattedContent"></div>

      <!-- 附件区域 -->
      <div class="attachment-section" v-if="article.file_path">
        <h3 class="attachment-title">
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/>
          </svg>
          附件
        </h3>
        <div class="attachment-actions">
          <button v-if="isPdf" class="preview-btn" @click="togglePreview">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
              <circle cx="12" cy="12" r="3"/>
            </svg>
            {{ showPreview ? '收起预览' : '预览文档' }}
          </button>
          <button class="download-btn" @click="downloadFile">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
              <polyline points="7 10 12 15 17 10"/>
              <line x1="12" y1="15" x2="12" y2="3"/>
            </svg>
            下载附件
          </button>
        </div>
        <!-- PDF 预览区域 -->
        <div v-if="isPdf && showPreview" class="pdf-preview-container">
          <iframe
            :src="pdfPreviewUrl"
            class="pdf-preview-frame"
            frameborder="0"
          ></iframe>
          <div class="pdf-preview-actions">
            <button class="pdf-action-btn" @click="openFullscreen">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="15 3 21 3 21 9"/>
                <polyline points="9 21 3 21 3 15"/>
                <line x1="21" y1="3" x2="14" y2="10"/>
                <line x1="3" y1="21" x2="10" y2="14"/>
              </svg>
              全屏查看
            </button>
          </div>
        </div>
      </div>
    </div>

    <div class="loading-state" v-else-if="loading">
      <div class="loading-spinner"></div>
      <span>加载中...</span>
    </div>

    <div class="error-state" v-else>
      <svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
        <circle cx="12" cy="12" r="10"/>
        <line x1="12" y1="8" x2="12" y2="12"/>
        <line x1="12" y1="16" x2="12.01" y2="16"/>
      </svg>
      <p>文章不存在或已被删除</p>
      <router-link to="/" class="btn btn-primary">返回首页</router-link>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'

const route = useRoute()
const article = ref(null)
const loading = ref(true)
const categoryName = ref('')
const showPreview = ref(false)

// 判断是否为 PDF 文件
const isPdf = computed(() => {
  const filePath = article.value?.file_path || ''
  return filePath.toLowerCase().endsWith('.pdf')
})

// PDF 预览 URL（确保路径以 / 开头）
const pdfPreviewUrl = computed(() => {
  if (!article.value?.file_path) return ''
  const path = article.value.file_path
  return path.startsWith('/') ? path : '/' + path
})

async function fetchArticle() {
  const articleId = route.params.id
  if (!articleId) return

  loading.value = true
  try {
    const response = await axios.get(`/api/articles/${articleId}`)
    article.value = response.data

    // 获取栏目名称
    if (article.value.category_id) {
      const catResponse = await axios.get('/api/categories')
      const cat = catResponse.data.categories?.find(c => c.id === article.value.category_id)
      categoryName.value = cat?.name || '未分类'
    }
  } catch (error) {
    console.error('获取文章失败:', error)
    article.value = null
  } finally {
    loading.value = false
  }
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  })
}

const formattedContent = computed(() => {
  if (!article.value?.content) return ''

  let content = article.value.content

  // 如果内容已经是HTML格式（包含HTML标签），直接返回
  if (/<[a-z][\s\S]*>/i.test(content)) {
    return content
  }

  // 兼容旧数据：处理markdown风格的图片: ![alt](url)
  content = content.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" style="max-width:100%;border-radius:8px;margin:16px 0;" />')

  // 简单的换行处理
  content = content.replace(/\n/g, '<br>')

  return content
})

function togglePreview() {
  showPreview.value = !showPreview.value
}

function openFullscreen() {
  if (!pdfPreviewUrl.value) return
  window.open(pdfPreviewUrl.value, '_blank')
}

function downloadFile() {
  if (!article.value?.file_path) return

  // 确保路径以 / 开头
  const path = article.value.file_path
  const url = path.startsWith('/') ? path : '/' + path

  // 使用 fetch 下载文件
  fetch(url)
    .then(response => {
      if (!response.ok) throw new Error('下载失败')
      return response.blob()
    })
    .then(blob => {
      // 从路径中提取文件名
      const filename = path.split('/').pop() || 'download'
      // 创建下载链接
      const blobUrl = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = blobUrl
      link.download = filename
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(blobUrl)
    })
    .catch(error => {
      console.error('下载失败:', error)
      alert('下载失败，请重试')
    })
}

watch(() => route.params.id, fetchArticle)

onMounted(fetchArticle)
</script>

<style scoped>
.page-container {
  padding: var(--space-6);
  max-width: 900px;
  margin: 0 auto;
}

.article-detail {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-lighter);
  padding: var(--space-8);
}

.article-header {
  margin-bottom: var(--space-6);
  padding-bottom: var(--space-6);
  border-bottom: 1px solid var(--border-lighter);
}

.back-link {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  color: var(--primary-500);
  text-decoration: none;
  font-size: 14px;
  margin-bottom: var(--space-4);
}

.back-link:hover {
  color: var(--primary-600);
}

.article-title {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 var(--space-4);
  line-height: 1.4;
}

.article-meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-4);
}

.meta-item {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: 14px;
  color: var(--text-tertiary);
}

.article-summary {
  background: var(--fill-light);
  padding: var(--space-4);
  border-radius: var(--radius-md);
  margin-bottom: var(--space-6);
  border-left: 3px solid var(--primary-500);
}

.article-summary p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.8;
}

.article-content {
  font-size: 16px;
  line-height: 1.8;
  color: var(--text-primary);
}

.article-content :deep(h1),
.article-content :deep(h2),
.article-content :deep(h3) {
  margin: var(--space-6) 0 var(--space-3);
  color: var(--text-primary);
}

.article-content :deep(p) {
  margin: 0 0 var(--space-4);
}

.article-content :deep(img) {
  max-width: 100%;
  border-radius: var(--radius-md);
  margin: var(--space-4) 0;
}

.attachment-section {
  margin-top: var(--space-8);
  padding-top: var(--space-6);
  border-top: 1px solid var(--border-lighter);
}

.attachment-title {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 var(--space-4);
}

.attachment-title svg {
  color: var(--primary-500);
}

.attachment-actions {
  display: flex;
  gap: var(--space-3);
}

.preview-btn,
.download-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  background: var(--primary-50);
  color: var(--primary-600);
  border-radius: var(--radius-md);
  border: none;
  text-decoration: none;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.preview-btn:hover,
.download-btn:hover {
  background: var(--primary-100);
  color: var(--primary-700);
}

.pdf-preview-container {
  margin-top: var(--space-4);
  border: 1px solid var(--border-lighter);
  border-radius: var(--radius-md);
  overflow: hidden;
  background: var(--bg-secondary);
}

.pdf-preview-frame {
  width: 100%;
  height: 600px;
  border: none;
}

.pdf-preview-actions {
  display: flex;
  justify-content: center;
  padding: var(--space-3);
  border-top: 1px solid var(--border-lighter);
  background: var(--bg-card);
}

.pdf-action-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  background: transparent;
  color: var(--text-secondary);
  border: 1px solid var(--border-lighter);
  border-radius: var(--radius-md);
  font-size: 13px;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.pdf-action-btn:hover {
  border-color: var(--primary-500);
  color: var(--primary-500);
  background: var(--primary-50);
}

.loading-state,
.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-4);
  padding: var(--space-12);
  color: var(--text-tertiary);
}

.error-state svg {
  opacity: 0.3;
}

.btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-4);
  font-size: 14px;
  font-weight: 500;
  border-radius: var(--radius-md);
  border: 1px solid transparent;
  cursor: pointer;
  text-decoration: none;
}

.btn-primary {
  background: var(--primary-500);
  color: white;
  border-color: var(--primary-500);
}

.btn-primary:hover {
  background: var(--primary-600);
}

@media (max-width: 768px) {
  .article-detail {
    padding: var(--space-4);
  }

  .article-title {
    font-size: 22px;
  }

  .attachment-actions {
    flex-direction: column;
  }

  .pdf-preview-frame {
    height: 400px;
  }
}
</style>