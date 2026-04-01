import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Any request from React to /api/* is forwarded to FastAPI
      // This prevents CORS errors in development
      '/api': {
        target:      'http://localhost:8000',
        changeOrigin: true,
        rewrite:     path => path.replace(/^\/api/, ''),
      },
    },
    // in production build, VITE_API_URL is injected by GitHUb actions
    define: {
      __API_URL__: JSON.stringify(process.env.VITE_API_URL || 'http://localhost:8000'),
    }
  },
})