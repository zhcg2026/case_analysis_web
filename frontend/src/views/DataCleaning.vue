<template>
  <div class="cleaning-page">
    <div class="cleaning-header">
      <h1>数据清洗</h1>
      <p>上传原始案件数据，执行清洗规则后入库</p>
    </div>

    <!-- 步骤条 -->
    <el-steps :active="currentStep" finish-status="success" align-center class="cleaning-steps">
      <el-step title="上传数据" description="选择原始Excel文件" />
      <el-step title="配置规则" description="选择清洗规则" />
      <el-step title="预览结果" description="查看清洗对比" />
      <el-step title="确认入库" description="写入数据库" />
    </el-steps>

    <!-- Step 1: 上传数据 -->
    <div v-if="currentStep === 0" class="step-content">
      <el-upload
        class="upload-area"
        drag
        :auto-upload="false"
        :on-change="handleFileChange"
        :file-list="fileList"
        accept=".xlsx,.xls"
        :limit="1"
      >
        <el-icon class="el-icon--upload"><upload-filled /></el-icon>
        <div class="el-upload__text">
          拖拽 Excel 文件到此处，或<em>点击选择</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">支持 .xlsx / .xls 格式，单文件最大 50MB</div>
        </template>
      </el-upload>

      <div v-if="uploadResult" class="upload-info">
        <el-alert :title="`成功读取 ${uploadResult.total_rows} 条记录`" type="success" show-icon />
        <div class="column-list">
          <span class="label">检测到的列：</span>
          <el-tag v-for="col in uploadResult.columns" :key="col" size="small" class="col-tag">{{ col }}</el-tag>
        </div>
      </div>

      <div class="step-actions">
        <el-button type="primary" @click="goToStep1" :disabled="!uploadResult">下一步：配置规则</el-button>
      </div>
    </div>

    <!-- Step 2: 配置规则 -->
    <div v-if="currentStep === 1" class="step-content">
      <div class="rules-section">
        <h3>清洗规则</h3>
        <div class="rules-list">
          <div v-for="rule in rules" :key="rule.id" class="rule-item">
            <el-checkbox v-model="rule.enabled" :label="rule.name">
              <span class="rule-name">{{ rule.name }}</span>
              <span class="rule-desc">{{ rule.description }}</span>
            </el-checkbox>
          </div>
        </div>
      </div>

      <!-- 延期/返工/超时补充 -->
      <div class="delay-rework-section">
        <h3>延期/返工/超时案件补充（可选）</h3>
        <p class="section-tip">现在没有列表可跳过，后续可在「系统管理 → 数据管理」中上传列表更新标记。</p>
        <el-upload
          class="dr-upload"
          :auto-upload="false"
          :on-change="handleDelayReworkFile"
          :file-list="drFileList"
          accept=".txt,.xlsx,.xls"
          :limit="1"
        >
          <el-button size="small" type="info">
            <el-icon><upload /></el-icon>
            上传延期/返工/超时列表
          </el-button>
          <template #tip>
            <div class="el-upload__tip">
              支持 .txt 格式（延期：案件号1、案件号2 / 返工：案件号3 / 超时：案件号4）或 .xlsx 格式
            </div>
          </template>
        </el-upload>

        <div v-if="delayReworkResult" class="dr-info">
          <el-tag type="warning">延期 {{ delayReworkResult.delayed_count }} 条</el-tag>
          <el-tag type="danger">返工 {{ delayReworkResult.rework_count }} 条</el-tag>
          <el-tag type="info">超时 {{ delayReworkResult.overtime_count || 0 }} 条</el-tag>
        </div>
      </div>

      <div class="step-actions">
        <el-button @click="currentStep = 0">上一步</el-button>
        <el-button type="primary" @click="runPreview" :loading="previewLoading">下一步：预览结果</el-button>
      </div>
    </div>

    <!-- Step 3: 预览结果 -->
    <div v-if="currentStep === 2" class="step-content">
      <div v-if="previewLoading" class="loading-state">
        <el-icon class="is-loading" :size="40"><loading /></el-icon>
        <p>正在执行清洗规则...</p>
      </div>

      <div v-else-if="previewResult" class="preview-section">
        <!-- 清洗报告 -->
        <div class="report-cards">
          <div v-for="(item, key) in previewResult.report" :key="key" class="report-card">
            <div class="card-title">{{ item.name }}</div>
            <div class="card-count">
              <span class="count-num">{{ item.changed || 0 }}</span>
              <span class="count-label">条修改</span>
            </div>
            <div v-if="item.message" class="card-msg">{{ item.message }}</div>
          </div>
        </div>

        <!-- 数据预览表格 -->
        <div class="data-preview-section">
          <div class="preview-header">
            <h3>数据预览（高亮显示变更）</h3>
            <el-button type="primary" size="small" @click="downloadCleanedData">
              <el-icon><download /></el-icon>
              下载清洗结果
            </el-button>
          </div>
          <div class="preview-table-wrapper">
            <table class="preview-table">
              <thead>
                <tr>
                  <th class="row-num">#</th>
                  <th>任务号</th>
                  <th>问题来源</th>
                  <th>问题描述</th>
                  <th>所属片区</th>
                  <th>所属社区</th>
                  <th>监督员</th>
                  <th>X坐标</th>
                  <th>Y坐标</th>
                  <th>延期</th>
                  <th>返工</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, idx) in pagedData" :key="idx"
                    :class="{ 'row-changed': isRowChanged(row, pageStart + idx) }">
                  <td class="row-num">{{ pageStart + idx + 1 }}</td>
                  <td>{{ row.task_no || '' }}</td>
                  <td :class="{ 'cell-changed': isCellChanged('source', pageStart + idx) }">
                    {{ row.source || '' }}
                    <span v-if="isCellChanged('source', pageStart + idx)" class="change-indicator">✓</span>
                  </td>
                  <td :class="{ 'cell-changed': isCellChanged('description', pageStart + idx) }" class="desc-cell">
                    {{ truncate(row.description, 30) }}
                    <span v-if="isCellChanged('description', pageStart + idx)" class="change-indicator">✓</span>
                  </td>
                  <td :class="{ 'cell-changed': isCellChanged('district', pageStart + idx) }">
                    {{ row.district || '' }}
                    <span v-if="isCellChanged('district', pageStart + idx)" class="change-indicator">✓</span>
                  </td>
                  <td :class="{ 'cell-changed': isCellChanged('community', pageStart + idx) }">
                    {{ row.community || '' }}
                    <span v-if="isCellChanged('community', pageStart + idx)" class="change-indicator">✓</span>
                  </td>
                  <td :class="{ 'cell-changed': isCellChanged('supervisor', pageStart + idx) }">
                    {{ row.supervisor || '' }}
                    <span v-if="isCellChanged('supervisor', pageStart + idx)" class="change-indicator">✓</span>
                  </td>
                  <td :class="{ 'cell-changed': isCellChanged('longitude', pageStart + idx) }">
                    {{ row.longitude || '' }}
                    <span v-if="isCellChanged('longitude', pageStart + idx)" class="change-indicator">✓</span>
                  </td>
                  <td :class="{ 'cell-changed': isCellChanged('latitude', pageStart + idx) }">
                    {{ row.latitude || '' }}
                    <span v-if="isCellChanged('latitude', pageStart + idx)" class="change-indicator">✓</span>
                  </td>
                  <td :class="{ 'cell-changed': isCellChanged('is_delayed', pageStart + idx) }">
                    {{ row.is_delayed == 1 ? '是' : '否' }}
                  </td>
                  <td :class="{ 'cell-changed': isCellChanged('is_rework', pageStart + idx) }">
                    {{ row.is_rework == 1 ? '是' : '否' }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="preview-pagination">
            <el-pagination
              v-model:current-page="currentPage"
              :page-size="pageSize"
              :total="previewResult?.cleaned_data?.length || 0"
              layout="total, prev, pager, next, jumper"
              @current-change="handlePageChange"
            />
          </div>
          <p class="preview-note">共 {{ previewResult.total_rows }} 条记录。绿色高亮表示该单元格已被清洗修改。</p>
        </div>
      </div>

      <div class="step-actions">
        <el-button @click="currentStep = 1">上一步</el-button>
        <el-button type="primary" @click="currentStep = 3">下一步：确认入库</el-button>
      </div>
    </div>

    <!-- Step 4: 确认入库 -->
    <div v-if="currentStep === 3" class="step-content">
      <div class="confirm-section">
        <el-form label-width="120px" class="confirm-form">
          <el-form-item label="上传批次">
            <el-input v-model="batchInput" placeholder="如 202607，留空自动推断" />
          </el-form-item>
          <el-form-item label="覆盖写入">
            <el-switch v-model="overwriteBatch" />
            <span class="form-tip">开启后将删除同批次旧数据</span>
          </el-form-item>
        </el-form>

        <el-alert
          :title="`将入库 ${previewResult?.total_rows || 0} 条记录`"
          type="info"
          show-icon
          :closable="false"
          class="confirm-alert"
        />
      </div>

      <div class="step-actions">
        <el-button @click="currentStep = 2">上一步</el-button>
        <el-button type="danger" @click="executeClean" :loading="executeLoading" :disabled="executeSuccess">
          {{ executeSuccess ? '入库完成' : '确认清洗并入库' }}
        </el-button>
        <el-button v-if="executeSuccess" type="success" @click="resetAll">重新清洗</el-button>
      </div>

      <div v-if="executeResult" class="execute-result">
        <el-result
          :icon="executeResult.success ? 'success' : 'error'"
          :title="executeResult.success ? '入库成功' : '入库失败'"
          :sub-title="executeResult.message || executeResult.error"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled, Upload, Loading, Download } from '@element-plus/icons-vue'
