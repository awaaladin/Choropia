/**
 * Real-logo loading screens (see styles.css for the keyframes).
 *  - "full": app boot and login/signup — anything that has to round-trip the backend before
 *    the next screen makes sense. The mark pulses with a reflection underneath it; "Choropia"
 *    emerges from its right edge (the mark drifts left so the pair stays centered as a unit),
 *    holds, and retreats back into the mark, on a loop.
 *  - "simple": ordinary in-app navigation — the mark alone, pulsing.
 */
export function BrandLoader({ variant = "simple" }: { variant?: "full" | "simple" }) {
  return (
    <div className={variant === "full" ? "brand-loading-full" : "brand-loading-simple"} role="status" aria-live="polite" aria-label="Loading Choropia">
      {variant === "full" ? (
        <div className="flex items-center justify-center">
          <div className="relative">
            <img src="/favicon-512.png" alt="" className="brand-mark size-16" />
            <div className="brand-mark-reflection-clip absolute inset-x-0 top-full">
              <img src="/favicon-512.png" alt="" aria-hidden className="brand-mark-reflection size-16" />
            </div>
          </div>
          <div className="brand-wordmark-track">
            <span className="brand-wordmark font-display text-lg font-semibold text-primary">Choropia</span>
          </div>
        </div>
      ) : (
        <img src="/favicon-512.png" alt="" className="brand-mark size-12" />
      )}
    </div>
  );
}
