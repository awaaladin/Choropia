import { motion } from "motion/react";
import { Check } from "lucide-react";
import { cn } from "@/lib/utils";
import { spring, useCalmMotion } from "./motion";

const STEPS = ["Offered", "Paid into escrow", "Handed over", "Released"] as const;

/** Where the deal is: 0 offered, 1 paid into escrow, 2 handed over, 3 released to the seller. */
export function OfferStatusTimeline({ step }: { step: 0 | 1 | 2 | 3 }) {
  const calm = useCalmMotion();
  return (
    <ol className="mt-4 flex items-start" aria-label="Progress">
      {STEPS.map((label, i) => {
        const done = i < step;
        const current = i === step;
        return (
          <li key={label} className="relative flex flex-1 flex-col items-center text-center" aria-current={current ? "step" : undefined}>
            {i > 0 && (
              <span className="absolute right-1/2 top-[9px] h-0.5 w-full -translate-y-1/2 bg-o-hairline" aria-hidden="true">
                <motion.span
                  className="block h-full origin-left bg-o-accent"
                  initial={false}
                  animate={{ scaleX: i <= step ? 1 : 0 }}
                  transition={calm ? { duration: 0 } : spring}
                />
              </span>
            )}
            <span
              className={cn(
                "relative z-10 grid size-[18px] place-items-center rounded-full border-2 transition-colors",
                done ? "border-o-accent bg-o-accent text-o-accent-fg" : current ? "border-o-accent bg-o-raised" : "border-o-hairline bg-o-raised",
              )}
              aria-hidden="true"
            >
              {done && <Check size={10} strokeWidth={3} />}
              {current && <span className="size-1.5 rounded-full bg-o-accent" />}
            </span>
            <span className={cn("mt-1.5 text-[11px] leading-tight", current ? "font-semibold text-o-text" : "text-o-muted")}>
              {label}
              <span className="sr-only">{done ? " (done)" : current ? " (now)" : ""}</span>
            </span>
          </li>
        );
      })}
    </ol>
  );
}
