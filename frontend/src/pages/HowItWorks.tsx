import { ArrowRight, Minus, Plus, ShieldCheck } from "lucide-react";
import { useState } from "react";
import exchange from "@/assets/choropia-exchange.jpg";
import { LinkButton } from "@/components/Button";
import { PublicShell } from "@/components/PublicShell";
import { Segmented } from "@/components/ui";
import { useReveal } from "@/lib/useReveal";

const BUY_STEPS = [
  ["Discover nearby", "Search by category, browse the marketplace, and open a listing to see its price, condition, and seller."],
  ["Ask before you agree", "Message the seller about availability, condition, and pickup or delivery."],
  ["Pay into escrow, then confirm", "Your payment is held until you've received the item — only then does the seller get paid."],
] as const;

const SELL_STEPS = [
  ["Give it a good introduction", "Add clear photos, an honest description, a price, and the item's condition."],
  ["Make the details clear", "Respond to questions and agree on handover details before completing a sale."],
  ["Deliver what you promised", "Prepare the item carefully, keep the buyer updated, and complete the agreed handover."],
] as const;

const FAQ = [
  ["What does escrow mean?", "When a buyer pays for an order, the money is held by Choropia, not sent straight to the seller. It's only released once the buyer confirms they received the item — or automatically a few days after delivery if nothing's reported wrong."],
  ["Can I arrange a pickup?", "Ask the seller about pickup before committing. Confirm the location and time, choose a public place, and inspect the item before confirming receipt."],
  ["How do I choose a seller?", "Read the full listing, check the seller's storefront and reviews, and ask for recent photos or additional details. Never share a password, verification code, or bank PIN."],
  ["What if something goes wrong?", "If an item doesn't arrive or isn't as described, open a dispute from your order page before confirming receipt — a moderator reviews it before anything is released."],
] as const;

export function HowItWorksPage() {
  useReveal();
  const [mode, setMode] = useState<"buy" | "sell">("buy");
  const [open, setOpen] = useState<number | null>(0);
  const steps = mode === "buy" ? BUY_STEPS : SELL_STEPS;

  return (
    <PublicShell>
      <section className="mx-auto max-w-[1400px] px-5 py-14 lg:px-8 lg:py-20">
        <p className="page-enter eyebrow">A GOOD TRADE, STEP BY STEP</p>
        <h1 className="page-enter mt-4 text-4xl font-semibold sm:text-6xl">How Choropia works.</h1>
        <p className="mt-6 max-w-xl text-base leading-7 text-muted-foreground">A little discovery. A real conversation. Something good changing hands.</p>

        <div className="mt-8 max-w-xs">
          <Segmented options={["buy", "sell"] as const} value={mode} onChange={setMode} labels={{ buy: "Buying", sell: "Selling" }} />
        </div>

        <div key={mode} className="page-enter mt-10 grid gap-8 md:grid-cols-3">
          {steps.map(([title, copy], i) => (
            <article key={title} className="border-t border-border pt-6">
              <span className="text-3xl font-semibold text-primary/50">0{i + 1}</span>
              <h2 className="mt-5 text-xl font-semibold">{title}</h2>
              <p className="mt-3 text-sm leading-7 text-muted-foreground">{copy}</p>
            </article>
          ))}
        </div>
        <LinkButton to={mode === "buy" ? "/marketplace" : "/listings/new"} className="mt-8 h-11 px-5">
          {mode === "buy" ? "Explore marketplace" : "Create a listing"} <ArrowRight size={17} />
        </LinkButton>
      </section>

      <section className="border-y border-border bg-panel">
        <div className="mx-auto grid max-w-[1400px] items-center gap-10 px-5 py-14 md:grid-cols-2 lg:px-8">
          <img data-reveal src={exchange} alt="A friendly local purchase handover" loading="lazy" className="aspect-[4/3] w-full rounded-md object-cover" />
          <div data-reveal>
            <ShieldCheck className="text-success" size={28} />
            <h2 className="mt-5 text-3xl font-semibold">A little care goes a long way.</h2>
            <ul className="mt-6 space-y-4 text-sm leading-6 text-muted-foreground">
              <li>Keep conversations on the platform and confirm all important details.</li>
              <li>Don't pay unexpected fees or share private verification codes.</li>
              <li>Meet in a public place for pickup. Let someone know where you're going.</li>
              <li>Check your item before marking an order as received.</li>
            </ul>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-3xl px-5 py-16">
        <p className="eyebrow">A FEW THINGS WORTH KNOWING</p>
        <h2 className="mb-8 mt-4 text-3xl font-semibold">Questions, answered.</h2>
        {FAQ.map(([q, a], i) => (
          <div key={q} className="border-t border-border">
            <button
              className="flex h-auto w-full items-center justify-between gap-4 py-5 text-left text-foreground"
              aria-expanded={open === i}
              aria-controls={`answer-${i}`}
              onClick={() => setOpen(open === i ? null : i)}
            >
              <span className="font-medium">{q}</span>
              {open === i ? <Minus size={17} className="shrink-0" /> : <Plus size={17} className="shrink-0" />}
            </button>
            {open === i && (
              <p id={`answer-${i}`} className="animate-fade-in pb-6 text-sm leading-7 text-muted-foreground">
                {a}
              </p>
            )}
          </div>
        ))}
      </section>
    </PublicShell>
  );
}
