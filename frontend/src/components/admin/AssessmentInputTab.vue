<template>
  <div class="ami-tab">
    <div class="toolbar">
      <label class="lbl">考核月份</label>
      <select v-model="batch" class="sel" @change="loadAll">
        <option value="">请选择月份</option>
        <option v-for="m in months" :key="m.batch" :value="m.batch">{{ formatMonth(m.batch) }}</option>
      </select>
      <button class="btn btn-primary" :disabled="!batch || saving" @click="saveAll">
        {{ saving ? '保存中…' : saveLabel }}
      </button>
      <span v-if="loadedHint" class="hint">{{ loadedHint }}</span>
    </div>

    <div v-if="!batch" class="empty">请先选择考核月份</div>

    <div v-else class="sections">
      <!-- 平台 -->
      <section v-if="isPlatform" class="card">
        <h3>平台录入</h3>
        <div class="row">
          <div class="field">
            <label>当月考核案件数（月报受理数）</label>
            <input type="number" v-model.number="monthly.assessment_case_cnt" min="0" />
          </div>
        </div>
        <div class="field">
          <label>工作动态（整月总结，一行一条，序号自行填写）</label>
          <textarea v-model="monthly.work_note" rows="6" placeholder="一行一条，如：&#10;提升防汛实战能力。紧扣…&#10;加强部门协调联动。针对…"></textarea>
        </div>
        <div class="field">
          <label>加减分项说明（月报市容秩序表注，可空）</label>
          <textarea v-model="monthly.extra_note" rows="2" placeholder="如：未到 18:00 准许出摊时间，饭店提前店外经营，1处扣0.1分"></textarea>
        </div>

        <h4>市容秩序 · 执法分队</h4>
        <table class="ami-grid">
          <thead>
            <tr><th>分队</th><th>队考核分</th><th>街道办分</th><th>加减分项</th></tr>
          </thead>
          <tbody>
            <tr v-for="t in tmpl.dispatch_teams" :key="t">
              <td>{{ t }}</td>
              <td><input type="number" step="0.1" v-model.number="scoreMap[`dispatch|${t}|team`]" /></td>
              <td><input type="number" step="0.1" v-model.number="scoreMap[`dispatch|${t}|street`]" /></td>
              <td><input type="number" step="0.1" v-model.number="scoreMap[`dispatch|${t}|extra`]" /></td>
            </tr>
          </tbody>
        </table>

        <h4>环境卫生 · 片区</h4>
        <table class="ami-grid">
          <thead>
            <tr><th>片区</th><th>中心考核分</th><th>加减分项</th></tr>
          </thead>
          <tbody>
            <tr v-for="d in tmpl.sanitation_districts" :key="d">
              <td>{{ d }}</td>
              <td><input type="number" step="0.1" v-model.number="scoreMap[`sanitation|${d}|center`]" /></td>
              <td><input type="number" step="0.1" v-model.number="scoreMap[`sanitation|${d}|extra`]" /></td>
            </tr>
          </tbody>
        </table>

        <h4>园林绿化 · 片区</h4>
        <table class="ami-grid">
          <thead>
            <tr><th>片区</th><th>中心考核分</th><th>加减分项</th></tr>
          </thead>
          <tbody>
            <tr v-for="d in tmpl.garden_districts" :key="d">
              <td>{{ d }}</td>
              <td><input type="number" step="0.1" v-model.number="scoreMap[`garden|${d}|center`]" /></td>
              <td><input type="number" step="0.1" v-model.number="scoreMap[`garden|${d}|extra`]" /></td>
            </tr>
          </tbody>
        </table>

        <h4>园林绿化 · 公园广场</h4>
        <table class="ami-grid">
          <thead>
            <tr><th>单位</th><th>中心考核分</th><th>加减分项</th></tr>
          </thead>
          <tbody>
            <tr v-for="p in tmpl.parks" :key="p">
              <td>{{ p }}</td>
              <td><input type="number" step="0.1" v-model.number="scoreMap[`garden_park|${p}|center`]" /></td>
              <td><input type="number" step="0.1" v-model.number="scoreMap[`garden_park|${p}|extra`]" /></td>
            </tr>
          </tbody>
        </table>

        <h4>市政公用 · 子单位</h4>
        <table class="ami-grid">
          <thead>
            <tr><th>单位</th><th>加减分项</th></tr>
          </thead>
          <tbody>
            <tr v-for="u in tmpl.municipal_units" :key="u">
              <td>{{ u }}</td>
              <td><input type="number" step="0.1" v-model.number="scoreMap[`municipal|${u}|extra`]" /></td>
            </tr>
          </tbody>
        </table>
      </section>

      <!-- 采集异常日（月报数据质量） -->
      <section v-if="isPlatform" class="card">
        <h3>采集异常日</h3>
        <p class="card-tip">标记当月因降雨、系统故障等原因导致采集量异常的日期，生成月度分析报告时写入「数据质量」章节。增删后即时保存。</p>
        <div v-if="anomaliesLoading" class="empty-hint">加载中…</div>
        <div v-else>
          <div v-if="!anomalies.length" class="empty-hint">本月暂无异常日</div>
          <div v-for="(a, i) in anomalies" :key="i" class="anom-item">
            <span class="anom-date">{{ a.date }}</span>
            <span class="anom-type-tag" :class="anomTypeClass(a.type)">{{ a.type }}</span>
            <span class="anom-note">{{ a.note || '—' }}</span>
            <button class="link danger" type="button" @click="removeAnomaly(i)">删</button>
          </div>
          <div class="anom-form">
            <input type="date" v-model="anomDate" class="anom-input" />
            <select v-model="anomType" class="anom-input">
              <option>降雨</option>
              <option>系统故障</option>
              <option>其他</option>
            </select>
            <input type="text" v-model="anomNote" class="anom-input anom-note-input" placeholder="说明（可选）" />
            <button class="btn" type="button" :disabled="!anomDate || anomaliesSaving" @click="addAnomaly">
              {{ anomaliesSaving ? '保存中…' : '+ 添加' }}
            </button>
          </div>
        </div>
      </section>

      <!-- 台账 -->
      <section v-if="isPlatform" class="card">
        <h3>台账材料</h3>

        <h4>部门挂账案件</h4>
        <table class="ami-grid">
          <thead>
            <tr><th>单位</th><th>数量</th><th>主要内容</th><th>理由</th><th>截止时间</th><th></th></tr>
          </thead>
          <tbody>
            <tr v-for="(it, i) in ledgers.pending" :key="i">
              <td><input list="unit-list" v-model="it.unit_name" /></td>
              <td><input type="number" v-model.number="it.piece_cnt" min="0" /></td>
              <td><input v-model="it.content" /></td>
              <td><input v-model="it.reason" /></td>
              <td><input type="date" v-model="it.deadline" /></td>
              <td><button class="link danger" @click="ledgers.pending.splice(i,1)">删</button></td>
            </tr>
          </tbody>
        </table>
        <button class="btn" @click="ledgers.pending.push({unit_name:'',piece_cnt:null,content:'',reason:'',deadline:''})">+ 添加挂账</button>

        <h4>1月至今积压案件</h4>
        <table class="ami-grid">
          <thead>
            <tr><th>单位</th><th>部门</th><th>数量</th><th>主要内容</th><th></th></tr>
          </thead>
          <tbody>
            <tr v-for="(it, i) in ledgers.backlog" :key="i">
              <td><input list="unit-list" v-model="it.unit_name" /></td>
              <td><input list="dept-list" v-model="it.dept_name" /></td>
              <td><input type="number" v-model.number="it.piece_cnt" min="0" /></td>
              <td><input v-model="it.content" /></td>
              <td><button class="link danger" @click="ledgers.backlog.splice(i,1)">删</button></td>
            </tr>
          </tbody>
        </table>
        <button class="btn" @click="ledgers.backlog.push({unit_name:'',dept_name:'',piece_cnt:null,content:''})">+ 添加积压</button>

        <h4>表扬件</h4>
        <table class="ami-grid">
          <thead>
            <tr><th>来源</th><th>单位</th><th>内容</th><th></th></tr>
          </thead>
          <tbody>
            <tr v-for="(it, i) in ledgers.praise" :key="i">
              <td><input v-model="it.source" /></td>
              <td><input list="unit-list" v-model="it.unit_name" /></td>
              <td><input v-model="it.content" /></td>
              <td><button class="link danger" @click="ledgers.praise.splice(i,1)">删</button></td>
            </tr>
          </tbody>
        </table>
        <button class="btn" @click="ledgers.praise.push({source:'',unit_name:'',content:''})">+ 添加表扬</button>
      </section>

      <!-- 采集员 -->
      <section v-if="isCollector" class="card">
        <h3>采集员录入</h3>
        <h4>单体垃圾件数</h4>
        <div class="row">
          <div class="field" v-for="r in tmpl.garbage_regions" :key="r.region">
            <label>{{ r.region }}（{{ r.district }}）</label>
            <input type="number" min="0" v-model.number="garbage[r.region]" />
          </div>
        </div>
        <div class="row">
          <div class="field">
            <label>采集员自行处置数</label>
            <input type="number" min="0" v-model.number="selfDisposeCnt" />
          </div>
          <div class="field">
            <label>专项采集汇总（自动）</label>
            <input :value="specialSummary" disabled />
          </div>
          <div class="field">
            <label>专项采集不考核数（自动）</label>
            <input :value="noAssessTotal" disabled />
          </div>
        </div>

        <h4>专项采集明细（类别 + 件数）</h4>
        <table class="ami-grid">
          <thead>
            <tr><th>大类</th><th>小类</th><th>件数</th><th></th></tr>
          </thead>
          <tbody>
            <tr v-for="(d, i) in specialDetails" :key="i">
              <td>
                <select v-model="d.major_name" @change="onMajorChange(d)">
                  <option value="">选择大类</option>
                  <option v-for="c in categories" :key="c.id" :value="c.cat_name">{{ c.cat_name }}</option>
                </select>
              </td>
              <td>
                <select v-model="d.minor_name">
                  <option value="">选择小类</option>
                  <option v-for="s in subOptions[d.major_name] || []" :key="s.id" :value="s.sub_name">{{ s.sub_name }}</option>
                </select>
              </td>
              <td><input type="number" min="0" v-model.number="d.piece_cnt" /></td>
              <td><button class="link danger" @click="specialDetails.splice(i,1)">删</button></td>
            </tr>
          </tbody>
        </table>
        <button class="btn" @click="specialDetails.push({major_name:'',minor_name:'',piece_cnt:0})">+ 添加明细</button>
      </section>
    </div>

    <datalist id="unit-list">
      <option v-for="u in allUnits" :key="u.id" :value="u.unit_name" />
    </datalist>
    <datalist id="dept-list">
      <option v-for="u in allUnits" :key="'d'+u.id" :value="u.unit_name" />
    </datalist>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'