import axios from 'axios'
import * as XLSX from 'xlsx'

const API_BASE = import.meta.env.VITE_API_TARGET || ''

// 步骤控制
const currentStep = ref(0)

// Step 1: 上传
const fileList = ref([])
const uploadResult = ref(null)

// Step 2: 规则配置
const rules = ref([
  { id: 'rule1', name: '问题来源替换', description: '其他问题上报→采集员上报', enabled: true },
  { id: 'rule2', name: '问题描述清洗', description: '清除开头无关数字、序号、标点', enabled: true },
  { id: 'rule3', name: '所属片区判定', description: '根据坐标判定五大片区 + 环卫片区分配', enabled: true },
  { id: 'rule4', name: '所属社区补全', description: '根据坐标就近匹配社区', enabled: true },
  { id: 'rule5', name: '坐标转换', description: '百度墨卡托→高德坐标系', enabled: true },
  { id: 'rule6', name: '监督员规范化', description: '去除姓名周围多余修饰字符', enabled: true },
  { id: 'rule7', name: '问题描述脱敏', description: '手机号、座机号、地址脱敏', enabled: true },
  { id: 'rule8', name: '删除指定区域', description: '删除运城市绛县的记录', enabled: true },
])
const drFileList = ref([])
const delayReworkResult = ref(null)
const delayTaskNos = ref([])
const reworkTaskNos = ref([])
const overtimeTaskNos = ref([])

