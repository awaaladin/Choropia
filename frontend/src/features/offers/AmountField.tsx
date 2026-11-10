import { AnimatePresence, motion } from "motion/react";
import { forwardRef, useId } from "react";
import { cn } from "@/lib/utils";
import { discountPercent, formatKobo, koboToInput, parseNairaToKobo } from "./format";
import { snappy, fade, useCalmMotion } from "./motion";

/**
 * The offer amount. ₦ prefix, grouping as you type, tabular numerals, the listed price struck through beside it and a
 * "% off" chip when the offer is lower. The value handed back is kobo (or null while what's typed isn't an amount).
 */
export const AmountField = forwardRef<
  HTMLInputElement,
  {
    text: string;
    onTextChange: (text: string) => void;
    listedKobo: number;
    maxKobo: number;
    errorId?: string;
    invalid?: boolean;
  }
>(function AmountField({ text, onTextChange, listedKobo, maxKobo, errorId, invalid }, ref) {
  const calm = useCalmMotion();
  const id = useId();
  const hintId = useId();
  const kobo = parseNairaToKobo(text);
  const off = kobo !== null ? discountPercent(kobo, listedKobo) : 0;
  const tooHigh = kobo !== null && kobo > maxKobo;

  const onChange = (raw: string) => {
    const clean = raw.replace(/[^\d.]/g, "");
    const [whole = "", ...rest] = clean.split(".");
    const frac = rest.join("").slice(0, 2);
    const grouped = whole ? Number(whole.slice(0, 11)).toLocaleString("en-NG") : "";
    onTextChange(clean.includes(".") ? `${grouped}.${frac}` : grouped);
  };

  return (
    <div>
      <label htmlFor={id} className="text-sm font-medium text-o-text">
        Your price
      </label>
      <div
        className={cn(
          "mt-1.5 flex items-center gap-2 rounded-o-md border bg-o-raised px-4 py-3 transition-colors focus-within:ring-2 focus-within:ring-o-accent",
          invalid || tooHigh ? "border-o-danger" : "border-o-hairline",
        )}
      >
        <span className="font-display text-2xl font-semibold text-o-muted" aria-hidden="true">
          ₦
        </span>
        <input
          ref={ref}
          id={id}
          inputMode="decimal"
          autoComplete="off"
          enterKeyHint="next"
          value={text}
          onChange={(e) => onChange(e.target.value)}
          aria-invalid={invalid || tooHigh || undefined}
          aria-describedby={[hintId, errorId].filter(Boolean).join(" ")}
          placeholder={koboToInput(listedKobo)}
          className="min-w-0 flex-1 bg-transparent font-display text-2xl font-semibold tabular-nums text-o-text outline-none placeholder:text-o-muted/50"
        />
        <AnimatePresence initial={false}>
          {off > 0 && !tooHigh && (
            <motion.span
              key="off"
              className="shrink-0 rounded-full bg-o-tide px-2.5 py-1 text-xs font-semibold tabular-nums text-o-tide-fg"
              initial={calm ? { opacity: 0 } : { opacity: 0, scale: 0.85 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: calm ? 1 : 0.85 }}
              transition={calm ? fade : snappy}
            >
              {off}% off
            </motion.span>
          )}
        </AnimatePresence>
      </div>
      <p id={hintId} className="mt-1.5 text-sm text-o-muted">
        Listed at <s className="tabular-nums">{formatKobo(listedKobo)}</s>
        {tooHigh ? (
          <span className="text-o-danger"> · An offer can't be higher than {formatKobo(maxKobo)}.</span>
        ) : (
          <span> · You can lower the price, never raise it.</span>
        )}
      </p>
    </div>
  );
});
