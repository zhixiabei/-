import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  // 关键：禁用导致报错的inspect/devtools插件
  optimizeDeps: {
    exclude: ['vite-plugin-inspect', 'vite-plugin-vue-devtools']
  },
  // 关闭依赖预优化，彻底避开插件冲突
  server: {
    fs: {
      strict: false
    }
  }
})