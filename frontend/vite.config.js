import { defineConfig, loadEnv } from "vite";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "VITE_");
  const apiUrl = env.VITE_API_BASE_URL;
  if (!apiUrl) {
    throw new Error("Run python -m application.scripts.deploy_local_backend before starting the UI.");
  }
  const target = new URL(apiUrl);
  return {
    plugins: [tailwindcss()],
    server: {
      port: 5173,
      strictPort: true,
      proxy: {
        "/api": {
          target: target.origin,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, target.pathname),
        },
      },
    },
  };
});
