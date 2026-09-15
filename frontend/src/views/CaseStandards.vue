<template>
  <div class="case-standards-page">
    <div class="page-header">
      <div>
        <h2>立结案标准</h2>
        <p class="page-sub">按大类/小类查询立案条件与处置标准（原系统管理页迁出）</p>
      </div>
    </div>
    <div class="standards-body">
      <CaseStandardsTab />
    </div>
  </div>
</template>

<script setup>
import CaseStandardsTab from '../components/admin/CaseStandardsTab.vue'
</script>

<style scoped>
.case-standards-page {
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
}

.standards-body {
  border: 1px solid var(--border-lighter);
  border-radius: var(--radius-md);
  background: var(--bg-card);
  padding: var(--space-4);
  min-height: 420px;
}
</style>
