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

      <!-- 延期/返工补充 -->
      <div class="delay-rework-section">
        <h3>延期/返工案件补充（可选）</h3>
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
            上传延期/返工列表
          </el-button>
          <template #tip>
            <div class="el-upload__tip">
              支持 .txt 格式（延期：案件号1、案件号2）或 .xlsx 格式
            </div>
          </template>
        </el-upload>

        <div v-if="delayReworkResult" class="dr-info">
          <el-tag type="warning">延期 {{ delayReworkResult.delayed_count }} 条</el-tag>
          <el-tag type="danger">返工 {{ delayReworkResult.rework_count }} 条</el-tag>
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

        <!-- 差异对比表 -->
        <div v-if="previewResult.compare && previewResult.compare.length > 0" class="compare-section">
          <h3>清洗前后对比（前20条变更记录）</h3>
          <el-table :data="previewResult.compare" stripe border size="small" max-height="400">
            <el-table-column prop="index" label="行号" width="60" />
            <el-table-column prop="task_no" label="任务号" width="120" />
            <el-table-column label="变更字段" width="120">
              <template #default="{ row }">
                <el-tag v-for="col in row.changes" :key="col" size="small" class="change-tag">{{ col }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="清洗前">
              <template #default="{ row }">
                <div v-for="(val, key) in row.before" :key="key" class="diff-before">
                  <span class="diff-key">{{ key }}：</span>
                  <span class="diff-val">{{ val }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="清洗后">
              <template #default="{ row }">
                <div v-for="(val, key) in row.after" :key="key" class="diff-after">
                  <span class="diff-key">{{ key }}：</span>
                  <span class="diff-val">{{ val }}</span>
                </div>
              </template>
            </el-table-column>
          </el-table>
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
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled, Upload, Loading } from '@element-plus/icons-vue'
import axios from 'axios'

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
  { id: 'rule3', name: '所属片区判定', description: '根据坐标判定五大片区（需GeoJSON）', enabled: true },
  { id: 'rule4', name: '所属社区补全', description: '根据坐标就近匹配社区', enabled: true },
  { id: 'rule5', name: '坐标转换', description: '百度墨卡托→高德坐标系', enabled: true },
  { id: 'rule6', name: '监督员规范化', description: '去除姓名周围多余修饰字符', enabled: true },
  { id: 'rule7', name: '问题描述脱敏', description: '手机号、座机号、地址脱敏', enabled: false },
])
const drFileList = ref([])
const delayReworkResult = ref(null)
const delayTaskNos = ref([])
const reworkTaskNos = ref([])

// Step 3: 预览
const previewLoading = ref(false)
const previewResult = ref(null)
const originalFileData = ref(null)

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
      ElMessage.success(`延期 ${res.data.delayed_count} 条，返工 ${res.data.rework_count} 条`)
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
    // 需要重新上传完整文件数据
    const formData = new FormData()
    const file = fileList.value[0]?.raw
    if (file) {
      formData.append('file', file)
    }

    // 先获取完整数据
    const uploadRes = await axios.post(`${API_BASE}/api/cleaning/upload`, formData, {
      headers: { Authorization: `Bearer ${getToken()}` }
    })

    if (!uploadRes.data.success) {
      throw new Error('文件上传失败')
    }

    // 用完整数据做预览
    const res = await axios.post(`${API_BASE}/api/cleaning/preview`, {
      file_data: uploadRes.data.preview, // 前10行预览
      rules_config: rulesConfig,
      delay_task_nos: delayTaskNos.value,
      rework_task_nos: reworkTaskNos.value
    }, {
      headers: { Authorization: `Bearer ${getToken()}` }
    })

    if (res.data.success) {
      previewResult.value = res.data
      ElMessage.success('清洗预览完成')
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
    // 重新上传完整文件并清洗入库
    const file = fileList.value[0]?.raw
    if (!file) {
      throw new Error('文件丢失，请重新上传')
    }

    const formData = new FormData()
    formData.append('file', file)

    // 获取完整清洗数据
    const uploadRes = await axios.post(`${API_BASE}/api/cleaning/upload`, formData, {
      headers: { Authorization: `Bearer ${getToken()}` }
    })

    const rulesConfig = {}
    rules.value.forEach(r => { rulesConfig[r.id] = r.enabled })

    const previewRes = await axios.post(`${API_BASE}/api/cleaning/preview`, {
      file_data: uploadRes.data.preview,
      rules_config: rulesConfig,
      delay_task_nos: delayTaskNos.value,
      rework_task_nos: reworkTaskNos.value
    }, {
      headers: { Authorization: `Bearer ${getToken()}` }
    })

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
</style>
