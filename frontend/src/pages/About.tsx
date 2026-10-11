import { ArrowUpRight, Eye, HeartHandshake, MapPin } from "lucide-react";
import community from "@/assets/choropia-community.jpg";
import exchange from "@/assets/choropia-exchange.jpg";
import { Link } from "@/components/AppLink";
import { PublicShell } from "@/components/PublicShell";
import { useReveal } from "@/lib/useReveal";

const VALUES = [
  [MapPin, "Stay close", "Celebrate local businesses and keep everyday discovery rooted in our community."],
  [Eye, "Keep it clear", "Honest descriptions, useful details, and conversations before commitments."],
  [HeartHandshake, "Put people first", "Respect for the person on the other side of every message and every exchange."],
] as const;

export function AboutPage() {
  useReveal();
  return (
    <PublicShell>
      <section className="mx-auto max-w-[1400px] px-5 pb-12 pt-14 lg:px-8 lg:pt-20">
        <p className="page-enter eyebrow">OUR REASON FOR BEING</p>
        <h1 className="page-enter mt-4 max-w-3xl text-4xl font-semibold leading-tight sm:text-6xl">
          Choropia.
          <br />
          Local at heart.
        </h1>
        <p className="page-enter mt-6 max-w-xl text-base leading-7 text-muted-foreground">
          Good trade starts with people. We're building a place where the everyday talent, enterprise, and generosity of Uyo can be
          seen — with every purchase held in escrow until the buyer confirms delivery.
        </p>
      </section>
      <div className="mx-auto max-w-[1400px] px-5 lg:px-8">
        <img src={exchange} alt="Neighbours sharing a friendly parcel handover" className="h-[320px] w-full rounded-md object-cover sm:h-[500px]" />
      </div>
      <section className="mx-auto grid max-w-[1100px] gap-10 px-5 py-16 md:grid-cols-2 lg:py-24">
        <h2 data-reveal className="text-3xl font-semibold">
          The best things are
          <br />
          often right here.
        </h2>
        <div data-reveal className="space-y-5 text-sm leading-7 text-muted-foreground">
          <p>Local markets have always been places of connection: a familiar face, an honest recommendation, a conversation that turns into a good deal.</p>
          <p>Choropia carries that spirit online. From independent makers to neighbourhood merchants and people giving something a second life, everyone has a place here.</p>
          <p>Our aim is simple: make local discovery more welcoming, and the details of buying and selling clearer — escrow holds every payment until you've confirmed your item arrived.</p>
        </div>
      </section>
      <section className="border-y border-border bg-panel">
        <div className="mx-auto grid max-w-[1400px] gap-8 px-5 py-16 sm:grid-cols-3 lg:px-8">
          {VALUES.map(([Icon, title, copy]) => (
            <article data-reveal key={title}>
              <Icon size={24} className="text-primary" />
              <h2 className="mt-6 text-xl font-semibold">{title}</h2>
              <p className="mt-3 text-sm leading-7 text-muted-foreground">{copy}</p>
            </article>
          ))}
        </div>
      </section>
      <section className="mx-auto grid max-w-[1400px] items-center gap-10 px-5 py-16 md:grid-cols-2 lg:px-8">
        <img data-reveal src={community} alt="A fabric artisan surrounded by her work" loading="lazy" className="aspect-[4/3] w-full rounded-md object-cover" />
        <div data-reveal>
          <p className="eyebrow">ROOM FOR YOUR STORY</p>
          <h2 className="mt-4 text-3xl font-semibold">What you make matters.</h2>
          <p className="mt-5 max-w-md text-sm leading-7 text-muted-foreground">
            Have something to share with your community? Give your craft, shop, or next great find a home on Choropia.
          </p>
          <Link to="/merchants/apply" className="mt-6 inline-flex items-center gap-2 text-sm font-semibold text-primary">
            Become a merchant <ArrowUpRight size={17} />
          </Link>
        </div>
      </section>
    </PublicShell>
  );
}
