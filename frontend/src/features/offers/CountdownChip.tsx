import { useEffect, useMemo, useState } from "react";
import { Clock } from "lucide-react";
import { cn } from "@/lib/utils";
import { clock } from "./format";

/**
 * Time left on an offer, counted against the server's clock (server_now) so a phone with the wrong time still shows
 * the truth. Under an hour it turns to the caution colour and counts seconds. Reaching zero calls onExpire once.
 */
export function CountdownChip({ expiresAt, serverNow, onExpire }: { expiresAt: string; serverNow: string; onExpire?: () => void }) {
  const skew = useMemo(() => Date.parse(serverNow) - Date.now(), [serverNow]);
  const remaining = () => Math.max(0, Math.floor((Date.parse(expiresAt) - (Date.now() + skew)) / 1000));
  const [left, setLeft] = useState(remaining);

  useEffect(() => {
    setLeft(remaining());
    const t = window.setInterval(() => {
      const next = remaining();
      setLeft(next);
      if (next === 0) {
        window.clearInterval(t);
        onExpire?.();
      }
    }, 1000);
    return () => window.clearInterval(t);
  }, [expiresAt, skew]); // eslint-disable-line react-hooks/exhaustive-deps

  const soon = left < 3600;
  const text = left === 0 ? "Expired" : soon ? clock(left) : left >= 2 * 3600 ? `${Math.floor(left / 3600)}h left` : `${Math.floor(left / 60)}m left`;
  const spoken = left === 0 ? "This offer has expired" : soon ? `Expires in ${Math.ceil(left / 60)} minutes` : `Expires in about ${Math.round(left / 3600)} hours`;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium tabular-nums",
        soon ? "bg-o-caution-bg text-o-caution" : "bg-o-surface text-o-muted",
      )}
      title={spoken}
    >
      <Clock size={12} strokeWidth={1.75} aria-hidden="true" />
      <span aria-hidden="true">{text}</span>
      <span className="sr-only">{spoken}</span>
    </span>
  );
}
