import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/persons': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/daily_ranking': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    }
  }
});