<template>
  <div class="insp-page">
    <div class="page-header">
      <div>
        <h2>巡查数据入库</h2>
        <p class="page-sub">
          把每日巡查部门表解析出的图片与案件 JSON 提交入库。同一份表重复导入不会翻倍；
          只有照片与库内完全相同的才会进「疑似重复」等你确认，文字描述相同不拦。
        </p>
      </div>
      <div>
        <el-button @click="loadDicts">刷新字典</el-button>
        <el-button type="primary" :loading="submitting" :disabled="!canSubmit" @click="submitImport">
          提交入库
        </el-button>
      </div>
    </div>

    <el-row :gutter="16">
      <!-- 左：批次信息 -->
      <el-col :span="8">
        <el-card shadow="never" class="pane">
          <template #header><b>批次信息</b></template>
          <el-form label-width="88px" label-position="top">
            <el-form-item label="来源文件">
              <el-input v-model="batch.source_file" placeholder="如 问题处置汇总台账（10月22日）.xlsx" />
            </el-form-item>
            <el-form-item label="批次号">
              <el-input v-model="batch.batch_no" placeholder="留空则自动生成" />
            </el-form-item>
            <el-form-item label="默认日期">
              <el-date-picker
                v-model="batch.default_date"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="表里没写日期的行用这天"
                style="width: 100%"
              />
            </el-form-item>
          </el-form>
          <el-alert type="info" :closable="false" show-icon class="tip">
            <template #title>
              批次号相同 + 来源文件相同 + 行号相同 = 同一条记录，重复提交会被跳过并计入
              <b>duplicates_skipped</b>。
            </template>
          </el-alert>
        </el-card>
      </el-col>

      <!-- 中：照片上传 -->
      <el-col :span="8">
        <el-card shadow="never" class="pane">
          <template #header>
            <div class="card-head">
              <b>照片上传</b>
              <span class="muted">已上传 {{ staged.length }} 张</span>
            </div>
          </template>
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            multiple
            list-type="picture-card"
            :file-list="[]"
            :on-change="onFileChange"
            :on-remove="onFileRemove"
            accept=".jpg,.jpeg,.png,.webp,.bmp"
          >
            <el-icon><Plus /></el-icon>
            <template #file="{ file }">
              <div class="upload-thumb">
                <img :src="file.url" alt="" />
                <span v-if="file.staging" class="upload-staging">上传中</span>
              </div>
            </template>
          </el-upload>
          <div class="upload-actions">
            <el-button size="small" type="primary" :loading="uploading" :disabled="!pendingFiles.length" @click="doUpload">
              上传到暂存区
            </el-button>
            <el-button size="small" :disabled="!staged.length" @click="clearStaged">清空</el-button>
          </div>
          <el-alert v-if="uploadErrors.length" type="warning" :closable="false" show-icon class="tip">
            <template #title>
              有 {{ uploadErrors.length }} 个文件失败：
              <span class="err-line" v-for="(e, i) in uploadErrors.slice(0, 3)" :key="i">{{ e }}</span>
            </template>
          </el-alert>
        </el-card>
      </el-col>

      <!-- 右：案件 JSON -->
      <el-col :span="8">
        <el-card shadow="never" class="pane">
          <template #header>
            <div class="card-head">
              <b>案件 JSON</b>
              <span class="muted">{{ parsedCount }} 件</span>
            </div>
          </template>
          <el-input
            v-model="jsonText"
            type="textarea"
            :rows="14"
            placeholder='粘贴 _parse_daily.py 生成的 import_payload.json 内容（含 "cases" 数组）'
            spellcheck="false"
          />
          <div class="upload-actions">
            <el-button size="small" @click="parseJson">解析</el-button>
            <el-button size="small" :disabled="!cases.length" @click="fillTokens">按文件名匹配 token</el-button>
            <el-button size="small" :disabled="!cases.length" @click="clearCases">清空</el-button>
          </div>
          <el-alert v-if="jsonError" type="error" :closable="false" show-icon class="tip">
            <template #title>{{ jsonError }}</template>
          </el-alert>
        </el-card>
      </el-col>
    </el-row>

    <!-- 对账结果 -->
    <el-card v-if="result" shadow="never" class="result-card">
      <template #header>
        <div class="card-head">
          <b>对账结果</b>
          <el-tag :type="result.errors?.length ? 'warning' : 'success'" size="small">
            {{ result.errors?.length ? `${result.errors.length} 条待处理` : '全部通过' }}
          </el-tag>
        </div>
      </template>
      <el-row :gutter="12" class="count-row">
        <el-col :span="4" v-for="c in countCards" :key="c.key">
          <div class="count-box" :class="c.cls">
            <div class="count-num">{{ result[c.key] }}</div>
            <div class="count-label">{{ c.label }}</div>
          </div>
        </el-col>
      </el-row>
      <div v-if="result.errors?.length" class="errors">
        <div class="errors-title">以下条目没有入库，请逐条处理后重新提交：</div>
        <el-table :data="result.errors" border size="small" max-height="260">
          <el-table-column prop="source_row" label="来源行" width="90" />
          <el-table-column prop="reason" label="原因" min-width="320" show-overflow-tooltip />
        </el-table>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'