const props = defineProps({
  mode: {
    type: String,
    default: 'platform',
    validator: (v) => ['platform', 'collector'].includes(v)
  }
})

const isPlatform = computed(() => props.mode !== 'collector')
const isCollector = computed(() => props.mode === 'collector')
const saveLabel = computed(() => (isCollector.value ? '保存本月采集数据' : '保存本月平台数据'))

const batch = ref('')
const months = ref([])
const tmpl = ref({
  dispatch_teams: [], sanitation_districts: [], garden_districts: [],
  parks: [], municipal_units: [], garbage_regions: [],
})
const monthly = reactive({ assessment_case_cnt: null, work_note: '', extra_note: '' })
const scoreMap = reactive({})
const garbage = reactive({ 东: 0, 西: 0, 南: 0, 北: 0, 中: 0 })
const selfDisposeCnt = ref(0)
const specialDetails = ref([])
const ledgers = reactive({ pending: [], backlog: [], praise: [] })
const categories = ref([])
const subOptions = reactive({})
const allUnits = ref([])
const saving = ref(false)
const loadedHint = ref('')

// 采集异常日（月报 config）
const anomalies = ref([])
const anomaliesLoading = ref(false)
const anomaliesSaving = ref(false)
const anomDate = ref('')
const anomType = ref('降雨')
const anomNote = ref('')