// Step 3: 预览
const previewLoading = ref(false)
const previewResult = ref(null)
const originalFileData = ref(null)

// 预览数据处理
const currentPage = ref(1)
const pageSize = 100

const pageStart = computed(() => (currentPage.value - 1) * pageSize)

const pagedData = computed(() => {
  if (!previewResult.value?.cleaned_data) return []
  const start = pageStart.value
  return previewResult.value.cleaned_data.slice(start, start + pageSize)
})

// 原始数据（用于对比）
const originalData = computed(() => {
  if (!previewResult.value?.original_data) return []
  return previewResult.value.original_data
})

function handlePageChange(page) {
  currentPage.value = page
}

// 检查单元格是否变更
function isCellChanged(col, idx) {
  if (!originalData.value[idx] || !previewResult.value?.cleaned_data?.[idx]) return false
  const before = String(originalData.value[idx][col] || '')
  const after = String(previewResult.value.cleaned_data[idx][col] || '')
  return before !== after && before !== 'nan' && after !== 'nan'
}

// 检查整行是否有变更
function isRowChanged(row, idx) {
  const cols = ['source', 'description', 'district', 'community', 'supervisor', 'longitude', 'latitude']
  return cols.some(col => isCellChanged(col, idx))
}

// 截断文本
function truncate(text, len) {
  if (!text) return ''
  return text.length > len ? text.slice(0, len) + '...' : text
}

