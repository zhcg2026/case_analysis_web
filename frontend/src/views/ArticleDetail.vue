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
  // 简单的换行处理，后续可以用富文本编辑器
  return article.value.content.replace(/\n/g, '<br>')
})

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
}
</style>