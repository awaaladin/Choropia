import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { toast } from "sonner";
import { errorMessage } from "@/lib/actions";
import { api } from "@/lib/api";

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: { client_id: string; callback: (r: { credential: string }) => void }) => void;
          renderButton: (el: HTMLElement, options: Record<string, unknown>) => void;
        };
      };
    };
  }
}

const SCRIPT = "https://accounts.google.com/gsi/client";

function loadScript(): Promise<void> {
  return new Promise((resolve, reject) => {
    if (window.google) return resolve();
    const existing = document.querySelector(`script[src="${SCRIPT}"]`);
    const script = existing ?? Object.assign(document.createElement("script"), { src: SCRIPT, async: true });
    script.addEventListener("load", () => resolve());
    script.addEventListener("error", () => reject(new Error("Google sign-in could not load")));
    if (!existing) document.head.appendChild(script);
  });
}

/** "Continue with Google". Shows nothing until Google sign-in has been configured on the server. */
export function GoogleButton({ onToken }: { onToken: (idToken: string) => Promise<void> }) {
  const holder = useRef<HTMLDivElement>(null);
  const config = useQuery({ queryKey: ["google-config"], queryFn: api.googleConfig, staleTime: 10 * 60_000, retry: false });
  const clientId = config.data?.client_id;

  useEffect(() => {
    if (!clientId || !holder.current) return;
    let cancelled = false;
    loadScript()
      .then(() => {
        if (cancelled || !holder.current || !window.google) return;
        window.google.accounts.id.initialize({
          client_id: clientId,
          callback: (response) => onToken(response.credential).catch((err) => toast.error(errorMessage(err))),
        });
        window.google.accounts.id.renderButton(holder.current, { theme: "outline", size: "large", width: 320, text: "continue_with" });
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [clientId, onToken]);

  if (!clientId) return null;
  return (
    <div className="mt-4">
      <div className="mb-3 flex items-center gap-3 text-xs text-muted-foreground">
        <span className="h-px flex-1 bg-border" /> or <span className="h-px flex-1 bg-border" />
      </div>
      <div ref={holder} className="flex justify-center" />
    </div>
  );
}
