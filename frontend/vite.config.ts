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
    // Raspberry Pi Optimierungen
    minify: 'terser',
    terserOptions: {
      compress: {
        drop_console: true,
        drop_debugger: true,
        pure_funcs: ['console.log', 'console.info', 'console.debug'],
        passes: 2,
      },
      mangle: {
        safari10: true,
      },
      format: {
        comments: false,
      },
    },
    // Code Splitting fuer kleinere initiale Bundles
    rollupOptions: {
      output: {
        manualChunks: {
          // Vendor chunks
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          'vendor-ui': ['html5-qrcode'],
          // Feature chunks
          'feature-inventory': [
            './src/pages/Inventur',
            './src/pages/LagerortInventur',
            './src/components/BarcodeScanner',
          ],
          'feature-settings': [
            './src/pages/Settings',
            './src/pages/SystemControl',
            './src/pages/Account',
          ],
          'feature-articles': [
            './src/pages/ArticleForm',
            './src/pages/BulkArticleForm',
            './src/pages/ArticleDetail',
            './src/pages/ArticleList',
          ],
          'feature-persons': [
            './src/pages/Persons',
            './src/pages/MyArticles',
            './src/pages/OpenIssues',
          ],
        },
        // Chunk naming for better caching
        chunkFileNames: 'assets/[name]-[hash].js',
        entryFileNames: 'assets/[name]-[hash].js',
        assetFileNames: 'assets/[name]-[hash].[ext]',
      },
    },
    // Reduce bundle size
    cssCodeSplit: true,
    // Report compressed sizes
    reportCompressedSize: true,
    // Target modern browsers for smaller output
    target: 'es2020',
  },
  resolve: {
    alias: {
      '@': '/src',
    },
  },
})