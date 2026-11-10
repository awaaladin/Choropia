import { motion } from "motion/react";
import { useEffect, useState } from "react";
import { Lock, WifiOff } from "lucide-react";
import { Button } from "@/components/Button";
import { api, ApiError } from "@/lib/api";
import type { ChatOffer, OfferDeliveryMethod } from "@/lib/types";
import { BottomSheet } from "./BottomSheet";
import { DeliveryMethodPicker } from "./DeliveryMethodPicker";
import { formatKobo } from "./format";
import { InlineError } from "./InlineError";
import { spring, useCalmMotion } from "./motion";
import { useOnline } from "./useOnline";

/**
 * Buyer: choose how to receive the item, then pay the locked price into escrow through Paystack. The buyer never sees
 * Choropia's fee. A rider order goes to the order page first to pick the rider and drop-off (delivery fee added there).
 */
export function PaySheet({
  open,
  onClose,
  offer,
  onCheckout,
}: {
  open: boolean;
  onClose: () => void;
  offer: ChatOffer;
  /** Called with the checkout result; the page decides where to go (Paystack, or the order page for a rider). */
  onCheckout: (result: { order_id: number; authorization_url: string | null }) => void;
}) {
  const calm = useCalmMotion();
  const online = useOnline();
  const [method, setMethod] = useState<OfferDeliveryMethod>(offer.delivery_method || offer.allowed_delivery_methods[0]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const locked = offer.status === "payment_processing" && Boolean(offer.delivery_method);

  useEffect(() => {
    if (open) {
      setMethod(offer.delivery_method || offer.allowed_delivery_methods[0]);
      setError(null);
    }
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  const pay = async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await api.checkoutOffer(offer.id, method);
      onCheckout(result);
    } catch (e) {
      setError(
        e instanceof ApiError
          ? e.code === "expired"
            ? "This offer has expired. Ask the seller for a new one."
            : e.message
          : navigator.onLine
            ? "Payment couldn't be opened. Try again."
            : "You're offline. Connect and try again.",
      );
    } finally {
      setBusy(false);
    }
  };

  const rider = method === "rider";

  return (
    <BottomSheet open={open} onClose={onClose} title="Pay into escrow" description={offer.listing.title} dismissible={!busy}>
      <div className="space-y-5">
        {!online && (
          <p className="flex items-center gap-2 rounded-o-sm bg-o-caution-bg px-3 py-2 text-sm text-o-caution" role="status">
            <WifiOff size={16} strokeWidth={1.75} aria-hidden="true" /> You're offline.
          </p>
        )}

        <DeliveryMethodPicker
          mode="single"
          legend={locked ? "Handover (chosen at checkout)" : "How do you want to receive it?"}
          options={locked ? [offer.delivery_method as OfferDeliveryMethod] : offer.allowed_delivery_methods}
          value={[method]}
          onChange={([m]) => m && setMethod(m)}
        />

        <motion.dl
          className="space-y-2 rounded-o-md bg-o-surface p-4 text-sm"
          layout={!calm}
          transition={spring}
          aria-label="Summary"
        >
          <div className="flex justify-between">
            <dt className="text-o-muted">Price agreed with the seller</dt>
            <dd className="tabular-nums text-o-text">{formatKobo(offer.amount_kobo)}</dd>
          </div>
          {rider && (
            <div className="flex justify-between">
              <dt className="text-o-muted">Rider delivery</dt>
              <dd className="text-o-muted">{offer.delivery_fee_kobo ? formatKobo(offer.delivery_fee_kobo) : "Chosen next"}</dd>
            </div>
          )}
          <div className="flex items-baseline justify-between border-t border-o-hairline pt-2">
            <dt className="font-semibold text-o-text">{rider && !offer.delivery_fee_kobo ? "To pay now (before delivery)" : "You pay"}</dt>
            <dd className="font-display text-xl font-semibold tabular-nums text-o-text">
              {formatKobo(offer.amount_kobo + (rider ? offer.delivery_fee_kobo : 0))}
            </dd>
          </div>
        </motion.dl>

        <p className="flex items-start gap-2 text-xs text-o-muted">
          <Lock size={14} strokeWidth={1.75} className="mt-0.5 shrink-0" aria-hidden="true" />
          Your money is held by Choropia and only released to the seller after you have the item. If the deal falls through
          before handover, you get a full refund.
        </p>

        <InlineError message={error} />

        <Button className="min-h-12 w-full text-base" onClick={pay} loading={busy} disabled={!online}>
          {rider ? "Continue to delivery" : `Pay ${formatKobo(offer.amount_kobo)} securely`}
        </Button>
        <p className="text-center text-xs text-o-muted">Card, bank transfer or USSD via Paystack</p>
      </div>
    </BottomSheet>
  );
}
