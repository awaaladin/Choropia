import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Send, Tag } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useParams } from "react-router";
import { toast } from "sonner";
import { Link } from "@/components/AppLink";
import { Button } from "@/components/Button";
import { ErrorState, Field, Input, Modal, Select, Skeleton, Textarea } from "@/components/ui";
import { errorMessage } from "@/lib/actions";
import { api, rows, wsUrl } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { ChatOffer, Message, OfferDeliveryMethod } from "@/lib/types";
import { cn, naira } from "@/lib/utils";

const DELIVERY_LABELS: Record<OfferDeliveryMethod, string> = {
  rider: "Choropia rider",
  seller_delivers: "Seller delivers",
  meetup: "Meet up",
};

const OFFER_STATUS_LABELS: Record<ChatOffer["status"], string> = {
  pending: "Waiting for buyer",
  payment_processing: "Payment in progress",
  paid: "Paid into escrow",
  declined: "Declined by buyer",
  cancelled: "Cancelled by seller",
  expired: "Expired",
  superseded: "Replaced by a newer offer",
};

function amountToKobo(value: string) {
  const cleaned = value.trim().replace(/,/g, "");
  if (!/^\d+(?:\.\d{1,2})?$/.test(cleaned)) return null;
  const [whole, fraction = ""] = cleaned.split(".");
  const amount = Number(whole) * 100 + Number(fraction.padEnd(2, "0"));
  return Number.isSafeInteger(amount) && amount > 0 ? amount : null;
}

