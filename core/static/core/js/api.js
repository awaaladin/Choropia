/**
 * Thin client for the Choropia API. Auth is 100% token-based (no cookies/sessions) — the
 * same contract the Kotlin app uses — so tokens live in localStorage and every request
 * attaches an Authorization header manually.
 */
const Choropia = (() => {
  const BASE_URL = window.CHOROPIA_API_BASE_URL;

  function getTokens() {
    return {
      access: localStorage.getItem("choropia_access"),
      refresh: localStorage.getItem("choropia_refresh"),
    };
  }

  function setTokens({ access, refresh }) {
    if (access) localStorage.setItem("choropia_access", access);
    if (refresh) localStorage.setItem("choropia_refresh", refresh);
  }

  function clearTokens() {
    localStorage.removeItem("choropia_access");
    localStorage.removeItem("choropia_refresh");
  }

  function isAuthenticated() {
    return Boolean(getTokens().access);
  }

  async function refreshAccessToken() {
    const { refresh } = getTokens();
    if (!refresh) return false;

    const response = await fetch(`${BASE_URL}/auth/refresh/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh }),
    });
    if (!response.ok) {
      clearTokens();
      return false;
    }
    const data = await response.json();
    setTokens({ access: data.access });
    return true;
  }

  async function request(path, { method = "GET", body, auth = true, retry = true, isFormData = false } = {}) {
    const headers = {};
    if (!isFormData) headers["Content-Type"] = "application/json";
    if (auth) {
      const { access } = getTokens();
      if (access) headers["Authorization"] = `Bearer ${access}`;
    }

    const response = await fetch(`${BASE_URL}${path}`, {
      method,
      headers,
      body: body ? (isFormData ? body : JSON.stringify(body)) : undefined,
    });

    if (response.status === 401 && auth && retry) {
      const refreshed = await refreshAccessToken();
      if (refreshed) return request(path, { method, body, auth, retry: false, isFormData });
    }

    if (response.status === 204) return null;

    const data = await response.json().catch(() => null);
    if (!response.ok) {
      throw new Error(extractErrorMessage(data) || `Request to ${path} failed (${response.status})`);
    }
    return data;
  }

  /**
   * DRF errors show up in several shapes depending on what failed:
   *   {"detail": "..."}                        — permission/auth errors, custom views
   *   {"non_field_errors": ["..."]}             — serializer-level validation
   *   {"email": ["...","..."], "password": [..]} — per-field validation
   * This picks the first human-readable string out of any of those instead of dumping the
   * raw JSON on screen.
   */
  function extractErrorMessage(data) {
    if (!data) return null;
    if (typeof data === "string") return data;
    if (data.detail) return data.detail;
    if (Array.isArray(data)) return data[0];

    for (const key of Object.keys(data)) {
      const value = data[key];
      const text = Array.isArray(value) ? value[0] : value;
      if (typeof text === "string") {
        return key === "non_field_errors" ? text : `${key}: ${text}`;
      }
    }
    return null;
  }

  return {
    login: (identifier, password) =>
      request("/auth/login/", { method: "POST", body: { identifier, password }, auth: false }).then(
        (data) => {
          setTokens({ access: data.access, refresh: data.refresh });
          return data.user;
        }
      ),

    register: (payload) =>
      request("/auth/register/", { method: "POST", body: payload, auth: false }).then((data) => {
        setTokens({ access: data.access, refresh: data.refresh });
        return data.user;
      }),

    logout: async () => {
      const { refresh } = getTokens();
      if (refresh) {
        await request("/auth/logout/", { method: "POST", body: { refresh } }).catch(() => {});
      }
      clearTokens();
    },

    requestPasswordReset: (email) =>
      request("/auth/password-reset/", { method: "POST", body: { email }, auth: false }),
    confirmPasswordReset: (uid, token, password) =>
      request("/auth/password-reset/confirm/", { method: "POST", body: { uid, token, password }, auth: false }),

    me: () => request("/users/me/"),
    updateProfile: (data) => request("/users/me/", { method: "PATCH", body: data }),

    isAuthenticated,

    listListings: (params = {}) => {
      const query = new URLSearchParams(params).toString();
      return request(`/listings/${query ? `?${query}` : ""}`, { auth: false });
    },
    getListing: (id) => request(`/listings/${id}/`, { auth: false }),
    getFeed: () => request("/feed/"),

    listConversations: () => request("/conversations/"),
    getMessages: (conversationId) => request(`/messages/?conversation=${conversationId}`),
    startConversation: (listingId) =>
      request("/conversations/", { method: "POST", body: { listing: listingId } }),

    listCategories: () => request("/categories/", { auth: false }),

    createListing: (formData) =>
      request("/listings/", { method: "POST", body: formData, auth: true, isFormData: true }),

    getMerchant: (id) => request(`/merchants/${id}/`, { auth: false }),
    listMerchants: () => request("/merchants/", { auth: false }),
    listMerchantListings: (merchantId) => request(`/listings/?merchant=${merchantId}`, { auth: false }),

    listOrders: () => request("/orders/"),
    getOrder: (id) => request(`/orders/${id}/`),
    createOrder: (listingId) => request("/orders/", { method: "POST", body: { listing: listingId } }),
    confirmReceipt: (orderId) => request(`/orders/${orderId}/confirm_receipt/`, { method: "POST" }),
    openDispute: (orderId, reason) =>
      request(`/orders/${orderId}/open_dispute/`, { method: "POST", body: { reason } }),
    assignCourier: (orderId) => request(`/orders/${orderId}/assign_courier/`, { method: "POST" }),

    initializePayment: (orderId) =>
      request("/payments/initialize/", { method: "POST", body: { order_id: orderId } }),

    listNotifications: () => request("/notifications/"),
    markNotificationRead: (id) => request(`/notifications/${id}/mark_read/`, { method: "POST" }),
    markAllNotificationsRead: () => request("/notifications/mark-all-read/", { method: "POST" }),

    listComments: (listingId) => request(`/comments/?listing=${listingId}`, { auth: false }),
    createComment: (listingId, body, parent = null) =>
      request("/comments/", { method: "POST", body: { listing: listingId, body, parent } }),

    listMyLikes: () => request("/likes/"),
    likeListing: (listingId) => request("/likes/", { method: "POST", body: { listing: listingId } }),
    unlikeListing: (likeId) => request(`/likes/${likeId}/`, { method: "DELETE" }),

    listMyFollows: () => request("/follows/"),
    follow: (targetType, targetId) =>
      request("/follows/", { method: "POST", body: { target_type: targetType, target_id: targetId } }),
    unfollow: (followId) => request(`/follows/${followId}/`, { method: "DELETE" }),

    applyForMerchant: (payload) => request("/merchant-applications/", { method: "POST", body: payload }),
    myMerchantApplications: () => request("/merchant-applications/"),

    reportListing: (listingId, reason) =>
      request("/reports/", { method: "POST", body: { target_type: "listing", target_id: listingId, reason } }),

    listReviewsFor: (userId) => request(`/reviews/?user=${userId}`, { auth: false }),
    createReview: (orderId, rating, comment) =>
      request("/reviews/", { method: "POST", body: { order: orderId, rating, comment } }),

    wsUrl: (path) => {
      const { access } = getTokens();
      const base =
        window.CHOROPIA_WS_BASE_URL ||
        `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}`;
      return `${base}${path}?token=${access || ""}`;
    },
  };
})();
