<template>
  <div class="cyw-ledger-tab">
    <div class="page-header">
      <div>
        <h2>问题台账</h2>
        <p class="page-sub">共 {{ total }} 条；登记即视为已派发，部门反馈即办结。台账数据用于趋势分析，不作为部门考核依据。</p>
      </div>
      <div>
        <el-button type="primary" @click="importVisible = true">Excel 一键导入</el-button>
        <el-button @click="load">刷新</el-button>
      </div>
    </div>

    <el-card shadow="never" class="filter-card">
      <div class="filter-row">
        <el-select v-model="filters.status" placeholder="状态" clearable style="width: 120px" @change="load">
          <el-option v-for="s in statusOptions" :key="s" :label="s" :value="s" />
        </el-select>
        <el-select v-model="filters.type_id" placeholder="问题类型" clearable style="width: 140px" @change="load">
          <el-option v-for="t in types" :key="t.id" :label="t.name" :value="t.id" />
        </el-select>
        <el-select v-model="filters.dept_id" placeholder="派发部门" clearable style="width: 130px" @change="load">
          <el-option v-for="d in depts" :key="d.id" :label="d.name" :value="d.id" />
        </el-select>
        <el-date-picker
          v-model="filters.dateRange"
          type="daterange"
          value-format="YYYY-MM-DD"
          start-placeholder="发现日期起"
          end-placeholder="止"
          style="width: 240px"
          @change="load"
        />
        <el-input
          v-model="filters.keyword"
          placeholder="案件编号/描述/点位"
          clearable
          style="width: 200px"
          @keyup.enter="load"
          @clear="load"
        />
        <el-button type="primary" @click="load">查询</el-button>
        <el-button @click="resetFilters">重置</el-button>
      </div>
    </el-card>

    <el-card shadow="never">
      <el-table :data="issues" v-loading="loading" border stripe row-key="id">
        <el-table-column prop="case_no" label="案件编号" width="150" fixed="left" />
        <el-table-column label="发现时间" width="145">
          <template #default="{ row }">{{ row.found_at?.slice(5, 16) }}</template>
        </el-table-column>
        <el-table-column label="点位" min-width="170">
          <template #default="{ row }">
            <b>{{ row.monitor_no }}</b> {{ row.spot_name }}
            <el-tag v-if="row.is_key" type="danger" size="small" effect="plain">重点</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="type_name" label="类型" width="90" />
        <el-table-column label="派发部门" width="100">
          <template #default="{ row }">
            <span v-if="row.dept_name" class="host-tag" :style="{ borderColor: row.dept_color }">
              {{ row.dept_name }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="反馈" width="110">
          <template #default="{ row }">
            <span v-if="row.is_fed" class="fed-all">已于 {{ row.fed_at?.slice(5, 16) }} 反馈</span>
            <span v-else class="unfed-names">待反馈</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="照片" width="70" align="center">
          <template #default="{ row }">
            <span v-if="row.photos?.length">{{ row.photos.length }} 张</span>
            <span v-else>—</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="genSlip(row)">详单</el-button>
            <el-button link type="primary" @click="openFeedback(row)">
              {{ row.is_fed ? '查看/更正反馈' : '反馈' }}
            </el-button>
            <el-button v-if="row.status === '处置中'" link type="info" @click="openEdit(row)">编辑</el-button>
            <el-popconfirm
              v-if="row.status === '处置中'"
              title="登记错误才删除，删除后不可恢复，确认？"
              confirm-button-text="删除"
              @confirm="remove(row)"
            >
              <template #reference>
                <el-button link type="danger">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
      <div class="pager">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          :page-sizes="[20, 50, 100]"
          @current-change="load"
          @size-change="load"
        />
      </div>
    </el-card>

    <!-- 反馈回填：派发部门单部门反馈 -->
    <el-dialog v-model="fbDialog.visible" title="回填处置反馈" width="640px">
      <div v-if="fbDialog.issue">
        <p class="fb-title">
          案件 <b>{{ fbDialog.issue.case_no }}</b>（{{ fbDialog.issue.spot_name }} · {{ fbDialog.issue.type_name }}）
          <el-tag :type="statusTagType(fbDialog.issue.status)" size="small" style="margin-left: 8px">
            {{ fbDialog.issue.status }}
          </el-tag>
        </p>
        <div class="fb-dept">
          <div class="fb-dept-head">
            <span class="dept-dot" :style="{ background: fbDialog.issue.dept_color }"></span>
            <b>{{ fbDialog.issue.dept_name }}</b>
            <el-tag v-if="fbDialog.issue.is_fed" type="success" size="small">
              已于 {{ fbDialog.issue.fed_at }} 反馈
            </el-tag>
            <el-tag v-else type="info" size="small">待反馈</el-tag>
          </div>
          <template v-if="fbDialog.issue.is_fed">
            <div class="fb-done-note">{{ fbDialog.issue.feedback_note || '（未填写说明）' }}</div>
            <div v-if="fbDialog.issue.feedback_photos?.length" class="fb-photos">
              <el-image
                v-for="(p, i) in fbDialog.issue.feedback_photos"
                :key="p.url"
                :src="p.url"
                :preview-src-list="fbDialog.issue.feedback_photos.map((x) => x.url)"
                :initial-index="i"
                fit="cover"
              />
            </div>
            <p class="fb-tip">已反馈内容留档展示；重新保存只更新反馈内容，首次办结时间不变</p>
          </template>
          <template v-else>
            <el-input
              v-model="fbDialog.draft.note"
              type="textarea"
              :rows="3"
              placeholder="群内反馈内容（单位+事项+完成情况）"
            />
            <div class="fb-actions">
              <el-upload
                action="/api/cyw/upload-image"
                :headers="uploadHeaders"
                :on-success="onFbUploadSuccess"
                :show-file-list="false"
                multiple
                accept="image/*"
              >
                <el-button size="small" plain>上传反馈照片</el-button>
              </el-upload>
              <span v-if="fbDialog.draft.photos.length" class="fb-photo-count">
                已选 {{ fbDialog.draft.photos.length }} 张
              </span>
              <el-button size="small" type="primary" :loading="fbDialog.saving" @click="saveFeedback">
                保存反馈
              </el-button>
            </div>
          </template>
        </div>
        <p class="fb-tip">保存反馈即视为该问题已办结；已办结的案件仍可再反馈一次作为更正通道。</p>
      </div>
    </el-dialog>

    <!-- 历史台账 Excel 一键导入 -->
    <el-dialog v-model="importVisible" title="导入历史问题台账" width="860px">
      <template v-if="!importState.preview">
        <el-upload drag :http-request="onImportFile" :show-file-list="false" accept=".xlsx,.xls">
          <div class="import-drop">
            <p>将历史台账 Excel 拖到此处，或<b>点击选择文件</b></p>
            <p class="import-tip">
              支持每月一个工作表（如"1月""2月"）的台账格式：表头需含「点位/问题描述」列；<br>
              日期列仅每天首行有值即可（自动向下填充）；点位列 = 监控序号 + 名称连写（无序号按名称匹配）；<br>
              处置单位按台账原名入库（如"环卫中心""夜市"，字典没有的单位自动创建）；<br>
              处置结果非空视为已办结（含处理时间），空着按「处置中」入库（单位未反馈，之后可在台账页回填反馈）；重复导入不会重复入库。
            </p>
          </div>
        </el-upload>
      </template>
      <template v-else>
        <el-alert type="info" :closable="false"
          :title="`识别 ${importState.preview.sheets.join('、')} 共 ${importState.preview.total} 条案件`" />
        <el-alert v-if="importState.preview.skipped_sheets?.length" type="info" :closable="false" style="margin-top: 8px"
          :title="`已跳过 ${importState.preview.skipped_sheets.length} 个工作表：${importState.preview.skipped_sheets.map(s => s.sheet).join('、')}（仅导入按月份命名的工作表）`" />
        <el-alert v-if="importState.preview.stats.new_spot_count || importState.preview.stats.new_dept_count"
          type="warning" :closable="false" style="margin-top: 8px"
          :title="`将自动创建 ${importState.preview.stats.new_spot_count} 个缺失点位、${importState.preview.stats.new_dept_count} 个缺失单位：${[...importState.preview.new_spots.slice(0, 5), ...importState.preview.new_depts.slice(0, 5)].join('、')}${importState.preview.stats.new_spot_count + importState.preview.stats.new_dept_count > 10 ? ' 等' : ''}`" />
        <el-alert v-if="importState.preview.stats.unmatched_type" type="warning" :closable="false" style="margin-top: 8px"
          :title="`${importState.preview.stats.unmatched_type} 条描述未能自动识别问题类型，将按下方回退类型入库`">
          <div style="margin-top: 8px">
            回退类型：
            <el-select v-model="importState.fallbackTypeId" size="small" style="width: 160px">
              <el-option v-for="t in types" :key="t.id" :label="t.name" :value="t.id" />
            </el-select>
          </div>
        </el-alert>
        <el-alert v-if="importState.preview.stats.no_result" type="warning" :closable="false" style="margin-top: 8px"
          :title="`${importState.preview.stats.no_result} 条没有处置结果，将按「处置中」入库`" />
        <el-alert v-if="importState.preview.stats.dup_in_file" type="warning" :closable="false" style="margin-top: 8px"
          :title="`文件内有 ${importState.preview.stats.dup_in_file} 条重复记录，导入时自动跳过`" />
        <el-alert v-if="importState.preview.invalid?.length" type="error" :closable="false" style="margin-top: 8px"
          :title="`${importState.preview.invalid.length} 行无法解析被跳过：${importState.preview.invalid.slice(0, 3).map(x => x.reason).join('；')}`" />
        <p style="margin: 12px 0 8px">预览前 10 条：</p>
        <el-table :data="importState.preview.preview" border size="small" max-height="300">
          <el-table-column prop="sheet" label="来源" width="60" />
          <el-table-column label="发现时间" width="145">
            <template #default="{ row }">{{ row.found_at?.slice(0, 16) }}</template>
          </el-table-column>
          <el-table-column prop="spot_text" label="点位" min-width="180" show-overflow-tooltip />
          <el-table-column label="单位" width="90">
            <template #default="{ row }">
              {{ row.dept_name }}
              <el-tag v-if="row.dept_new" type="warning" size="small" effect="plain">新建</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="类型" width="90">
            <template #default="{ row }">
              <span v-if="row.type_name === '未识别'" style="color: #e6a23c">未识别</span>
              <template v-else>{{ row.type_name }}</template>
            </template>
          </el-table-column>
          <el-table-column prop="description" label="问题描述" min-width="150" show-overflow-tooltip />
          <el-table-column label="处置结果/状态" min-width="130" show-overflow-tooltip>
            <template #default="{ row }">
              <el-tag :type="row.status === '已办结' ? 'success' : 'info'" size="small">{{ row.status }}</el-tag>
              <span v-if="row.result_raw" style="margin-left: 6px; color: #909399">{{ row.result_raw }}</span>
            </template>
          </el-table-column>
        </el-table>
      </template>
      <template #footer>
        <el-button @click="resetImport">重新选择</el-button>
        <el-button v-if="importState.preview" type="primary" :loading="importState.saving"
          :disabled="!!(importState.preview.stats.unmatched_type && !importState.fallbackTypeId)"
          @click="confirmImport">
          确认导入（{{ importState.preview.total }} 条）
        </el-button>
      </template>
    </el-dialog>

    <!-- 编辑（仅处置中可改） -->
    <el-dialog v-model="editDialog.visible" title="编辑问题" width="640px">
      <el-form :model="editDialog.form" label-width="90px">
        <el-form-item label="点位" required>
          <el-select v-model="editDialog.form.spot_id" filterable style="width: 100%">
            <el-option
              v-for="s in editDialog.spots"
              :key="s.id"
              :label="`${s.monitor_no} ${s.name}`"
              :value="s.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="问题类型" required>
          <el-select v-model="editDialog.form.type_id" style="width: 100%">
            <el-option v-for="t in editDialog.types" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="派发部门" required>
          <el-select v-model="editDialog.form.dept_id" style="width: 100%">
            <el-option v-for="d in editDialog.depts" :key="d.id" :label="d.name" :value="d.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="发现时间">
          <el-date-picker
            v-model="editDialog.form.found_at"
            type="datetime"
            value-format="YYYY-MM-DD HH:mm:ss"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="问题描述" required>
          <el-input v-model="editDialog.form.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="editDialog.saving" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import axios from 'axios'


const statusOptions = ['处置中', '已办结']
const statusTagType = (s) => ({ '处置中': 'warning', '已办结': 'success' }[s] || 'info')

const issues = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const types = ref([])
const depts = ref([])
const uploadHeaders = computed(() => ({ Authorization: `Bearer ${localStorage.getItem('token')}` }))
const route = useRoute()
const router = useRouter()

const filters = reactive({
  status: '', type_id: '', dept_id: '', dateRange: null, keyword: ''
})

// 编辑中的问题 id（openEdit 时记录）
const currentEditId = ref(null)

async function load() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (filters.status) params.status = filters.status
    if (filters.type_id) params.type_id = filters.type_id
    if (filters.dept_id) params.dept_id = filters.dept_id
    if (filters.keyword.trim()) params.keyword = filters.keyword.trim()
    if (filters.dateRange?.length === 2) {
      params.date_from = filters.dateRange[0]
      params.date_to = filters.dateRange[1]
    }
    const { data } = await axios.get('/api/cyw/issues', { params })
    issues.value = data.issues || []
    total.value = data.total || 0
  } catch { /* error toast via interceptor */ }
  finally { loading.value = false }
}

