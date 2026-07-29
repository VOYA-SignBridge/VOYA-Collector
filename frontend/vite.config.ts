import { defineConfig } from 'vite'
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
            return 'vendor';
          }
        },
      },
    },
  },
})
