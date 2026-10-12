import { useQuery } from "@tanstack/react-query";
import { ArrowDownLeft, ArrowUpRight, ExternalLink, Info, Lock, Wallet as WalletIcon } from "lucide-react";
import { Link } from "@/components/AppLink";
import { Badge, EmptyState, ErrorState, Skeleton } from "@/components/ui";
import { api, rows } from "@/lib/api";
import { naira, timeAgo } from "@/lib/utils";

const STATUS_TONE: Record<string, "muted" | "success" | "primary" | "danger"> = {
  paid_held: "primary",
  released: "success",
  refunded: "danger",
  failed: "danger",
};

function etherscan(txHash: string) {
  return `https://sepolia.etherscan.io/tx/${txHash}`;
}

export function WalletPage() {
  const summary = useQuery({ queryKey: ["wallet-summary"], queryFn: api.getWalletSummary });
  const transactions = useQuery({ queryKey: ["wallet-transactions"], queryFn: async () => rows(await api.listWalletTransactions()) });

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="editorial-enter font-display text-2xl font-bold">Wallet</h1>
      <p className="editorial-enter mt-1 text-sm text-muted-foreground">Where your escrow money actually stands — paid in, held, and released.</p>

      {summary.isPending && (
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <Skeleton className="h-32" />
          <Skeleton className="h-32" />
        </div>
      )}
      {summary.isError && <ErrorState message={(summary.error as Error).message} onRetry={() => summary.refetch()} />}
      {summary.data && (
        <div className="editorial-enter mt-4 grid gap-4 sm:grid-cols-2">
          <div className="panel p-5">
            <div className="flex items-center gap-2 text-sm font-semibold text-muted-foreground">
              <ArrowUpRight size={15} className="text-success" /> As a seller
            </div>
            <p className="mt-3 text-2xl font-semibold">{naira(summary.data.selling.released_total)}</p>
            <p className="text-xs text-muted-foreground">Released to you</p>
            <p className="mt-3 text-sm font-medium">{naira(summary.data.selling.held_total)}</p>
            <p className="text-xs text-muted-foreground">Still held in escrow from buyers</p>
          </div>
          <div className="panel p-5">
            <div className="flex items-center gap-2 text-sm font-semibold text-muted-foreground">
              <ArrowDownLeft size={15} className="text-primary" /> As a buyer
            </div>
            <p className="mt-3 text-2xl font-semibold">{naira(summary.data.buying.held_total)}</p>
            <p className="text-xs text-muted-foreground">Currently held, awaiting your delivery confirmation</p>
            <p className="mt-3 text-sm font-medium">{naira(summary.data.buying.spent_total)}</p>
            <p className="text-xs text-muted-foreground">Total ever paid into escrow</p>
          </div>
        </div>
      )}

      <div className="editorial-enter mt-4 flex items-start gap-2 rounded-lg bg-accent p-3 text-xs leading-5 text-muted-foreground">
        <Info size={14} className="mt-0.5 shrink-0 text-primary" />
        <span>
          "Released" means Choropia has approved the payout, held on the escrow checkout page for now — automatic crypto payouts aren't
          wired up yet. Payments settle in ETH on Sepolia (testnet); amounts above are shown in the NGN equivalent used at checkout.
        </span>
      </div>

      <h2 className="editorial-enter mb-2 mt-6 text-sm font-semibold">Transactions</h2>
      <div className="panel editorial-enter divide-y divide-border">
        {transactions.isPending && Array.from({ length: 3 }, (_, i) => <Skeleton key={i} className="m-4 h-12 rounded-md" />)}
        {transactions.isError && <ErrorState message={(transactions.error as Error).message} onRetry={() => transactions.refetch()} />}
        {transactions.isSuccess && transactions.data.length === 0 && (
          <EmptyState icon={<WalletIcon size={20} />} title="No transactions yet" hint="Payments you make or receive through escrow will show up here." />
        )}
        {transactions.data?.map((tx) => (
          <div key={tx.id} className="flex items-center gap-3 p-4">
            <span className="grid size-9 shrink-0 place-items-center rounded-full bg-accent text-muted-foreground">
              {tx.status === "paid_held" ? <Lock size={15} /> : tx.role === "selling" ? <ArrowUpRight size={15} /> : <ArrowDownLeft size={15} />}
            </span>
            <div className="min-w-0 flex-1">
              <Link to={`/orders/${tx.order}`} className="truncate text-sm font-medium hover:text-primary">
                {tx.listing_title || `Order #${tx.order}`}
              </Link>
              <p className="text-xs text-muted-foreground">
                {tx.role === "selling" ? "From" : "To"} {tx.other_party_name} · {timeAgo(tx.created_at)}
              </p>
            </div>
            <div className="shrink-0 text-right">
              <p className="text-sm font-semibold">{naira(tx.amount)}</p>
              <Badge tone={STATUS_TONE[tx.status] ?? "muted"}>{tx.status.replace("_", " ")}</Badge>
            </div>
            {tx.tx_hash && (
              <a href={etherscan(tx.tx_hash)} target="_blank" rel="noreferrer" aria-label="View on Etherscan" className="shrink-0 text-muted-foreground hover:text-primary">
                <ExternalLink size={14} />
              </a>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
