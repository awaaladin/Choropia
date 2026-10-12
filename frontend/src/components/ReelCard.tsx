import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Heart, MessageCircle, Share2, ShoppingBag, Trash2, Volume2, VolumeX } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { errorMessage, useEnsureLogin } from "@/lib/actions";
import { api, rows } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Reel } from "@/lib/types";
import { naira, timeAgo } from "@/lib/utils";
import { Link } from "./AppLink";
import { FollowButton } from "./FollowButton";
import { Avatar, Input, Modal } from "./ui";

function useInView<T extends HTMLElement>(threshold = 0.6) {
  const ref = useRef<T>(null);
  const [inView, setInView] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(([entry]) => setInView(entry.isIntersecting), { threshold });
    observer.observe(el);
    return () => observer.disconnect();
  }, [threshold]);
  return [ref, inView] as const;
}

export function ReelCard({ reel }: { reel: Reel }) {
  const { user } = useAuth();
  const ensureLogin = useEnsureLogin();
  const queryClient = useQueryClient();
  const [containerRef, inView] = useInView<HTMLDivElement>();
  const videoRef = useRef<HTMLVideoElement>(null);
  const [muted, setMuted] = useState(true);
  const [commentsOpen, setCommentsOpen] = useState(false);
  const [liked, setLiked] = useState(reel.is_liked);
  const [likes, setLikes] = useState(reel.likes_count);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    if (inView) video.play().catch(() => {});
    else video.pause();
  }, [inView]);

  const toggleLike = useMutation({
    mutationFn: async () => {
      if (liked) {
        const mine = rows(await api.listMyReelLikes());
        const existing = mine.find((l) => l.reel === reel.id);
        if (existing) await api.unlikeReel(existing.id);
      } else {
        await api.likeReel(reel.id);
      }
    },
    onMutate: () => {
      setLiked((v) => !v);
      setLikes((n) => n + (liked ? -1 : 1));
    },
    onError: (err) => {
      setLiked((v) => !v);
      setLikes((n) => n + (liked ? 1 : -1));
      toast.error(errorMessage(err));
    },
  });

  const remove = useMutation({
    mutationFn: () => api.deleteReel(reel.id),
    onSuccess: () => {
      toast.success("Reel removed");
      queryClient.invalidateQueries({ queryKey: ["reels"] });
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const share = async () => {
    const url = `${window.location.origin}/reels/${reel.id}`;
    try {
      await navigator.clipboard.writeText(url);
      toast.success("Link copied");
    } catch {
      toast.error("Could not copy link");
    }
  };

  const isMine = user?.id === reel.owner;
  const targetType = reel.merchant ? "merchant" : "user";

  return (
    <div ref={containerRef} className="relative h-full w-full shrink-0 snap-start overflow-hidden bg-foreground md:rounded-xl">
      <video
        ref={videoRef}
        src={reel.video}
        loop
        muted={muted}
        playsInline
        className="h-full w-full object-cover"
        onClick={() => (videoRef.current?.paused ? videoRef.current.play() : videoRef.current?.pause())}
      />
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-foreground/80 via-transparent to-foreground/20" />

      <button
        onClick={() => setMuted((m) => !m)}
        aria-label={muted ? "Unmute" : "Mute"}
        className="absolute right-3 top-3 grid size-9 place-items-center rounded-full bg-background/20 text-background backdrop-blur-sm"
      >
        {muted ? <VolumeX size={16} /> : <Volume2 size={16} />}
      </button>

      {/* Action rail */}
      <div className="absolute bottom-24 right-3 flex flex-col items-center gap-5 text-background md:bottom-6">
        <button onClick={() => ensureLogin() && toggleLike.mutate()} className="flex flex-col items-center gap-1" aria-pressed={liked}>
          <Heart size={26} fill={liked ? "currentColor" : "none"} className={liked ? "text-destructive" : undefined} />
          <span className="text-xs font-medium tabular-nums">{likes}</span>
        </button>
        <button onClick={() => ensureLogin() && setCommentsOpen(true)} className="flex flex-col items-center gap-1">
          <MessageCircle size={26} />
          <span className="text-xs font-medium tabular-nums">{reel.comments_count}</span>
        </button>
        <button onClick={share} className="flex flex-col items-center gap-1">
          <Share2 size={24} />
        </button>
        {isMine && (
          <button onClick={() => remove.mutate()} className="flex flex-col items-center gap-1 text-destructive" aria-label="Delete reel">
            <Trash2 size={22} />
          </button>
        )}
      </div>

      {/* Creator + caption + shoppable card */}
      <div className="absolute inset-x-3 bottom-4 flex flex-col gap-3 text-background md:bottom-6 md:right-20">
        <div className="flex items-center gap-2">
          <Avatar src={reel.creator_avatar} name={reel.creator_name} size={34} />
          <span className="font-semibold">{reel.creator_name}</span>
          {!isMine && <FollowButton targetId={reel.creator_id} targetType={targetType} className="h-7 px-2.5 text-xs" />}
          <span className="ml-auto text-xs text-background/70">{timeAgo(reel.created_at)}</span>
        </div>
        {reel.caption && <p className="line-clamp-2 text-sm text-background/90">{reel.caption}</p>}
        {reel.listing && (
          <Link to={`/listings/${reel.listing}`} className="flex items-center gap-3 rounded-lg bg-background/15 p-2.5 backdrop-blur-sm transition-colors hover:bg-background/25">
            <span className="grid size-9 shrink-0 place-items-center rounded-md bg-background/20">
              <ShoppingBag size={16} />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-medium">{reel.listing_title}</span>
              <span className="block text-xs text-background/70">{naira(reel.listing_price ?? "0")}</span>
            </span>
            <span className="shrink-0 rounded-full bg-background px-3 py-1.5 text-xs font-semibold text-foreground">Buy</span>
          </Link>
        )}
      </div>

      <ReelComments reelId={reel.id} open={commentsOpen} onClose={() => setCommentsOpen(false)} />
    </div>
  );
}

function ReelComments({ reelId, open, onClose }: { reelId: number; open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [body, setBody] = useState("");
  const comments = useQuery({ queryKey: ["reel-comments", reelId], queryFn: async () => rows(await api.listReelComments(reelId)), enabled: open });

  const post = useMutation({
    mutationFn: (text: string) => api.createReelComment(reelId, text),
    onSuccess: () => {
      setBody("");
      queryClient.invalidateQueries({ queryKey: ["reel-comments", reelId] });
      queryClient.invalidateQueries({ queryKey: ["reels"] });
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  return (
    <Modal open={open} onClose={onClose} title="Comments">
      <div className="max-h-80 space-y-3 overflow-y-auto">
        {comments.isPending && <p className="text-sm text-muted-foreground">Loading…</p>}
        {comments.isSuccess && comments.data.length === 0 && <p className="text-sm text-muted-foreground">No comments yet.</p>}
        {comments.data?.map((c) => (
          <div key={c.id} className="text-sm">
            <span className="font-semibold">{c.author_name}</span> <span className="text-xs text-muted-foreground">{timeAgo(c.created_at)}</span>
            <p className="text-muted-foreground">{c.body}</p>
          </div>
        ))}
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (body.trim()) post.mutate(body.trim());
        }}
        className="mt-4 flex gap-2"
      >
        <Input value={body} onChange={(e) => setBody(e.target.value)} placeholder="Add a comment" />
        <button type="submit" className="shrink-0 text-sm font-semibold text-primary disabled:opacity-50" disabled={post.isPending}>
          Post
        </button>
      </form>
    </Modal>
  );
}
