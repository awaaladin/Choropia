import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Ban, CircleAlert, CircleCheck, CircleX, Clock3, Hourglass, Loader2, RefreshCcw, Scale, Undo2 } from "lucide-react";
import { Link } from "@/components/AppLink";
import type { ChatOffer } from "@/lib/types";
import { cn } from "@/lib/utils";
import { AnimatedAmount } from "./AnimatedAmount";
import { CountdownChip } from "./CountdownChip";
import { DELIVERY } from "./DeliveryMethodPicker";
import { discountPercent, formatKobo } from "./format";
import { BuyerHandoverCode, SellerHandoverEntry } from "./HandoverCodeCard";
import { fade, spring, useCalmMotion, usePress } from "./motion";
import { OfferStatusTimeline } from "./OfferStatusTimeline";
import { Padlock } from "./Padlock";

export type OfferCardState =
  | "pending"
  | "payment_failed"
  | "processing"
  | "held"
  | "handed_over"
  | "released"
  | "declined"
  | "cancelled"
  | "expired"
  | "superseded"
  | "refund_pending"
  | "refunded"
  | "disputed";

/** One visual state for everything the offer and its order can be. */
export function offerCardState(offer: ChatOffer, now = Date.now()): OfferCardState {
  const stage = offer.order_stage;
  if (stage === "refund_pending") return "refund_pending";
  if (stage === "refunded") return "refunded";
  if (stage === "disputed") return "disputed";
  switch (offer.status) {
    case "pending": {
      const skew = Date.parse(offer.server_now) - Date.now();
      if (Date.parse(offer.expires_at) <= now + skew) return "expired";
      return offer.last_payment_failed ? "payment_failed" : "pending";
    }
    case "payment_processing":
      return "processing";
    case "paid":
      return stage === "released" ? "released" : stage === "handed_over" ? "handed_over" : "held";
    default:
      return offer.status;
  }
}

type Tone = "neutral" | "tide" | "ok" | "caution" | "danger" | "closed";

const META: Record<OfferCardState, { label: string; tone: Tone; icon?: ReactNode }> = {
  pending: { label: "Offer", tone: "neutral" },
  payment_failed: { label: "Payment didn't go through", tone: "danger", icon: <CircleAlert size={14} strokeWidth={1.75} /> },
  processing: { label: "Payment processing", tone: "tide", icon: <Loader2 size={14} strokeWidth={1.75} className="animate-spin" /> },
  held: { label: "Paid · held in escrow", tone: "tide" },
  handed_over: { label: "Handed over", tone: "tide", icon: <Hourglass size={14} strokeWidth={1.75} /> },
  released: { label: "Completed", tone: "ok", icon: <CircleCheck size={14} strokeWidth={1.75} /> },
  declined: { label: "Declined", tone: "closed", icon: <CircleX size={14} strokeWidth={1.75} /> },
  cancelled: { label: "Cancelled", tone: "closed", icon: <Ban size={14} strokeWidth={1.75} /> },
  expired: { label: "Expired", tone: "closed", icon: <Clock3 size={14} strokeWidth={1.75} /> },
  superseded: { label: "Replaced by a newer offer", tone: "closed", icon: <RefreshCcw size={14} strokeWidth={1.75} /> },
  refund_pending: { label: "Refund on its way", tone: "caution", icon: <Undo2 size={14} strokeWidth={1.75} /> },
  refunded: { label: "Refunded", tone: "closed", icon: <Undo2 size={14} strokeWidth={1.75} /> },
  disputed: { label: "Under review", tone: "caution", icon: <Scale size={14} strokeWidth={1.75} /> },
};

const TONE_CHIP: Record<Tone, string> = {
  neutral: "bg-o-surface text-o-muted",
  tide: "bg-o-tide text-o-tide-fg",
  ok: "bg-o-ok-bg text-o-ok",
  caution: "bg-o-caution-bg text-o-caution",
  danger: "bg-o-danger-bg text-o-danger",
  closed: "bg-o-surface text-o-muted",
};

