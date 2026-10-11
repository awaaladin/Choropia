import { Check } from "lucide-react";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";
import { Button } from "@/components/Button";
import { Field, Input, Textarea } from "@/components/ui";
import { errorMessage } from "@/lib/actions";
import { api } from "@/lib/api";

export function ApplyMerchantPage() {
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);

  const onSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = e.currentTarget;
    const payload = Object.fromEntries(new FormData(form).entries()) as Record<string, string>;
    setLoading(true);
    try {
      await api.applyForMerchant(payload);
      setSubmitted(true);
      form.reset();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="panel editorial-enter mx-auto max-w-lg p-6">
      <h1 className="text-xl font-bold">Open a storefront</h1>
      <p className="mb-4 mt-1 text-sm text-muted-foreground">
        Merchant storefronts get their own followers and listing feed, separate from your personal profile. Applications are reviewed by a moderator.
      </p>

      <form onSubmit={onSubmit} className="space-y-3">
        <Field label="Business name">
          <Input name="business_name" required />
        </Field>
        <Field label="What do you sell?">
          <Textarea name="business_description" rows={3} />
        </Field>
        <Field label="Business phone">
          <Input name="business_phone" required />
        </Field>
        <Field label="Business address">
          <Input name="business_address" required />
        </Field>

        {submitted && (
          <p className="animate-fade-in flex items-center gap-1 text-sm font-medium text-success">
            <Check size={14} /> Application submitted — you'll be notified once it's reviewed.
          </p>
        )}
        <Button type="submit" className="w-full" loading={loading}>
          Submit application
        </Button>
      </form>
    </div>
  );
}
