import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PackageSearch, Truck } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { Link } from "@/components/AppLink";
import { Button } from "@/components/Button";
import { EmptyState, ErrorState, Input, Pill, Segmented, Skeleton } from "@/components/ui";
import { errorMessage } from "@/lib/actions";
import { api, rows } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { STATUS_LABELS, naira } from "@/lib/utils";

export function OrdersPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [role, setRole] = useState<"buying" | "selling">("buying");
  const [status, setStatus] = useState("all");
  const [search, setSearch] = useState("");

  const orders = useQuery({ queryKey: ["orders"], queryFn: async () => rows(await api.listOrders()) });
  const dispatch = useMutation({
    mutationFn: (orderId: number) => api.assignCourier(orderId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["orders"] }),
    onError: (err) => toast.error(errorMessage(err)),
  });

  const scoped = useMemo(
    () => (orders.data ?? []).filter((o) => (role === "buying" ? o.buyer === user?.id : o.seller === user?.id)),
    [orders.data, role, user],
  );
  const counts = useMemo(() => {
    const map: Record<string, number> = {};
    scoped.forEach((o) => (map[o.status] = (map[o.status] ?? 0) + 1));
    return map;
  }, [scoped]);
  const tabs = [{ key: "all", label: "All" }, ...Object.keys(STATUS_LABELS).filter((k) => counts[k]).map((k) => ({ key: k, label: STATUS_LABELS[k] }))];

  const results = scoped
    .filter((o) => status === "all" || o.status === status)
    .filter((o) => {
      if (!search.trim()) return true;
      const other = role === "buying" ? o.seller_name : o.buyer_name;
      return `${o.listing_title ?? ""} ${other ?? ""}`.toLowerCase().includes(search.trim().toLowerCase());
    });

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="editorial-enter font-display text-2xl font-bold">Orders</h1>

      <div className="editorial-enter mt-4" style={{ maxWidth: 220 }}>
        <Segmented
          options={["buying", "selling"] as const}
          value={role}
          onChange={(v) => {
            setRole(v);
            setStatus("all");
          }}
        />
      </div>

      {tabs.length > 1 && (
        <div className="editorial-enter mt-4 flex items-center gap-2 overflow-x-auto pb-1">
          {tabs.map((t) => (
            <Pill key={t.key} active={status === t.key} onClick={() => setStatus(t.key)}>
              {t.label}
              {t.key !== "all" && ` (${counts[t.key]})`}
            </Pill>
          ))}
        </div>
      )}

      <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search by listing or person…" className="editorial-enter mt-4" />

      <div className="panel editorial-enter mt-4 divide-y divide-border">
        {orders.isPending && Array.from({ length: 3 }, (_, i) => <Skeleton key={i} className="m-4 h-14 rounded-md" />)}
        {orders.isError && <ErrorState message={(orders.error as Error).message} onRetry={() => orders.refetch()} />}
        {orders.isSuccess && results.length === 0 && (
          <EmptyState icon={<PackageSearch size={20} />} title="No orders here" hint={role === "buying" ? "Orders you place will show up here." : "Orders placed on your listings will show up here."} />
        )}
        {results.map((order) => {
          const other = role === "buying" ? order.seller_name : order.buyer_name;
          const canDispatch = role === "selling" && order.status === "paid_escrow";
          return (
            <div key={order.id} className="flex items-center gap-3 p-4">
              <Link to={`/orders/${order.id}`} className="flex min-w-0 flex-1 items-center gap-3 transition-opacity hover:opacity-80">
                <div className="size-12 shrink-0 overflow-hidden rounded-md bg-accent">
                  {order.listing_cover_photo && <img src={order.listing_cover_photo} alt="" className="h-full w-full object-cover" />}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">{order.listing_title || `Order #${order.id}`}</p>
                  <p className="text-sm text-muted-foreground">
                    {role === "buying" ? "Seller" : "Buyer"}: {other || "—"} · {naira(order.price)}
                  </p>
                </div>
              </Link>
              <span className="shrink-0 rounded-full bg-accent px-2.5 py-0.5 text-[10px] font-semibold text-muted-foreground">{STATUS_LABELS[order.status] || order.status}</span>
              {canDispatch && (
                <Button className="shrink-0" loading={dispatch.isPending} onClick={() => dispatch.mutate(order.id)}>
                  <Truck size={14} /> Assign courier
                </Button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
