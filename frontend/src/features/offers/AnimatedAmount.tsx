import { animate, useMotionValue, useMotionValueEvent } from "motion/react";
import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import { formatKobo, spokenKobo } from "./format";
import { useCalmMotion } from "./motion";

/** A naira amount (from kobo) that counts to its new value instead of jumping. Tabular numerals so digits don't shift.
 * Screen readers get the final value only, never the in-between numbers. */
export function AnimatedAmount({ kobo, className }: { kobo: number; className?: string }) {
  const calm = useCalmMotion();
  const value = useMotionValue(kobo);
  const [shown, setShown] = useState(kobo);

  useMotionValueEvent(value, "change", (latest) => setShown(Math.round(latest)));

  useEffect(() => {
    if (calm) {
      value.set(kobo);
      setShown(kobo);
      return;
    }
    const controls = animate(value, kobo, { type: "spring", stiffness: 160, damping: 26, restDelta: 0.5 });
    return () => controls.stop();
  }, [kobo, calm, value]);

  return (
    <span className={cn("tabular-nums", className)}>
      <span aria-hidden="true">{formatKobo(shown)}</span>
      <span className="sr-only">{spokenKobo(kobo)}</span>
    </span>
  );
}
