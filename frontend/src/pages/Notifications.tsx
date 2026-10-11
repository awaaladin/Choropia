import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, Gavel, Handshake, Mail, UserPlus } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Link } from "@/components/AppLink";
import { Button } from "@/components/Button";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui";
import { api, rows } from "@/lib/api";
import type { AppNotification } from "@/lib/types";
import { cn, timeAgo } from "@/lib/utils";

const TYPE_ICONS: Record<AppNotification["notification_type"], LucideIcon> = {
  follow: UserPlus,
  message: Mail,
  order_status: Handshake,
  dispute: Gavel,
};

function targetHref(n: AppNotification): string | null {
  if (!n.target_object_id) return null;
  if (n.target_type === "conversation") return `/messages/${n.target_object_id}`;
  if (n.target_type === "order") return `/orders/${n.target_object_id}`;
  if (n.target_type === "merchant") return `/merchants/${n.target_object_id}`;
  return null;
}

export function NotificationsPage() {
  const queryClient = useQueryClient();
  const notifications = useQuery({ queryKey: ["notifications"], queryFn: async () => rows(await api.listNotifications()) });
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["notifications"] });
  const markRead = useMutation({ mutationFn: (id: number) => api.markNotificationRead(id), onSuccess: invalidate });
  const markAll = useMutation({ mutationFn: api.markAllNotificationsRead, onSuccess: invalidate });

  return (
    <div className="mx-auto max-w-2xl">
      <div className="editorial-enter flex items-center justify-between">
        <h1 className="font-display text-2xl font-bold">Notifications</h1>
        <Button variant="secondary" onClick={() => markAll.mutate()} loading={markAll.isPending} disabled={!notifications.data?.some((n) => !n.is_read)}>
          Mark all read
        </Button>
      </div>

      <div className="panel editorial-enter mt-4 divide-y divide-border">
        {notifications.isPending && Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="m-4 h-10 rounded-md" />)}
        {notifications.isError && <ErrorState message={(notifications.error as Error).message} onRetry={() => notifications.refetch()} />}
        {notifications.isSuccess && notifications.data.length === 0 && <EmptyState icon={<Bell size={20} />} title="You're all caught up" />}
        {notifications.data?.map((n) => {
          const Icon = TYPE_ICONS[n.notification_type] ?? Bell;
          const href = targetHref(n);
          const body = (
            <>
              <Icon size={18} className={cn("mt-0.5 shrink-0", n.is_read ? "text-muted-foreground" : "text-primary")} />
              <div className="min-w-0 flex-1">
                <p className="text-sm">{n.verb}</p>
                <p className="mt-1 text-xs text-muted-foreground">{timeAgo(n.created_at)}</p>
              </div>
              {!n.is_read && (
                <button
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    markRead.mutate(n.id);
                  }}
                  className="shrink-0 text-xs font-medium text-primary hover:underline"
                >
                  Mark read
                </button>
              )}
            </>
          );
          const className = cn("flex items-start gap-3 p-4", !n.is_read && "bg-accent/40", href && "transition-colors hover:bg-accent");
          return href ? (
            <Link key={n.id} to={href} className={className} onClick={() => !n.is_read && markRead.mutate(n.id)}>
              {body}
            </Link>
          ) : (
            <div key={n.id} className={className}>
              {body}
            </div>
          );
        })}
      </div>
    </div>
  );
}
