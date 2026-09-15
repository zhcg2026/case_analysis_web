<template>
  <div class="data-stats-page">
    <div class="page-header">
      <div>
        <h2>统计查询</h2>
        <p class="page-sub">按条件汇总处置部门案件量；点数字反查明细（只读）。口径与考核一致：结案=阶段[办结]；超时/延期/返工取对应字段。</p>
      </div>
    </div>

    <el-card shadow="never" class="filter-card">
      <div class="filters">
        <div v-for="(f, i) in filters" :key="i" class="filter-row">
          <el-select v-model="f.field" style="width: 140px" @change="onFieldChange(f)">
            <el-option v-for="opt in fieldOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
          </el-select>
          <el-select v-model="f.op" style="width: 100px">
            <el-option v-for="op in opsFor(f.field)" :key="op.value" :label="op.label" :value="op.value" />
          </el-select>
          <!-- 多值任务号 -->
          <el-input
            v-if="f.field === 'task_no' && f.op === 'in'"
            v-model="f.text"
            placeholder="多个任务号，逗号分隔"
            style="flex: 1; min-width: 180px"
          />
          <!-- 日期时间 -->
          <template v-else-if="isDateField(f.field)">
            <template v-if="f.op === 'between'">
              <el-date-picker v-model="f.from" type="datetime" style="width: 170px" placeholder="开始" value-format="YYYY-MM-DD HH:mm:ss" />
              <el-date-picker v-model="f.to" type="datetime" style="width: 170px" placeholder="结束" value-format="YYYY-MM-DD HH:mm:ss" />
            </template>
            <el-date-picker
              v-else
              v-model="f.value"
              type="datetime"
              style="flex: 1; min-width: 160px"
              placeholder="选择时间"
              value-format="YYYY-MM-DD HH:mm:ss"
            />
          </template>
          <!-- 布尔 -->
          <el-select v-else-if="isBoolField(f.field)" v-model="f.text" style="flex: 1; min-width: 120px">
            <el-option label="是" value="1" />
            <el-option label="否" value="0" />
          </el-select>
          <!-- 下拉 -->
          <el-select
            v-else-if="selectField(f.field)"
            v-model="f.text"
            filterable
            allow-create
            clearable
            style="flex: 1; min-width: 140px"
            :placeholder="selectField(f.field).placeholder"
          >
            <el-option v-for="v in selectField(f.field).options" :key="v" :label="v" :value="v" />
          </el-select>
          <!-- 文本 -->
          <el-input v-else v-model="f.text" clearable style="flex: 1; min-width: 140px" placeholder="输入值" />
          <el-button type="danger" link @click="filters.splice(i, 1)">删除</el-button>
        </div>
        <div class="filter-actions">
          <el-button @click="addFilter">＋ 添加条件</el-button>
          <el-button type="primary" :loading="loading" @click="runQuery">查询</el-button>
        </div>
      </div>
    </el-card>

    <el-card v-if="resultReady" shadow="never" class="result-card">
      <el-tabs v-model="resultTab">
        <el-tab-pane label="统计结果" name="agg">
          <div class="sum-strip">
            <span>合计 应处置 <b>{{ summary.total }}</b></span>
            <span>结案 <b>{{ summary.closed }}</b></span>
            <span>待处置 <b>{{ summary.pending }}</b></span>
            <span>结案率 <b>{{ summary.close_rate }}%</b></span>
            <span>超时 <b>{{ summary.overtime }}</b></span>
            <span>延期 <b>{{ summary.delayed }}</b></span>
            <span>返工 <b>{{ summary.rework }}</b></span>
          </div>
          <el-table :data="aggRows" border stripe size="small" v-loading="loading">
            <el-table-column prop="department" label="处置部门" min-width="140" fixed="left" />
            <el-table-column label="应处置数" width="100" align="center">
              <template #default="{ row }">
                <el-link type="primary" :underline="false" @click="openDetail(row.department, null)">{{ row.total }}</el-link>
              </template>
            </el-table-column>
            <el-table-column label="结案数" width="90" align="center">
              <template #default="{ row }">
                <el-link type="success" :underline="false" @click="openDetail(row.department, 'closed')">{{ row.closed }}</el-link>
              </template>
            </el-table-column>
            <el-table-column label="待处置数" width="100" align="center">
              <template #default="{ row }">
                <el-link type="warning" :underline="false" @click="openDetail(row.department, 'pending')">{{ row.pending }}</el-link>
              </template>
            </el-table-column>
            <el-table-column label="结案率" width="90" align="center">
              <template #default="{ row }">{{ row.close_rate }}%</template>
            </el-table-column>
            <el-table-column label="超时数" width="90" align="center">
              <template #default="{ row }">
                <el-link type="danger" :underline="false" @click="openDetail(row.department, 'overtime')">{{ row.overtime }}</el-link>
              </template>
            </el-table-column>
            <el-table-column label="延期数" width="90" align="center">
              <template #default="{ row }">
                <el-link type="danger" :underline="false" @click="openDetail(row.department, 'delayed')">{{ row.delayed }}</el-link>
              </template>
            </el-table-column>
            <el-table-column label="返工数" width="90" align="center">
              <template #default="{ row }">
                <el-link type="danger" :underline="false" @click="openDetail(row.department, 'rework')">{{ row.rework }}</el-link>
              </template>
            </el-table-column>
            <template #empty><span>无统计数据</span></template>
          </el-table>
        </el-tab-pane>

        <el-tab-pane :label="detailTabLabel" name="detail">
          <div v-if="detailContext" class="detail-ctx">
            反查明细（只读）
            <template v-if="detailContext.department"> · 部门：{{ detailContext.department }}</template>
            <template v-if="detailContext.metric"> · 指标：{{ detailContext.metricLabel }}</template>
            <el-button size="small" style="margin-left: 12px" @click="backToAgg">返回统计</el-button>
          </div>
          <el-table :data="detailRows" border stripe size="small" v-loading="detailLoading">
            <el-table-column prop="task_no" label="任务号" width="110" />
            <el-table-column prop="report_time" label="上报时间" width="150" />
            <el-table-column prop="deadline" label="处置截止" width="150" />
            <el-table-column prop="department" label="处置部门" width="120" show-overflow-tooltip />
            <el-table-column prop="source" label="问题来源" width="100" show-overflow-tooltip />
            <el-table-column prop="stage" label="当前阶段" width="100" show-overflow-tooltip />
            <el-table-column prop="address" label="地址" min-width="140" show-overflow-tooltip />
            <el-table-column prop="description" label="问题描述" min-width="160" show-overflow-tooltip />
            <el-table-column label="标志" width="140" align="center">
              <template #default="{ row }">
                <el-tag v-if="row.is_overtime == 1" type="danger" size="small" style="margin:1px">超时</el-tag>
                <el-tag v-if="row.is_delayed == 1" type="warning" size="small" style="margin:1px">延期</el-tag>
                <el-tag v-if="row.is_rework == 1" type="danger" size="small" style="margin:1px">返工</el-tag>
                <span v-if="!row.is_overtime && !row.is_delayed && !row.is_rework">—</span>
              </template>
            </el-table-column>
            <template #empty><span>无明细</span></template>
          </el-table>
          <el-pagination
            style="margin-top: 12px; justify-content: flex-end"
            v-model:current-page="detailPage"
            v-model:page-size="detailPageSize"
            :total="detailTotal"
            :page-sizes="[20, 50, 100]"
            layout="total, sizes, prev, pager, next"
            @current-change="loadDetail"
            @size-change="loadDetail"
          />
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'

