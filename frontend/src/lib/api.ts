import type {
  AppNotification,
  Area,
  DriverJobs,
  DriverMe,
  ListingDeliveryInfo,
  OrderDelivery,
  PublicDriver,
  RoutePrice,
  Category,
  ChatOffer,
  FeePreview,
  HandoverCode,
  PinStatus,
  Comment,
  Conversation,
  Follow,
  GuestLikeState,
  GuestLikeToken,
  Like,
  Listing,
  Merchant,
  Message,
  OfferDeliveryMethod,
  Order,
  Paginated,
  PublicProfile,
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

// Sign-in state. The short-lived access token lives only in memory, and the long-lived refresh token is an HttpOnly cookie that
// page scripts cannot read, so a script injected into the page cannot steal a login. "choropia_session" is only a hint that
// this browser has signed in before, so a returning visitor knows to ask for a fresh access token.
const LEGACY_ACCESS_KEY = "choropia_access";
const LEGACY_REFRESH_KEY = "choropia_refresh";
const SESSION_HINT = "choropia_session";
const GUEST_LIKE_TOKEN_KEY = "choropia_guest_like_token";

let accessToken: string | null = null;
let guestLikeTokenRequest: Promise<string> | null = null;

export const tokens = {
  get access() {
    return accessToken;
  },
  get hasSession() {
    return Boolean(accessToken) || localStorage.getItem(SESSION_HINT) === "1" || Boolean(localStorage.getItem(LEGACY_REFRESH_KEY));
  },
  set(access?: string, _refresh?: string) {
    if (access) {
      accessToken = access;
      localStorage.setItem(SESSION_HINT, "1");
    }
  },
  clear() {
    accessToken = null;
    localStorage.removeItem(SESSION_HINT);
    localStorage.removeItem(LEGACY_ACCESS_KEY);
    localStorage.removeItem(LEGACY_REFRESH_KEY);
  },
};

export const isAuthenticated = () => tokens.hasSession;

export class ApiError extends Error {
  status: number;
  /** The raw error body, e.g. {code: "pin_locked", retry_after: 900} for the offer and PIN endpoints. */
  data: Record<string, unknown>;
  constructor(message: string, status: number, data: unknown = null) {
    super(message);
    this.status = status;
    this.data = data && typeof data === "object" && !Array.isArray(data) ? (data as Record<string, unknown>) : {};
  }
  get code(): string | undefined {
    return typeof this.data.code === "string" ? this.data.code : undefined;
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

let refreshing: Promise<boolean> | null = null;

/** Asks for a new access token using the cookie (one request at a time, however many calls are waiting). */
function refreshAccessToken(): Promise<boolean> {
  if (!refreshing) {
    refreshing = (async () => {
      // A browser that signed in before this change still holds its refresh token in storage: hand it over once so it
      // moves into the protected cookie, then delete it.
      const legacy = localStorage.getItem(LEGACY_REFRESH_KEY);
      const response = await fetch(`${BASE_URL}/auth/refresh/`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Client": "web" },
        body: JSON.stringify(legacy ? { refresh: legacy } : {}),
      }).catch(() => null);
      if (!response) return false; // offline: keep the session, try again later
      if (!response.ok) {
        tokens.clear();
        return false;
      }
      const data = await response.json();
      localStorage.removeItem(LEGACY_ACCESS_KEY);
      localStorage.removeItem(LEGACY_REFRESH_KEY);
      tokens.set(data.access);
      return true;
    })().finally(() => {
      refreshing = null;
    });
  }
  return refreshing;
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
  const headers: Record<string, string> = { "X-Client": "web" };
  if (!formData) headers["Content-Type"] = "application/json";
  const includesListingEngagement = path.startsWith("/listings/") || path === "/feed/" || path === "/likes/guest/";
  const guestLikeToken = includesListingEngagement ? localStorage.getItem(GUEST_LIKE_TOKEN_KEY) : null;
  if (guestLikeToken) headers["X-Guest-Like-Token"] = guestLikeToken;
  if (auth && !tokens.access && tokens.hasSession) await refreshAccessToken(); // a reload: get a fresh access token first
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
      data,
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

async function getGuestLikeToken(): Promise<string> {
  const existing = localStorage.getItem(GUEST_LIKE_TOKEN_KEY);
  if (existing) return existing;
  if (!guestLikeTokenRequest) {
    guestLikeTokenRequest = request<GuestLikeToken>("/likes/guest-token/", {
      method: "POST",
      auth: false,
    })
      .then(({ token }) => {
        localStorage.setItem(GUEST_LIKE_TOKEN_KEY, token);
        return token;
      })
      .finally(() => {
        guestLikeTokenRequest = null;
      });
  }
  return guestLikeTokenRequest;
}

/** List endpoints are paginated when the server has pagination on; normalise both shapes. */
export const rows = <T,>(data: Paginated<T> | T[] | null | undefined): T[] =>
  Array.isArray(data) ? data : (data?.results ?? []);

interface AuthResponse {
  access: string;
  refresh: string;
  user: User;
}

/** Returned by /auth/login/ and /auth/google/ instead of tokens when the account has 2-step
 * verification on — the client must then post {challenge, code} to /auth/2fa/verify/. */
interface TwoFactorChallenge {
  two_factor_required: true;
  challenge: string;
}

export const api = {
  // --- auth ---
  async login(identifier: string, password: string): Promise<AuthResponse | TwoFactorChallenge> {
    const data = await request<AuthResponse | TwoFactorChallenge>("/auth/login/", {
      method: "POST",
      body: { identifier, password },
      auth: false,
    });
    if ("access" in data) tokens.set(data.access, data.refresh);
    return data;
  },
  googleConfig: () => request<{ client_id: string }>("/auth/google/config/", { auth: false }),
  async googleLogin(idToken: string): Promise<AuthResponse | TwoFactorChallenge> {
    const data = await request<AuthResponse | TwoFactorChallenge>("/auth/google/", { method: "POST", body: { id_token: idToken }, auth: false });
    if ("access" in data) tokens.set(data.access, data.refresh);
    return data;
  },
  async verifyTwoFactor(challenge: string, code: string) {
    const data = await request<AuthResponse>("/auth/2fa/verify/", { method: "POST", body: { challenge, code }, auth: false });
    tokens.set(data.access, data.refresh);
    return data.user;
  },
  async register(payload: Record<string, string>) {
    const data = await request<AuthResponse>("/auth/register/", { method: "POST", body: payload, auth: false });
    tokens.set(data.access, data.refresh);
    return data.user;
  },
  async logout() {
    // The refresh token travels in the cookie; the server blacklists it and clears the cookie.
    if (tokens.hasSession) await request("/auth/logout/", { method: "POST", body: {} }).catch(() => {});
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

  /** Emails a fresh 6-digit code to the signed-in person, to verify their address. */
  requestEmailCode: () => request<{ detail: string }>("/auth/email-otp/request/", { method: "POST" }),
  confirmEmailCode: (code: string) => request<{ email_verified: boolean }>("/auth/email-otp/confirm/", { method: "POST", body: { code } }),

  // --- delivery by independent drivers ---
  dispatch: {
    areas: () => request<Area[]>("/dispatch/areas/", { auth: false }),
    addArea: (name: string) => request<Area>("/dispatch/areas/", { method: "POST", body: { name } }),
    driverMe: () => request<DriverMe | null>("/dispatch/driver/me/"),
    apply: (body: Record<string, unknown>) => request<DriverMe>("/dispatch/driver/me/", { method: "PUT", body }),
    setAvailable: (available: boolean) => request<DriverMe>("/dispatch/driver/me/", { method: "PUT", body: { available } }),
    uploadDocument: (kind: string, file: File) => {
      const form = new FormData();
      form.append("kind", kind);
      form.append("file", file);
      return request<DriverMe>("/dispatch/driver/documents/", { method: "POST", body: form, formData: true });
    },
    routes: () => request<RoutePrice[]>("/dispatch/driver/routes/"),
    addRoute: (body: { from_area: number; to_area: number; price: string }) => request("/dispatch/driver/routes/", { method: "POST", body }),
    deleteRoute: (id: number) => request(`/dispatch/driver/routes/${id}/`, { method: "DELETE" }),
    jobs: () => request<DriverJobs>("/dispatch/driver/jobs/"),
    accept: (id: number) => request<OrderDelivery>(`/dispatch/driver/jobs/${id}/accept/`, { method: "POST" }),
    decline: (id: number) => request(`/dispatch/driver/jobs/${id}/decline/`, { method: "POST" }),
    pickup: (id: number) => request<OrderDelivery>(`/dispatch/driver/jobs/${id}/pickup/`, { method: "POST" }),
    deliver: (id: number, code: string, photo: File) => {
      const form = new FormData();
      form.append("code", code);
      form.append("photo", photo);
      return request<OrderDelivery>(`/dispatch/driver/jobs/${id}/deliver/`, { method: "POST", body: form, formData: true });
    },
    browseDrivers: (fromArea: number) => request<PublicDriver[]>(`/dispatch/drivers/?from=${fromArea}`),
    listingDelivery: (listingId: number, to?: number) =>
      request<ListingDeliveryInfo>(`/dispatch/listings/${listingId}/delivery/${to ? `?to=${to}` : ""}`, { auth: false }),
    saveListingDelivery: (listingId: number, body: { enabled: boolean; payer: string; pickup_area: number; drivers: number[] }) =>
      request<ListingDeliveryInfo>(`/dispatch/listings/${listingId}/delivery/`, { method: "PUT", body }),
    orderDelivery: (orderId: number) => request<OrderDelivery | null>(`/dispatch/orders/${orderId}/delivery/`),
    chooseDelivery: (orderId: number, body: { dropoff_area: number; driver: number; dropoff_note: string }) =>
      request<OrderDelivery>(`/dispatch/orders/${orderId}/delivery/`, { method: "POST", body }),
    clearDelivery: (orderId: number) => request(`/dispatch/orders/${orderId}/delivery/`, { method: "DELETE" }),
    reassign: (orderId: number) => request<OrderDelivery>(`/dispatch/orders/${orderId}/delivery/reassign/`, { method: "POST" }),
  },

  // --- payout account (where sellers and drivers are paid) ---
  banks: () => request<{ code: string; name: string }[]>("/payouts/banks/"),
  payoutAccount: () => request<{ configured: boolean; bank_name: string; account_last4: string; account_name: string }>("/payouts/account/"),
  savePayoutAccount: (bank_code: string, account_number: string) =>
    request<{ configured: boolean; bank_name: string; account_last4: string; account_name: string }>("/payouts/account/", { method: "PUT", body: { bank_code, account_number } }),
  deletePayoutAccount: () => request("/payouts/account/", { method: "DELETE" }),

  // --- profile ---
  me: () => request<User>("/users/me/"),
  updateProfile: (data: unknown) => request<User>("/users/me/", { method: "PATCH", body: data }),
  publicProfile: (id: number) => request<PublicProfile>(`/users/${id}/profile/`, { auth: false }),
  publicProfileListings: (id: number, page = 1) =>
    request<Paginated<Listing> | Listing[]>(`/users/${id}/listings/${page > 1 ? `?page=${page}` : ""}`, { auth: false }),

  // --- listings ---
  listCategories: () => request<Category[]>("/categories/", { auth: false }),
  listListings: (params: Record<string, string | undefined> = {}) =>
    request<Paginated<Listing> | Listing[]>(`/listings/${qs(params)}`, { auth: false }),
  listMyListings: () => request<Paginated<Listing> | Listing[]>("/listings/?mine=true"),
  listMerchantListings: (merchantId: number) =>
    request<Paginated<Listing> | Listing[]>(`/listings/?merchant=${merchantId}`, { auth: false }),
  getListing: (id: number | string) => request<Listing>(`/listings/${encodeURIComponent(String(id))}/`),
  deleteListing: (id: number) => request(`/listings/${id}/`, { method: "DELETE" }),
  removeListingPhoto: (id: number, photoId: number) => request<Listing>(`/listings/${id}/photos/${photoId}/`, { method: "DELETE" }),
  addListingPhotos: (id: number, files: File[]) => {
    const form = new FormData();
    files.forEach((f) => form.append("uploaded_photos", f));
    return request<Listing>(`/listings/${id}/`, { method: "PATCH", body: form, formData: true });
  },
  uploadAvatar: (file: File) => {
    const form = new FormData();
    form.append("image", file);
    return request<{ avatar: string }>("/users/me/avatar/", { method: "POST", body: form, formData: true });
  },
  removeAvatar: () => request("/users/me/avatar/", { method: "DELETE" }),
  myListings: () => request<Paginated<Listing> | Listing[]>("/listings/?mine=true"),
  markSold: (id: number, durationDays?: number) =>
    request<Listing>(`/listings/${id}/mark_sold/`, {
      method: "POST",
      body: durationDays === undefined ? {} : { duration_days: durationDays },
    }),
  extendMarketVisibility: (id: number, durationDays: number) =>
    request<Listing>(`/listings/${id}/extend_market_visibility/`, { method: "POST", body: { duration_days: durationDays } }),
  relist: (id: number) => request<Listing>(`/listings/${id}/relist/`, { method: "POST" }),
  getFeed: () => request<Paginated<Listing> | Listing[]>("/feed/"),
  updateListing: (id: number, data: unknown) => request<Listing>(`/listings/${id}/`, { method: "PATCH", body: data }),
  createListing: (formData: FormData) => request<Listing>("/listings/", { method: "POST", body: formData, formData: true }),

  // --- social ---
  listComments: (listingId: number) => request<Paginated<Comment> | Comment[]>(`/comments/?listing=${listingId}`, { auth: false }),
  createComment: (listingId: number, body: string) =>
    request<Comment>("/comments/", { method: "POST", body: { listing: listingId, body, parent: null } }),
  listMyLikes: () => request<Paginated<Like> | Like[]>("/likes/"),
  async likeListing(listingId: number): Promise<Like | GuestLikeState> {
    if (tokens.hasSession) {
      return request<Like>("/likes/", { method: "POST", body: { listing: listingId } });
    }
    await getGuestLikeToken();
    return request<GuestLikeState>("/likes/guest/", {
      method: "POST",
      body: { listing: listingId },
      auth: false,
    });
  },
  unlikeListing: (likeId: number) => request(`/likes/${likeId}/`, { method: "DELETE" }),
  async unlikeGuestListing(listingId: number): Promise<GuestLikeState> {
    await getGuestLikeToken();
    return request<GuestLikeState>("/likes/guest/", {
      method: "DELETE",
      body: { listing: listingId },
      auth: false,
    });
  },
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
  getConversation: (ref: number | string) => request<Conversation>(`/conversations/${encodeURIComponent(String(ref))}/`),
  startConversation: (listingId: number) => request<Conversation>("/conversations/", { method: "POST", body: { listing: listingId } }),
  openConversation: (otherUserId: number, listingId?: number) =>
    request<Conversation>("/conversations/open/", { method: "POST", body: { other_user_id: otherUserId, listing_id: listingId } }),
  getMessages: (conversationId: number) => request<Paginated<Message> | Message[]>(`/messages/?conversation=${conversationId}`),
  sendMessage: (conversationId: number, body: string) =>
    request<Message>("/messages/", { method: "POST", body: { conversation: conversationId, body } }),
  deleteMessage: (messageId: number) => request<void>(`/messages/${messageId}/`, { method: "DELETE" }),
  sendAttachment: (conversationId: number, file: File, durationSeconds?: number, body = "") => {
    const form = new FormData();
    form.append("conversation", String(conversationId));
    form.append("body", body);
    if (durationSeconds !== undefined) form.append("duration_seconds", String(durationSeconds));
    form.append("attachment", file);
    return request<Message>("/messages/", { method: "POST", body: form, formData: true });
  },
  offers: (conversationId: number) => request<ChatOffer[]>(`/conversations/${conversationId}/offers/`),
  createOffer: (
    conversationId: number,
    body: {
      listing_id: number;
      amount_kobo: number;
      allowed_delivery_methods: OfferDeliveryMethod[];
      note?: string;
      pin: string;
    },
  ) => request<ChatOffer>(`/conversations/${conversationId}/offers/`, { method: "POST", body }),
  checkoutOffer: (offerId: string, deliveryMethod: OfferDeliveryMethod, source: "web" | "app" = "web") =>
    request<{ order_id: number; authorization_url: string | null }>(`/offers/${offerId}/checkout/`, {
      method: "POST",
      body: { delivery_method: deliveryMethod, source },
    }),
  getOffer: (offerId: string) => request<ChatOffer>(`/offers/${offerId}/`),
  cancelOffer: (offerId: string) => request<ChatOffer>(`/offers/${offerId}/cancel/`, { method: "POST" }),
  declineOffer: (offerId: string) => request<ChatOffer>(`/offers/${offerId}/decline/`, { method: "POST" }),
  verifyOfferPayment: (offerId: string) => request<ChatOffer>(`/offers/${offerId}/verify-payment/`, { method: "POST" }),
  feePreview: (amountKobo: number, verified: boolean) =>
    request<FeePreview>(`/fees/preview/${qs({ amount_kobo: amountKobo, verified: verified ? "true" : "false" })}`, { auth: false }),
  pinStatus: () => request<PinStatus>("/account/pin/"),
  setPin: (body: { pin: string; old_pin?: string; password?: string; email_code?: string }) =>
    request<PinStatus>("/account/pin/", { method: "POST", body }),
  pinResetCode: () => request<{ detail: string }>("/account/pin/reset-code/", { method: "POST" }),
  handoverCode: (orderId: number) => request<HandoverCode>(`/orders/${orderId}/handover-code/`),
  confirmHandover: (orderId: number, code: string) =>
    request<unknown>(`/orders/${orderId}/confirm-handover/`, { method: "POST", body: { code } }),

  // --- orders & payments ---
  listOrders: () => request<Paginated<Order> | Order[]>("/orders/"),
  getOrder: (id: number | string) => request<Order>(`/orders/${encodeURIComponent(String(id))}/`),
  createOrder: (listingId: number) => request<Order>("/orders/", { method: "POST", body: { listing: listingId } }),
  confirmReceipt: (id: number) => request(`/orders/${id}/confirm_receipt/`, { method: "POST" }),
  openDispute: (id: number, reason: string) => request(`/orders/${id}/open_dispute/`, { method: "POST", body: { reason } }),
  assignCourier: (id: number) => request(`/orders/${id}/assign_courier/`, { method: "POST" }),
  markInTransit: (id: number) => request(`/orders/${id}/mark_in_transit/`, { method: "POST" }),
  markDelivered: (id: number) => request(`/orders/${id}/mark_delivered/`, { method: "POST" }),
  cancelOrder: (id: number) => request(`/orders/${id}/cancel/`, { method: "POST" }),
  initializePayment: (orderId: number) =>
    request<{ authorization_url: string }>("/payments/initialize/", { method: "POST", body: { order_id: orderId } }),
  verifyPayment: (orderId: number) =>
    request<{ reference: string; status: string; order_status: string }>("/payments/verify/", {
      method: "POST",
      body: { order_id: orderId },
    }),

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
