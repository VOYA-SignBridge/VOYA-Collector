import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ command }) => ({
  plugins: [
    react({
      babel: {
        plugins: [['babel-plugin-react-compiler']],
      },
    }),
  ],
  // Bỏ console.log/console.debug khỏi bundle production. Code hiện có rải rác
  // hàng chục lời gọi không được bọc `import.meta.env.DEV` (nặng nhất là
  // getClassesList in cả JSON.stringify của response), làm console rất ồn khi
  // mở DevTools lúc demo. Đánh dấu "pure" để esbuild tree-shake chúng — giữ
  // nguyên console.error/console.warn vì đó là báo lỗi thật.
  // Chỉ áp lúc build: dev vẫn cần log để gỡ lỗi.
  esbuild: command === 'build' ? { pure: ['console.log', 'console.debug'] } : {},
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true,
      },
      '/auth': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/classes': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/dataset': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/inference': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/jobs': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/realtime': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/upload': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id: string) {
          if (id.includes('node_modules')) {
            if (id.includes('@mediapipe')) return 'vendor_mediapipe';
            if (id.includes('recharts')) return 'vendor_recharts';
            if (id.includes('axios')) return 'vendor_axios';
            return 'vendor';
          }
        },
      },
    },
  },
  // Vitest chạy code chạm tới `window` ngay lúc import (axiosClient đọc
  // window.__ENV__), nên phải có DOM giả. Thiếu khối này thì environment mặc
  // định là 'node' và vitest.setup.ts không bao giờ được nạp → 3 file test
  // chết ngay ở bước import với "window is not defined".
  test: {
    environment: 'jsdom',
    setupFiles: ['./vitest.setup.ts'],
    globals: true,
    // tests-e2e/ holds Playwright specs (test.describe/beforeAll from
    // @playwright/test, a different runner) — vitest's default include glob
    // picks up any *.spec.ts, so without this it tries to import them too
    // and dies on "test.beforeAll() ... not expected to be called here".
    exclude: ['**/node_modules/**', '**/tests-e2e/**'],
  },
}))
