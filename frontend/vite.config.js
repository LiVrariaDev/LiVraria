import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'
import tailwindcss from '@tailwindcss/vite'
import path from 'node:path'
import fs from 'node:fs'

// 環境変数からSSL設定を取得
const useSSL = process.env.USE_SSL === 'true'
const certDir = path.resolve(__dirname, '..', 'certs')

// HTTPS設定
const httpsConfig = useSSL ? {
  key: fs.readFileSync(path.join(certDir, 'key.pem')),
  cert: fs.readFileSync(path.join(certDir, 'cert.pem')),
} : undefined

// プロキシターゲット（SSL有効時はhttps、無効時はhttp）
const proxyTarget = useSSL ? 'https://localhost:8000' : 'http://localhost:8000'

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

  server: {
    https: httpsConfig,
    proxy: {
      '/users': {
        target: proxyTarget,
        changeOrigin: true,
        secure: false, // 自己署名証明書を許可
      },
      '/sessions': {
        target: proxyTarget,
        changeOrigin: true,
        secure: false,
      },
      '/nfc': {
        target: proxyTarget,
        changeOrigin: true,
        secure: false,
      },
      '/search': {
        target: proxyTarget,
        changeOrigin: true,
        secure: false,
      },
      '/books': {
        target: proxyTarget,
        changeOrigin: true,
        secure: false,
      }
    }
  }
})