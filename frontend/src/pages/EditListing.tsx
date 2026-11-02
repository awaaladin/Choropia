import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router";
import { toast } from "sonner";
import { Button } from "@/components/Button";
import { ErrorState, Field, Input, Select, Skeleton, Textarea } from "@/components/ui";
import { errorMessage } from "@/lib/actions";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { naira } from "@/lib/utils";

/** The owner changes their own listing. A changed price can be shown to buyers (old price crossed out) or quietly replaced. */
export function EditListingPage() {
  const id = Number(useParams().id);
  const { user } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const listing = useQuery({ queryKey: ["listing", id], queryFn: () => api.getListing(id) });
  const [price, setPrice] = useState("");
  const [showChange, setShowChange] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (listing.data) setPrice(String(Number(listing.data.price)));
  }, [listing.data]);

  if (listing.isPending) return <Skeleton className="mx-auto h-64 max-w-xl" />;
  if (listing.isError || !listing.data) return <ErrorState message="We couldn't load this listing." onRetry={() => listing.refetch()} />;
  const item = listing.data;
  if (item.seller_id !== user?.id) return <ErrorState message="Only the person who posted this can edit it." />;

  const priceChanged = Number(price) !== Number(item.price);

  const onSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const body: Record<string, unknown> = {
      title: String(form.get("title") ?? "").trim(),
      description: String(form.get("description") ?? ""),
      price: Number(price).toFixed(2),
      quantity: Number(form.get("quantity") ?? 1),
      condition: String(form.get("condition") ?? "used"),
      show_price_change: priceChanged && showChange,
    };
    setSaving(true);
    try {
      await api.updateListing(id, body);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["listing", id] }),
        queryClient.invalidateQueries({ queryKey: ["feed"] }),
        queryClient.invalidateQueries({ queryKey: ["listings"] }),
      ]);
      toast.success("Your listing was updated");
      navigate(`/listings/${id}`, { viewTransition: true });
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="panel editorial-enter mx-auto max-w-xl p-6">
      <h1 className="text-xl font-bold">Edit your listing</h1>
      <p className="mb-5 mt-1 text-sm text-muted-foreground">Changes apply straight away, wherever the listing appears.</p>
      <form onSubmit={onSubmit} className="space-y-4">
        <Field label="Title">
          <Input name="title" defaultValue={item.title} required maxLength={120} />
        </Field>
        <Field label="Description">
          <Textarea name="description" rows={4} defaultValue={item.description ?? ""} />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Price (₦)">
            <Input name="price" type="number" step="0.01" min="0" value={price} onChange={(e) => setPrice(e.target.value)} required />
          </Field>
          <Field label="How many do you have?">
            <Input name="quantity" type="number" min="1" max="999" step="1" defaultValue={item.quantity ?? 1} required />
          </Field>
        </div>
        {priceChanged && (
          <label className="flex items-start gap-3 rounded-lg border border-border bg-accent/40 p-3 text-sm">
            <input type="checkbox" className="mt-1" checked={showChange} onChange={(e) => setShowChange(e.target.checked)} />
            <span>
              <strong>Show buyers that the price changed.</strong>
              <br />
              <span className="text-muted-foreground">
                Ticked: buyers see {naira(item.price)} crossed out next to the new price. Not ticked: they only see the new price.
              </span>
            </span>
          </label>
        )}
        <Field label="Condition">
          <Select name="condition" defaultValue={item.condition}>
            <option value="used">Used</option>
            <option value="new">New</option>
          </Select>
        </Field>
        <div className="flex gap-3">
          <Button type="submit" loading={saving}>
            Save changes
          </Button>
          <Button type="button" variant="secondary" onClick={() => navigate(-1)}>
            Cancel
          </Button>
        </div>
      </form>
    </div>
  );
}
