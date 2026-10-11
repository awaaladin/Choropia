import { ArrowUpRight } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Menu, Settings, X } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { Link, NavLink } from "./AppLink";
import { Button, LinkButton } from "./Button";
import { SettingsDrawer } from "./SettingsDrawer";

const PUBLIC_LINKS = [
  { to: "/about", label: "About us" },
  { to: "/how-it-works", label: "How it works" },
  { to: "/contact", label: "Contact" },
] as const;

const FOOTER_LINKS = [...PUBLIC_LINKS, { to: "/privacy", label: "Privacy" }] as const;

/** The marketing-site shell (landing, about, how-it-works, contact, privacy) — a simpler header
 * and a real footer, as opposed to AppShell's logged-in app chrome. */
export function PublicShell({ children }: { children: ReactNode }) {
  const { loggedIn } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);

  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <header className="sticky top-0 z-40 border-b border-border bg-panel backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-[1400px] items-center gap-4 px-4 lg:px-8">
          <Link to="/" className="flex shrink-0 items-center" aria-label="Choropia home">
            <img src="/logo.png" alt="Choropia" className="h-7 w-auto dark:invert dark:opacity-90" />
          </Link>

          <nav aria-label="Main navigation" className="hidden items-center gap-6 lg:flex">
            {PUBLIC_LINKS.map((item) => (
              <NavLink key={item.to} to={item.to} className={({ isActive }) => cn("text-sm transition-colors", isActive ? "font-semibold text-primary" : "text-muted-foreground hover:text-primary")}>
                {item.label}
              </NavLink>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-2">
            <Button variant="icon" aria-label="Display settings" title="Display settings" onClick={() => setSettingsOpen(true)} className="size-9 p-0">
              <Settings size={16} />
            </Button>
            {loggedIn ? (
              <LinkButton to="/feed" className="hidden sm:inline-flex">
                Go to your feed
              </LinkButton>
            ) : (
              <>
                <LinkButton to="/login" variant="ghost" className="hidden sm:inline-flex">
                  Log in
                </LinkButton>
                <LinkButton to="/register" className="hidden sm:inline-flex">
                  Join Choropia
                </LinkButton>
              </>
            )}
            <Button
              variant="icon"
              className="size-9 p-0 lg:hidden"
              aria-label={mobileOpen ? "Close menu" : "Open menu"}
              aria-expanded={mobileOpen}
              onClick={() => setMobileOpen(!mobileOpen)}
            >
              {mobileOpen ? <X size={17} /> : <Menu size={17} />}
            </Button>
          </div>
        </div>

        {mobileOpen && (
          <nav aria-label="Mobile navigation" className="page-enter grid gap-1 border-t border-border px-5 py-4 lg:hidden">
            {PUBLIC_LINKS.map((item) => (
              <Link key={item.to} to={item.to} onClick={() => setMobileOpen(false)} className="py-2 text-sm">
                {item.label}
              </Link>
            ))}
            <Link to="/marketplace" onClick={() => setMobileOpen(false)} className="py-2 text-sm text-primary">
              Marketplace
            </Link>
            {loggedIn ? (
              <Link to="/feed" onClick={() => setMobileOpen(false)} className="py-2 text-sm font-semibold text-primary">
                Go to your feed
              </Link>
            ) : (
              <>
                <Link to="/login" onClick={() => setMobileOpen(false)} className="py-2 text-sm">
                  Log in
                </Link>
                <Link to="/register" onClick={() => setMobileOpen(false)} className="py-2 text-sm font-semibold text-primary">
                  Join Choropia
                </Link>
              </>
            )}
          </nav>
        )}
      </header>

      <main className="flex-1">{children}</main>

      <footer className="border-t border-border bg-panel">
        <div className="mx-auto grid max-w-[1400px] gap-10 px-5 py-14 md:grid-cols-[1fr_1fr] lg:px-8">
          <div>
            <Link to="/" className="font-display text-2xl font-semibold text-primary">
              Choropia<span className="text-success">.</span>
            </Link>
            <p className="mt-4 max-w-xs text-sm leading-6 text-muted-foreground">Good things. Real people. Closer to home.</p>
            <p className="mt-5 text-xs text-muted-foreground">Uyo, Akwa Ibom · Nigeria</p>
          </div>
          <nav aria-label="Footer" className="grid grid-cols-2 gap-x-6 gap-y-4 text-sm">
            {FOOTER_LINKS.map((item) => (
              <Link key={item.to} to={item.to} className="inline-flex items-center gap-2 text-muted-foreground transition-colors hover:text-primary">
                {item.label}
                <ArrowUpRight size={13} />
              </Link>
            ))}
            <Link to="/marketplace" className="text-muted-foreground transition-colors hover:text-primary">
              Explore marketplace
            </Link>
            <Link to="/merchants/apply" className="text-muted-foreground transition-colors hover:text-primary">
              Become a merchant
            </Link>
          </nav>
        </div>
        <div className="mx-auto flex max-w-[1400px] flex-wrap justify-between gap-3 border-t border-border px-5 py-5 text-xs text-muted-foreground lg:px-8">
          <span>© {new Date().getFullYear()} Choropia</span>
          <span>A little more local. A lot more human.</span>
        </div>
      </footer>

      <SettingsDrawer open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  );
}