function anomTypeClass(type) {
  if (type === '系统故障') return 'fault'
  if (type === '降雨') return 'rain'
  return 'other'
}

async function loadAnomalies() {
  anomalies.value = []
  anomDate.value = ''
  anomNote.value = ''
  if (!isPlatform.value || !batch.value) return
  anomaliesLoading.value = true
  try {
    const res = await axios.get(`/api/monthly-report/${batch.value}/config`)
    anomalies.value = res.data?.anomalies || []
  } catch {
    anomalies.value = []
  } finally {
    anomaliesLoading.value = false
  }
}

async function saveAnomalies() {
  if (!isPlatform.value || !batch.value) return
  anomaliesSaving.value = true
  try {
    const res = await axios.put(`/api/monthly-report/${batch.value}/config`, {
      anomalies: anomalies.value,
    })
    if (res.data?.anomalies) anomalies.value = res.data.anomalies
  } catch (e) {
    ElMessage.error('采集异常日保存失败: ' + (e.response?.data?.error || e.message))
  } finally {
    anomaliesSaving.value = false
  }
}

async function addAnomaly() {
  if (!anomDate.value) return
  anomalies.value = [...anomalies.value, {
    date: anomDate.value,
    type: anomType.value,
    note: anomNote.value || '',
  }]
  anomDate.value = ''
  anomNote.value = ''
  await saveAnomalies()
}

