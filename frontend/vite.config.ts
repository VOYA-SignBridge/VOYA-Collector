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
