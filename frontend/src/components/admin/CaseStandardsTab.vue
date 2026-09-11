<template>
  <div class="cs-tab">
    <div class="cs-toolbar">
      <div class="domain-tabs">
        <button
          v-for="d in domainOptions"
          :key="d.value"
          class="domain-tab"
          :class="{ active: domain === d.value }"
          @click="onDomainChange(d.value)"
        >{{ d.label }}</button>
      </div>
      <div class="search-box">
        <input
          v-model="keyword"
          type="text"
          placeholder="搜索小类名称…"
          class="search-input"
          @keyup.enter="loadSubcategories"
        />
        <button class="btn btn-secondary" @click="loadSubcategories">搜索</button>
      </div>
      <span class="stat-hint" v-if="subcategories.length">小类 {{ subcategories.length }} 条</span>
    </div>

    <div class="cs-body">
      <!-- 左：大类 + 小类 -->
      <div class="cs-list-panel">
        <div v-if="loadingList" class="empty-tip">加载中…</div>
        <div v-else-if="!grouped.length" class="empty-tip">无数据</div>
        <div v-for="group in grouped" :key="group.cat_name" class="cat-group">
          <div class="cat-title">
            <span class="cat-name">{{ group.cat_name }}</span>
            <span class="cat-domain">{{ domainLabel(group.domain) }}</span>
            <span class="cat-count">{{ group.items.length }}</span>
          </div>
          <ul class="sub-list">
            <li
              v-for="item in group.items"
              :key="item.id"
              class="sub-item"
              :class="{ active: selected?.id === item.id }"
              @click="selectSub(item)"
            >
              <span class="sub-code" v-if="item.sub_code">{{ item.sub_code }}</span>
              <span class="sub-name">{{ item.sub_name }}</span>
            </li>
          </ul>
        </div>
      </div>

      <!-- 右：标准明细 -->
      <div class="cs-detail-panel">
        <div v-if="!selected" class="empty-tip">点击左侧小类查看立结案标准</div>
        <div v-else>
          <div class="detail-header">
            <h3>{{ selected.sub_name }}</h3>
            <p class="meta">
              {{ selected.cat_name }} · {{ domainLabel(selected.domain) }}
              <template v-if="selected.sub_code"> · 代码 {{ selected.sub_code }}</template>
            </p>
          </div>

          <div v-if="loadingDetail" class="empty-tip">加载标准…</div>
          <template v-else>
            <!-- 小类级：监管/责任/采集要求 只显示一次 -->
            <div class="subject-card">
              <div class="subject-title">小类主体信息</div>
              <dl class="std-fields">
                <div v-if="subMeta?.regulator">
                  <dt>监管主体</dt>
                  <dd>{{ subMeta.regulator }}</dd>
                </div>
                <div v-if="subMeta?.responsible">
                  <dt>责任主体</dt>
                  <dd>{{ subMeta.responsible }}</dd>
                </div>
                <div v-if="subMeta?.collect_note">
                  <dt>采集要求</dt>
                  <dd>{{ subMeta.collect_note }}</dd>
                </div>
                <div v-if="!subMeta?.regulator && !subMeta?.responsible && !subMeta?.collect_note" class="empty-inline">
                  该小类未填写监管/责任主体
                </div>
              </dl>
            </div>

            <div class="conditions-title">立案条件（{{ standards.length }}）</div>
            <div v-if="!standards.length" class="empty-tip">该小类暂无条件明细</div>
            <div v-for="(st, idx) in standards" :key="st.id" class="std-card">
              <div class="std-card-title">
                <span class="badge">条件 {{ st.condition_order || idx + 1 }}</span>
                <span class="limit" v-if="st.time_limit_text">时限：{{ st.time_limit_text }}</span>
                <span class="limit-hours" v-if="st.time_limit_hours != null">≈{{ st.time_limit_hours }}h</span>
              </div>
              <dl class="std-fields">
                <div v-if="st.case_condition">
                  <dt>立案条件</dt>
                  <dd>{{ st.case_condition }}</dd>
                </div>
                <div v-if="st.close_condition">
                  <dt>结案条件</dt>
                  <dd>{{ st.close_condition }}</dd>
                </div>
              </dl>
            </div>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'

const domainOptions = [
  { value: '', label: '全部' },
  { value: 'part', label: '部件' },
  { value: 'event', label: '事件' },
  { value: 'service', label: '服务事项' },
]

const domain = ref('')
const keyword = ref('')
const subcategories = ref([])
const selected = ref(null)
const standards = ref([])
const subMeta = ref(null)
const loadingList = ref(false)
const loadingDetail = ref(false)

const grouped = computed(() => {
  const map = new Map()
  for (const item of subcategories.value) {
    const key = item.cat_name || '未分类'
    if (!map.has(key)) {
      map.set(key, { cat_name: key, domain: item.domain, items: [] })
    }
    map.get(key).items.push(item)
  }
  return Array.from(map.values())
})

function domainLabel(d) {
  return domainOptions.find(x => x.value === d)?.label || d
}

async function loadSubcategories() {
  loadingList.value = true
  selected.value = null
  standards.value = []
  subMeta.value = null
  try {
    const params = {}
    if (domain.value) params.domain = domain.value
    if (keyword.value.trim()) params.q = keyword.value.trim()
    const res = await axios.get('/api/dict/subcategories', { params })
    if (res.data?.success) {
      subcategories.value = res.data.subcategories || []
    } else {
      ElMessage.error(res.data?.error || '加载失败')
    }
  } catch (e) {
    ElMessage.error('加载小类失败')
  } finally {
    loadingList.value = false
  }
}

