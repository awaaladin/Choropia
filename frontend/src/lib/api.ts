import type {
  AppNotification,
  Category,
  Comment,
  Conversation,
  Follow,
  Like,
  Listing,
  Merchant,
  Message,
  Order,
  Paginated,
  Reel,
  ReelComment,
  ReelLike,
  Review,
  User,
  WalletSummary,
  WalletTransaction,
} from "./types";

/**
 * Client for the Choropia REST API. Auth is token-based (no cookies) — the same contract the
 * Kotlin app uses — so tokens live in localStorage and every request attaches a Bearer header.
 * The SPA and the API share one origin, so the base URL is relative.
 */
const BASE_URL = "/api/v1";

const ACCESS_KEY = "choropia_access";
const REFRESH_KEY = "choropia_refresh";

export const tokens = {
  get access() {
    return localStorage.getItem(ACCESS_KEY);
  },
  get refresh() {
    return localStorage.getItem(REFRESH_KEY);
  },
  set(access?: string, refresh?: string) {
    if (access) localStorage.setItem(ACCESS_KEY, access);
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
};

export const isAuthenticated = () => Boolean(tokens.access);

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

/** DRF errors come as {detail}, {non_field_errors: []}, {field: []} or a bare list. */
function extractErrorMessage(data: unknown): string | null {
  if (!data) return null;
  if (typeof data === "string") return data;
  if (Array.isArray(data)) return typeof data[0] === "string" ? data[0] : null;
  const record = data as Record<string, unknown>;
  if (typeof record.detail === "string") return record.detail;
  for (const key of Object.keys(record)) {
    const value = record[key];
    const text = Array.isArray(value) ? value[0] : value;
    if (typeof text === "string") return key === "non_field_errors" ? text : `${key}: ${text}`;
  }
  return null;
}

async function refreshAccessToken() {
  const refresh = tokens.refresh;
  if (!refresh) return false;
  const response = await fetch(`${BASE_URL}/auth/refresh/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh }),
  });
  if (!response.ok) {
    tokens.clear();
    return false;
  }
  const data = await response.json();
  tokens.set(data.access);
  return true;
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  auth?: boolean;
  retry?: boolean;
  formData?: boolean;
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, auth = true, retry = true, formData = false } = opts;
  const headers: Record<string, string> = {};
  if (!formData) headers["Content-Type"] = "application/json";
  if (auth && tokens.access) headers.Authorization = `Bearer ${tokens.access}`;

  const response = await fetch(`${BASE_URL}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : formData ? (body as FormData) : JSON.stringify(body),
  });

  if (response.status === 401 && auth && retry && (await refreshAccessToken())) {
    return request<T>(path, { ...opts, retry: false });
  }
  if (response.status === 204) return null as T;

  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(
      extractErrorMessage(data) || `Request to ${path} failed (${response.status})`,
      response.status,
    );
  }
  return data as T;
}

const qs = (params: Record<string, string | number | undefined | null>) => {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => v !== undefined && v !== null && v !== "" && search.set(k, String(v)));
  const text = search.toString();
  return text ? `?${text}` : "";
};

/** List endpoints are paginated when the server has pagination on; normalise both shapes. */
export const rows = <T,>(data: Paginated<T> | T[] | null | undefined): T[] =>
  Array.isArray(data) ? data : (data?.results ?? []);

interface AuthResponse {
  access: string;
  refresh: string;
  user: User;
}

