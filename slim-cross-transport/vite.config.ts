import { fileURLToPath, URL } from "node:url";

import { defineConfig } from "vite";

// Setting server.fs.allow replaces Vite's default list, so include both this
// project and the sibling slim-bindings checkout (WASM lives outside node_modules).
const projectRoot = fileURLToPath(new URL(".", import.meta.url));
const bindingsRoot = fileURLToPath(
  new URL("../../slim-bindings/react-native", import.meta.url),
);

export default defineConfig({
  build: {
    target: "es2022",
  },
  server: {
    fs: {
      allow: [projectRoot, bindingsRoot],
    },
    port: 5173,
    strictPort: true,
  },
});
