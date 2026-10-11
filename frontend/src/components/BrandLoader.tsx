/**
 * Real-logo loading screens (see styles.css for the keyframes).
 *  - "full": app boot and login/signup — anything that has to round-trip the backend before
 *    the next screen makes sense. The mark pulses with a reflection; "Choropia" slides out
 *    from the left, holds, and retreats back the way it came, on a loop.
 *  - "simple": ordinary in-app navigation — the mark alone, pulsing.
 */
export function BrandLoader({ variant = "simple" }: { variant?: "full" | "simple" }) {
  return (
    <div className={variant === "full" ? "brand-loading-full" : "brand-loading-simple"} role="status" aria-live="polite" aria-label="Loading Choropia">
      {variant === "full" ? (
        <div className="flex flex-col items-center gap-4">
          <div className="flex flex-col items-center">
            <img src="/favicon-512.png" alt="" className="brand-mark size-16" />
            <img src="/favicon-512.png" alt="" aria-hidden className="brand-mark brand-mark-reflection size-16" />
          </div>
          <div className="h-6 w-28 overflow-hidden text-center">
            <span className="brand-wordmark inline-block font-display text-lg font-semibold text-primary">Choropia</span>
          </div>
        </div>
      ) : (
        <img src="/favicon-512.png" alt="" className="brand-mark size-12" />
      )}
    </div>
  );
}
