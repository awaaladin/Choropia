import type { createBrowserRouter } from "react-router";

/** Counts page views for the staff Analytics page. Anonymous: a random id kept in this browser tells repeat visitors apart.
 * No account, name or IP address is sent. Failures are ignored; counting must never affect the site. */
const KEY = "choropia-visitor";

function visitorId(): string {
  try {
    let id = localStorage.getItem(KEY);
    if (!id) {
      id = (crypto.randomUUID?.() ?? `${Date.now()}${Math.random().toString(36).slice(2)}`).replace(/[^A-Za-z0-9_-]/g, "").slice(0, 36);
      localStorage.setItem(KEY, id);
    }
    return id;
  } catch {
    return "";
  }
}

let last = "";
function hit(path: string) {
  const vid = visitorId();
  if (!vid || path === last || path.startsWith("/staff")) return;
  last = path;
  try {
    void fetch("/api/v1/analytics/hit/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path, vid, ref: document.referrer, w: window.innerWidth }),
      keepalive: true,
    }).catch(() => undefined);
  } catch {
    /* ignore */
  }
}

export function startAnalytics(router: ReturnType<typeof createBrowserRouter>) {
  hit(router.state.location.pathname);
  router.subscribe((state) => {
    if (state.navigation.state === "idle") hit(state.location.pathname);
  });
}
