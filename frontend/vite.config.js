import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Builds a single self-contained IIFE bundle (JS) plus a single CSS file, with
// fixed (unhashed) output names. The jobsearch server inlines both files
// directly into the page it serves -- the strict CSP here is `default-src
// 'none'` with `script-src` allowed only by exact SHA-256 hash of the inline
// script content, so there is no `<script src=...>` this bundle could be
// loaded from, and no external CDN it could pull React/recharts from either.
// Everything has to be one inlineable, dependency-free blob.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    cssCodeSplit: false,
    assetsInlineLimit: 100000000,
    rollupOptions: {
      input: 'src/main.jsx',
      output: {
        format: 'iife',
        entryFileNames: 'bundle.js',
        chunkFileNames: 'bundle.js',
        assetFileNames: 'bundle.[ext]',
        inlineDynamicImports: true,
      },
    },
  },
})
