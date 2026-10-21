<template>
  <div class="cyw-check-tab">
    <div class="page-header">
      <div>
        <h2>在岗抽查</h2>
        <p class="page-sub">
          从管理单位为「城市管理局」的点位中随机抽取 5 个，每个点位同时核对<b>环卫</b>和<b>执法</b>两侧的联系人。
          点「去电」后开始 5 分钟倒计时，倒计时内人员在监控中出现就点「在岗」；
          到点未点，系统自动判定为不在岗。刷新或关掉页面都不会丢进度——判定以服务器时间为准。
        </p>
      </div>
      <div class="report-actions">
        <el-button type="primary" :loading="starting" @click="startCheck">开始抽查</el-button>
        <el-button v-if="batch" :disabled="!batch.items.length" @click="finishCheck">结束抽查</el-button>
        <el-button v-if="batch" :loading="exporting" @click="exportTxt">下载抽查报告</el-button>
      </div>
    </div>

    <div v-if="!batch" class="empty-tip">
      <el-empty description="暂无进行中的抽查">
        <template #default>
          <el-button type="primary" @click="startCheck">开始抽查</el-button>
        </template>
      </el-empty>
    </div>

    <template v-else>
      <div class="stat-cards">
        <el-card shadow="never" class="stat-card">
          <div class="stat-num info">{{ batch.items.length }}</div>
          <div class="stat-label">抽查项数</div>
        </el-card>
        <el-card shadow="never" class="stat-card">
          <div class="stat-num success">{{ batch.on_count }}</div>
          <div class="stat-label">在岗</div>
        </el-card>
        <el-card shadow="never" class="stat-card">
          <div class="stat-num danger">{{ batch.off_count }}</div>
          <div class="stat-label">不在岗</div>
        </el-card>
        <el-card shadow="never" class="stat-card">
          <div class="stat-num warning">{{ batch.wait_count }}</div>
          <div class="stat-label">待抽查</div>
        </el-card>
      </div>

      <el-card shadow="never" class="batch-meta">
        <span>抽查批次：<b>{{ batch.batch_no }}</b></span>
        <span>发起人：{{ batch.created_by }}</span>
        <span>发起时间：{{ batch.created_at }}</span>
        <el-tag :type="batch.status === '进行中' ? 'success' : 'info'" size="small">{{ batch.status }}</el-tag>
      </el-card>

      <el-card shadow="never">
        <el-table :data="batch.items" border stripe :span-method="spanMethod">
          <el-table-column prop="spot_seq" label="#" width="50" />
          <el-table-column prop="spot_no" label="点位编号" width="110" />
          <el-table-column prop="spot_name" label="点位名称" min-width="180" show-overflow-tooltip />
          <el-table-column prop="dept_label" label="部门/角色" width="150" show-overflow-tooltip />
          <el-table-column label="联系人" width="150">
            <template #default="{ row }">
              <span v-if="row.person">{{ row.person }}</span>
              <el-tag v-else type="info" size="small">未登记</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="phone" label="电话" width="130" />
          <el-table-column label="倒计时" width="150">
            <template #default="{ row }">
              <span v-if="row.status !== '待抽查'" :class="row.status === '在岗' ? 'txt-ok' : 'txt-no'">
                {{ row.status }}
              </span>
              <span v-else-if="!row.deadline_at" class="txt-idle">未开始</span>
              <span v-else-if="remainSec(row) > 0" class="txt-count">{{ fmtSec(remainSec(row)) }}</span>
              <span v-else class="txt-no">已到点，待判定</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="230" fixed="right">
            <template #default="{ row }">
              <el-button
                size="small"
                type="primary"
                plain
                :disabled="!row.person || row.status !== '待抽查' || !!row.called_at || !isAdmin"
                :loading="row._calling"
                @click="callItem(row)"
              >去电</el-button>
              <el-button
                size="small"
                type="success"
                plain
                :disabled="!row.person || row.status !== '待抽查' || !row.called_at || !isAdmin"
                :loading="row._duty"
                @click="markOnDuty(row)"
              >在岗</el-button>
              <el-button
                size="small"
                :disabled="!row.person || !isAdmin"
                @click="openCorrect(row)"
              >修正</el-button>
            </template>
          </el-table-column>
          <el-table-column prop="pick_rule" label="取人规则" width="110" show-overflow-tooltip />
          <el-table-column label="判定信息" min-width="220">
            <template #default="{ row }">
              <template v-if="row.result_at">
                <div>{{ row.result_at }}</div>
                <div class="txt-sub">{{ row.result_by }}</div>
                <div v-if="row.corrected" class="txt-correct">
                  管理员修正{{ row.corrected_by ? '：' + row.corrected_by : '' }}
                  <span v-if="row.corrected_reason">（{{ row.corrected_reason }}）</span>
                </div>
              </template>
              <span v-else class="txt-idle">—</span>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </template>

    <el-card shadow="never" class="history-card" v-if="history.length">
      <template #header>
        <div class="detail-title"><span>历史抽查</span></div>
      </template>
      <el-table :data="history" border>
        <el-table-column prop="batch_no" label="批次号" width="180" />
        <el-table-column prop="created_at" label="发起时间" width="180" />
        <el-table-column prop="created_by" label="发起人" width="110" />
        <el-table-column label="人数" width="70">
          <template #default="{ row }">{{ row.item_cnt }}</template>
        </el-table-column>
        <el-table-column label="在岗/不在岗" width="130">
          <template #default="{ row }">
            <span class="txt-ok">{{ row.on_cnt }}</span> / <span class="txt-no">{{ row.off_cnt }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="90" />
        <el-table-column label="操作" width="160">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click="viewBatch(row.id)">查看</el-button>
            <el-button size="small" link type="primary" @click="exportBatch(row.id)">下载报告</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="correctDlg" title="修正到岗情况" width="420px">
      <el-alert type="warning" :closable="false" show-icon
        title="修正会覆盖原判定并写入留痕（谁、何时、改成什么）" style="margin-bottom: 12px" />
      <el-form label-width="80px">
        <el-form-item label="点位">
          <span>{{ editing?.spot_no }} {{ editing?.spot_name }}</span>
        </el-form-item>
        <el-form-item label="联系人">
          <span>{{ editing?.person }} {{ editing?.phone }}</span>
        </el-form-item>
        <el-form-item label="修正为">
          <el-radio-group v-model="correctForm.status">
            <el-radio-button label="在岗">在岗</el-radio-button>
            <el-radio-button label="不在岗">不在岗</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="原因">
          <el-input v-model="correctForm.reason" type="textarea" :rows="2" maxlength="200"
            show-word-limit placeholder="选填，例如：电话未接通但监控确认在岗" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="correctDlg = false">取消</el-button>
        <el-button type="primary" :loading="correcting" @click="submitCorrect">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useUserStore } from '../stores/user'

