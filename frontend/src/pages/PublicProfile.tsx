import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { BadgeCheck, MessageCircle, PackageOpen, UserRound } from "lucide-react";
import { useState } from "react";
import { useNavigate, useParams } from "react-router";
import { toast } from "sonner";
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
  const [tab, setTab] = useState<"listings" | "about">("listings");
  const validUserId = Number.isSafeInteger(userId) && userId > 0;
  const profile = useQuery({ queryKey: ["public-profile", userId], queryFn: () => api.publicProfile(userId), enabled: validUserId });
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
      navigate(`/messages/${conversation.id}`);
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
          onClick={() => setTab("about")}
          aria-current={tab === "about" ? "page" : undefined}
          className={`flex items-center gap-2 border-b-2 px-4 py-3 text-sm font-semibold ${tab === "about" ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"}`}
        >
          <UserRound size={16} /> About
        </button>
      </nav>

      {tab === "about" ? (
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
                <Link key={listing.id} to={`/listings/${listing.id}`} className="panel overflow-hidden transition-colors hover:border-primary/50">
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
