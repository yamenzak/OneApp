import path from 'path'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// Built into the Frappe app rather than served from the edge. Each site then
// serves exactly the frontend matching its own backend, so a rolling migration
// can never leave a new SPA talking to an unmigrated site.
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: { '@': path.resolve(__dirname, 'src') },
  },
  build: {
    outDir: '../oneapp/public/frontend',
    emptyOutDir: true,
    target: 'es2015',
    rollupOptions: {
      output: {
        // Stable entry names so the Jinja template can reference them without a
        // manifest lookup.
        entryFileNames: 'assets/[name].js',
        chunkFileNames: 'assets/[name]-[hash].js',
        assetFileNames: 'assets/[name][extname]',
      },
    },
  },
  server: {
    proxy: {
      '^/(app|api|assets|files|private)': {
        target: 'http://localhost:8000',
        ws: true,
        changeOrigin: true,
      },
    },
  },
})
