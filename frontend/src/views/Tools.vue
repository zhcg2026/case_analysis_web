<template>
  <div class="page-container">
    <h1 class="page-title">小工具</h1>

    <!-- 子标签导航 -->
    <div class="tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="tab"
        :class="{ active: activeTab === tab.key }"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
      </button>
    </div>

    <div class="content-card">
      <!-- 市容环卫案件分配 -->
      <div v-if="activeTab === 'huanwei'" class="tool-section">
        <h2 class="section-title">市容环卫案件分配</h2>
        <p class="section-desc">上传案件Excel文件，自动分配责任单位</p>

        <div class="upload-area" @click="$refs.huanweiFile.click()">
          <input ref="huanweiFile" type="file" accept=".xlsx,.xls" @change="handleHuanweiFile" hidden />
          <div class="upload-icon">📁</div>
          <div class="upload-text">点击或拖拽上传Excel文件</div>
        </div>

        <div v-if="huanweiLoading" class="loading-state">
          <div class="loading-spinner"></div>
          <span>处理中...</span>
        </div>

        <div v-if="huanweiResult" class="result-section">
          <div class="result-info">处理完成，共分配 {{ huanweiResult.total }} 条案件</div>
          <a :href="huanweiResult.downloadUrl" class="btn btn-primary" download>下载结果</a>
        </div>
      </div>

      <!-- 地址信息提取 -->
      <div v-else-if="activeTab === 'location'" class="tool-section">
        <h2 class="section-title">地址信息提取</h2>
        <p class="section-desc">从案件描述中提取地址信息</p>

        <div class="upload-area" @click="$refs.locationFile.click()">
          <input ref="locationFile" type="file" accept=".xlsx,.xls" @change="handleLocationFile" hidden />
          <div class="upload-icon">📍</div>
          <div class="upload-text">点击或拖拽上传Excel文件</div>
        </div>

        <div v-if="locationLoading" class="loading-state">
          <div class="loading-spinner"></div>
          <span>提取中...</span>
        </div>

        <div v-if="locationResult" class="result-section">
          <div class="result-info">提取完成</div>
          <a :href="locationResult.downloadUrl" class="btn btn-primary" download>下载结果</a>
        </div>
      </div>

      <!-- 数据清洗 -->
      <div v-else-if="activeTab === 'cleaning'" class="tool-section">
        <h2 class="section-title">数据清洗</h2>
        <p class="section-desc">清洗重复数据、格式化字段</p>

        <div class="form-row">
          <div class="form-group">
            <label class="form-label">选择数据表</label>
            <select v-model="cleaningTable" class="form-select">
              <option value="">请选择</option>
              <option v-for="table in tables" :key="table" :value="table">{{ table }}</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">清洗字段</label>
            <select v-model="cleaningField" class="form-select">
              <option value="">请选择</option>
              <option v-for="field in cleaningFields" :key="field" :value="field">{{ field }}</option>
            </select>
          </div>
        </div>

        <button class="btn btn-primary" @click="runCleaning" :disabled="cleaningLoading">
          {{ cleaningLoading ? '清洗中...' : '开始清洗' }}
        </button>

        <div v-if="cleaningResult" class="result-section">
          <pre>{{ cleaningResult }}</pre>
        </div>
      </div>

      <!-- SQL生成器 -->
      <div v-else-if="activeTab === 'sql'" class="tool-section">
        <h2 class="section-title">SQL生成器</h2>
        <p class="section-desc">使用自然语言生成SQL查询</p>

        <div class="form-group">
          <label class="form-label">选择数据表</label>
          <select v-model="sqlTable" class="form-select">
            <option value="">请选择</option>
            <option v-for="table in tables" :key="table" :value="table">{{ table }}</option>
          </select>
        </div>

        <div class="form-group">
          <label class="form-label">自然语言描述</label>
          <textarea v-model="sqlQuery" class="form-textarea" placeholder="例如：查询本月新增的所有案件" rows="3"></textarea>
        </div>

        <button class="btn btn-primary" @click="generateSQL" :disabled="sqlLoading">
          {{ sqlLoading ? '生成中...' : '生成SQL' }}
        </button>

        <div v-if="generatedSQL" class="result-section">
          <div class="sql-result">
            <code>{{ generatedSQL }}</code>
          </div>
          <button class="btn btn-secondary" @click="executeSQL">执行查询</button>
        </div>

        <div v-if="sqlResult" class="result-section">
          <table class="data-table">
            <thead>
              <tr>
                <th v-for="(col, i) in sqlResult.columns" :key="i">{{ col }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, i) in sqlResult.data" :key="i">
                <td v-for="(cell, j) in row" :key="j">{{ cell }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import axios from 'axios'

const tabs = [
  { key: 'huanwei', label: '环卫案件分配' },
  { key: 'location', label: '地址提取' },
  { key: 'cleaning', label: '数据清洗' },
  { key: 'sql', label: 'SQL生成器' }
]

const activeTab = ref('huanwei')
const tables = ref([])

// 环卫案件分配
const huanweiLoading = ref(false)
const huanweiResult = ref(null)

// 地址提取
const locationLoading = ref(false)
const locationResult = ref(null)

// 数据清洗
const cleaningTable = ref('')
const cleaningField = ref('')
const cleaningFields = ref([])
const cleaningLoading = ref(false)
const cleaningResult = ref('')

// SQL生成器
const sqlTable = ref('')
const sqlQuery = ref('')
const sqlLoading = ref(false)
const generatedSQL = ref('')
const sqlResult = ref(null)

async function fetchTables() {
  try {
    const response = await axios.get('/api/tables')
    tables.value = response.data.tables || []
  } catch (error) {
    console.error('获取表列表失败:', error)
  }
}

async function handleHuanweiFile(e) {
  const file = e.target.files[0]
  if (!file) return

  huanweiLoading.value = true
  const formData = new FormData()
  formData.append('file', file)

  try {
    const response = await axios.post('/api/tools/huanwei-assignment', formData)
    huanweiResult.value = response.data
  } catch (error) {
    console.error('处理失败:', error)
  } finally {
    huanweiLoading.value = false
  }
}

async function handleLocationFile(e) {
  const file = e.target.files[0]
  if (!file) return

  locationLoading.value = true
  const formData = new FormData()
  formData.append('file', file)

  try {
    const response = await axios.post('/api/tools/extract-location', formData)
    locationResult.value = response.data
  } catch (error) {
    console.error('处理失败:', error)
  } finally {
    locationLoading.value = false
  }
}

async function runCleaning() {
  if (!cleaningTable.value) return

  cleaningLoading.value = true
  try {
    const response = await axios.post('/api/tools/data-cleaning', {
      table: cleaningTable.value,
      field: cleaningField.value
    })
    cleaningResult.value = response.data.message || '清洗完成'
  } catch (error) {
    cleaningResult.value = '清洗失败: ' + error.message
  } finally {
    cleaningLoading.value = false
  }
}

async function generateSQL() {
  if (!sqlTable.value || !sqlQuery.value) return

  sqlLoading.value = true
  sqlResult.value = null
  try {
    const response = await axios.post('/api/tools/natural-language-query', {
      table_name: sqlTable.value,
      query: sqlQuery.value
    })
    generatedSQL.value = response.data.sql || response.data.query
  } catch (error) {
    console.error('生成失败:', error)
  } finally {
    sqlLoading.value = false
  }
}

async function executeSQL() {
  if (!generatedSQL.value) return

  try {
    const response = await axios.post('/api/tools/natural-language-query', {
      table_name: sqlTable.value,
      query: sqlQuery.value,
      execute: true
    })
    sqlResult.value = response.data.result || response.data
  } catch (error) {
    console.error('执行失败:', error)
  }
}

watch(cleaningTable, async (table) => {
  if (table) {
    try {
      const response = await axios.get(`/api/tables/${table}/columns`)
      cleaningFields.value = response.data.columns || []
    } catch (error) {
      cleaningFields.value = []
    }
  }
})

onMounted(() => {
  fetchTables()
})
</script>

<style scoped>
.page-container {
  padding: var(--space-6);
  max-width: 1400px;
  margin: 0 auto;
}

.page-title {
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 var(--space-6);
}

.tabs {
  display: flex;
  gap: var(--space-1);
  margin-bottom: var(--space-4);
  border-bottom: 1px solid var(--border-lighter);
}

.tab {
  padding: var(--space-3) var(--space-4);
  font-size: 14px;
  font-weight: 500;
  color: var(--text-tertiary);
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.tab:hover { color: var(--primary-500); }
.tab.active { color: var(--primary-500); border-bottom-color: var(--primary-500); }

.content-card {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-lighter);
  padding: var(--space-6);
}

.tool-section {
  max-width: 800px;
}

.section-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 var(--space-2);
}

