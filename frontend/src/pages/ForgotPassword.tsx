import { AtSign, MailCheck, LockKeyhole, Send } from "lucide-react";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";
import { Link } from "@/components/AppLink";
import { Button } from "@/components/Button";
import { Input } from "@/components/ui";
import { errorMessage } from "@/lib/actions";
import { api } from "@/lib/api";

export function ForgotPasswordPage() {
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);

  const onSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const email = String(new FormData(e.currentTarget).get("email"));
    setLoading(true);
    try {
      await api.requestPasswordReset(email);
      setSent(true);
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="panel editorial-enter mx-auto max-w-md p-8">
      <div className="mb-4 grid size-12 place-items-center rounded-xl bg-accent text-primary">
        <LockKeyhole size={20} />
      </div>
      <h1 className="text-xl font-bold">Forgot your password?</h1>
      <p className="mb-6 mt-1 text-sm text-muted-foreground">Enter the email you registered with and we'll send you a link to choose a new one.</p>

      <form onSubmit={onSubmit} className="space-y-4">
        <div className="relative">
          <AtSign size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input name="email" type="email" placeholder="Email" required className="pl-9" autoFocus />
        </div>
        <Button type="submit" className="w-full" loading={loading}>
          <Send size={15} /> Send reset link
        </Button>
      </form>

      {sent && (
        <div className="animate-fade-in mt-4 flex items-start gap-2 rounded-lg bg-accent p-3 text-sm text-primary">
          <MailCheck size={16} className="mt-0.5 shrink-0" />
          <span>If that email is registered, a reset link is on its way. Check your inbox (and spam).</span>
        </div>
      )}

      <p className="mt-6 text-sm text-muted-foreground">
        Remembered it?{" "}
        <Link to="/login" className="font-medium text-primary hover:underline">
          Back to log in
        </Link>
      </p>
    </div>
  );
}
