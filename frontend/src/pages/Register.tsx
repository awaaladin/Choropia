import { AtSign, Heart, Lock, Phone, Tag, User, UserPlus, Verified } from "lucide-react";
import { useState, type CSSProperties, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import community from "@/assets/choropia-community.jpg";
import { Link } from "@/components/AppLink";
import { Button } from "@/components/Button";
import { BrandLoader } from "@/components/BrandLoader";
import { Input } from "@/components/ui";
import { errorMessage } from "@/lib/actions";
import { useAuth } from "@/lib/auth";
import { usePrefs } from "@/lib/prefs";

const FEATURES = [
  { icon: Tag, text: "Post goods, services, or digital listings for free" },
  { icon: Heart, text: "Like, comment, and follow the sellers you trust" },
  { icon: Verified, text: "Get paid only once the buyer confirms delivery" },
];

const delay = (ms: number): CSSProperties => ({ animationDelay: `${ms}ms` });

export function RegisterPage() {
  const { register } = useAuth();
  const prefs = usePrefs();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);

  const onSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const payload = Object.fromEntries(form.entries()) as Record<string, string>;
    if (!payload.phone_number) delete payload.phone_number;
    setLoading(true);
    try {
      await register(payload);
      navigate("/feed", { viewTransition: true });
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto grid max-w-4xl grid-cols-1 overflow-hidden rounded-xl border border-border shadow-2xl lg:grid-cols-12">
      {loading && <BrandLoader variant="full" />}

      <div className="relative isolate flex min-h-[260px] flex-col justify-between overflow-hidden text-hero-foreground lg:col-span-5 lg:min-h-full">
        <img src={community} alt="A textile artisan arranging indigo fabrics in her shop" className="auth-kenburns absolute inset-0 -z-20 h-full w-full object-cover object-[65%_center]" />
        <div className="absolute inset-0 -z-10 bg-gradient-to-t from-foreground/90 via-foreground/55 to-foreground/30" />

        <div className="page-enter relative z-10 flex items-center gap-2 p-8 pb-0">
          <Verified size={18} />
          <span className="font-display text-lg font-semibold">Choropia</span>
        </div>

        <div className="relative z-10 space-y-4 p-8 pt-16">
          <span className="page-enter inline-block rounded bg-background/10 px-2 py-1 text-xs font-semibold uppercase tracking-wider text-hero-foreground/80 backdrop-blur-sm" style={delay(60)}>
            Uyo pilot
          </span>
          <h2 className="page-enter font-display text-2xl font-semibold leading-snug" style={delay(120)}>
            Join a marketplace where every deal is escrow-protected.
          </h2>
          <p className="page-enter text-sm text-hero-foreground/80" style={delay(180)}>
            Post listings, follow storefronts, chat with buyers and sellers, and get paid safely.
          </p>
          <ul className="space-y-3 pt-2">
            {FEATURES.map(({ icon: Icon, text }, i) => (
              <li key={text} className="page-enter flex items-center gap-3" style={delay(240 + i * 70)}>
                <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-background/10 backdrop-blur-sm">
                  <Icon size={16} className="text-hero-accent" />
                </span>
                <span className="text-sm text-hero-foreground/85">{text}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className={prefs.motion === "full" ? "auth-float relative z-10 mx-8 mb-8 flex items-center gap-2 rounded-lg bg-background/15 px-3 py-2 text-xs backdrop-blur-sm" : "relative z-10 mx-8 mb-8 flex items-center gap-2 rounded-lg bg-background/15 px-3 py-2 text-xs backdrop-blur-sm"}>
          <Verified size={14} className="text-hero-accent" /> Social buy-and-sell marketplace
        </div>
      </div>

      <div className="flex flex-col justify-center bg-popover p-8 lg:col-span-7">
        <h1 className="page-enter text-xl font-bold">Create your account</h1>
        <p className="page-enter mb-6 mt-1 text-sm text-muted-foreground" style={delay(40)}>
          It only takes a minute.
        </p>

        <form onSubmit={onSubmit} className="space-y-4">
          <div className="page-enter grid grid-cols-2 gap-3" style={delay(80)}>
            <div className="relative">
              <User size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <Input name="first_name" placeholder="First name" className="pl-9" autoFocus />
            </div>
            <Input name="last_name" placeholder="Last name" />
          </div>
          <div className="page-enter relative" style={delay(120)}>
            <AtSign size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <Input name="email" type="email" placeholder="Email" required className="pl-9" />
          </div>
          <div className="page-enter relative" style={delay(160)}>
            <Phone size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <Input name="phone_number" placeholder="Phone number (optional)" className="pl-9" />
          </div>
          <div className="page-enter relative" style={delay(200)}>
            <Lock size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <Input name="password" type="password" placeholder="Password" required className="pl-9" />
          </div>
          <Button type="submit" className="page-enter w-full" style={delay(240)} loading={loading}>
            <UserPlus size={15} /> Create account
          </Button>
        </form>
        <p className="page-enter mt-4 text-sm text-muted-foreground" style={delay(280)}>
          Already have an account?{" "}
          <Link to="/login" className="font-medium text-primary hover:underline">
            Log in
          </Link>
        </p>
      </div>
    </div>
  );
}
