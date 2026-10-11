import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // Bind 0.0.0.0 so the macmini nginx (docker container, 172.17.0.1) can
  // reach the dev server; default is loopback-only which 502s through nginx.
  server: {
    host: true,
    allowedHosts: ['linguard.joseantmazonsb.es'],
    // Prevent any intermediary/browser from caching dev modules — a stale
    // cached module once caused requests to a hardcoded old API URL.
    headers: {
      'Cache-Control': 'no-store',
    },
    proxy: {
      // Same-origin API access: the dev server forwards /api and /ws to the
      // backend so the frontend can use relative URLs behind any reverse proxy.
      // changeOrigin must stay FALSE: with it, the backend sees Host
      // localhost:8000 and builds absolute 307 redirects (trailing-slash
      // normalization) pointing at the wrong host for remote browsers.
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: false,
      },
      '/health': {
        target: 'http://localhost:8000',
        changeOrigin: false,
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
        changeOrigin: false,
      },
    },
  },
  optimizeDeps: {
    include: ['react', 'react-dom', 'react-toastify']
  },
  resolve: {
    dedupe: ['react', 'react-dom']
  }
})
