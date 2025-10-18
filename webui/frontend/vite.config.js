import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      // 在开发环境中，所有对 /api 的请求都将被代理到后端服务
      // start_webui.py 脚本会确保后端服务运行在 7099 端口
      '/api': {
        target: 'http://127.0.0.1:7099',
        changeOrigin: true,
      },
    }
  }
})