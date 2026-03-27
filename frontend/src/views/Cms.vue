<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">文章管理</h1>
      <div class="header-actions">
        <button class="btn btn-secondary" @click="showCategoryManager = true">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M4 6h16M4 12h16M4 18h16"/>
          </svg>
          栏目管理
        </button>
        <button class="btn btn-primary" @click="openArticleEditor()">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="12" y1="5" x2="12" y2="19"/>
            <line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
          发布文章
        </button>
      </div>
    </div>

    <!-- 分类导航 -->
    <div class="category-nav">
      <button
        v-for="cat in categories"
        :key="cat.id"
        class="category-btn"
        :class="{ active: selectedCategory === cat.id }"
        @click="selectCategory(cat.id)"
      >
        {{ cat.name }}
        <span class="category-count" v-if="cat.count">{{ cat.count }}</span>
      </button>
    </div>

    <!-- 文章列表 -->
    <div class="content-card">
      <div v-if="loading" class="loading-state">
        <div class="loading-spinner"></div>
      </div>

      <div v-else class="articles-list">
        <div v-for="article in articles" :key="article.id" class="article-item">
          <div class="article-info" @click="viewArticle(article)">
            <div class="article-header">
              <h3 class="article-title">{{ article.title }}</h3>
              <span :class="['status-tag', article.status]">
                {{ article.status === 'published' ? '已发布' : '草稿' }}
              </span>
            </div>
            <div class="article-meta">
              <span class="category-tag">{{ getCategoryName(article.category_id) }}</span>
              <span>{{ formatDate(article.created_at) }}</span>
              <span v-if="article.view_count">阅读 {{ article.view_count }}</span>
            </div>
          </div>
          <div class="article-actions">
            <button class="btn-icon" @click="openArticleEditor(article)" title="编辑">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
              </svg>
            </button>
            <button class="btn-icon danger" @click="deleteArticle(article)" title="删除">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="3 6 5 6 21 6"/>
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
              </svg>
            </button>
          </div>
        </div>

        <div v-if="articles.length === 0" class="empty-state">
          <svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
            <line x1="16" y1="13" x2="8" y2="13"/>
            <line x1="16" y1="17" x2="8" y2="17"/>
          </svg>
          <span>暂无文章</span>
          <button class="btn btn-primary" @click="openArticleEditor()">发布第一篇文章</button>
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

    <!-- 文章编辑弹窗 -->
    <div class="modal-overlay" v-if="showArticleEditor" @click.self="closeArticleEditor">
      <div class="modal-content article-editor">
        <div class="modal-header">
          <h2>{{ editingArticle ? '编辑文章' : '发布文章' }}</h2>
          <button class="btn-close" @click="closeArticleEditor">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"/>
              <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label class="form-label">文章标题 *</label>
            <input v-model="articleForm.title" type="text" class="form-input" placeholder="请输入文章标题" />
          </div>
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">所属栏目 *</label>
              <select v-model="articleForm.category_id" class="form-select">
                <option value="">请选择栏目</option>
                <option v-for="cat in categoryList" :key="cat.id" :value="cat.id">{{ cat.name }}</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">发布状态</label>
              <select v-model="articleForm.status" class="form-select">
                <option value="draft">草稿</option>
                <option value="published">发布</option>
              </select>
            </div>
          </div>
          <div class="form-group">
            <label class="form-label">文章摘要</label>
            <textarea v-model="articleForm.summary" class="form-textarea" rows="2" placeholder="请输入文章摘要（选填）"></textarea>
          </div>
          <div class="form-group">
            <label class="form-label">文章内容 *</label>
            <textarea v-model="articleForm.content" class="form-textarea content-editor" rows="12" placeholder="请输入文章内容"></textarea>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" @click="closeArticleEditor">取消</button>
          <button class="btn btn-primary" @click="saveArticle" :disabled="saving">
            {{ saving ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 栏目管理弹窗 -->
    <div class="modal-overlay" v-if="showCategoryManager" @click.self="showCategoryManager = false">
      <div class="modal-content category-manager">
        <div class="modal-header">
          <h2>栏目管理</h2>
          <button class="btn-close" @click="showCategoryManager = false">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"/>
              <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
        <div class="modal-body">
          <!-- 添加栏目 -->
          <div class="add-category">
            <input v-model="newCategoryName" type="text" class="form-input" placeholder="输入新栏目名称" @keyup.enter="addCategory" />
            <button class="btn btn-primary" @click="addCategory" :disabled="!newCategoryName.trim()">添加</button>
          </div>
          <!-- 栏目列表 -->
          <div class="category-list">
            <div v-for="cat in categoryList" :key="cat.id" class="category-item">
              <div class="category-info">
                <span class="category-name">{{ cat.name }}</span>
                <span class="category-slug">{{ cat.slug }}</span>
              </div>
              <div class="category-actions">
                <button class="btn-icon" @click="editCategory(cat)" title="编辑">
                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                  </svg>
                </button>
                <button class="btn-icon danger" @click="deleteCategory(cat)" title="删除">
                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="3 6 5 6 21 6"/>
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 栏目编辑弹窗 -->
    <div class="modal-overlay" v-if="showCategoryEditor" @click.self="showCategoryEditor = false">
      <div class="modal-content category-editor">
        <div class="modal-header">
          <h2>编辑栏目</h2>
          <button class="btn-close" @click="showCategoryEditor = false">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"/>
              <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label class="form-label">栏目名称</label>
            <input v-model="editingCategory.name" type="text" class="form-input" />
          </div>
          <div class="form-group">
            <label class="form-label">栏目描述</label>
            <textarea v-model="editingCategory.description" class="form-textarea" rows="2"></textarea>
          </div>
          <div class="form-group">
            <label class="form-label">排序</label>
            <input v-model.number="editingCategory.order" type="number" class="form-input" />
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" @click="showCategoryEditor = false">取消</button>
          <button class="btn btn-primary" @click="updateCategory">保存</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import axios from 'axios'

// 数据
const categories = ref([{ id: 'all', name: '全部' }])
const categoryList = ref([])
const articles = ref([])
const loading = ref(false)
const saving = ref(false)
const currentPage = ref(1)
const pageSize = 10
const totalArticles = ref(0)
const totalPages = ref(1)
const selectedCategory = ref('all')

// 文章编辑
const showArticleEditor = ref(false)
const editingArticle = ref(null)
const articleForm = ref({
  title: '',
  category_id: '',
  status: 'draft',
  summary: '',
  content: ''
})

// 栏目管理
const showCategoryManager = ref(false)
const showCategoryEditor = ref(false)
const newCategoryName = ref('')
const editingCategory = ref({})

// 方法
function formatDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString('zh-CN')
}

function getCategoryName(categoryId) {
  const cat = categoryList.value.find(c => c.id === categoryId)
  return cat ? cat.name : '未分类'
}

async function fetchCategories() {
  try {
    const response = await axios.get('/api/categories')
    categoryList.value = response.data.categories || []
    categories.value = [
      { id: 'all', name: '全部' },
      ...categoryList.value.map(c => ({ id: c.id, name: c.name }))
    ]
  } catch (error) {
    console.error('获取栏目失败:', error)
  }
}

async function fetchArticles() {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      per_page: pageSize,
      include_drafts: 'true'
    }
    if (selectedCategory.value !== 'all') {
      params.category_id = selectedCategory.value
    }
    const response = await axios.get('/api/articles', { params })
    articles.value = response.data.articles || []
    totalArticles.value = response.data.total || 0
    totalPages.value = Math.ceil(totalArticles.value / pageSize) || 1
  } catch (error) {
    console.error('获取文章列表失败:', error)
  } finally {
    loading.value = false
  }
}