function resetFilters() {
  filters.status = ''
  filters.type_id = ''
  filters.dept_id = ''
  filters.dateRange = null
  filters.keyword = ''
  page.value = 1
  load()
}

// 数据分析页跳转带过来的过滤条件：keyword 直接模糊匹配，type_name/dept_name 回查成 id，
// date/date_from+date_to 还原统计区间。应用后清掉 query，避免刷新时条件重复叠加
function applyQueryFilters() {
  const q = route.query
  if (!q || !Object.keys(q).length) return
  if (q.keyword) filters.keyword = String(q.keyword)
  if (q.type_name) {
    const t = types.value.find(x => x.name === q.type_name)
    if (t) filters.type_id = String(t.id)
  }
  if (q.dept_name) {
    const d = depts.value.find(x => x.name === q.dept_name)
    if (d) filters.dept_id = String(d.id)
  }
  if (q.date_from && q.date_to) filters.dateRange = [String(q.date_from), String(q.date_to)]
  else if (q.date) filters.dateRange = [String(q.date), String(q.date)]
  router.replace({ path: '/cyw/ledger', query: {} })
}

// ---- 详单 ----
async function genSlip(row) {
  try {
    const { data } = await axios.post(`/api/cyw/issues/${row.id}/slip`)
    if (data.success) {
      window.open(data.url, '_blank')
      ElMessage.success('详单已生成，请下载后发到处置群并@相关单位')
    }
  } catch { /* error toast via interceptor */ }
}

