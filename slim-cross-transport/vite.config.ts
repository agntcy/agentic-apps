import { defineConfig } from "vite";

export default defineConfig({
  build: {
    target: "es2022",
  },
  assetsInclude: ["**/*.wasm"],
  optimizeDeps: {
    // Pre-bundling rewrites the relative WASM URL in web.ts to a path under
    // node_modules/.vite/deps/ that does not exist, so the browser receives
    // index.html instead of the binary.
    exclude: ["@agntcy/slim-bindings-react-native"],
  },
  server: {
    port: 5173,
    strictPort: true,
  },
  plugins: [
    {
      name: "wasm-mime-type",
      configureServer(server) {
        server.middlewares.use((req, res, next) => {
          if (req.url?.includes(".wasm")) {
            res.setHeader("Content-Type", "application/wasm");
          }
          next();
        });
      },
    },
  ],
});
