import { Link } from "@/components/AppLink";
import { PublicShell } from "@/components/PublicShell";
import { useReveal } from "@/lib/useReveal";

const SECTIONS = [
  [
    "About this notice",
    "This is a plain-language summary of how Choropia handles your information during the Uyo pilot. It isn't a substitute for a full legal policy — that should be reviewed by counsel before a wider public launch.",
  ],
  [
    "Account information",
    "When you register, we store your email or phone number, your name, and a securely hashed password — we never store your password itself. You can add a bio, location, and profile photo from your profile page.",
  ],
  [
    "Listings, orders and messages",
    "Listings you post, orders you place or receive, and messages you send are stored so the marketplace and escrow flow can work — sellers see buyer names on their orders, and the other party in a conversation can see your messages.",
  ],
  [
    "Payments",
    "Order payments are processed through our escrow payment provider, which handles the payment itself — Choropia doesn't store your payment credentials.",
  ],
  [
    "Your display preferences",
    "Your browser stores your chosen theme, feed layout, content density, and motion level in local storage on this device. These settings don't automatically carry over to another device unless you're logged in, in which case your theme is also saved to your account.",
  ],
  [
    "Removing saved preferences",
    "Change these anytime from Display settings in the header. To remove them entirely, clear this site's storage through your browser's settings.",
  ],
  [
    "Third parties",
    "Pages load fonts from Google Fonts. Your browser requests them directly, which can share your IP address and browser details with Google, governed by Google's own policies.",
  ],
  [
    "Questions",
    "See the contact page for the quickest way to reach the right place for your question.",
  ],
] as const;

export function PrivacyPage() {
  useReveal();
  return (
    <PublicShell>
      <section className="mx-auto max-w-[1100px] px-5 py-14 lg:py-20">
        <p className="page-enter eyebrow">CLEAR BY DESIGN</p>
        <h1 className="page-enter mt-4 text-4xl font-semibold sm:text-6xl">Your privacy matters.</h1>
        <p className="mt-6 max-w-xl text-base leading-7 text-muted-foreground">A plain-language look at what happens to your information on Choropia.</p>

        <div className="mt-12 grid gap-10 md:grid-cols-[220px_1fr]">
          <nav aria-label="On this page" className="self-start md:sticky md:top-24">
            <p className="mb-4 text-xs font-semibold uppercase text-primary">ON THIS PAGE</p>
            {SECTIONS.map(([title], i) => (
              <a key={title} href={`#privacy-${i}`} className="block py-2 text-xs leading-5 text-muted-foreground hover:text-primary">
                {title}
              </a>
            ))}
          </nav>
          <div>
            {SECTIONS.map(([title, copy], i) => (
              <section data-reveal id={`privacy-${i}`} key={title} className="scroll-mt-24 border-t border-border pb-10 pt-6">
                <p className="text-xs font-semibold text-primary">0{i + 1}</p>
                <h2 className="mt-3 text-xl font-semibold">{title}</h2>
                <p className="mt-4 text-sm leading-7 text-muted-foreground">{copy}</p>
              </section>
            ))}
            <Link to="/contact" className="text-sm font-semibold text-primary">
              Visit the contact page →
            </Link>
          </div>
        </div>
      </section>
    </PublicShell>
  );
}
