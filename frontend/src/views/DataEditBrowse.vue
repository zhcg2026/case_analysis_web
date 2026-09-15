<template>
  <div class="data-edit-browse-page">
    <div class="page-header">
      <div>
        <h2>数据编辑浏览</h2>
        <p class="page-sub">上传案件数据、更新延期/返工/超时标记，浏览与维护已入库数据（原系统管理「数据管理」迁出）</p>
      </div>
    </div>
    <div class="browse-body">
      <DataManagementTab />
    </div>
  </div>
</template>

<script setup>
import DataManagementTab from '../components/admin/DataManagementTab.vue'
</script>

<style scoped>
.data-edit-browse-page {
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

.browse-body {
  /* 内部 content-card 自带边框 */
  min-height: 360px;
}
</style>
