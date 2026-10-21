<template>
  <div class="cyw-input-tab">
    <div class="page-header">
      <div>
        <h2>快速录入</h2>
        <p class="page-sub">下拉选择点位自动带出序号 → 粘贴照片（AI 自动识别描述/类型，可改）→ 保存。今日已登记 <b>{{ todayCount }}</b> 条</p>
      </div>
      <el-button @click="resetForm">清空重录</el-button>
    </div>

    <el-card shadow="never">
      <el-form :model="form" label-width="110px" class="cyw-form">
        <el-row :gutter="16">
          <el-col :span="10">
            <el-form-item label="点位信息" required>
              <el-select
                ref="spotSelectRef"
                v-model="form.spotId"
                filterable
                placeholder="下拉选择点位（可搜名称/序号）"
                style="width: 100%"
                @change="onSpotChange"
              >
                <el-option v-for="s in spots" :key="s.id" :value="s.id" :label="spotLabel(s)">
                  <span class="opt-name">{{ s.name }}</span>
                  <span class="opt-sub">{{ s.road }}{{ s.road && s.manage_unit ? ' · ' : '' }}{{ s.manage_unit }}</span>
                </el-option>
              </el-select>
              <div v-if="spot" class="spot-hit">
                <el-tag v-if="spot.is_key" type="danger" size="small">重点</el-tag>
                <el-tag v-if="spot.spot_type" size="small" type="warning">{{ spot.spot_type }}</el-tag>
                <b>{{ spot.name }}</b>
                <span v-if="spot.road" class="spot-road">{{ spot.road }}</span>
                <el-tag v-if="spot.manage_unit" size="small" type="info">{{ spot.manage_unit }}</el-tag>
                <span v-if="spot.lng != null && spot.lat != null" class="spot-coord">
                  {{ Number(spot.lng).toFixed(6).replace(/0+$/, '').replace(/\.$/, '') }},
                  {{ Number(spot.lat).toFixed(6).replace(/0+$/, '').replace(/\.$/, '') }}
                </span>
                <!-- 联系人按源表格式一条一行：部门/角色 — 姓名 — 电话，三列对齐 -->
                <div v-if="spot.contacts?.length" class="spot-contacts">
                  <div v-for="(c, i) in spot.contacts" :key="i" class="spot-contact-row">
                    <span class="sc-dept">{{ c.dept_label || '联系人' }}</span>
                    <span class="sc-person">{{ c.person }}</span>
                    <span class="sc-phone">{{ c.phone }}</span>
                  </div>
                </div>
              </div>
              <span v-else class="spot-empty">下拉选择点位，自动带出监控序号</span>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="监控序号" required>
              <el-input
                v-model="form.monitorNo"
                placeholder="输入序号回车"
                clearable
                @keyup.enter="lookupSpot"
                @blur="lookupSpot"
              />
              <div class="form-tip">选点位自动带出，也可直接输序号回查</div>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="问题类型" required>
              <el-select v-model="form.typeId" placeholder="选择类型" style="width: 100%" @change="onTypeChange">
                <el-option v-for="t in types" :key="t.id" :label="t.name" :value="t.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="派发部门" required>
              <el-select v-model="form.deptId" placeholder="选择派发部门" style="width: 100%">
                <el-option v-for="d in depts" :key="d.id" :label="d.name" :value="d.id" />
              </el-select>
              <div class="form-tip">按问题类型默认带出，可改派单个部门</div>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="发现时间">
              <el-date-picker
                v-model="form.foundAt"
                type="datetime"
                value-format="YYYY-MM-DD HH:mm:ss"
                placeholder="发现时间"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="问题描述" required>
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="2"
            placeholder="简要描述问题（文字能说清可不发照片）"
            @input="onDescInput"
          />
          <div class="ai-line">
            <el-button
              link
              type="primary"
              size="small"
              :loading="aiParsing"
              :disabled="!form.photos.length || aiParsing"
              @click="manualParse"
            >
              <el-icon><MagicStick /></el-icon>AI 识别照片
            </el-button>
            <span v-if="aiParsing" class="ai-hint">识别中，约需几秒…</span>
            <span v-else-if="aiHint" class="ai-hint" :class="{ ok: aiOk }">{{ aiHint }}</span>
            <span v-else class="ai-hint">上传照片后自动识别描述与类型，AI 结果可手动修改</span>
          </div>
        </el-form-item>

        <el-form-item label="现场照片">
          <div
            class="photo-zone"
            :class="{ dragging: dragging }"
            tabindex="0"
            @dragover.prevent="dragging = true"
            @dragleave="dragging = false"
            @drop.prevent="onDrop"
            @paste="onPaste"
          >
            <div v-if="form.photos.length" class="photo-list">
              <div v-for="(p, i) in form.photos" :key="p.url" class="photo-item">
                <img :src="p.url" alt="现场照片" />
                <el-button class="photo-remove" size="small" type="danger" circle @click="form.photos.splice(i, 1)">
                  <el-icon><Close /></el-icon>
                </el-button>
              </div>
            </div>
            <div v-else class="photo-empty">
              <el-icon class="photo-icon"><Picture /></el-icon>
              <p>按 <b>Ctrl+V</b> 粘贴 PC 微信复制的照片，或拖拽图片到此处（上传后 AI 自动识别描述）</p>
              <el-upload
                action="/api/cyw/upload-image"
                :headers="uploadHeaders"
                :on-success="(res) => onUploadSuccess(res)"
                :show-file-list="false"
                multiple
                accept="image/*"
              >
                <el-button size="small" type="primary" plain>选择文件</el-button>
              </el-upload>
            </div>
            <div v-if="form.photos.length" class="photo-more">
              <el-upload
                action="/api/cyw/upload-image"
                :headers="uploadHeaders"
                :on-success="(res) => onUploadSuccess(res)"
                :show-file-list="false"
                multiple
                accept="image/*"
              >
                <el-button size="small" type="primary" plain>继续添加</el-button>
              </el-upload>
              <span class="photo-tip">也可继续 Ctrl+V 粘贴 / 拖入</span>
            </div>
          </div>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" size="large" :loading="saving" @click="save">保存登记</el-button>
          <span class="save-tip">登记后可直接生成处置详单，发到处置群并@相关单位</span>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Close, Picture, MagicStick } from '@element-plus/icons-vue'
