<template>
  <div class="dm-tab">
    <!-- 上传区 -->
    <div class="content-card">
      <div class="card-header">
        <h3>数据上传</h3>
      </div>
      <div class="card-body">
        <div class="upload-area" @dragover.prevent @drop.prevent="handleDrop">
          <input type="file" ref="fileInput" accept=".xlsx,.xls" @change="handleFileSelect" hidden />
          <div class="upload-content" @click="$refs.fileInput.click()">
            <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
            <span>点击或拖拽上传Excel文件</span>
            <span class="upload-hint">上传将按月份覆盖已有数据</span>
          </div>
        </div>
        <div v-if="uploadLoading" class="upload-progress">上传中...</div>
        <div v-if="uploadMessage" class="upload-result success">{{ uploadMessage }}</div>
        <div v-if="uploadError" class="upload-result error">{{ uploadError }}</div>
      </div>
    </div>

    <!-- 更新延期/返工/超时 -->
    <div class="content-card">
      <div class="card-header">
        <h3>更新延期/返工/超时标记</h3>
      </div>
      <div class="card-body">
        <p class="hint-text">上传延期/返工/超时案件列表（支持txt或xlsx格式），系统会自动检测所属批次并更新标记。</p>
        <div class="upload-area" @dragover.prevent @drop.prevent="handleDelayReworkDrop">
          <input type="file" ref="drFileInput" accept=".txt,.xlsx,.xls" @change="handleDelayReworkSelect" hidden />
          <div class="upload-content" @click="$refs.drFileInput.click()">
            <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
            <span>点击或拖拽上传延期/返工/超时列表</span>
            <span class="upload-hint">格式：任务号+类型（延期/返工/超时）</span>
          </div>
        </div>
        <div v-if="drUploadLoading" class="upload-progress">解析中...</div>
        <div v-if="drDetectResult" class="detect-result">
          <div class="detect-summary">
            <span v-if="drDetectResult.total_delayed">延期 {{ drDetectResult.total_delayed }} 条</span>
            <span v-if="drDetectResult.total_rework">返工 {{ drDetectResult.total_rework }} 条</span>
            <span v-if="drDetectResult.total_overtime">超时 {{ drDetectResult.total_overtime }} 条</span>
          </div>
          <div v-for="(stats, batch) in drDetectResult.batch_stats" :key="batch" class="batch-info">
            <span class="batch-name">{{ formatMonth(batch) }}：</span>
            <span v-if="stats.delayed">延期{{ stats.delayed }}条 </span>
            <span v-if="stats.rework">返工{{ stats.rework }}条 </span>
            <span v-if="stats.overtime">超时{{ stats.overtime }}条</span>
          </div>
          <div v-if="drDetectResult.not_found?.length" class="not-found">
            未找到 {{ drDetectResult.not_found.length }} 个任务号
          </div>
          <button class="btn btn-primary" style="margin-top:12px" @click="applyDelayRework" :disabled="drApplyLoading">
            {{ drApplyLoading ? '更新中...' : '确认更新' }}
          </button>
        </div>
        <div v-if="drApplyMessage" class="upload-result success">{{ drApplyMessage }}</div>
        <div v-if="drApplyError" class="upload-result error">{{ drApplyError }}</div>
      </div>
    </div>

    <!-- 数据浏览 -->
    <div class="content-card">
      <div class="card-header">
        <h3>数据浏览</h3>
        <div class="header-actions">
          <button class="btn btn-primary" @click="openAddRecordModal">新增记录</button>
          <button class="btn btn-secondary" @click="exportData" :disabled="exportLoading">
            {{ exportLoading ? '导出中...' : '导出Excel' }}
          </button>
        </div>
      </div>
      <div class="card-body">
        <!-- 过滤栏 -->
        <div class="filter-row">
          <div class="form-group">
            <label class="form-label">月份</label>
            <select v-model="editMonth" class="form-select" @change="fetchRecords">
              <option value="">全部月份</option>
              <option v-for="m in availableMonths" :key="m.batch" :value="m.batch">
                {{ formatMonth(m.batch) }} ({{ m.count }}条)
              </option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">搜索字段</label>
            <select v-model="searchField" class="form-select">
              <option value="">选择字段</option>
              <option v-for="col in searchableColumns" :key="col.name" :value="col.name">{{ col.label }}</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">搜索内容</label>
            <input v-model="searchValue" type="text" class="form-input" placeholder="输入搜索内容" @keyup.enter="fetchRecords" />
          </div>
          <div class="form-group filter-actions">
            <button class="btn btn-primary" @click="page = 1; fetchRecords()">搜索</button>
            <button class="btn btn-secondary" @click="resetFilters">重置</button>
          </div>
        </div>

        <!-- 批量操作栏 -->
        <div class="action-bar" v-if="selectedIds.length > 0">
          <span class="action-bar-label">已选择 {{ selectedIds.length }} 条记录</span>
          <div class="quick-actions">
            <div class="quick-group">
              <label class="quick-label">阶段</label>
              <select v-model="quickStage" class="form-select form-select-sm">
                <option value="">选择阶段</option>
                <option v-for="s in stageOptions" :key="s" :value="s">{{ s }}</option>
              </select>
              <button class="btn btn-primary btn-sm" @click="applyQuickStage" :disabled="!quickStage || quickActionLoading">应用</button>
            </div>
            <div class="quick-separator"></div>
            <div class="quick-group">
              <button class="btn btn-sm" :class="quickFlagState.is_delayed ? 'btn-warning' : 'btn-outline'" @click="applyQuickFlag('is_delayed', quickFlagState.is_delayed ? 0 : 1)" :disabled="quickActionLoading">
                {{ quickFlagState.is_delayed ? '取消延期' : '设为延期' }}
              </button>
              <button class="btn btn-sm" :class="quickFlagState.is_overtime ? 'btn-warning' : 'btn-outline'" @click="applyQuickFlag('is_overtime', quickFlagState.is_overtime ? 0 : 1)" :disabled="quickActionLoading">
                {{ quickFlagState.is_overtime ? '取消超时' : '设为超时' }}
              </button>
              <button class="btn btn-sm" :class="quickFlagState.is_rework ? 'btn-warning' : 'btn-outline'" @click="applyQuickFlag('is_rework', quickFlagState.is_rework ? 0 : 1)" :disabled="quickActionLoading">
                {{ quickFlagState.is_rework ? '取消返工' : '设为返工' }}
              </button>
            </div>
          </div>
          <div class="action-bar-right">
            <button class="btn btn-secondary btn-sm" @click="showBatchEditModal = true">批量修改</button>
            <button class="btn btn-danger btn-sm" @click="confirmBatchDelete">批量删除</button>
            <button class="btn-text" @click="selectedIds = []; selectAll = false">取消选择</button>
          </div>
        </div>

        <!-- 表格 -->
        <div class="table-wrapper">
          <table class="data-table">
            <thead>
              <tr>
                <th class="col-check"><input type="checkbox" v-model="selectAll" @change="toggleSelectAll" /></th>
                <th v-for="col in displayColumns" :key="col.name" @click="sortBy(col.name)" :class="{ sortable: true, active: sortField === col.name }">
                  {{ col.label }}
                  <span v-if="sortField === col.name" class="sort-arrow">{{ sortOrder === 'asc' ? ' \u2191' : ' \u2193' }}</span>
                </th>
                <th class="col-actions">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="loading">
                <td :colspan="displayColumns.length + 2" class="center-cell">加载中...</td>
              </tr>
              <tr v-else-if="records.length === 0">
                <td :colspan="displayColumns.length + 2" class="center-cell">暂无数据</td>
              </tr>
              <tr v-else v-for="record in records" :key="record.id" :class="{ selected: selectedIds.includes(record.id) }">
                <td class="col-check"><input type="checkbox" :value="record.id" v-model="selectedIds" /></td>
                <td v-for="col in displayColumns" :key="col.name" :title="formatCellValue(record[col.name], col)">{{ formatCellValue(record[col.name], col) }}</td>
                <td class="col-actions">
                  <button class="btn-text" @click="openEditRecordModal(record)">编辑</button>
                  <button class="btn-text danger" @click="confirmDeleteRecord(record)">删除</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- 分页 -->
        <div class="pagination" v-if="totalPages > 1">
          <button class="btn btn-secondary btn-sm" :disabled="page <= 1" @click="page--; fetchRecords()">上一页</button>
          <span class="page-info">{{ page }} / {{ totalPages }} (共 {{ total }} 条)</span>
          <button class="btn btn-secondary btn-sm" :disabled="page >= totalPages" @click="page++; fetchRecords()">下一页</button>
        </div>
      </div>
    </div>

    <!-- 操作日志 -->
    <div class="content-card">
      <div class="card-header">
        <h3>操作日志</h3>
        <div class="header-actions">
          <select v-model="logFilterType" class="form-select form-select-sm" @change="logPage = 1; fetchLogs()">
            <option value="">全部类型</option>
            <option value="update">编辑</option>
            <option value="batch_update">批量修改</option>
            <option value="delete">删除</option>
            <option value="batch_delete">批量删除</option>
            <option value="rollback">回滚</option>
          </select>
          <button class="btn btn-secondary btn-sm" @click="fetchLogs">刷新</button>
        </div>
      </div>
      <div class="card-body">
        <div v-if="logsLoading" class="center-cell">加载中...</div>
        <div v-else-if="logs.length === 0" class="center-cell">暂无操作日志</div>
        <template v-else>
          <div class="table-wrapper">
            <table class="data-table">
              <thead>
                <tr>
                  <th style="width:160px">操作时间</th>
                  <th style="width:100px">操作类型</th>
                  <th style="width:80px">操作人</th>
                  <th>操作内容</th>
                  <th style="width:100px">影响记录</th>
                  <th style="width:120px">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="log in logs" :key="log.id">
                  <td>{{ log.created_at }}</td>
                  <td>
                    <span class="log-type-badge" :class="'log-type-' + log.operation_type">{{ logTypeLabel(log.operation_type) }}</span>
                  </td>
                  <td>{{ log.username }}</td>
                  <td class="log-content-cell" :title="log.old_value || log.new_value">{{ log.old_value || log.new_value || '-' }}</td>
                  <td>{{ log.record_id ? log.record_id.split(',').length : 0 }} 条</td>
                  <td class="col-actions">
                    <button class="btn-text" @click="viewLogDetail(log)">详情</button>
                    <button class="btn-text" :class="log.snapshot_data ? '' : 'disabled'" @click="log.snapshot_data && confirmRollback(log)">回滚</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="pagination" v-if="logTotalPages > 1">
            <button class="btn btn-secondary btn-sm" :disabled="logPage <= 1" @click="logPage--; fetchLogs()">上一页</button>
            <span class="page-info">{{ logPage }} / {{ logTotalPages }} (共 {{ logTotal }} 条)</span>
            <button class="btn btn-secondary btn-sm" :disabled="logPage >= logTotalPages" @click="logPage++; fetchLogs()">下一页</button>
          </div>
        </template>
      </div>
    </div>

    <!-- 日志详情模态框 -->
    <div class="modal-overlay" v-if="showLogDetailModal" @click.self="showLogDetailModal = false">
      <div class="modal-content modal-large">
        <div class="modal-header">
          <h3>操作详情</h3>
          <button class="close-btn" @click="showLogDetailModal = false">&times;</button>
        </div>
        <div class="modal-body modal-body-scroll">
          <div class="log-detail" v-if="logDetail">
            <p><strong>操作人：</strong>{{ logDetail.username }}</p>
            <p><strong>操作类型：</strong>{{ logTypeLabel(logDetail.operation_type) }}</p>
            <p><strong>操作时间：</strong>{{ logDetail.created_at }}</p>
            <p><strong>影响记录ID：</strong>{{ logDetail.record_id || '-' }}</p>
            <p v-if="logDetail.old_value"><strong>操作内容：</strong>{{ logDetail.old_value }}</p>
            <p v-if="logDetail.new_value"><strong>新值：</strong>{{ logDetail.new_value }}</p>
            <div v-if="logDetail.snapshot_data" class="snapshot-section">
              <strong>变更前快照：</strong>
              <pre class="snapshot-json">{{ formatSnapshot(logDetail.snapshot_data) }}</pre>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 回滚确认模态框 -->
    <div class="modal-overlay" v-if="showRollbackConfirm" @click.self="showRollbackConfirm = false">
      <div class="modal-content modal-small">
        <div class="modal-header">
          <h3>确认回滚</h3>
          <button class="close-btn" @click="showRollbackConfirm = false">&times;</button>
        </div>
        <div class="modal-body">
          <p>{{ rollbackMessage }}</p>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" @click="showRollbackConfirm = false">取消</button>
          <button class="btn btn-warning" @click="executeRollback" :disabled="rollbackLoading">{{ rollbackLoading ? '回滚中...' : '确认回滚' }}</button>
        </div>
      </div>
    </div>

    <!-- 新增/编辑记录模态框 -->
    <div class="modal-overlay" v-if="showRecordModal" @click.self="showRecordModal = false">
      <div class="modal-content modal-record">
        <div class="modal-header">
          <h3>{{ isAddRecord ? '新增记录' : '编辑记录' }}</h3>
          <button class="close-btn" @click="showRecordModal = false">&times;</button>
        </div>
        <div class="modal-body modal-body-scroll">
          <div class="form-group" v-for="col in editableColumns" :key="col.name">
            <label class="form-label">{{ col.label }}</label>
            <template v-if="col.name === 'task_no'">
              <input v-model="recordForm[col.name]" type="number" class="form-input" :disabled="!isAddRecord" :placeholder="isAddRecord ? '' : '不可编辑'" />
            </template>
            <template v-else-if="col.name === 'is_delayed' || col.name === 'is_rework' || col.name === 'is_overtime'">
              <select v-model="recordForm[col.name]" class="form-select">
                <option :value="0">否</option>
                <option :value="1">是</option>
              </select>
            </template>
            <template v-else-if="col.type === 'datetime'">
              <input v-model="recordForm[col.name]" type="datetime-local" class="form-input" />
            </template>
            <template v-else-if="col.name === 'description'">
              <textarea v-model="recordForm[col.name]" class="form-textarea" rows="3"></textarea>
            </template>
            <template v-else>
              <input v-model="recordForm[col.name]" type="text" class="form-input" />
            </template>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" @click="showRecordModal = false">取消</button>
          <button class="btn btn-primary" @click="saveRecord" :disabled="recordSaving">{{ recordSaving ? '保存中...' : '确认' }}</button>
        </div>
      </div>
    </div>

    <!-- 批量修改模态框 -->
    <div class="modal-overlay" v-if="showBatchEditModal" @click.self="showBatchEditModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3>批量修改</h3>
          <button class="close-btn" @click="showBatchEditModal = false">&times;</button>
        </div>
        <div class="modal-body">
          <p>将修改 {{ selectedIds.length }} 条记录</p>
          <div class="form-group">
            <label class="form-label">选择修改字段</label>
            <select v-model="batchEditField" class="form-select">
              <option value="">请选择</option>
              <option v-for="col in editableColumns.filter(c => c.name !== 'task_no')" :key="col.name" :value="col.name">{{ col.label }}</option>
            </select>
          </div>
          <div class="form-group" v-if="batchEditField">
            <label class="form-label">新值</label>
            <template v-if="batchEditField === 'is_delayed' || batchEditField === 'is_rework' || batchEditField === 'is_overtime'">
              <select v-model="batchEditValue" class="form-select">
                <option :value="0">否</option>
                <option :value="1">是</option>
              </select>
            </template>
            <template v-else>
              <input v-model="batchEditValue" type="text" class="form-input" placeholder="输入新值" />
            </template>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" @click="showBatchEditModal = false">取消</button>
          <button class="btn btn-primary" @click="batchUpdateRecords" :disabled="batchEditSaving">{{ batchEditSaving ? '保存中...' : '确认修改' }}</button>
        </div>
      </div>
    </div>

    <!-- 删除确认模态框 -->
    <div class="modal-overlay" v-if="showDeleteConfirm" @click.self="showDeleteConfirm = false">
      <div class="modal-content modal-small">
        <div class="modal-header">
          <h3>确认删除</h3>
          <button class="close-btn" @click="showDeleteConfirm = false">&times;</button>
        </div>
        <div class="modal-body">
          <p>{{ deleteConfirmMessage }}</p>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" @click="showDeleteConfirm = false">取消</button>
          <button class="btn btn-danger" @click="executeDelete" :disabled="deleteSaving">{{ deleteSaving ? '删除中...' : '确认删除' }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'

const API = '/api/data-management'

// 上传
const fileInput = ref(null)
const uploadLoading = ref(false)
const uploadMessage = ref('')
const uploadError = ref('')

// 月份 & 过滤
const availableMonths = ref([])
const editMonth = ref('')
const searchField = ref('')
const searchValue = ref('')
const sortField = ref('id')
const sortOrder = ref('desc')

// 记录
const records = ref([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = 20
const columns = ref([])
const selectedIds = ref([])
const selectAll = ref(false)

// 模态框
const showRecordModal = ref(false)
const isAddRecord = ref(true)
const recordForm = ref({})
const recordSaving = ref(false)

const showBatchEditModal = ref(false)
const batchEditField = ref('')
const batchEditValue = ref('')
const batchEditSaving = ref(false)

const showDeleteConfirm = ref(false)
const deleteTarget = ref(null)
const deleteConfirmMessage = ref('')
const deleteSaving = ref(false)

const exportLoading = ref(false)

// 快捷操作
const stageOptions = ['[办结]', '二级专业部门', '其他问题流向', '市政问题流向', '市指挥中心督查', '值班长（结案）', '监督中心（核查）']
const quickStage = ref('')
const quickActionLoading = ref(false)
const quickFlagState = ref({ is_delayed: 0, is_overtime: 0, is_rework: 0 })

// 操作日志
const logs = ref([])
const logsLoading = ref(false)
const logTotal = ref(0)
const logPage = ref(1)
const logPageSize = 20
const logFilterType = ref('')
const showLogDetailModal = ref(false)
const logDetail = ref(null)
const showRollbackConfirm = ref(false)
const rollbackTarget = ref(null)
const rollbackMessage = ref('')
const rollbackLoading = ref(false)

// 延期/返工/超时更新
const drFileInput = ref(null)
const drUploadLoading = ref(false)
const drDetectResult = ref(null)
const drDelayTaskNos = ref([])
const drReworkTaskNos = ref([])
const drOvertimeTaskNos = ref([])
const drApplyLoading = ref(false)
const drApplyMessage = ref('')
const drApplyError = ref('')

// 计算属性
const displayColumns = computed(() =>
  columns.value.filter(c => !['id', 'upload_time', 'uploader'].includes(c.name))
)

const editableColumns = computed(() =>
  columns.value.filter(c => c.editable)
)

const searchableColumns = computed(() =>
  columns.value.filter(c => c.editable && ['varchar', 'text', 'bigint', 'int'].includes(c.type))
)

const totalPages = computed(() => Math.ceil(total.value / pageSize))
const logTotalPages = computed(() => Math.ceil(logTotal.value / logPageSize))

// 方法
function formatMonth(batch) {
  if (!batch || batch.length < 6) return batch || ''
  return batch.substring(0, 4) + '年' + batch.substring(4, 6) + '月'
}

function formatCellValue(val, col) {
  if (val === null || val === undefined) return ''
  if (col.name === 'is_delayed' || col.name === 'is_rework' || col.name === 'is_overtime') return val ? '是' : '否'
  if (col.type === 'datetime' && typeof val === 'string' && val.length > 10) return val.substring(0, 16).replace('T', ' ')
  const str = String(val)
  return str.length > 40 ? str.substring(0, 40) + '...' : str
}

async function fetchMonths() {
  try {
    const res = await axios.get(`${API}/months`)
    if (res.data?.success) availableMonths.value = res.data.months
  } catch (e) { console.error('获取月份失败:', e) }
}

async function fetchRecords() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize }
    if (editMonth.value) params.month = editMonth.value
    if (searchField.value && searchValue.value) {
      params.search_field = searchField.value
      params.search_value = searchValue.value
    }
    if (sortField.value) {
      params.sort_field = sortField.value
      params.sort_order = sortOrder.value
    }
    const res = await axios.get(`${API}/records`, { params })
    if (res.data?.success) {
      records.value = res.data.records
      total.value = res.data.total
      columns.value = res.data.columns || []
    }
  } catch (e) { console.error('获取记录失败:', e) }
  finally { loading.value = false }
}

