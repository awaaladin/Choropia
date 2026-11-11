import { listingPath, chatPath } from "@/lib/links";
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { BadgeCheck, MessageCircle, PackageOpen, Star, UserRound } from "lucide-react";
import { useState } from "react";
import { useNavigate, useParams } from "react-router";
import { toast } from "sonner";
import { SellerRating } from "@/components/SellerRating";
import { Avatar, ErrorState, Skeleton } from "@/components/ui";
import { Button } from "@/components/Button";
import { api, rows } from "@/lib/api";
import { errorMessage } from "@/lib/actions";
import { useAuth } from "@/lib/auth";
import { naira } from "@/lib/utils";
import { Link } from "@/components/AppLink";

export function PublicProfilePage() {
  const { id } = useParams();
  const userId = Number(id);
  const navigate = useNavigate();
  const { loggedIn, user: signedInUser } = useAuth();
  const [tab, setTab] = useState<"listings" | "reviews" | "about">("listings");
  const validUserId = Number.isSafeInteger(userId) && userId > 0;
  const profile = useQuery({ queryKey: ["public-profile", userId], queryFn: () => api.publicProfile(userId), enabled: validUserId });
  const summary = useQuery({ queryKey: ["review-summary", userId], queryFn: () => api.reviewSummary(userId), enabled: validUserId, staleTime: 5 * 60_000 });
  const reviews = useQuery({
    queryKey: ["reviews", userId],
    queryFn: async () => rows(await api.listReviewsFor(userId)),
    enabled: validUserId && tab === "reviews" && !!summary.data?.eligible,
  });
  const listings = useInfiniteQuery({
    queryKey: ["public-profile-listings", userId],
    initialPageParam: 1,
    queryFn: ({ pageParam }) => api.publicProfileListings(userId, pageParam),
    getNextPageParam: (lastPage, _pages, lastPageParam) =>
      !Array.isArray(lastPage) && lastPage.next ? lastPageParam + 1 : undefined,
    enabled: validUserId,
  });

  const message = async () => {
    if (!loggedIn) {
      navigate("/login");
      return;
    }
    try {
      const conversation = await api.openConversation(userId);
      navigate(chatPath(conversation));
    } catch (error) {
      toast.error(errorMessage(error));
    }
  };

  if (!validUserId) return <ErrorState message="This profile link is invalid." />;
  if (profile.isPending) return <Skeleton className="mx-auto h-64 max-w-2xl" />;
  if (profile.isError) return <ErrorState message="We couldn't load this profile." onRetry={() => profile.refetch()} />;
  const user = profile.data;
  const listingItems = listings.data?.pages.flatMap(rows) ?? [];
  const joinedAt = new Date(user.joined_at);
  const joinedLabel = Number.isNaN(joinedAt.getTime()) ? "—" : joinedAt.toLocaleDateString(undefined, { year: "numeric", month: "long" });

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <header className="panel flex flex-wrap items-center gap-4 p-6">
        <Avatar src={user.avatar_url} name={user.display_name} size={80} />
        <div className="min-w-0 flex-1">
          <h1 className="flex items-center gap-2 font-display text-xl font-bold">
            {user.display_name}
            {user.verified && <BadgeCheck size={18} className="text-primary" aria-label="Verified seller" />}
          </h1>
          <p className="text-sm text-muted-foreground">@{user.username}</p>
          <SellerRating userId={userId} className="mt-1" />
          {user.bio && <p className="mt-2 text-sm">{user.bio}</p>}
        </div>
        {signedInUser?.id !== user.id && (
          <Button onClick={message}><MessageCircle size={15} /> Message</Button>
        )}
      </header>

      <nav className="flex gap-2 border-b border-border" aria-label="Public profile sections">
        <button
          type="button"
          onClick={() => setTab("listings")}
          aria-current={tab === "listings" ? "page" : undefined}
          className={`flex items-center gap-2 border-b-2 px-4 py-3 text-sm font-semibold ${tab === "listings" ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"}`}
        >
          <PackageOpen size={16} /> Listings
        </button>
        <button
          type="button"
          onClick={() => setTab("reviews")}
          aria-current={tab === "reviews" ? "page" : undefined}
          className={`flex items-center gap-2 border-b-2 px-4 py-3 text-sm font-semibold ${tab === "reviews" ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"}`}
        >
          <Star size={16} /> Reviews{summary.data?.eligible && summary.data.count > 0 ? ` (${summary.data.count})` : ""}
        </button>
        <button
          type="button"
          onClick={() => setTab("about")}
          aria-current={tab === "about" ? "page" : undefined}
          className={`flex items-center gap-2 border-b-2 px-4 py-3 text-sm font-semibold ${tab === "about" ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"}`}
        >
          <UserRound size={16} /> About
        </button>
      </nav>

      {tab === "reviews" ? (
        <section className="panel p-5" aria-label={`Reviews of ${user.display_name}`}>
          {summary.data && !summary.data.eligible && (
            <p className="text-sm text-muted-foreground">Reviews appear once a seller has posted a few listings and completed a sale.</p>
          )}
          {summary.data?.eligible && (
            <div className="mb-4 flex items-baseline gap-3">
              <span className="font-display text-3xl font-bold">{summary.data.average ? summary.data.average.toFixed(1) : "-"}</span>
              <span className="text-sm text-muted-foreground">
                {summary.data.count} review{summary.data.count === 1 ? "" : "s"}
              </span>
            </div>
          )}
          {summary.data?.eligible && reviews.isSuccess && (reviews.data ?? []).length === 0 && <p className="text-sm text-muted-foreground">No reviews yet.</p>}
          {(reviews.data ?? []).map((r) => (
            <div key={r.id} className="border-t border-border py-3 text-sm first:border-0">
              <div className="flex items-center justify-between gap-2">
                <span className="text-primary">
                  {"★".repeat(r.rating)}
                  <span className="text-border">{"★".repeat(5 - r.rating)}</span>
                </span>
                <span className="text-xs text-muted-foreground">{r.reviewer_name}</span>
              </div>
              {r.comment && <p className="mt-1 text-muted-foreground">{r.comment}</p>}
            </div>
          ))}
        </section>
      ) : tab === "about" ? (
        <section className="panel space-y-5 p-5" aria-labelledby="about-heading">
          <h2 id="about-heading" className="font-display text-lg font-bold">About {user.display_name}</h2>
          <p className="text-sm text-muted-foreground">{user.bio || "This member hasn’t added a bio yet."}</p>
          <dl className="grid gap-4 sm:grid-cols-2">
            <div className="rounded-xl bg-accent p-4">
              <dt className="text-xs text-muted-foreground">Member since</dt>
              <dd className="mt-1 font-semibold">{joinedLabel}</dd>
            </div>
            <div className="rounded-xl bg-accent p-4">
              <dt className="text-xs text-muted-foreground">Completed sales</dt>
              <dd className="mt-1 font-semibold">{user.completed_sales}</dd>
            </div>
            <div className="rounded-xl bg-accent p-4">
              <dt className="text-xs text-muted-foreground">Account</dt>
              <dd className="mt-1 font-semibold">{user.verified ? "Verified seller" : "Community member"}</dd>
            </div>
          </dl>
        </section>
      ) : (
        <section aria-label={`${user.display_name}'s public listings`}>
          <div className="mb-3 flex items-baseline justify-between gap-3">
            <h2 className="font-display text-lg font-bold">Listings</h2>
            {listings.isSuccess && <span className="text-xs text-muted-foreground">{listingItems.length} shown</span>}
          </div>
          {listings.isPending && <Skeleton className="h-32 w-full" />}
          {listings.isError && <ErrorState message="We couldn't load these listings." onRetry={() => listings.refetch()} />}
          {listings.isSuccess && listingItems.length === 0 && (
            <p className="panel p-6 text-center text-sm text-muted-foreground">No public listings right now.</p>
          )}
          {listingItems.length > 0 && (
            <div className="grid gap-3 sm:grid-cols-2">
              {listingItems.map((listing) => (
                <Link key={listing.id} to={listingPath(listing)} className="panel overflow-hidden transition-colors hover:border-primary/50">
                  {listing.cover_photo ? (
                    <img src={listing.cover_photo} alt="" loading="lazy" className="aspect-[4/3] w-full object-cover" />
                  ) : (
                    <div className="grid aspect-[4/3] place-items-center bg-accent text-sm text-muted-foreground">No photo</div>
                  )}
                  <div className="p-3">
                    <div className="flex items-center justify-between gap-2">
                      <p className="truncate font-semibold">{listing.title}</p>
                      {listing.status === "sold" && <span className="shrink-0 rounded-full bg-accent px-2 py-1 text-xs text-muted-foreground">Sold</span>}
                    </div>
                    <p className="mt-1 font-mono text-sm">{naira(listing.price)}</p>
                  </div>
                </Link>
              ))}
            </div>
          )}
          {listings.hasNextPage && (
            <div className="mt-4 text-center">
              <Button variant="secondary" onClick={() => listings.fetchNextPage()} loading={listings.isFetchingNextPage}>
                Load more listings
              </Button>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