const fieldOptions = [
  { value: 'task_no', label: '任务号' },
  { value: 'report_time', label: '上报时间' },
  { value: 'deadline', label: '处置截止时间' },
  { value: 'department', label: '处置部门' },
  { value: 'source', label: '问题来源' },
  { value: 'stage', label: '当前阶段名称' },
  { value: 'address', label: '地址描述' },
  { value: 'description', label: '问题描述' },
  { value: 'is_delayed', label: '延期案件' },
  { value: 'is_rework', label: '返工案件' },
  { value: 'is_overtime', label: '超时案件' },
  { value: 'upload_batch', label: '月份批次' }
]

const DATE_FIELDS = new Set(['report_time', 'deadline'])
const BOOL_FIELDS = new Set(['is_delayed', 'is_rework', 'is_overtime'])

const meta = reactive({ departments: [], sources: [], stages: [], batches: [] })
const filters = ref([])
const loading = ref(false)
const resultReady = ref(false)
const resultTab = ref('agg')
const aggRows = ref([])
const summary = reactive({ total: 0, closed: 0, pending: 0, overtime: 0, delayed: 0, rework: 0, close_rate: 0 })

const detailRows = ref([])
const detailTotal = ref(0)
const detailPage = ref(1)
const detailPageSize = ref(50)
const detailLoading = ref(false)
const detailContext = ref(null)

