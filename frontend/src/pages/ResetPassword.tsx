import { Check, Lock } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useSearchParams } from "react-router";
import { toast } from "sonner";
import { Link } from "@/components/AppLink";
import { Button } from "@/components/Button";
import { Input } from "@/components/ui";
import { errorMessage } from "@/lib/actions";
import { api } from "@/lib/api";

export function ResetPasswordPage() {
  const [params] = useSearchParams();
  const uid = params.get("uid");
  const token = params.get("token");
  const [done, setDone] = useState(false);
  const [loading, setLoading] = useState(false);

  const onSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const password = String(form.get("password"));
    if (password !== String(form.get("confirm"))) {
      toast.error("Passwords don't match.");
      return;
    }
    if (!uid || !token) {
      toast.error("This reset link is incomplete. Request a new one.");
      return;
    }
    setLoading(true);
    try {
      await api.confirmPasswordReset(uid, token, password);
      setDone(true);
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="panel editorial-enter mx-auto max-w-md p-8">
      <div className="mb-4 grid size-12 place-items-center rounded-xl bg-accent text-primary">
        <Lock size={20} />
      </div>
      <h1 className="text-xl font-bold">Choose a new password</h1>
      <p className="mb-6 mt-1 text-sm text-muted-foreground">Pick something you haven't used here before.</p>

      {!done ? (
        <form onSubmit={onSubmit} className="space-y-4">
          <Input name="password" type="password" placeholder="New password" required autoFocus />
          <Input name="confirm" type="password" placeholder="Confirm new password" required />
          <Button type="submit" className="w-full" loading={loading}>
            <Check size={15} /> Update password
          </Button>
        </form>
      ) : (
        <div className="animate-fade-in flex items-start gap-2 rounded-lg bg-accent p-3 text-sm text-primary">
          <Check size={16} className="mt-0.5 shrink-0" />
          <span>
            Password updated.{" "}
            <Link to="/login" className="font-semibold underline">
              Log in
            </Link>{" "}
            with your new password.
          </span>
        </div>
      )}
    </div>
  );
}
