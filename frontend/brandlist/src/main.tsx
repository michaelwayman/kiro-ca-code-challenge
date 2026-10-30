// PLACEHOLDER (replaced in spec 5): the real <BrandList /> mount, hydrating from the
// server-rendered list and its json_script initial data (D-022).
// It exists so the image's frontend build stage produces a Vite manifest from day one.

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

const mount = document.getElementById("brand-list-root");

if (mount) {
  createRoot(mount).render(<StrictMode>{null}</StrictMode>);
}
