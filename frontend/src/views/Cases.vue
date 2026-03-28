<template>
  <div class="page-container">
    <h1 class="page-title">案件管理</h1>

    <!-- 顶部统计卡片 -->
    <div class="stats-row">
      <div class="stat-card" :class="{ active: !filterCategory }" @click="switchCategory('')">
        <span class="stat-value">{{ stats.total }}</span>
        <span class="stat-label">全部案件</span>
      </div>
      <div class="stat-card" :class="{ active: filterCategory === '非我局管辖' }" @click="switchCategory('非我局管辖')">
        <span class="stat-value">{{ stats.non_jurisdiction }}</span>
        <span class="stat-label">非我局管辖</span>
      </div>
      <div class="stat-card" :class="{ active: filterCategory === '挂账案件' }" @click="switchCategory('挂账案件')">
        <span class="stat-value">{{ stats.pending }}<span v-if="stats.expiring_soon > 0" class="expiring-badge">!{{ stats.expiring_soon }}</span></span>
        <span class="stat-label">挂账案件</span>
      </div>
      <div class="stat-card" :class="{ active: filterCategory === '疑难案件' }" @click="switchCategory('疑难案件')">
        <span class="stat-value">{{ stats.difficult }}</span>
        <span class="stat-label">疑难案件</span>
      </div>
    </div>

    <!-- 操作栏 -->
    <div class="action-bar">
      <div class="search-box">
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8"></circle>
          <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
        </svg>
        <input v-model="searchText" type="text" placeholder="搜索任务号、问题描述、地址..." class="search-input" @keyup.enter="searchCases" />
        <select v-model="filterStatus" class="status-select" @change="searchCases">
          <option value="">全部状态</option>
          <option value="跟进中">跟进中</option>
          <option value="已结案">已结案</option>
        </select>
        <button class="btn-search" @click="searchCases">搜索</button>
      </div>
      <div class="action-buttons">
        <button class="btn btn-primary" @click="showImport = true">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
          导入
        </button>
      </div>
    </div>

    <!-- 案件列表 -->
    <div class="content-card" v-if="!showDetail">
      <div v-if="loading" class="loading-state">
        <div class="loading-spinner"></div>
        <span>加载中...</span>
      </div>

      <div v-else-if="cases.length === 0" class="empty-state">
        <div class="empty-icon">📭</div>
        <p>暂无案件数据</p>
      </div>

      <div v-else class="table-container">
        <!-- 批量操作栏 -->
        <div v-if="selectedIds.length > 0" class="batch-actions">
          <span class="selected-count">已选择 {{ selectedIds.length }} 项</span>
          <button class="btn btn-sm btn-primary" @click="showBatchCategory = true">批量分类</button>
          <button class="btn btn-sm btn-danger" @click="showBatchDelete = true">批量删除</button>
          <button class="btn btn-sm btn-secondary" @click="selectedIds = []">取消选择</button>
        </div>

        <table class="data-table">
          <thead>
            <tr>
              <th class="checkbox-col">
                <input type="checkbox" :checked="isAllSelected" @change="toggleSelectAll" />
              </th>
              <th>任务号</th>
              <th>上报时间</th>
              <th>问题描述</th>
              <th>分类</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(caseItem, index) in cases" :key="caseItem.id" :class="{ selected: selectedIds.includes(caseItem.id) }" @click="viewDetail(caseItem.id)">
              <td class="checkbox-col" @click.stop>
                <input type="checkbox" :checked="selectedIds.includes(caseItem.id)" @change="toggleSelection(caseItem.id)" />
              </td>
              <td class="task-number">{{ caseItem.task_number }}</td>
              <td class="report-time">{{ caseItem.report_time || '-' }}</td>
              <td class="problem-desc">{{ caseItem.problem_desc || '-' }}</td>
              <td>
                <span v-if="caseItem.category === '非我局管辖'" class="category-badge non-jurisdiction">非我局</span>
                <span v-else-if="caseItem.category === '挂账案件'" class="category-badge pending">挂账</span>
                <span v-else-if="caseItem.category === '疑难案件'" class="category-badge difficult">疑难</span>
                <span v-else class="category-badge none">未分类</span>
              </td>
              <td>
                <span :class="['status-badge', caseItem.status === '已结案' ? 'closed' : 'following']">
                  {{ caseItem.status || '跟进中' }}
                </span>
              </td>
              <td>
                <button class="btn-text" @click.stop="viewDetail(caseItem.id)">查看</button>
              </td>
            </tr>
          </tbody>
        </table>

        <!-- 分页 -->
        <div class="pagination" v-if="totalPages > 1">
          <button class="pagination-btn" :disabled="currentPage === 1" @click="changePage(currentPage - 1)">上一页</button>
          <span class="page-info">第 {{ currentPage }} / {{ totalPages }} 页</span>
          <button class="pagination-btn" :disabled="currentPage === totalPages" @click="changePage(currentPage + 1)">下一页</button>
        </div>
      </div>
    </div>

    <!-- 案件详情 -->
    <div class="detail-card" v-if="showDetail && currentCase">
      <div class="detail-header">
        <div class="header-info">
          <h3 class="case-title">{{ currentCase.task_number }}</h3>
          <div class="case-tags">
            <span v-if="currentCase.category" :class="['category-tag', getCategoryClass(currentCase.category)]">
              {{ currentCase.category }}
            </span>
            <span :class="['status-tag', currentCase.status === '已结案' ? 'closed' : 'following']">
              {{ currentCase.status || '跟进中' }}
            </span>
            <span v-if="currentCase.follow_count" class="follow-count">已跟进 {{ currentCase.follow_count }} 次</span>
          </div>
        </div>
        <div class="header-actions">
          <button class="btn btn-secondary" @click="showCategoryModal = true">分类</button>
          <button class="btn btn-secondary" @click="showFollowModal = true">跟进</button>
          <button v-if="currentCase.status !== '已结案'" class="btn btn-secondary" @click="showCloseModal = true">结案</button>
          <button class="btn btn-secondary danger" @click="showDeleteModal = true">删除</button>
          <button class="btn btn-primary" @click="closeDetail">返回</button>
        </div>
      </div>

      <div class="detail-body">
        <!-- 左侧：基本信息 -->
        <div class="detail-left">
          <div class="info-section">
            <h4 class="section-title">基本信息</h4>
            <div class="info-grid">
              <div class="info-item">
                <span class="info-label">上报时间</span>
                <span class="info-value">{{ currentCase.report_time || '-' }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">问题来源</span>
                <span class="info-value">{{ currentCase.source || '-' }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">责属区域</span>
                <span class="info-value">{{ currentCase.responsible_area_name || '-' }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">最近跟进</span>
                <span class="info-value">{{ currentCase.last_follow_time || '-' }}</span>
              </div>
            </div>
          </div>

          <div class="info-section">
            <h4 class="section-title">问题描述</h4>
            <p class="info-text">{{ currentCase.problem_desc || '-' }}</p>
          </div>

          <div class="info-section">
            <h4 class="section-title">地址</h4>
            <p class="info-text">{{ currentCase.address_desc || '-' }}</p>
          </div>

          <!-- 非我局管辖信息 -->
          <div v-if="currentCase.category === '非我局管辖'" class="info-section category-info non-jurisdiction">
            <h4 class="section-title">权属信息</h4>
            <div class="info-grid">
              <div class="info-item">
                <span class="info-label">权属单位</span>
                <span class="info-value">{{ currentCase.owner_unit || '-' }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">联系人</span>
                <span class="info-value">{{ currentCase.contact_person || '-' }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">联系电话</span>
                <span class="info-value">{{ currentCase.contact_phone || '-' }}</span>
              </div>
            </div>
          </div>

          <!-- 挂账案件信息 -->
          <div v-if="currentCase.category === '挂账案件'" class="info-section category-info pending">
            <h4 class="section-title">挂账信息</h4>
            <div class="info-grid">
              <div class="info-item">
                <span class="info-label">挂账原因</span>
                <span class="info-value">{{ currentCase.pending_reason || '-' }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">预计处置时间</span>
                <span class="info-value">{{ currentCase.pending_deadline || '-' }}</span>
              </div>
            </div>
          </div>

          <!-- 疑难案件信息 -->
          <div v-if="currentCase.category === '疑难案件'" class="info-section category-info difficult">
            <h4 class="section-title">疑难信息</h4>
            <div class="info-item">
              <span class="info-label">疑难类型</span>
              <span class="info-value">{{ currentCase.difficult_type || '-' }}</span>
            </div>
          </div>

          <!-- 结案信息 -->
          <div v-if="currentCase.status === '已结案'" class="info-section category-info closed">
            <h4 class="section-title">结案信息</h4>
            <div class="info-grid">
              <div class="info-item">
                <span class="info-label">结案时间</span>
                <span class="info-value">{{ currentCase.close_time || '-' }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">结案说明</span>
                <span class="info-value">{{ currentCase.close_remark || '-' }}</span>
              </div>
            </div>
          </div>

          <!-- 照片展示 -->
          <div v-if="currentCase.photo_path" class="info-section">
            <h4 class="section-title">案件照片</h4>
            <div class="photo-grid">
              <img v-for="(photo, index) in getPhotoPaths(currentCase.photo_path)" :key="index" :src="photo" :alt="'照片' + (index + 1)" class="photo-item" @click="previewImage(photo)" />
            </div>
          </div>
        </div>

        <!-- 右侧：跟进记录 -->
        <div class="detail-right">
          <h4 class="section-title">
            跟进记录
            <span class="follow-total">（共 {{ follows.length }} 条）</span>
          </h4>

          <div v-if="follows.length === 0" class="empty-follows">
            <div class="empty-icon">📭</div>
            <p>暂无跟进记录</p>
            <button class="btn btn-info" @click="showFollowModal = true">添加跟进</button>
          </div>

          <div v-else class="follow-timeline">
            <div v-for="(follow, index) in follows" :key="follow.id" class="follow-item">
              <div class="timeline-dot"></div>
              <div v-if="index < follows.length - 1" class="timeline-line"></div>
              <div class="follow-card">
                <div class="follow-header">
                  <span class="follow-type">{{ follow.follow_type }}</span>
                  <span class="follow-time">{{ follow.follow_time }}</span>
                </div>
                <p class="follow-content">{{ follow.content }}</p>
                <p v-if="follow.follow_user" class="follow-user">跟进人：{{ follow.follow_user }}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 分类弹窗 -->
    <div v-if="showCategoryModal" class="modal-overlay" @click="showCategoryModal = false">
      <div class="modal-content" @click.stop>
        <h3 class="modal-title">设置案件分类</h3>
        <div class="form-group">
          <label class="form-label">案件分类</label>
          <select v-model="categoryForm.category" class="form-select">
            <option value="">请选择分类</option>
            <option value="非我局管辖">非我局管辖</option>
            <option value="挂账案件">挂账案件</option>
            <option value="疑难案件">疑难案件</option>
          </select>
        </div>

        <!-- 非我局管辖 -->
        <template v-if="categoryForm.category === '非我局管辖'">
          <div class="form-group">
            <label class="form-label">权属单位</label>
            <input v-model="categoryForm.owner_unit" class="form-input" placeholder="请输入权属单位" />
          </div>
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">联系人</label>
              <input v-model="categoryForm.contact_person" class="form-input" />
            </div>
            <div class="form-group">
              <label class="form-label">联系电话</label>
              <input v-model="categoryForm.contact_phone" class="form-input" />
            </div>
          </div>
        </template>

        <!-- 挂账案件 -->
        <template v-if="categoryForm.category === '挂账案件'">
          <div class="form-group">
            <label class="form-label">挂账原因</label>
            <textarea v-model="categoryForm.pending_reason" class="form-textarea" rows="3" placeholder="请输入挂账原因"></textarea>
          </div>
          <div class="form-group">
            <label class="form-label">预计处置时间</label>
            <input v-model="categoryForm.pending_deadline" type="date" class="form-input" />
          </div>
        </template>

        <!-- 疑难案件 -->
        <template v-if="categoryForm.category === '疑难案件'">
          <div class="form-group">
            <label class="form-label">疑难类型</label>
            <select v-model="categoryForm.difficult_type" class="form-select">
              <option value="">请选择</option>
              <option value="建筑垃圾">建筑垃圾</option>
              <option value="自建房">自建房</option>
              <option value="违建">违建</option>
              <option value="其他">其他</option>
            </select>
          </div>
        </template>

        <div class="modal-actions">
          <button class="btn btn-secondary" @click="showCategoryModal = false">取消</button>
          <button class="btn btn-primary" @click="updateCategory">保存</button>
        </div>
      </div>
    </div>

    <!-- 批量分类弹窗 -->
    <div v-if="showBatchCategory" class="modal-overlay" @click="showBatchCategory = false">
      <div class="modal-content" @click.stop>
        <h3 class="modal-title">批量设置分类</h3>
        <p class="modal-desc">已选择 {{ selectedIds.length }} 条案件</p>
        <div class="form-group">
          <label class="form-label">案件分类</label>
          <select v-model="batchCategoryForm.category" class="form-select">
            <option value="">请选择分类</option>
            <option value="非我局管辖">非我局管辖</option>
            <option value="挂账案件">挂账案件</option>
            <option value="疑难案件">疑难案件</option>
          </select>
        </div>

        <template v-if="batchCategoryForm.category === '非我局管辖'">
          <div class="form-group">
            <label class="form-label">权属单位</label>
            <input v-model="batchCategoryForm.owner_unit" class="form-input" placeholder="请输入权属单位" />
          </div>
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">联系人</label>
              <input v-model="batchCategoryForm.contact_person" class="form-input" />
            </div>
            <div class="form-group">
              <label class="form-label">联系电话</label>
              <input v-model="batchCategoryForm.contact_phone" class="form-input" />
            </div>
          </div>
        </template>

        <template v-if="batchCategoryForm.category === '挂账案件'">
          <div class="form-group">
            <label class="form-label">挂账原因</label>
            <textarea v-model="batchCategoryForm.pending_reason" class="form-textarea" rows="3" placeholder="请输入挂账原因"></textarea>
          </div>
          <div class="form-group">
            <label class="form-label">预计处置时间</label>
            <input v-model="batchCategoryForm.pending_deadline" type="date" class="form-input" />
          </div>
        </template>

        <template v-if="batchCategoryForm.category === '疑难案件'">
          <div class="form-group">
            <label class="form-label">疑难类型</label>
            <select v-model="batchCategoryForm.difficult_type" class="form-select">
              <option value="">请选择</option>
              <option value="建筑垃圾">建筑垃圾</option>
              <option value="自建房">自建房</option>
              <option value="违建">违建</option>
              <option value="其他">其他</option>
            </select>
          </div>
        </template>

        <div class="modal-actions">
          <button class="btn btn-secondary" @click="showBatchCategory = false">取消</button>
          <button class="btn btn-primary" @click="batchUpdateCategory">批量保存</button>
        </div>
      </div>
    </div>

    <!-- 跟进弹窗 -->
    <div v-if="showFollowModal" class="modal-overlay" @click="showFollowModal = false">
      <div class="modal-content" @click.stop>
        <h3 class="modal-title">添加跟进记录</h3>
        <div class="form-group">
          <label class="form-label">跟进类型</label>
          <select v-model="followForm.follow_type" class="form-select">
            <option value="发函">发函</option>
            <option value="协调">协调</option>
            <option value="督办">督办</option>
            <option value="其他">其他</option>
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">跟进内容</label>
          <textarea v-model="followForm.content" class="form-textarea" rows="4" placeholder="请输入跟进内容"></textarea>
        </div>
        <div class="form-group">
          <label class="form-label">跟进人</label>
          <input v-model="followForm.follow_user" class="form-input" placeholder="请输入跟进人姓名" />
        </div>
        <div class="modal-actions">
          <button class="btn btn-secondary" @click="showFollowModal = false">取消</button>
          <button class="btn btn-primary" @click="addFollow">保存</button>
        </div>
      </div>
    </div>

    <!-- 结案弹窗 -->
    <div v-if="showCloseModal" class="modal-overlay" @click="showCloseModal = false">
      <div class="modal-content" @click.stop>
        <h3 class="modal-title">结案确认</h3>
        <div class="form-group">
          <label class="form-label">结案说明</label>
          <textarea v-model="closeRemark" class="form-textarea" rows="3" placeholder="请输入结案说明（可选）"></textarea>
        </div>
        <div class="modal-actions">
          <button class="btn btn-secondary" @click="showCloseModal = false">取消</button>
          <button class="btn btn-success" @click="closeCase">确认结案</button>
        </div>
      </div>
    </div>

    <!-- 删除确认弹窗 -->
    <div v-if="showDeleteModal" class="modal-overlay" @click="showDeleteModal = false">
      <div class="modal-content" @click.stop>
        <h3 class="modal-title danger">删除确认</h3>
        <p class="modal-desc">确定要删除案件 <strong>{{ currentCase?.task_number }}</strong> 吗？</p>
        <p class="modal-warning">此操作不可恢复。</p>
        <div class="modal-actions">
          <button class="btn btn-secondary" @click="showDeleteModal = false">取消</button>
          <button class="btn btn-danger" @click="deleteCase">确认删除</button>
        </div>
      </div>
    </div>

    <!-- 批量删除确认弹窗 -->
    <div v-if="showBatchDelete" class="modal-overlay" @click="showBatchDelete = false">
      <div class="modal-content" @click.stop>
        <h3 class="modal-title danger">批量删除确认</h3>
        <p class="modal-desc">确定要删除选中的 <strong class="danger">{{ selectedIds.length }}</strong> 条案件吗？</p>
        <p class="modal-warning">此操作不可恢复。</p>
        <div class="modal-actions">
          <button class="btn btn-secondary" @click="showBatchDelete = false">取消</button>
          <button class="btn btn-danger" @click="batchDelete">确认删除</button>
        </div>
      </div>
    </div>

    <!-- 图片预览弹窗 -->
    <div v-if="showImagePreview" class="image-preview-overlay" @click="showImagePreview = false">
      <img :src="previewImageUrl" class="preview-image" @click.stop />
      <button class="close-preview" @click="showImagePreview = false">关闭</button>
    </div>

    <!-- 导入弹窗 -->
    <div v-if="showImport" class="modal-overlay" @click="showImport = false">
      <div class="modal-content" @click.stop>
        <h3 class="modal-title">导入案件数据</h3>
        <div class="alert-box">
          上传前需确保Excel表的第一行是字段行（表头行）
        </div>
        <div class="form-group">
          <label class="form-label">选择Excel文件</label>
          <input type="file" accept=".xlsx" @change="handleFileSelect" class="form-file" />
        </div>
        <div v-if="importFile" class="file-info">
          已选择: {{ importFile.name }}
        </div>
        <div v-if="importMessage" class="success-message">{{ importMessage }}</div>
        <div v-if="importError" class="error-message">{{ importError }}</div>
        <div class="modal-actions">
          <button class="btn btn-secondary" @click="showImport = false; importMessage = ''; importError = '';">关闭</button>
          <button class="btn btn-primary" @click="importCases" :disabled="importLoading || !importFile">
            {{ importLoading ? '导入中...' : '开始导入' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import axios from 'axios'

// 列表状态
const cases = ref([])
const stats = ref({ total: 0, non_jurisdiction: 0, pending: 0, difficult: 0, follow_up: 0, closed: 0, expiring_soon: 0 })
const loading = ref(false)
const searchText = ref('')
const filterCategory = ref('')
const filterStatus = ref('')
const currentPage = ref(1)
const pageSize = 20
const totalCases = ref(0)
const selectedIds = ref([])

// 详情状态
const showDetail = ref(false)
const currentCase = ref(null)
const follows = ref([])

// 弹窗状态
const showCategoryModal = ref(false)
const showBatchCategory = ref(false)
const showFollowModal = ref(false)
const showCloseModal = ref(false)
const showDeleteModal = ref(false)
const showBatchDelete = ref(false)
const showImport = ref(false)
const showImagePreview = ref(false)
const previewImageUrl = ref('')

// 表单数据
const categoryForm = ref({ category: '', owner_unit: '', contact_person: '', contact_phone: '', pending_reason: '', pending_deadline: '', difficult_type: '' })
const batchCategoryForm = ref({ category: '', owner_unit: '', contact_person: '', contact_phone: '', pending_reason: '', pending_deadline: '', difficult_type: '' })
const followForm = ref({ follow_type: '其他', content: '', follow_user: '' })
const closeRemark = ref('')

// 导入状态
const importFile = ref(null)
const importLoading = ref(false)
const importMessage = ref('')
const importError = ref('')

const totalPages = computed(() => Math.ceil(totalCases.value / pageSize) || 1)
const isAllSelected = computed(() => cases.value.length > 0 && cases.value.every(c => selectedIds.value.includes(c.id)))

// 获取案件列表
async function fetchCases() {
  loading.value = true
  try {
    const response = await axios.get('/api/cases', {
      params: {
        page: currentPage.value,
        per_page: pageSize,
        search: searchText.value,
        category: filterCategory.value,
        status: filterStatus.value
      }
    })
    cases.value = response.data.cases || []
    totalCases.value = response.data.total || 0
  } catch (error) {
    console.error('获取案件列表失败:', error)
  } finally {
    loading.value = false
  }
}

// 获取统计信息
async function fetchStats() {
  try {
    const response = await axios.get('/api/cases/stats')
    stats.value = response.data || {}
  } catch (error) {
    console.error('获取统计失败:', error)
  }
}

// 获取案件详情
async function fetchCaseDetail(id) {
  try {
    const response = await axios.get(`/api/cases/${id}`)
    currentCase.value = response.data
  } catch (error) {
    console.error('获取案件详情失败:', error)
  }
}

// 获取跟进记录
async function fetchFollows(id) {
  try {
    const response = await axios.get(`/api/cases/${id}/follows`)
    follows.value = response.data.follows || []
  } catch (error) {
    console.error('获取跟进记录失败:', error)
  }
}

// 切换分类
function switchCategory(category) {
  filterCategory.value = category
  currentPage.value = 1
  fetchCases()
}

// 搜索
function searchCases() {
  currentPage.value = 1
  fetchCases()
}

// 翻页
function changePage(page) {
  currentPage.value = page
  fetchCases()
}

// 查看详情
async function viewDetail(id) {
  showDetail.value = true
  await fetchCaseDetail(id)
  await fetchFollows(id)
}

// 关闭详情
function closeDetail() {
  showDetail.value = false
  currentCase.value = null
  follows.value = []
}

// 选择相关
function toggleSelection(id) {
  const index = selectedIds.value.indexOf(id)
  if (index === -1) {
    selectedIds.value.push(id)
  } else {
    selectedIds.value.splice(index, 1)
  }
}

function toggleSelectAll() {
  if (isAllSelected.value) {
    selectedIds.value = []
  } else {
    selectedIds.value = cases.value.map(c => c.id)
  }
}

// 更新分类
async function updateCategory() {
  if (!categoryForm.value.category) return
  try {
    await axios.put(`/api/cases/${currentCase.value.id}/category`, categoryForm.value)
    showCategoryModal.value = false
    await fetchCaseDetail(currentCase.value.id)
    fetchStats()
  } catch (error) {
    console.error('更新分类失败:', error)
    alert('更新失败: ' + (error.response?.data?.error || error.message))
  }
}

// 批量更新分类
async function batchUpdateCategory() {
  if (!batchCategoryForm.value.category) return
  try {
    await axios.put('/api/cases/batch-category', {
      case_ids: selectedIds.value,
      ...batchCategoryForm.value
    })
    showBatchCategory.value = false
    selectedIds.value = []
    fetchCases()
    fetchStats()
  } catch (error) {
    console.error('批量更新分类失败:', error)
    alert('更新失败: ' + (error.response?.data?.error || error.message))
  }
}

// 添加跟进
async function addFollow() {
  if (!followForm.value.content) return
  try {
    await axios.post(`/api/cases/${currentCase.value.id}/follow`, followForm.value)
    showFollowModal.value = false
    followForm.value = { follow_type: '其他', content: '', follow_user: '' }
    await fetchCaseDetail(currentCase.value.id)
    await fetchFollows(currentCase.value.id)
  } catch (error) {
    console.error('添加跟进失败:', error)
    alert('添加失败: ' + (error.response?.data?.error || error.message))
  }
}

// 结案
async function closeCase() {
  try {
    await axios.put(`/api/cases/${currentCase.value.id}/close`, { close_remark: closeRemark.value })
    showCloseModal.value = false
    closeRemark.value = ''
    await fetchCaseDetail(currentCase.value.id)
    fetchStats()
  } catch (error) {
    console.error('结案失败:', error)
    alert('结案失败: ' + (error.response?.data?.error || error.message))
  }
}

// 删除案件
async function deleteCase() {
  try {
    await axios.delete(`/api/cases/${currentCase.value.id}`)
    showDeleteModal.value = false
    closeDetail()
    fetchCases()
    fetchStats()
  } catch (error) {
    console.error('删除失败:', error)
    alert('删除失败: ' + (error.response?.data?.error || error.message))
  }
}

// 批量删除
async function batchDelete() {
  try {
    await axios.post('/api/cases/batch-delete', { case_ids: selectedIds.value })
    showBatchDelete.value = false
    selectedIds.value = []
    fetchCases()
    fetchStats()
  } catch (error) {
    console.error('批量删除失败:', error)
    alert('删除失败: ' + (error.response?.data?.error || error.message))
  }
}

// 文件选择
function handleFileSelect(e) {
  importFile.value = e.target.files[0]
  importMessage.value = ''
  importError.value = ''
}

// 导入案件
async function importCases() {
  if (!importFile.value) return
  importLoading.value = true
  importMessage.value = ''
  importError.value = ''
  try {
    const formData = new FormData()
    formData.append('file', importFile.value)
    const response = await axios.post('/api/cases/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    importMessage.value = `导入完成，成功 ${response.data.imported_count} 条，跳过 ${response.data.skipped_count} 条`
    importFile.value = null
    fetchCases()
    fetchStats()
  } catch (error) {
    console.error('导入失败:', error)
    importError.value = '导入失败: ' + (error.response?.data?.error || error.message)
  } finally {
    importLoading.value = false
  }
}

// 工具函数
function getPhotoPaths(photoPath) {
  if (!photoPath) return []
  return photoPath.split(',').filter(p => p.trim())
}

function previewImage(url) {
  previewImageUrl.value = url
  showImagePreview.value = true
}

function getCategoryClass(category) {
  if (category === '非我局管辖') return 'non-jurisdiction'
  if (category === '挂账案件') return 'pending'
  if (category === '疑难案件') return 'difficult'
  return ''
}

onMounted(() => {
  fetchCases()
  fetchStats()
})
</script>

<style scoped>
.page-container {
  padding: var(--space-6);
  max-width: 1400px;
  margin: 0 auto;
}

.page-title {
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 var(--space-6);
}

/* 统计卡片 */
.stats-row {
  display: flex;
  gap: var(--space-4);
  margin-bottom: var(--space-6);
}

.stat-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--space-4);
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-lighter);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-lg);
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.expiring-badge {
  font-size: 12px;
  color: var(--danger);
  font-weight: 600;
}

.stat-label {
  font-size: 14px;
  color: var(--text-tertiary);
}

/* 操作栏 */
.action-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-4);
}

.search-box {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  background: var(--bg-card);
  border: 1px solid var(--border-lighter);
  border-radius: var(--radius-md);
  flex: 1;
  max-width: 600px;
}

.search-input {
  flex: 1;
  border: none;
  background: transparent;
  font-size: 14px;
  color: var(--text-primary);
  min-width: 200px;
}

.search-input:focus { outline: none; }

.status-select {
  padding: var(--space-1) var(--space-2);
  border: 1px solid var(--border-lighter);
  border-radius: var(--radius-sm);
  background: var(--bg-primary);
  color: var(--text-primary);
  font-size: 14px;
  min-width: 100px;
}

.btn-search {
  padding: var(--space-1) var(--space-3);
  background: var(--primary-500);
  color: white;
  border: none;
  border-radius: var(--radius-sm);
  font-size: 14px;
  cursor: pointer;
}

.btn-search:hover { background: var(--primary-600); }

.action-buttons {
  display: flex;
  gap: var(--space-2);
}

/* 按钮 */
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

.btn-sm { padding: var(--space-1) var(--space-3); font-size: 13px; }
.btn-primary { background: var(--primary-500); color: white; }
.btn-primary:hover { background: var(--primary-600); }
.btn-secondary { background: var(--bg-card); color: var(--text-primary); border-color: var(--border-lighter); }
.btn-secondary:hover { border-color: var(--primary-300); }
.btn-secondary.danger { color: var(--danger); }
.btn-secondary.danger:hover { background: rgba(245, 108, 108, 0.1); border-color: var(--danger); }
.btn-success { background: var(--success); color: white; }
.btn-danger { background: var(--danger); color: white; }
.btn-warning { background: var(--warning); color: white; }
.btn-info { background: var(--primary-500); color: white; }

.btn-text {
  padding: var(--space-1) var(--space-2);
  background: transparent;
  color: var(--primary-500);
  border: none;
  cursor: pointer;
  font-size: 14px;
}

.btn-text:hover { text-decoration: underline; }

/* 内容卡片 */
.content-card {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-lighter);
  padding: var(--space-6);
}

.loading-state, .empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  padding: var(--space-8);
  color: var(--text-tertiary);
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid var(--border-lighter);
  border-top-color: var(--primary-500);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

.empty-icon { font-size: 48px; }

/* 批量操作栏 */
.batch-actions {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3);
  background: var(--primary-50);
  border-radius: var(--radius-md);
  margin-bottom: var(--space-3);
}

.selected-count {
  color: var(--primary-500);
  font-weight: 500;
}

/* 表格 */
.table-container { overflow-x: auto; }

.data-table {
  width: 100%;
  border-collapse: collapse;
}

.data-table th, .data-table td {
  padding: var(--space-3) var(--space-4);
  text-align: left;
  border-bottom: 1px solid var(--border-lighter);
}

.data-table th {
  background: var(--bg-secondary);
  font-weight: 600;
  color: var(--text-secondary);
  white-space: nowrap;
}

.data-table tbody tr {
  cursor: pointer;
  transition: background var(--transition-fast);
}

.data-table tbody tr:hover { background: var(--fill-light); }
.data-table tbody tr.selected { background: var(--primary-50); }

.checkbox-col { width: 40px; text-align: center !important; }
.task-number { font-weight: 600; white-space: nowrap; }
.report-time { font-size: 13px; white-space: nowrap; }
.problem-desc {
  max-width: 300px;
  white-space: pre-wrap;
  word-break: break-all;
}

/* 分类标签 */
.category-badge {
  padding: 2px 8px;
  font-size: 12px;
  border-radius: var(--radius-full);
}

.category-badge.non-jurisdiction { background: rgba(255, 152, 0, 0.15); color: #ff9800; }
.category-badge.pending { background: rgba(255, 182, 193, 0.3); color: #ff6b9d; }
.category-badge.difficult { background: rgba(233, 30, 99, 0.15); color: #e91e63; }
.category-badge.none { background: rgba(255, 255, 255, 0.1); color: var(--text-tertiary); }

/* 状态标签 */
.status-badge {
  padding: 2px 8px;
  font-size: 12px;
  border-radius: var(--radius-full);
  font-weight: 500;
}

.status-badge.following { background: var(--primary-100); color: var(--primary-700); }
.status-badge.closed { background: rgba(103, 194, 58, 0.15); color: #67c23a; }

/* 分页 */
.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  margin-top: var(--space-4);
}

.pagination-btn {
  padding: var(--space-2) var(--space-3);
  font-size: 14px;
  color: var(--text-secondary);
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  cursor: pointer;
}

.pagination-btn:hover:not(:disabled) { border-color: var(--primary-500); color: var(--primary-500); }
.pagination-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.page-info { color: var(--text-secondary); font-size: 14px; }

/* 详情卡片 */
.detail-card {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-lighter);
  overflow: hidden;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-4) var(--space-6);
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-lighter);
}

.case-title { font-size: 18px; font-weight: 600; margin: 0; color: var(--text-primary); }

.case-tags { display: flex; gap: var(--space-2); margin-top: var(--space-2); align-items: center; }

.category-tag, .status-tag {
  padding: 2px 10px;
  border-radius: var(--radius-full);
  font-size: 12px;
  font-weight: 500;
}

.category-tag.non-jurisdiction { background: rgba(255, 152, 0, 0.15); color: #ff9800; }
.category-tag.pending { background: rgba(233, 30, 99, 0.15); color: #e91e63; }
.category-tag.difficult { background: rgba(156, 39, 176, 0.15); color: #9c27b0; }

.status-tag.following { background: rgba(64, 158, 255, 0.15); color: var(--primary-500); }
.status-tag.closed { background: rgba(103, 194, 58, 0.15); color: #67c23a; }

.follow-count { font-size: 12px; color: var(--text-tertiary); }

.header-actions { display: flex; gap: var(--space-2); }

.detail-body {
  display: grid;
  grid-template-columns: 1fr 400px;
  gap: 0;
}

.detail-left { padding: var(--space-6); border-right: 1px solid var(--border-lighter); }
.detail-right { padding: var(--space-6); background: var(--bg-secondary); }

.info-section { margin-bottom: var(--space-6); }
.info-section:last-child { margin-bottom: 0; }

.section-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 var(--space-3);
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.follow-total { font-size: 12px; color: var(--text-tertiary); font-weight: normal; }

.info-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-3);
}

.info-item {
  padding: var(--space-3);
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  border-left: 3px solid var(--primary-500);
}

.info-label {
  display: block;
  font-size: 12px;
  color: var(--text-tertiary);
  margin-bottom: var(--space-1);
}

.info-value { font-size: 14px; color: var(--text-primary); }
.info-text { font-size: 14px; color: var(--text-primary); line-height: 1.6; margin: 0; }

/* 分类专属信息 */
.category-info {
  border-radius: var(--radius-md);
  padding: var(--space-4);
}

.category-info.non-jurisdiction { background: rgba(255, 152, 0, 0.1); border: 1px solid rgba(255, 152, 0, 0.3); }
.category-info.pending { background: rgba(255, 182, 193, 0.1); border: 1px solid rgba(255, 182, 193, 0.3); }
.category-info.difficult { background: rgba(233, 30, 99, 0.1); border: 1px solid rgba(233, 30, 99, 0.3); }
.category-info.closed { background: rgba(67, 233, 123, 0.1); border: 1px solid rgba(67, 233, 123, 0.3); }

.category-info .section-title { color: var(--text-primary); }

/* 照片 */
.photo-grid { display: flex; flex-wrap: wrap; gap: var(--space-3); }

.photo-item {
  width: 150px;
  height: 110px;
  object-fit: cover;
  border-radius: var(--radius-md);
  cursor: pointer;
  border: 1px solid var(--border-lighter);
  transition: transform var(--transition-fast);
}

.photo-item:hover { transform: scale(1.05); }

/* 跟进记录 */
.empty-follows {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--space-8);
  color: var(--text-tertiary);
  text-align: center;
}

.follow-timeline { max-height: 500px; overflow-y: auto; }

.follow-item {
  position: relative;
  padding-left: var(--space-6);
  margin-bottom: var(--space-4);
}

.timeline-dot {
  position: absolute;
  left: 0;
  top: 8px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--primary-500);
  border: 2px solid var(--bg-card);
}

.timeline-line {
  position: absolute;
  left: 5px;
  top: 24px;
  width: 2px;
  height: calc(100% + 8px);
  background: var(--primary-200);
}

.follow-card {
  padding: var(--space-3);
  background: var(--bg-card);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-lighter);
}

.follow-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-2);
}

