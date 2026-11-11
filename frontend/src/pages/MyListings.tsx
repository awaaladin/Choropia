import { listingPath } from "@/lib/links";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PackagePlus, Pencil, Trash2, Truck } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Link } from "@/components/AppLink";
import { Button } from "@/components/Button";
import { EmptyState, ErrorState, Modal, Pill, Skeleton } from "@/components/ui";
import { errorMessage } from "@/lib/actions";
import { api, rows } from "@/lib/api";
import { naira } from "@/lib/utils";

/** Everything you have posted, in one place: see how many are left, edit, set delivery, or mark sold. */
export function MyListingsPage() {
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<"active" | "sold">("active");
  const [durationAction, setDurationAction] = useState<{ id: number; action: "sold" | "extend" } | null>(null);
  const [durationDays, setDurationDays] = useState(3);
  const listings = useQuery({ queryKey: ["my-listings"], queryFn: async () => rows(await api.myListings()) });
  const sold = useMutation({
    mutationFn: ({ id, days }: { id: number; days: number }) => api.markSold(id, days),
    onSuccess: () => {
      setDurationAction(null);
      toast.success("Marked as sold.");
      queryClient.invalidateQueries({ queryKey: ["my-listings"] });
      queryClient.invalidateQueries({ queryKey: ["feed"] });
    },
    onError: (err) => toast.error(errorMessage(err)),
  });
  const extend = useMutation({
    mutationFn: ({ id, days }: { id: number; days: number }) => api.extendMarketVisibility(id, days),
    onSuccess: () => {
      setDurationAction(null);
      toast.success("Market visibility extended.");
      queryClient.invalidateQueries({ queryKey: ["my-listings"] });
      queryClient.invalidateQueries({ queryKey: ["feed"] });
    },
    onError: (err) => toast.error(errorMessage(err)),
  });
  const relist = useMutation({
    mutationFn: (id: number) => api.relist(id),
    onSuccess: () => {
      toast.success("Listing is back on the market.");
      queryClient.invalidateQueries({ queryKey: ["my-listings"] });
      queryClient.invalidateQueries({ queryKey: ["feed"] });
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const remove = useMutation({
    mutationFn: (id: number) => api.deleteListing(id),
    onSuccess: () => {
      toast.success("Listing deleted.");
      queryClient.invalidateQueries({ queryKey: ["my-listings"] });
      queryClient.invalidateQueries({ queryKey: ["feed"] });
      queryClient.invalidateQueries({ queryKey: ["listings"] });
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  if (listings.isPending) return <Skeleton className="mx-auto h-64 max-w-3xl" />;
  if (listings.isError) return <ErrorState message="We couldn't load your listings." onRetry={() => listings.refetch()} />;
  const all = listings.data;
  const shown = all.filter((l) => (tab === "active" ? l.status === "active" : l.status === "sold"));

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl font-bold">My listings</h1>
          <p className="text-sm text-muted-foreground">Everything you have posted. Tap a listing to see it as buyers do.</p>
        </div>
        <Link to="/listings/new" className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground">
          <PackagePlus size={16} /> Post a listing
        </Link>
      </div>
      <div className="flex gap-2">
        <Pill active={tab === "active"} onClick={() => setTab("active")}>Active ({all.filter((l) => l.status === "active").length})</Pill>
        <Pill active={tab === "sold"} onClick={() => setTab("sold")}>Sold ({all.filter((l) => l.status === "sold").length})</Pill>
      </div>
      {shown.length === 0 ? (
        <EmptyState
          icon={<PackagePlus size={22} />}
          title={tab === "active" ? "No active listings" : "Nothing sold yet"}
          hint={tab === "active" ? "Post something for sale and it will show up here." : "Items that sell, or that you mark as sold, appear here."}
          action={tab === "active" ? <Link to="/listings/new" className="text-sm font-medium text-primary underline">Post a listing</Link> : undefined}
        />
      ) : (
        <ul className="space-y-3">
          {shown.map((l) => (
            <li key={l.id} className="panel flex gap-4 p-4">
              <Link to={listingPath(l)} className="shrink-0">
                {l.cover_photo ? (
                  <img src={l.cover_photo} alt="" className="size-24 rounded-lg object-cover" />
                ) : (
                  <div className="grid size-24 place-items-center rounded-lg bg-accent text-xs text-muted-foreground">No photo</div>
                )}
              </Link>
              <div className="min-w-0 flex-1">
                <Link to={listingPath(l)} className="block truncate font-semibold hover:underline">{l.title}</Link>
                <p className="mt-0.5 font-mono text-sm">
                  {l.previous_price && Number(l.previous_price) !== Number(l.price) && <s className="mr-2 text-muted-foreground">{naira(l.previous_price)}</s>}
                  {naira(l.price)}
                </p>
                <p className="text-sm text-muted-foreground">
                  {l.status === "sold" ? "Sold out" : l.quantity === 1 ? "1 left" : `${l.quantity ?? 1} left`} · {l.likes_count ?? 0} likes
                </p>
                {l.status === "sold" && l.market_visible_until && (
                  <p className="text-xs text-muted-foreground">
                    {new Date(l.market_visible_until) > new Date()
                      ? `Visible to buyers until ${new Date(l.market_visible_until).toLocaleDateString()}`
                      : "No longer visible to buyers"}
                  </p>
                )}
                <div className="mt-3 flex flex-wrap gap-2">
                  {l.status === "active" && (
                    <>
                    <Link to={`/listings/${l.id}/edit`} className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm font-medium hover:bg-accent"><Pencil size={14} /> Edit</Link>
                    <Link to={`/listings/${l.id}/delivery`} className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm font-medium hover:bg-accent"><Truck size={14} /> Delivery</Link>
                    <Button variant="secondary" onClick={() => { setDurationDays(3); setDurationAction({ id: l.id, action: "sold" }); }}>
                      Mark sold
                    </Button>
                    </>
                  )}
                  {l.status === "sold" && (
                    <>
                      <Button variant="secondary" onClick={() => { setDurationDays(3); setDurationAction({ id: l.id, action: "extend" }); }}>
                        Extend visibility
                      </Button>
                      <Button variant="secondary" loading={relist.isPending && relist.variables === l.id} onClick={() => relist.mutate(l.id)}>
                        Relist
                      </Button>
                    </>
                  )}
                  <Button variant="danger" loading={remove.isPending && remove.variables === l.id} onClick={() => window.confirm("Delete this listing for good? Buyers will no longer see it.") && remove.mutate(l.id)}>
                    <Trash2 size={14} /> Delete
                  </Button>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
      <Modal
        open={durationAction !== null}
        onClose={() => setDurationAction(null)}
        title={durationAction?.action === "extend" ? "Extend market visibility" : "How long should this stay on the market?"}
      >
        <p className="mb-4 text-sm text-muted-foreground">
          The listing will show a Sold badge for this duration. Buyers can still message you, but cannot buy it.
        </p>
        <div className="grid grid-cols-5 gap-2">
          {[1, 3, 7, 14, 30].map((days) => (
            <button
              key={days}
              type="button"
              aria-pressed={durationDays === days}
              onClick={() => setDurationDays(days)}
              className={`min-h-11 rounded-lg border px-2 text-sm ${durationDays === days ? "border-primary bg-primary text-primary-foreground" : "border-border hover:bg-accent"}`}
            >
              {days}d
            </button>
          ))}
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setDurationAction(null)}>Cancel</Button>
          <Button
            loading={sold.isPending || extend.isPending}
            onClick={() => {
              if (!durationAction) return;
              if (durationAction.action === "sold") sold.mutate({ id: durationAction.id, days: durationDays });
              else extend.mutate({ id: durationAction.id, days: durationDays });
            }}
          >
            {durationAction?.action === "extend" ? "Extend" : "Mark sold"}
          </Button>
        </div>
      </Modal>
    </div>
  );
}