const batch = reactive({ batch_no: '', source_file: '', default_date: '' })
const pendingFiles = ref([])   // 待上传的 File
const staged = ref([])         // 已上传 {file_token, orig_name, phash}
const uploadErrors = ref([])
const uploading = ref(false)
const jsonText = ref('')
const jsonError = ref('')
const cases = ref([])
const submitting = ref(false)
const result = ref(null)

const countCards = [
  { key: 'inserted', label: '新入库' },
  { key: 'updated', label: '回填更新' },
  { key: 'duplicates_skipped', label: '重复跳过' },
  { key: 'pending_review', label: '待人工确认' },
  { key: 'photos_received', label: '收到照片' },
  { key: 'photos_saved', label: '照片入库' },
]

const parsedCount = computed(() => cases.value.length)
const canSubmit = computed(() => cases.value.length > 0 && !!batch.source_file.trim())

function onFileChange(file, files) {
  pendingFiles.value = files.filter(f => f.raw).map(f => f.raw)
}
function onFileRemove(_file, files) {
  pendingFiles.value = files.filter(f => f.raw).map(f => f.raw)
}
function clearStaged() {
  staged.value = []
  uploadErrors.value = []
}

async function doUpload() {
  if (!pendingFiles.value.length) return
  uploading.value = true
  uploadErrors.value = []
  const fd = new FormData()
  for (const f of pendingFiles.value) fd.append('files', f)
  try {
    const { data } = await axios.post('/api/inspection/photos', fd)
    staged.value.push(...(data.saved || []))
    uploadErrors.value = (data.errors || []).map(e => `${e.file}：${e.reason}`)
    if (data.saved?.length) ElMessage.success(`上传成功 ${data.saved.length} 张`)
    if (uploadErrors.value.length) ElMessage.warning(`${uploadErrors.value.length} 个文件失败`)
  } catch { /* 拦截器已提示 */ }
  uploading.value = false
}

function parseJson() {
  jsonError.value = ''
  cases.value = []
  const raw = jsonText.value.trim()
  if (!raw) { jsonError.value = '请先粘贴 JSON'; return }
  let obj
  try {
    obj = JSON.parse(raw)
  } catch (e) {
    jsonError.value = `JSON 解析失败：${e.message}`
    return
  }
  const list = Array.isArray(obj) ? obj : obj.cases
  if (!Array.isArray(list) || !list.length) {
    jsonError.value = '没找到 cases 数组（或数组为空）'
    return
  }
  cases.value = list.map((c, i) => ({
    source_row: c.source_row ?? i + 1,
    case_date: c.case_date || batch.default_date || '',
    road: c.road || '',
    location: c.location || '',
    problem: c.problem || '',
    dept: c.dept || '',
    result: c.result || '',
    status: c.status || '',
    leader_group: c.leader_group || '',
    photos: (c.photos || []).map((p, j) => ({
      kind: p.kind || 'problem',
      seq: p.seq || j + 1,
      file_token: p.file_token || '',
      phash: p.phash || '',
    })),
  }))
  if (!batch.source_file && obj.source_file) batch.source_file = obj.source_file
  if (!batch.batch_no && obj.batch_no) batch.batch_no = obj.batch_no
  ElMessage.success(`解析出 ${cases.value.length} 件`)
}

