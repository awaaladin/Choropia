import { useQuery } from "@tanstack/react-query";
import { ArrowRight, ArrowUpRight, MapPin, MessageCircle, ShieldCheck } from "lucide-react";
import community from "@/assets/choropia-community.jpg";
import exchange from "@/assets/choropia-exchange.jpg";
import { Link } from "@/components/AppLink";
import { LinkButton } from "@/components/Button";
import { PublicShell } from "@/components/PublicShell";
import { Skeleton } from "@/components/ui";
import { api, rows } from "@/lib/api";
import { useReveal } from "@/lib/useReveal";
import { naira } from "@/lib/utils";

const PILLARS = [
  { icon: MapPin, label: "Local discovery" },
  { icon: MessageCircle, label: "Real conversations" },
  { icon: ShieldCheck, label: "Thoughtful trade" },
] as const;

const STEPS = [
  ["01", "Find something you love", "Browse local listings and get to know the person behind them."],
  ["02", "Start a conversation", "Ask questions, confirm the details, and agree on a handover."],
  ["03", "Make it yours", "Pay into escrow and confirm once your item has arrived."],
] as const;

export function LandingPage() {
  useReveal();
  const listings = useQuery({ queryKey: ["listings", { landing: true }], queryFn: async () => rows(await api.listListings()) });
  const featured = (listings.data ?? []).slice(0, 3);

  return (
    <PublicShell>
      <section className="public-hero relative isolate overflow-hidden">
        <img
          src={community}
          alt="A textile artisan arranging indigo fabrics in her shop"
          fetchPriority="high"
          className="absolute inset-0 -z-20 h-full w-full object-cover object-[65%_center]"
        />
        <div className="hero-shade absolute inset-0 -z-10" />
        <div className="mx-auto flex h-full max-w-[1400px] flex-col justify-end px-5 pb-12 pt-20 lg:px-8 lg:pb-16">
          <p className="page-enter mb-5 flex items-center gap-2 text-xs font-semibold uppercase text-hero-foreground/80">
            <span className="size-1.5 rounded-full bg-success" />
            Rooted in Uyo. Open to you.
          </p>
          <h1 className="page-enter max-w-2xl text-5xl font-semibold leading-[1.08] text-hero-foreground sm:text-7xl">
            Choropia<span className="text-hero-accent">.</span>
            <br />
            <span className="text-4xl sm:text-6xl">
              Good things.
              <br />
              Closer to home.
            </span>
          </h1>
          <p className="page-enter mt-6 max-w-md text-base leading-7 text-hero-foreground/85">
            Behind every good find is a real person. Discover the makers, merchants, and everyday treasures in your neighbourhood.
          </p>
          <div className="page-enter mt-8 flex flex-wrap gap-3">
            <LinkButton to="/marketplace" variant="secondary" className="h-11 px-5">
              Find your next good thing <ArrowUpRight size={17} />
            </LinkButton>
            <Link to="/how-it-works" className="inline-flex h-11 items-center gap-2 px-3 text-sm font-semibold text-hero-foreground">
              How it works <ArrowRight size={16} />
            </Link>
          </div>
          <div className="mt-10 flex items-center gap-2 text-xs text-hero-foreground/75">
            <MapPin size={14} /> Uyo, Akwa Ibom
          </div>
        </div>
      </section>

      <div className="border-b border-border bg-panel">
        <div className="mx-auto grid max-w-[1400px] grid-cols-3 gap-3 px-5 py-6 text-xs font-semibold sm:text-sm lg:px-8">
          {PILLARS.map(({ icon: Icon, label }) => (
            <span key={label} className="flex items-center justify-center gap-2">
              <Icon size={17} className="shrink-0 text-primary" />
              {label}
            </span>
          ))}
        </div>
      </div>

      <section className="mx-auto max-w-[1400px] px-5 py-16 lg:px-8 lg:py-24">
        <div data-reveal className="flex flex-wrap items-end justify-between gap-5">
          <div>
            <p className="eyebrow">THE LOCAL EDIT</p>
            <h2 className="mt-3 text-3xl font-semibold sm:text-4xl">Not far. Not ordinary.</h2>
          </div>
          <Link to="/marketplace" className="flex items-center gap-2 text-sm font-semibold text-primary">
            Explore the marketplace <ArrowUpRight size={17} />
          </Link>
        </div>
        <div className="mt-8 grid gap-6 sm:grid-cols-3">
          {listings.isPending && Array.from({ length: 3 }, (_, i) => <Skeleton key={i} className="aspect-[4/3] w-full" />)}
          {featured.map((item, index) => (
            <Link data-reveal key={item.id} to={`/listings/${item.id}`} className="group">
              <div className="relative overflow-hidden rounded-md">
                {item.cover_photo ? (
                  <img
                    src={item.cover_photo}
                    alt={item.title}
                    loading="lazy"
                    className="aspect-[4/3] w-full object-cover transition-transform duration-700 group-hover:scale-[1.035]"
                  />
                ) : (
                  <div className="grid aspect-[4/3] w-full place-items-center bg-accent text-xs text-muted-foreground">No photo</div>
                )}
                <span className="absolute left-3 top-3 rounded-sm bg-panel px-2 py-1 text-xs backdrop-blur-md">0{index + 1}</span>
              </div>
              <div className="mt-4 flex items-start justify-between gap-3">
                <h3 className="text-base font-semibold">{item.title}</h3>
                <ArrowUpRight size={18} className="shrink-0 text-primary" />
              </div>
              <p className="mt-2 text-xs text-muted-foreground">
                {item.seller_name} · {item.location || "Uyo"}
              </p>
              <p className="mt-3 text-sm font-semibold text-primary">{naira(item.price)}</p>
            </Link>
          ))}
          {listings.isSuccess && featured.length === 0 && (
            <p className="col-span-full text-sm text-muted-foreground">No listings yet — be the first to post one.</p>
          )}
        </div>
      </section>

      <section className="border-y border-border bg-panel">
        <div className="mx-auto grid max-w-[1400px] items-center gap-10 px-5 py-16 md:grid-cols-2 lg:gap-20 lg:px-8 lg:py-24">
          <div data-reveal className="overflow-hidden rounded-md">
            <img src={exchange} alt="A local seller and customer exchanging a parcel" loading="lazy" className="aspect-[5/4] w-full object-cover" />
          </div>
          <div data-reveal>
            <p className="eyebrow">MORE THAN A TRANSACTION</p>
            <h2 className="mt-4 text-3xl font-semibold leading-tight sm:text-4xl">
              A neighbourhood.
              <br />
              Not just a marketplace.
            </h2>
            <p className="mt-6 max-w-md text-sm leading-7 text-muted-foreground">
              The fabric made by a neighbour. The laptop ready for a second chapter. The fresh ingredients just down the road. Choropia
              brings everyday local trade into one welcoming place — with every purchase held in escrow until you confirm delivery.
            </p>
            <Link to="/about" className="mt-7 inline-flex items-center gap-2 text-sm font-semibold text-primary">
              Meet Choropia <ArrowRight size={17} />
            </Link>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-[1400px] px-5 py-16 lg:px-8 lg:py-24">
        <div data-reveal className="grid gap-8 md:grid-cols-[1fr_1.3fr]">
          <div>
            <p className="eyebrow">SMALL STEPS. GOOD CONNECTIONS.</p>
            <h2 className="mt-4 text-3xl font-semibold sm:text-4xl">
              From a first look
              <br />
              to a good find.
            </h2>
            <Link to="/how-it-works" className="mt-6 inline-flex items-center gap-2 text-sm font-semibold text-primary">
              A closer look at how it works <ArrowRight size={16} />
            </Link>
          </div>
          <div>
            {STEPS.map(([n, title, copy]) => (
              <div key={n} className="grid grid-cols-[40px_1fr] gap-5 border-t border-border py-6">
                <span className="text-xs font-semibold text-primary">{n}</span>
                <div>
                  <h3 className="font-semibold">{title}</h3>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">{copy}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="border-t border-border bg-primary text-primary-foreground">
        <div data-reveal className="mx-auto flex max-w-[1400px] flex-col justify-between gap-8 px-5 py-14 sm:flex-row sm:items-center lg:px-8">
          <div>
            <p className="text-xs uppercase opacity-75">YOUR NEXT CHAPTER STARTS NEARBY</p>
            <h2 className="mt-3 text-3xl font-semibold">
              Something to find.
              <br />
              Something to share.
            </h2>
          </div>
          <LinkButton to="/listings/new" variant="secondary" className="h-11 px-5">
            Sell something <ArrowUpRight size={17} />
          </LinkButton>
        </div>
      </section>
    </PublicShell>
  );
}
