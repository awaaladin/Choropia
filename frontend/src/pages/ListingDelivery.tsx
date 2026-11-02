import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { toast } from "sonner";
import { AreaSelect } from "@/components/AreaSelect";
import { Button } from "@/components/Button";
import { ErrorState, Skeleton } from "@/components/ui";
import { errorMessage } from "@/lib/actions";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Area } from "@/lib/types";
import { naira } from "@/lib/utils";

const PAYERS = [
  ["buyer", "Buyer pays delivery"],
  ["seller", "I (the seller) pay delivery"],
  ["split", "Split 50/50"],
] as const;

/** The seller decides, per listing, whether delivery is offered, who pays, and which drivers can take the job. */
export function ListingDeliveryPage() {
  const id = Number(useParams().id);
  const { user } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const listing = useQuery({ queryKey: ["listing", id], queryFn: () => api.getListing(id) });
  const current = useQuery({ queryKey: ["listing-delivery", id], queryFn: () => api.dispatch.listingDelivery(id) });
  const [enabled, setEnabled] = useState(false);
  const [payer, setPayer] = useState<string>("buyer");
  const [pickup, setPickup] = useState<Area | null>(null);
  const [chosen, setChosen] = useState<number[]>([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!current.data) return;
    setEnabled(current.data.enabled);
    setPayer(current.data.payer ?? "buyer");
    setPickup(current.data.pickup_area ?? null);
    setChosen((current.data.drivers ?? []).map((d) => d.id));
  }, [current.data]);

  const drivers = useQuery({
    queryKey: ["drivers-from", pickup?.id],
    queryFn: () => api.dispatch.browseDrivers(pickup!.id),
    enabled: !!pickup,
  });

  if (listing.isPending || current.isPending) return <Skeleton className="mx-auto h-64 max-w-xl" />;
  if (listing.isError || !listing.data) return <ErrorState message="We couldn't load this listing." />;
  if (listing.data.seller_id !== user?.id) return <ErrorState message="Only the seller can change delivery for this listing." />;

  const toggle = (driverId: number) => setChosen((c) => (c.includes(driverId) ? c.filter((x) => x !== driverId) : [...c, driverId]));

  const save = async () => {
    if (enabled && !pickup) return toast.error("Choose where the item will be collected from.");
    if (enabled && chosen.length === 0) return toast.error("Pick at least one driver. Picking more than one gets your item collected faster.");
    setSaving(true);
    try {
      await api.dispatch.saveListingDelivery(id, { enabled, payer, pickup_area: pickup?.id ?? 0, drivers: chosen });
      await queryClient.invalidateQueries({ queryKey: ["listing-delivery", id] });
      toast.success("Delivery settings saved");
      navigate(`/listings/${id}`);
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="panel editorial-enter mx-auto max-w-xl space-y-5 p-6">
      <div>
        <h1 className="text-xl font-bold">Delivery for “{listing.data.title}”</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Delivery is optional. When it's on, buyers pick one of your drivers and see the exact price before they pay. Everything is paid on Choropia, so your money is protected and the driver is paid for you.
        </p>
      </div>
      <label className="flex items-center gap-3 font-medium">
        <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} /> Offer delivery on this item
      </label>
      {enabled && (
        <>
          <div>
            <p className="mb-2 text-sm font-semibold">Who pays for delivery?</p>
            {PAYERS.map(([value, label]) => (
              <label key={value} className="flex items-center gap-3 py-1 text-sm">
                <input type="radio" name="payer" checked={payer === value} onChange={() => setPayer(value)} /> {label}
              </label>
            ))}
            {payer === "split" && <p className="mt-1 text-sm text-muted-foreground">Split is always exactly half each. Your half comes out of your payout.</p>}
            {payer !== "buyer" && <p className="mt-1 text-sm text-muted-foreground">You can change the item's price if you'd like to cover the delivery cost.</p>}
          </div>
          <div>
            <p className="mb-2 text-sm font-semibold">Where will the driver collect it?</p>
            <AreaSelect value={pickup?.id ?? null} onChange={(a) => { setPickup(a); setChosen([]); }} placeholder="Pickup area" />
          </div>
          {pickup && (
            <div>
              <p className="mb-1 text-sm font-semibold">Pick your drivers</p>
              <p className="mb-2 text-sm text-muted-foreground">Choose more than one. When the buyer pays, all of them are told and the first to accept takes the job.</p>
              {drivers.data?.length === 0 && <p className="rounded-lg bg-accent p-3 text-sm">No approved drivers serve this area yet. Try another area, or check back soon.</p>}
              <ul className="space-y-2">
                {drivers.data?.map((d) => (
                  <li key={d.id}>
                    <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-border p-3">
                      <input type="checkbox" className="mt-1" checked={chosen.includes(d.id)} onChange={() => toggle(d.id)} />
                      <span className="text-sm">
                        <strong>{d.name}</strong> <span className="text-muted-foreground">· {d.vehicle_type}</span>
                        {d.routes.map((r) => (
                          <span key={r.id} className="block">To {r.to_area.name}: {naira(r.price)}</span>
                        ))}
                      </span>
                    </label>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
      <Button loading={saving} onClick={save}>
        Save delivery settings
      </Button>
    </div>
  );
}
