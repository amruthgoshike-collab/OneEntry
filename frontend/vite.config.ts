import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // The backend's CORS allow-list is pinned to this exact origin, so never
  // silently hop to 5174 — fail loudly instead.
  server: { port: 5173, strictPort: true },
})
