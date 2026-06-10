import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { config } from "dotenv";
import { resolve } from "path";

config({ path: resolve(__dirname, "../../.env") });

export default defineConfig({
  plugins: [react()],
  build: { outDir: "../dist/client", emptyOutDir: true },
  server: {
    proxy: {
      "/api": `http://localhost:${process.env.PORT ?? 3001}`,
    },
  },
});
