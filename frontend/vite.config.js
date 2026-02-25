import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiTarget = env.VITE_API_TARGET || 'http://localhost:5000'
  
  return {
    plugins: [vue()],
    server: {
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true,
          secure: false
        },
        '/health': {
          target: apiTarget,
          changeOrigin: true,
          secure: false
        },
        '/uploads': {
          target: apiTarget,
          changeOrigin: true,
          secure: false
        }
      }
    }
  }
})
