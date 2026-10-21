import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// dev-сервер проксирует /api на бэкенд (по умолчанию :8000); в контейнере эту роль выполняет nginx
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/api': { target: process.env.VITE_API_PROXY ?? 'http://localhost:8000', changeOrigin: true } },
  },
  build: {
    sourcemap: false,
    chunkSizeWarningLimit: 900,
    rollupOptions: {
      output: {
        manualChunks: {
          react: ['react', 'react-dom', 'react-router-dom', '@tanstack/react-query'],
          mantine: ['@mantine/core', '@mantine/hooks', '@mantine/notifications', '@mantine/dropzone'],
          charts: ['recharts'],
        },
      },
    },
  },
});