// 下载清洗结果
function downloadCleanedData() {
  if (!previewResult.value?.cleaned_data) {
    ElMessage.warning('没有可下载的数据')
    return
  }

  const data = previewResult.value.cleaned_data
  const original = previewResult.value.original_data || []

  // 准备下载数据，包含清洗前后对比
  const downloadData = data.map((row, idx) => {
    const originalRow = original[idx] || {}
    return {
      '序号': idx + 1,
      '任务号': row.task_no || '',
      '处置部门_清洗后': row.department || '',
      '处置部门_原始': originalRow.department || '',
      '问题来源_清洗后': row.source || '',
      '问题来源_原始': originalRow.source || '',
      '问题描述_清洗后': row.description || '',
      '问题描述_原始': originalRow.description || '',
      '所属片区_清洗后': row.district || '',
      '所属片区_原始': originalRow.district || '',
      '所属社区_清洗后': row.community || '',
      '所属社区_原始': originalRow.community || '',
      '监督员_清洗后': row.supervisor || '',
      '监督员_原始': originalRow.supervisor || '',
      'X坐标_清洗后': row.longitude || '',
      'X坐标_原始': originalRow.longitude || '',
      'Y坐标_清洗后': row.latitude || '',
      'Y坐标_原始': originalRow.latitude || '',
      '是否延期': row.is_delayed == 1 ? '是' : '否',
      '是否返工': row.is_rework == 1 ? '是' : '否',
      '是否超时': row.is_overtime == 1 ? '是' : '否'
    }
  })

  // 创建工作簿
  const wb = XLSX.utils.book_new()
  const ws = XLSX.utils.json_to_sheet(downloadData)

  // 设置列宽
  ws['!cols'] = [
    { wch: 6 },   // 序号
    { wch: 15 },  // 任务号
    { wch: 18 },  // 处置部门_清洗后
    { wch: 18 },  // 处置部门_原始
    { wch: 15 },  // 问题来源_清洗后
    { wch: 15 },  // 问题来源_原始
    { wch: 30 },  // 问题描述_清洗后
    { wch: 30 },  // 问题描述_原始
    { wch: 10 },  // 所属片区_清洗后
    { wch: 10 },  // 所属片区_原始
    { wch: 12 },  // 所属社区_清洗后
    { wch: 12 },  // 所属社区_原始
    { wch: 10 },  // 监督员_清洗后
    { wch: 10 },  // 监督员_原始
    { wch: 15 },  // X坐标_清洗后
    { wch: 15 },  // X坐标_原始
    { wch: 15 },  // Y坐标_清洗后
    { wch: 15 },  // Y坐标_原始
    { wch: 8 },   // 是否延期
    { wch: 8 },   // 是否返工
    { wch: 8 },   // 是否超时
  ]

  XLSX.utils.book_append_sheet(wb, ws, '清洗结果')

  // 导出文件
  const now = new Date()
  const dateStr = now.toISOString().slice(0, 10).replace(/-/g, '')
  XLSX.writeFile(wb, `数据清洗结果_${dateStr}.xlsx`)

  ElMessage.success('下载成功')
}

// Step 4: 入库
const batchInput = ref('')
const overwriteBatch = ref(true)
const executeLoading = ref(false)
const executeSuccess = ref(false)
const executeResult = ref(null)

// 获取token
function getToken() {
  return localStorage.getItem('token') || ''
}

// Step 1: 文件选择
async function handleFileChange(file) {
  // 保存文件到 fileList
  fileList.value = [file]

  const formData = new FormData()
  formData.append('file', file.raw)

  try {
    const res = await axios.post(`${API_BASE}/api/cleaning/upload`, formData, {
      headers: { Authorization: `Bearer ${getToken()}` }
    })
    if (res.data.success) {
      uploadResult.value = res.data
      // 保存原始数据用于后续步骤
      originalFileData.value = res.data.preview
      ElMessage.success(`成功读取 ${res.data.total_rows} 条记录`)
    }
  } catch (err) {
    ElMessage.error(err.response?.data?.error || '上传失败')
  }
}

function goToStep1() {
  if (!uploadResult.value) {
    ElMessage.warning('请先上传文件')
    return
  }
  currentStep.value = 1
}

