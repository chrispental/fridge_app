import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// During `npm run dev`, /api is proxied to the backend so the app is same-origin.
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