function resetFilters() {
  editMonth.value = ''
  searchField.value = ''
  searchValue.value = ''
  sortField.value = 'id'
  sortOrder.value = 'desc'
  page.value = 1
  fetchRecords()
}

function sortBy(field) {
  if (sortField.value === field) {
    sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortField.value = field
    sortOrder.value = 'desc'
  }
  fetchRecords()
}

function toggleSelectAll() {
  selectedIds.value = selectAll.value ? records.value.map(r => r.id) : []
}

// 上传
function handleFileSelect(e) {
  const file = e.target.files?.[0]
  if (file) uploadFile(file)
}

function handleDrop(e) {
  const file = e.dataTransfer?.files?.[0]
  if (file && file.name.endsWith(('.xlsx', '.xls'))) uploadFile(file)
}

async function uploadFile(file) {
  uploadLoading.value = true
  uploadMessage.value = ''
  uploadError.value = ''
  const formData = new FormData()
  formData.append('file', file)
  try {
    const res = await axios.post(`${API}/upload`, formData)
    if (res.data?.success) {
      uploadMessage.value = res.data.message
      await fetchMonths()
      await fetchRecords()
    } else {
      uploadError.value = res.data?.error || '上传失败'
    }
  } catch (e) {
    uploadError.value = e.response?.data?.error || '上传失败'
  } finally {
    uploadLoading.value = false
    if (fileInput.value) fileInput.value.value = ''
  }
}