// ---- 删除 ----
async function remove(row) {
  try {
    await axios.delete(`/api/cyw/issues/${row.id}`)
    ElMessage.success('已删除')
    load()
  } catch { /* error toast via interceptor */ }
}

// ---- 反馈 ----
const fbDialog = reactive({ visible: false, issue: null, draft: { note: '', photos: [] }, saving: false })

async function openFeedback(row) {
  try {
    const { data } = await axios.get(`/api/cyw/issues/${row.id}`)
    fbDialog.issue = data.issue
    fbDialog.draft = { note: '', photos: [] }
    fbDialog.visible = true
  } catch { /* error toast via interceptor */ }
}

function onFbUploadSuccess(res) {
  if (res?.success && res.url) {
    fbDialog.draft.photos.push({ name: res.name || '照片', url: res.url })
  }
}

async function saveFeedback() {
  if (!fbDialog.draft.note.trim() && !fbDialog.draft.photos.length) {
    return ElMessage.warning('请填写反馈说明或上传反馈照片')
  }
  fbDialog.saving = true
  try {
    await axios.post(`/api/cyw/issues/${fbDialog.issue.id}/feedback`, {
      feedback_note: fbDialog.draft.note.trim(),
      feedback_photos: fbDialog.draft.photos
    })
    ElMessage.success(`${fbDialog.issue.dept_name} 反馈已回填，问题已办结`)
    await openFeedback({ id: fbDialog.issue.id })
    load()
  } catch { /* error toast via interceptor */ }
  finally { fbDialog.saving = false }
}

