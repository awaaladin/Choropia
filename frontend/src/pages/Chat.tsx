import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Send } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useParams } from "react-router";
import { toast } from "sonner";
import { Link } from "@/components/AppLink";
import { ErrorState, Input, Skeleton } from "@/components/ui";
import { errorMessage } from "@/lib/actions";
import { api, rows, wsUrl } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Message } from "@/lib/types";
import { cn } from "@/lib/utils";

export function ChatPage() {
  const { id } = useParams();
  const conversationId = Number(id);
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [live, setLive] = useState<Message[]>([]);
  const paneRef = useRef<HTMLDivElement>(null);
  const socketRef = useRef<WebSocket | null>(null);

  const history = useQuery({
    queryKey: ["messages", conversationId],
    queryFn: async () => rows(await api.getMessages(conversationId)),
    // No live WebSocket available (e.g. on Vercel without the realtime host) → poll instead.
    refetchInterval: wsUrl("/ws/chat/0/") ? false : 4000,
  });

  useEffect(() => setLive([]), [conversationId]);

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
        setLive((current) => (current.some((m) => m.id === message.id) ? current : [...current, message]));
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
  }, [conversationId]);

  const messages = [...(history.data ?? []), ...live.filter((m) => !(history.data ?? []).some((h) => h.id === m.id))];

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

  return (
    <div className="panel editorial-enter flex h-[75vh] flex-col overflow-hidden">
      <div className="flex items-center gap-2 border-b border-border p-3 md:hidden">
        <Link to="/messages" className="rounded-md p-1 text-muted-foreground hover:bg-accent" aria-label="Back to messages">
          <ArrowLeft size={18} />
        </Link>
        <span className="text-sm font-semibold">Conversation</span>
      </div>

      <div ref={paneRef} className="flex-1 space-y-2 overflow-y-auto bg-background p-4">
        {history.isPending && <Skeleton className="h-10 w-2/3" />}
        {history.isError && <ErrorState message={(history.error as Error).message} onRetry={() => history.refetch()} />}
        {history.isSuccess && messages.length === 0 && <p className="text-sm text-muted-foreground">No messages yet — say hello.</p>}
        {messages.map((m) => {
          const mine = m.sender_id === user?.id;
          return (
            <div key={m.id} className={cn("flex", mine ? "justify-end" : "justify-start")}>
              <div className={cn("animate-pop-in max-w-[75%] rounded-xl px-3 py-2 text-sm", mine ? "bg-primary text-primary-foreground" : "bg-accent text-foreground")}>
                {m.body}
              </div>
            </div>
          );
        })}
      </div>

      <form onSubmit={send} className="flex gap-2 border-t border-border bg-panel p-3">
        <Input value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Type a message" required disabled={sending} />
        <button type="submit" disabled={sending} className="grid size-10 shrink-0 place-items-center rounded-md bg-primary text-primary-foreground shadow-button transition-transform active:translate-y-px disabled:opacity-50">
          <Send size={16} />
        </button>
      </form>
    </div>
  );
}
