import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Gavel, Lock, Package, ShieldCheck, Truck } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { useParams, useSearchParams } from "react-router";
import { toast } from "sonner";
import { Button } from "@/components/Button";
import { ErrorState, Modal, Skeleton, Textarea } from "@/components/ui";
import { errorMessage } from "@/lib/actions";
import { api, rows } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { STATUS_LABELS, naira, timeAgo } from "@/lib/utils";

const STEPS = [
  { key: "paid_escrow", label: "Paid", icon: Lock },
  { key: "courier_assigned", label: "Dispatched", icon: Truck },
  { key: "in_transit", label: "In transit", icon: Package },
  { key: "delivered", label: "Delivered", icon: Package },
  { key: "confirmed", label: "Confirmed", icon: CheckCircle2 },
  { key: "completed", label: "Completed", icon: ShieldCheck },
] as const;

function Stepper({ status }: { status: string }) {
  if (status === "disputed" || status === "refunded") {
    return (
      <div className="mt-4 flex items-center gap-2 rounded-lg bg-destructive/10 p-3 text-destructive">
        <Gavel size={18} />
        <span className="text-sm font-medium">{status === "disputed" ? "Under dispute — a moderator is reviewing this order." : "Refunded to buyer."}</span>
      </div>
    );
  }
  const index = STEPS.findIndex((s) => s.key === status);
  const progress = Math.max(0, index / (STEPS.length - 1)) * 100;
  return (
    <div className="relative mt-5 px-4">
      <div className="absolute left-4 right-4 top-4 h-0.5 bg-border" />
      <div className="absolute left-4 top-4 h-0.5 bg-primary transition-all duration-500" style={{ width: `calc((100% - 2rem) * ${progress / 100})` }} />
      <div className="relative flex justify-between">
        {STEPS.map((step, i) => {
          const done = index > i;
          const active = index === i;
          const Icon = step.icon;
          return (
            <div key={step.key} className="-mx-1 flex w-16 flex-col items-center">
              <div
                className={`grid size-8 shrink-0 place-items-center rounded-full transition-colors ${
                  done ? "bg-primary text-primary-foreground" : active ? "bg-foreground text-background" : "bg-accent text-muted-foreground"
                }`}
              >
                <Icon size={14} />
              </div>
              <span className={`mt-1 text-center text-[10px] leading-tight ${active ? "font-semibold text-foreground" : "text-muted-foreground"}`}>{step.label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function Stars({ rating }: { rating: number }) {
  return (
    <span className="text-primary">
      {"★".repeat(rating)}
      <span className="text-border">{"★".repeat(5 - rating)}</span>
    </span>
  );
}

export function OrderDetailPage() {
  const { id } = useParams();
  const orderId = Number(id);
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [disputeOpen, setDisputeOpen] = useState(false);
  const [disputeReason, setDisputeReason] = useState("");

  const order = useQuery({ queryKey: ["order", orderId], queryFn: () => api.getOrder(orderId) });
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["order", orderId] });

  // Paystack sends the buyer back here with ?reference=...; confirm with the server straight away
  // instead of waiting for the webhook.
  const [searchParams, setSearchParams] = useSearchParams();
  const returnedReference = searchParams.get("reference");
  useEffect(() => {
    if (!returnedReference) return;
    api
      .verifyPayment(orderId)
      .then((result) => {
        if (result.order_status !== "pending_payment") toast.success("Payment received. It's held safely in escrow.");
      })
      .catch(() => {})
      .finally(() => {
        invalidate();
        setSearchParams({}, { replace: true });
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [returnedReference, orderId]);

  const pay = useMutation({
    mutationFn: () => api.initializePayment(orderId),
    onSuccess: (data) => window.location.assign(data.authorization_url),
    onError: (err) => toast.error(errorMessage(err)),
  });
  const assignCourier = useMutation({ mutationFn: () => api.assignCourier(orderId), onSuccess: invalidate, onError: (err) => toast.error(errorMessage(err)) });
  const inTransit = useMutation({ mutationFn: () => api.markInTransit(orderId), onSuccess: invalidate, onError: (err) => toast.error(errorMessage(err)) });
  const delivered = useMutation({ mutationFn: () => api.markDelivered(orderId), onSuccess: invalidate, onError: (err) => toast.error(errorMessage(err)) });
  const cancel = useMutation({
    mutationFn: () => api.cancelOrder(orderId),
    onSuccess: () => {
      toast.success("The order was cancelled.");
      invalidate();
    },
    onError: (err) => toast.error(errorMessage(err)),
  });
  const confirm = useMutation({ mutationFn: () => api.confirmReceipt(orderId), onSuccess: invalidate, onError: (err) => toast.error(errorMessage(err)) });
  const dispute = useMutation({
    mutationFn: (reason: string) => api.openDispute(orderId, reason),
    onSuccess: () => {
      setDisputeOpen(false);
      setDisputeReason("");
      invalidate();
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const otherPartyId = order.data && (user?.id === order.data.buyer ? order.data.seller : order.data.buyer);
  const reviews = useQuery({
    queryKey: ["reviews", otherPartyId],
    queryFn: async () => rows(await api.listReviewsFor(otherPartyId!)),
    enabled: !!otherPartyId && order.data?.status === "completed",
  });
  const submitReview = useMutation({
    mutationFn: (payload: { rating: number; comment: string }) => api.createReview(orderId, payload.rating, payload.comment),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["reviews", otherPartyId] }),
    onError: (err) => toast.error(errorMessage(err)),
  });

  if (order.isPending) {
    return (
      <div className="mx-auto max-w-xl">
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }
  if (order.isError) {
    return (
      <div className="mx-auto max-w-xl">
        <ErrorState message={(order.error as Error).message} onRetry={() => order.refetch()} />
      </div>
    );
  }

  const o = order.data!;
  const isBuyer = user?.id === o.buyer;
  const isSeller = user?.id === o.seller;
  const myReview = reviews.data?.find((r) => r.order === o.id && r.reviewer === user?.id);

  const onSubmitDispute = (e: FormEvent) => {
    e.preventDefault();
    if (disputeReason.trim()) dispute.mutate(disputeReason.trim());
  };
  const onSubmitReview = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    submitReview.mutate({ rating: Number(form.get("rating")), comment: String(form.get("comment") ?? "") });
  };

  return (
    <div className="mx-auto max-w-xl">
      <div className="panel editorial-enter p-6">
        <div className="flex items-center gap-3">
          <div className="size-14 shrink-0 overflow-hidden rounded-md bg-accent">
            {o.listing_cover_photo && <img src={o.listing_cover_photo} alt="" className="h-full w-full object-cover" />}
          </div>
          <div className="min-w-0 flex-1">
            <h1 className="truncate font-display text-lg font-bold">{o.listing_title || `Order #${o.id}`}</h1>
            <span className="font-mono text-muted-foreground">{naira(o.price)}</span>
          </div>
          <span className="shrink-0 rounded-full bg-accent px-2.5 py-0.5 text-[10px] font-semibold text-muted-foreground">{STATUS_LABELS[o.status] || o.status}</span>
        </div>

        {o.dispute_reason && (
          <p className="mt-3 flex items-center gap-1 text-sm text-destructive">
            <AlertTriangle size={14} /> Dispute: {o.dispute_reason}
          </p>
        )}

        <Stepper status={o.status} />

        <h2 className="mt-6 flex items-center gap-1 text-sm font-semibold">
          <ShieldCheck size={14} className="text-primary" /> Escrow timeline
        </h2>
        {o.history.length === 0 ? (
          <p className="mt-2 text-sm text-muted-foreground">No status changes yet.</p>
        ) : (
          <ol className="mt-2 space-y-3">
            {o.history.map((h) => (
              <li key={h.id} className="border-l-2 border-primary/40 pl-3 text-sm">
                <span className="font-medium">{STATUS_LABELS[h.to_status] || h.to_status}</span>
                <span className="text-muted-foreground"> · {timeAgo(h.created_at)}</span>
                {h.note && <p className="text-muted-foreground">{h.note}</p>}
              </li>
            ))}
          </ol>
        )}

        {o.status === "pending_payment" && isBuyer && (
          <Button className="mt-4" loading={pay.isPending} onClick={() => pay.mutate()}>
            <Lock size={15} /> Pay into escrow
          </Button>
        )}
        {/* The seller moves the item along; nobody is "assigned" by the site. Delivery by a Choropia driver (when offered) is
            accepted by a driver in the Choropia app, and the order then shows who is coming. */}
        {o.status === "paid_escrow" && isSeller && (
          <div className="mt-4 space-y-2">
            <Button loading={assignCourier.isPending} onClick={() => assignCourier.mutate()}>
              <Truck size={15} /> I've dispatched it
            </Button>
            <p className="text-sm text-muted-foreground">
              Tap this once the item has left you (you handed it over, or sent it with someone). Dispatch within 7 days or the buyer is refunded
              automatically. You are paid as soon as the buyer confirms.
            </p>
          </div>
        )}
        {o.status === "courier_assigned" && isSeller && (
          <Button className="mt-4" loading={inTransit.isPending} onClick={() => inTransit.mutate()}>
            <Package size={15} /> It's on its way
          </Button>
        )}
        {o.status === "in_transit" && isSeller && (
          <div className="mt-4 space-y-2">
            <Button loading={delivered.isPending} onClick={() => delivered.mutate()}>
              <CheckCircle2 size={15} /> Mark as delivered
            </Button>
            <p className="text-sm text-muted-foreground">If the buyer does nothing, you are paid automatically 3 days after you mark it delivered.</p>
          </div>
        )}
        {["paid_escrow", "courier_assigned", "in_transit", "delivered"].includes(o.status) && isBuyer && (
          <div className="mt-4 flex flex-wrap gap-3">
            <Button loading={confirm.isPending} onClick={() => confirm.mutate()}>
              <CheckCircle2 size={15} /> {o.status === "delivered" ? "Confirm receipt" : "I received it"}
            </Button>
            {o.status !== "paid_escrow" && (
              <Button variant="danger" onClick={() => setDisputeOpen(true)}>
                {o.status === "delivered" ? "Report a problem" : "It hasn't arrived"}
              </Button>
            )}
          </div>
        )}
        {["pending_payment", "paid_escrow"].includes(o.status) && (isBuyer || isSeller) && (
          <div className="mt-4">
            <Button
              variant="secondary"
              loading={cancel.isPending}
              onClick={() => {
                if (window.confirm(o.status === "paid_escrow" ? "Cancel this order? The buyer is refunded in full." : "Cancel this order?")) cancel.mutate();
              }}
            >
              Cancel order
            </Button>
            {o.status === "paid_escrow" && <p className="mt-1 text-sm text-muted-foreground">Until the item is on its way, either of you can cancel and the buyer gets their money back.</p>}
          </div>
        )}

        {o.status === "completed" && otherPartyId && (
          <div className="mt-6">
            {myReview ? (
              <>
                <h2 className="text-sm font-semibold">Your review</h2>
                <p className="mt-1">
                  <Stars rating={myReview.rating} />
                </p>
                {myReview.comment && <p className="text-sm text-muted-foreground">{myReview.comment}</p>}
              </>
            ) : (
              <>
                <h2 className="text-sm font-semibold">Leave a review</h2>
                <form onSubmit={onSubmitReview} className="mt-2 space-y-2">
                  <select name="rating" defaultValue="5" className="w-full rounded-md border border-border bg-panel px-3 py-2 text-sm">
                    {[5, 4, 3, 2, 1].map((n) => (
                      <option key={n} value={n}>
                        {"★".repeat(n)}
                        {"☆".repeat(5 - n)}
                      </option>
                    ))}
                  </select>
                  <Textarea name="comment" rows={2} placeholder="How was this transaction?" />
                  <Button type="submit" variant="secondary" loading={submitReview.isPending}>
                    Submit review
                  </Button>
                </form>
              </>
            )}
          </div>
        )}
      </div>

      <Modal open={disputeOpen} onClose={() => setDisputeOpen(false)} title="What went wrong?">
        <form onSubmit={onSubmitDispute} className="space-y-3">
          <Textarea value={disputeReason} onChange={(e) => setDisputeReason(e.target.value)} rows={3} required autoFocus />
          <Button type="submit" variant="danger" className="w-full" loading={dispute.isPending}>
            Open dispute
          </Button>
        </form>
      </Modal>
    </div>
  );
}
