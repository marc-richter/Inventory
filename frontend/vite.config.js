import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      // Nur fuer "npm run dev" ausserhalb von Docker relevant. Im Docker-Setup
      // uebernimmt nginx (siehe nginx.conf) das Proxying zum "backend"-Service.
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    // Zielplattform: moderne Browser -> kleinere Ausgabe.
    target: 'es2020',
    rollupOptions: {
      output: {
        // Bibliotheken in eigene Buendel, damit sie nach einem Update der
        // Anwendung im Browser-Cache bleiben. Gerade auf dem Pi und ueber
        // WLAN spuerbar.
        manualChunks: {
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          'vendor-scanner': ['html5-qrcode'],
        },
      },
    },
  },
})