import axios from 'axios'

const depts = ref([])
const types = ref([])
const spots = ref([])
const spot = ref(null)
const saving = ref(false)
const dragging = ref(false)
const todayCount = ref(0)
const spotSelectRef = ref(null)
// AI 照片识别状态：aiTried 保证每次登记只自动识别一次；aiFilledDesc 记住 AI 填过的描述，
// 操作员一旦手工改动（onDescInput 清空），后续 AI 结果不再覆盖人工内容
const aiParsing = ref(false)
const aiHint = ref('')
const aiOk = ref(false)
const aiFilledDesc = ref('')
let aiTried = false

const nowText = () => {
  const d = new Date()
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

const form = reactive({
  monitorNo: '',
  spotId: null,
  typeId: null,
  deptId: null,
  foundAt: nowText(),
  description: '',
  photos: []
})

const uploadHeaders = computed(() => ({ Authorization: `Bearer ${localStorage.getItem('token')}` }))


async function loadDicts() {
  const [dRes, tRes, sRes] = await Promise.all([
    axios.get('/api/cyw/depts'),
    axios.get('/api/cyw/types'),
    axios.get('/api/cyw/spots', { params: { page_size: 200 } })
  ])
  depts.value = dRes.data.depts || []
  types.value = tRes.data.types || []
  spots.value = sRes.data.spots || []
}

async function loadTodayCount() {
  try {
    const { data } = await axios.get('/api/cyw/report/daily')
    todayCount.value = data.counts?.new || 0
  } catch { /* error toast via interceptor */ }
}

// 下拉选点位 → 回填监控序号与档案展示（反向：输入序号回查命中时 form.spotId 同步，下拉自动跟随）
function spotLabel(s) {
  return `${s.monitor_no} ${s.name}`
}

function onSpotChange(spotId) {
  const s = spots.value.find((x) => x.id === spotId)
  if (!s) return
  spot.value = s
  form.spotId = s.id
  form.monitorNo = s.monitor_no
}

async function lookupSpot() {
  const no = (form.monitorNo || '').trim()
  if (!no) return
  try {
    const { data } = await axios.get('/api/cyw/spot-by-no', { params: { no } })
    if (data.hit) {
      // spot-by-no 的联系人在顶层（与 spot 字段平级），合并进来供命中行展示
      spot.value = { ...data.spot, contacts: data.contacts || [] }
      form.spotId = data.spot.id
      if (data.types?.length) types.value = data.types
    }
  } catch {
    // 404 = 未找到该序号：拦截器已提示，此处清理带出状态
    spot.value = null
    form.spotId = null
  }
}

function onTypeChange(typeId) {
  const t = types.value.find((x) => x.id === typeId)
  if (!t) return
  form.typeId = t.id
  if (t.default_dept_id) form.deptId = t.default_dept_id
}

function onUploadSuccess(res) {
  if (res?.success && res.url) {
    form.photos.push({ name: res.name || '照片', url: res.url })
    afterPhotoAdded()
  }
}

async function uploadPhotoFile(file) {
  const fd = new FormData()
  fd.append('file', file)
  const { data } = await axios.post('/api/cyw/upload-image', fd)
  if (data?.success && data.url) {
    form.photos.push({ name: data.name || file.name, url: data.url })
    afterPhotoAdded()
  }
}

// 每张照片上传完后：本次登记首次上传自动触发一次 AI 识别，后续照片不重复打扰（可点按钮手动识别）
function afterPhotoAdded() {
  if (aiTried || aiParsing.value || !form.photos.length) return
  aiTried = true
  parsePhoto(form.photos[form.photos.length - 1].url)
}

function manualParse() {
  if (!form.photos.length) return
  parsePhoto(form.photos[form.photos.length - 1].url)
}

function onDescInput() {
  // 人工一改动描述，AI 填入记录即失效，后续识别结果只进提示、不再覆盖
  aiFilledDesc.value = ''
}

// 调后端私有化 Qwen2.5-VL 识别照片；失败/超时后端返回 success:false，此处静默降级为手动填写
async function parsePhoto(url) {
  if (aiParsing.value) return
  aiParsing.value = true
  aiOk.value = false
  aiHint.value = '识别中，约需几秒…'
  const t0 = Date.now()
  try {
    const { data } = await axios.post('/api/cyw/parse-photo', { url })
    if (data.success) {
      const secs = ((data.elapsed_ms || Date.now() - t0) / 1000).toFixed(1)
      const filled = []
      if (data.description && (!form.description || form.description === aiFilledDesc.value)) {
        form.description = data.description
        aiFilledDesc.value = data.description
        filled.push('描述')
      }
      if (data.type_id && !form.typeId) {
        form.typeId = data.type_id
        onTypeChange(data.type_id)
        filled.push('类型')
      }
      aiOk.value = true
      aiHint.value = filled.length
        ? `AI 已填入${filled.join('、')}（${secs} 秒），请核对，可直接修改`
        : `AI 建议：${data.description}（${secs} 秒）；描述/类型已有人工内容，未覆盖`
    } else {
      // 后端错误文案本身就是给操作员看的（超时/服务暂不可用/未识别出问题），自动触发也照实显示：
      // 吞成同一句通用提示会让"GPU 掉了在跑 CPU"这类故障在现场毫无线索
      aiOk.value = false
      aiHint.value = data.error || 'AI 未能识别，请手动填写'
    }
  } catch {
    aiOk.value = false
    aiHint.value = 'AI 服务异常，请手动填写'
  } finally {
    aiParsing.value = false
  }
}

// 页面级粘贴监听：操作员从 PC 微信复制照片后无需先点击输入框（仅处理图片，文本粘贴不拦截）
function onPaste(e) {
  const files = Array.from(e.clipboardData?.files || []).filter((f) => f.type.startsWith('image/'))
  if (!files.length) return
  e.preventDefault()
  Promise.all(files.map(uploadPhotoFile)).catch(() => {})
}

function onDrop(e) {
  dragging.value = false
  const files = Array.from(e.dataTransfer?.files || []).filter((f) => f.type.startsWith('image/'))
  if (!files.length) return
  Promise.all(files.map(uploadPhotoFile)).catch(() => {})
}

async function save() {
  if (!form.spotId) return ElMessage.warning('请先选择点位（下拉选择或输入监控序号）')
  if (!form.typeId) return ElMessage.warning('请选择问题类型')
  if (!form.description.trim()) return ElMessage.warning('请填写问题描述')
  if (!form.deptId) return ElMessage.warning('请选择派发部门')
  saving.value = true
  try {
    const { data } = await axios.post('/api/cyw/issues', {
      spot_id: form.spotId,
      type_id: form.typeId,
      dept_id: form.deptId,
      found_at: form.foundAt,
      description: form.description.trim(),
      photos: form.photos
    })
    ElMessage.success(`登记成功，案件编号 ${data.case_no}（已视为派发，单位反馈后即办结）`)
    resetForm()
    try {
      await ElMessageBox.confirm(
        `案件 ${data.case_no} 已登记，是否立即生成处置详单？`,
        '登记成功',
        { confirmButtonText: '生成详单', cancelButtonText: '稍后', type: 'success' }
      )
      genSlip(data.id)
    } catch { /* 稍后生成 */ }
  } catch { /* error toast via interceptor */ }
  finally { saving.value = false }
}

async function genSlip(id) {
  try {
    const { data } = await axios.post(`/api/cyw/issues/${id}/slip`)
    if (data.success) {
      window.open(data.url, '_blank')
      ElMessage.success('详单已生成，请下载后发到处置群并@相关单位')
    }
  } catch { /* error toast via interceptor */ }
}

function resetForm() {
  form.monitorNo = ''
  form.spotId = null
  form.typeId = null
  form.deptId = null
  form.foundAt = nowText()
  form.description = ''
  form.photos = []
  spot.value = null
  aiParsing.value = false
  aiHint.value = ''
  aiOk.value = false
  aiFilledDesc.value = ''
  aiTried = false
  nextTick(() => spotSelectRef.value?.focus())
}

onMounted(() => {
  loadDicts()
  loadTodayCount()
  window.addEventListener('paste', onPaste)
  nextTick(() => spotSelectRef.value?.focus())
})

onBeforeUnmount(() => {
  window.removeEventListener('paste', onPaste)
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
.spot-hit { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.spot-road { color: #909399; font-size: 13px; }
/* 联系人一条一行，部门列定宽对齐，派单时照着念就能找到人 */
.spot-contacts { width: 100%; margin-top: 2px; }
.spot-contact-row {
  display: grid;
  grid-template-columns: 240px 72px 1fr;
  align-items: baseline;
  column-gap: 12px;
  font-size: 13px;
  line-height: 1.9;
}
.sc-dept { color: #606266; }
.sc-person { color: #303133; font-weight: 500; }
.sc-phone { color: #409eff; font-family: Consolas, Menlo, monospace; }
.spot-coord { color: #a8abb2; font-size: 12px; font-family: Consolas, Menlo, monospace; }
.spot-empty { color: #c0c4cc; font-size: 13px; }
.opt-name { display: inline-block; max-width: 62%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; vertical-align: bottom; }
.opt-sub { float: right; color: #a8abb2; font-size: 12px; }
.form-tip { font-size: 12px; color: #909399; line-height: 1.6; }
.save-tip { margin-left: 12px; color: #909399; font-size: 12px; }
.photo-zone {
  border: 1px dashed #dcdfe6;
  border-radius: 6px;
  padding: 12px;
  outline: none;
  transition: border-color 0.2s;
}
.photo-zone:focus, .photo-zone.dragging { border-color: #409eff; }
.photo-empty { text-align: center; color: #909399; padding: 8px 0; }
.photo-empty p { margin: 6px 0 10px; font-size: 13px; }
.photo-icon { font-size: 28px; color: #c0c4cc; }
.photo-list { display: flex; flex-wrap: wrap; gap: 10px; }
.photo-item { position: relative; }
.photo-item img {
  width: 120px;
  height: 90px;
  object-fit: cover;
  border-radius: 4px;
  border: 1px solid #ebeef5;
}
.photo-remove { position: absolute; top: -8px; right: -8px; padding: 4px; }
.photo-more { display: flex; align-items: center; gap: 10px; margin-top: 10px; }
.photo-tip { color: #c0c4cc; font-size: 12px; }
.ai-line { display: flex; align-items: center; gap: 8px; margin-top: 4px; min-height: 22px; }
.ai-hint { color: #c0c4cc; font-size: 12px; }
.ai-hint.ok { color: #67c23a; }
</style>