// ---- 编辑 ----
const editDialog = reactive({
  visible: false,
  form: { spot_id: null, type_id: null, dept_id: null, found_at: '', description: '' },
  spots: [], types: [], depts: [], saving: false
})

async function openEdit(row) {
  currentEditId.value = row.id
  try {
    const [detail, spotsRes, typesRes, deptsRes] = await Promise.all([
      axios.get(`/api/cyw/issues/${row.id}`),
      axios.get('/api/cyw/spots', { params: { page_size: 200 } }),
      axios.get('/api/cyw/types'),
      axios.get('/api/cyw/depts')
    ])
    editDialog.spots = spotsRes.data.spots || []
    editDialog.types = typesRes.data.types || []
    editDialog.depts = deptsRes.data.depts || []
    const i = detail.data.issue
    editDialog.form = {
      spot_id: i.spot_id,
      type_id: i.type_id,
      dept_id: i.dept_id,
      found_at: i.found_at,
      description: i.description
    }
    editDialog.visible = true
  } catch { /* error toast via interceptor */ }
}

async function submitEdit() {
  if (!editDialog.form.dept_id) return ElMessage.warning('请选择派发部门')
  if (!editDialog.form.description?.trim()) return ElMessage.warning('请填写问题描述')
  editDialog.saving = true
  try {
    const f = editDialog.form
    await axios.put(`/api/cyw/issues/${currentEditId.value}`, f)
    ElMessage.success('已保存')
    editDialog.visible = false
    load()
  } catch { /* error toast via interceptor */ }
  finally { editDialog.saving = false }
}

