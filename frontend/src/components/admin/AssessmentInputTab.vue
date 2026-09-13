<template>
  <div class="ami-tab">
    <div class="toolbar">
      <label class="lbl">考核月份</label>
      <select v-model="batch" class="sel" @change="loadAll">
        <option value="">请选择月份</option>
        <option v-for="m in months" :key="m.batch" :value="m.batch">{{ formatMonth(m.batch) }}</option>
      </select>
      <button class="btn btn-primary" :disabled="!batch || saving" @click="saveAll">
        {{ saving ? '保存中…' : '保存本月数据' }}
      </button>
      <span v-if="loadedHint" class="hint">{{ loadedHint }}</span>
    </div>

    <div v-if="!batch" class="empty">请先选择考核月份</div>

    <div v-else class="sections">
      <!-- 平台 -->
      <section class="card">
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

      <!-- 台账 -->
      <section class="card">
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
      <section class="card">
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

    <!-- 豁免期（全局设置，不随月份变化） -->
    <section class="card">
      <h3>不参与考核设置（豁免期）</h3>
      <p class="card-tip">
        设置后，豁免期覆盖到的考核月份内，该部门整月不参与考核计算，考核计分页将显示备注及文件依据。此设置全局生效，不随上方考核月份变化。
      </p>
      <table class="ami-grid">
        <thead>
          <tr><th>部门</th><th>开始日期</th><th>截止日期</th><th>原因</th><th>文件依据</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-for="(it, i) in exemptions" :key="i">
            <td><input list="assess-unit-list" v-model="it.unit_name" /></td>
            <td><input type="date" v-model="it.start_date" /></td>
            <td><input type="date" v-model="it.end_date" /></td>
            <td><input v-model="it.reason" placeholder="不参与考核原因" /></td>
            <td>
              <template v-if="it.file_url">
                <a :href="it.file_url" target="_blank" class="file-link">{{ it.file_name || '查看文件' }}</a>
                <button class="link danger" @click="clearExemptFile(it)">删</button>
              </template>
              <button v-else class="link" :disabled="it._uploading" @click="pickExemptFile(i)">
                {{ it._uploading ? '上传中…' : '+ 上传依据' }}
              </button>
            </td>
            <td><button class="link danger" @click="exemptions.splice(i,1)">删</button></td>
          </tr>
          <tr v-if="!exemptions.length">
            <td colspan="6" class="grid-empty">暂无豁免设置</td>
          </tr>
        </tbody>
      </table>
      <div class="exempt-actions">
        <button class="btn" @click="addExempt">+ 添加豁免</button>
        <button class="btn btn-primary" :disabled="savingExempt" @click="saveExemptions">
          {{ savingExempt ? '保存中…' : '保存豁免设置' }}
        </button>
      </div>
    </section>

    <input ref="exemptFileInput" type="file" style="display:none" @change="onExemptFileChosen" />

    <datalist id="assess-unit-list">
      <option v-for="u in assessUnitOptions" :key="'a'+u" :value="u" />
    </datalist>
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

// 豁免期（全局，不随月份变化）
const exemptions = ref([])
const savingExempt = ref(false)
const exemptFileIndex = ref(-1)
const exemptFileInput = ref(null)

const assessUnitOptions = computed(() => {
  const t = tmpl.value
  const seen = new Set()
  const list = []
  for (const u of [...t.dispatch_teams, ...t.sanitation_districts, ...t.garden_districts, ...t.parks, ...t.municipal_units]) {
    if (u && !seen.has(u)) { seen.add(u); list.push(u) }
  }
  return list
})

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
  const [cats, units] = await Promise.all([
    axios.get('/api/dict/categories'),
    axios.get('/api/assessment/units'),
  ])
  if (cats.data?.success) categories.value = cats.data.categories || []
  if (units.data?.success) allUnits.value = units.data.units || []
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
    if (d.monthly) {
      monthly.assessment_case_cnt = d.monthly.assessment_case_cnt
      monthly.work_note = d.monthly.work_note || ''
      monthly.extra_note = d.monthly.extra_note || ''
    }
    for (const s of d.scores || []) {
      scoreMap[scoreKey(s.unit_type, s.unit_name, s.score_type)] = s.score_value
    }
    for (const g of d.garbage || []) {
      if (g.region) garbage[g.region] = g.piece_count
    }
    if (d.collector) selfDisposeCnt.value = d.collector.self_dispose_cnt || 0
    specialDetails.value = (d.special_details || []).map(x => ({
      major_name: x.major_name, minor_name: x.minor_name, piece_cnt: x.piece_cnt,
    }))
    for (const l of d.ledgers || []) {
      const item = { ...l }
      if (item.deadline) item.deadline = String(item.deadline).slice(0, 10)
      if (l.ledger_type === 'pending') ledgers.pending.push(item)
      else if (l.ledger_type === 'backlog') ledgers.backlog.push(item)
      else if (l.ledger_type === 'praise') ledgers.praise.push(item)
    }
    // preload sub options for existing details
    for (const row of specialDetails.value) {
      if (row.major_name && !subOptions[row.major_name]) await onMajorChange(row)
    }
    loadedHint.value = d.monthly || d.scores.length ? '已回填已录入数据' : '该月尚未录入'
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
    const payload = {
      batch: batch.value,
      monthly: {
        assessment_case_cnt: monthly.assessment_case_cnt,
        work_note: monthly.work_note,
        extra_note: monthly.extra_note,
      },
      scores: collectScores(),
      garbage: { ...garbage },
      self_dispose_cnt: selfDisposeCnt.value,
      special_details: specialDetails.value.filter(d => d.major_name && d.minor_name),
      ledgers: {
        pending: ledgers.pending,
        backlog: ledgers.backlog,
        praise: ledgers.praise,
      },
    }
    const res = await axios.post('/api/assessment/manual/save-all', payload)
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