export const api = {
  // --- auth ---
  async login(identifier: string, password: string) {
    const data = await request<AuthResponse>("/auth/login/", { method: "POST", body: { identifier, password }, auth: false });
    tokens.set(data.access, data.refresh);
    return data.user;
  },
  async register(payload: Record<string, string>) {
    const data = await request<AuthResponse>("/auth/register/", { method: "POST", body: payload, auth: false });
    tokens.set(data.access, data.refresh);
    return data.user;
  },
  async logout() {
    const refresh = tokens.refresh;
    if (refresh) await request("/auth/logout/", { method: "POST", body: { refresh } }).catch(() => {});
    tokens.clear();
  },
  async logoutEverywhere() {
    await request("/auth/logout-all/", { method: "POST" });
    tokens.clear();
  },
  requestPasswordReset: (email: string) =>
    request("/auth/password-reset/", { method: "POST", body: { email }, auth: false }),
  confirmPasswordReset: (uid: string, token: string, password: string) =>
    request("/auth/password-reset/confirm/", { method: "POST", body: { uid, token, password }, auth: false }),

  // --- profile ---
  me: () => request<User>("/users/me/"),
  updateProfile: (data: unknown) => request<User>("/users/me/", { method: "PATCH", body: data }),

  // --- listings ---
  listCategories: () => request<Category[]>("/categories/", { auth: false }),
  listListings: (params: Record<string, string | undefined> = {}) =>
    request<Paginated<Listing> | Listing[]>(`/listings/${qs(params)}`, { auth: false }),
  listMerchantListings: (merchantId: number) =>
    request<Paginated<Listing> | Listing[]>(`/listings/?merchant=${merchantId}`, { auth: false }),
  getListing: (id: number) => request<Listing>(`/listings/${id}/`),
  getFeed: () => request<Paginated<Listing> | Listing[]>("/feed/"),
  createListing: (formData: FormData) => request<Listing>("/listings/", { method: "POST", body: formData, formData: true }),

  // --- social ---
  listComments: (listingId: number) => request<Paginated<Comment> | Comment[]>(`/comments/?listing=${listingId}`, { auth: false }),
  createComment: (listingId: number, body: string) =>
    request<Comment>("/comments/", { method: "POST", body: { listing: listingId, body, parent: null } }),
  listMyLikes: () => request<Paginated<Like> | Like[]>("/likes/"),
  likeListing: (listingId: number) => request<Like>("/likes/", { method: "POST", body: { listing: listingId } }),
  unlikeListing: (likeId: number) => request(`/likes/${likeId}/`, { method: "DELETE" }),
  listMyFollows: () => request<Paginated<Follow> | Follow[]>("/follows/"),
  follow: (targetType: string, targetId: number) =>
    request<Follow>("/follows/", { method: "POST", body: { target_type: targetType, target_id: targetId } }),
  unfollow: (followId: number) => request(`/follows/${followId}/`, { method: "DELETE" }),
  reportListing: (listingId: number, reason: string) =>
    request("/reports/", { method: "POST", body: { target_type: "listing", target_id: listingId, reason } }),

  // --- merchants ---
  listMerchants: () => request<Paginated<Merchant> | Merchant[]>("/merchants/", { auth: false }),
  getMerchant: (id: number) => request<Merchant>(`/merchants/${id}/`, { auth: false }),
  applyForMerchant: (payload: Record<string, string>) => request("/merchant-applications/", { method: "POST", body: payload }),

  // --- reviews ---
  listReviewsFor: (userId: number) => request<Paginated<Review> | Review[]>(`/reviews/?user=${userId}`, { auth: false }),
  createReview: (orderId: number, rating: number, comment: string) =>
    request("/reviews/", { method: "POST", body: { order: orderId, rating, comment } }),

  // --- chat ---
  listConversations: () => request<Paginated<Conversation> | Conversation[]>("/conversations/"),
  startConversation: (listingId: number) => request<Conversation>("/conversations/", { method: "POST", body: { listing: listingId } }),
  getMessages: (conversationId: number) => request<Paginated<Message> | Message[]>(`/messages/?conversation=${conversationId}`),
  sendMessage: (conversationId: number, body: string) =>
    request<Message>("/messages/", { method: "POST", body: { conversation: conversationId, body } }),

  // --- orders & payments ---
  listOrders: () => request<Paginated<Order> | Order[]>("/orders/"),
  getOrder: (id: number) => request<Order>(`/orders/${id}/`),
  createOrder: (listingId: number) => request<Order>("/orders/", { method: "POST", body: { listing: listingId } }),
  confirmReceipt: (id: number) => request(`/orders/${id}/confirm_receipt/`, { method: "POST" }),
  openDispute: (id: number, reason: string) => request(`/orders/${id}/open_dispute/`, { method: "POST", body: { reason } }),
  assignCourier: (id: number) => request(`/orders/${id}/assign_courier/`, { method: "POST" }),
  initializePayment: (orderId: number) =>
    request<{ authorization_url: string }>("/payments/initialize/", { method: "POST", body: { order_id: orderId } }),

  // --- notifications ---
  listNotifications: () => request<Paginated<AppNotification> | AppNotification[]>("/notifications/"),
  markNotificationRead: (id: number) => request(`/notifications/${id}/mark_read/`, { method: "POST" }),
  markAllNotificationsRead: () => request("/notifications/mark-all-read/", { method: "POST" }),

  // --- reels ---
  listReels: (params: Record<string, string | undefined> = {}) => request<Paginated<Reel> | Reel[]>(`/reels/${qs(params)}`, { auth: false }),
  getReel: (id: number) => request<Reel>(`/reels/${id}/`),
  createReel: (formData: FormData) => request<Reel>("/reels/", { method: "POST", body: formData, formData: true }),
  deleteReel: (id: number) => request(`/reels/${id}/`, { method: "DELETE" }),
  listMyReelLikes: () => request<Paginated<ReelLike> | ReelLike[]>("/reel-likes/"),
  likeReel: (reelId: number) => request<ReelLike>("/reel-likes/", { method: "POST", body: { reel: reelId } }),
  unlikeReel: (likeId: number) => request(`/reel-likes/${likeId}/`, { method: "DELETE" }),
  listReelComments: (reelId: number) => request<Paginated<ReelComment> | ReelComment[]>(`/reel-comments/?reel=${reelId}`, { auth: false }),
  createReelComment: (reelId: number, body: string) => request<ReelComment>("/reel-comments/", { method: "POST", body: { reel: reelId, body } }),

  // --- wallet ---
  getWalletSummary: () => request<WalletSummary>("/wallet/summary/"),
  listWalletTransactions: () => request<Paginated<WalletTransaction> | WalletTransaction[]>("/wallet/transactions/"),
};

/**
 * WebSocket URL for chat/notifications. Vercel can't hold WebSockets, so the realtime host
 * (docker-compose) is configured with VITE_WS_BASE_URL at build time; on localhost the dev
 * proxy / Django ASGI server handles them same-origin. Returns null where none is available,
 * and callers fall back to polling.
 */
export function wsUrl(path: string): string | null {
  const configured = import.meta.env.VITE_WS_BASE_URL as string | undefined;
  let base = configured;
  if (!base) {
    const { hostname, protocol, host } = window.location;
    if (hostname !== "localhost" && hostname !== "127.0.0.1") return null;
    base = `${protocol === "https:" ? "wss:" : "ws:"}//${host}`;
  }
  return `${base}${path}?token=${tokens.access ?? ""}`;
}
