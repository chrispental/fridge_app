import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// During `npm run dev`, /api is proxied to the backend so the app is same-origin.
// VITE_SUPABASE_* come from the repo-root .env (shared with the backend); only
// VITE_-prefixed vars are exposed to the bundle.
export default defineConfig({
  plugins: [react()],
  envDir: '..',
  server: {
    host: true,
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
