import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { SaltProvider } from "@salt-ds/core";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";

import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "@fontsource/inter/700.css";
import "@fontsource/inter/800.css";
import "material-symbols/outlined.css";

import "@salt-ds/theme/index.css";
import "./theme/autodoc-theme.css";
import "./index.css";

import App from "./App";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 2,
      refetchOnWindowFocus: false,
    },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <SaltProvider mode="light">
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </SaltProvider>
    </QueryClientProvider>
  </StrictMode>,
);
