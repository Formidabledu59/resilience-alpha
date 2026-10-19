import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    // Pas de source maps en production : le code source n'est pas exposé
    sourcemap: false,
  },
  test: {
    environment: 'node',
  },
})
