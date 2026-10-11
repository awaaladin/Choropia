import { AtSign, Lock, LogIn, MessageCircle, ShieldCheck, Store } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { toast } from "sonner";
import { Link } from "@/components/AppLink";
import { Button } from "@/components/Button";
import { BrandLoader } from "@/components/BrandLoader";
import { Input } from "@/components/ui";
import { errorMessage } from "@/lib/actions";
import { useAuth } from "@/lib/auth";

const FEATURES = [
  { icon: Lock, text: "Funds held in escrow until you confirm delivery" },
  { icon: MessageCircle, text: "Message sellers directly before you buy" },
  { icon: Store, text: "Follow local storefronts and verified sellers" },
];

export function LoginPage() {
  const { login } = useAuth();
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
      <div className="relative flex flex-col justify-between overflow-hidden bg-foreground p-8 text-background lg:col-span-5">
        <div className="pointer-events-none absolute -bottom-20 -right-16 size-72 rounded-full bg-primary opacity-30 blur-3xl" />
        <div className="pointer-events-none absolute -top-14 -left-14 size-56 rounded-full bg-primary/40 opacity-20 blur-2xl" />
        <div className="relative z-10 flex items-center gap-2">
          <Store size={18} />
          <span className="font-display text-lg font-semibold">Choropia</span>
        </div>
        <div className="relative z-10 space-y-4 py-8">
          <span className="inline-block rounded bg-background/10 px-2 py-1 text-xs font-semibold uppercase tracking-wider text-background/80">Uyo pilot</span>
          <h2 className="font-display text-2xl font-semibold leading-snug">Buy and sell locally, with every purchase held in escrow.</h2>
          <p className="text-sm text-background/70">Sellers only get paid once you confirm delivery — no more sending money and hoping for the best.</p>
          <ul className="space-y-3 pt-4">
            {FEATURES.map(({ icon: Icon, text }) => (
              <li key={text} className="flex items-center gap-3">
                <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-background/10">
                  <Icon size={16} className="text-primary" />
                </span>
                <span className="text-sm text-background/80">{text}</span>
              </li>
            ))}
          </ul>
        </div>
        <p className="relative z-10 flex items-center gap-1 text-xs text-background/50">
          <ShieldCheck size={13} /> Social buy-and-sell marketplace
        </p>
      </div>

      <div className="flex flex-col justify-center bg-popover p-8 lg:col-span-7">
        <h1 className="text-xl font-bold">Welcome back</h1>
        <p className="mb-6 mt-1 text-sm text-muted-foreground">Sign in to your Choropia account.</p>

        <form onSubmit={onSubmit} className="space-y-4">
          <label className="block">
            <span className="mb-1.5 block text-sm font-medium">Email or phone</span>
            <div className="relative">
              <AtSign size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <Input name="identifier" required className="pl-9" autoFocus />
            </div>
          </label>
          <label className="block">
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
          <Button type="submit" className="w-full" loading={loading}>
            <LogIn size={15} /> Log in
          </Button>
        </form>
        <p className="mt-4 text-sm text-muted-foreground">
          No account?{" "}
          <Link to="/register" className="font-medium text-primary hover:underline">
            Register
          </Link>
        </p>
      </div>
    </div>
  );
}
