"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Suspense, useState, type ReactNode } from "react";
import { Toaster } from "sonner";
import { AuthHydrator } from "@/features/auth/AuthHydrator";
import { TopLoader } from "@/components/TopLoader";

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: false },
        },
      }),
  );
  return (
    <QueryClientProvider client={client}>
      <Suspense fallback={null}>
        <TopLoader />
      </Suspense>
      <AuthHydrator />
      {children}
      <Toaster position="top-right" theme="dark" richColors />
    </QueryClientProvider>
  );
}