function ChatOfferCard({
  offer,
  onCancel,
  onDecline,
  busy,
}: {
  offer: ChatOffer;
  onCancel: (offer: ChatOffer) => void;
  onDecline: (offer: ChatOffer) => void;
  busy: boolean;
}) {
  const methods = offer.delivery_method
    ? [DELIVERY_LABELS[offer.delivery_method]]
    : offer.allowed_delivery_methods.map((method) => DELIVERY_LABELS[method]);
  return (
    <div className="min-w-64 max-w-sm rounded-xl border border-border bg-panel p-4 text-foreground">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-xs text-muted-foreground">{offer.listing.title}</p>
          <p className="mt-1 font-display text-xl font-bold">{naira(offer.amount_kobo / 100)}</p>
          <p className="text-xs text-muted-foreground">
            Listed at {naira(offer.listing_price_kobo / 100)}
          </p>
        </div>
        <span className="shrink-0 rounded-full bg-accent px-2 py-1 text-[10px] font-semibold">
          {OFFER_STATUS_LABELS[offer.status]}
        </span>
      </div>
      <p className="mt-3 text-xs text-muted-foreground">
        Handover: {methods.length ? methods.join(", ") : "No method selected"}
      </p>
      {offer.note && <p className="mt-2 whitespace-pre-wrap text-sm">{offer.note}</p>}
      {offer.status === "pending" && offer.viewer_role === "buyer" && (
        <div className="mt-3 space-y-2 border-t border-border pt-3">
          <p className="text-xs text-muted-foreground">
            This chat offer can’t be paid through escrow yet.
          </p>
          <Button variant="secondary" disabled={busy} onClick={() => onDecline(offer)}>
            Decline offer
          </Button>
        </div>
      )}
      {offer.status === "pending" && offer.viewer_role === "seller" && (
        <div className="mt-3 border-t border-border pt-3">
          <Button variant="secondary" disabled={busy} onClick={() => onCancel(offer)}>
            Cancel offer
          </Button>
        </div>
      )}
    </div>
  );
}

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
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [live, setLive] = useState<Message[]>([]);
  const [offerDialogOpen, setOfferDialogOpen] = useState(false);
  const [selectedListingId, setSelectedListingId] = useState<number | "">("");
  const [offerAmount, setOfferAmount] = useState("");
  const [offerMethods, setOfferMethods] = useState<OfferDeliveryMethod[]>(["meetup"]);
  const [offerNote, setOfferNote] = useState("");
  const [offerPin, setOfferPin] = useState("");
  const [offerSending, setOfferSending] = useState(false);
  const [busyOfferId, setBusyOfferId] = useState<string | null>(null);
  const paneRef = useRef<HTMLDivElement>(null);
  const socketRef = useRef<WebSocket | null>(null);
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
  const selectedListing = myListings.data?.find((item) => item.id === selectedListingId);
  const listingDelivery = useQuery({
    queryKey: ["listingDelivery", selectedListingId],
    queryFn: () => api.dispatch.listingDelivery(Number(selectedListingId)),
    enabled: offerDialogOpen && !!selectedListingId,
  });

  useEffect(() => {
    if (!selectedListingId && myListings.data?.length) {
      const currentThreadListing = myListings.data.find((item) => item.id === conversation?.listing);
      setSelectedListingId(currentThreadListing?.id ?? myListings.data[0].id);
    }
  }, [conversation?.listing, myListings.data, selectedListingId]);

  useEffect(() => {
    if (selectedListing) setOfferAmount(selectedListing.price);
  }, [selectedListing?.id]);

  useEffect(() => {
    if (!listingDelivery.data?.enabled) {
      setOfferMethods((current) => current.filter((method) => method !== "rider"));
    }
  }, [listingDelivery.data?.enabled, selectedListingId]);

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
      socket.onopen = () => (retry = 0);
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

  const submitOffer = async (e: FormEvent) => {
    e.preventDefault();
    const amountKobo = amountToKobo(offerAmount);
    const methods = offerMethods.filter((method) => method !== "rider" || listingDelivery.data?.enabled);
    if (!selectedListingId || amountKobo === null || !methods.length || !offerPin.trim()) {
      toast.error("Choose a listing, enter an amount, select a handover method and enter your PIN.");
      return;
    }
    setOfferSending(true);
    try {
      await api.createOffer(conversationId, {
        listing_id: selectedListingId,
        amount_kobo: amountKobo,
        allowed_delivery_methods: methods,
        note: offerNote.trim(),
        pin: offerPin,
      });
      setOfferDialogOpen(false);
      setOfferPin("");
      setOfferNote("");
      queryClient.invalidateQueries({ queryKey: ["messages", conversationId] });
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
      toast.success("Offer sent.");
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setOfferSending(false);
    }
  };

  const updateOffer = async (offer: ChatOffer, action: "cancel" | "decline") => {
    const verb = action === "cancel" ? "cancel" : "decline";
    if (!window.confirm(`Are you sure you want to ${verb} this offer?`)) return;
    setBusyOfferId(offer.id);
    try {
      if (action === "cancel") await api.cancelOffer(offer.id);
      else await api.declineOffer(offer.id);
      await queryClient.invalidateQueries({ queryKey: ["messages", conversationId] });
      toast.success(action === "cancel" ? "Offer cancelled." : "Offer declined.");
    } catch (error) {
      toast.error(errorMessage(error));
      queryClient.invalidateQueries({ queryKey: ["messages", conversationId] });
    } finally {
      setBusyOfferId(null);
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
              <div className={cn("animate-pop-in max-w-[85%] rounded-xl text-sm", m.type === "listing_ref" || m.type === "offer" ? "bg-transparent" : `px-3 py-2 ${mine ? "bg-primary text-primary-foreground" : "bg-accent text-foreground"}`)}>
                {m.type === "offer" && m.offer ? (
                  <ChatOfferCard
                    offer={m.offer}
                    onCancel={(offer) => void updateOffer(offer, "cancel")}
                    onDecline={(offer) => void updateOffer(offer, "decline")}
                    busy={busyOfferId === m.offer.id}
                  />
                ) : m.type === "listing_ref" ? (
                  <ListingReferenceCard message={m} onQuickReply={setDraft} showQuickReplies={mine} />
                ) : (
                  m.body
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
        <Input value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Type a message" required disabled={sending} />
        <button type="submit" disabled={sending} className="grid size-10 shrink-0 place-items-center rounded-md bg-primary text-primary-foreground shadow-button transition-transform active:translate-y-px disabled:opacity-50">
          <Send size={16} />
        </button>
        </form>
      </div>

      <Modal open={offerDialogOpen} onClose={() => setOfferDialogOpen(false)} title="Offer a different price">
        <form onSubmit={submitOffer} className="space-y-3">
          <Field label="Your listing">
            <Select value={selectedListingId} onChange={(e) => setSelectedListingId(Number(e.target.value))} required>
              {(myListings.data ?? []).map((listing) => (
                <option key={listing.id} value={listing.id}>{listing.title}</option>
              ))}
            </Select>
          </Field>
          <Field label="Offer amount (₦)">
            <Input
              inputMode="decimal"
              value={offerAmount}
              onChange={(e) => setOfferAmount(e.target.value)}
              placeholder="e.g. 185000"
              required
            />
          </Field>
          <fieldset>
            <legend className="mb-1.5 text-xs font-semibold text-muted-foreground">Handover methods</legend>
            <div className="space-y-2">
              {(Object.entries(DELIVERY_LABELS) as [OfferDeliveryMethod, string][])
                .filter(([method]) => method !== "rider" || listingDelivery.data?.enabled)
                .map(([method, label]) => (
                <label key={method} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={offerMethods.includes(method)}
                    onChange={(e) => setOfferMethods((current) =>
                      e.target.checked ? [...current, method] : current.filter((value) => value !== method),
                    )}
                  />
                  {label}
                </label>
              ))}
            </div>
            {!listingDelivery.data?.enabled && (
              <p className="mt-1 text-xs text-muted-foreground">Set up rider delivery in the listing settings to offer that option.</p>
            )}
          </fieldset>
          <Field label="Note (optional)">
            <Textarea value={offerNote} onChange={(e) => setOfferNote(e.target.value)} maxLength={300} rows={2} />
          </Field>
          <Field label="Transaction PIN">
            <Input type="password" inputMode="numeric" autoComplete="new-password" maxLength={12} value={offerPin} onChange={(e) => setOfferPin(e.target.value)} required />
          </Field>
          <p className="text-xs text-muted-foreground">Your PIN approves this offer. The buyer can decline it; escrow checkout for chat offers is not available yet.</p>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="secondary" onClick={() => setOfferDialogOpen(false)}>Back</Button>
            <Button type="submit" loading={offerSending} disabled={!offerMethods.length}>Send offer</Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
