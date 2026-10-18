/// <reference types="vitest/config" />
// Vite configuration: dev server, production build, PWA and unit tests.
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'
import { defineConfig } from 'vite'

export default defineConfig({
  // Read VITE_* variables from the `.env` at the repo root (one file for the whole project).
  envDir: '..',
  plugins: [
    react(),
    // Makes the app installable on PC and Android ("Add to home screen").
    // It generates the web manifest and a service worker that caches the app
    // files, so the interface still opens without network.
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.png', 'icons/apple-touch-icon.png'],
      manifest: {
        name: 'App Sport',
        short_name: 'Sport',
        description: 'Mon application de sport personnelle',
        lang: 'fr',
        start_url: '/',
        display: 'standalone',
        background_color: '#ffffff',
        theme_color: '#111317',
        icons: [
          { src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png' },
          {
            src: '/icons/icon-maskable-512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable',
          },
        ],
      },
    }),
  ],
  test: {
    // jsdom simulates a browser (DOM, window...) inside Node so components can render in tests.
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    // Playwright end-to-end tests live in e2e/ and are run separately.
    include: ['src/**/*.test.{ts,tsx}'],
  },
})