async function removeAnomaly(idx) {
  anomalies.value = anomalies.value.filter((_, i) => i !== idx)
  await saveAnomalies()
}

const specialSummary = computed(() =>
  specialDetails.value.reduce((s, d) => s + (Number(d.piece_cnt) || 0), 0)
)
const garbageTotal = computed(() =>
  Object.values(garbage).reduce((s, n) => s + (Number(n) || 0), 0)
)
const noAssessTotal = computed(() =>
  garbageTotal.value + (Number(selfDisposeCnt.value) || 0) + specialSummary.value
)

function formatMonth(b) {
  if (!b || b.length < 6) return b
  return `${b.slice(0, 4)}年${b.slice(4, 6)}月`
}

function scoreKey(ut, unit, st) {
  return `${ut}|${unit}|${st}`
}

function initScores() {
  Object.keys(scoreMap).forEach(k => delete scoreMap[k])
  if (!isPlatform.value) return
  for (const t of tmpl.value.dispatch_teams) {
    scoreMap[scoreKey('dispatch', t, 'team')] = 100
    scoreMap[scoreKey('dispatch', t, 'street')] = 100
    scoreMap[scoreKey('dispatch', t, 'extra')] = 0
  }
  for (const d of tmpl.value.sanitation_districts) {
    scoreMap[scoreKey('sanitation', d, 'center')] = 100
    scoreMap[scoreKey('sanitation', d, 'extra')] = 0
  }
  for (const d of tmpl.value.garden_districts) {
    scoreMap[scoreKey('garden', d, 'center')] = 100
    scoreMap[scoreKey('garden', d, 'extra')] = 0
  }
  for (const p of tmpl.value.parks) {
    scoreMap[scoreKey('garden_park', p, 'center')] = 100
    scoreMap[scoreKey('garden_park', p, 'extra')] = 0
  }
  for (const u of tmpl.value.municipal_units) {
    scoreMap[scoreKey('municipal', u, 'extra')] = 0
  }
  for (const r of ['东', '西', '南', '北', '中']) garbage[r] = 0
}

async function fetchMonths() {
  try {
    const res = await axios.get('/api/assessment/months')
    if (res.data?.success) months.value = res.data.months || []
  } catch (e) { /* ignore */ }
}

async function fetchTemplate() {
  const res = await axios.get('/api/assessment/manual/template')
  if (res.data?.success) tmpl.value = res.data
  initScores()
}

async function fetchDicts() {
  const tasks = []
  if (isCollector.value) tasks.push(axios.get('/api/dict/categories'))
  if (isPlatform.value) tasks.push(axios.get('/api/assessment/units'))
  const results = await Promise.all(tasks)
  let i = 0
  if (isCollector.value) {
    const cats = results[i++]
    if (cats.data?.success) categories.value = cats.data.categories || []
  }
  if (isPlatform.value) {
    const units = results[i++]
    if (units.data?.success) allUnits.value = units.data.units || []
  }
}