// Step 2: 延期/返工文件
async function handleDelayReworkFile(file) {
  const formData = new FormData()
  formData.append('file', file.raw)

  try {
    const res = await axios.post(`${API_BASE}/api/cleaning/upload-delay-rework`, formData, {
      headers: { Authorization: `Bearer ${getToken()}` }
    })
    if (res.data.success) {
      delayReworkResult.value = res.data
      delayTaskNos.value = res.data.delayed_task_nos || []
      reworkTaskNos.value = res.data.rework_task_nos || []
      overtimeTaskNos.value = res.data.overtime_task_nos || []
      const parts = []
      if (res.data.delayed_count) parts.push(`延期 ${res.data.delayed_count} 条`)
      if (res.data.rework_count) parts.push(`返工 ${res.data.rework_count} 条`)
      if (res.data.overtime_count) parts.push(`超时 ${res.data.overtime_count} 条`)
      ElMessage.success(parts.join('，') || '未匹配到记录')
    }
  } catch (err) {
    ElMessage.error(err.response?.data?.error || '解析失败')
  }
}

// Step 3: 预览
async function runPreview() {
  previewLoading.value = true
  currentStep.value = 2

  const rulesConfig = {}
  rules.value.forEach(r => { rulesConfig[r.id] = r.enabled })

  try {
    // 用FormData发送文件 + 规则配置
    const formData = new FormData()
    const file = fileList.value[0]?.raw
    if (!file) {
      throw new Error('请先上传文件')
    }
    formData.append('file', file)
    formData.append('rules_config', JSON.stringify(rulesConfig))
    formData.append('delay_task_nos', JSON.stringify(delayTaskNos.value))
    formData.append('rework_task_nos', JSON.stringify(reworkTaskNos.value))
    formData.append('overtime_task_nos', JSON.stringify(overtimeTaskNos.value))

    const res = await axios.post(`${API_BASE}/api/cleaning/preview`, formData, {
      headers: {
        Authorization: `Bearer ${getToken()}`
      }
    })

    if (res.data.success) {
      previewResult.value = res.data
      ElMessage.success(`清洗预览完成，共处理 ${res.data.total_rows} 条`)
    }
  } catch (err) {
    ElMessage.error(err.response?.data?.error || '预览失败')
    currentStep.value = 1
  } finally {
    previewLoading.value = false
  }
}

// Step 4: 入库
async function executeClean() {
  executeLoading.value = true

  try {
    // 重新上传文件并清洗入库
    const file = fileList.value[0]?.raw
    if (!file) {
      throw new Error('文件丢失，请重新上传')
    }

    const rulesConfig = {}
    rules.value.forEach(r => { rulesConfig[r.id] = r.enabled })

    // 先做预览获取清洗后数据
    const formData = new FormData()
    formData.append('file', file)
    formData.append('rules_config', JSON.stringify(rulesConfig))

    const previewRes = await axios.post(`${API_BASE}/api/cleaning/preview`, formData, {
      headers: {
        Authorization: `Bearer ${getToken()}`
      }
    })

    if (!previewRes.data.success) {
      throw new Error(previewRes.data.error || '清洗失败')
    }

    // 执行入库
    const res = await axios.post(`${API_BASE}/api/cleaning/execute`, {
      cleaned_data: previewRes.data.cleaned_data,
      batch: batchInput.value
    }, {
      headers: { Authorization: `Bearer ${getToken()}` }
    })

    if (res.data.success) {
      executeResult.value = res.data
      executeSuccess.value = true
      ElMessage.success(res.data.message)
    }
  } catch (err) {
    executeResult.value = { success: false, error: err.response?.data?.error || '入库失败' }
    ElMessage.error(err.response?.data?.error || '入库失败')
  } finally {
    executeLoading.value = false
  }
}

// 重置
function resetAll() {
  currentStep.value = 0
  fileList.value = []
  uploadResult.value = null
  drFileList.value = []
  delayReworkResult.value = null
  delayTaskNos.value = []
  reworkTaskNos.value = []
  overtimeTaskNos.value = []
  previewResult.value = null
  originalFileData.value = null
  batchInput.value = ''
  executeSuccess.value = false
  executeResult.value = null
}

onMounted(() => {
  // 页面加载时可以预加载规则列表
})
</script>

<style scoped>
.cleaning-page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}

.cleaning-header {
  text-align: center;
  margin-bottom: 32px;
}

.cleaning-header h1 {
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 8px;
}

