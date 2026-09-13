<template>
  <div class="assessment-page">
    <div class="page-header">
      <h2>考核计分</h2>
      <div class="header-actions">
        <el-select v-model="selectedBatch" placeholder="选择月份" @change="loadSummary" style="width: 150px">
          <el-option v-for="m in months" :key="m.batch" :label="formatMonth(m.batch)" :value="m.batch" />
        </el-select>
        <el-button type="primary" @click="calculateScores" :loading="calculating" :disabled="!selectedBatch">
          计算得分
        </el-button>
        <el-button type="success" @click="generateMonthlyReport" :loading="generatingReport" :disabled="!selectedBatch">
          生成考核月报
        </el-button>
      </div>
    </div>

    <div v-if="manualHint" class="manual-hint" :class="manualHintClass">{{ manualHint }}</div>

    <div v-if="summary" class="overview-section">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="处置情况" name="overview">
          <div class="table-wrapper">
            <table class="data-table">
              <thead>
                <tr>
                  <th>处置部门</th><th>应结案数</th><th>结案数</th><th>结案率</th><th>占比</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(stats, dept) in summary.dept_groups" :key="dept">
                  <td>{{ dept }}</td>
                  <td>{{ stats.total }}</td>
                  <td>{{ stats.closed }}</td>
                  <td>{{ formatRate(stats.closed, stats.total) }}</td>
                  <td>{{ formatPercent(stats.total, totalCount) }}</td>
                </tr>
                <tr class="total-row">
                  <td><strong>合计</strong></td>
                  <td><strong>{{ totalCount }}</strong></td>
                  <td><strong>{{ totalClosed }}</strong></td>
                  <td><strong>{{ formatRate(totalClosed, totalCount) }}</strong></td>
                  <td><strong>100%</strong></td>
                </tr>
              </tbody>
            </table>
          </div>
        </el-tab-pane>

        <el-tab-pane label="市容秩序" name="dispatch">
          <div class="table-wrapper">
            <table class="data-table">
              <thead>
                <tr>
                  <th>执法分队</th><th>应结案数</th><th>结案数</th><th>超期率</th><th>延期率</th><th>返工率</th>
                  <th>系统分数</th><th>队考核分</th><th>街道办分</th><th>加减分项</th><th>总分</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(stats, team) in summary.dispatch_teams" :key="team">
                  <td>{{ team }}</td>
                  <td>{{ stats.total }}</td>
                  <td>{{ stats.closed }}</td>
                  <td>{{ formatRate(stats.overtime, stats.total) }}</td>
                  <td>{{ formatRate(stats.delayed, stats.total) }}</td>
                  <td>{{ formatRate(stats.rework, stats.total) }}</td>
                  <td>{{ results?.[team]?.system_score ?? '-' }}</td>
                  <td>{{ displayScore(team, 'team') }}</td>
                  <td>{{ displayScore(team, 'street') }}</td>
                  <td>{{ displayScore(team, 'extra') }}</td>
                  <td>
                    <template v-if="exemptInfo(team)">
                      <span class="exempt-tag">不参与考核</span>
                      <div class="exempt-note">{{ exemptInfo(team).note }}</div>
                      <a v-if="exemptInfo(team).file_url" :href="exemptInfo(team).file_url" target="_blank" class="exempt-file">依据：{{ exemptInfo(team).file_name || '查看文件' }}</a>
                    </template>
                    <strong v-else-if="results?.[team]?.final_score != null">{{ results[team].final_score }}</strong>
                    <span v-else class="miss">未录入，不参与计算</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="formula-box">
            <div class="formula-title">市容秩序（执法分队）计分公式</div>
            <ul class="formula-list">
              <li>系统分 =（按期结案率×100% + 超期结案率×40%）×80% +（1−延期率）×10% +（1−返工率）×10%</li>
              <li>总分 = 系统分×0.7 + 队考核分×0.15 + 街道办分×0.15 + 加减分项</li>
            </ul>
          </div>
        </el-tab-pane>

        <el-tab-pane label="环境卫生" name="sanitation">
          <div class="table-wrapper">
            <table class="data-table">
              <thead>
                <tr>
                  <th>环卫片区</th><th>应结案数</th><th>结案数</th><th>超期率</th><th>延期率</th><th>返工率</th>
                  <th>系统分数</th><th>单体垃圾得分</th><th>中心考核分</th><th>加减分项</th><th>总分</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(stats, district) in summary.sanitation_districts" :key="district">
                  <td>{{ district }}</td>
                  <td>{{ stats.total }}</td>
                  <td>{{ stats.closed }}</td>
                  <td>{{ formatRate(stats.overtime, stats.total) }}</td>
                  <td>{{ formatRate(stats.delayed, stats.total) }}</td>
                  <td>{{ formatRate(stats.rework, stats.total) }}</td>
                  <td>{{ results?.[district]?.system_score ?? '-' }}</td>
                  <td>{{ displayGarbage(district) }}</td>
                  <td>{{ displayScore(district, 'center', 'sanitation') }}</td>
                  <td>{{ displayScore(district, 'extra', 'sanitation') }}</td>
                  <td>
                    <template v-if="exemptInfo(district)">
                      <span class="exempt-tag">不参与考核</span>
                      <div class="exempt-note">{{ exemptInfo(district).note }}</div>
                      <a v-if="exemptInfo(district).file_url" :href="exemptInfo(district).file_url" target="_blank" class="exempt-file">依据：{{ exemptInfo(district).file_name || '查看文件' }}</a>
                    </template>
                    <strong v-else-if="results?.[district]?.final_score != null">{{ results[district].final_score }}</strong>
                    <span v-else class="miss">未录入，不参与计算</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="formula-box">
            <div class="formula-title">环境卫生（片区）计分公式</div>
            <ul class="formula-list">
              <li>系统分 =（按期结案率×100% + 超期结案率×40%）×80% +（1−延期率）×10% +（1−返工率）×10%</li>
              <li>单体垃圾得分 = 100 − 该片区垃圾件数×0.01</li>
              <li>总分 = 系统分×0.3 + 单体垃圾得分×0.3 + 中心考核分×0.4 + 加减分项</li>
            </ul>
          </div>
        </el-tab-pane>

        <el-tab-pane label="园林绿化" name="garden">
          <h4 class="sub-title">园林片区</h4>
          <div class="table-wrapper">
            <table class="data-table">
              <thead>
                <tr>
                  <th>园林片区</th><th>应结案数</th><th>结案数</th><th>超期率</th><th>延期率</th><th>返工率</th>
                  <th>系统分数</th><th>中心考核分</th><th>加减分项</th><th>总分</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(stats, district) in summary.garden_districts" :key="district">
                  <td>{{ district }}</td>
                  <td>{{ stats.total }}</td>
                  <td>{{ stats.closed }}</td>
                  <td>{{ formatRate(stats.overtime, stats.total) }}</td>
                  <td>{{ formatRate(stats.delayed, stats.total) }}</td>
                  <td>{{ formatRate(stats.rework, stats.total) }}</td>
                  <td>{{ results?.[district]?.system_score ?? '-' }}</td>
                  <td>{{ displayScore(district, 'center', 'garden') }}</td>
                  <td>{{ displayScore(district, 'extra', 'garden') }}</td>
                  <td>
                    <template v-if="exemptInfo(district)">
                      <span class="exempt-tag">不参与考核</span>
                      <div class="exempt-note">{{ exemptInfo(district).note }}</div>
                      <a v-if="exemptInfo(district).file_url" :href="exemptInfo(district).file_url" target="_blank" class="exempt-file">依据：{{ exemptInfo(district).file_name || '查看文件' }}</a>
                    </template>
                    <strong v-else-if="results?.[district]?.final_score != null">{{ results[district].final_score }}</strong>
                    <span v-else class="miss">未录入，不参与计算</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <h4 class="sub-title">公园广场</h4>
          <div class="table-wrapper">
            <table class="data-table">
              <thead>
                <tr>
                  <th>公园广场</th><th>应结案数</th><th>结案数</th><th>超期率</th><th>延期率</th><th>返工率</th>
                  <th>系统分数</th><th>中心考核分</th><th>加减分项</th><th>总分</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(stats, park) in summary.parks" :key="park">
                  <td>{{ park }}</td>
                  <td>{{ stats.total }}</td>
                  <td>{{ stats.closed }}</td>
                  <td>{{ formatRate(stats.overtime, stats.total) }}</td>
                  <td>{{ formatRate(stats.delayed, stats.total) }}</td>
                  <td>{{ formatRate(stats.rework, stats.total) }}</td>
                  <td>{{ results?.[park]?.system_score ?? '-' }}</td>
                  <td>{{ displayScore(park, 'center', 'garden_park') }}</td>
                  <td>{{ displayScore(park, 'extra', 'garden_park') }}</td>
                  <td>
                    <template v-if="exemptInfo(park)">
                      <span class="exempt-tag">不参与考核</span>
                      <div class="exempt-note">{{ exemptInfo(park).note }}</div>
                      <a v-if="exemptInfo(park).file_url" :href="exemptInfo(park).file_url" target="_blank" class="exempt-file">依据：{{ exemptInfo(park).file_name || '查看文件' }}</a>
                    </template>
                    <strong v-else-if="results?.[park]?.final_score != null">{{ results[park].final_score }}</strong>
                    <span v-else class="miss">未录入，不参与计算</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="formula-box">
            <div class="formula-title">园林绿化（片区 / 公园广场）计分公式</div>
            <ul class="formula-list">
              <li>系统分 =（按期结案率×100% + 超期结案率×40%）×80% +（1−延期率）×10% +（1−返工率）×10%</li>
              <li>总分 = 系统分×0.7 + 中心考核分×0.3 + 加减分项</li>
            </ul>
          </div>
        </el-tab-pane>

        <el-tab-pane label="市政公用" name="municipal">
          <div class="table-wrapper">
            <table class="data-table">
              <thead>
                <tr>
                  <th>市政考核</th><th>应结案数</th><th>结案数</th><th>结案率</th><th>超期率</th><th>延期率</th><th>返工率</th>
                  <th>加减分项</th><th>分数</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(stats, unit) in summary.municipal_units" :key="unit">
                  <td>{{ unit }}</td>
                  <td>{{ stats.total }}</td>
                  <td>{{ stats.closed }}</td>
                  <td>{{ formatRate(stats.closed, stats.total) }}</td>
                  <td>{{ formatRate(stats.overtime, stats.total) }}</td>
                  <td>{{ formatRate(stats.delayed, stats.total) }}</td>
                  <td>{{ formatRate(stats.rework, stats.total) }}</td>
                  <td>{{ displayScore(unit, 'extra', 'municipal') }}</td>
                  <td>
                    <template v-if="exemptInfo(unit)">
                      <span class="exempt-tag">不参与考核</span>
                      <div class="exempt-note">{{ exemptInfo(unit).note }}</div>
                      <a v-if="exemptInfo(unit).file_url" :href="exemptInfo(unit).file_url" target="_blank" class="exempt-file">依据：{{ exemptInfo(unit).file_name || '查看文件' }}</a>
                    </template>
                    <strong v-else-if="results?.[unit]?.final_score != null">{{ results[unit].final_score }}</strong>
                    <span v-else class="miss">未录入，不参与计算</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="formula-box">
            <div class="formula-title">市政公用计分公式</div>
            <ul class="formula-list">
              <li><strong>城市照明部、排水服务中心：</strong>系统分 =（按期结案率×100% + 超期结案率×40%）×80% +（1−延期率）×10% +（1−返工率）×10%；总分 = 系统分 + 加减分项</li>
              <li><strong>应急执法分队、市政设施维护部：</strong>得分 = 结案数 ÷ 应结案数 × 100；总分 = 得分 + 加减分项</li>
            </ul>
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>

    <div v-else-if="!loading" class="empty-state">
      <p>请选择月份查看考核数据</p>
    </div>

    <div v-if="loading" class="loading-state">
      <el-icon class="is-loading" :size="40"><Loading /></el-icon>
      <p>加载中...</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import axios from 'axios'

