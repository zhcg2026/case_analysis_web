<template>
  <div class="assessment-input-page">
    <div class="page-header">
      <div>
        <h2>采集员数据录入</h2>
        <p class="page-sub">按月录入采集员侧数据：单体垃圾件数、自行处置数与专项采集明细，供考核计分与月报使用。已录入月份可再次打开修改。</p>
      </div>
    </div>
    <div class="input-body">
      <AssessmentInputTab mode="collector" />
    </div>
  </div>
</template>

<script setup>
import AssessmentInputTab from '../components/admin/AssessmentInputTab.vue'
</script>

<style scoped>
.assessment-input-page {
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

.input-body {
  border: 1px solid var(--border-lighter);
  border-radius: var(--radius-md);
  background: var(--bg-card);
  padding: var(--space-4);
  min-height: 360px;
}
</style>
