<template>
  <div class="duty-schedule-page">
    <div class="page-header">
      <h2>排班管理</h2>
      <el-button v-if="entries.length" type="danger" plain @click="clearAll">清空全部</el-button>
    </div>

    <el-alert
      type="info"
      :closable="false"
      show-icon
      class="schedule-hint"
      title="一行一天的格式：日期 白班：张三、李四、王五，夜班：赵六（人员分隔可用顿号/逗号/空格）。支持 9月13日、2026-09-13 等日期写法；日期后可用括号加备注，如「10月1日（国庆节） 白班：张三」。保存后首页欢迎区将显示今日值班；值班记录填人时可按排班带出。"
    />

    <el-card shadow="never" class="editor-card">
      <el-input
        v-model="text"
        type="textarea"
        :rows="6"
        placeholder="9月13日 白班：张三、李四、王五，夜班：赵六&#10;9月14日 白班：王五，夜班：张三"
      />
      <div class="editor-actions">
        <el-button plain @click="fileInput?.click()">导入 txt 文件</el-button>
        <input ref="fileInput" type="file" accept=".txt,.csv" hidden @change="handleFile" />
        <el-checkbox v-model="appendMode">追加模式（保留现有排班）</el-checkbox>
        <el-button type="primary" :loading="busy" :disabled="!text.trim()" @click="preview">
          {{ busy ? '解析中…' : '解析预览' }}
        </el-button>
      </div>
    </el-card>

    <el-card v-if="previewData" shadow="never" class="preview-card">
      <div class="preview-header">
        <h3>
          解析结果：{{ previewData.days }} 天 / {{ previewData.total }} 条排班
          <span v-if="previewData.errors.length" class="error-count">（{{ previewData.errors.length }} 行未识别）</span>
        </h3>
        <div class="preview-actions">
          <el-button type="primary" :loading="saving" @click="save">
            {{ saving ? '保存中…' : (appendMode ? '追加保存' : '保存（替换现有值班表）') }}
          </el-button>
          <el-button @click="previewData = null">取消</el-button>
        </div>
      </div>
      <el-table :data="previewData.entries" border stripe size="small">
        <el-table-column prop="date" label="日期" width="120" />
        <el-table-column label="班次" width="90" align="center">
          <template #default="{ row }">
            <el-tag size="small">{{ row.shift }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="人员" min-width="160">
          <template #default="{ row }">{{ row.members.join('、') }}</template>
        </el-table-column>
        <el-table-column label="备注" min-width="120">
          <template #default="{ row }">{{ row.note || '—' }}</template>
        </el-table-column>
      </el-table>
      <ul v-if="previewData.errors.length" class="preview-errors">
        <li v-for="(err, i) in previewData.errors" :key="i">{{ err }}</li>
      </ul>
    </el-card>

    <el-card shadow="never" class="list-card">
      <div class="list-header">
        <h3>当前值班表</h3>
        <span class="list-count">{{ entries.length }} 条</span>
      </div>
      <el-table :data="entries" border stripe v-loading="loading">
        <el-table-column prop="date" label="日期" width="120" />
        <el-table-column label="班次" width="90" align="center">
          <template #default="{ row }">
            <el-tag size="small">{{ row.shift }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="人员" min-width="160">
          <template #default="{ row }">{{ row.members.join('、') }}</template>
        </el-table-column>
        <el-table-column label="备注" min-width="120">
          <template #default="{ row }">{{ row.note || '—' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="90" align="center">
          <template #default="{ row }">
            <el-popconfirm title="确定删除该条排班？" @confirm="removeEntry(row)">
              <template #reference>
                <el-button type="danger" link size="small">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
        <template #empty>
          <span>暂无排班，请在上方粘贴或导入值班表</span>
        </template>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'

const text = ref('')
const appendMode = ref(false)
const busy = ref(false)
const saving = ref(false)
const loading = ref(false)
const previewData = ref(null)
const entries = ref([])
const fileInput = ref(null)

async function fetchList() {
  loading.value = true
  try {
    const { data } = await axios.get('/api/duty/schedule')
    entries.value = data.entries || []
  } catch (e) {
    ElMessage.error('获取值班表失败')
  } finally {
    loading.value = false
  }
}

function handleFile(ev) {
  const file = ev.target.files && ev.target.files[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = () => { text.value = String(reader.result || '') }
  reader.readAsText(file, 'utf-8')
  ev.target.value = ''
}

async function preview() {
  busy.value = true
  try {
    const { data } = await axios.post('/api/duty/preview', { text: text.value })
    previewData.value = data
  } catch (e) {
    ElMessage.error('解析失败: ' + (e.response?.data?.error || e.message))
  } finally {
    busy.value = false
  }
}

async function save() {
  saving.value = true
  try {
    await axios.post('/api/duty/upload', {
      text: text.value,
      mode: appendMode.value ? 'append' : 'replace'
    })
    previewData.value = null
    text.value = ''
    ElMessage.success('保存成功')
    await fetchList()
  } catch (e) {
    ElMessage.error('保存失败: ' + (e.response?.data?.error || e.message))
  } finally {
    saving.value = false
  }
}

async function removeEntry(entry) {
  try {
    await axios.delete(`/api/duty/schedule/${entry.id}`)
    ElMessage.success('已删除')
    await fetchList()
  } catch (e) {
    ElMessage.error('删除失败: ' + (e.response?.data?.error || e.message))
  }
}

async function clearAll() {
  try {
    await axios.delete('/api/duty/schedule')
    ElMessage.success('已清空')
    await fetchList()
  } catch (e) {
    ElMessage.error('清空失败: ' + (e.response?.data?.error || e.message))
  }
}

onMounted(fetchList)
</script>

<style scoped>
.duty-schedule-page {
  padding: var(--space-5);
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-4);
}

.page-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
}

.schedule-hint {
  margin-bottom: var(--space-4);
}

.editor-card,
.preview-card,
.list-card {
  margin-bottom: var(--space-4);
}

.editor-actions {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-top: var(--space-3);
  flex-wrap: wrap;
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
  flex-wrap: wrap;
}

.preview-header h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.error-count {
  color: var(--danger);
  font-weight: 600;
}

.preview-actions {
  display: flex;
  gap: var(--space-3);
}

.preview-errors {
  margin: var(--space-3) 0 0;
  padding-left: 20px;
  font-size: 13px;
  color: var(--danger);
}

.list-header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}

.list-header h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.list-count {
  font-size: 12px;
  color: var(--text-tertiary);
}
</style>