async function onMajorChange(row) {
  row.minor_name = ''
  if (!row.major_name) return
  const cat = categories.value.find(c => c.cat_name === row.major_name)
  if (!cat) return
  const res = await axios.get('/api/dict/subcategories', { params: { category_id: cat.id } })
  if (res.data?.success) subOptions[row.major_name] = res.data.subcategories || []
}

async function loadAll() {
  if (!batch.value) return
  initScores()
  ledgers.pending = []
  ledgers.backlog = []
  ledgers.praise = []
  specialDetails.value = []
  selfDisposeCnt.value = 0
  monthly.assessment_case_cnt = null
  monthly.work_note = ''
  monthly.extra_note = ''
  loadedHint.value = '加载中…'
  try {
    const res = await axios.get('/api/assessment/manual', { params: { batch: batch.value } })
    if (!res.data?.success) {
      ElMessage.error(res.data?.error || '加载失败')
      loadedHint.value = ''
      return
    }
    const d = res.data
    if (isPlatform.value) {
      if (d.monthly) {
        monthly.assessment_case_cnt = d.monthly.assessment_case_cnt
        monthly.work_note = d.monthly.work_note || ''
        monthly.extra_note = d.monthly.extra_note || ''
      }
      for (const s of d.scores || []) {
        scoreMap[scoreKey(s.unit_type, s.unit_name, s.score_type)] = s.score_value
      }
      for (const l of d.ledgers || []) {
        const item = { ...l }
        if (item.deadline) item.deadline = String(item.deadline).slice(0, 10)
        if (l.ledger_type === 'pending') ledgers.pending.push(item)
        else if (l.ledger_type === 'backlog') ledgers.backlog.push(item)
        else if (l.ledger_type === 'praise') ledgers.praise.push(item)
      }
      loadAnomalies()
    }
    if (isCollector.value) {
      for (const g of d.garbage || []) {
        if (g.region) garbage[g.region] = g.piece_count
      }
      if (d.collector) selfDisposeCnt.value = d.collector.self_dispose_cnt || 0
      specialDetails.value = (d.special_details || []).map(x => ({
        major_name: x.major_name, minor_name: x.minor_name, piece_cnt: x.piece_cnt,
      }))
      for (const row of specialDetails.value) {
        if (row.major_name && !subOptions[row.major_name]) await onMajorChange(row)
      }
    }
    if (isPlatform.value) {
      loadedHint.value = d.monthly || d.scores.length || (d.ledgers || []).length ? '已回填已录入数据' : '该月尚未录入'
    } else {
      const hasCollector = (d.garbage || []).length || d.collector || (d.special_details || []).length
      loadedHint.value = hasCollector ? '已回填已录入数据' : '该月尚未录入'
    }
  } catch (e) {
    ElMessage.error('加载失败')
    loadedHint.value = ''
  }
}

function collectScores() {
  const scores = []
  for (const [k, v] of Object.entries(scoreMap)) {
    if (v === undefined || v === null || v === '') continue
    const [unit_type, unit_name, score_type] = k.split('|')
    scores.push({ unit_type, unit_name, score_type, score_value: v })
  }
  return scores
}

