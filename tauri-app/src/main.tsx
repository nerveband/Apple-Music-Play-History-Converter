import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";
import { setupPluginListeners } from "tauri-plugin-mcp";

// Initialize MCP plugin listeners for E2E testing (dev-debug builds only).
if (import.meta.env.DEV) {
  setupPluginListeners();
  console.log("MCP plugin listeners initialized");
}

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
