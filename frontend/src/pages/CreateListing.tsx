import { useQuery } from "@tanstack/react-query";
import { ImagePlus, X } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { Button } from "@/components/Button";
import { Field, Input, Select, Textarea } from "@/components/ui";
import { errorMessage } from "@/lib/actions";
import { api } from "@/lib/api";

export function CreateListingPage() {
  const navigate = useNavigate();
  const categories = useQuery({ queryKey: ["categories"], queryFn: api.listCategories, staleTime: 10 * 60_000 });
  const [files, setFiles] = useState<File[]>([]);
  const [previews, setPreviews] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const urls = files.map((f) => URL.createObjectURL(f));
    setPreviews(urls);
    return () => urls.forEach((u) => URL.revokeObjectURL(u));
  }, [files]);

  const addFiles = (incoming: FileList | null) => {
    if (!incoming) return;
    setFiles((current) => [...current, ...Array.from(incoming)]);
  };
  const removeFile = (index: number) => setFiles((current) => current.filter((_, i) => i !== index));

  const onSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    files.forEach((f) => form.append("uploaded_photos", f));
    setSubmitting(true);
    try {
      const listing = await api.createListing(form);
      toast.success("Listing posted");
      navigate(`/listings/${listing.id}`, { viewTransition: true });
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-lg">
      <div className="panel editorial-enter p-6">
        <h1 className="font-display text-xl font-bold">Post a listing</h1>
        <p className="mt-1 text-sm text-muted-foreground">Takes less than a minute. Add a few photos to sell faster.</p>

        <form onSubmit={onSubmit} encType="multipart/form-data" className="mt-5 space-y-4">
          <Field label="Title">
            <Input name="title" required maxLength={120} />
          </Field>
          <Field label="Description">
            <Textarea name="description" rows={3} />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Price (₦)">
              <Input name="price" type="number" step="0.01" min="0" required />
            </Field>
            <Field label="Condition">
              <Select name="condition" defaultValue="used">
                <option value="used">Used</option>
                <option value="new">New</option>
              </Select>
            </Field>
          </div>
          <Field label="Category">
            <Select name="category" required defaultValue="">
              <option value="" disabled>
                Choose a category
              </option>
              {categories.data?.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Location">
            <Input name="location" placeholder="e.g. Uyo — Use of Ibom campus" />
          </Field>

          <Field label="Photos">
            <div className="grid grid-cols-4 gap-2">
              {previews.map((src, i) => (
                <div key={src} className="group relative aspect-square overflow-hidden rounded-md border border-border">
                  <img src={src} alt="" className="h-full w-full object-cover" />
                  <button
                    type="button"
                    onClick={() => removeFile(i)}
                    aria-label="Remove photo"
                    className="absolute right-1 top-1 grid size-5 place-items-center rounded-full bg-foreground/70 text-background opacity-0 transition-opacity group-hover:opacity-100"
                  >
                    <X size={11} />
                  </button>
                </div>
              ))}
              <button
                type="button"
                onClick={() => fileInput.current?.click()}
                className="grid aspect-square place-items-center rounded-md border border-dashed border-border text-muted-foreground transition-colors hover:border-primary hover:text-primary"
              >
                <ImagePlus size={18} />
              </button>
            </div>
            <input ref={fileInput} type="file" accept="image/*" multiple className="sr-only" onChange={(e) => addFiles(e.target.files)} />
          </Field>

          <Button type="submit" className="w-full" loading={submitting}>
            Post listing
          </Button>
        </form>
      </div>
    </div>
  );
}
