import { motion, useAnimationControls } from "motion/react";
import { useEffect, useId, useRef, useState } from "react";
import { Delete, Lock, LockKeyhole } from "lucide-react";
import { cn } from "@/lib/utils";
import { clock, haptic } from "./format";
import { snappy, useCalmMotion, usePress } from "./motion";

const KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "", "0", "del"] as const;

/**
 * PIN entry: dots plus a keypad. Physical keyboards and screen readers use a real (visually hidden) input, so the PIN
 * works without the keypad. `errorTick` changes on every wrong PIN: the dots shake (or, with reduced motion, turn red).
 * `lockedFor` (seconds) disables entry and shows the countdown.
 */
export function PinPad({
  length = 4,
  value,
  onChange,
  onComplete,
  label,
  errorTick = 0,
  error,
  disabled,
  lockedFor,
}: {
  length?: number;
  value: string;
  onChange: (value: string) => void;
  onComplete?: (value: string) => void;
  label: string;
  errorTick?: number;
  error?: boolean;
  disabled?: boolean;
  lockedFor?: number | null;
}) {
  const calm = useCalmMotion();
  const press = usePress(calm);
  const shake = useAnimationControls();
  const inputRef = useRef<HTMLInputElement>(null);
  const inputId = useId();
  const statusId = useId();
  const locked = Boolean(lockedFor && lockedFor > 0);
  const off = disabled || locked;

  useEffect(() => {
    if (!errorTick) return;
    haptic([12, 40, 12]);
    if (!calm) void shake.start({ x: [0, -10, 9, -6, 4, -2, 0], transition: { duration: 0.42, ease: "easeOut" } });
  }, [errorTick, calm, shake]);

  const set = (next: string) => {
    const clean = next.replace(/\D/g, "").slice(0, length);
    if (clean === value) return;
    if (clean.length > value.length) haptic(6);
    onChange(clean);
    if (clean.length === length) onComplete?.(clean);
  };

  const tap = (key: (typeof KEYS)[number]) => {
    if (off || !key) return;
    set(key === "del" ? value.slice(0, -1) : value + key);
  };

  return (
    <div className="flex flex-col items-center">
      <label htmlFor={inputId} className="text-sm font-medium text-o-text">
        {label}
      </label>
      {/* Real input for keyboards, password managers off, and screen readers. */}
      <input
        ref={inputRef}
        id={inputId}
        type="password"
        inputMode="numeric"
        autoComplete="off"
        pattern="[0-9]*"
        maxLength={length}
        value={value}
        disabled={off}
        onChange={(e) => set(e.target.value)}
        aria-describedby={statusId}
        aria-invalid={error || undefined}
        className="sr-only"
      />
      <motion.div
        animate={shake}
        className="mt-4 flex gap-4"
        onClick={() => inputRef.current?.focus()}
        aria-hidden="true"
      >
        {Array.from({ length }, (_, i) => {
          const filled = i < value.length;
          return (
            <motion.span
              key={i}
              className={cn(
                "size-3.5 rounded-full border-2 transition-colors",
                error ? "border-o-danger" : "border-o-accent",
                filled && (error ? "bg-o-danger" : "bg-o-accent"),
              )}
              animate={filled && !calm ? { scale: [1, 1.35, 1] } : { scale: 1 }}
              transition={snappy}
            />
          );
        })}
      </motion.div>
      <p id={statusId} className="sr-only" aria-live="polite">
        {locked ? `PIN locked. Try again in ${clock(lockedFor ?? 0)}.` : `${value.length} of ${length} digits entered.`}
      </p>

      {locked ? (
        <div className="mt-6 flex flex-col items-center gap-2 rounded-o-md bg-o-caution-bg px-5 py-4 text-center text-o-caution">
          <LockKeyhole size={22} strokeWidth={1.75} aria-hidden="true" />
          <p className="text-sm font-medium">Too many wrong PINs</p>
          <p className="text-sm">
            Try again in <span className="font-semibold tabular-nums">{clock(lockedFor ?? 0)}</span>
          </p>
        </div>
      ) : (
        <div className="mt-6 grid w-full max-w-[17rem] grid-cols-3 gap-3" role="group" aria-label="PIN keypad">
          {KEYS.map((key, i) =>
            key === "" ? (
              <span key={i} />
            ) : (
              <motion.button
                key={i}
                type="button"
                {...press}
                disabled={off}
                onClick={() => tap(key)}
                aria-label={key === "del" ? "Delete last digit" : key}
                className={cn(
                  "grid h-14 place-items-center rounded-o-md text-xl font-medium tabular-nums text-o-text transition-colors",
                  "bg-o-surface hover:bg-o-tide focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-o-accent disabled:opacity-40",
                  key === "del" && "bg-transparent text-o-muted",
                )}
              >
                {key === "del" ? <Delete size={22} strokeWidth={1.75} aria-hidden="true" /> : key}
              </motion.button>
            ),
          )}
        </div>
      )}
      {error && calm && (
        <span className="mt-3 inline-flex items-center gap-1 text-sm text-o-danger" aria-hidden="true">
          <Lock size={14} strokeWidth={1.75} /> Not right
        </span>
      )}
    </div>
  );
}

/** Counts down from `seconds` once per second (for the PIN lock). */
export function useCountdown(seconds: number | null) {
  const [left, setLeft] = useStateFrom(seconds);
  useEffect(() => {
    if (!left || left <= 0) return;
    const t = window.setInterval(() => setLeft((s) => (s && s > 0 ? s - 1 : 0)), 1000);
    return () => window.clearInterval(t);
  }, [left !== null && left > 0, setLeft]); // eslint-disable-line react-hooks/exhaustive-deps
  return left;
}

function useStateFrom(initial: number | null) {
  const [value, setValue] = useState<number | null>(initial);
  const [seen, setSeen] = useState(initial);
  if (initial !== seen) {
    setSeen(initial);
    setValue(initial);
  }
  return [value, setValue] as const;
}
