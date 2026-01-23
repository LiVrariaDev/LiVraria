import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'
import tailwindcss from '@tailwindcss/vite'
import path from 'node:path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    vueDevTools(),
    tailwindcss(),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    },
  },
  envDir: path.resolve(__dirname, '..'),
  
  // ▼▼▼ この設定を追加してください ▼▼▼
  server: {
    proxy: {
      '/users': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/sessions': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/nfc': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  }
  // ▲▲▲ ここまで ▲▲▲
})