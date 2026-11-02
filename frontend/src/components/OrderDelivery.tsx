import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Truck } from "lucide-react";
import { useState } from "react";
import { Link } from "@/components/AppLink";
import { toast } from "sonner";
import { AreaSelect } from "@/components/AreaSelect";
import { Button } from "@/components/Button";
import { Field, Textarea } from "@/components/ui";
import { errorMessage } from "@/lib/actions";
import { api } from "@/lib/api";
import type { Area } from "@/lib/types";
import { naira } from "@/lib/utils";

/** Delivery on an order: the buyer picks where to and which driver's price (before paying); after that, everyone sees who is on it. */
export function OrderDelivery({ orderId, listingId, orderStatus, isBuyer, isSeller }: { orderId: number; listingId: number; orderStatus: string; isBuyer: boolean; isSeller: boolean }) {
  const queryClient = useQueryClient();
  const delivery = useQuery({
    queryKey: ["order-delivery", orderId],
    queryFn: () => api.dispatch.orderDelivery(orderId),
    // While a driver is being found, or is on the way, keep an eye on it.
    refetchInterval: ["paid_escrow", "courier_assigned", "in_transit"].includes(orderStatus) ? 8000 : false,
  });
  const beforePayment = isBuyer && orderStatus === "pending_payment";
  const options = useQuery({
    queryKey: ["listing-delivery", listingId, "buyer"],
    queryFn: () => api.dispatch.listingDelivery(listingId),
    enabled: beforePayment && delivery.data === null,
  });
  const [dropoff, setDropoff] = useState<Area | null>(null);
  const [driverId, setDriverId] = useState<number | null>(null);
  const [note, setNote] = useState("");
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["order-delivery", orderId] });

  const priced = useQuery({
    queryKey: ["listing-delivery", listingId, dropoff?.id],
    queryFn: () => api.dispatch.listingDelivery(listingId, dropoff!.id),
    enabled: beforePayment && !!dropoff,
  });
  const choose = useMutation({
    mutationFn: () => api.dispatch.chooseDelivery(orderId, { dropoff_area: dropoff!.id, driver: driverId!, dropoff_note: note }),
    onSuccess: refresh,
    onError: (err) => toast.error(errorMessage(err)),
  });
  const clear = useMutation({ mutationFn: () => api.dispatch.clearDelivery(orderId), onSuccess: refresh, onError: (err) => toast.error(errorMessage(err)) });
  const reassign = useMutation({
    mutationFn: () => api.dispatch.reassign(orderId),
    onSuccess: () => {
      toast.success("The job was offered to your drivers again.");
      refresh();
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const d = delivery.data;
  if (d && d.status !== "cancelled") {
    return (
      <div className="mt-6 rounded-lg border border-border p-4">
        <h2 className="flex items-center gap-2 text-sm font-semibold"><Truck size={15} /> Delivery</h2>
        <p className="mt-1 font-medium text-primary">{d.status_label}</p>
        <p className="mt-1 text-sm">{d.pickup_area.name} to {d.dropoff_area.name}</p>
        <p className="text-sm text-muted-foreground">
          Delivery fee {naira(d.fee)}
          {d.payer === "split" ? " (split 50/50)" : d.payer === "seller" ? " (paid by the seller)" : ""}
        </p>
        {d.driver && (
          <p className="mt-2 text-sm">
            Driver: <strong>{d.driver.name}</strong> · {d.driver.vehicle_type} {d.driver.plate_number}
            {d.driver.phone && <span className="block text-muted-foreground">Phone {d.driver.phone} · WhatsApp {d.driver.whatsapp}</span>}
          </p>
        )}
        {isSeller && d.status === "offered" && <p className="mt-2 text-sm">{d.drivers_notified} driver(s) have been told. The first to accept gets the job.</p>}
        {isBuyer && d.handover_code && (
          <div className="mt-3 rounded-xl bg-accent p-4 text-center">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Your handover code</p>
            <p className="my-1 font-mono text-3xl font-bold tracking-widest">{d.handover_code.replace(/(\d{3})(\d{3})/, "$1 $2")}</p>
            <p className="text-xs text-muted-foreground">Tell the driver this code only when the item is in your hands. It confirms delivery and releases your payment to the seller.</p>
          </div>
        )}
        {isSeller && d.can_reassign && (
          <div className="mt-3 flex flex-wrap gap-2">
            <Button variant="secondary" loading={reassign.isPending} onClick={() => window.confirm("Change the driver? The current driver is told they're no longer needed and your other drivers are offered the job.") && reassign.mutate()}>
              Change the driver
            </Button>
            <Link to={`/listings/${listingId}/delivery`} className="self-center text-sm font-medium text-primary hover:underline">
              Add more drivers
            </Link>
          </div>
        )}
        {isBuyer && d.can_cancel_choice && (
          <Button className="mt-3" variant="secondary" loading={clear.isPending} onClick={() => clear.mutate()}>
            Collect it myself instead
          </Button>
        )}
      </div>
    );
  }

  if (beforePayment && options.data?.enabled) {
    const info = priced.data ?? options.data;
    const choices = (priced.data?.drivers ?? []).flatMap((dr) => dr.routes.map((r) => ({ dr, r })));
    return (
      <div className="mt-6 rounded-lg border border-border p-4">
        <h2 className="flex items-center gap-2 text-sm font-semibold"><Truck size={15} /> Delivery (optional)</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          The seller can have this delivered by a Choropia driver.{" "}
          {info.payer === "seller" ? "The seller covers the delivery." : info.payer === "split" ? "You and the seller each pay half of the delivery fee." : "You pay the delivery fee."}
        </p>
        <div className="mt-3 space-y-3">
          <Field label="Deliver to"><AreaSelect value={dropoff?.id ?? null} onChange={(a) => { setDropoff(a); setDriverId(null); }} /></Field>
          {dropoff && choices.length === 0 && <p className="text-sm">None of the seller's drivers go to {dropoff.name} yet.</p>}
          {choices.map(({ dr, r }) => (
            <label key={`${dr.id}-${r.id}`} className="flex cursor-pointer items-start gap-3 rounded-lg border border-border p-3 text-sm">
              <input type="radio" name="driver" checked={driverId === dr.id} onChange={() => setDriverId(dr.id)} className="mt-1" />
              <span>
                <strong>{dr.name}</strong> · {dr.vehicle_type}
                <span className="block text-muted-foreground">
                  Fee {naira(r.price)}
                  {r.you_pay && info.payer !== "buyer" ? ` · you pay ${naira(r.you_pay)}` : ""}
                </span>
              </span>
            </label>
          ))}
          {choices.length > 0 && (
            <>
              <Field label="Exact address or landmark">
                <Textarea value={note} onChange={(e) => setNote(e.target.value.slice(0, 300))} rows={2} />
              </Field>
              <Button loading={choose.isPending} disabled={!driverId || !note.trim()} onClick={() => choose.mutate()}>
                Add delivery
              </Button>
            </>
          )}
        </div>
        <p className="mt-3 text-xs text-muted-foreground">Prefer to meet the seller? Skip this and just pay for the item. Your address and phone number stay private until a driver accepts.</p>
      </div>
    );
  }
  return null;
}

