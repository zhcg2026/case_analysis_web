<template>
  <div class="page-container">
    <div class="page-header">
      <router-link to="/" class="back-link">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="15 18 9 12 15 6"/>
        </svg>
        返回首页
      </router-link>
      <h1 class="page-title">{{ categoryName }}</h1>
    </div>

    <div class="content-card" v-if="!loading">
      <div class="articles-list">
        <div
          v-for="article in articles"
          :key="article.id"
          class="article-item"
          @click="viewArticle(article)"
        >
          <div class="article-info">
            <h3 class="article-title">{{ article.title }}</h3>
            <p class="article-summary" v-if="article.summary">{{ article.summary }}</p>
            <div class="article-meta">
              <span>{{ formatDate(article.created_at) }}</span>
              <span v-if="article.view_count">{{ article.view_count }} 次阅读</span>
            </div>
          </div>
        </div>

        <div v-if="articles.length === 0" class="empty-state">
          <svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
            <line x1="16" y1="13" x2="8" y2="13"/>
            <line x1="16" y1="17" x2="8" y2="17"/>
          </svg>
          <span>该栏目暂无文章</span>
        </div>
      </div>

      <!-- 分页 -->
      <div class="pagination" v-if="totalPages > 1">
        <button class="pagination-btn" :disabled="currentPage === 1" @click="currentPage--">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="15 18 9 12 15 6"/>
          </svg>
        </button>
        <span class="page-info">{{ currentPage }} / {{ totalPages }}</span>
        <button class="pagination-btn" :disabled="currentPage === totalPages" @click="currentPage++">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="9 18 15 12 9 6"/>
          </svg>
        </button>
      </div>
    </div>

    <div class="loading-state" v-else>
      <div class="loading-spinner"></div>
      <span>加载中...</span>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'

const route = useRoute()
const router = useRouter()

const articles = ref([])
const loading = ref(true)
const categoryName = ref('')
const currentPage = ref(1)
const totalPages = ref(1)
const pageSize = 15

async function fetchCategory() {
  const categoryId = route.params.id
  if (!categoryId) return

  try {
    const response = await axios.get('/api/categories')
    const cat = response.data.categories?.find(c => c.id === parseInt(categoryId))
    categoryName.value = cat?.name || '文章列表'
  } catch (error) {
    console.error('获取栏目信息失败:', error)
  }
}

async function fetchArticles() {
  const categoryId = route.params.id
  if (!categoryId) return

  loading.value = true
  try {
    const response = await axios.get('/api/articles', {
      params: {
        category_id: categoryId,
        page: currentPage.value,
        per_page: pageSize
      }
    })
    articles.value = response.data.articles || []
    const total = response.data.total || 0
    totalPages.value = Math.ceil(total / pageSize) || 1
  } catch (error) {
    console.error('获取文章列表失败:', error)
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

function viewArticle(article) {
  router.push(`/article/${article.id}`)
}

watch(() => route.params.id, () => {
  currentPage.value = 1
  fetchCategory()
  fetchArticles()
})

watch(currentPage, fetchArticles)

onMounted(() => {
  fetchCategory()
  fetchArticles()
})
</script>

<style scoped>
.page-container {
  padding: var(--space-6);
  max-width: 1000px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: var(--space-6);
}

.back-link {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  color: var(--primary-500);
  text-decoration: none;
  font-size: 14px;
  margin-bottom: var(--space-3);
}

.back-link:hover {
  color: var(--primary-600);
}

.page-title {
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.content-card {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-lighter);
  padding: var(--space-4);
}

.articles-list {
  display: flex;
  flex-direction: column;
}

.article-item {
  padding: var(--space-4);
  border-bottom: 1px solid var(--border-lighter);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.article-item:last-child {
  border-bottom: none;
}

.article-item:hover {
  background: var(--fill-light);
}

.article-info {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.article-title {
  font-size: 16px;
  font-weight: 500;
  color: var(--text-primary);
  margin: 0;
}

.article-summary {
  font-size: 14px;
  color: var(--text-tertiary);
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.article-meta {
  display: flex;
  gap: var(--space-4);
  font-size: 13px;
  color: var(--text-tertiary);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-12);
  color: var(--text-tertiary);
}

.empty-state svg {
  opacity: 0.3;
}

.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  margin-top: var(--space-4);
  padding-top: var(--space-4);
  border-top: 1px solid var(--border-lighter);
}

.pagination-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.pagination-btn:hover:not(:disabled) {
  border-color: var(--primary-500);
  color: var(--primary-500);
}

.pagination-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.page-info {
  color: var(--text-secondary);
  font-size: 14px;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  padding: var(--space-12);
  color: var(--text-tertiary);
}
</style>