import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    // Makes the site installable ("Add to Home Screen"). It adds no app feature or screen.
    VitePWA({
      // A new deploy's service worker takes over on its own; nobody has to clear anything.
      registerType: 'autoUpdate',
      // /registerSW.js is a file, not inline code: the security policy (nginx.conf) allows no inline scripts.
      injectRegister: 'script',
      // Do not pre-download the icons when the worker installs; they are fetched when needed.
      includeManifestIcons: false,
      manifest: {
        id: '/',
        name: 'SkillDARA',
        short_name: 'SkillDARA',
        description: 'AI agents for students and professionals to upgrade skills and get job-ready.',
        lang: 'en',
        start_url: '/',
        scope: '/',
        display: 'standalone',
        theme_color: '#17348e',
        background_color: '#ffffff',
        categories: ['education'],
        icons: [
          { src: '/pwa-192x192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
          { src: '/pwa-512x512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
          { src: '/pwa-maskable-192x192.png', sizes: '192x192', type: 'image/png', purpose: 'maskable' },
          { src: '/pwa-maskable-512x512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      workbox: {
        // Only static files are ever stored, and only as they are used. Nothing but the
        // tiny manifest file is pre-downloaded, no page (HTML) is cached and no navigation is answered by the
        // worker, so the public pages (/agents/ ...), /login and the sign-in return are
        // always fetched from the server exactly as before.
        globPatterns: [],
        navigateFallback: null,
        cleanupOutdatedCaches: true,
        runtimeCaching: [
          {
            // The built JS, CSS and fonts. File names carry a content hash, so a cached copy never goes stale.
            urlPattern: ({ url, sameOrigin }) => sameOrigin && url.pathname.startsWith('/assets/'),
            handler: 'CacheFirst',
            options: {
              cacheName: 'skilldara-assets',
              cacheableResponse: { statuses: [200] },
              expiration: { maxEntries: 150, maxAgeSeconds: 60 * 60 * 24 * 30 },
            },
          },
          {
            // Images and fonts that are files of this site. Never anything the orchestrator serves
            // (/chat, /gateway, /registry, /api, /auth and every other proxied prefix), and nothing
            // from another origin, so port 8100 is never touched.
            urlPattern: ({ url, sameOrigin }) =>
              sameOrigin &&
              /\.(?:png|jpe?g|webp|gif|svg|ico|woff2?)$/i.test(url.pathname) &&
              !/^\/(?:auth|chat|chats|gateway|billing|platform-admin|registry|api|learner|organizations|a2a|voice|conductor|links|proctoring|assessments|my-assessments|knowledge|courses|course-media|agent-state|shared|assessment|certificate-link)(?:\/|$)/.test(url.pathname),
            handler: 'StaleWhileRevalidate',
            options: {
              cacheName: 'skilldara-images',
              cacheableResponse: { statuses: [200] },
              expiration: { maxEntries: 80, maxAgeSeconds: 60 * 60 * 24 * 14 },
            },
          },
        ],
      },
    }),
  ],
})
