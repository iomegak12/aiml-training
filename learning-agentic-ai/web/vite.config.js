import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// In development the Vite server plays nginx's role: /api/* is proxied to the API
// with the /api prefix stripped (set VITE_API_PROXY_TARGET to change the target).
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const target = env.VITE_API_PROXY_TARGET || 'http://localhost:8000'

  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        '/api': {
          target,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ''),
        },
      },
    },
    build: {
      chunkSizeWarningLimit: 700,
    },
  }
})
