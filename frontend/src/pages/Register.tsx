import { AtSign, Heart, Lock, Phone, Tag, User, UserPlus, Verified } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { Link } from "@/components/AppLink";
import { Button } from "@/components/Button";
import { BrandLoader } from "@/components/BrandLoader";
import { Input } from "@/components/ui";
import { errorMessage } from "@/lib/actions";
import { useAuth } from "@/lib/auth";

const FEATURES = [
  { icon: Tag, text: "Post goods, services, or digital listings for free" },
  { icon: Heart, text: "Like, comment, and follow the sellers you trust" },
  { icon: Verified, text: "Get paid only once the buyer confirms delivery" },
];

export function RegisterPage() {
  const { register } = useAuth();
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
      <div className="relative flex flex-col justify-between overflow-hidden bg-foreground p-8 text-background lg:col-span-5">
        <div className="pointer-events-none absolute -bottom-20 -right-16 size-72 rounded-full bg-primary opacity-30 blur-3xl" />
        <div className="pointer-events-none absolute -top-14 -left-14 size-56 rounded-full bg-primary/40 opacity-20 blur-2xl" />
        <div className="relative z-10 flex items-center gap-2">
          <Verified size={18} />
          <span className="font-display text-lg font-semibold">Choropia</span>
        </div>
        <div className="relative z-10 space-y-4 py-8">
          <span className="inline-block rounded bg-background/10 px-2 py-1 text-xs font-semibold uppercase tracking-wider text-background/80">Uyo pilot</span>
          <h2 className="font-display text-2xl font-semibold leading-snug">Join a marketplace where every deal is escrow-protected.</h2>
          <p className="text-sm text-background/70">Post listings, follow storefronts, chat with buyers and sellers, and get paid safely.</p>
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
        <p className="relative z-10 text-xs text-background/50">Social buy-and-sell marketplace</p>
      </div>

      <div className="flex flex-col justify-center bg-popover p-8 lg:col-span-7">
        <h1 className="text-xl font-bold">Create your account</h1>
        <p className="mb-6 mt-1 text-sm text-muted-foreground">It only takes a minute.</p>

        <form onSubmit={onSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="relative">
              <User size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <Input name="first_name" placeholder="First name" className="pl-9" autoFocus />
            </div>
            <Input name="last_name" placeholder="Last name" />
          </div>
          <div className="relative">
            <AtSign size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <Input name="email" type="email" placeholder="Email" required className="pl-9" />
          </div>
          <div className="relative">
            <Phone size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <Input name="phone_number" placeholder="Phone number (optional)" className="pl-9" />
          </div>
          <div className="relative">
            <Lock size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <Input name="password" type="password" placeholder="Password" required className="pl-9" />
          </div>
          <Button type="submit" className="w-full" loading={loading}>
            <UserPlus size={15} /> Create account
          </Button>
        </form>
        <p className="mt-4 text-sm text-muted-foreground">
          Already have an account?{" "}
          <Link to="/login" className="font-medium text-primary hover:underline">
            Log in
          </Link>
        </p>
      </div>
    </div>
  );
}