// 记录编辑
function openAddRecordModal() {
  isAddRecord.value = true
  recordForm.value = {}
  editableColumns.value.forEach(col => { recordForm.value[col.name] = '' })
  showRecordModal.value = true
}

function openEditRecordModal(record) {
  isAddRecord.value = false
  recordForm.value = { ...record }
  showRecordModal.value = true
}

async function saveRecord() {
  recordSaving.value = true
  try {
    if (isAddRecord.value) {
      await axios.post(`${API}/record`, { record_data: recordForm.value })
    } else {
      await axios.put(`${API}/record/${recordForm.value.id}`, { record_data: recordForm.value })
    }
    showRecordModal.value = false
    fetchRecords()
  } catch (e) {
    alert(e.response?.data?.error || '保存失败')
  } finally { recordSaving.value = false }
}

// 删除
function confirmDeleteRecord(record) {
  deleteTarget.value = { type: 'single', id: record.id }
  deleteConfirmMessage.value = `确定删除该记录？此操作不可恢复。`
  showDeleteConfirm.value = true
}

function confirmBatchDelete() {
  if (!selectedIds.value.length) return
  deleteTarget.value = { type: 'batch', ids: [...selectedIds.value] }
  deleteConfirmMessage.value = `确定删除选中的 ${selectedIds.value.length} 条记录？此操作不可恢复。`
  showDeleteConfirm.value = true
}

