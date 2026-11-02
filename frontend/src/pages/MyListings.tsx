import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PackagePlus, Pencil, Truck } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Link } from "@/components/AppLink";
import { Button } from "@/components/Button";
import { EmptyState, ErrorState, Pill, Skeleton } from "@/components/ui";
import { errorMessage } from "@/lib/actions";
import { api, rows } from "@/lib/api";
import { naira } from "@/lib/utils";

/** Everything you have posted, in one place: see how many are left, edit, set delivery, or mark sold. */
export function MyListingsPage() {
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<"active" | "sold">("active");
  const listings = useQuery({ queryKey: ["my-listings"], queryFn: async () => rows(await api.myListings()) });
  const sold = useMutation({
    mutationFn: (id: number) => api.markSold(id),
    onSuccess: () => {
      toast.success("Marked as sold.");
      queryClient.invalidateQueries({ queryKey: ["my-listings"] });
      queryClient.invalidateQueries({ queryKey: ["feed"] });
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
              <Link to={`/listings/${l.id}`} className="shrink-0">
                {l.cover_photo ? (
                  <img src={l.cover_photo} alt="" className="size-24 rounded-lg object-cover" />
                ) : (
                  <div className="grid size-24 place-items-center rounded-lg bg-accent text-xs text-muted-foreground">No photo</div>
                )}
              </Link>
              <div className="min-w-0 flex-1">
                <Link to={`/listings/${l.id}`} className="block truncate font-semibold hover:underline">{l.title}</Link>
                <p className="mt-0.5 font-mono text-sm">
                  {l.previous_price && Number(l.previous_price) !== Number(l.price) && <s className="mr-2 text-muted-foreground">{naira(l.previous_price)}</s>}
                  {naira(l.price)}
                </p>
                <p className="text-sm text-muted-foreground">
                  {l.status === "sold" ? "Sold out" : l.quantity === 1 ? "1 left" : `${l.quantity ?? 1} left`} · {l.likes_count ?? 0} likes
                </p>
                {l.status === "active" && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Link to={`/listings/${l.id}/edit`} className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm font-medium hover:bg-accent"><Pencil size={14} /> Edit</Link>
                    <Link to={`/listings/${l.id}/delivery`} className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm font-medium hover:bg-accent"><Truck size={14} /> Delivery</Link>
                    <Button variant="secondary" loading={sold.isPending && sold.variables === l.id} onClick={() => window.confirm("Mark this listing as sold? It will stop showing to buyers.") && sold.mutate(l.id)}>
                      Mark sold
                    </Button>
                  </div>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
