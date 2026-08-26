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
      </div>
    </div>

    <!-- 统计概览 -->
    <div v-if="summary" class="overview-section">
      <el-tabs v-model="activeTab">
        <!-- 处置情况 -->
        <el-tab-pane label="处置情况" name="overview">
          <div class="table-wrapper">
            <table class="data-table">
              <thead>
                <tr>
                  <th>处置部门</th>
                  <th>应结案数</th>
                  <th>结案数</th>
                  <th>结案率</th>
                  <th>占比</th>
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

        <!-- 市容秩序（执法队） -->
        <el-tab-pane label="市容秩序" name="dispatch">
          <div class="table-wrapper">
            <table class="data-table">
              <thead>
                <tr>
                  <th>执法分队</th>
                  <th>应结案数</th>
                  <th>结案数</th>
                  <th>超期率</th>
                  <th>延期率</th>
                  <th>返工率</th>
                  <th>系统分数</th>
                  <th>队考核分</th>
                  <th>街道办分</th>
                  <th>加减分项</th>
                  <th v-if="results">总分</th>
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
                  <td><el-input-number v-model="externalData[`dispatch_${team}_team_score`]" :min="0" :max="100" :step="0.1" size="small" style="width:80px" /></td>
                  <td><el-input-number v-model="externalData[`dispatch_${team}_street_score`]" :min="0" :max="100" :step="0.1" size="small" style="width:80px" /></td>
                  <td><el-input-number v-model="externalData[`dispatch_${team}_extra`]" :min="-10" :max="10" :step="0.1" size="small" style="width:80px" /></td>
                  <td v-if="results"><strong>{{ results[team]?.final_score ?? '-' }}</strong></td>
                </tr>
              </tbody>
            </table>
          </div>
        </el-tab-pane>

        <!-- 环境卫生 -->
        <el-tab-pane label="环境卫生" name="sanitation">
          <div class="table-wrapper">
            <table class="data-table">
              <thead>
                <tr>
                  <th>环卫片区</th>
                  <th>应结案数</th>
                  <th>结案数</th>
                  <th>超期率</th>
                  <th>延期率</th>
                  <th>返工率</th>
                  <th>系统分数</th>
                  <th>单体垃圾数</th>
                  <th>中心考核分</th>
                  <th>加减分项</th>
                  <th v-if="results">总分</th>
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
                  <td><el-input-number v-model="externalData[`san_${district}_garbage`]" :min="0" :step="1" size="small" style="width:80px" /></td>
                  <td><el-input-number v-model="externalData[`san_${district}_center`]" :min="0" :max="100" :step="0.1" size="small" style="width:80px" /></td>
                  <td><el-input-number v-model="externalData[`san_${district}_extra`]" :min="-10" :max="10" :step="0.1" size="small" style="width:80px" /></td>
                  <td v-if="results"><strong>{{ results[district]?.final_score ?? '-' }}</strong></td>
                </tr>
              </tbody>
            </table>
          </div>
        </el-tab-pane>

        <!-- 园林绿化 -->
        <el-tab-pane label="园林绿化" name="garden">
          <h4 class="sub-title">园林片区</h4>
          <div class="table-wrapper">
            <table class="data-table">
              <thead>
                <tr>
                  <th>园林片区</th>
                  <th>应结案数</th>
                  <th>结案数</th>
                  <th>超期率</th>
                  <th>延期率</th>
                  <th>返工率</th>
                  <th>系统分数</th>
                  <th>中心考核分</th>
                  <th>加减分项</th>
                  <th v-if="results">总分</th>
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
                  <td><el-input-number v-model="externalData[`garden_${district}_center`]" :min="0" :max="100" :step="0.1" size="small" style="width:80px" /></td>
                  <td><el-input-number v-model="externalData[`garden_${district}_extra`]" :min="-10" :max="10" :step="0.1" size="small" style="width:80px" /></td>
                  <td v-if="results"><strong>{{ results[district]?.final_score ?? '-' }}</strong></td>
                </tr>
              </tbody>
            </table>
          </div>

          <h4 class="sub-title">公园广场</h4>
          <div class="table-wrapper">
            <table class="data-table">
              <thead>
                <tr>
                  <th>公园广场</th>
                  <th>应结案数</th>
                  <th>结案数</th>
                  <th>超期率</th>
                  <th>延期率</th>
                  <th>返工率</th>
                  <th>系统分数</th>
                  <th>中心考核分</th>
                  <th>加减分项</th>
                  <th v-if="results">总分</th>
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
                  <td><el-input-number v-model="externalData[`garden_${park}_center`]" :min="0" :max="100" :step="0.1" size="small" style="width:80px" /></td>
                  <td><el-input-number v-model="externalData[`garden_${park}_extra`]" :min="-10" :max="10" :step="0.1" size="small" style="width:80px" /></td>
                  <td v-if="results"><strong>{{ results[park]?.final_score ?? '-' }}</strong></td>
                </tr>
              </tbody>
            </table>
          </div>
        </el-tab-pane>

        <!-- 市政公用 -->
        <el-tab-pane label="市政公用" name="municipal">
          <div class="table-wrapper">
            <table class="data-table">
              <thead>
                <tr>
                  <th>市政考核</th>
                  <th>应结案数</th>
                  <th>结案数</th>
                  <th>结案率</th>
                  <th>超期率</th>
                  <th>延期率</th>
                  <th>返工率</th>
                  <th>加减分项</th>
                  <th v-if="results">分数</th>
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
                  <td><el-input-number v-model="externalData[`muni_${unit}_extra`]" :min="-10" :max="10" :step="0.1" size="small" style="width:80px" /></td>
                  <td v-if="results"><strong>{{ results[unit]?.final_score ?? '-' }}</strong></td>
                </tr>
              </tbody>
            </table>
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>

    <!-- 空状态 -->
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
import { ElMessage } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import axios from 'axios'