function selectCategory(categoryId) {
  selectedCategory.value = categoryId
  currentPage.value = 1
  fetchArticles()
}

// 文章操作
function openArticleEditor(article = null) {
  editingArticle.value = article
  if (article) {
    articleForm.value = {
      title: article.title,
      category_id: article.category_id,
      status: article.status,
      summary: article.summary || '',
      content: article.content || ''
    }
  } else {
    articleForm.value = {
      title: '',
      category_id: '',
      status: 'draft',
      summary: '',
      content: ''
    }
  }
  showArticleEditor.value = true
}

function closeArticleEditor() {
  showArticleEditor.value = false
  editingArticle.value = null
}

async function saveArticle() {
  if (!articleForm.value.title.trim()) {
    alert('请输入文章标题')
    return
  }
  if (!articleForm.value.category_id) {
    alert('请选择所属栏目')
    return
  }
  if (!articleForm.value.content.trim()) {
    alert('请输入文章内容')
    return
  }

  saving.value = true
  try {
    if (editingArticle.value) {
      await axios.put(`/api/articles/${editingArticle.value.id}`, articleForm.value)
    } else {
      await axios.post('/api/articles', articleForm.value)
    }
    closeArticleEditor()
    fetchArticles()
  } catch (error) {
    console.error('保存文章失败:', error)
    alert(error.response?.data?.error || '保存失败')
  } finally {
    saving.value = false
  }
}

