import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Video, X } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { Button } from "@/components/Button";
import { Field, Textarea } from "@/components/ui";
import { errorMessage } from "@/lib/actions";
import { api, rows } from "@/lib/api";
import type { Listing } from "@/lib/types";

const MAX_BYTES = 4 * 1024 * 1024;

export function CreateReelPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const myListings = useQuery({
    queryKey: ["my-listings"],
    queryFn: async () => rows(await api.listMyListings()),
  });
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [uploadState, setUploadState] = useState<"ready" | "uploading" | "failed">("ready");
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!file) {
      setPreview(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const pickFile = (incoming: File | null) => {
    if (!incoming) return;
    if (incoming.size > MAX_BYTES) {
      toast.error("Until large-video uploads are available, reels must be 4MB or smaller.");
      return;
    }
    if (incoming.type && !incoming.type.startsWith("video/")) {
      toast.error("Choose a video file.");
      return;
    }
    setUploadState("ready");
    setUploadError(null);
    setFile(incoming);
  };

  const onSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!file) {
      toast.error("Add a video first.");
      return;
    }
    const form = new FormData(e.currentTarget);
    form.set("video", file);
    setUploadState("uploading");
    setUploadError(null);
    try {
      const reel = await api.createReel(form);
      await queryClient.invalidateQueries({ queryKey: ["reels"] });
      await queryClient.invalidateQueries({ queryKey: ["reels-listing-fallback"] });
      toast.success("Reel posted");
      navigate(`/reels`, { viewTransition: true, state: { justPosted: reel.id } });
    } catch (err) {
      const message = errorMessage(err);
      setUploadError(message);
      setUploadState("failed");
      toast.error(message);
    }
  };

  return (
    <div className="mx-auto max-w-lg">
      <div className="panel editorial-enter p-6">
        <h1 className="font-display text-xl font-bold">Post a reel</h1>
        <p className="mt-1 text-sm text-muted-foreground">A short vertical video — great for showing off a listing in action. For now, keep uploads under 4MB.</p>

        <form onSubmit={onSubmit} className="mt-5 space-y-4">
          <Field label="Video">
            {preview ? (
              <div className="relative mx-auto aspect-[9/16] w-48 overflow-hidden rounded-md border border-border bg-foreground">
                <video src={preview} className="h-full w-full object-cover" controls muted />
                <button
                  type="button"
                  onClick={() => setFile(null)}
                  aria-label="Remove video"
                  className="absolute right-1.5 top-1.5 grid size-6 place-items-center rounded-full bg-foreground/70 text-background"
                >
                  <X size={13} />
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => fileInput.current?.click()}
                className="flex aspect-[9/16] w-48 mx-auto flex-col items-center justify-center gap-2 rounded-md border border-dashed border-border text-muted-foreground transition-colors hover:border-primary hover:text-primary"
              >
                <Video size={22} />
                <span className="text-xs">Choose a video</span>
              </button>
            )}
            <input ref={fileInput} type="file" accept="video/mp4,video/webm,video/quicktime" className="sr-only" onChange={(e) => pickFile(e.target.files?.[0] ?? null)} />
          </Field>

          <Field label="Caption">
            <Textarea name="caption" rows={3} placeholder="What's in this video?" maxLength={500} />
          </Field>

          <Field label="Tag one of your listings (optional)">
            <select
              name="listing"
              defaultValue=""
              className="h-10 w-full rounded-md border border-border bg-background px-3 text-sm"
              disabled={myListings.isPending || myListings.isError}
            >
              <option value="">No listing</option>
              {rows<Listing>(myListings.data).map((listing) => (
                <option key={listing.id} value={listing.id}>{listing.title}</option>
              ))}
            </select>
            {myListings.isError && <p className="mt-1 text-xs text-muted-foreground">Listings could not be loaded; you can still post without tagging one.</p>}
          </Field>

          {uploadState === "uploading" && (
            <p role="status" aria-live="polite" className="text-sm text-muted-foreground">
              Uploading your reel… Keep this page open until it finishes.
            </p>
          )}
          {uploadError && (
            <p role="alert" className="text-sm text-destructive">
              Upload failed: {uploadError}. Your video is still selected; you can retry.
            </p>
          )}

          <Button type="submit" className="w-full" loading={uploadState === "uploading"} disabled={!file || uploadState === "uploading"}>
            {uploadState === "failed" ? "Retry upload" : "Post reel"}
          </Button>
        </form>
      </div>
    </div>
  );
}