/** Sentence announced to screen readers when the card changes state (and what each person should do next). */
function announcement(state: OfferCardState, role: "buyer" | "seller" | null, amount: string) {
  const seller = role === "seller";
  const lines: Record<OfferCardState, string> = {
    pending: seller ? `Offer of ${amount} sent.` : `New offer: ${amount}.`,
    payment_failed: "The payment didn't go through. The offer is open again.",
    processing: seller ? "The buyer is paying." : "Payment in progress.",
    held: seller ? `Paid. ${amount} is held in escrow. Hand the item over.` : `Paid. ${amount} is held safely in escrow.`,
    handed_over: "Marked as handed over.",
    released: seller ? "The buyer has the item. Your payout is on its way." : "Done. The seller has been paid.",
    declined: "The offer was declined.",
    cancelled: "The offer was cancelled.",
    expired: "The offer has expired.",
    superseded: "This offer was replaced by a newer one.",
    refund_pending: "The payment is being refunded.",
    refunded: "The payment was refunded.",
    disputed: "This order is under review by Choropia.",
  };
  return lines[state];
}

export interface OfferCardActions {
  onPay: (offer: ChatOffer) => void;
  onDecline: (offer: ChatOffer) => Promise<void> | void;
  onCancel: (offer: ChatOffer) => Promise<void> | void;
  onCheckPayment: (offer: ChatOffer) => Promise<void> | void;
  onReleased: (offer: ChatOffer) => void;
}

