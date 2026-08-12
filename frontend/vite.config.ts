/// <reference types="vitest" />
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  base: '',
  test: {
    environment: 'jsdom',
    setupFiles: ['./vitest.setup.ts'],
    globals: true
  },
  plugins: [
    react({
      babel: {
        plugins: [['babel-plugin-react-compiler']],
      },
    }),
  ],
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
      // Keys starting with ^ are regexes. /realtime and /upload are BOTH SPA
      // routes and API prefixes, so a plain prefix rule sends the page request
      // to the backend on reload and the browser gets a JSON 404 instead of the
      // app. Match only the API paths underneath them.
      '^/realtime/(predict|models|health)': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '^/upload/(camera|video)': {
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
            // three.js is only reached via the lazy Hand3DPlayer import —
            // keep it out of the eager catch-all vendor chunk.
            if (id.includes('/node_modules/three/')) return 'vendor_three';
            if (id.includes('recharts')) return 'vendor_recharts';
            if (id.includes('axios')) return 'vendor_axios';
            // Split the stable React runtime into its own chunk so that
            // shipping app-code changes doesn't invalidate the (large,
            // rarely-changing) React bundle in users' caches.
            if (
              id.includes('/node_modules/react/') ||
              id.includes('/node_modules/react-dom/') ||
              id.includes('/node_modules/scheduler/') ||
              id.includes('/node_modules/react-is/')
            ) return 'vendor_react';
            if (id.includes('/node_modules/react-router')) return 'vendor_router';
            return 'vendor';
          }
        },
      },
    },
  },
})
