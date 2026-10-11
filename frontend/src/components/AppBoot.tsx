import { useEffect, useState, type ReactNode } from "react";
import { BrandLoader } from "./BrandLoader";

const MIN_VISIBLE_MS = 2400;

/** Full brand splash from first paint until the page (and a minimum dwell time, so it never
 * just flashes) is ready — this is the "hard refresh" moment. */
export function AppBoot({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const start = Date.now();
    const finish = () => setTimeout(() => setReady(true), Math.max(0, MIN_VISIBLE_MS - (Date.now() - start)));
    if (document.readyState === "complete") finish();
    else {
      window.addEventListener("load", finish, { once: true });
      return () => window.removeEventListener("load", finish);
    }
  }, []);

  return (
    <>
      {!ready && <BrandLoader variant="full" />}
      {children}
    </>
  );
}