function viewArticle(article) {
  // 可以跳转到文章详情页或打开预览
  console.log('查看文章:', article)
}

async function deleteArticle(article) {
  if (!confirm(`确定删除文章「${article.title}」？`)) return

  try {
    await axios.delete(`/api/articles/${article.id}`)
    fetchArticles()
  } catch (error) {
    console.error('删除文章失败:', error)
    alert(error.response?.data?.error || '删除失败')
  }
}

// 栏目操作
async function addCategory() {
  if (!newCategoryName.value.trim()) return

  try {
    await axios.post('/api/categories', { name: newCategoryName.value.trim() })
    newCategoryName.value = ''
    fetchCategories()
  } catch (error) {
    console.error('添加栏目失败:', error)
    alert(error.response?.data?.error || '添加失败')
  }
}

function editCategory(category) {
  editingCategory.value = { ...category }
  showCategoryEditor.value = true
}

async function updateCategory() {
  try {
    await axios.put(`/api/categories/${editingCategory.value.id}`, {
      name: editingCategory.value.name,
      description: editingCategory.value.description,
      order: editingCategory.value.order
    })
    showCategoryEditor.value = false
    fetchCategories()
  } catch (error) {
    console.error('更新栏目失败:', error)
    alert(error.response?.data?.error || '更新失败')
  }
}

async function deleteCategory(category) {
  if (!confirm(`确定删除栏目「${category.name}」？\n注意：该栏目下有文章时无法删除。`)) return

  try {
    await axios.delete(`/api/categories/${category.id}`)
    fetchCategories()
  } catch (error) {
    console.error('删除栏目失败:', error)
    alert(error.response?.data?.error || '删除失败')
  }
}

watch(currentPage, fetchArticles)

onMounted(() => {
  fetchCategories()
  fetchArticles()
})
</script>

<style scoped>
.page-container {
  padding: var(--space-6);
  max-width: 1400px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-6);
}

.page-title {
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.header-actions {
  display: flex;
  gap: var(--space-3);
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
  transition: all var(--transition-fast);
}

.btn-primary {
  background: var(--primary-500);
  color: white;
  border-color: var(--primary-500);
}

.btn-primary:hover { background: var(--primary-600); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-secondary {
  background: var(--bg-card);
  color: var(--text-primary);
  border-color: var(--border-lighter);
}

.btn-secondary:hover { border-color: var(--primary-300); }

.btn-icon {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: 1px solid var(--border-lighter);
  border-radius: var(--radius-md);
  color: var(--text-tertiary);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.btn-icon:hover {
  border-color: var(--primary-300);
  color: var(--primary-500);
  background: var(--primary-50);
}

.btn-icon.danger:hover {
  border-color: var(--danger-light);
  color: var(--danger);
  background: rgba(245, 108, 108, 0.1);
}

.category-nav {
  display: flex;
  gap: var(--space-2);
  margin-bottom: var(--space-4);
  flex-wrap: wrap;
}

.category-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-4);
  font-size: 14px;
  color: var(--text-secondary);
  background: var(--bg-card);
  border: 1px solid var(--border-lighter);
  border-radius: var(--radius-full);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.category-btn:hover { border-color: var(--primary-300); }
.category-btn.active {
  background: var(--primary-500);
  color: white;
  border-color: var(--primary-500);
}

.category-count {
  padding: 1px 6px;
  font-size: 11px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: var(--radius-full);
}

.category-btn:not(.active) .category-count {
  background: var(--neutral-100);
}

.content-card {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-lighter);
  padding: var(--space-4);
}

.loading-state {
  display: flex;
  justify-content: center;
  padding: var(--space-8);
}

.articles-list {
  display: flex;
  flex-direction: column;
}

.article-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-4);
  border-bottom: 1px solid var(--border-lighter);
  transition: background var(--transition-fast);
}