.cleaning-header p {
  color: var(--text-secondary);
  margin: 0;
}

.cleaning-steps {
  margin-bottom: 32px;
}

.step-content {
  background: var(--bg-card);
  border-radius: 12px;
  padding: 24px;
  border: 1px solid var(--border-lighter);
}

.upload-area {
  width: 100%;
}

.upload-info {
  margin-top: 16px;
}

.column-list {
  margin-top: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.column-list .label {
  color: var(--text-secondary);
  font-size: 13px;
}

.col-tag {
  margin: 2px;
}

.rules-section, .delay-rework-section {
  margin-bottom: 24px;
}

.rules-section h3, .delay-rework-section h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 12px;
}

.rules-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.rule-item {
  padding: 12px;
  border: 1px solid var(--border-lighter);
  border-radius: 8px;
  transition: all 0.2s;
}

.rule-item:hover {
  border-color: var(--primary-200);
}

.rule-name {
  font-weight: 500;
  margin-right: 8px;
}

.rule-desc {
  color: var(--text-secondary);
  font-size: 13px;
}

.section-tip {
  font-size: 13px;
  color: var(--text-tertiary);
  margin: 0 0 12px;
}

.dr-upload {
  margin-bottom: 12px;
}

.dr-info {
  display: flex;
  gap: 8px;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px;
  color: var(--text-secondary);
}

.report-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
  margin-bottom: 24px;
}

.report-card {
  padding: 16px;
  border: 1px solid var(--border-lighter);
  border-radius: 8px;
  text-align: center;
}

.card-title {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.count-num {
  font-size: 24px;
  font-weight: 600;
  color: var(--primary-500);
}

.count-label {
  font-size: 12px;
  color: var(--text-secondary);
  margin-left: 4px;
}

.card-msg {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-top: 4px;
}

.compare-section {
  margin-top: 16px;
}

.compare-section h3 {
  font-size: 14px;
  font-weight: 600;
  margin: 0 0 12px;
}

.change-tag {
  margin: 2px;
}

.diff-before, .diff-after {
  margin: 2px 0;
  font-size: 13px;
}

.diff-key {
  color: var(--text-secondary);
}

.diff-before .diff-val {
  color: var(--danger);
  text-decoration: line-through;
}

.diff-after .diff-val {
  color: var(--success);
  font-weight: 500;
}

.confirm-section {
  max-width: 500px;
}

.confirm-form {
  margin-bottom: 16px;
}

.form-tip {
  margin-left: 12px;
  color: var(--text-secondary);
  font-size: 13px;
}

.confirm-alert {
  margin-top: 16px;
}

.step-actions {
  display: flex;
  justify-content: center;
  gap: 12px;
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid var(--border-lighter);
}

.execute-result {
  margin-top: 24px;
}

/* 数据预览表格 */
.data-preview-section {
  margin-top: 24px;
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.preview-header h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.preview-table-wrapper {
  overflow-x: auto;
  border: 1px solid var(--border-lighter);
  border-radius: 8px;
}

.preview-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.preview-table th {
  background: var(--fill-light);
  padding: 10px 12px;
  text-align: left;
  font-weight: 600;
  color: var(--text-primary);
  border-bottom: 2px solid var(--border-lighter);
  white-space: nowrap;
  position: sticky;
  top: 0;
  z-index: 1;
}

.preview-table td {
  padding: 8px 12px;
  border-bottom: 1px solid var(--border-lighter);
  color: var(--text-regular);
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.preview-table tr:hover {
  background: var(--fill-light);
}

.row-num {
  width: 40px;
  text-align: center;
  color: var(--text-secondary);
  font-size: 12px;
}

.row-changed {
  background: rgba(103, 194, 58, 0.05);
}

.cell-changed {
  background: rgba(103, 194, 58, 0.15) !important;
  color: var(--success) !important;
  font-weight: 500;
}

.change-indicator {
  color: var(--success);
  font-weight: 700;
  margin-left: 4px;
  font-size: 12px;
}

.desc-cell {
  max-width: 250px;
}

.preview-note {
  margin-top: 12px;
  color: var(--text-secondary);
  font-size: 13px;
}

.preview-pagination {
  margin-top: 16px;
  display: flex;
  justify-content: center;
}
</style>