const metricLabels = { closed: '结案', pending: '待处置', overtime: '超时', delayed: '延期', rework: '返工' }
const detailTabLabel = computed(() => {
  if (detailContext.value?.department) {
    return `反查结果（${detailContext.value.department}）`
  }
  return '反查结果'
})

function isDateField(f) { return DATE_FIELDS.has(f) }
function isBoolField(f) { return BOOL_FIELDS.has(f) }

function opsFor(field) {
  if (field === 'task_no') return [
    { value: 'eq', label: '等于' },
    { value: 'in', label: '多值' }
  ]
  if (DATE_FIELDS.has(field)) return [
    { value: 'eq', label: '等于' },
    { value: 'lt', label: '小于' },
    { value: 'gt', label: '大于' },
    { value: 'between', label: '介于' }
  ]
  if (BOOL_FIELDS.has(field)) return [
    { value: 'eq', label: '等于' },
    { value: 'neq', label: '不等于' }
  ]
  if (['stage', 'address', 'description'].includes(field)) return [
    { value: 'eq', label: '等于' },
    { value: 'contains', label: '包含' },
    { value: 'ncontains', label: '不包含' }
  ]
  if (['department', 'source', 'upload_batch'].includes(field)) return [
    { value: 'eq', label: '等于' }
  ]
  return [{ value: 'eq', label: '等于' }]
}

function selectField(field) {
  if (field === 'department') return { options: meta.departments, placeholder: '选择处置部门' }
  if (field === 'source') return { options: meta.sources, placeholder: '选择问题来源' }
  if (field === 'stage') return { options: meta.stages, placeholder: '选择或输入阶段' }
  if (field === 'upload_batch') return { options: meta.batches, placeholder: '如 202609' }
  return null
}

function onFieldChange(f) {
  const ops = opsFor(f.field)
  if (!ops.find(o => o.value === f.op)) f.op = ops[0].value
  f.value = null
  f.from = null
  f.to = null
  f.text = ''
}

function emptyFilter(field = 'department') {
  return { field, op: 'eq', value: null, from: null, to: null, text: '' }
}

function addFilter() {
  filters.value.push(emptyFilter())
}

function collectFilters() {
  const out = []
  for (const f of filters.value) {
    if (f.field === 'task_no') {
      if (f.op === 'in') {
        if ((f.text || '').trim()) out.push({ field: 'task_no', op: 'in', value: f.text })
      } else if (f.value != null && f.value !== '') {
        out.push({ field: 'task_no', op: 'eq', value: String(f.value).trim() })
      }
      continue
    }
    if (DATE_FIELDS.has(f.field)) {
      if (f.op === 'between') {
        if (f.from && f.to) out.push({ field: f.field, op: 'between', value: [f.from, f.to] })
      } else if (f.value) {
        out.push({ field: f.field, op: f.op, value: f.value })
      }
      continue
    }
    if (BOOL_FIELDS.has(f.field)) {
      if (f.text === '' || f.text == null) continue
      out.push({ field: f.field, op: f.op, value: f.text })
      continue
    }
    const t = (f.text ?? f.value ?? '').toString().trim()
    if (t) out.push({ field: f.field, op: f.op, value: t })
  }
  return out
}

