import { MailCheck, ShieldCheck } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "@/components/Button";
import { Input } from "@/components/ui";
import { errorMessage } from "@/lib/actions";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

/** Shown right after sign-up (the welcome email carries the first code) and reachable any time while unverified. */
export function VerifyEmailPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);

  const onSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const code = String(new FormData(e.currentTarget).get("code") ?? "").trim();
    setLoading(true);
    try {
      await api.confirmEmailCode(code);
      await queryClient.invalidateQueries({ queryKey: ["me"] });
      toast.success("Email verified. Thank you!");
      navigate("/feed", { viewTransition: true });
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const resend = async () => {
    setResending(true);
    try {
      const r = await api.requestEmailCode();
      toast.success(r.detail || "We sent a new code.");
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setResending(false);
    }
  };

  return (
    <div className="panel editorial-enter mx-auto max-w-md p-8">
      <div className="mb-4 grid size-12 place-items-center rounded-xl bg-accent text-primary">
        <MailCheck size={20} />
      </div>
      <h1 className="text-xl font-bold">Verify your email</h1>
      <p className="mb-6 mt-1 text-sm text-muted-foreground">
        We sent a 6-digit code to <strong>{user?.email ?? "your email"}</strong>. It can take a minute and may land in spam.
      </p>

      <form onSubmit={onSubmit} className="space-y-4">
        <Input name="code" inputMode="numeric" autoComplete="one-time-code" maxLength={6} pattern="[0-9]{6}" placeholder="6-digit code" required autoFocus />
        <Button type="submit" className="w-full" loading={loading}>
          <ShieldCheck size={15} /> Verify
        </Button>
      </form>

      <div className="mt-5 flex items-center justify-between text-sm">
        <button type="button" onClick={resend} disabled={resending} className="font-medium text-primary hover:underline disabled:opacity-60">
          Send me a new code
        </button>
        <button type="button" onClick={() => navigate("/feed")} className="text-muted-foreground hover:underline">
          I'll do this later
        </button>
      </div>
    </div>
  );
}
