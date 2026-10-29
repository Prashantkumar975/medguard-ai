import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import pkg from './package.json'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  define: {
    __PKG_VERSION__: JSON.stringify(
      process.env.npm_package_version || '0.0.0'
    ),
  },
})
