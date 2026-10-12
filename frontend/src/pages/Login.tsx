import { AtSign, Lock, LogIn, MessageCircle, ShieldCheck, Store } from "lucide-react";
import { useState, type CSSProperties, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { toast } from "sonner";
import exchange from "@/assets/choropia-exchange.jpg";
import { Link } from "@/components/AppLink";
import { Button } from "@/components/Button";
import { BrandLoader } from "@/components/BrandLoader";
import { Input } from "@/components/ui";
import { errorMessage } from "@/lib/actions";
import { useAuth } from "@/lib/auth";
import { usePrefs } from "@/lib/prefs";

const FEATURES = [
  { icon: Lock, text: "Funds held in escrow until you confirm delivery" },
  { icon: MessageCircle, text: "Message sellers directly before you buy" },
  { icon: Store, text: "Follow local storefronts and verified sellers" },
];

const delay = (ms: number): CSSProperties => ({ animationDelay: `${ms}ms` });

export function LoginPage() {
  const { login } = useAuth();
  const prefs = usePrefs();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [loading, setLoading] = useState(false);

  const onSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    setLoading(true);
    try {
      await login(String(form.get("identifier")), String(form.get("password")));
      navigate(params.get("next") || "/feed", { viewTransition: true });
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
        <img src={exchange} alt="A local seller and buyer exchanging a parcel" className="auth-kenburns absolute inset-0 -z-20 h-full w-full object-cover" />
        <div className="absolute inset-0 -z-10 bg-gradient-to-t from-foreground/90 via-foreground/55 to-foreground/30" />

        <div className="page-enter relative z-10 flex items-center gap-2 p-8 pb-0">
          <Store size={18} />
          <span className="font-display text-lg font-semibold">Choropia</span>
        </div>

        <div className="relative z-10 space-y-4 p-8 pt-16">
          <span className="page-enter inline-block rounded bg-background/10 px-2 py-1 text-xs font-semibold uppercase tracking-wider text-hero-foreground/80 backdrop-blur-sm" style={delay(60)}>
            Uyo pilot
          </span>
          <h2 className="page-enter font-display text-2xl font-semibold leading-snug" style={delay(120)}>
            Buy and sell locally, with every purchase held in escrow.
          </h2>
          <p className="page-enter text-sm text-hero-foreground/80" style={delay(180)}>
            Sellers only get paid once you confirm delivery — no more sending money and hoping for the best.
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
          <ShieldCheck size={14} className="text-hero-accent" /> Social buy-and-sell marketplace
        </div>
      </div>

      <div className="flex flex-col justify-center bg-popover p-8 lg:col-span-7">
        <h1 className="page-enter text-xl font-bold">Welcome back</h1>
        <p className="page-enter mb-6 mt-1 text-sm text-muted-foreground" style={delay(40)}>
          Sign in to your Choropia account.
        </p>

        <form onSubmit={onSubmit} className="space-y-4">
          <label className="page-enter block" style={delay(80)}>
            <span className="mb-1.5 block text-sm font-medium">Email or phone</span>
            <div className="relative">
              <AtSign size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground transition-colors" />
              <Input name="identifier" required className="pl-9" autoFocus />
            </div>
          </label>
          <label className="page-enter block" style={delay(130)}>
            <div className="mb-1.5 flex items-center justify-between">
              <span className="text-sm font-medium">Password</span>
              <Link to="/forgot-password" className="text-xs font-medium text-primary hover:underline">
                Forgot password?
              </Link>
            </div>
            <div className="relative">
              <Lock size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <Input name="password" type="password" required className="pl-9" />
            </div>
          </label>
          <Button type="submit" className="page-enter w-full" style={delay(180)} loading={loading}>
            <LogIn size={15} /> Log in
          </Button>
        </form>
        <p className="page-enter mt-4 text-sm text-muted-foreground" style={delay(220)}>
          No account?{" "}
          <Link to="/register" className="font-medium text-primary hover:underline">
            Register
          </Link>
        </p>
      </div>
    </div>
  );
}
