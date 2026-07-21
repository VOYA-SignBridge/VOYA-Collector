/// <reference types="vitest" />
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react({
      babel: {
        plugins: [['babel-plugin-react-compiler']],
      },
    }),
  ],
  // Restored 2026-07-21: commit cb46a07 dropped this block, which silently
  // disabled the whole frontend suite — vitest fell back to the node
  // environment, so every test importing axiosClient died on
  // "window is not defined". jsdom and vitest.setup.ts were still installed.
  test: {
    environment: 'jsdom',
    setupFiles: ['./vitest.setup.ts'],
    globals: true,
  },
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
        manualChunks(id) {
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
})