const API = '/api/assessment'

const months = ref([])
const selectedBatch = ref('')
const loading = ref(false)
const summary = ref(null)
const results = ref(null)
const calculating = ref(false)
const generatingReport = ref(false)
const activeTab = ref('overview')

// 人工分值（库中）
const manualScores = ref([]) // [{unit_name, unit_type, score_type, score_value}]
const garbage = ref([]) // [{region, district_name, piece_count}]
const hasManual = ref(false)
const manualHint = ref('')
const manualHintClass = ref('')

// 豁免期：unit_name → {note, file_url, file_name}
const exemptMap = ref({})

function exemptInfo(unit) {
  return exemptMap.value[unit] || null
}

const totalCount = computed(() => {
  if (!summary.value?.dept_groups) return 0
  return Object.values(summary.value.dept_groups).reduce((sum, s) => sum + Number(s.total || 0), 0)
})
const totalClosed = computed(() => {
  if (!summary.value?.dept_groups) return 0
  return Object.values(summary.value.dept_groups).reduce((sum, s) => sum + Number(s.closed || 0), 0)
})

function formatMonth(batch) {
  if (!batch || batch.length < 6) return batch || ''
  return batch.substring(0, 4) + '年' + batch.substring(4, 6) + '月'
}
function formatRate(numerator, denominator) {
  if (!denominator) return '-'
  return ((numerator / denominator) * 100).toFixed(2) + '%'
}
function formatPercent(value, total) {
  if (!total) return '-'
  return ((value / total) * 100).toFixed(2) + '%'
}

