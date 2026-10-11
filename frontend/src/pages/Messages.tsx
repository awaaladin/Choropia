import { useQuery } from "@tanstack/react-query";
import { MessageCircle } from "lucide-react";
import { Outlet, useParams } from "react-router";
import { Link } from "@/components/AppLink";
import { Avatar, EmptyState, ErrorState, Skeleton } from "@/components/ui";
import { api, rows } from "@/lib/api";
import { cn, timeAgo } from "@/lib/utils";

export function MessagesLayout() {
  const { id } = useParams();
  const conversations = useQuery({ queryKey: ["conversations"], queryFn: async () => rows(await api.listConversations()), refetchInterval: 30_000 });

  return (
    <div className="mx-auto grid max-w-5xl gap-5 md:grid-cols-[320px_minmax(0,1fr)]">
      <div className={cn("panel editorial-enter divide-y divide-border overflow-hidden", id && "hidden md:block")}>
        <h1 className="p-4 font-display text-lg font-bold">Messages</h1>
        {conversations.isPending && Array.from({ length: 3 }, (_, i) => <Skeleton key={i} className="m-3 h-14 rounded-md" />)}
        {conversations.isError && <ErrorState message={(conversations.error as Error).message} onRetry={() => conversations.refetch()} />}
        {conversations.isSuccess && conversations.data.length === 0 && (
          <EmptyState icon={<MessageCircle size={20} />} title="No conversations yet" hint="Message a seller from a listing to start one." />
        )}
        {conversations.data?.map((c) => (
          <Link
            key={c.id}
            to={`/messages/${c.id}`}
            className={cn("flex items-center gap-3 p-4 transition-colors hover:bg-accent", Number(id) === c.id && "bg-accent")}
          >
            <Avatar src={c.other_party_avatar} name={c.other_party_name} size={44} />
            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between gap-2">
                <span className="truncate font-semibold">{c.other_party_name || "Choropia user"}</span>
                {c.last_message && <span className="shrink-0 text-xs text-muted-foreground">{timeAgo(c.last_message.created_at)}</span>}
              </div>
              <p className="truncate text-xs font-medium text-primary">{c.listing_title || `Listing #${c.listing}`}</p>
              <p className="truncate text-sm text-muted-foreground">{c.last_message ? c.last_message.body : "No messages yet"}</p>
            </div>
          </Link>
        ))}
      </div>
      <div className={cn(!id && "hidden md:block")}>
        <Outlet />
      </div>
    </div>
  );
}

export function MessagesIndex() {
  return (
    <div className="panel hidden h-full min-h-[50vh] place-items-center p-6 text-sm text-muted-foreground md:grid">
      Pick a conversation to start chatting.
    </div>
  );
}
