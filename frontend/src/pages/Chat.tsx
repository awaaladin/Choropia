import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ImagePlus, Mic, Send, Square, Tag, Trash2 } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router";
import { toast } from "sonner";
import { Link } from "@/components/AppLink";
import { Button } from "@/components/Button";
import { ErrorState, Input, Skeleton } from "@/components/ui";
import { OfferCard, OfferComposerSheet, PaySheet, type OfferCardActions } from "@/features/offers";
import { errorMessage } from "@/lib/actions";
import { api, rows, wsUrl } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { ChatOffer, Message } from "@/lib/types";
import { cn, naira } from "@/lib/utils";

const MAX_ATTACHMENT_BYTES = 3 * 1024 * 1024;

function ListingReferenceCard({
  message,
  onQuickReply,
  showQuickReplies,
}: {
  message: Message;
  onQuickReply: (reply: string) => void;
  showQuickReplies: boolean;
}) {
  const snapshot = message.listing_snapshot;
  const status = message.listing_status ?? snapshot?.status;
  const statusLabel = status === "active" ? "Available" : status === "sold" ? "Sold" : "No longer listed";
  const listingContent = (
    <>
      {snapshot?.thumbnail ? (
        <img src={snapshot.thumbnail} alt="" className="size-16 shrink-0 rounded-lg object-cover" />
      ) : (
        <div className="size-16 shrink-0 rounded-lg bg-accent" aria-hidden="true" />
      )}
      <div className="min-w-0">
        <p className="truncate font-semibold">{snapshot?.title ?? "Listing"}</p>
        {typeof snapshot?.price_kobo === "number" && (
          <p className="text-sm font-medium">{naira(snapshot.price_kobo / 100)}</p>
        )}
        <span className="text-xs text-muted-foreground">{statusLabel}</span>
      </div>
    </>
  );
  return (
    <div className="min-w-64 max-w-sm overflow-hidden rounded-xl border border-border bg-panel text-foreground">
      {message.listing ? (
        <Link to={`/listings/${message.listing}`} className="flex items-center gap-3 p-3">{listingContent}</Link>
      ) : (
        <div className="flex items-center gap-3 p-3">{listingContent}</div>
      )}
      {showQuickReplies && (
        <div className="flex flex-wrap gap-2 px-3 pb-3">
          {["Is this still available?", "Can you lower the price?"].map((reply) => (
            <button
              key={reply}
              type="button"
              onClick={() => onQuickReply(reply)}
              className="min-h-11 rounded-full border border-border px-3 text-xs hover:bg-accent"
            >
              {reply}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function ChatPage() {
  const { id } = useParams();
  const conversationId = Number(id);
  const navigate = useNavigate();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [live, setLive] = useState<Message[]>([]);
  const [offerDialogOpen, setOfferDialogOpen] = useState(false);
  const [payingOffer, setPayingOffer] = useState<ChatOffer | null>(null);
  const [deletingMessageId, setDeletingMessageId] = useState<number | null>(null);
  const [recording, setRecording] = useState(false);
  const paneRef = useRef<HTMLDivElement>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const recordStartedAtRef = useRef(0);
  const conversations = useQuery({
    queryKey: ["conversations"],
    queryFn: async () => rows(await api.listConversations()),
  });
  const conversation = conversations.data?.find((item) => item.id === conversationId);
  const canOffer = conversation?.listing != null && conversation.seller === user?.id;
  const myListings = useQuery({
    queryKey: ["myListings"],
    queryFn: async () => rows(await api.listMyListings()).filter((item) => item.status === "active" && (item.quantity ?? 1) > 0),
    enabled: !!canOffer,
  });
  useEffect(() => () => {
    const recorder = recorderRef.current;
    if (recorder) recorder.onstop = null;
    if (recorder?.state !== "inactive") recorder?.stop();
    mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
  }, []);
  const history = useQuery({
    queryKey: ["messages", conversationId],
    queryFn: async () => rows(await api.getMessages(conversationId)),
    // No live WebSocket available (e.g. on Vercel without the realtime host) → poll instead.
    refetchInterval: wsUrl("/ws/chat/0/") ? false : 4000,
  });

  useEffect(() => setLive([]), [conversationId]);

  // Fetching the messages marks them read on the server, so the unread badge must be refreshed to drop them.
  useEffect(() => {
    if (history.isSuccess) {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
    }
  }, [history.dataUpdatedAt, history.isSuccess, queryClient]);

  useEffect(() => {
    const url = wsUrl(`/ws/chat/${conversationId}/`);
    if (!url) return;
    let closed = false;
    let retry = 0;
    let timer: number | undefined;

    const connect = () => {
      const socket = new WebSocket(url);
      socketRef.current = socket;
      socket.onopen = () => {
        // Back after a drop: anything may have changed while we were away (an offer paid, expired, cancelled).
        if (retry > 0) queryClient.invalidateQueries({ queryKey: ["messages", conversationId] });
        retry = 0;
      };
      socket.onmessage = (event) => {
        const message = JSON.parse(event.data) as Message;
        setLive((current) => {
          const index = current.findIndex((m) => m.id === message.id);
          if (index < 0) return [...current, message];
          return current.map((item, itemIndex) => itemIndex === index ? message : item);
        });
        if (message.event === "offer.updated") {
          queryClient.invalidateQueries({ queryKey: ["messages", conversationId] });
        }
      };
      socket.onclose = () => {
        if (closed) return;
        retry += 1;
        timer = window.setTimeout(connect, Math.min(15_000, 1000 * 2 ** retry));
      };
    };
    connect();
    return () => {
      closed = true;
      window.clearTimeout(timer);
      socketRef.current?.close();
      socketRef.current = null;
    };
  }, [conversationId, queryClient]);

  const messagesById = new Map<number, Message>();
  for (const message of history.data ?? []) messagesById.set(message.id, message);
  for (const message of live) messagesById.set(message.id, message);
  const messages = [...messagesById.values()].sort((a, b) => a.created_at.localeCompare(b.created_at));

  useEffect(() => {
    paneRef.current?.scrollTo({ top: paneRef.current.scrollHeight, behavior: "smooth" });
  }, [messages.length]);

  const send = async (e: FormEvent) => {
    e.preventDefault();
    const body = draft.trim();
    if (!body) return;
    const socket = socketRef.current;
    setDraft("");
    setSending(true);
    try {
      if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ body }));
      } else {
        const message = await api.sendMessage(conversationId, body);
        setLive((current) => [...current, message]);
      }
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
    } catch (err) {
      toast.error(errorMessage(err));
      setDraft(body);
    } finally {
      setSending(false);
    }
  };

  const sendAttachment = async (file: File, durationSeconds?: number) => {
    if (file.size > MAX_ATTACHMENT_BYTES) {
      toast.error("Attachments can be at most 3 MB.");
      return;
    }
    const body = draft.trim();
    setSending(true);
    try {
      const message = await api.sendAttachment(conversationId, file, durationSeconds, body);
      setLive((current) => [...current, message]);
      setDraft("");
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setSending(false);
    }
  };

  const startRecording = async () => {
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      toast.error("Voice recording is not supported in this browser.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = stream;
      const mimeType = ["audio/webm;codecs=opus", "audio/mp4", "audio/ogg;codecs=opus"]
        .find((type) => MediaRecorder.isTypeSupported(type));
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      const chunks: BlobPart[] = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size) chunks.push(event.data);
      };
      recorder.onstop = () => {
        stream.getTracks().forEach((track) => track.stop());
        mediaStreamRef.current = null;
        recorderRef.current = null;
        const duration = Math.max(1, Math.ceil((Date.now() - recordStartedAtRef.current) / 1000));
        if (duration > 600) {
          toast.error("Voice notes can be at most 10 minutes.");
          return;
        }
        const type = recorder.mimeType || "audio/webm";
        const extension = type.includes("mp4") ? "m4a" : type.includes("ogg") ? "ogg" : "webm";
        void sendAttachment(new File([new Blob(chunks, { type })], `voice-note.${extension}`, { type }), duration);
      };
      recorderRef.current = recorder;
      recordStartedAtRef.current = Date.now();
      recorder.start();
      setRecording(true);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not access the microphone.");
    }
  };

  const stopRecording = () => {
    const recorder = recorderRef.current;
    if (recorder && recorder.state !== "inactive") {
      setRecording(false);
      recorder.stop();
    }
  };

  const refreshOffers = () => queryClient.invalidateQueries({ queryKey: ["messages", conversationId] });

  const offerActions: OfferCardActions = {
    onPay: (offer) => setPayingOffer(offer),
    onDecline: async (offer) => {
      try {
        await api.declineOffer(offer.id);
        toast("Offer declined.");
      } catch (error) {
        toast.error(errorMessage(error));
      } finally {
        await refreshOffers();
      }
    },
    onCancel: async (offer) => {
      try {
        await api.cancelOffer(offer.id);
        toast("Offer cancelled.");
      } catch (error) {
        toast.error(errorMessage(error));
      } finally {
        await refreshOffers();
      }
    },
    onCheckPayment: async (offer) => {
      try {
        const updated = await api.verifyOfferPayment(offer.id);
        if (updated.status === "paid") toast.success("Payment received. It's held safely in escrow.");
        else if (updated.last_payment_failed) toast.error("The payment didn't go through. Nothing was taken.");
        else toast("No payment yet. If you've just paid, give it a minute.");
      } catch (error) {
        toast.error(errorMessage(error));
      } finally {
        await refreshOffers();
      }
    },
    onReleased: () => {
      toast.success("Handover confirmed. Your payout is on its way.");
      void refreshOffers();
    },
  };

  const deleteMessage = async (message: Message) => {
    if (!window.confirm("Delete this message for everyone?")) return;
    setDeletingMessageId(message.id);
    try {
      await api.deleteMessage(message.id);
      const deleted = (item: Message): Message => ({
        ...item,
        body: "",
        attachment: null,
        attachment_type: "",
        duration_seconds: null,
        is_deleted: true,
      });
      queryClient.setQueryData<Message[]>(["messages", conversationId], (current) =>
        current?.map((item) => item.id === message.id ? deleted(item) : item),
      );
      setLive((current) => current.map((item) => item.id === message.id ? deleted(item) : item));
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
      toast.success("Message deleted for everyone.");
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setDeletingMessageId(null);
    }
  };

  return (
    <div className="panel editorial-enter flex h-[75vh] flex-col overflow-hidden">
      <div className="flex items-center gap-2 border-b border-border p-3 md:hidden">
        <Link to="/messages" className="rounded-md p-1 text-muted-foreground hover:bg-accent" aria-label="Back to messages">
          <ArrowLeft size={18} />
        </Link>
        {conversation?.other_party_id ? (
          <Link to={`/users/${conversation.other_party_id}`} className="text-sm font-semibold hover:underline">
            {conversation.other_party_name ?? "Conversation"}
          </Link>
        ) : (
          <span className="text-sm font-semibold">{conversation?.other_party_name ?? "Conversation"}</span>
        )}
      </div>

      <div ref={paneRef} className="flex-1 space-y-2 overflow-y-auto bg-background p-4">
        {history.isPending && <Skeleton className="h-10 w-2/3" />}
        {history.isError && <ErrorState message={(history.error as Error).message} onRetry={() => history.refetch()} />}
        {history.isSuccess && messages.length === 0 && <p className="text-sm text-muted-foreground">No messages yet — say hello.</p>}
        {messages.map((m) => {
          const mine = m.sender_id === user?.id;
          return (
            <div key={m.id} className={cn("flex", mine ? "justify-end" : "justify-start")}>
              <div className={cn("flex max-w-[90%] items-end gap-1", mine ? "flex-row-reverse" : "flex-row")}>
                <div className={cn("animate-pop-in max-w-[calc(100%-2.5rem)] rounded-xl text-sm", m.type === "listing_ref" || m.type === "offer" ? "bg-transparent" : `px-3 py-2 ${mine ? "bg-primary text-primary-foreground" : "bg-accent text-foreground"}`)}>
                  {m.type === "offer" && m.offer ? (
                    <OfferCard offer={m.offer} actions={offerActions} />
                  ) : m.type === "listing_ref" ? (
                    <ListingReferenceCard message={m} onQuickReply={setDraft} showQuickReplies={mine} />
                  ) : m.is_deleted ? (
                    <p className="italic opacity-75">Message deleted</p>
                  ) : (
                    <>
                      {m.attachment_type === "image" && m.attachment && (
                        <a href={m.attachment} target="_blank" rel="noreferrer">
                          <img src={m.attachment} alt="Chat attachment" className="mb-2 max-h-80 max-w-full rounded-lg object-contain" />
                        </a>
                      )}
                      {m.attachment_type === "audio" && m.attachment && (
                        <audio controls preload="metadata" src={m.attachment} className="mb-2 max-w-full" />
                      )}
                      {m.attachment_type === "file" && m.attachment && (
                        <a href={m.attachment} target="_blank" rel="noreferrer" className="mb-2 block underline">Open attachment</a>
                      )}
                      {m.body}
                    </>
                  )}
                </div>
                {mine && m.type === "text" && !m.is_deleted && (
                  <button
                    type="button"
                    aria-label="Delete message for everyone"
                    title="Delete for everyone"
                    disabled={deletingMessageId === m.id}
                    onClick={() => void deleteMessage(m)}
                    className="grid size-8 shrink-0 place-items-center rounded-full text-muted-foreground hover:bg-accent disabled:opacity-50"
                  >
                    <Trash2 size={15} />
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <div className="flex items-center justify-between gap-2 border-t border-border bg-panel p-3">
        {canOffer && (
          <Button
            variant="secondary"
            disabled={myListings.isPending || !myListings.data?.length}
            onClick={() => setOfferDialogOpen(true)}
            title={!myListings.data?.length ? "You need an active listing to make an offer" : undefined}
          >
            <Tag size={15} /> Offer a different price
          </Button>
        )}
        <form onSubmit={send} className="flex min-w-0 flex-1 gap-2">
          <input
            ref={fileInputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp,image/gif"
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0];
              event.target.value = "";
              if (file) void sendAttachment(file);
            }}
          />
          <button type="button" aria-label="Attach image" title="Attach image" disabled={sending || recording} onClick={() => fileInputRef.current?.click()} className="grid size-10 shrink-0 place-items-center rounded-md border border-border disabled:opacity-50">
            <ImagePlus size={16} />
          </button>
          <Input value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Type a message" disabled={sending || recording} />
          <button type="button" aria-label={recording ? "Stop recording" : "Record voice note"} title={recording ? "Stop recording" : "Record voice note"} disabled={sending} onClick={() => recording ? stopRecording() : void startRecording()} className="grid size-10 shrink-0 place-items-center rounded-md border border-border disabled:opacity-50">
            {recording ? <Square size={16} /> : <Mic size={16} />}
          </button>
          <button type="submit" disabled={sending || recording || !draft.trim()} aria-label="Send message" className="grid size-10 shrink-0 place-items-center rounded-md bg-primary text-primary-foreground shadow-button transition-transform active:translate-y-px disabled:opacity-50">
            <Send size={16} />
          </button>
        </form>
      </div>

      {canOffer && (
        <OfferComposerSheet
          open={offerDialogOpen}
          onClose={() => setOfferDialogOpen(false)}
          conversationId={conversationId}
          listings={myListings.data ?? []}
          defaultListingId={conversation?.listing}
          onSent={() => {
            setOfferDialogOpen(false);
            toast.success("Offer sent. The buyer can pay from the chat.");
            void refreshOffers();
            queryClient.invalidateQueries({ queryKey: ["conversations"] });
          }}
        />
      )}
      {payingOffer && (
        <PaySheet
          open={payingOffer !== null}
          onClose={() => setPayingOffer(null)}
          offer={payingOffer}
          onCheckout={(result) => {
            void refreshOffers();
            if (result.authorization_url) window.location.assign(result.authorization_url);
            else navigate(`/orders/${result.order_id}`);
          }}
        />
      )}
    </div>
  );
}
