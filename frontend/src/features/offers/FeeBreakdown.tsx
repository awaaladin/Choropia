import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { motion } from "motion/react";
import { useEffect, useState } from "react";
import { BadgeCheck } from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { AnimatedAmount } from "./AnimatedAmount";
import { fade, spring, useCalmMotion } from "./motion";

function useDebounced<T>(value: T, ms: number) {
  const [current, setCurrent] = useState(value);
  useEffect(() => {
    const t = window.setTimeout(() => setCurrent(value), ms);
    return () => window.clearTimeout(t);
  }, [value, ms]);
  return current;
}

/**
 * Seller only: offer amount, Choropia's fee, and "You receive". The numbers come from the server's fee preview, the same
 * function that locks the fee when the offer is made. The buyer never sees this.
 */
export function FeeBreakdown({ amountKobo, verified }: { amountKobo: number | null; verified: boolean }) {
  const calm = useCalmMotion();
  const debounced = useDebounced(amountKobo, 250);
  const preview = useQuery({
    queryKey: ["fee-preview", debounced, verified],
    queryFn: () => api.feePreview(debounced as number, verified),
    enabled: debounced !== null && debounced > 0,
    placeholderData: keepPreviousData,
    staleTime: 60_000,
  });

  if (amountKobo === null || amountKobo <= 0) return null;

  if (preview.isPending) {
    return (
      <div className="space-y-2.5 rounded-o-md bg-o-surface p-4" aria-busy="true" aria-label="Working out your fee">
        {[0, 1, 2].map((i) => (
          <div key={i} className="flex justify-between">
            <span className="h-4 w-24 animate-pulse rounded bg-o-hairline" />
            <span className="h-4 w-20 animate-pulse rounded bg-o-hairline" />
          </div>
        ))}
      </div>
    );
  }
  if (preview.isError || !preview.data) {
    return (
      <p className="rounded-o-md bg-o-surface p-4 text-sm text-o-muted">
        {navigator.onLine ? "Couldn't load the fee just now." : "You're offline, so the fee can't be shown."} It's worked out
        when you send the offer.
      </p>
    );
  }

  const { fee_kobo: fee, seller_net_kobo: net } = preview.data;
  const rows = [
    { label: "Offer price", kobo: amountKobo, sign: "" },
    { label: "Choropia fee", kobo: fee, sign: "−", chip: verified },
  ];

  return (
    <section aria-label="What you receive" className={cn("rounded-o-md bg-o-surface p-4", preview.isFetching && "opacity-80")}>
      <dl className="space-y-2 text-sm">
        {rows.map((row, i) => (
          <motion.div
            key={row.label}
            className="flex items-center justify-between gap-3"
            initial={calm ? { opacity: 0 } : { opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={calm ? fade : { ...spring, delay: i * 0.04 }}
          >
            <dt className="flex items-center gap-1.5 text-o-muted">
              {row.label}
              {row.chip && (
                <span className="inline-flex items-center gap-1 rounded-full bg-o-tide px-2 py-0.5 text-[11px] font-medium text-o-tide-fg">
                  <BadgeCheck size={12} strokeWidth={1.75} aria-hidden="true" /> Verified rate
                </span>
              )}
            </dt>
            <dd className="text-o-text">
              {row.sign && <span aria-hidden="true">{row.sign} </span>}
              <AnimatedAmount kobo={row.kobo} />
            </dd>
          </motion.div>
        ))}
        <motion.div
          className="mt-1 flex items-center justify-between gap-3 border-t border-o-hairline pt-3"
          initial={calm ? { opacity: 0 } : { opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={calm ? fade : { ...spring, delay: 0.08 }}
        >
          <dt className="font-semibold text-o-text">You receive</dt>
          <dd className="font-display text-lg font-semibold text-o-text">
            <AnimatedAmount kobo={net} />
          </dd>
        </motion.div>
      </dl>
      <p className="sr-only" aria-live="polite">
        You receive {(net / 100).toLocaleString("en-NG")} naira after a {(fee / 100).toLocaleString("en-NG")} naira fee.
      </p>
    </section>
  );
}