async function saveAll() {
  if (!batch.value) return
  saving.value = true
  try {
    const url = isCollector.value
      ? '/api/assessment/manual/save-collector'
      : '/api/assessment/manual/save-platform'
    const payload = isCollector.value
      ? {
          batch: batch.value,
          garbage: { ...garbage },
          self_dispose_cnt: selfDisposeCnt.value,
          special_details: specialDetails.value.filter(d => d.major_name && d.minor_name),
        }
      : {
          batch: batch.value,
          monthly: {
            assessment_case_cnt: monthly.assessment_case_cnt,
            work_note: monthly.work_note,
            extra_note: monthly.extra_note,
          },
          scores: collectScores(),
          ledgers: {
            pending: ledgers.pending,
            backlog: ledgers.backlog,
            praise: ledgers.praise,
          },
        }
    const res = await axios.post(url, payload)
    if (res.data?.success) {
      ElMessage.success('已保存')
      loadedHint.value = '已保存 ' + new Date().toLocaleTimeString()
    } else {
      ElMessage.error(res.data?.error || '保存失败')
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  await Promise.all([fetchMonths(), fetchTemplate(), fetchDicts()])
})
</script>

<style scoped>
.ami-tab { display: flex; flex-direction: column; gap: 16px; }
.toolbar { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; }
.lbl { font-size: 13px; color: var(--text-secondary); }
.sel, .field input, .field select, .ami-grid input, .ami-grid select, .ami-grid textarea, textarea {
  height: 32px; padding: 0 8px; border: 1px solid var(--border-lighter, #e5e7eb);
  border-radius: 6px; background: var(--bg-card, #fff); color: var(--text-primary); font-size: 13px;
}
textarea, .field textarea { height: auto; padding: 8px; width: 100%; }
.btn {
  height: 32px; padding: 0 14px; border-radius: 8px; border: 1px solid var(--border-lighter, #e5e7eb);
  background: var(--bg-secondary, #f8fafc); cursor: pointer; font-size: 13px;
}
.btn-primary {
  background: var(--primary-600, #2563eb); color: #fff; border-color: transparent;
}
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
.hint { font-size: 12px; color: var(--text-tertiary); }
.empty { padding: 40px; text-align: center; color: var(--text-tertiary); }
.card {
  border: 1px solid var(--border-lighter, #e5e7eb); border-radius: 10px; padding: 16px;
  background: var(--bg-card, #fff);
}
.card h3 { margin: 0 0 12px; font-size: 15px; }
.card h4 { margin: 16px 0 8px; font-size: 13px; color: var(--text-secondary); }
.row { display: flex; flex-wrap: wrap; gap: 16px; margin-bottom: 12px; }
.field { display: flex; flex-direction: column; gap: 4px; min-width: 120px; }
.field label { font-size: 12px; color: var(--text-tertiary); }
.ami-grid { width: 100%; border-collapse: collapse; font-size: 13px; margin-bottom: 8px; }
.ami-grid th, .ami-grid td { border-bottom: 1px solid var(--border-lighter, #e5e7eb); padding: 6px 8px; text-align: left; }
.ami-grid th { color: var(--text-secondary); font-weight: 600; background: var(--bg-secondary, #f8fafc); }
/* 输入框水平内边距收窄，使输入值与表头文字左对齐（否则值比表头右缩进约9px） */
.ami-grid input, .ami-grid select { width: 100%; min-width: 80px; padding: 0 2px; }
.link { border: none; background: none; color: var(--primary-600, #2563eb); cursor: pointer; font-size: 12px; }
.link.danger { color: #dc2626; }
.card-tip { margin: 0 0 12px; font-size: 12px; color: var(--text-tertiary, #6b7280); line-height: 1.6; }
.grid-empty { text-align: center; color: var(--text-tertiary, #9ca3af); font-size: 12px; padding: 12px 0; }
.empty-hint { font-size: 12px; color: var(--text-tertiary); padding: 4px 0 8px; }
.anom-item {
  display: flex; align-items: center; gap: 8px; padding: 8px 0;
  border-bottom: 1px solid var(--border-lighter, #e5e7eb); font-size: 13px;
}
.anom-item:last-of-type { border-bottom: none; }
.anom-date { font-weight: 600; color: var(--text-primary); min-width: 88px; }
.anom-type-tag {
  font-size: 11px; padding: 2px 6px; border-radius: 3px; white-space: nowrap;
}
.anom-type-tag.rain { background: #e6f7ff; color: #1890ff; }
.anom-type-tag.fault { background: #fff2e8; color: #fa541c; }
.anom-type-tag.other { background: #f0f0f0; color: #666; }
.anom-note { flex: 1; color: var(--text-secondary); min-width: 0; }
.anom-form {
  display: flex; gap: 8px; margin-top: 12px; flex-wrap: wrap; align-items: center;
}
.anom-input {
  height: 32px; padding: 0 8px; border: 1px solid var(--border-lighter, #e5e7eb);
  border-radius: 6px; background: var(--bg-card, #fff); color: var(--text-primary); font-size: 13px;
}
.anom-input:focus { outline: none; border-color: var(--primary-500); }
.anom-note-input { flex: 1; min-width: 120px; }
</style>
