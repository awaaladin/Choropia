import { ArrowRight, MapPin, MessageCircle, ShieldAlert } from "lucide-react";
import { Link } from "@/components/AppLink";
import { PublicShell } from "@/components/PublicShell";
import { useReveal } from "@/lib/useReveal";

export function ContactPage() {
  useReveal();
  return (
    <PublicShell>
      <section className="mx-auto max-w-[1400px] px-5 py-14 lg:px-8 lg:py-20">
        <p className="page-enter eyebrow">LET'S TALK</p>
        <h1 className="page-enter mt-4 text-4xl font-semibold sm:text-6xl">
          Good conversations
          <br />
          start here.
        </h1>
        <p className="mt-6 max-w-xl text-base leading-7 text-muted-foreground">
          Most questions have a faster answer than a contact form — here's where to take them.
        </p>

        <div className="mt-12 grid gap-6 sm:grid-cols-3">
          <div data-reveal className="border-t border-border py-6">
            <MessageCircle className="text-primary" size={22} />
            <h2 className="mt-4 font-semibold">A question about an item or order?</h2>
            <p className="mt-2 text-sm leading-7 text-muted-foreground">The seller is the best person to ask about condition, availability, and pickup — message them directly.</p>
            <Link to="/messages" className="mt-4 inline-flex items-center gap-2 text-sm font-semibold text-primary">
              Open messages <ArrowRight size={15} />
            </Link>
          </div>
          <div data-reveal className="border-t border-border py-6">
            <ShieldAlert className="text-primary" size={22} />
            <h2 className="mt-4 font-semibold">Something wrong with an order?</h2>
            <p className="mt-2 text-sm leading-7 text-muted-foreground">Open a dispute right from the order page — a moderator reviews it before escrow is released.</p>
            <Link to="/orders" className="mt-4 inline-flex items-center gap-2 text-sm font-semibold text-primary">
              Go to your orders <ArrowRight size={15} />
            </Link>
          </div>
          <div data-reveal className="border-t border-border py-6">
            <MapPin className="text-primary" size={22} />
            <h2 className="mt-4 font-semibold">Rooted in Uyo</h2>
            <p className="mt-2 text-sm leading-7 text-muted-foreground">Akwa Ibom, Nigeria</p>
            <Link to="/how-it-works" className="mt-4 inline-flex items-center gap-2 text-sm font-semibold text-primary">
              Find an answer in our guide <ArrowRight size={15} />
            </Link>
          </div>
        </div>
      </section>
    </PublicShell>
  );
}
