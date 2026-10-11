import { useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import { useLocation, useNavigate } from "react-router";
import { toast } from "sonner";
import { api, ApiError, rows } from "./api";
import { useAuth } from "./auth";

/** Sends logged-out users to /login and back again; returns true when the action may proceed. */
export function useEnsureLogin() {
  const { loggedIn } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  return useCallback(() => {
    if (loggedIn) return true;
    navigate(`/login?next=${encodeURIComponent(location.pathname + location.search)}`, { viewTransition: true });
    return false;
  }, [loggedIn, navigate, location]);
}

export const errorMessage = (err: unknown) => (err instanceof ApiError || err instanceof Error ? err.message : "Something went wrong");

export function useListingActions() {
  const ensureLogin = useEnsureLogin();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const buy = useCallback(
    async (listingId: number) => {
      if (!ensureLogin()) return;
      try {
        const order = await api.createOrder(listingId);
        navigate(`/orders/${order.id}`, { viewTransition: true });
      } catch (err) {
        toast.error(errorMessage(err));
      }
    },
    [ensureLogin, navigate],
  );

  const messageSeller = useCallback(
    async (listingId: number) => {
      if (!ensureLogin()) return;
      try {
        const conversation = await api.startConversation(listingId);
        navigate(`/messages/${conversation.id}`, { viewTransition: true });
      } catch (err) {
        toast.error(errorMessage(err));
      }
    },
    [ensureLogin, navigate],
  );

  /** Likes or unlikes; throws on failure so the caller can roll back its optimistic state. */
  const setLiked = useCallback(
    async (listingId: number, liked: boolean) => {
      if (liked) {
        await api.likeListing(listingId);
      } else {
        const mine = rows(await api.listMyLikes());
        const existing = mine.find((like) => like.listing === listingId);
        if (existing) await api.unlikeListing(existing.id);
      }
      queryClient.invalidateQueries({ queryKey: ["listings"] });
      queryClient.invalidateQueries({ queryKey: ["feed"] });
    },
    [queryClient],
  );

  return { ensureLogin, buy, messageSeller, setLiked };
}
