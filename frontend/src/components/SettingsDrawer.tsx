import { Check, Grid2X2, LayoutList, Settings, SlidersHorizontal, SunMoon, X } from "lucide-react";
import { useEffect, type ReactNode } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { usePrefs } from "@/lib/prefs";
import { Segmented } from "./ui";

function Group({ icon, label, children }: { icon: ReactNode; label: string; children: ReactNode }) {
  return (
    <section>
      <div className="mb-3 flex items-center gap-2 text-sm font-semibold">
        {icon}
        {label}
      </div>
      {children}
    </section>
  );
}

export function SettingsDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const prefs = usePrefs();
  const { loggedIn } = useAuth();

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const setTheme = (theme: "light" | "dark") => {
    prefs.update("theme", theme);
    // Keep the account's saved preference in step so other devices open the same way.
    if (loggedIn) api.updateProfile({ profile: { theme_preference: theme } }).catch(() => {});
  };

  return (
    <div className="animate-fade-in fixed inset-0 z-50 bg-foreground/20 backdrop-blur-sm" onMouseDown={onClose}>
      <aside
        role="dialog"
        aria-modal="true"
        aria-label="Display settings"
        className="animate-slide-in-right ml-auto flex h-full w-full max-w-sm flex-col border-l border-border bg-background p-5 shadow-2xl"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-lg font-semibold">Your feed, your way</h2>
            <p className="mt-1 text-sm text-muted-foreground">Changes apply instantly and stay saved.</p>
          </div>
          <button
            onClick={onClose}
            aria-label="Close settings"
            className="grid size-9 place-items-center rounded-md border border-border bg-panel text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
          >
            <X size={16} />
          </button>
        </div>

        <div className="mt-8 space-y-7">
          <Group icon={<SunMoon size={16} />} label="Appearance">
            <Segmented options={["light", "dark"] as const} value={prefs.theme} onChange={setTheme} />
          </Group>
          <Group icon={prefs.view === "editorial" ? <LayoutList size={16} /> : <Grid2X2 size={16} />} label="Feed layout">
            <Segmented options={["editorial", "grid"] as const} value={prefs.view} onChange={(v) => prefs.update("view", v)} />
          </Group>
          <Group icon={<SlidersHorizontal size={16} />} label="Content density">
            <Segmented options={["comfortable", "compact"] as const} value={prefs.density} onChange={(v) => prefs.update("density", v)} />
          </Group>
          <Group icon={<Settings size={16} />} label="Motion">
            <Segmented options={["full", "reduced"] as const} value={prefs.motion} onChange={(v) => prefs.update("motion", v)} />
          </Group>
        </div>

        <div className="panel mt-auto p-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-success">
            <Check size={15} /> Preferences saved
          </div>
          <p className="mt-1 text-xs text-muted-foreground">Your interface will open this way next time.</p>
        </div>
      </aside>
    </div>
  );
}
