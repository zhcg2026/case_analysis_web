<template>
  <div class="special-matters-page">
    <div class="page-header">
      <div>
        <h2>特殊事项归属</h2>
        <p class="page-sub">大小类标准之外的特例清单（移交历史等原因「谁实际管」）</p>
      </div>
      <el-button v-if="userStore.isAdmin" type="primary" @click="openEditor()">
        <el-icon><Plus /></el-icon> 添加
      </el-button>
    </div>

    <el-card shadow="never" class="list-card">
      <div v-loading="loading">
        <div v-for="m in matters" :key="m.id" class="matter-item">
          <div class="matter-line1">
            <span class="matter-name">{{ m.matter }}</span>
            <span class="matter-arrow">→</span>
            <el-tag size="small">{{ m.dept }}</el-tag>
          </div>
          <div class="matter-line2" v-if="m.contact || m.phone">
            <span v-if="m.contact" class="meta">{{ m.contact }}</span>
            <a v-if="m.phone" :href="'tel:' + m.phone" class="meta phone">{{ m.phone }}</a>
          </div>
          <div v-if="m.note" class="matter-note">{{ m.note }}</div>
          <div v-if="userStore.isAdmin" class="matter-ops">
            <el-button type="primary" link size="small" @click="openEditor(m)">编辑</el-button>
            <el-popconfirm title="确定删除该特殊事项？" @confirm="remove(m)">
              <template #reference>
                <el-button type="danger" link size="small">删除</el-button>
              </template>
            </el-popconfirm>
          </div>
        </div>
        <el-empty v-if="!loading && !matters.length" description="暂无特殊事项" :image-size="80" />
      </div>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="(form.id ? '编辑' : '添加') + '特殊事项'" width="520px">
      <el-form :model="form" label-width="90px">
        <el-form-item label="事项/路段" required>
          <el-input v-model="form.matter" placeholder="如：圣惠南路 / 南城墙路立面改造" />
        </el-form-item>
        <el-form-item label="处置部门" required>
          <el-input v-model="form.dept" placeholder="如：市政工程部" />
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="联系人">
              <el-input v-model="form.contact" placeholder="可选" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="联系电话">
              <el-input v-model="form.phone" placeholder="可选" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="备注">
          <el-input v-model="form.note" type="textarea" :rows="2" placeholder="如：未移交，暂由市政工程部负责（可选）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import axios from 'axios'
import { useUserStore } from '../stores/user'

const userStore = useUserStore()
const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const matters = ref([])
const form = ref({ id: null, matter: '', dept: '', contact: '', phone: '', note: '' })

async function load() {
  loading.value = true
  try {
    const { data } = await axios.get('/api/special-matters')
    matters.value = data.matters || []
  } catch {
    // error toast via interceptor
  } finally {
    loading.value = false
  }
}

function openEditor(m = null) {
  form.value = m
    ? { id: m.id, matter: m.matter, dept: m.dept, contact: m.contact || '', phone: m.phone || '', note: m.note || '' }
    : { id: null, matter: '', dept: '', contact: '', phone: '', note: '' }
  dialogVisible.value = true
}

async function save() {
  if (!form.value.matter.trim()) {
    ElMessage.warning('请填写事项/路段')
    return
  }
  if (!form.value.dept.trim()) {
    ElMessage.warning('请填写处置部门')
    return
  }
  saving.value = true
  try {
    if (form.value.id) {
      await axios.put(`/api/special-matters/${form.value.id}`, form.value)
    } else {
      await axios.post('/api/special-matters', form.value)
    }
    ElMessage.success('保存成功')
    dialogVisible.value = false
    await load()
  } catch {
    // error toast via interceptor
  } finally {
    saving.value = false
  }
}

async function remove(m) {
  try {
    await axios.delete(`/api/special-matters/${m.id}`)
    ElMessage.success('删除成功')
    await load()
  } catch {
    // error toast via interceptor
  }
}

onMounted(load)
</script>

<style scoped>
.special-matters-page {
  padding: var(--space-5);
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: var(--space-4);
  gap: var(--space-3);
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
}

.list-card {
  border: 1px solid var(--border-lighter);
}

.matter-item {
  border: 1px solid var(--border-lighter);
  border-radius: var(--radius-md);
  padding: 12px 14px;
  margin-bottom: 10px;
  background: var(--bg-secondary, var(--fill-lighter));
}

.matter-line1 {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.matter-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.matter-arrow {
  color: var(--text-tertiary);
}

.matter-line2 {
  margin-top: 6px;
  display: flex;
  gap: 12px;
  font-size: 13px;
}

.meta {
  color: var(--text-secondary);
}

.phone {
  color: var(--primary-500);
  text-decoration: none;
}

.matter-note {
  margin-top: 6px;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
  white-space: pre-wrap;
}

.matter-ops {
  margin-top: 8px;
  display: flex;
  gap: 4px;
}
</style>