// _parse_daily.py 输出的 file_token 就是 photos/ 里的文件名，这里按文件名把它们
// 和上传后拿到的 token 对上（上传返回的 orig_name 就是原文件名）
function fillTokens() {
  if (!staged.value.length) { ElMessage.warning('请先上传照片'); return }
  const byName = {}
  for (const s of staged.value) byName[s.orig_name] = s.file_token
  let hit = 0, miss = 0
  for (const c of cases.value) {
    for (const p of c.photos) {
      const token = byName[p.file_token] || byName[`${p.file_token}.jpg`]
      if (token) { p.file_token = token; hit++ }
      else miss++
    }
  }
  if (miss) ElMessage.warning(`匹配到 ${hit} 张，${miss} 张没对应上（检查文件名是否一致）`)
  else ElMessage.success(`${hit} 张照片全部匹配`)
}

function clearCases() {
  cases.value = []
  jsonText.value = ''
  jsonError.value = ''
}

async function submitImport() {
  if (!cases.value.length) { ElMessage.warning('没有可提交的案件'); return }
  if (!batch.source_file.trim()) { ElMessage.warning('请填写来源文件名（幂等靠它）'); return }
  submitting.value = true
  result.value = null
  try {
    const payload = {
      batch_no: batch.batch_no.trim() || `B${new Date().toISOString().slice(0, 10).replace(/-/g, '')}-1`,
      source_file: batch.source_file.trim(),
      cases: cases.value,
    }
    const { data } = await axios.post('/api/inspection/import', payload)
    result.value = data
    const bad = data.errors?.length || 0
    if (bad) ElMessage.warning(`入库 ${data.inserted} 件，${bad} 条待处理`)
    else ElMessage.success(`入库 ${data.inserted} 件、照片 ${data.photos_saved} 张`)
  } catch { /* 拦截器已提示 */ }
  submitting.value = false
}

function loadDicts() { /* 预留：本页不需要字典，保留按钮与创文页一致的操作手感 */ }

onMounted(() => {
  const d = new Date()
  const pad = (n) => String(n).padStart(2, '0')
  batch.default_date = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
})
</script>

<style scoped>
.insp-page { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; }
.page-header h2 { margin: 0 0 6px; font-size: 20px; }
.page-sub { margin: 0; color: #909399; font-size: 13px; max-width: 720px; line-height: 1.6; }
.pane { min-height: 380px; }
.card-head { display: flex; justify-content: space-between; align-items: center; }
.muted { color: #909399; font-size: 12px; font-weight: normal; }
.tip { margin-top: 12px; }
.err-line { display: block; font-size: 12px; }
.upload-actions { display: flex; gap: 8px; margin-top: 12px; }
.upload-thumb { position: relative; width: 100%; height: 100%; }
.upload-thumb img { width: 100%; height: 100%; object-fit: cover; }
.upload-staging { position: absolute; inset: 0; background: rgba(0,0,0,.5); color: #fff; font-size: 12px; display: flex; align-items: center; justify-content: center; }
.result-card { margin-top: 16px; }
.count-row { margin-bottom: 4px; }
.count-box { text-align: center; padding: 14px 8px; border-radius: 6px; background: #f5f7fa; }
.count-num { font-size: 24px; font-weight: 600; color: #303133; }
.count-label { font-size: 12px; color: #909399; margin-top: 4px; }
.errors { margin-top: 14px; }
.errors-title { font-size: 13px; color: #e6a23c; margin-bottom: 8px; }
</style>
