<template>
  <div class="ipl-page">
    <div class="page-header">
      <div>
        <h2>巡查问题台账</h2>
        <p class="page-sub">
          共 {{ total }} 条。状态只有「待整改 / 已整改」两值；同一路段不同点位的同类问题会分成多条，不合并。
        </p>
      </div>
      <div>
        <el-button @click="exportExcel">导出台账</el-button>
        <el-button type="primary" @click="load">刷新</el-button>
      </div>
    </div>

    <!-- 疑似重复待确认：放最顶部，每天第一件事就是点掉它 -->
    <el-banner v-if="dupTotal > 0" class="dup-banner" type="warning" :closable="false">
      <template #title>
        有 <b>{{ dupTotal }}</b> 条疑似重复待确认（新导入的案件照片与库内已有案件完全相同）。
        <el-button link type="primary" @click="dupVisible = true">立即处理</el-button>
        <el-button link @click="loadDup">刷新</el-button>
      </template>
    </el-banner>

    <el-card shadow="never" class="filter-card">
      <div class="filter-row">
        <el-select v-model="filters.status" placeholder="整改状态" clearable style="width: 120px" @change="load">
          <el-option v-for="s in statusOptions" :key="s" :label="s" :value="s" />
        </el-select>
        <el-select v-model="filters.dept" placeholder="责任单位" clearable style="width: 130px" @change="load">
          <el-option v-for="d in deptOptions" :key="d" :label="d" :value="d" />
        </el-select>
        <el-input v-model="filters.road" placeholder="道路" clearable style="width: 130px" @change="load" />
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
          placeholder="位置/问题/处理结果"
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
      <el-table :data="cases" v-loading="loading" border stripe row-key="id">
        <el-table-column label="日期" width="110">
          <template #default="{ row }">{{ fmtDate(row.case_date) }}</template>
        </el-table-column>
        <el-table-column prop="road" label="道路" width="110" show-overflow-tooltip />
        <el-table-column label="具体位置" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">{{ row.location }}</template>
        </el-table-column>
        <el-table-column label="问题" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ row.problem }}</template>
        </el-table-column>
        <el-table-column prop="dept" label="责任单位" width="100" />
        <el-table-column label="处理结果" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.result && row.result !== '—'">{{ row.result }}</span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.status === '已整改' ? 'success' : 'warning'" size="small">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="照片" width="90" align="center">
          <template #default="{ row }">
            <el-button v-if="row.photos?.length" link type="primary" @click="openPhotos(row)">
              {{ row.photos.length }} 张
            </el-button>
            <span v-else class="muted">无</span>
          </template>
        </el-table-column>
        <el-table-column label="来源" width="150" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="src-text">{{ row.source_file }} · 第{{ row.source_row }}行</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openRectify(row)">
              {{ row.status === '已整改' ? '查看/更正' : '回填整改' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="pager">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          :page-sizes="[20, 50, 100, 200]"
          @current-change="load"
          @size-change="load"
        />
      </div>
    </el-card>

    <!-- 照片查看 -->
    <el-dialog v-model="photoDialog" title="案件照片" width="720px">
      <div v-if="photoRow" class="photo-meta">
        <b>{{ photoRow.location }}</b> · {{ photoRow.problem }}
      </div>
      <el-row :gutter="10">
        <el-col :span="12" v-for="p in photoRow?.photos || []" :key="p.file_path">
          <div class="photo-item">
            <el-image :src="photoUrl(p.file_path)" fit="cover" :preview-src-list="previewList" lazy />
            <div class="photo-kind">
              <el-tag :type="p.kind === 'problem' ? 'danger' : 'success'" size="small">
                {{ p.kind === 'problem' ? '问题图' : '整改图' }}
              </el-tag>
              <span class="muted">#{{ p.seq }}</span>
            </div>
          </div>
        </el-col>
      </el-row>
    </el-dialog>

    <!-- 回填整改结果 -->
    <el-dialog v-model="rectifyDialog" title="回填整改结果" width="560px">
      <div v-if="rectifyRow" class="rectify-body">
        <p class="rectify-title">
          {{ rectifyRow.location }} · {{ rectifyRow.problem }}
          <el-tag :type="rectifyRow.status === '已整改' ? 'success' : 'warning'" size="small" style="margin-left:8px">
            {{ rectifyRow.status }}
          </el-tag>
        </p>
        <el-form label-width="88px">
          <el-form-item label="整改状态">
            <el-radio-group v-model="rectifyForm.status">
              <el-radio label="已整改">已整改</el-radio>
              <el-radio label="待整改">待整改</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="处理结果">
            <el-input v-model="rectifyForm.result" type="textarea" :rows="3"
                      placeholder="部门填写的原文，如「已更换」「已清理」" />
          </el-form-item>
        </el-form>
        <el-alert type="info" :closable="false" show-icon>
          <template #title>
            处理结果里出现「不属于 / 非我中心 / 建议转 / 搬不动」时，即使选已整改也按待整改统计
            ——这代表活儿没干完，不代表要区分责任。
          </template>
        </el-alert>
      </div>
      <template #footer>
        <el-button @click="rectifyDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveRectify">保存</el-button>
      </template>
    </el-dialog>

    <!-- 疑似重复人工确认 -->
    <el-dialog v-model="dupVisible" title="疑似重复待确认" width="900px" top="6vh">
      <div class="dup-head">
        <span class="muted">
          判定依据是<b>照片完全相同</b>。位置和问题描述相同不判重——同一路段不同点位常被写成一样。
        </span>
      </div>
      <div v-for="d in dupList" :key="d.id" class="dup-item">
        <div class="dup-cols">
          <div class="dup-col">
            <div class="dup-col-head new">新导入（第{{ d.new_case.source_row }}行）</div>
            <div class="dup-line"><b>位置</b>{{ d.new_case.location }}</div>
            <div class="dup-line"><b>问题</b>{{ d.new_case.problem }}</div>
            <div class="dup-line"><b>单位</b>{{ d.new_case.dept || '未填' }} · {{ d.new_case.case_date }}</div>
            <div class="dup-line"><b>结果</b>{{ d.new_case.result || '—' }}</div>
          </div>
          <div class="dup-col">
            <div class="dup-col-head old">库内已有（#{{ d.matched_case?.id }}）</div>
            <div class="dup-line"><b>位置</b>{{ d.matched_case?.location }}</div>
            <div class="dup-line"><b>问题</b>{{ d.matched_case?.problem }}</div>
            <div class="dup-line"><b>单位</b>{{ d.matched_case?.dept || '未填' }} · {{ d.matched_case?.case_date }}</div>
            <div class="dup-line"><b>状态</b>{{ d.matched_case?.status }}</div>
          </div>
        </div>
        <div class="dup-actions">
          <el-button type="primary" size="small" :loading="deciding === d.id" @click="decide(d, 'merged')">
            并到已有案件
          </el-button>
          <el-button size="small" :loading="deciding === d.id" @click="decide(d, 'new')">
            是全新案件
          </el-button>
          <span class="muted dup-hint">
            「并到已有」会把新记录的整改结果与整改图并过去，不改原记录的位置和日期。
          </span>
        </div>
      </div>
      <el-empty v-if="!dupList.length && !dupLoading" description="没有待确认的疑似重复" />
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'

const loading = ref(false)
const cases = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const statusOptions = ['待整改', '已整改']
const deptOptions = ['市政', '执法队', '环卫', '园林', '排水', '市容秩序科']

const filters = reactive({ status: '', dept: '', road: '', keyword: '', dateRange: null })

const photoDialog = ref(false)
const photoRow = ref(null)
const previewList = ref([])

const rectifyDialog = ref(false)
const rectifyRow = ref(null)
const rectifyForm = reactive({ status: '待整改', result: '' })
const saving = ref(false)

const dupVisible = ref(false)
const dupList = ref([])
const dupTotal = ref(0)
const dupLoading = ref(false)
const deciding = ref(null)

const pad = (n) => String(n).padStart(2, '0')
const fmtDate = (d) => {
  if (!d) return ''
  const s = String(d)
  if (/^\d{4}-\d{2}-\d{2}/.test(s)) return `${s.slice(5, 7)}月${s.slice(8, 10)}日`
  return s
}

function rangeParams() {
  return filters.dateRange?.length === 2
    ? { date_from: filters.dateRange[0], date_to: filters.dateRange[1] }
    : {}
}

async function load() {
  loading.value = true
  try {
    const { data } = await axios.get('/api/inspection/cases', {
      params: {
        page: page.value, size: pageSize.value,
        status: filters.status, dept: filters.dept, road: filters.road,
        keyword: filters.keyword, ...rangeParams(),
      },
    })
    cases.value = data.items || []
    total.value = data.total || 0
  } catch { /* 拦截器已提示 */ }
  loading.value = false
}

function resetFilters() {
  filters.status = ''
  filters.dept = ''
  filters.road = ''
  filters.keyword = ''
  filters.dateRange = null
  page.value = 1
  load()
}

function photoUrl(p) { return p }
function openPhotos(row) {
  photoRow.value = row
  previewList.value = (row.photos || []).map(p => photoUrl(p.file_path))
  photoDialog.value = true
}

function openRectify(row) {
  rectifyRow.value = row
  rectifyForm.status = row.status || '待整改'
  rectifyForm.result = row.result && row.result !== '—' ? row.result : ''
  rectifyDialog.value = true
}

async function saveRectify() {
  if (!rectifyRow.value) return
  saving.value = true
  try {
    // 只回填整改结果与状态；位置/问题/责任单位/日期是巡查现场原始记录，不可改
    const { data } = await axios.put(`/api/inspection/cases/${rectifyRow.value.id}`, {
      result: rectifyForm.result,
      status: rectifyForm.status,
    })
    ElMessage.success(`已回填（${data.status}）`)
    rectifyDialog.value = false
    load()
  } catch { /* 拦截器已提示 */ }
  saving.value = false
}

async function loadDup() {
  dupLoading.value = true
  try {
    const { data } = await axios.get('/api/inspection/dup-candidates', { params: { decision: 'pending' } })
    dupList.value = data.items || []
    dupTotal.value = dupList.value.length
  } catch { /* 拦截器已提示 */ }
  dupLoading.value = false
}

async function decide(d, action) {
  const label = action === 'merged' ? '并到已有案件' : '判为全新案件'
  try {
    await ElMessageBox.confirm(
      action === 'merged'
        ? `确认把「${d.new_case.location}」并入案件 #${d.matched_case?.id}？\n新记录的整改结果与整改图会挂过去，原记录的位置与日期不变。`
        : `确认「${d.new_case.location}」是全新案件，正式入库？`,
      label, { type: 'warning' },
    )
  } catch { return }
  deciding.value = d.id
  try {
    const { data } = await axios.post(`/api/inspection/dup-candidates/${d.id}`, { decision: action })
    if (data.ok) {
      ElMessage.success(action === 'merged' ? '已并入' : '已作为新案入库')
      loadDup()
      load()
    }
  } catch { /* 拦截器已提示 */ }
  deciding.value = null
}

async function exportExcel() {
  try {
    const params = { status: filters.status, dept: filters.dept, road: filters.road, ...rangeParams() }
    const { data, headers } = await axios.get('/api/inspection/export', {
      params, responseType: 'blob',
    })
    const disposition = headers['content-disposition'] || ''
    const utf8 = /filename\*=UTF-8''([^;]+)/i.exec(disposition)
    const fname = utf8 ? decodeURIComponent(utf8[1]) : '巡查问题台账.xlsx'
    const url = URL.createObjectURL(data)
    const a = document.createElement('a')
    a.href = url
    a.download = fname
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch { /* 拦截器已提示 */ }
}

onMounted(() => {
  load()
  loadDup()
})
</script>

<style scoped>
.ipl-page { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; }
.page-header h2 { margin: 0 0 6px; font-size: 20px; }
.page-sub { margin: 0; color: #909399; font-size: 13px; max-width: 720px; line-height: 1.6; }
.dup-banner { margin-bottom: 14px; }
.filter-card { margin-bottom: 14px; }
.filter-row { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
.pager { display: flex; justify-content: flex-end; margin-top: 14px; }
.muted { color: #909399; }
.src-text { font-size: 12px; color: #909399; }
.photo-meta { margin-bottom: 12px; font-size: 13px; color: #606266; }
.photo-item { margin-bottom: 12px; }
.photo-item .el-image { width: 100%; height: 200px; border-radius: 4px; }
.photo-kind { display: flex; align-items: center; gap: 6px; margin-top: 4px; font-size: 12px; }
.rectify-title { margin: 0 0 14px; font-size: 14px; color: #303133; line-height: 1.6; }
.dup-head { margin-bottom: 14px; font-size: 13px; }
.dup-item { border: 1px solid #ebeef5; border-radius: 6px; padding: 14px; margin-bottom: 12px; }
.dup-cols { display: flex; gap: 14px; }
.dup-col { flex: 1; background: #fafafa; border-radius: 4px; padding: 10px 12px; }
.dup-col-head { font-weight: 600; font-size: 13px; margin-bottom: 8px; }
.dup-col-head.new { color: #e6a23c; }
.dup-col-head.old { color: #409eff; }
.dup-line { font-size: 13px; line-height: 1.8; color: #303133; }
.dup-line b { display: inline-block; width: 40px; color: #909399; font-weight: normal; font-size: 12px; }
.dup-actions { display: flex; align-items: center; gap: 10px; margin-top: 12px; }
.dup-hint { font-size: 12px; }
</style>
