import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronRight, Flag, Lock, ShieldCheck, Verified } from "lucide-react";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";
import { Link } from "@/components/AppLink";
import { Button } from "@/components/Button";
import { Avatar, Badge, ErrorState, Input, Modal, Skeleton, Textarea } from "@/components/ui";
import { errorMessage, useEnsureLogin, useListingActions } from "@/lib/actions";
import { api, rows } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { usePrefs } from "@/lib/prefs";
import { naira, timeAgo } from "@/lib/utils";
import { useParams } from "react-router";

export function ListingDetailPage() {
  const { id } = useParams();
  const listingId = Number(id);
  const prefs = usePrefs();
  const { user, loggedIn } = useAuth();
  const ensureLogin = useEnsureLogin();
  const { buy, messageSeller, setLiked } = useListingActions();
  const queryClient = useQueryClient();
  const [reportOpen, setReportOpen] = useState(false);
  const [reportReason, setReportReason] = useState("");
  const [commentBody, setCommentBody] = useState("");

  const listing = useQuery({ queryKey: ["listing", listingId], queryFn: () => api.getListing(listingId) });
  const comments = useQuery({
    queryKey: ["comments", listingId],
    queryFn: async () => rows(await api.listComments(listingId)),
    enabled: !!listing.data,
  });

  const toggleLike = useMutation({
    mutationFn: () => setLiked(listingId, !listing.data!.is_liked),
    onMutate: async () => {
      await queryClient.cancelQueries({ queryKey: ["listing", listingId] });
      const previous = queryClient.getQueryData(["listing", listingId]);
      queryClient.setQueryData(["listing", listingId], (old: typeof listing.data) =>
        old ? { ...old, is_liked: !old.is_liked, likes_count: old.likes_count + (old.is_liked ? -1 : 1) } : old,
      );
      return { previous };
    },
    onError: (err, _vars, ctx) => {
      if (ctx?.previous) queryClient.setQueryData(["listing", listingId], ctx.previous);
      toast.error(errorMessage(err));
    },
  });

  const postComment = useMutation({
    mutationFn: (body: string) => api.createComment(listingId, body),
    onSuccess: () => {
      setCommentBody("");
      queryClient.invalidateQueries({ queryKey: ["comments", listingId] });
      queryClient.invalidateQueries({ queryKey: ["listing", listingId] });
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const report = useMutation({
    mutationFn: (reason: string) => api.reportListing(listingId, reason),
    onSuccess: () => {
      setReportOpen(false);
      setReportReason("");
      toast.success("Thanks — this has been sent to our moderators.");
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const submitComment = (e: FormEvent) => {
    e.preventDefault();
    if (!ensureLogin() || !commentBody.trim()) return;
    postComment.mutate(commentBody.trim());
  };
  const submitReport = (e: FormEvent) => {
    e.preventDefault();
    if (reportReason.trim()) report.mutate(reportReason.trim());
  };

  if (listing.isPending) {
    return (
      <div className="mx-auto max-w-4xl">
        <div className="grid gap-8 md:grid-cols-2">
          <Skeleton className="aspect-square" />
          <div className="space-y-3">
            <Skeleton className="h-7 w-3/4" />
            <Skeleton className="h-4 w-1/2" />
            <Skeleton className="h-24 w-full" />
          </div>
        </div>
      </div>
    );
  }
  if (listing.isError) {
    return (
      <div className="mx-auto max-w-4xl">
        <ErrorState message={(listing.error as Error).message} onRetry={() => listing.refetch()} />
      </div>
    );
  }

  const item = listing.data!;
  const photo = item.photos?.[0];
  const isMine = user?.id === item.seller_id;

  return (
    <div className="mx-auto max-w-4xl">
      <nav className="editorial-enter mb-4 flex items-center gap-1 text-xs text-muted-foreground" aria-label="Breadcrumb">
        <Link to="/marketplace" className="transition-colors hover:text-foreground">
          Marketplace
        </Link>
        <ChevronRight size={13} />
        <span className="max-w-[240px] truncate font-medium text-foreground">{item.title}</span>
      </nav>

      <div className="panel editorial-enter grid gap-8 p-6 md:grid-cols-2">
        <div className="aspect-square overflow-hidden rounded-xl bg-accent">
          {photo ? (
            <img src={photo.image} alt={item.title} className="h-full w-full object-cover" />
          ) : (
            <div className="grid h-full place-items-center text-sm text-muted-foreground">No photo</div>
          )}
        </div>

        <div className="flex flex-col">
          <div className="flex items-start justify-between gap-3">
            <h1 className="font-display text-2xl font-bold">{item.title}</h1>
            <span className="shrink-0 font-mono text-2xl font-semibold">{naira(item.price)}</span>
          </div>
          <p className="mt-1 text-sm capitalize text-muted-foreground">
            {item.condition} · {item.location || "Uyo"}
          </p>
          <p className="mt-4 whitespace-pre-line text-muted-foreground">{item.description}</p>

          <Link
            to={item.merchant ? `/merchants/${item.merchant}` : "#"}
            className="mt-6 flex items-center justify-between gap-3 rounded-xl bg-accent p-4 transition-colors hover:bg-accent/70"
          >
            <div className="flex min-w-0 items-center gap-3">
              <Avatar src={item.seller_avatar} name={item.seller_name} size={40} />
              <div className="min-w-0">
                <div className="flex items-center gap-1">
                  <span className="truncate font-semibold">{item.seller_name}</span>
                  {item.merchant && <Verified size={15} className="shrink-0 text-primary" />}
                </div>
                <span className="text-xs text-muted-foreground">{item.merchant ? "Storefront" : "Individual seller"}</span>
              </div>
            </div>
            <Badge tone="success" className="shrink-0">
              <ShieldCheck size={11} /> Escrow protected
            </Badge>
          </Link>

          <div className="mt-6 flex gap-3">
            <Button onClick={() => buy(item.id)} disabled={isMine}>
              <Lock size={15} /> Buy with escrow
            </Button>
            <Button variant="secondary" onClick={() => messageSeller(item.id)} disabled={isMine}>
              Message seller
            </Button>
          </div>

          <div className="mt-4 flex items-center gap-4 text-sm text-muted-foreground">
            <button
              onClick={() => ensureLogin() && toggleLike.mutate()}
              aria-pressed={item.is_liked}
              className="flex items-center gap-1 font-medium transition-colors hover:text-destructive data-[liked=true]:text-destructive"
              data-liked={item.is_liked}
            >
              <span className={item.is_liked ? "text-destructive" : undefined}>♥</span> {item.likes_count} like{item.likes_count === 1 ? "" : "s"}
            </button>
            <span>{item.comments_count} comment{item.comments_count === 1 ? "" : "s"}</span>
            <button onClick={() => ensureLogin() && setReportOpen(true)} className="ml-auto flex items-center gap-1 transition-colors hover:text-destructive">
              <Flag size={13} /> Report
            </button>
          </div>
        </div>
      </div>

      <div className="editorial-enter mt-8 border-t border-border pt-5" style={prefs.stagger(1)}>
        <h2 className="mb-3 text-sm font-semibold">Comments</h2>
        <div className="space-y-3">
          {comments.isPending && <Skeleton className="h-10 w-full" />}
          {comments.data?.length === 0 && <p className="text-sm text-muted-foreground">No comments yet.</p>}
          {comments.data?.map((c) => (
            <div key={c.id} className="flex items-start gap-3 border-b border-border py-2 text-sm">
              <Avatar name={c.author_name} size={28} />
              <div className="min-w-0">
                <span className="font-medium">{c.author_name || `User #${c.author_id}`}</span>
                <span className="text-muted-foreground"> · {timeAgo(c.created_at)}</span>
                <p className="mt-0.5 text-muted-foreground">{c.body}</p>
              </div>
            </div>
          ))}
        </div>
        <form onSubmit={submitComment} className="mt-3 flex gap-2">
          <Input value={commentBody} onChange={(e) => setCommentBody(e.target.value)} placeholder={loggedIn ? "Add a comment" : "Log in to comment"} required />
          <Button type="submit" variant="secondary" loading={postComment.isPending}>
            Post
          </Button>
        </form>
      </div>

      <Modal open={reportOpen} onClose={() => setReportOpen(false)} title="Report this listing">
        <form onSubmit={submitReport} className="space-y-3">
          <Textarea value={reportReason} onChange={(e) => setReportReason(e.target.value)} rows={3} placeholder="What's wrong with this listing?" required autoFocus />
          <Button type="submit" className="w-full" loading={report.isPending}>
            Submit report
          </Button>
        </form>
      </Modal>
    </div>
  );
}
