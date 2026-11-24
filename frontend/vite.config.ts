import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      autoUpdate: true,
      manifest: {
        name: "KALYCE — LiveShop Escrow",
        short_name: "KALYCE",
        theme_color: "#1B4332",
        background_color: "#ffffff",
        display: "standalone",
        icons: [
          { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" }
        ]
      },
      workbox: {
        runtimeCaching: [
          { urlPattern: /\/api\/v1\/sessions\/.*/,
            handler: "NetworkFirst", options: { cacheName: "live-sessions" } },
          { urlPattern: /\.(?:png|jpg|webp)$/,
            handler: "CacheFirst", options: { cacheName: "product-images",
                                              expiration: { maxEntries: 200 } } }
        ]
      }
    })
  ],
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          react: ["react", "react-dom", "react-router-dom"],
          query: ["@tanstack/react-query", "zustand"],
          live: ["./src/features/live/index.ts"],
          payment: ["./src/features/payment/index.ts"],
          backoffice: ["./src/features/admin/index.ts"]
        }
      }
    }
  },
  resolve: {
    alias: { "@": "/src" }
  }
});