function findScore(unit, scoreType, unitType) {
  return manualScores.value.find(
    s => s.unit_name === unit && s.score_type === scoreType && (!unitType || s.unit_type === unitType)
  )
}

function displayScore(unit, scoreType, unitType) {
  const s = findScore(unit, scoreType, unitType)
  if (s == null || s === undefined) return '未录入'
  return s.score_value
}

function displayGarbage(district) {
  const g = garbage.value.find(x => x.district_name === district)
  if (!g) return '未录入'
  const score = 100 - Number(g.piece_count || 0) * 0.01
  return score.toFixed(2)
}

async function fetchMonths() {
  try {
    const res = await axios.get(`${API}/months`)
    if (res.data?.success) months.value = res.data.months
  } catch (e) {
    console.error('获取月份失败:', e)
  }
}

async function loadSummary() {
  if (!selectedBatch.value) return
  loading.value = true
  summary.value = null
  results.value = null
  manualHint.value = ''
  exemptMap.value = {}
  try {
    const [sumRes, manRes, exRes] = await Promise.all([
      axios.get(`${API}/summary`, { params: { batch: selectedBatch.value } }),
      axios.get(`${API}/manual`, { params: { batch: selectedBatch.value } }),
      axios.get(`${API}/exemptions`, { params: { batch: selectedBatch.value } }),
    ])
    if (sumRes.data?.success) summary.value = sumRes.data
    if (manRes.data?.success) {
      manualScores.value = manRes.data.scores || []
      garbage.value = manRes.data.garbage || []
      hasManual.value = manualScores.value.length > 0
      if (!hasManual.value) {
        manualHint.value = '该月人工分值尚未录入。请到「系统管理 → 考核数据录入」维护后计算；确认后仍可计算，缺分单位不计总分。'
        manualHintClass.value = 'warn'
      } else {
        manualHint.value = `已从库中读取人工分值 ${manualScores.value.length} 条。若需修改，请到「系统管理 → 考核数据录入」。`
        manualHintClass.value = 'info'
      }
    }
    if (exRes.data?.success) {
      const em = {}
      for (const it of exRes.data.exemptions || []) {
        for (const n of it.unit_names || [it.unit_name]) {
          em[n] = it
        }
      }
      exemptMap.value = em
      if (Object.keys(em).length) {
        manualHint.value = (manualHint.value ? manualHint.value + ' ' : '') +
          `本月 ${Object.keys(em).length} 个部门设置豁免期，不参与考核。`
        if (!manualHintClass.value) manualHintClass.value = 'warn'
      }
    }
  } catch (e) {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

async function calculateScores() {
  if (!selectedBatch.value) return
  try {
    if (!hasManual.value) {
      await ElMessageBox.confirm(
        '该月人工分值未录入或不完整。继续计算时：仅系统得分照常展示，缺失考核分/加减分/垃圾件数的单位不计算总分。是否继续？',
        '未录入提示',
        { type: 'warning', confirmButtonText: '继续计算', cancelButtonText: '取消' }
      )
    }
  } catch {
    return
  }

  calculating.value = true
  try {
    // 由后端从库中读人工分计算，不再传 external_data
    const res = await axios.post(`${API}/calculate`, {
      batch: selectedBatch.value,
    })
    if (res.data?.success) {
      results.value = res.data.results
      ElMessage.success('计算完成')
    } else {
      ElMessage.error(res.data?.error || '计算失败')
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '计算失败')
  } finally {
    calculating.value = false
  }
}

async function generateMonthlyReport() {
  if (!selectedBatch.value) return
  try {
    await ElMessageBox.confirm(
      '将读取当月案件数据与考核录入数据，自动计算得分并生成 Word 运行月报（同月重复生成将覆盖），是否继续？',
      '生成考核月报',
      { type: 'info', confirmButtonText: '生成', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  generatingReport.value = true
  try {
    const res = await axios.post(`${API}/report/generate`, { batch: selectedBatch.value })
    if (res.data?.success) {
      ElMessage.success('考核月报已生成')
      window.open(res.data.file_url, '_blank')
    } else {
      ElMessage.error(res.data?.error || '生成失败')
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '生成失败，请检查考核录入数据')
  } finally {
    generatingReport.value = false
  }
}

onMounted(() => {
  fetchMonths()
})
</script>

<style scoped>
.assessment-page { padding: 20px; }
.page-header {
  display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;
}
.page-header h2 { margin: 0; font-size: 20px; font-weight: 600; }
.header-actions { display: flex; gap: 12px; align-items: center; }
.manual-hint {
  margin-bottom: 12px; padding: 10px 14px; border-radius: 8px; font-size: 13px;
}
.manual-hint.warn {
  background: #fef3c7; color: #92400e; border: 1px solid #fcd34d;
}
.manual-hint.info {
  background: #eff6ff; color: #1e40af; border: 1px solid #bfdbfe;
}
.overview-section {
  background: var(--bg-card); border-radius: 8px; border: 1px solid var(--border-lighter); padding: 16px;
}
.sub-title { font-size: 15px; font-weight: 600; color: var(--text-primary); margin: 20px 0 12px; }
.table-wrapper { overflow-x: auto; margin-top: 16px; }
.data-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.data-table th, .data-table td {
  padding: 10px 12px; text-align: center; border-bottom: 1px solid var(--border-lighter);
}
.data-table th { font-weight: 600; color: var(--text-secondary); background: var(--bg-secondary, #f8fafc); }
.data-table td:first-child, .data-table th:first-child { text-align: left; }
.data-table tr:hover { background: var(--bg-secondary, #f8fafc); }
.total-row { background: var(--bg-secondary, #f8fafc); }
.total-row td { font-weight: 600; }
.miss { color: #b45309; font-size: 12px; }
.exempt-tag {
  display: inline-block; padding: 2px 8px; border-radius: 4px;
  background: #fef3c7; color: #92400e; border: 1px solid #fcd34d; font-size: 12px;
}
.exempt-note { font-size: 12px; color: var(--text-secondary, #6b7280); margin-top: 4px; }
.exempt-file { font-size: 12px; color: var(--primary-600, #2563eb); display: inline-block; margin-top: 2px; }
.formula-box {
  margin-top: 16px;
  padding: 12px 16px;
  border-radius: 8px;
  border: 1px solid var(--border-lighter, #e5e7eb);
  background: var(--bg-secondary, #f8fafc);
}
.formula-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 8px;
}
.formula-list {
  margin: 0;
  padding-left: 18px;
  font-size: 12px;
  line-height: 1.7;
  color: var(--text-secondary);
}
.formula-list li {
  margin-bottom: 2px;
}
.formula-list strong {
  color: var(--text-primary);
}
.empty-state { text-align: center; padding: 48px; color: var(--text-tertiary); }
.loading-state {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 48px; color: var(--text-secondary);
}
</style>
