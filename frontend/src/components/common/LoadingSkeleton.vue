<template>
  <div class="skeleton-wrapper" :class="{ 'skeleton-inline': inline }">
    <!-- 卡片骨架 -->
    <template v-if="type === 'card'">
      <div class="skeleton-card">
        <div class="skeleton skeleton-title"></div>
        <div class="skeleton skeleton-text"></div>
        <div class="skeleton skeleton-text" style="width: 70%"></div>
      </div>
    </template>

    <!-- 表格骨架 -->
    <template v-else-if="type === 'table'">
      <div class="skeleton-table">
        <div class="skeleton-table-header">
          <div v-for="i in columns" :key="i" class="skeleton skeleton-th"></div>
        </div>
        <div v-for="row in rows" :key="row" class="skeleton-table-row">
          <div v-for="col in columns" :key="col" class="skeleton skeleton-td"></div>
        </div>
      </div>
    </template>

    <!-- 列表骨架 -->
    <template v-else-if="type === 'list'">
      <div v-for="i in count" :key="i" class="skeleton-list-item">
        <div class="skeleton skeleton-avatar"></div>
        <div class="skeleton-list-content">
          <div class="skeleton skeleton-text" style="width: 40%"></div>
          <div class="skeleton skeleton-text" style="width: 80%"></div>
        </div>
      </div>
    </template>

    <!-- 图表骨架 -->
    <template v-else-if="type === 'chart'">
      <div class="skeleton-chart">
        <div class="skeleton skeleton-title" style="width: 30%"></div>
        <div class="skeleton-chart-content">
          <div class="skeleton-chart-bar" v-for="i in 8" :key="i" :style="{ height: Math.random() * 60 + 40 + '%' }"></div>
        </div>
      </div>
    </template>

    <!-- 文本骨架 -->
    <template v-else-if="type === 'text'">
      <div v-for="i in count" :key="i" class="skeleton skeleton-text" :style="{ width: widths[i-1] || '100%' }"></div>
    </template>

    <!-- 默认骨架 -->
    <template v-else>
      <div class="skeleton" :style="{ width, height }"></div>
    </template>
  </div>
</template>

<script setup>
defineProps({
  type: {
    type: String,
    default: 'default',
    validator: (v) => ['default', 'card', 'table', 'list', 'chart', 'text'].includes(v)
  },
  count: {
    type: Number,
    default: 3
  },
  rows: {
    type: Number,
    default: 5
  },
  columns: {
    type: Number,
    default: 4
  },
  width: {
    type: String,
    default: '100%'
  },
  height: {
    type: String,
    default: '20px'
  },
  widths: {
    type: Array,
    default: () => ['100%', '90%', '80%']
  },
  inline: {
    type: Boolean,
    default: false
  }
})
</script>

<style scoped>
.skeleton-wrapper {
  width: 100%;
}

.skeleton {
  background: linear-gradient(
    90deg,
    var(--bg-tertiary) 25%,
    var(--bg-secondary) 50%,
    var(--bg-tertiary) 75%
  );
  background-size: 200% 100%;
  animation: skeleton-loading 1.5s infinite;
  border-radius: var(--radius-sm);
}

@keyframes skeleton-loading {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.skeleton-inline {
  display: inline-block;
}

/* 卡片骨架 */
.skeleton-card {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: var(--space-6);
  border: 1px solid var(--border-lighter);
}

.skeleton-title {
  height: 24px;
  margin-bottom: var(--space-4);
}

.skeleton-text {
  height: 14px;
  margin-bottom: var(--space-2);
}

/* 表格骨架 */
.skeleton-table {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  overflow: hidden;
  border: 1px solid var(--border-lighter);
}

.skeleton-table-header {
  display: flex;
  padding: var(--space-4);
  background: var(--bg-tertiary);
  gap: var(--space-4);
}

.skeleton-th {
  flex: 1;
  height: 16px;
}

.skeleton-table-row {
  display: flex;
  padding: var(--space-4);
  border-top: 1px solid var(--border-lighter);
  gap: var(--space-4);
}

.skeleton-td {
  flex: 1;
  height: 14px;
}

/* 列表骨架 */
.skeleton-list-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3);
  background: var(--bg-card);
  border-radius: var(--radius-md);
  margin-bottom: var(--space-2);
}

.skeleton-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  flex-shrink: 0;
}

.skeleton-list-content {
  flex: 1;
}

/* 图表骨架 */
.skeleton-chart {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
  border: 1px solid var(--border-lighter);
}

.skeleton-chart-content {
  display: flex;
  align-items: flex-end;
  justify-content: space-around;
  height: 200px;
  margin-top: var(--space-4);
}

.skeleton-chart-bar {
  width: 30px;
  background: linear-gradient(
    180deg,
    var(--primary-200) 0%,
    var(--primary-100) 100%
  );
  border-radius: var(--radius-sm) var(--radius-sm) 0 0;
}

[data-theme="dark"] .skeleton-chart-bar {
  background: linear-gradient(
    180deg,
    var(--primary-700) 0%,
    var(--primary-800) 100%
  );
}
</style>