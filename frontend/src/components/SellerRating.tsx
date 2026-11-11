import { useQuery } from "@tanstack/react-query";
import { Star } from "lucide-react";
import { VerifiedBadge } from "@/components/VerifiedBadge";
import { api } from "@/lib/api";

/** "4.7 (12 reviews)" with a Verified tick. Shows nothing for a seller who has not posted enough to be rated. */
export function SellerRating({ userId, className }: { userId: number | null | undefined; className?: string }) {
  const summary = useQuery({
    queryKey: ["review-summary", userId],
    queryFn: () => api.reviewSummary(userId!),
    enabled: !!userId,
    staleTime: 5 * 60_000,
  });
  const data = summary.data;
  if (!data) return null;
  return (
    <span className={`inline-flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-muted-foreground ${className ?? ""}`}>
      {data.eligible &&
        (data.count > 0 ? (
          <span className="inline-flex items-center gap-1">
            <Star size={12} className="fill-current text-primary" />
            <strong className="text-foreground">{data.average?.toFixed(1)}</strong> ({data.count} review{data.count === 1 ? "" : "s"})
          </span>
        ) : (
          <span>No reviews yet</span>
        ))}
      {data.verified && (
        <span className="inline-flex items-center gap-1 text-primary">
          <VerifiedBadge size={15} /> Verified seller
        </span>
      )}
    </span>
  );
}
