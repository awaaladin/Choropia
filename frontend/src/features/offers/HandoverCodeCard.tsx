import { useQuery, useQueryClient } from "@tanstack/react-query";
import { motion, useAnimationControls } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router";
import { Bike, Eye, EyeOff, KeyRound } from "lucide-react";
import { Button } from "@/components/Button";
import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import { haptic } from "./format";
import { InlineError } from "./InlineError";
import { useCalmMotion, usePress } from "./motion";

/** Buyer: the 6-digit code to give the seller (or rider) once they hold the item. Hidden until revealed. */
export function BuyerHandoverCode({ orderId }: { orderId: number }) {
  const calm = useCalmMotion();
  const press = usePress(calm);
  const [shown, setShown] = useState(false);
  const code = useQuery({ queryKey: ["handover-code", orderId], queryFn: () => api.handoverCode(orderId), staleTime: 60_000 });

  if (code.isPending) return <div className="mt-4 h-20 animate-pulse rounded-o-md bg-o-surface" aria-busy="true" aria-label="Loading your code" />;
  if (code.isError) {
    return (
      <p className="mt-4 rounded-o-md bg-o-surface p-3 text-sm text-o-muted">
        {(code.error as Error).message || "Your code couldn't be loaded."}{" "}
        <button type="button" onClick={() => code.refetch()} className="font-medium text-o-accent underline-offset-4 hover:underline">
          Try again
        </button>
      </p>
    );
  }
  if (code.data.used || !code.data.code) return null;
  const rider = code.data.entered_by === "rider";

  return (
    <div className="mt-4 rounded-o-md border border-o-hairline bg-o-surface p-4">
      <div className="flex items-center gap-2 text-sm font-medium text-o-text">
        {rider ? <Bike size={16} strokeWidth={1.75} aria-hidden="true" /> : <KeyRound size={16} strokeWidth={1.75} aria-hidden="true" />}
        Your handover code
      </div>
      <p className="mt-1 text-xs text-o-muted">
        Only tell {rider ? "the rider" : "the seller"} this code once you have the item and you're happy with it. It releases the money.
      </p>
      <div className="mt-3 flex items-center justify-between gap-3">
        <span className="font-mono text-2xl font-semibold tracking-[0.35em] tabular-nums text-o-text" aria-live="polite">
          {shown ? code.data.code : "••••••"}
          {shown && <span className="sr-only">. Digits: {code.data.code.split("").join(" ")}</span>}
        </span>
        <motion.button
          type="button"
          {...press}
          onClick={() => setShown((s) => !s)}
          aria-pressed={shown}
          className="inline-flex min-h-11 items-center gap-1.5 rounded-o-sm px-3 text-sm font-medium text-o-accent hover:bg-o-tide focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-o-accent"
        >
          {shown ? <EyeOff size={16} strokeWidth={1.75} aria-hidden="true" /> : <Eye size={16} strokeWidth={1.75} aria-hidden="true" />}
          {shown ? "Hide" : "Show code"}
        </motion.button>
      </div>
    </div>
  );
}

/** Seller (meet-up / seller delivers): type the buyer's code after handing over. The right code releases escrow. */
export function SellerHandoverEntry({ orderId, onReleased }: { orderId: number; onReleased: () => void }) {
  const calm = useCalmMotion();
  const shake = useAnimationControls();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [digits, setDigits] = useState<string[]>(Array(6).fill(""));
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [locked, setLocked] = useState(false);
  const refs = useRef<(HTMLInputElement | null)[]>([]);

  useEffect(() => {
    if (error && !calm) void shake.start({ x: [0, -8, 7, -4, 2, 0], transition: { duration: 0.38 } });
  }, [error, calm, shake]);

  const submit = async (code: string) => {
    setBusy(true);
    setError(null);
    try {
      await api.confirmHandover(orderId, code);
      haptic([10, 30, 20]);
      queryClient.invalidateQueries({ queryKey: ["orders"] });
      onReleased();
    } catch (e) {
      haptic([12, 40, 12]);
      setDigits(Array(6).fill(""));
      refs.current[0]?.focus();
      if (e instanceof ApiError && e.code === "code_locked") setLocked(true);
      setError(e instanceof ApiError ? e.message : "Couldn't check the code. Check your connection and try again.");
    } finally {
      setBusy(false);
    }
  };

  const setAt = (i: number, raw: string) => {
    const incoming = raw.replace(/\D/g, "");
    if (!incoming && raw !== "") return;
    const next = [...digits];
    if (incoming.length > 1) {
      // pasted the whole code
      incoming.slice(0, 6 - i).split("").forEach((d, k) => (next[i + k] = d));
    } else {
      next[i] = incoming;
    }
    setDigits(next);
    setError(null);
    const firstEmpty = next.findIndex((d) => !d);
    if (firstEmpty === -1) void submit(next.join(""));
    else if (incoming) refs.current[Math.min(firstEmpty, 5)]?.focus();
  };

  return (
    <div className="mt-4 rounded-o-md border border-o-hairline bg-o-surface p-4">
      <p className="text-sm font-medium text-o-text" id={`handover-${orderId}`}>
        Handed it over? Enter the buyer's code
      </p>
      <p className="mt-1 text-xs text-o-muted">The buyer sees a 6-digit code once they have the item. It releases your money.</p>
      <motion.div animate={shake} className="mt-3 flex gap-2" role="group" aria-labelledby={`handover-${orderId}`}>
        {digits.map((d, i) => (
          <input
            key={i}
            ref={(el) => {
              refs.current[i] = el;
            }}
            value={d}
            disabled={busy || locked}
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={6}
            aria-label={`Digit ${i + 1} of 6`}
            onChange={(e) => setAt(i, e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Backspace" && !digits[i] && i > 0) refs.current[i - 1]?.focus();
            }}
            className={cn(
              "h-12 w-full min-w-0 rounded-o-sm border bg-o-raised text-center font-mono text-xl font-semibold tabular-nums text-o-text",
              "focus:outline-none focus:ring-2 focus:ring-o-accent disabled:opacity-50",
              error ? "border-o-danger" : "border-o-hairline",
            )}
          />
        ))}
      </motion.div>
      <InlineError message={error} />
      {busy && (
        <p className="mt-2 text-sm text-o-muted" aria-live="polite">
          Checking the code…
        </p>
      )}
      {locked && (
        <Button variant="secondary" className="mt-3 min-h-11 w-full" onClick={() => navigate(`/orders/${orderId}`)}>
          Open the order
        </Button>
      )}
    </div>
  );
}
