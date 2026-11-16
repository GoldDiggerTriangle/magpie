import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Isolated source fixture: deliberately no API/media proxy to the live service.
export default defineConfig({
  plugins: [react()],
  server: { host: "127.0.0.1", port: 4179, strictPort: true },
});
