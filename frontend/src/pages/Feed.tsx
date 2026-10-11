import { useQuery } from "@tanstack/react-query";
import { Bell, Home, MessageCircle, Package, ShieldCheck, ShoppingBag, Store, UserRound, type LucideIcon } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "@/components/AppLink";
import { FollowButton } from "@/components/FollowButton";
import { ListingCard } from "@/components/ListingCard";
import { Avatar, EmptyState, ErrorState, ListingSkeleton, Pill, Skeleton } from "@/components/ui";
import { api, rows } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { usePrefs } from "@/lib/prefs";
import { displayName } from "@/lib/types";
import { cn, naira } from "@/lib/utils";

const ESCROW_HELD = ["paid_escrow", "courier_assigned", "in_transit", "delivered", "confirmed", "disputed"];
const IN_PROGRESS = ["pending_payment", ...ESCROW_HELD];

const NAV: { to: string; label: string; icon: LucideIcon; end?: boolean }[] = [
  { to: "/feed", label: "Home feed", icon: Home, end: true },
  { to: "/marketplace", label: "Marketplace", icon: Store },
  { to: "/orders", label: "My orders", icon: Package },
  { to: "/messages", label: "Messages", icon: MessageCircle },
  { to: "/notifications", label: "Notifications", icon: Bell },
  { to: "/profile", label: "Profile", icon: UserRound },
];