const userStore = useUserStore()
// 只有管理员能「修正」判定结果（后端 correct 接口就是 admin_required）
const isAdmin = computed(() => userStore.isAdmin)
const batch = ref(null)
const history = ref([])
const starting = ref(false)
const exporting = ref(false)
const nowTs = ref(Date.now())
let timer = null

onMounted(async () => {
  await loadCurrent()
  await loadHistory()
  timer = setInterval(() => { nowTs.value = Date.now() }, 1000)
})

onUnmounted(() => { if (timer) clearInterval(timer) })

// 剩余秒数按服务器给的 deadline_at 算：本地只做显示，判定永远以服务端为准
function remainSec(row) {
  if (!row.deadline_at) return -1
  const end = new Date(row.deadline_at.replace(' ', 'T')).getTime()
  return Math.floor((end - nowTs.value) / 1000)
}

function fmtSec(s) {
  const m = Math.floor(s / 60)
  const ss = String(s % 60).padStart(2, '0')
  return `${m}:${ss}`
}

// 一个点位出两行（环卫一行、执法一行）：给每行标上「属于第几个点位」和「左侧合并几行」，
// 表格用 span-method 把点位序号/编号/名称合成一格，点位信息只显示一次
function decorate(items) {
  let seq = 0
  for (let i = 0; i < items.length;) {
    let j = i
    while (j < items.length && items[j].spot_id === items[i].spot_id) j++
    seq += 1
    items[i].spot_seq = seq
    items[i]._spanRows = j - i
    for (let k = i + 1; k < j; k++) {
      items[k].spot_seq = seq
      items[k]._spanRows = 0
    }
    i = j
  }
  return items
}

function spanMethod({ row, column }) {
  if (['#', '点位编号', '点位名称'].includes(column.label)) {
    const n = row._spanRows ?? 1
    return n > 0 ? { rowspan: n, colspan: 1 } : { rowspan: 0, colspan: 0 }
  }
  return { rowspan: 1, colspan: 1 }
}

async function loadCurrent() {
  try {
    const { data } = await axios.get('/api/cyw/check/current')
    if (data.batch) data.batch.items = decorate(data.batch.items)
    batch.value = data.batch
  } catch { /* error toast via interceptor */ }
}

async function loadHistory() {
  try {
    const { data } = await axios.get('/api/cyw/check/history', { params: { size: 10 } })
    history.value = data.list || []
  } catch { /* error toast via interceptor */ }
}

async function startCheck() {
  try {
    await ElMessageBox.confirm(
      '将从管理单位为「城市管理局」的点位中随机抽取 5 个开始新一轮抽查，'
      + '每个点位同时列出环卫和执法两侧的联系人。'
      + '若当前有未结束的抽查，系统会先把它按规则判定完毕后重开。',
      '开始抽查', { type: 'warning', confirmButtonText: '开始', cancelButtonText: '取消' })
  } catch { return }
  starting.value = true
  try {
    const { data } = await axios.post('/api/cyw/check/start', { spot_count: 5 })
    data.batch.items = decorate(data.batch.items)
    batch.value = data.batch
    const spots = new Set(data.batch.items.map((i) => i.spot_id)).size
    ElMessage.success(`已抽取 ${spots} 个点位、${data.batch.items.length} 名联系人，请逐个去电核对`)
    loadHistory()
  } catch { /* error toast via interceptor */ }
  finally { starting.value = false }
}