.article-item:last-child { border-bottom: none; }
.article-item:hover { background: var(--fill-light); }

.article-info { flex: 1; cursor: pointer; }

.article-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-1);
}

.article-title {
  font-size: 16px;
  font-weight: 500;
  color: var(--text-primary);
  margin: 0;
}

.status-tag {
  padding: 2px 8px;
  font-size: 11px;
  font-weight: 500;
  border-radius: var(--radius-sm);
}

.status-tag.published {
  background: var(--success-light);
  color: var(--success-dark);
}

.status-tag.draft {
  background: var(--neutral-100);
  color: var(--neutral-600);
}

.article-meta {
  display: flex;
  gap: var(--space-3);
  font-size: 13px;
  color: var(--text-tertiary);
}

.category-tag {
  color: var(--primary-500);
}

.article-actions {
  display: flex;
  gap: var(--space-2);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-12);
  color: var(--text-tertiary);
}

.empty-state svg { opacity: 0.3; }

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

.pagination-btn:hover:not(:disabled) { border-color: var(--primary-500); color: var(--primary-500); }
.pagination-btn:disabled { opacity: 0.4; cursor: not-allowed; }

.page-info { color: var(--text-secondary); font-size: 14px; }

/* 弹窗样式 */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  width: 90%;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-xl);
}

.article-editor { max-width: 800px; }
.category-manager { max-width: 500px; }
.category-editor { max-width: 400px; }

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-4) var(--space-6);
  border-bottom: 1px solid var(--border-lighter);
}

.modal-header h2 {
  font-size: 18px;
  font-weight: 600;
  margin: 0;
  color: var(--text-primary);
}

.btn-close {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  color: var(--text-tertiary);
  cursor: pointer;
  border-radius: var(--radius-md);
  transition: all var(--transition-fast);
}

.btn-close:hover {
  background: var(--fill-light);
  color: var(--text-primary);
}

.modal-body {
  flex: 1;
  padding: var(--space-6);
  overflow-y: auto;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-3);
  padding: var(--space-4) var(--space-6);
  border-top: 1px solid var(--border-lighter);
}

.form-group {
  margin-bottom: var(--space-4);
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-4);
}

.form-label {
  display: block;
  margin-bottom: var(--space-2);
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

.form-input,
.form-select,
.form-textarea {
  width: 100%;
  padding: var(--space-2) var(--space-3);
  font-size: 14px;
  color: var(--text-primary);
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  transition: all var(--transition-fast);
}

.form-input:focus,
.form-select:focus,
.form-textarea:focus {
  outline: none;
  border-color: var(--primary-500);
  box-shadow: 0 0 0 3px var(--primary-100);
}

.form-textarea {
  resize: vertical;
  min-height: 80px;
}

.content-editor {
  font-family: var(--font-mono);
  line-height: 1.6;
}

/* 栏目管理 */
.add-category {
  display: flex;
  gap: var(--space-2);
  margin-bottom: var(--space-4);
  padding-bottom: var(--space-4);
  border-bottom: 1px solid var(--border-lighter);
}

.add-category .form-input { flex: 1; }

.category-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.category-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-3);
  background: var(--fill-light);
  border-radius: var(--radius-md);
}

.category-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.category-name {
  font-weight: 500;
  color: var(--text-primary);
}

.category-slug {
  font-size: 12px;
  color: var(--text-tertiary);
}

.category-actions {
  display: flex;
  gap: var(--space-1);
}

@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
    gap: var(--space-4);
    align-items: flex-start;
  }

  .form-row {
    grid-template-columns: 1fr;
  }
}
</style>