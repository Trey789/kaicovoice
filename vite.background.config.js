import { defineConfig } from 'vite';

export default defineConfig({
  build: {
    outDir: 'assets',
    emptyOutDir: false,
    cssCodeSplit: false,
    rollupOptions: {
      input: 'src/background/main.jsx',
      output: {
        entryFileNames: 'ghost-fibers.js',
        assetFileNames: 'ghost-fibers.css',
      },
    },
  },
});
