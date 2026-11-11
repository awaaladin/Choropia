import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useContext, useEffect, type ReactNode } from "react";
import { useLocation, useNavigate, useParams } from "react-router";
import { Skeleton, ErrorState } from "@/components/ui";
import { api } from "./api";
import { chatPath, listingPath, orderPath } from "./links";

type Kind = "listing" | "chat" | "order";

const RouteIdContext = createContext<number | null>(null);

/** The internal number of the listing, chat or order this page is showing (whatever form the address used). */
export function useRouteId(): number {
  const resolved = useContext(RouteIdContext);
  const { id } = useParams();
  return resolved ?? Number(id);
}

const fetchers = {
  listing: (ref: string) => api.getListing(ref),
  chat: (ref: string) => api.getConversation(ref),
  order: (ref: string) => api.getOrder(ref),
} as const;

/** The cache key each page uses for its own object, so the page reuses this lookup instead of fetching again. */
const pageKey = { listing: "listing", chat: "conversation", order: "order" } as const;

/**
 * Wraps a detail page. Looks the object up once from the address (old number, public code, or listing title-slug-code),
 * gives the page its internal number through useRouteId(), and replaces an old numeric address with the coded one.
 * Permissions are the server's: someone who isn't part of a chat or order just gets "not found".
 */
export function RefRoute({ kind, children }: { kind: Kind; children: ReactNode }) {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const object = useQuery({
    queryKey: ["ref", kind, id],
    queryFn: async () => {
      const data = await fetchers[kind](id);
      queryClient.setQueryData([pageKey[kind], data.id], data);
      return data;
    },
    retry: false,
    staleTime: 5 * 60_000,
  });

  useEffect(() => {
    if (!object.data) return;
    const path = kind === "listing" ? listingPath(object.data) : kind === "chat" ? chatPath(object.data) : orderPath(object.data);
    // Old numeric address (or an outdated title slug): show the coded one without adding a history entry.
    if (location.pathname.replace(/\/$/, "") !== path) {
      navigate(path + location.search + location.hash, { replace: true });
    }
  }, [object.data, kind, location.pathname, location.search, location.hash, navigate]);

  if (object.isPending) {
    return (
      <div className="space-y-3 p-4" aria-busy="true" aria-label="Loading">
        <Skeleton className="h-8 w-1/2" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }
  if (object.isError || !object.data) {
    return <ErrorState message={kind === "listing" ? "This listing isn't available." : "We couldn't find that."} />;
  }
  return <RouteIdContext.Provider value={object.data.id}>{children}</RouteIdContext.Provider>;
}
