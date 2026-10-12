import { Video, X } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { Button } from "@/components/Button";
import { Field, Textarea } from "@/components/ui";
import { errorMessage } from "@/lib/actions";
import { api } from "@/lib/api";

const MAX_BYTES = 80 * 1024 * 1024; // 80MB — generous for a short vertical clip, well within what most hosts accept in one request.

export function CreateReelPage() {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
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
      toast.error("That video is too large — keep clips under 80MB.");
      return;
    }
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
    setSubmitting(true);
    try {
      const reel = await api.createReel(form);
      toast.success("Reel posted");
      navigate(`/reels`, { viewTransition: true, state: { justPosted: reel.id } });
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-lg">
      <div className="panel editorial-enter p-6">
        <h1 className="font-display text-xl font-bold">Post a reel</h1>
        <p className="mt-1 text-sm text-muted-foreground">A short vertical video — great for showing off a listing in action.</p>

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

          <Button type="submit" className="w-full" loading={submitting} disabled={!file}>
            Post reel
          </Button>
        </form>
      </div>
    </div>
  );
}