.section-desc {
  color: var(--text-tertiary);
  margin: 0 0 var(--space-6);
}

.upload-area {
  border: 2px dashed var(--border-color);
  border-radius: var(--radius-lg);
  padding: var(--space-8);
  text-align: center;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.upload-area:hover {
  border-color: var(--primary-400);
  background: var(--fill-light);
}

.upload-icon {
  font-size: 48px;
  margin-bottom: var(--space-2);
}

.upload-text {
  color: var(--text-secondary);
}

.loading-state {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-top: var(--space-4);
  color: var(--text-tertiary);
}

.result-section {
  margin-top: var(--space-6);
  padding: var(--space-4);
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
}

.result-info {
  color: var(--text-primary);
  margin-bottom: var(--space-3);
}

.form-row {
  display: flex;
  gap: var(--space-4);
  margin-bottom: var(--space-4);
}

.form-group {
  flex: 1;
  margin-bottom: var(--space-4);
}

.form-label {
  display: block;
  margin-bottom: var(--space-2);
  font-weight: 500;
  color: var(--text-primary);
}

.form-select,
.form-textarea {
  width: 100%;
  padding: var(--space-2) var(--space-3);
  font-size: 14px;
  color: var(--text-primary);
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
}

.form-textarea {
  resize: vertical;
  min-height: 80px;
}

.sql-result {
  background: var(--neutral-900);
  color: var(--neutral-100);
  padding: var(--space-3);
  border-radius: var(--radius-md);
  overflow-x: auto;
  margin-bottom: var(--space-3);
}

.sql-result code {
  font-family: var(--font-mono);
  font-size: 13px;
}
</style>