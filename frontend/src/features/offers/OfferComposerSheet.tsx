import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useId, useRef, useState } from "react";
import { ArrowLeft, ShieldCheck, WifiOff } from "lucide-react";
import { Button } from "@/components/Button";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { ChatOffer, OfferDeliveryMethod } from "@/lib/types";
import { cn } from "@/lib/utils";
import { AmountField } from "./AmountField";
import { BottomSheet } from "./BottomSheet";
import { DeliveryMethodPicker } from "./DeliveryMethodPicker";
import { FeeBreakdown } from "./FeeBreakdown";
import { formatKobo, koboToInput, parseNairaToKobo } from "./format";
import { InlineError } from "./InlineError";
import { fade, spring, useCalmMotion } from "./motion";
import { PinPad, useCountdown } from "./PinPad";
import { PinSetupFlow } from "./PinSetupFlow";
import { useOnline } from "./useOnline";

export interface ComposerListing {
  id: number;
  title: string;
  price: string; // naira, as the listings API returns it
}

type Step = "compose" | "pin" | "setup" | "reset";

/**
 * Seller: offer a listing at a lower, locked price, approved with the transaction PIN. If there's no PIN yet, setting
 * one comes first. The offer appears in the chat as a card the buyer can pay from.
 */
export function OfferComposerSheet({
  open,
  onClose,
  conversationId,
  listings,
  defaultListingId,
  onSent,
}: {
  open: boolean;
  onClose: () => void;
  conversationId: number;
  listings: ComposerListing[];
  defaultListingId?: number | null;
  onSent: (offer: ChatOffer) => void;
}) {
  const calm = useCalmMotion();
  const online = useOnline();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const amountRef = useRef<HTMLInputElement>(null);
  const errorId = useId();

  const [listingId, setListingId] = useState<number | null>(null);
  const [amountText, setAmountText] = useState("");
  const [methods, setMethods] = useState<OfferDeliveryMethod[]>(["meetup"]);
  const [note, setNote] = useState("");
  const [pin, setPin] = useState("");
  const [step, setStep] = useState<Step>("compose");
  const [error, setError] = useState<string | null>(null);
  const [pinError, setPinError] = useState<string | null>(null);
  const [errorTick, setErrorTick] = useState(0);
  const [lockSeconds, setLockSeconds] = useState<number | null>(null);
  const [sending, setSending] = useState(false);
  const lockedFor = useCountdown(lockSeconds);

  const pinStatus = useQuery({ queryKey: ["pin-status"], queryFn: api.pinStatus, enabled: open, staleTime: 30_000 });
  const listing = listings.find((l) => l.id === listingId) ?? null;
  const listedKobo = listing ? parseNairaToKobo(listing.price) ?? 0 : 0;
  const rider = useQuery({
    queryKey: ["listingDelivery", listingId],
    queryFn: () => api.dispatch.listingDelivery(listingId as number),
    enabled: open && listingId !== null,
  });
  const riderReady = Boolean(rider.data?.enabled);

  // Fresh sheet each time it opens.
  useEffect(() => {
    if (!open) return;
    const first = listings.find((l) => l.id === defaultListingId) ?? listings[0];
    setListingId(first?.id ?? null);
    setAmountText(first ? koboToInput(parseNairaToKobo(first.price) ?? 0) : "");
    setMethods(["meetup"]);
    setNote("");
    setPin("");
    setError(null);
    setPinError(null);
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (pinStatus.data && !pinStatus.data.has_pin) setStep("setup");
    else if (pinStatus.data) setStep((s) => (s === "setup" ? "compose" : s));
    if (pinStatus.data?.locked) setLockSeconds(pinStatus.data.retry_after);
  }, [pinStatus.data]);

  useEffect(() => {
    if (!riderReady) setMethods((m) => (m.includes("rider") ? m.filter((x) => x !== "rider") : m));
  }, [riderReady]);

  const amountKobo = parseNairaToKobo(amountText);
  const amountValid = amountKobo !== null && amountKobo > 0 && amountKobo <= listedKobo;
  const canContinue = Boolean(listing) && amountValid && methods.length > 0 && online;

  const goToPin = () => {
    if (!canContinue) {
      setError(
        !methods.length
          ? "Choose at least one way to hand the item over."
          : amountKobo !== null && amountKobo > listedKobo
            ? `An offer can't be higher than ${formatKobo(listedKobo)}.`
            : "Enter the price you're offering.",
      );
      return;
    }
    setError(null);
    setPin("");
    setStep("pin");
  };

  const send = async (enteredPin: string) => {
    if (!listing || amountKobo === null) return;
    setSending(true);
    setPinError(null);
    try {
      const offer = await api.createOffer(conversationId, {
        listing_id: listing.id,
        amount_kobo: amountKobo,
        allowed_delivery_methods: methods,
        note: note.trim(),
        pin: enteredPin,
      });
      queryClient.invalidateQueries({ queryKey: ["pin-status"] });
      onSent(offer);
    } catch (e) {
      setPin("");
      if (!(e instanceof ApiError)) {
        setPinError(navigator.onLine ? "Something went wrong. Try again." : "You're offline. Your offer wasn't sent.");
        return;
      }
      switch (e.code) {
        case "pin_invalid": {
          const left = e.data.attempts_left;
          setPinError(typeof left === "number" ? `That PIN is not right. ${left} ${left === 1 ? "try" : "tries"} left.` : e.message);
          setErrorTick((t) => t + 1);
          break;
        }
        case "pin_locked":
          setLockSeconds(Number(e.data.retry_after) || 900);
          setErrorTick((t) => t + 1);
          setPinError(null);
          break;
        default:
          // The offer itself was refused (price, listing, delivery, an open checkout): fix it on the first step.
          setStep("compose");
          setError(e.message);
      }
    } finally {
      setSending(false);
    }
  };

  const titles: Record<Step, [string, string | undefined]> = {
    compose: ["Offer a different price", "Only this buyer sees it. Your listing price doesn't change."],
    pin: ["Approve with your PIN", listing && amountKobo !== null ? `${formatKobo(amountKobo)} for ${listing.title}` : undefined],
    setup: ["Set a transaction PIN", "You need one before you can make offers."],
    reset: ["Reset your PIN", undefined],
  };
  const [title, description] = titles[step];
  const enter = calm ? { opacity: 0 } : { opacity: 0, x: 28 };
  const leave = calm ? { opacity: 0 } : { opacity: 0, x: -28 };

  return (
    <BottomSheet open={open} onClose={onClose} title={title} description={description} initialFocusRef={step === "compose" ? amountRef : undefined} dismissible={!sending}>
      {!online && (
        <p className="mb-3 flex items-center gap-2 rounded-o-sm bg-o-caution-bg px-3 py-2 text-sm text-o-caution" role="status">
          <WifiOff size={16} strokeWidth={1.75} aria-hidden="true" /> You're offline. You can finish writing; sending waits for a connection.
        </p>
      )}

      {pinStatus.isPending ? (
        <div className="space-y-3 py-2" aria-busy="true" aria-label="Loading">
          <div className="h-16 animate-pulse rounded-o-md bg-o-surface" />
          <div className="h-14 animate-pulse rounded-o-md bg-o-surface" />
          <div className="h-24 animate-pulse rounded-o-md bg-o-surface" />
        </div>
      ) : (
        <AnimatePresence mode="wait" initial={false}>
          {step === "setup" && (
            <motion.div key="setup" initial={enter} animate={{ opacity: 1, x: 0 }} exit={leave} transition={calm ? fade : spring}>
              <PinSetupFlow
                mode="setup"
                length={pinStatus.data?.length ?? 4}
                onDone={(status) => {
                  queryClient.setQueryData(["pin-status"], status);
                  setStep("compose");
                }}
              />
            </motion.div>
          )}

          {step === "reset" && (
            <motion.div key="reset" initial={enter} animate={{ opacity: 1, x: 0 }} exit={leave} transition={calm ? fade : spring}>
              <PinSetupFlow
                mode="reset"
                length={pinStatus.data?.length ?? 4}
                onDone={(status) => {
                  queryClient.setQueryData(["pin-status"], status);
                  setLockSeconds(null);
                  setPin("");
                  setPinError(null);
                  setStep("pin");
                }}
              />
            </motion.div>
          )}

          {step === "compose" && (
            <motion.form
              key="compose"
              className="space-y-5"
              initial={enter}
              animate={{ opacity: 1, x: 0 }}
              exit={leave}
              transition={calm ? fade : spring}
              onSubmit={(e) => {
                e.preventDefault();
                goToPin();
              }}
            >
              {listings.length > 1 && (
                <div>
                  <label htmlFor="offer-listing" className="text-sm font-medium text-o-text">
                    Listing
                  </label>
                  <select
                    id="offer-listing"
                    value={listingId ?? ""}
                    onChange={(e) => {
                      const next = listings.find((l) => l.id === Number(e.target.value));
                      setListingId(next?.id ?? null);
                      if (next) setAmountText(koboToInput(parseNairaToKobo(next.price) ?? 0));
                    }}
                    className="mt-1.5 min-h-11 w-full rounded-o-sm border border-o-hairline bg-o-raised px-3 text-sm text-o-text focus:outline-none focus:ring-2 focus:ring-o-accent"
                  >
                    {listings.map((l) => (
                      <option key={l.id} value={l.id}>
                        {l.title}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              {listings.length === 1 && listing && <p className="truncate text-sm font-medium text-o-text">{listing.title}</p>}

              <AmountField
                ref={amountRef}
                text={amountText}
                onTextChange={(t) => {
                  setAmountText(t);
                  setError(null);
                }}
                listedKobo={listedKobo}
                maxKobo={listedKobo}
                errorId={errorId}
                invalid={Boolean(error)}
              />

              <FeeBreakdown amountKobo={amountValid ? amountKobo : null} verified={Boolean(user?.profile?.seller_verified)} />

              <DeliveryMethodPicker
                mode="multiple"
                legend="How can it be handed over?"
                value={methods}
                onChange={(m) => {
                  setMethods(m);
                  setError(null);
                }}
                unavailable={riderReady ? [] : ["rider"]}
              />

              <div>
                <label htmlFor="offer-note" className="text-sm font-medium text-o-text">
                  Note <span className="font-normal text-o-muted">(optional)</span>
                </label>
                <textarea
                  id="offer-note"
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  maxLength={300}
                  rows={2}
                  placeholder="e.g. Final price, comes with the charger"
                  className="mt-1.5 w-full resize-none rounded-o-sm border border-o-hairline bg-o-raised px-3 py-2 text-sm text-o-text placeholder:text-o-muted/70 focus:outline-none focus:ring-2 focus:ring-o-accent"
                />
              </div>

              <InlineError message={error} id={errorId} />

              <p className="text-xs text-o-muted">The offer is valid for 24 hours. The buyer pays into Choropia escrow; you're paid once they confirm they have it.</p>
              <Button type="submit" className="min-h-12 w-full text-base" disabled={!online}>
                Continue
              </Button>
            </motion.form>
          )}

          {step === "pin" && (
            <motion.div key="pin" initial={enter} animate={{ opacity: 1, x: 0 }} exit={leave} transition={calm ? fade : spring}>
              <button
                type="button"
                onClick={() => setStep("compose")}
                disabled={sending}
                className="mb-2 inline-flex min-h-11 items-center gap-1.5 rounded-o-sm px-1 text-sm text-o-muted hover:text-o-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-o-accent"
              >
                <ArrowLeft size={16} strokeWidth={1.75} aria-hidden="true" /> Edit offer
              </button>
              <PinPad
                length={pinStatus.data?.length ?? 4}
                label="Enter your transaction PIN"
                value={pin}
                onChange={(v) => {
                  setPin(v);
                  if (v) setPinError(null);
                }}
                onComplete={(v) => void send(v)}
                errorTick={errorTick}
                error={Boolean(pinError)}
                disabled={sending || !online}
                lockedFor={lockedFor}
              />
              <InlineError message={pinError} />
              <div className={cn("mt-4 flex items-center justify-center gap-2 text-sm text-o-muted", !sending && "invisible")} aria-live="polite">
                <ShieldCheck size={16} strokeWidth={1.75} aria-hidden="true" /> {sending ? "Sending your offer…" : ""}
              </div>
              <div className="mt-2 text-center">
                <button
                  type="button"
                  onClick={() => setStep("reset")}
                  className="min-h-11 rounded-o-sm px-2 text-sm font-medium text-o-accent underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-o-accent"
                >
                  Forgot PIN?
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      )}
    </BottomSheet>
  );
}
