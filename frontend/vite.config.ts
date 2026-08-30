import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from 'tailwindcss'
import autoprefixer from 'autoprefixer'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const frontendPort = parseInt(process.env.FRONTEND_PORT || env.FRONTEND_PORT || '5188', 10)
  const backendPort = parseInt(process.env.BACKEND_PORT || env.BACKEND_PORT || '8080', 10)

  return {
    plugins: [react()],
    css: {
      postcss: {
        plugins: [
          tailwindcss({
            content: [
              "./index.html",
              "./src/**/*.{js,ts,jsx,tsx}",
            ],
            darkMode: 'class',
            theme: {
              extend: {
                fontFamily: {
                  sans: ['Inter', 'system-ui', 'sans-serif'],
                  mono: ['JetBrains Mono', 'monospace'],
                },
              },
            },
          }),
          autoprefixer()
        ]
      }
    },
    server: {
      port: frontendPort,
      strictPort: false,
      proxy: {
        '/api': {
          target: `http://localhost:${backendPort}`,
          changeOrigin: true,
        }
      }
    }
  }
})