.follow-type {
  padding: 2px 10px;
  background: var(--primary-100);
  color: var(--primary-700);
  border-radius: var(--radius-full);
  font-size: 12px;
  font-weight: 500;
}

.follow-time { font-size: 12px; color: var(--text-tertiary); }
.follow-content { font-size: 14px; color: var(--text-primary); margin: 0; line-height: 1.5; }
.follow-user { font-size: 12px; color: var(--text-tertiary); margin: var(--space-1) 0 0; }

/* 弹窗 */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: var(--bg-card);
  padding: var(--space-6);
  border-radius: var(--radius-lg);
  width: 450px;
  max-height: 80vh;
  overflow-y: auto;
}

.modal-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 var(--space-4);
}

.modal-title.danger { color: var(--danger); }
.modal-desc { color: var(--text-secondary); margin-bottom: var(--space-4); }
.modal-desc strong { color: var(--text-primary); }
.modal-desc strong.danger { color: var(--danger); }
.modal-warning { color: var(--text-tertiary); font-size: 13px; margin-bottom: var(--space-4); }

.modal-actions {
  display: flex;
  gap: var(--space-3);
  justify-content: flex-end;
  margin-top: var(--space-4);
}

/* 表单 */
.form-group { margin-bottom: var(--space-4); }
.form-row { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-4); }
.form-label { display: block; font-size: 14px; font-weight: 500; color: var(--text-primary); margin-bottom: var(--space-2); }
.form-input, .form-select, .form-textarea {
  width: 100%;
  padding: var(--space-2) var(--space-3);
  font-size: 14px;
  color: var(--text-primary);
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
}

