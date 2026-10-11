import { useQuery } from "@tanstack/react-query";
import { Store } from "lucide-react";
import { useParams } from "react-router";
import { Link } from "@/components/AppLink";
import { FollowButton } from "@/components/FollowButton";
import { Badge, EmptyState, ErrorState, Skeleton } from "@/components/ui";
import { api, rows } from "@/lib/api";
import { naira } from "@/lib/utils";

function Stars({ rating }: { rating: number }) {
  return (
    <span className="text-primary">
      {"★".repeat(rating)}
      <span className="text-border">{"★".repeat(5 - rating)}</span>
    </span>
  );
}

export function MerchantProfilePage() {
  const { id } = useParams();
  const merchantId = Number(id);

  const merchant = useQuery({ queryKey: ["merchant", merchantId], queryFn: () => api.getMerchant(merchantId) });
  const listings = useQuery({ queryKey: ["merchant-listings", merchantId], queryFn: async () => rows(await api.listMerchantListings(merchantId)) });
  const reviews = useQuery({
    queryKey: ["reviews", merchant.data?.owner_id],
    queryFn: async () => rows(await api.listReviewsFor(merchant.data!.owner_id)),
    enabled: !!merchant.data,
  });

  if (merchant.isPending) {
    return (
      <div className="mx-auto max-w-3xl">
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }
  if (merchant.isError) {
    return (
      <div className="mx-auto max-w-3xl">
        <ErrorState message={(merchant.error as Error).message} onRetry={() => merchant.refetch()} />
      </div>
    );
  }

  const m = merchant.data!;
  const reviewList = reviews.data ?? [];
  const avg = reviewList.length ? (reviewList.reduce((sum, r) => sum + r.rating, 0) / reviewList.length).toFixed(1) : null;

  return (
    <div className="mx-auto max-w-3xl">
      <div className="panel editorial-enter overflow-hidden">
        <div className="h-28 bg-primary" />
        <div className="-mt-10 px-6 pb-6">
          <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
            <div className="flex items-end gap-4">
              <div className="size-24 shrink-0 overflow-hidden rounded-xl bg-accent ring-4 ring-popover">
                {m.logo ? <img src={m.logo} alt="" className="h-full w-full object-cover" /> : <div className="grid h-full place-items-center text-muted-foreground"><Store size={28} /></div>}
              </div>
              <div className="min-w-0 pb-1">
                <div className="flex flex-wrap items-center gap-1.5">
                  <h1 className="truncate font-display text-xl font-bold">{m.business_name}</h1>
                  <Badge tone="primary">Verified</Badge>
                </div>
                <p className="text-sm text-muted-foreground">{m.location}</p>
              </div>
            </div>
            <FollowButton merchantId={m.id} className="shrink-0" />
          </div>

          <p className="mt-4 max-w-2xl text-muted-foreground">{m.description}</p>

          <div className="mt-6 grid grid-cols-3 gap-4 border-t border-border pt-4">
            <div>
              <span className="text-xs uppercase tracking-wider text-muted-foreground">Followers</span>
              <p className="text-lg font-semibold">{m.followers_count}</p>
            </div>
            <div>
              <span className="text-xs uppercase tracking-wider text-muted-foreground">Listings</span>
              <p className="text-lg font-semibold">{listings.data?.length ?? 0}</p>
            </div>
            <div>
              <span className="text-xs uppercase tracking-wider text-muted-foreground">Rating</span>
              <p className="text-lg font-semibold">{avg ? `${avg}★ (${reviewList.length})` : "No reviews yet"}</p>
            </div>
          </div>
        </div>
      </div>

      <h2 className="editorial-enter mb-2 mt-6 text-sm font-semibold">Listings</h2>
      <div className="editorial-enter mb-6 grid grid-cols-2 gap-4 sm:grid-cols-3">
        {listings.isPending && Array.from({ length: 3 }, (_, i) => <Skeleton key={i} className="aspect-square" />)}
        {listings.isSuccess && listings.data.length === 0 && (
          <div className="col-span-full">
            <EmptyState icon={<Store size={20} />} title="No listings yet" />
          </div>
        )}
        {listings.data?.map((item) => (
          <Link key={item.id} to={`/listings/${item.id}`} className="panel overflow-hidden transition-shadow hover:shadow-lg">
            <div className="grid aspect-square place-items-center bg-accent">
              {item.cover_photo ? <img src={item.cover_photo} alt="" className="h-full w-full object-cover" /> : <span className="text-xs text-muted-foreground">No photo</span>}
            </div>
            <div className="p-2">
              <p className="truncate text-sm font-medium">{item.title}</p>
              <p className="text-sm font-semibold text-primary">{naira(item.price)}</p>
            </div>
          </Link>
        ))}
      </div>

      <h2 className="editorial-enter mb-2 text-sm font-semibold">Reviews</h2>
      <div className="panel editorial-enter p-4">
        {reviewList.length === 0 && <p className="text-sm text-muted-foreground">No reviews yet.</p>}
        {reviewList.map((r) => (
          <div key={r.id} className="border-b border-border py-2 text-sm last:border-0">
            <Stars rating={r.rating} />
            {r.comment && <p className="text-muted-foreground">{r.comment}</p>}
          </div>
        ))}
      </div>
    </div>
  );
}
