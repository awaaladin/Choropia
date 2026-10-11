import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router";
import { AppBoot } from "@/components/AppBoot";
import { AuthProvider } from "@/lib/auth";
import { PrefsProvider } from "@/lib/prefs";
import { router } from "./router";
import "./styles.css";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: false } },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <PrefsProvider>
        <AuthProvider>
          <AppBoot>
            <RouterProvider router={router} />
          </AppBoot>
        </AuthProvider>
      </PrefsProvider>
    </QueryClientProvider>
  </StrictMode>,
);