async function callItem(row) {
  row._calling = true
  try {
    await axios.post(`/api/cyw/check/item/${row.id}/call`)
    ElMessage.success('已开始 5 分钟倒计时')
    await loadCurrent()
  } catch { /* error toast via interceptor */ }
  finally { row._calling = false }
}

async function markOnDuty(row) {
  row._duty = true
  try {
    await axios.post(`/api/cyw/check/item/${row.id}/on-duty`)
    ElMessage.success('已判定为在岗')
    await loadCurrent()
  } catch (e) {
    // 倒计时已过：后端返回 409 need_correct，引导走修正通道而不是死按钮
    if (e?.response?.status === 409 && e?.response?.data?.need_correct) {
      ElMessage.warning(e.response.data.error || '倒计时已结束，请使用「修正」通道')
    }
  } finally { row._duty = false }
}

async function finishCheck() {
  try {
    await ElMessageBox.confirm(
      '结束抽查后，仍未判定的明细将按「不在岗」记录，且不能再点「在岗」。确定结束？',
      '结束抽查', { type: 'warning', confirmButtonText: '结束', cancelButtonText: '取消' })
  } catch { return }
  try {
    const { data } = await axios.post(`/api/cyw/check/batch/${batch.value.id}/finish`)
    batch.value = data.batch
    ElMessage.success('抽查已结束，可下载报告')
    loadHistory()
  } catch { /* error toast via interceptor */ }
}

function download(resp, fallback) {
  const cd = resp.headers['content-disposition'] || ''
  const m = /filename\*=UTF-8''([^;]+)/i.exec(cd)
  const name = m ? decodeURIComponent(m[1]) : fallback
  const url = URL.createObjectURL(new Blob([resp.data], { type: 'text/plain; charset=utf-8' }))
  const a = document.createElement('a')
  a.href = url
  a.download = name
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

async function exportTxt() {
  exporting.value = true
  try {
    const resp = await axios.get(`/api/cyw/check/batch/${batch.value.id}/export`, { responseType: 'blob' })
    download(resp, '创文在岗抽查报告.txt')
    ElMessage.success('报告已下载')
  } catch (e) {
    const msg = await e?.response?.data?.text?.()
    ElMessage.error(msg ? JSON.parse(msg).error : '导出失败')
  } finally { exporting.value = false }
}

async function exportBatch(id) {
  try {
    const resp = await axios.get(`/api/cyw/check/batch/${id}/export`, { responseType: 'blob' })
    download(resp, '创文在岗抽查报告.txt')
    ElMessage.success('报告已下载')
  } catch { /* error toast via interceptor */ }
}

async function viewBatch(id) {
  try {
    const { data } = await axios.get(`/api/cyw/check/batch/${id}`)
    batch.value = data.batch
  } catch { /* error toast via interceptor */ }
}

const correctDlg = ref(false)
const correcting = ref(false)
const editing = ref(null)
const correctForm = reactive({ status: '在岗', reason: '' })

function openCorrect(row) {
  editing.value = row
  correctForm.status = row.status === '在岗' ? '不在岗' : '在岗'
  correctForm.reason = ''
  correctDlg.value = true
}

async function submitCorrect() {
  correcting.value = true
  try {
    await axios.put(`/api/cyw/check/item/${editing.value.id}/correct`, {
      status: correctForm.status, reason: correctForm.reason,
    })
    ElMessage.success('已修正并留痕')
    correctDlg.value = false
    await loadCurrent()
  } catch { /* error toast via interceptor */ }
  finally { correcting.value = false }
}
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; }
.page-header h2 { margin: 0 0 4px; }
.page-sub { margin: 0; color: #909399; font-size: 13px; max-width: 760px; line-height: 1.6; }
.report-actions { display: flex; gap: 10px; align-items: center; }
.stat-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}
.stat-card { text-align: center; padding: 8px 0; }
.stat-num { font-size: 32px; font-weight: bold; }
.stat-num.success { color: #67c23a; }
.stat-num.danger { color: #f56c6c; }
.stat-num.warning { color: #e6a23c; }
.stat-num.info { color: #909399; }
.stat-label { color: #606266; font-size: 13px; margin-top: 4px; }
.batch-meta { margin-bottom: 12px; }
.batch-meta :deep(.el-card__body) {
  display: flex; gap: 24px; align-items: center; font-size: 13px; color: #606266;
}
.empty-tip { padding: 40px 0; }
.history-card { margin-top: 16px; }
.detail-title { display: flex; justify-content: space-between; font-weight: bold; }
.txt-ok { color: #67c23a; font-weight: bold; }
.txt-no { color: #f56c6c; font-weight: bold; }
.txt-idle { color: #c0c4cc; }
.txt-count { color: #e6a23c; font-weight: bold; font-variant-numeric: tabular-nums; }
.txt-sub { color: #909399; font-size: 12px; }
.txt-correct { color: #e6a23c; font-size: 12px; }
</style>
