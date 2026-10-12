import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, Clapperboard, Home, MessageCircle, PlusCircle, Search, Settings, ShoppingBag, Store, Package } from "lucide-react";
import { useEffect, useRef, useState, type CSSProperties, type FormEvent } from "react";
import { Outlet, ScrollRestoration, useLocation, useNavigate } from "react-router";
import { Toaster, toast } from "sonner";
import { api, rows, wsUrl } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { usePrefs } from "@/lib/prefs";
import { displayName } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Link, NavLink } from "./AppLink";
import { Button, LinkButton } from "./Button";
import { BrandLoader } from "./BrandLoader";
import { SettingsDrawer } from "./SettingsDrawer";
import { Avatar } from "./ui";

const NAV = [
  { to: "/feed", label: "Feed", end: true },
  { to: "/marketplace", label: "Marketplace" },
  { to: "/reels", label: "Reels" },
  { to: "/orders", label: "Orders" },
  { to: "/wallet", label: "Wallet" },
  { to: "/messages", label: "Messages" },
] as const;

const TABS = [
  { to: "/feed", label: "Feed", icon: Home, end: true },
  { to: "/marketplace", label: "Market", icon: Store },
  { to: "/reels", label: "Reels", icon: Clapperboard },
  { to: "/listings/new", label: "Sell", icon: PlusCircle },
  { to: "/orders", label: "Orders", icon: Package },
  { to: "/messages", label: "Messages", icon: MessageCircle },
] as const;

const ROUTE_LOADER_MS = 420;

/** The "normal refresh" brand pulse: a brief transitional beat on every in-app navigation —
 * independent of how fast the destination page's own data actually loads. Skipped under the
 * "reduced motion" preference, same as every other animation in the app. */
function useRouteTransition(enabled: boolean) {
  const { pathname } = useLocation();
  const [transitioning, setTransitioning] = useState(false);
  const first = useRef(true);

  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    if (!enabled) return;
    setTransitioning(true);
    const timer = window.setTimeout(() => setTransitioning(false), ROUTE_LOADER_MS);
    return () => window.clearTimeout(timer);
  }, [pathname, enabled]);

  return transitioning;
}

function useUnreadNotifications() {
  const { loggedIn } = useAuth();
  const { data } = useQuery({
    queryKey: ["notifications"],
    queryFn: api.listNotifications,
    enabled: loggedIn,
    refetchInterval: 60_000,
  });
  return rows(data).filter((n) => !n.is_read);
}

/** Live notification pushes over WebSocket, when a realtime host is reachable; polling covers the rest. */
function useRealtimeNotifications() {
  const { loggedIn } = useAuth();
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!loggedIn) return;
    let socket: WebSocket | null = null;
    let retry = 0;
    let timer: number | undefined;
    let closed = false;

    const connect = () => {
      const url = wsUrl("/ws/notifications/");
      if (!url || closed) return;
      socket = new WebSocket(url);
      socket.onopen = () => (retry = 0);
      socket.onmessage = (event) => {
        try {
          const n = JSON.parse(event.data) as { verb?: string };
          if (n.verb) toast(n.verb);
        } catch {
          /* ignore malformed frames */
        }
        queryClient.invalidateQueries({ queryKey: ["notifications"] });
      };
      socket.onclose = () => {
        if (closed) return;
        retry += 1;
        timer = window.setTimeout(connect, Math.min(30_000, 1000 * 2 ** retry));
      };
    };
    connect();
    return () => {
      closed = true;
      window.clearTimeout(timer);
      socket?.close();
    };
  }, [loggedIn, queryClient]);
}