async function executeDelete() {
  deleteSaving.value = true
  try {
    if (deleteTarget.value.type === 'single') {
      await axios.delete(`${API}/record/${deleteTarget.value.id}`)
    } else {
      await axios.post(`${API}/batch-delete`, { ids: deleteTarget.value.ids })
    }
    showDeleteConfirm.value = false
    selectedIds.value = []
    selectAll.value = false
    fetchRecords()
  } catch (e) {
    alert(e.response?.data?.error || '删除失败')
  } finally { deleteSaving.value = false }
}

// 批量修改
async function batchUpdateRecords() {
  if (!batchEditField.value) { alert('请选择要修改的字段'); return }
  batchEditSaving.value = true
  try {
    await axios.post(`${API}/batch-update`, {
      ids: selectedIds.value,
      field: batchEditField.value,
      value: batchEditValue.value
    })
    showBatchEditModal.value = false
    batchEditField.value = ''
    batchEditValue.value = ''
    selectedIds.value = []
    selectAll.value = false
    fetchRecords()
  } catch (e) {
    alert(e.response?.data?.error || '批量修改失败')
  } finally { batchEditSaving.value = false }
}

// 快捷操作
async function applyQuickStage() {
  if (!quickStage.value || !selectedIds.value.length) return
  quickActionLoading.value = true
  try {
    await axios.post(`${API}/batch-update`, {
      ids: selectedIds.value,
      field: 'stage',
      value: quickStage.value
    })
    quickStage.value = ''
    selectedIds.value = []
    selectAll.value = false
    fetchRecords()
  } catch (e) {
    alert(e.response?.data?.error || '修改阶段失败')
  } finally { quickActionLoading.value = false }
}

