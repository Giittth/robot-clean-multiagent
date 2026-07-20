import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    }
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
        changeOrigin: true,
        // 关键：静默 WebSocket 代理错误
        logLevel: 'silent',
        // 或者自定义错误处理（可选）
        configure: (proxy, options) => {
          proxy.on('error', (err) => {
            // 忽略连接拒绝错误，不打印
            if (err.code === 'ECONNREFUSED') return;
            console.error('WebSocket proxy error:', err);
          });
        }
      }
    }
  }
})