// ---- 历史台账一键导入（两段式：预览 → 确认） ----
const importVisible = ref(false)
const importState = reactive({ preview: null, saving: false, fallbackTypeId: null })

async function onImportFile({ file }) {
  const fd = new FormData()
  fd.append('file', file)
  try {
    const { data } = await axios.post('/api/cyw/issues/import', fd)
    importState.preview = data
    // 未识别描述的回退类型：优先「其他」，没有再退回第一个类型
    importState.fallbackTypeId = types.value.find(t => t.name === '其他')?.id || types.value[0]?.id || null
  } catch { /* error toast via interceptor */ }
}

function resetImport() {
  importState.preview = null
}

async function confirmImport() {
  importState.saving = true
  try {
    const { data } = await axios.post('/api/cyw/issues/import/confirm', {
      rows: importState.preview.rows,
      fallback_type_id: importState.fallbackTypeId
    })
    ElMessage.success(`导入完成：新增 ${data.inserted} 条，重复跳过 ${data.skipped_dup} 条`
      + `（自动创建点位 ${data.created_spots} 个、单位 ${data.created_depts} 个）`)
    importVisible.value = false
    importState.preview = null
    load()
  } catch { /* error toast via interceptor */ }
  finally { importState.saving = false }
}

onMounted(async () => {
  // 字典就绪后再应用 URL 查询条件（数据分析页跳转带 type_name/dept_name），否则按名字回查 id 会落空
  const [typesRes, deptsRes] = await Promise.all([
    axios.get('/api/cyw/types').catch(() => ({ data: {} })),
    axios.get('/api/cyw/depts').catch(() => ({ data: {} }))
  ])
  types.value = typesRes.data.types || []
  depts.value = deptsRes.data.depts || []
  applyQueryFilters()
  load()
})
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}
.page-header h2 { margin: 0 0 4px; }
.page-sub { margin: 0; color: #909399; font-size: 13px; }
.filter-card { margin-bottom: 12px; }
.filter-row { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
.pager { display: flex; justify-content: flex-end; margin-top: 12px; }
.host-tag {
  border: 1px solid;
  border-radius: 3px;
  padding: 0 6px;
  font-size: 12px;
  color: #606266;
}
.fed-all { color: #67c23a; }
.unfed-names { color: #f56c6c; font-size: 12px; }
.fb-title { margin: 0 0 12px; }
.fb-dept { border: 1px solid #ebeef5; border-radius: 6px; padding: 12px; margin-bottom: 12px; }
.fb-dept-head { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.fb-done-note { color: #606266; font-size: 13px; margin-bottom: 8px; white-space: pre-wrap; }
.fb-photos { display: flex; gap: 8px; flex-wrap: wrap; }
.fb-photos .el-image { width: 90px; height: 70px; border-radius: 4px; border: 1px solid #ebeef5; }
.fb-actions { display: flex; align-items: center; gap: 10px; margin-top: 8px; }
.fb-photo-count { color: #909399; font-size: 12px; }
.fb-tip { color: #909399; font-size: 12px; margin: 4px 0 0; }
.dept-dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  margin-right: 5px;
  vertical-align: middle;
}
</style>
