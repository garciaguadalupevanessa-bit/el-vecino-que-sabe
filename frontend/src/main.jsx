import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import { configureBase } from "./lib/api.js";
import "./styles.css";

configureBase(import.meta.env.VITE_API_BASE ?? "");

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