// ---------- 豁免期 ----------
async function fetchExemptions() {
  try {
    const res = await axios.get('/api/assessment/exemptions')
    if (res.data?.success) {
      exemptions.value = (res.data.exemptions || []).map(x => ({
        unit_name: x.unit_name || '',
        start_date: String(x.start_date || '').slice(0, 10),
        end_date: String(x.end_date || '').slice(0, 10),
        reason: x.reason || '',
        file_url: x.file_url || '',
        file_name: x.file_name || '',
      }))
    }
  } catch (e) { /* ignore */ }
}

function addExempt() {
  exemptions.value.push({ unit_name: '', start_date: '', end_date: '', reason: '', file_url: '', file_name: '' })
}

function clearExemptFile(it) {
  it.file_url = ''
  it.file_name = ''
}

function pickExemptFile(i) {
  exemptFileIndex.value = i
  if (exemptFileInput.value) {
    exemptFileInput.value.value = ''
    exemptFileInput.value.click()
  }
}

async function onExemptFileChosen(e) {
  const i = exemptFileIndex.value
  const file = e.target.files && e.target.files[0]
  if (i < 0 || i >= exemptions.value.length || !file) return
  const row = exemptions.value[i]
  row._uploading = true
  try {
    const fd = new FormData()
    fd.append('file', file)
    const res = await axios.post('/api/upload/file', fd)
    if (res.data?.file_path) {
      row.file_url = res.data.file_path
      row.file_name = file.name
    } else {
      ElMessage.error(res.data?.error || '文件上传失败')
    }
  } catch (err) {
    ElMessage.error(err.response?.data?.error || '文件上传失败')
  } finally {
    row._uploading = false
    exemptFileIndex.value = -1
  }
}

async function saveExemptions() {
  const items = []
  for (const it of exemptions.value) {
    if (!it.unit_name && !it.start_date && !it.end_date && !it.reason && !it.file_url) continue
    if (!it.unit_name) { ElMessage.error('存在未填写部门的豁免行'); return }
    if (!it.start_date || !it.end_date) { ElMessage.error(`请补全「${it.unit_name}」的起止日期`); return }
    if (it.end_date < it.start_date) { ElMessage.error(`「${it.unit_name}」的截止日期不能早于开始日期`); return }
    items.push({
      unit_name: it.unit_name, start_date: it.start_date, end_date: it.end_date,
      reason: it.reason, file_url: it.file_url, file_name: it.file_name,
    })
  }
  savingExempt.value = true
  try {
    const res = await axios.post('/api/assessment/exemptions', { items })
    if (res.data?.success) {
      ElMessage.success(`豁免设置已保存（${res.data.saved || items.length} 条）`)
      fetchExemptions()
    } else {
      ElMessage.error(res.data?.error || '保存失败')
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '保存失败')
  } finally {
    savingExempt.value = false
  }
}

onMounted(async () => {
  await Promise.all([fetchMonths(), fetchTemplate(), fetchDicts(), fetchExemptions()])
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
.file-link { font-size: 12px; color: var(--primary-600, #2563eb); margin-right: 6px; word-break: break-all; }
.grid-empty { text-align: center; color: var(--text-tertiary, #9ca3af); font-size: 12px; padding: 12px 0; }
.exempt-actions { display: flex; justify-content: space-between; gap: 12px; }
</style>