async function applyQuickFlag(field, value) {
  if (!selectedIds.value.length) return
  quickActionLoading.value = true
  try {
    await axios.post(`${API}/batch-update`, {
      ids: selectedIds.value,
      field,
      value
    })
    selectedIds.value = []
    selectAll.value = false
    fetchRecords()
  } catch (e) {
    alert(e.response?.data?.error || '修改失败')
  } finally { quickActionLoading.value = false }
}

// 导出
async function exportData() {
  exportLoading.value = true
  try {
    const params = {}
    if (editMonth.value) params.month = editMonth.value
    if (searchField.value && searchValue.value) {
      params.search_field = searchField.value
      params.search_value = searchValue.value
    }
    const res = await axios.get(`${API}/export`, { params, responseType: 'blob' })
    const url = window.URL.createObjectURL(new Blob([res.data]))
    const link = document.createElement('a')
    link.href = url
    const disposition = res.headers['content-disposition']
    const filename = disposition ? disposition.split('filename=')[1]?.replace(/"/g, '') : 'case_data.xlsx'
    link.setAttribute('download', filename)
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
  } catch (e) {
    if (e.response?.data?.text) {
      const text = await e.response.data.text()
      const json = JSON.parse(text)
      alert(json.error || '导出失败')
    } else {
      alert('导出失败')
    }
  } finally { exportLoading.value = false }
}

// 延期/返工/超时更新
function handleDelayReworkSelect(e) {
  const file = e.target.files?.[0]
  if (file) parseDelayReworkFile(file)
}

function handleDelayReworkDrop(e) {
  const file = e.dataTransfer?.files?.[0]
  if (file && (file.name.endsWith('.txt') || file.name.endsWith('.xlsx') || file.name.endsWith('.xls'))) {
    parseDelayReworkFile(file)
  }
}

async function parseDelayReworkFile(file) {
  drUploadLoading.value = true
  drDetectResult.value = null
  drApplyMessage.value = ''
  drApplyError.value = ''

  const formData = new FormData()
  formData.append('file', file)

  try {
    const res = await axios.post('/api/cleaning/upload-delay-rework', formData)
    if (res.data?.success) {
      drDelayTaskNos.value = res.data.delayed_task_nos || []
      drReworkTaskNos.value = res.data.rework_task_nos || []
      drOvertimeTaskNos.value = res.data.overtime_task_nos || []

      // 自动检测批次
      const detectRes = await axios.post(`${API}/detect-delay-rework`, {
        delay_task_nos: drDelayTaskNos.value,
        rework_task_nos: drReworkTaskNos.value,
        overtime_task_nos: drOvertimeTaskNos.value
      })
      if (detectRes.data?.success) {
        drDetectResult.value = detectRes.data
      }
    }
  } catch (e) {
    drApplyError.value = e.response?.data?.error || '解析失败'
  } finally {
    drUploadLoading.value = false
    if (drFileInput.value) drFileInput.value.value = ''
  }
}

async function applyDelayRework() {
  if (!drDetectResult.value?.batch_stats) return

  const batches = Object.keys(drDetectResult.value.batch_stats)
  if (batches.length === 0) {
    drApplyError.value = '未找到匹配的批次'
    return
  }

  if (batches.length > 1) {
    drApplyError.value = '任务号分布在多个批次中，请确保列表中的任务号属于同一月份'
    return
  }

  drApplyLoading.value = true
  drApplyMessage.value = ''
  drApplyError.value = ''

  try {
    const res = await axios.post(`${API}/apply-delay-rework`, {
      batch: batches[0],
      delay_task_nos: drDelayTaskNos.value,
      rework_task_nos: drReworkTaskNos.value,
      overtime_task_nos: drOvertimeTaskNos.value
    })
    if (res.data?.success) {
      drApplyMessage.value = res.data.message
      drDetectResult.value = null
      fetchRecords()
    }
  } catch (e) {
    drApplyError.value = e.response?.data?.error || '更新失败'
  } finally {
    drApplyLoading.value = false
  }
}

// 操作日志
function logTypeLabel(type) {
  const map = { update: '编辑', batch_update: '批量修改', delete: '删除', batch_delete: '批量删除', rollback: '回滚', create: '新增' }
  return map[type] || type
}

async function fetchLogs() {
  logsLoading.value = true
  try {
    const params = { page: logPage.value, page_size: logPageSize }
    if (logFilterType.value) params.operation_type = logFilterType.value
    const res = await axios.get(`${API}/logs`, { params })
    if (res.data?.success) {
      logs.value = res.data.logs || []
      logTotal.value = res.data.total || 0
    }
  } catch (e) { console.error('获取日志失败:', e) }
  finally { logsLoading.value = false }
}

function viewLogDetail(log) {
  logDetail.value = log
  showLogDetailModal.value = true
}

function formatSnapshot(jsonStr) {
  try {
    const obj = typeof jsonStr === 'string' ? JSON.parse(jsonStr) : jsonStr
    return JSON.stringify(obj, null, 2)
  } catch { return jsonStr }
}

function confirmRollback(log) {
  const count = log.record_id ? log.record_id.split(',').length : 0
  rollbackTarget.value = log
  rollbackMessage.value = `确定要回滚此次操作吗？将恢复 ${count} 条记录到操作前的状态。`
  showRollbackConfirm.value = true
}

async function executeRollback() {
  if (!rollbackTarget.value) return
  rollbackLoading.value = true
  try {
    const res = await axios.post(`${API}/rollback`, { log_id: rollbackTarget.value.id })
    if (res.data?.success) {
      showRollbackConfirm.value = false
      fetchRecords()
      fetchLogs()
    } else {
      alert(res.data?.error || '回滚失败')
    }
  } catch (e) {
    alert(e.response?.data?.error || '回滚失败')
  } finally { rollbackLoading.value = false }
}

onMounted(() => {
  fetchMonths()
  fetchRecords()
  fetchLogs()
})
</script>

<style scoped>
.dm-tab { display: flex; flex-direction: column; gap: 20px; }

/* 复用 Admin 风格 */
.content-card { background: var(--bg-card); border-radius: 8px; border: 1px solid var(--border-lighter); }
.card-header { display: flex; align-items: center; justify-content: space-between; padding: 16px 20px; border-bottom: 1px solid var(--border-lighter); }
.card-header h3 { font-size: 15px; font-weight: 600; margin: 0; }
.header-actions { display: flex; gap: 8px; }
.card-body { padding: 16px 20px; }

/* 按钮 */
.btn { padding: 6px 14px; border-radius: 6px; font-size: 13px; cursor: pointer; border: none; font-weight: 500; transition: all 0.15s; }
.btn-primary { background: var(--primary-500); color: #fff; }
.btn-primary:hover { background: var(--primary-600); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-secondary { background: var(--bg-card); color: var(--text-primary); border: 1px solid var(--border-lighter); }
.btn-secondary:hover { border-color: var(--primary-300); }
.btn-danger { background: var(--danger, #ef4444); color: #fff; }
.btn-danger:hover:not(:disabled) { background: var(--danger-dark, #dc2626); }
.btn-sm { padding: 4px 10px; font-size: 12px; }
.btn-text { background: none; border: none; color: var(--primary-500); cursor: pointer; padding: 2px 6px; font-size: 13px; }
.btn-text:hover { text-decoration: underline; }
.btn-text.danger { color: var(--danger, #ef4444); }

/* 上传区 */
.upload-area { border: 2px dashed var(--border-lighter); border-radius: 8px; padding: 24px; text-align: center; cursor: pointer; transition: all 0.2s; }
.upload-area:hover { border-color: var(--primary-300); background: var(--primary-50, rgba(59,130,246,0.05)); }
.upload-content { display: flex; flex-direction: column; align-items: center; gap: 8px; color: var(--text-secondary); }
.upload-content svg { color: var(--primary-400); }
.upload-hint { font-size: 12px; color: var(--text-tertiary); }
.upload-progress { text-align: center; color: var(--primary-500); padding: 8px; font-size: 13px; }
.upload-result { padding: 8px 12px; border-radius: 6px; font-size: 13px; margin-top: 8px; }
.upload-result.success { background: rgba(34,197,94,0.1); color: #16a34a; }
.upload-result.error { background: rgba(239,68,68,0.1); color: #ef4444; }

/* 延期/返工/超时检测结果 */
.hint-text { font-size: 13px; color: var(--text-secondary); margin: 0 0 12px; }
.detect-result { margin-top: 12px; padding: 12px; background: var(--bg-secondary, #f8fafc); border-radius: 6px; font-size: 13px; }
.detect-summary { display: flex; gap: 16px; margin-bottom: 8px; font-weight: 500; }
.batch-info { color: var(--text-secondary); margin-bottom: 4px; }
.batch-name { font-weight: 500; color: var(--text-primary); }
.not-found { color: var(--text-tertiary); margin-top: 8px; font-size: 12px; }

/* 过滤栏 */
.filter-row { display: flex; gap: 12px; align-items: flex-end; flex-wrap: wrap; margin-bottom: 16px; }
.form-group { display: flex; flex-direction: column; gap: 4px; }
.form-label { font-size: 12px; color: var(--text-secondary); font-weight: 500; }
.form-input, .form-select, .form-textarea { padding: 6px 10px; border: 1px solid var(--border-lighter); border-radius: 6px; font-size: 13px; background: var(--bg-card); color: var(--text-primary); min-width: 120px; }
.form-input:focus, .form-select:focus, .form-textarea:focus { outline: none; border-color: var(--primary-400); }
.form-textarea { resize: vertical; min-width: 240px; }
.filter-actions { flex-direction: row; gap: 8px; }

/* 批量操作栏 */
.action-bar { display: flex; align-items: center; gap: 12px; padding: 8px 12px; background: var(--primary-50, rgba(59,130,246,0.05)); border-radius: 6px; margin-bottom: 12px; font-size: 13px; flex-wrap: wrap; }
.action-bar-label { font-weight: 500; white-space: nowrap; }
.action-bar-right { display: flex; gap: 8px; margin-left: auto; }
.quick-actions { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.quick-group { display: flex; align-items: center; gap: 6px; }
.quick-label { font-size: 12px; color: var(--text-secondary); font-weight: 500; white-space: nowrap; }
.quick-separator { width: 1px; height: 20px; background: var(--border-lighter); }
.form-select-sm { padding: 4px 8px; font-size: 12px; min-width: 130px; }
.btn-warning { background: #f59e0b; color: #fff; }
.btn-warning:hover:not(:disabled) { background: #d97706; }
.btn-outline { background: transparent; color: var(--text-primary); border: 1px solid var(--border-lighter); }
.btn-outline:hover:not(:disabled) { border-color: var(--primary-300); color: var(--primary-500); }

/* 操作日志 */
.log-type-badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 500; }
.log-type-update { background: #dbeafe; color: #1d4ed8; }
.log-type-batch_update { background: #fef3c7; color: #92400e; }
.log-type-delete { background: #fee2e2; color: #991b1b; }
.log-type-batch_delete { background: #fecaca; color: #991b1b; }
.log-type-create { background: #d1fae5; color: #065f46; }
.log-type-rollback { background: #e0e7ff; color: #3730a3; }
.log-content-cell { max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.modal-large { width: 700px; }
.snapshot-section { margin-top: 12px; }
.snapshot-json { background: var(--bg-secondary, #f8fafc); padding: 12px; border-radius: 6px; font-size: 12px; max-height: 300px; overflow: auto; white-space: pre-wrap; word-break: break-all; margin: 8px 0 0; }
.btn-text.disabled { opacity: 0.4; cursor: not-allowed; pointer-events: none; }

/* 表格 */
.table-wrapper { overflow-x: auto; }
.data-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.data-table th, .data-table td { padding: 8px 12px; text-align: left; border-bottom: 1px solid var(--border-lighter); white-space: nowrap; max-width: 200px; overflow: hidden; text-overflow: ellipsis; }
.data-table th { font-weight: 600; color: var(--text-secondary); font-size: 12px; background: var(--bg-secondary, #f8fafc); }
.data-table th.sortable { cursor: pointer; user-select: none; }
.data-table th.sortable:hover { color: var(--primary-500); }
.data-table th.active { color: var(--primary-500); }
.data-table tr:hover { background: var(--bg-secondary, #f8fafc); }
.data-table tr.selected { background: var(--primary-50, rgba(59,130,246,0.05)); }
.sort-arrow { font-size: 11px; }
.col-check { width: 36px; text-align: center; }
.col-actions { width: 100px; text-align: center; }
.center-cell { text-align: center; padding: 24px; color: var(--text-tertiary); }

/* 分页 */
.pagination { display: flex; align-items: center; justify-content: center; gap: 12px; padding: 12px 0; font-size: 13px; }
.page-info { color: var(--text-secondary); }

/* 模态框 */
.modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); z-index: 1000; display: flex; align-items: center; justify-content: center; }
.modal-content { background: var(--bg-card); border-radius: 12px; width: 560px; max-height: 80vh; display: flex; flex-direction: column; }
.modal-small { width: 400px; }
.modal-header { display: flex; align-items: center; justify-content: space-between; padding: 16px 20px; border-bottom: 1px solid var(--border-lighter); }
.modal-header h3 { font-size: 15px; margin: 0; }
.close-btn { background: none; border: none; font-size: 20px; cursor: pointer; color: var(--text-tertiary); padding: 0; line-height: 1; }
.close-btn:hover { color: var(--text-primary); }
.modal-body { padding: 16px 20px; overflow-y: auto; flex: 1; }
.modal-body-scroll { max-height: 50vh; overflow-y: auto; }
.modal-body p { margin: 0 0 12px; font-size: 14px; }
.modal-body .form-group { margin-bottom: 12px; }
.modal-body .form-input, .modal-body .form-select, .modal-body .form-textarea { width: 100%; min-width: unset; }
.modal-footer { display: flex; justify-content: flex-end; gap: 8px; padding: 12px 20px; border-top: 1px solid var(--border-lighter); }

@media (max-width: 768px) {
  .filter-row { flex-direction: column; }
  .form-input, .form-select { min-width: unset; width: 100%; }
  .modal-content { width: 95vw; }
}
</style>