async function loadMeta() {
  try {
    const { data } = await axios.get('/api/data-stats/meta')
    if (data.success) {
      meta.departments = data.departments || []
      meta.sources = data.sources || []
      meta.stages = data.stages || []
      meta.batches = data.batches || []
    }
  } catch (e) { /* ignore */ }
}

async function runQuery() {
  const fs = collectFilters()
  if (!fs.length) {
    ElMessage.warning('请至少设置一个筛选条件')
    return
  }
  loading.value = true
  resultReady.value = true
  resultTab.value = 'agg'
  try {
    const { data } = await axios.post('/api/data-stats/aggregate', { filters: fs })
    if (!data.success) {
      ElMessage.error(data.error || '查询失败')
      return
    }
    aggRows.value = data.rows || []
    Object.assign(summary, data.summary || {})
    detailContext.value = null
    detailRows.value = []
    detailTotal.value = 0
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '查询失败')
  } finally {
    loading.value = false
  }
}

function openDetail(department, metric = null) {
  resultTab.value = 'detail'
  detailPage.value = 1
  detailContext.value = {
    department: department || null,
    metric,
    metricLabel: metric ? metricLabels[metric] : null
  }
  loadDetail()
}

function detailFilters() {
  const fs = collectFilters()
  if (detailContext.value?.department) {
    fs.push({ field: 'department', op: 'eq', value: detailContext.value.department })
  }
  const m = detailContext.value?.metric
  if (m === 'closed') {
    fs.push({ field: 'stage', op: 'eq', value: '[办结]' })
  } else if (m === 'pending') {
    // 待处置 = 非办结，后端用特殊 op 不支持时拆成：不包含办结
    fs.push({ field: 'stage', op: 'ncontains', value: '[办结]' })
  } else if (m === 'overtime') {
    fs.push({ field: 'is_overtime', op: 'eq', value: '1' })
  } else if (m === 'delayed') {
    fs.push({ field: 'is_delayed', op: 'eq', value: '1' })
  } else if (m === 'rework') {
    fs.push({ field: 'is_rework', op: 'eq', value: '1' })
  }
  return fs
}

async function loadDetail() {
  detailLoading.value = true
  try {
    const { data } = await axios.post('/api/data-stats/detail', {
      filters: detailFilters(),
      page: detailPage.value,
      page_size: detailPageSize.value
    })
    if (!data.success) {
      ElMessage.error(data.error || '反查失败')
      return
    }
    detailRows.value = data.rows || []
    detailTotal.value = data.total || 0
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '反查失败')
  } finally {
    detailLoading.value = false
  }
}

function backToAgg() {
  resultTab.value = 'agg'
}

onMounted(() => {
  filters.value.push(emptyFilter('upload_batch'))
  loadMeta()
})
</script>

<style scoped>
.data-stats-page {
  padding: var(--space-5);
}

.page-header {
  margin-bottom: var(--space-4);
}

.page-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
}

.page-sub {
  margin: 6px 0 0;
  font-size: 13px;
  color: var(--text-secondary);
}

.filter-card,
.result-card {
  margin-bottom: var(--space-4);
  border: 1px solid var(--border-lighter);
}

.filters {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.filter-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 8px;
}

.sum-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 12px;
  font-size: 13px;
  color: var(--text-secondary);
}

.sum-strip b {
  color: var(--text-primary);
}

.detail-ctx {
  margin-bottom: 10px;
  font-size: 13px;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  flex-wrap: wrap;
}
</style>
