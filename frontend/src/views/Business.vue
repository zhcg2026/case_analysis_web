<template>
  <div class="page-container">
    <h1 class="page-title">业务平台</h1>
    <div class="content-card">
      <div v-if="platforms.length > 0" class="platform-grid">
        <a
          v-for="platform in platforms"
          :key="platform.id"
          :href="platform.url"
          target="_blank"
          rel="noopener noreferrer"
          class="platform-card"
        >
          <img v-if="platform.image_path" :src="platform.image_path" :alt="platform.name" class="platform-image" />
          <div v-else class="platform-icon">
            <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
              <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
            </svg>
          </div>
          <div class="platform-name">{{ platform.name }}</div>
        </a>
      </div>
      <div v-else class="empty-state">
        <svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
          <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
          <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
        </svg>
        <span>暂无业务平台链接</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const platforms = ref([])

async function fetchPlatforms() {
  try {
    const response = await axios.get('/api/business-platforms')
    platforms.value = response.data.platforms || []
  } catch (error) {
    console.error('获取业务平台列表失败:', error)
  }
}

onMounted(() => {
  fetchPlatforms()
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

.content-card {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-lighter);
  padding: var(--space-6);
}

.platform-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: var(--space-4);
}

.platform-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-4);
  background: var(--bg-secondary);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-lighter);
  text-decoration: none;
  transition: all var(--transition-fast);
}

.platform-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-lg);
  border-color: var(--primary-200);
}

.platform-image {
  width: 80px;
  height: 80px;
  object-fit: contain;
  border-radius: var(--radius-md);
}

.platform-icon {
  width: 80px;
  height: 80px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 40px;
  background: var(--primary-50);
  border-radius: var(--radius-md);
}

.platform-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  text-align: center;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-12);
  color: var(--text-tertiary);
}

.empty-state svg {
  opacity: 0.3;
}
</style>