/** The offer as a card in the chat, rendered from the live offer (never a stale copy). */
export function OfferCard({ offer, actions }: { offer: ChatOffer; actions: OfferCardActions }) {
  const calm = useCalmMotion();
  const press = usePress(calm);
  const [, forceTick] = useState(0);
  const state = offerCardState(offer);
  const role = offer.viewer_role;
  const meta = META[state];
  const previous = useRef<OfferCardState>(state);
  const [justLocked, setJustLocked] = useState(false);
  const [said, setSaid] = useState("");
  const [confirming, setConfirming] = useState<"decline" | "cancel" | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    if (previous.current !== state) {
      if (state === "held" && (previous.current === "processing" || previous.current === "pending" || previous.current === "payment_failed")) {
        setJustLocked(true);
      }
      setSaid(announcement(state, role, formatKobo(offer.amount_kobo)));
      previous.current = state;
      setConfirming(null);
    }
  }, [state, role, offer.amount_kobo]);

  const closed = meta.tone === "closed";
  const escrow = state === "held" || state === "handed_over" || state === "processing";
  const off = discountPercent(offer.amount_kobo, offer.listing_price_kobo);
  const timelineStep = (state === "pending" || state === "payment_failed" || state === "processing"
    ? 0
    : state === "held"
      ? 1
      : state === "handed_over"
        ? 2
        : 3) as 0 | 1 | 2 | 3;
  const showTimeline = ["pending", "payment_failed", "processing", "held", "handed_over", "released"].includes(state);
  const riderOrder = offer.delivery_method === "rider";

  const run = async (key: string, fn: () => Promise<void> | void) => {
    setBusy(key);
    try {
      await fn();
    } finally {
      setBusy(null);
      setConfirming(null);
    }
  };

  return (
    <motion.article
      layout={!calm}
      transition={spring}
      aria-label={`Offer: ${formatKobo(offer.amount_kobo)} for ${offer.listing.title}. ${meta.label}.`}
      className={cn(
        "w-[min(22rem,80vw)] overflow-hidden rounded-o-lg border text-o-text shadow-o-card transition-colors duration-300",
        escrow ? "border-o-tide-fg/20 bg-o-tide" : "border-o-hairline bg-o-raised",
        closed && "opacity-80",
      )}
    >
      <p className="sr-only" aria-live="polite" aria-atomic="true">
        {said}
      </p>

      <motion.div layout={!calm ? "position" : false} className="flex gap-3 p-4">
        {offer.listing.photo ? (
          <img src={offer.listing.photo} alt="" className="size-14 shrink-0 rounded-o-sm object-cover" />
        ) : (
          <div className="size-14 shrink-0 rounded-o-sm bg-o-surface" aria-hidden="true" />
        )}
        <div className="min-w-0 flex-1">
          <p className="truncate text-xs text-o-muted">{offer.listing.title}</p>
          <p className={cn("mt-0.5 font-display text-2xl font-semibold tracking-tight", closed && "text-o-muted line-through decoration-1")}>
            <AnimatedAmount kobo={offer.amount_kobo} />
          </p>
          {off > 0 && (
            <p className="text-xs text-o-muted">
              <s className="tabular-nums">{formatKobo(offer.listing_price_kobo)}</s> · {off}% off
            </p>
          )}
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1.5">
          <AnimatePresence mode="popLayout" initial={false}>
            <motion.span
              key={state}
              className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium", TONE_CHIP[meta.tone])}
              initial={calm ? { opacity: 0 } : { opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={calm ? { opacity: 0 } : { opacity: 0, scale: 0.9 }}
              transition={calm ? fade : spring}
            >
              {meta.icon && <span aria-hidden="true">{meta.icon}</span>}
              {meta.label}
            </motion.span>
          </AnimatePresence>
          {(state === "pending" || state === "payment_failed") && (
            <CountdownChip expiresAt={offer.expires_at} serverNow={offer.server_now} onExpire={() => forceTick((t) => t + 1)} />
          )}
          {(state === "held" || state === "handed_over" || state === "released") && (
            <span className={state === "released" ? "text-o-ok" : "text-o-tide-fg"} title="Money held in escrow">
              <Padlock locked play={justLocked} size={26} />
            </span>
          )}
        </div>
      </motion.div>

      <div className="px-4 pb-4">
        {offer.note && <p className="mb-3 whitespace-pre-wrap rounded-o-sm bg-o-surface/70 px-3 py-2 text-sm">{offer.note}</p>}

        {/* What's on offer, then where it stands. */}
        <p className="text-xs text-o-muted">
          {offer.delivery_method
            ? `Handover: ${DELIVERY[offer.delivery_method].label}`
            : `Handover: ${offer.allowed_delivery_methods.map((m) => DELIVERY[m].label).join(" · ")}`}
        </p>

        {role === "seller" && offer.seller_net_kobo !== undefined && !closed && state !== "refund_pending" && (
          <p className="mt-1 text-xs text-o-muted">
            You receive <span className="font-semibold tabular-nums text-o-text">{formatKobo(offer.seller_net_kobo)}</span> after the
            Choropia fee
          </p>
        )}

        {showTimeline && <OfferStatusTimeline step={timelineStep} />}

        {/* State-specific guidance */}
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={state + (confirming ?? "")}
            initial={calm ? { opacity: 0 } : { opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={calm ? fade : spring}
          >
            {state === "payment_failed" && (
              <p className="mt-3 text-sm text-o-danger">
                {role === "buyer" ? "Nothing was taken. You can try again." : "The buyer's payment failed. The offer is still open."}
              </p>
            )}
            {state === "processing" && role === "seller" && <p className="mt-3 text-sm text-o-muted">The buyer is paying now. This updates by itself.</p>}
            {state === "held" && role === "seller" && !riderOrder && offer.order_id && (
              <SellerHandoverEntry orderId={offer.order_id} onReleased={() => actions.onReleased(offer)} />
            )}
            {state === "held" && role === "seller" && riderOrder && (
              <p className="mt-3 text-sm text-o-muted">A Choropia rider will pick it up. They take the buyer's code at delivery.</p>
            )}
            {(state === "held" || state === "handed_over") && role === "buyer" && offer.order_id && <BuyerHandoverCode orderId={offer.order_id} />}
            {state === "released" && (
              <p className="mt-3 text-sm text-o-ok">
                {role === "seller" ? "The buyer has the item. Your payout is being sent." : "All done. The seller has been paid."}
              </p>
            )}
            {state === "refund_pending" && (
              <p className="mt-3 text-sm text-o-caution">
                {role === "buyer" ? "This payment couldn't be used, so it's being refunded to you automatically." : "The buyer's payment is being refunded."}
              </p>
            )}
            {state === "disputed" && <p className="mt-3 text-sm text-o-caution">Choropia is reviewing this order. The money stays safe in escrow.</p>}
          </motion.div>
        </AnimatePresence>

        {/* Actions */}
        {role === "buyer" && (state === "pending" || state === "payment_failed") && (
          <div className="mt-4 flex gap-2">
            {confirming === "decline" ? (
              <>
                <motion.button {...press} type="button" onClick={() => run("decline", () => actions.onDecline(offer))} disabled={busy !== null}
                  className="min-h-11 flex-1 rounded-o-sm bg-o-danger-bg px-3 text-sm font-semibold text-o-danger focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-o-accent">
                  {busy === "decline" ? "Declining…" : "Yes, decline"}
                </motion.button>
                <motion.button {...press} type="button" onClick={() => setConfirming(null)}
                  className="min-h-11 rounded-o-sm px-3 text-sm font-medium text-o-muted hover:bg-o-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-o-accent">
                  Keep it
                </motion.button>
              </>
            ) : (
              <>
                <motion.button {...press} type="button" onClick={() => actions.onPay(offer)}
                  className="min-h-11 flex-1 rounded-o-sm bg-o-accent px-3 text-sm font-semibold text-o-accent-fg shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-o-accent focus-visible:ring-offset-2">
                  Pay {formatKobo(offer.amount_kobo)}
                </motion.button>
                <motion.button {...press} type="button" onClick={() => setConfirming("decline")}
                  className="min-h-11 rounded-o-sm px-3 text-sm font-medium text-o-muted hover:bg-o-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-o-accent">
                  Decline
                </motion.button>
              </>
            )}
          </div>
        )}

        {role === "buyer" && state === "processing" && (
          <div className="mt-4 flex gap-2">
            <motion.button {...press} type="button" onClick={() => actions.onPay(offer)}
              className="min-h-11 flex-1 rounded-o-sm bg-o-accent px-3 text-sm font-semibold text-o-accent-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-o-accent focus-visible:ring-offset-2">
              Continue payment
            </motion.button>
            <motion.button {...press} type="button" disabled={busy !== null} onClick={() => run("check", () => actions.onCheckPayment(offer))}
              className="min-h-11 rounded-o-sm px-3 text-sm font-medium text-o-accent hover:bg-o-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-o-accent">
              {busy === "check" ? "Checking…" : "I've paid"}
            </motion.button>
          </div>
        )}

        {role === "seller" && (state === "pending" || state === "payment_failed") && (
          <div className="mt-4">
            {confirming === "cancel" ? (
              <div className="flex gap-2">
                <motion.button {...press} type="button" disabled={busy !== null} onClick={() => run("cancel", () => actions.onCancel(offer))}
                  className="min-h-11 flex-1 rounded-o-sm bg-o-danger-bg px-3 text-sm font-semibold text-o-danger focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-o-accent">
                  {busy === "cancel" ? "Cancelling…" : "Yes, cancel offer"}
                </motion.button>
                <motion.button {...press} type="button" onClick={() => setConfirming(null)}
                  className="min-h-11 rounded-o-sm px-3 text-sm font-medium text-o-muted hover:bg-o-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-o-accent">
                  Keep it
                </motion.button>
              </div>
            ) : (
              <motion.button {...press} type="button" onClick={() => setConfirming("cancel")}
                className="min-h-11 rounded-o-sm px-3 text-sm font-medium text-o-muted hover:bg-o-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-o-accent">
                Cancel offer
              </motion.button>
            )}
          </div>
        )}

        {offer.order_id && !["pending", "payment_failed"].includes(state) && (
          <Link to={`/orders/${offer.order_id}`} className="mt-3 inline-flex min-h-11 items-center text-sm font-medium text-o-accent underline-offset-4 hover:underline">
            View order #{offer.order_id}
          </Link>
        )}
      </div>
    </motion.article>
  );
}

/** Placeholder while an offer card's data is loading. */
export function OfferCardSkeleton() {
  return (
    <div className="w-[min(22rem,80vw)] rounded-o-lg border border-o-hairline bg-o-raised p-4" aria-busy="true" aria-label="Loading offer">
      <div className="flex gap-3">
        <div className="size-14 animate-pulse rounded-o-sm bg-o-surface" />
        <div className="flex-1 space-y-2">
          <div className="h-3 w-1/2 animate-pulse rounded bg-o-surface" />
          <div className="h-6 w-2/3 animate-pulse rounded bg-o-surface" />
        </div>
      </div>
      <div className="mt-4 h-11 animate-pulse rounded-o-sm bg-o-surface" />
    </div>
  );
}