export function AppShell() {
  const { user, loggedIn } = useAuth();
  const prefs = usePrefs();
  const navigate = useNavigate();
  const routeTransitioning = useRouteTransition(prefs.motion === "full");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [query, setQuery] = useState("");
  const unread = useUnreadNotifications();
  useRealtimeNotifications();

  const submitSearch = (e: FormEvent) => {
    e.preventDefault();
    navigate(query.trim() ? `/marketplace?search=${encodeURIComponent(query.trim())}` : "/marketplace", { viewTransition: true });
  };

  const hasUnreadMessages = unread.some((n) => n.notification_type === "message");

  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <header className="sticky top-0 z-40 border-b border-border bg-panel backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-[1400px] items-center gap-4 px-4 lg:gap-5 lg:px-8">
          <Link to="/feed" className="flex shrink-0 items-center" aria-label="Choropia home">
            <img src="/logo.png" alt="Choropia" className="h-7 w-auto dark:invert dark:opacity-90" />
          </Link>

          <nav className="hidden items-center gap-1 text-sm md:flex">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={"end" in item}
                className={({ isActive }) =>
                  cn(
                    "relative flex items-center px-3 py-5 transition-colors",
                    isActive
                      ? "font-semibold text-foreground after:absolute after:inset-x-3 after:bottom-0 after:h-0.5 after:rounded-full after:bg-primary"
                      : "text-muted-foreground hover:text-foreground",
                  )
                }
              >
                {item.label}
                {item.to === "/messages" && hasUnreadMessages && <span className="ml-1.5 size-1.5 rounded-full bg-success" />}
              </NavLink>
            ))}
          </nav>

          <form
            onSubmit={submitSearch}
            className="ml-auto hidden h-9 w-72 items-center gap-2 rounded-md border border-border bg-panel px-3 text-muted-foreground shadow-sm transition-shadow focus-within:ring-2 focus-within:ring-ring lg:flex"
          >
            <Search size={15} />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
              placeholder="Search Uyo listings…"
              aria-label="Search listings"
            />
          </form>

          <div className="ml-auto flex items-center gap-2 lg:ml-0">
            <LinkButton to="/listings/new" className="hidden sm:inline-flex">
              <ShoppingBag size={15} /> Sell
            </LinkButton>
            {loggedIn && (
              <Link
                to="/notifications"
                aria-label="Notifications"
                title="Notifications"
                className="relative grid size-9 place-items-center rounded-md border border-border bg-panel text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
              >
                <Bell size={16} />
                {unread.length > 0 && (
                  <span className="absolute -right-1 -top-1 grid min-w-4 place-items-center rounded-full bg-primary px-1 text-[10px] font-bold leading-4 text-primary-foreground">
                    {unread.length > 9 ? "9+" : unread.length}
                  </span>
                )}
              </Link>
            )}
            <Button variant="icon" aria-label="Open display settings" title="Display settings" onClick={() => setSettingsOpen(true)} className="size-9 p-0">
              <Settings size={16} />
            </Button>
            {loggedIn ? (
              <Link to="/profile" aria-label="Your profile" title="Your profile">
                <Avatar src={user?.profile?.avatar} name={displayName(user)} size={36} />
              </Link>
            ) : (
              <LinkButton to="/login" variant="secondary">
                Log in
              </LinkButton>
            )}
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-[1400px] flex-1 px-4 py-5 pb-24 md:pb-8 lg:px-8">
        <Outlet />
      </main>

      <footer className="hidden border-t border-border py-6 text-center text-xs text-muted-foreground md:block">
        Choropia — social buy-and-sell marketplace (Uyo pilot)
      </footer>

      <nav className="fixed inset-x-0 bottom-0 z-40 border-t border-border bg-panel pb-[env(safe-area-inset-bottom)] backdrop-blur-xl md:hidden" aria-label="Primary">
        <div className="grid grid-cols-6">
          {TABS.map(({ to, label, icon: Icon, ...rest }) => (
            <NavLink
              key={to}
              to={to}
              end={"end" in rest}
              className={({ isActive }) =>
                cn(
                  "flex flex-col items-center gap-0.5 py-2 text-[10px] font-medium transition-colors active:scale-95",
                  isActive ? "text-primary" : "text-muted-foreground",
                )
              }
            >
              <Icon size={19} />
              {label}
            </NavLink>
          ))}
        </div>
      </nav>

      {routeTransitioning && <BrandLoader variant="simple" />}
      <SettingsDrawer open={settingsOpen} onClose={() => setSettingsOpen(false)} />
      <Toaster
        theme={prefs.theme}
        position="top-right"
        offset={72}
        toastOptions={{ classNames: { toast: "!rounded-lg !border !border-border font-sans" } }}
        style={{ "--normal-bg": "var(--popover)", "--normal-text": "var(--foreground)", "--normal-border": "var(--border)" } as CSSProperties}
      />
      <ScrollRestoration />
    </div>
  );
}
