import { Heart, MessageCircle } from "lucide-react";
import { useEffect, useState, type CSSProperties } from "react";
import { toast } from "sonner";
import { errorMessage, useListingActions } from "@/lib/actions";
import type { Listing } from "@/lib/types";
import type { Density, View } from "@/lib/prefs";
import { cn, naira } from "@/lib/utils";
import { Link } from "./AppLink";
import { Button } from "./Button";
import { Avatar, Badge } from "./ui";

export function ListingCard({ item, view, density, style }: { item: Listing; view: View; density: Density; style?: CSSProperties }) {
  const { ensureLogin, buy, messageSeller, setLiked } = useListingActions();
  const compact = density === "compact";
  const [liked, setLikedState] = useState(item.is_liked);
  const [likes, setLikes] = useState(item.likes_count);
  const [popKey, setPopKey] = useState(0);

  useEffect(() => {
    setLikedState(item.is_liked);
    setLikes(item.likes_count);
  }, [item.is_liked, item.likes_count]);

  const toggleLike = async () => {
    if (!ensureLogin()) return;
    const next = !liked;
    setLikedState(next);
    setLikes((n) => n + (next ? 1 : -1));
    setPopKey((k) => k + 1);
    try {
      await setLiked(item.id, next);
    } catch (err) {
      setLikedState(!next);
      setLikes((n) => n + (next ? -1 : 1));
      toast.error(errorMessage(err));
    }
  };

  const href = `/listings/${item.id}`;
  const editorial = view === "editorial";

  return (
    <article
      style={style}
      className={cn(
        "editorial-enter panel group overflow-hidden transition-[transform,box-shadow] duration-300 hover:-translate-y-0.5 hover:shadow-lg",
        editorial ? "flex flex-col sm:flex-row" : "flex flex-col",
      )}
    >
      <Link to={href} className={cn("block overflow-hidden bg-accent", editorial ? cn(compact ? "sm:w-36" : "sm:w-52", "sm:shrink-0") : "w-full")} aria-label={item.title}>
        {item.cover_photo ? (
          <img
            src={item.cover_photo}
            alt=""
            loading="lazy"
            className={cn("h-full w-full object-cover transition-transform duration-700 ease-out group-hover:scale-[1.03]", editorial ? "aspect-[4/3] sm:aspect-auto" : "aspect-[4/3]")}
          />
        ) : (
          <div className="grid aspect-[4/3] h-full w-full place-items-center text-xs text-muted-foreground sm:aspect-auto">No photo</div>
        )}
      </Link>

      <div className={cn("flex min-w-0 flex-1 flex-col", compact ? "p-3" : "p-4")}>
        <div className="flex items-center gap-2">
          <Link to={href} className="min-w-0 truncate text-sm font-semibold hover:text-primary sm:text-base">
            {item.title}
          </Link>
          <Badge tone="success">Escrow</Badge>
        </div>
        <p className={cn("mt-1 text-xs leading-relaxed text-muted-foreground", compact ? "line-clamp-1" : "line-clamp-2")}>
          {item.description || `${item.condition} · ${item.location || "Uyo"}`}
        </p>

        <div className="mt-auto flex flex-wrap items-center gap-2 pt-3 text-xs text-muted-foreground">
          <Avatar src={item.seller_avatar} name={item.seller_name} size={24} />
          <Link to={item.merchant ? `/merchants/${item.merchant}` : href} className="hover:text-foreground">
            {item.seller_name}
          </Link>
          <span>· {item.location || "Uyo"}</span>
          <span className="capitalize">· {item.condition}</span>
        </div>

        <div className="mt-3 flex items-center gap-2">
          <Button
            variant="icon"
            aria-label={liked ? "Unlike listing" : "Like listing"}
            aria-pressed={liked}
            title={liked ? "Unlike" : "Like"}
            onClick={toggleLike}
            className={cn("h-9 gap-1.5 px-2.5", liked && "text-destructive")}
          >
            <Heart key={popKey} size={15} fill={liked ? "currentColor" : "none"} className={popKey ? "heart-pop" : undefined} />
            <span className="text-xs tabular-nums">{likes}</span>
          </Button>
          <Button variant="secondary" className="ml-auto" onClick={() => messageSeller(item.id)}>
            <MessageCircle size={14} /> <span className="hidden sm:inline">Message</span>
          </Button>
          <Button onClick={() => buy(item.id)}>Buy {naira(item.price)}</Button>
        </div>
      </div>
    </article>
  );
}
