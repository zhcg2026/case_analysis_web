<template>
  <div class="exemption-settings-page">
    <div class="page-header">
      <div>
        <h2>豁免期设置</h2>
        <p class="page-sub">
          设置后，豁免期覆盖到的考核月份内，该部门整月不参与考核计算，考核计分页将显示备注及文件依据。全局生效，不随考核月份变化。
        </p>
      </div>
    </div>

    <el-card shadow="never" class="table-card">
      <div v-loading="loading">
        <el-table :data="exemptions" border stripe size="small">
          <el-table-column label="部门" min-width="140">
            <template #default="{ row }">
              <el-select v-model="row.unit_name" filterable allow-create default-first-option placeholder="选择或输入部门" style="width: 100%">
                <el-option v-for="u in unitOptions" :key="u" :label="u" :value="u" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="开始日期" width="150">
            <template #default="{ row }">
              <el-date-picker v-model="row.start_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </template>
          </el-table-column>
          <el-table-column label="截止日期" width="150">
            <template #default="{ row }">
              <el-date-picker v-model="row.end_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </template>
          </el-table-column>
          <el-table-column label="原因" min-width="140">
            <template #default="{ row }">
              <el-input v-model="row.reason" placeholder="不参与考核原因" />
            </template>
          </el-table-column>
          <el-table-column label="文件依据" min-width="140">
            <template #default="{ row, $index }">
              <template v-if="row.file_url">
                <a :href="row.file_url" target="_blank" class="file-link">{{ row.file_name || '查看文件' }}</a>
                <el-button type="danger" link size="small" @click="clearFile(row)">删除</el-button>
              </template>
              <el-button v-else type="primary" link size="small" :loading="uploadIndex === $index" @click="pickFile($index)">
                {{ uploadIndex === $index ? '上传中…' : '上传依据' }}
              </el-button>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="80" align="center">
            <template #default="{ $index }">
              <el-button type="danger" link size="small" @click="exemptions.splice($index, 1)">删除</el-button>
            </template>
          </el-table-column>
          <template #empty>
            <span>暂无豁免设置，点击下方「添加豁免」</span>
          </template>
        </el-table>

        <div class="actions">
          <el-button @click="add">＋ 添加豁免</el-button>
          <el-button type="primary" :loading="saving" @click="save">保存豁免设置</el-button>
        </div>
      </div>
    </el-card>

    <input ref="fileInput" type="file" style="display:none" @change="onFileChosen" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'

const loading = ref(false)
const saving = ref(false)
const exemptions = ref([])
const unitOptions = ref([])
const uploadIndex = ref(-1)
const fileInput = ref(null)

async function load() {
  loading.value = true
  try {
    const [exRes, unitRes] = await Promise.all([
      axios.get('/api/assessment/exemptions'),
      axios.get('/api/assessment/units').catch(() => null),
    ])
    if (exRes.data?.success) {
      exemptions.value = (exRes.data.exemptions || []).map(x => ({
        unit_name: x.unit_name || '',
        start_date: String(x.start_date || '').slice(0, 10),
        end_date: String(x.end_date || '').slice(0, 10),
        reason: x.reason || '',
        file_url: x.file_url || '',
        file_name: x.file_name || '',
      }))
    }
    if (unitRes?.data?.success) {
      unitOptions.value = (unitRes.data.units || []).map(u => u.unit_name || u)
    }
  } catch (e) {
    ElMessage.error('加载豁免设置失败')
  } finally {
    loading.value = false
  }
}

function add() {
  exemptions.value.push({ unit_name: '', start_date: '', end_date: '', reason: '', file_url: '', file_name: '' })
}

function clearFile(it) {
  it.file_url = ''
  it.file_name = ''
}

function pickFile(i) {
  uploadIndex.value = i
  if (fileInput.value) {
    fileInput.value.value = ''
    fileInput.value.click()
  }
}

async function onFileChosen(e) {
  const i = uploadIndex.value
  const file = e.target.files && e.target.files[0]
  if (i < 0 || i >= exemptions.value.length || !file) return
  const row = exemptions.value[i]
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
    uploadIndex.value = -1
  }
}

async function save() {
  const items = []
  for (const it of exemptions.value) {
    if (!it.unit_name && !it.start_date && !it.end_date && !it.reason && !it.file_url) continue
    if (!it.unit_name) {
      ElMessage.error('存在未填写部门的豁免行')
      return
    }
    if (!it.start_date || !it.end_date) {
      ElMessage.error(`请补全「${it.unit_name}」的起止日期`)
      return
    }
    if (it.end_date < it.start_date) {
      ElMessage.error(`「${it.unit_name}」的截止日期不能早于开始日期`)
      return
    }
    items.push({
      unit_name: it.unit_name,
      start_date: it.start_date,
      end_date: it.end_date,
      reason: it.reason,
      file_url: it.file_url,
      file_name: it.file_name,
    })
  }
  saving.value = true
  try {
    const res = await axios.post('/api/assessment/exemptions', { items })
    if (res.data?.success) {
      ElMessage.success(`豁免设置已保存（${res.data.saved || items.length} 条）`)
      await load()
    } else {
      ElMessage.error(res.data?.error || '保存失败')
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.exemption-settings-page {
  padding: var(--space-5);
}

.page-header {
  margin-bottom: var(--space-4);
}

.page-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
}

.page-sub {
  margin: 6px 0 0;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
}

.table-card {
  border: 1px solid var(--border-lighter);
}

.actions {
  display: flex;
  justify-content: space-between;
  margin-top: var(--space-4);
}

.file-link {
  font-size: 12px;
  color: var(--primary-500);
  margin-right: 6px;
  word-break: break-all;
}
</style>