async function selectSub(item) {
  selected.value = item
  loadingDetail.value = true
  standards.value = []
  subMeta.value = item
  try {
    const res = await axios.get('/api/dict/standards', {
      params: { subcategory_id: item.id },
    })
    if (res.data?.success) {
      subMeta.value = res.data.subcategory || item
      standards.value = res.data.conditions || res.data.standards || []
    } else {
      ElMessage.error(res.data?.error || '加载标准失败')
    }
  } catch (e) {
    ElMessage.error('加载标准失败')
  } finally {
    loadingDetail.value = false
  }
}

function onDomainChange(d) {
  domain.value = d
  loadSubcategories()
}

onMounted(() => {
  loadSubcategories()
})
</script>

<style scoped>
.cs-tab {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 480px;
}

.cs-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
}

.domain-tabs {
  display: flex;
  gap: 4px;
  background: var(--bg-secondary, #f8fafc);
  border-radius: 8px;
  padding: 4px;
}

.domain-tab {
  padding: 6px 14px;
  border: none;
  background: transparent;
  border-radius: 6px;
  font-size: 13px;
  color: var(--text-secondary);
  cursor: pointer;
}

.domain-tab.active {
  background: var(--bg-card, #fff);
  color: var(--primary-600, #2563eb);
  font-weight: 600;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
}

.search-box {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  max-width: 320px;
}

.search-input {
  flex: 1;
  height: 34px;
  padding: 0 12px;
  border: 1px solid var(--border-lighter, #e5e7eb);
  border-radius: 8px;
  background: var(--bg-card, #fff);
  color: var(--text-primary);
  font-size: 13px;
  outline: none;
}

.search-input:focus {
  border-color: var(--primary-500, #3b82f6);
}

.stat-hint {
  font-size: 12px;
  color: var(--text-tertiary);
}

.cs-body {
  display: grid;
  grid-template-columns: minmax(240px, 300px) 1fr;
  gap: 16px;
  align-items: start;
  min-height: 420px;
}

.cs-list-panel {
  border: 1px solid var(--border-lighter, #e5e7eb);
  border-radius: 10px;
  background: var(--bg-card, #fff);
  max-height: 620px;
  overflow: auto;
  padding: 8px 0;
}

.cat-group + .cat-group {
  border-top: 1px solid var(--border-lighter, #e5e7eb);
}

.cat-title {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px 6px;
  position: sticky;
  top: 0;
  background: var(--bg-card, #fff);
}

.cat-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.cat-domain {
  font-size: 11px;
  color: var(--text-tertiary);
  background: var(--bg-secondary, #f8fafc);
  padding: 1px 6px;
  border-radius: 4px;
}

.cat-count {
  margin-left: auto;
  font-size: 11px;
  color: var(--text-tertiary);
}

.sub-list {
  list-style: none;
  margin: 0;
  padding: 0 8px 8px;
}

.sub-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  color: var(--text-secondary);
}

.sub-item:hover {
  background: var(--bg-secondary, #f8fafc);
  color: var(--text-primary);
}

.sub-item.active {
  background: color-mix(in srgb, var(--primary-500, #3b82f6) 12%, transparent);
  color: var(--primary-700, #1d4ed8);
  font-weight: 600;
}

.sub-code {
  font-size: 11px;
  color: var(--text-tertiary);
  min-width: 22px;
}

.cs-detail-panel {
  border: 1px solid var(--border-lighter, #e5e7eb);
  border-radius: 10px;
  background: var(--bg-card, #fff);
  padding: 16px;
  max-height: 620px;
  overflow: auto;
}

.detail-header h3 {
  margin: 0 0 4px;
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
}

.detail-header .meta {
  margin: 0 0 14px;
  font-size: 12px;
  color: var(--text-tertiary);
}

.subject-card {
  border: 1px solid var(--border-lighter, #e5e7eb);
  border-radius: 10px;
  padding: 12px 14px;
  margin-bottom: 14px;
  background: color-mix(in srgb, var(--primary-500, #3b82f6) 6%, transparent);
}

.subject-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.conditions-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 10px;
}

.empty-inline {
  font-size: 12px;
  color: var(--text-tertiary);
  padding: 4px 0;
}

.std-card {
  border: 1px solid var(--border-lighter, #e5e7eb);
  border-radius: 10px;
  padding: 12px 14px;
  margin-bottom: 12px;
  background: var(--bg-secondary, #fafafa);
}

.std-card-title {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.badge {
  font-size: 12px;
  font-weight: 600;
  color: var(--primary-700, #1d4ed8);
  background: color-mix(in srgb, var(--primary-500, #3b82f6) 14%, transparent);
  padding: 2px 8px;
  border-radius: 999px;
}

.limit {
  font-size: 13px;
  font-weight: 600;
  color: #b45309;
}

.limit-hours {
  font-size: 12px;
  color: var(--text-tertiary);
}

.std-fields {
  margin: 0;
  display: grid;
  gap: 8px;
}

.std-fields dt {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-bottom: 2px;
}

.std-fields dd {
  margin: 0;
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
}

.empty-tip {
  text-align: center;
  color: var(--text-tertiary);
  padding: 40px 16px;
  font-size: 13px;
}

.btn {
  height: 34px;
  padding: 0 12px;
  border-radius: 8px;
  border: 1px solid transparent;
  font-size: 13px;
  cursor: pointer;
}

.btn-secondary {
  background: var(--bg-secondary, #f8fafc);
  border-color: var(--border-lighter, #e5e7eb);
  color: var(--text-primary);
}

@media (max-width: 900px) {
  .cs-body {
    grid-template-columns: 1fr;
  }

  .cs-list-panel {
    max-height: 280px;
  }
}
</style>