export function FeedPage() {
  const { user, loggedIn } = useAuth();
  const prefs = usePrefs();
  const [scope, setScope] = useState<"all" | "verified">("all");
  const [categoryId, setCategoryId] = useState<number | null>(null);

  const categories = useQuery({ queryKey: ["categories"], queryFn: api.listCategories, staleTime: 10 * 60_000 });
  const feed = useQuery({
    queryKey: ["feed", loggedIn],
    queryFn: async () => rows(loggedIn ? await api.getFeed() : await api.listListings()),
  });
  const orders = useQuery({ queryKey: ["orders"], queryFn: async () => rows(await api.listOrders()), enabled: loggedIn });
  const merchants = useQuery({ queryKey: ["merchants"], queryFn: async () => rows(await api.listMerchants()) });

  const listings = feed.data ?? [];
  const visible = useMemo(
    () => listings.filter((l) => (scope === "all" || l.merchant) && (categoryId === null || l.category === categoryId)),
    [listings, scope, categoryId],
  );
  const trending = useMemo(() => [...listings].sort((a, b) => b.likes_count - a.likes_count).slice(0, 4), [listings]);

  const myBuying = (orders.data ?? []).filter((o) => o.buyer === user?.id);
  const inProgress = myBuying.filter((o) => IN_PROGRESS.includes(o.status)).length;
  const heldOrders = myBuying.filter((o) => ESCROW_HELD.includes(o.status));
  const heldTotal = heldOrders.reduce((sum, o) => sum + Number(o.price), 0);

  return (
    <div className="grid grid-cols-1 gap-5 md:grid-cols-[210px_minmax(0,1fr)] xl:grid-cols-[220px_minmax(0,1fr)_290px]">
      {/* LEFT RAIL */}
      <aside className="hidden self-start md:sticky md:top-20 md:flex md:flex-col md:gap-5">
        <section className="panel editorial-enter p-4">
          {loggedIn && user ? (
            <>
              <div className="flex items-center gap-3">
                <Avatar src={user.profile?.avatar} name={displayName(user)} size={40} />
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold">{displayName(user)}</p>
                  <p className="truncate text-xs text-muted-foreground">{user.profile?.location || "Uyo"} · Buyer</p>
                </div>
              </div>
              <Link to="/orders" className="mt-3 block rounded-md bg-accent px-3 py-2 text-xs text-primary transition-colors hover:bg-accent/70">
                {inProgress} escrow order{inProgress === 1 ? "" : "s"} in progress
              </Link>
            </>
          ) : (
            <>
              <p className="text-sm font-semibold">Welcome to Choropia</p>
              <p className="mt-1 text-xs leading-relaxed text-muted-foreground">Log in to like, message sellers and buy with escrow.</p>
              <Link to="/login" className="mt-3 block rounded-md bg-primary px-3 py-2 text-center text-xs font-semibold text-primary-foreground shadow-button transition-colors hover:bg-primary-hover">
                Log in or join
              </Link>
            </>
          )}
        </section>

        <nav className="panel editorial-enter p-2 text-sm" style={prefs.stagger(1)}>
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <Link
              key={to}
              to={to}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2.5 transition-colors",
                end ? "bg-accent font-semibold text-primary" : "text-muted-foreground hover:bg-accent hover:text-foreground",
              )}
            >
              <Icon size={15} />
              {label}
            </Link>
          ))}
        </nav>

        {(categories.data?.length ?? 0) > 0 && (
          <section className="editorial-enter rounded-lg bg-foreground p-4 text-background shadow-sm" style={prefs.stagger(2)}>
            <p className="text-xs font-semibold uppercase text-background/60">Categories</p>
            <div className="mt-3 flex flex-wrap gap-2 text-xs">
              {categories.data!.map((c) => (
                <button
                  key={c.id}
                  onClick={() => setCategoryId(categoryId === c.id ? null : c.id)}
                  className={cn("rounded-full px-2.5 py-1.5 transition-colors", categoryId === c.id ? "bg-background text-foreground" : "bg-background/10 hover:bg-background/20")}
                >
                  {c.name}
                </button>
              ))}
            </div>
          </section>
        )}
      </aside>

      {/* FEED */}
      <section className="min-w-0">
        <Link to="/listings/new" className="editorial-enter panel flex items-center gap-3 p-3 transition-shadow hover:shadow-md">
          <span className="grid size-9 place-items-center rounded-md bg-accent text-lg font-semibold text-primary">+</span>
          <span className="text-sm text-muted-foreground">List a new item or service for Uyo buyers…</span>
          <span className="ml-auto hidden text-xs font-semibold text-primary sm:block">Post listing</span>
        </Link>

        <div className="editorial-enter mt-5 flex items-center gap-2 overflow-x-auto pb-1 text-xs" style={prefs.stagger(0)}>
          <Pill active={scope === "all"} onClick={() => setScope("all")}>
            All
          </Pill>
          <Pill active={scope === "verified"} onClick={() => setScope("verified")}>
            Verified storefronts
          </Pill>
          {categoryId !== null && (
            <Pill active onClick={() => setCategoryId(null)}>
              {categories.data?.find((c) => c.id === categoryId)?.name} ✕
            </Pill>
          )}
          <span className="ml-auto hidden whitespace-nowrap text-muted-foreground sm:block">Freshest first</span>
        </div>

        <div className={cn("mt-5 grid", prefs.density === "compact" ? "gap-3" : "gap-5", prefs.view === "grid" ? "sm:grid-cols-2" : "grid-cols-1")}>
          {feed.isPending &&
            Array.from({ length: 3 }, (_, i) => <ListingSkeleton key={i} view={prefs.view} />)}
          {feed.isError && (
            <div className="col-span-full">
              <ErrorState message={(feed.error as Error).message} onRetry={() => feed.refetch()} />
            </div>
          )}
          {feed.isSuccess && visible.length === 0 && (
            <div className="panel col-span-full">
              <EmptyState
                icon={<ShoppingBag size={20} />}
                title={listings.length ? "Nothing matches those filters" : "No listings yet"}
                hint={listings.length ? "Try a different category or show all listings." : "Be the first to post something for sale in Uyo."}
                action={
                  listings.length ? (
                    <Pill onClick={() => (setScope("all"), setCategoryId(null))}>Clear filters</Pill>
                  ) : (
                    <Link to="/listings/new" className="text-xs font-semibold text-primary hover:underline">
                      Post a listing
                    </Link>
                  )
                }
              />
            </div>
          )}
          {visible.map((item, index) => (
            <ListingCard key={item.id} item={item} view={prefs.view} density={prefs.density} style={prefs.stagger(index + 1)} />
          ))}
        </div>
      </section>

      {/* RIGHT RAIL */}
      <aside className="hidden self-start xl:sticky xl:top-20 xl:flex xl:flex-col xl:gap-5">
        <section className="panel editorial-enter overflow-hidden" style={prefs.stagger(1)}>
          <div className="flex justify-between px-4 py-3">
            <h2 className="text-sm font-semibold">Trending in Uyo</h2>
            <span className="text-xs text-muted-foreground">Most liked</span>
          </div>
          {feed.isPending && (
            <div className="space-y-3 border-t border-border p-4">
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-4 w-2/3" />
            </div>
          )}
          {trending.map((item, i) => (
            <Link key={item.id} to={`/listings/${item.id}`} className="flex items-center gap-3 border-t border-border px-4 py-3 text-sm transition-colors hover:bg-accent">
              <span className="text-xs text-muted-foreground">0{i + 1}</span>
              <span className="min-w-0 flex-1 truncate">{item.title}</span>
              <span className="text-xs text-muted-foreground">{naira(item.price)}</span>
            </Link>
          ))}
          {feed.isSuccess && trending.length === 0 && <p className="border-t border-border px-4 py-3 text-xs text-muted-foreground">Nothing trending yet.</p>}
        </section>

        <section className="panel editorial-enter p-4" style={prefs.stagger(2)}>
          <div className="flex gap-3">
            <span className="grid size-8 shrink-0 place-items-center rounded-md bg-success/15 text-success">
              <ShieldCheck size={17} />
            </span>
            <div>
              <h2 className="text-sm font-semibold">Choropia Escrow</h2>
              <p className="mt-1 text-xs leading-relaxed text-muted-foreground">Funds stay protected until you confirm delivery.</p>
            </div>
          </div>
          {loggedIn && (
            <>
              <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-accent">
                <div className="h-full bg-success transition-[width] duration-700" style={{ width: `${myBuying.length ? Math.min(100, (heldOrders.length / myBuying.length) * 100) : 0}%` }} />
              </div>
              <p className="mt-2 text-xs text-muted-foreground">
                {heldOrders.length} order{heldOrders.length === 1 ? "" : "s"} protected · {naira(heldTotal)} held
              </p>
            </>
          )}
        </section>

        <section className="panel editorial-enter p-4" style={prefs.stagger(3)}>
          <h2 className="text-sm font-semibold">Storefronts to follow</h2>
          <div className="mt-3 space-y-3">
            {merchants.isPending && <Skeleton className="h-9 w-full" />}
            {(merchants.data ?? []).slice(0, 3).map((m) => (
              <div key={m.id} className="flex items-center gap-2">
                <Link to={`/merchants/${m.id}`} className="flex min-w-0 flex-1 items-center gap-2">
                  <Avatar src={m.logo} name={m.business_name} size={36} />
                  <div className="min-w-0">
                    <p className="truncate text-xs font-semibold">{m.business_name}</p>
                    <p className="text-xs text-muted-foreground">{m.followers_count} follower{m.followers_count === 1 ? "" : "s"}</p>
                  </div>
                </Link>
                <FollowButton merchantId={m.id} className="min-h-8 px-2 text-xs" />
              </div>
            ))}
            {merchants.isSuccess && merchants.data.length === 0 && <p className="text-xs text-muted-foreground">No storefronts yet.</p>}
          </div>
        </section>
      </aside>
    </div>
  );
}
