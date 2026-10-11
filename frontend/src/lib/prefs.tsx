import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

export type Theme = "light" | "dark";
export type View = "editorial" | "grid";
export type Density = "comfortable" | "compact";
export type Motion = "full" | "reduced";

interface Prefs {
  theme: Theme;
  view: View;
  density: Density;
  motion: Motion;
}

interface PrefsContext extends Prefs {
  update: <K extends keyof Prefs>(key: K, value: Prefs[K]) => void;
  /** Stagger delay for the entrance animation of the nth item; none when motion is reduced. */
  stagger: (index: number) => { animationDelay: string } | undefined;
  /** True if the user has chosen a theme on this device (so an account preference shouldn't override it). */
  hasStoredChoice: boolean;
}

const KEY = "choropia-preferences";
const DEFAULTS: Prefs = { theme: "light", view: "editorial", density: "comfortable", motion: "full" };

function load(): { prefs: Prefs; stored: boolean } {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) return { prefs: { ...DEFAULTS, ...(JSON.parse(raw) as Partial<Prefs>) }, stored: true };
  } catch {
    localStorage.removeItem(KEY);
  }
  return { prefs: DEFAULTS, stored: false };
}

const Ctx = createContext<PrefsContext | null>(null);

export function PrefsProvider({ children }: { children: ReactNode }) {
  const [{ prefs: initial, stored }] = useState(load);
  const [prefs, setPrefs] = useState<Prefs>(initial);
  const [hasStoredChoice, setHasStoredChoice] = useState(stored);

  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle("dark", prefs.theme === "dark");
    root.dataset.motion = prefs.motion;
    root.dataset.density = prefs.density;
    if (hasStoredChoice) localStorage.setItem(KEY, JSON.stringify(prefs));
  }, [prefs, hasStoredChoice]);

  const update = useCallback<PrefsContext["update"]>((key, value) => {
    setHasStoredChoice(true);
    setPrefs((current) => ({ ...current, [key]: value }));
  }, []);

  const value = useMemo<PrefsContext>(
    () => ({
      ...prefs,
      update,
      hasStoredChoice,
      stagger: (index) => (prefs.motion === "full" ? { animationDelay: `${80 + index * 60}ms` } : undefined),
    }),
    [prefs, update, hasStoredChoice],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function usePrefs() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("usePrefs must be used inside PrefsProvider");
  return ctx;
}
