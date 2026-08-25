import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const frontendPort = parseInt(process.env.FRONTEND_PORT || env.FRONTEND_PORT || '5188', 10)
  const backendPort = parseInt(process.env.BACKEND_PORT || env.BACKEND_PORT || '8088', 10)

  return {
    plugins: [react()],
    server: {
      port: frontendPort,
      strictPort: false, // will auto-increment if 5188 is taken
      proxy: {
        '/api': {
          target: `http://localhost:${backendPort}`,
          changeOrigin: true,
        }
      }
    }
  }
})