.form-input:focus, .form-select:focus, .form-textarea:focus {
  outline: none;
  border-color: var(--primary-500);
}

.form-textarea { resize: vertical; min-height: 80px; }
.form-file { width: 100%; }

.alert-box {
  padding: var(--space-3);
  background: rgba(255, 193, 7, 0.15);
  border: 1px solid rgba(255, 193, 7, 0.3);
  border-radius: var(--radius-md);
  color: var(--warning);
  font-size: 14px;
  margin-bottom: var(--space-4);
}

.file-info {
  padding: var(--space-2) var(--space-3);
  background: var(--primary-50);
  border-radius: var(--radius-md);
  color: var(--primary-700);
  font-size: 13px;
  margin-bottom: var(--space-4);
}

.success-message {
  padding: var(--space-3);
  background: rgba(103, 194, 58, 0.15);
  border: 1px solid rgba(103, 194, 58, 0.3);
  border-radius: var(--radius-md);
  color: #67c23a;
  font-size: 14px;
  margin-bottom: var(--space-4);
}

.error-message {
  padding: var(--space-3);
  background: rgba(245, 108, 108, 0.15);
  border: 1px solid rgba(245, 108, 108, 0.3);
  border-radius: var(--radius-md);
  color: #f56c6c;
  font-size: 14px;
  margin-bottom: var(--space-4);
}

/* 图片预览 */
.image-preview-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.9);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  cursor: zoom-out;
}

.preview-image {
  max-width: 90%;
  max-height: 90%;
  object-fit: contain;
  border-radius: var(--radius-md);
}

.close-preview {
  position: absolute;
  top: var(--space-4);
  right: var(--space-4);
  padding: var(--space-2) var(--space-4);
  background: rgba(255, 255, 255, 0.1);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
}

/* 响应式 */
@media (max-width: 1024px) {
  .detail-body {
    grid-template-columns: 1fr;
  }

  .detail-left { border-right: none; border-bottom: 1px solid var(--border-lighter); }
}

@media (max-width: 768px) {
  .stats-row { flex-wrap: wrap; }
  .stat-card { flex: 1 1 calc(50% - var(--space-2)); min-width: 140px; }

  .action-bar { flex-direction: column; align-items: stretch; gap: var(--space-3); }
  .search-box { flex-wrap: wrap; max-width: none; }
  .search-input { min-width: 100%; order: 1; }
  .status-select, .btn-search { order: 2; }

  .form-row { grid-template-columns: 1fr; }
}
</style>