const API = '/api/assessment'

// 月份
const months = ref([])
const selectedBatch = ref('')
const loading = ref(false)

// 统计数据
const summary = ref(null)
const results = ref(null)
const calculating = ref(false)
const activeTab = ref('overview')

// 外部数据
const externalData = ref({
  dispatch_team_score: 100,
  dispatch_street_score: 100,
  dispatch_extra: 0,
  san_garbage_count: 0,
  san_center_score: 100,
  san_extra: 0,
  garden_center_score: 100,
  garden_extra: 0,
  muni_extra: 0
})

// 计算属性
const totalCount = computed(() => {
  if (!summary.value?.dept_groups) return 0
  return Object.values(summary.value.dept_groups).reduce((sum, s) => sum + Number(s.total || 0), 0)
})

const totalClosed = computed(() => {
  if (!summary.value?.dept_groups) return 0
  return Object.values(summary.value.dept_groups).reduce((sum, s) => sum + Number(s.closed || 0), 0)
})

// 格式化月份
function formatMonth(batch) {
  if (!batch || batch.length < 6) return batch || ''
  return batch.substring(0, 4) + '年' + batch.substring(4, 6) + '月'
}

// 格式化比率
function formatRate(numerator, denominator) {
  if (!denominator) return '-'
  return ((numerator / denominator) * 100).toFixed(2) + '%'
}

// 格式化百分比
function formatPercent(value, total) {
  if (!total) return '-'
  return ((value / total) * 100).toFixed(2) + '%'
}

// 获取月份列表
async function fetchMonths() {
  try {
    const res = await axios.get(`${API}/months`)
    if (res.data?.success) {
      months.value = res.data.months
    }
  } catch (e) {
    console.error('获取月份失败:', e)
  }
}

// 加载统计数据
async function loadSummary() {
  if (!selectedBatch.value) return

  loading.value = true
  summary.value = null
  results.value = null

  try {
    const res = await axios.get(`${API}/summary`, {
      params: { batch: selectedBatch.value }
    })
    if (res.data?.success) {
      summary.value = res.data
      // 初始化外部数据
      initExternalData(res.data)
    }
  } catch (e) {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

// 初始化外部数据
function initExternalData(data) {
  const newData = {}

  // 执法分队
  if (data.dispatch_teams) {
    Object.keys(data.dispatch_teams).forEach(team => {
      newData[`dispatch_${team}_team_score`] = 100
      newData[`dispatch_${team}_street_score`] = 100
      newData[`dispatch_${team}_extra`] = 0
    })
  }

  // 环卫片区
  if (data.sanitation_districts) {
    Object.keys(data.sanitation_districts).forEach(district => {
      newData[`san_${district}_garbage`] = 0
      newData[`san_${district}_center`] = 100
      newData[`san_${district}_extra`] = 0
    })
  }

  // 园林片区
  if (data.garden_districts) {
    Object.keys(data.garden_districts).forEach(district => {
      newData[`garden_${district}_center`] = 100
      newData[`garden_${district}_extra`] = 0
    })
  }

  // 公园广场
  if (data.parks) {
    Object.keys(data.parks).forEach(park => {
      newData[`garden_${park}_center`] = 100
      newData[`garden_${park}_extra`] = 0
    })
  }

  // 市政公用
  if (data.municipal_units) {
    Object.keys(data.municipal_units).forEach(unit => {
      newData[`muni_${unit}_extra`] = 0
    })
  }

  externalData.value = newData
}

// 计算得分
async function calculateScores() {
  if (!selectedBatch.value) return

  calculating.value = true

  try {
    const res = await axios.post(`${API}/calculate`, {
      batch: selectedBatch.value,
      external_data: externalData.value
    })
    if (res.data?.success) {
      results.value = res.data.results
      ElMessage.success('计算完成')
    }
  } catch (e) {
    ElMessage.error('计算失败')
  } finally {
    calculating.value = false
  }
}

onMounted(() => {
  fetchMonths()
})
</script>

<style scoped>
.assessment-page {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.header-actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

.overview-section {
  background: var(--bg-card);
  border-radius: 8px;
  border: 1px solid var(--border-lighter);
  padding: 16px;
}

.sub-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 20px 0 12px;
}

.table-wrapper {
  overflow-x: auto;
  margin-top: 16px;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.data-table th,
.data-table td {
  padding: 10px 12px;
  text-align: center;
  border-bottom: 1px solid var(--border-lighter);
}

.data-table th {
  font-weight: 600;
  color: var(--text-secondary);
  background: var(--bg-secondary, #f8fafc);
}

.data-table td:first-child,
.data-table th:first-child {
  text-align: left;
}

.data-table tr:hover {
  background: var(--bg-secondary, #f8fafc);
}

.total-row {
  background: var(--bg-secondary, #f8fafc);
}

.total-row td {
  font-weight: 600;
}

.external-form {
  background: var(--bg-secondary, #f8fafc);
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
}

.external-form h4 {
  margin: 0 0 12px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.form-row {
  display: flex;
  gap: 24px;
  flex-wrap: wrap;
}

.form-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.form-item label {
  font-size: 13px;
  color: var(--text-secondary);
  white-space: nowrap;
}

.empty-state {
  text-align: center;
  padding: 48px;
  color: var(--text-tertiary);
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px;
  color: var(--text-secondary);
}
</style>
