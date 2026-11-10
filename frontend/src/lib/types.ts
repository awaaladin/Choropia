export interface Paginated<T> {
  count?: number;
  next?: string | null;
  results: T[];
}

export interface Profile {
  bio: string;
  avatar: string | null;
  location: string;
  theme_preference: "light" | "dark";
  email_verified?: boolean;
  /** Set by Choropia staff; verified sellers pay a lower fee (see the fee preview). */
  seller_verified?: boolean;
}

export interface User {
  id: number;
  email: string;
  phone_number: string | null;
  first_name: string;
  last_name: string;
  profile?: Profile;
}

export interface PublicProfile {
  id: number;
  display_name: string;
  username: string;
  avatar_url: string | null;
  verified: boolean;
  bio: string;
  joined_at: string;
  completed_sales: number;
}

export function displayName(user?: Pick<User, "first_name" | "last_name" | "email"> | null) {
  if (!user) return "";
  return `${user.first_name} ${user.last_name}`.trim() || user.email;
}

export interface Category {
  id: number;
  name: string;
  slug: string;
}

export interface ListingPhoto {
  id: number;
  image: string;
}

export interface Listing {
  id: number;
  title: string;
  description?: string;
  price: string;
  /** How many are left. Each paid order takes one; at zero the listing is sold. */
  quantity?: number;
  /** "uniuyo" when the listing is on the UniUyo campus market. */
  campus?: string;
  status?: "active" | "sold" | "removed";
  sold_at?: string | null;
  market_visible_until?: string | null;
  /** Set when the seller chose to show a price change: the old price, to be shown crossed out. */
  previous_price?: string | null;
  condition: string;
  category: number;
  location?: string;
  merchant: number | null;
  merchant_id?: number | null;
  photos?: ListingPhoto[];
  cover_photo?: string | null;
  seller_id: number;
  seller_name: string;
  seller_avatar: string | null;
  likes_count: number;
  comments_count: number;
  is_liked: boolean;
  created_at: string;
}

export interface Comment {
  id: number;
  author_id: number;
  author: {
    id: number;
    display_name: string;
    username: string;
    avatar_url: string | null;
    verified: boolean;
  };
  body: string;
  created_at: string;
}

export interface Like {
  id: number;
  listing: number;
}

export interface GuestLikeToken {
  token: string;
}

export interface GuestLikeState {
  listing: number;
  liked: boolean;
}

export interface Merchant {
  id: number;
  owner_id: number;
  business_name: string;
  description?: string;
  location?: string;
  logo: string | null;
  followers_count: number;
}

export interface Follow {
  id: number;
  target_type_display: string;
  object_id: number;
}

export interface OrderHistory {
  id: number;
  to_status: string;
  note: string;
  created_at: string;
}

export interface Order {
  id: number;
  listing: number;
  buyer: number;
  seller: number;
  status: string;
  price: string;
  listing_title?: string;
  listing_cover_photo?: string | null;
  buyer_name?: string;
  seller_name?: string;
  dispute_reason?: string;
  history: OrderHistory[];
}

export interface Message {
  id: number;
  conversation: number;
  sender_id: number;
  body: string;
  attachment: string | null;
  attachment_type: "image" | "audio" | "file" | "";
  is_deleted?: boolean;
  duration_seconds: number | null;
  type?: "text" | "offer" | "listing_ref";
  event?: string;
  offer?: ChatOffer | null;
  listing?: number | null;
  listing_snapshot?: {
    title?: string;
    thumbnail?: string | null;
    price_kobo?: number;
    status?: string;
  };
  listing_status?: "active" | "sold" | "removed";
  created_at: string;
}

export type OfferDeliveryMethod = "rider" | "seller_delivers" | "meetup";
export type ChatOfferStatus =
  | "pending"
  | "payment_processing"
  | "paid"
  | "declined"
  | "cancelled"
  | "expired"
  | "superseded";

export interface ChatOffer {
  id: string;
  reference: string;
  conversation: number;
  listing: { id: number; title: string; photo: string | null };
  seller: number;
  buyer: number;
  viewer_role: "seller" | "buyer" | null;
  amount_kobo: number;
  listing_price_kobo: number;
  fee_kobo?: number;
  seller_net_kobo?: number;
  seller_verified_snapshot?: boolean;
  allowed_delivery_methods: OfferDeliveryMethod[];
  note: string;
  status: ChatOfferStatus;
  expires_at: string;
  delivery_method: OfferDeliveryMethod | "";
  delivery_fee_kobo: number;
  total_kobo: number;
  order_id: number | null;
  created_at: string;
  updated_at: string;
  paid_at: string | null;
  closed_at: string | null;
  server_now: string;
  /** Where the money is once an order exists (see offers/serializers.py order_stage). */
  order_stage?: OfferOrderStage | null;
  /** The last checkout failed at Paystack; the offer is open again. */
  last_payment_failed?: boolean;
}

export type OfferOrderStage =
  | "awaiting_payment"
  | "escrow_held"
  | "handed_over"
  | "released"
  | "disputed"
  | "refund_pending"
  | "refunded"
  | "cancelled";

export interface FeePreview {
  amount_kobo: number;
  fee_kobo: number;
  seller_net_kobo: number;
  verified: boolean;
  min_fee_kobo: number;
}

export interface PinStatus {
  has_pin: boolean;
  length: number;
  locked: boolean;
  locked_until: string | null;
  retry_after: number | null;
}

export interface HandoverCode {
  code: string | null;
  entered_by: "seller" | "rider";
  used: boolean;
}

export interface Conversation {
  id: number;
  listing: number | null;
  listing_title?: string;
  buyer?: number;
  seller?: number;
  orders?: number[];
  other_party_name?: string | null;
  other_party_id?: number | null;
  other_party_avatar?: string | null;
  last_message: Message | null;
}

export interface AppNotification {
  id: number;
  notification_type: "follow" | "message" | "order_status" | "dispute";
  verb: string;
  target_type: string | null;
  target_object_id: number | null;
  is_read: boolean;
  created_at: string;
}

export interface Review {
  id: number;
  order: number;
  reviewer: number;
  rating: number;
  comment: string;
}

export interface Reel {
  id: number;
  owner: number;
  merchant: number | null;
  listing: number | null;
  listing_title: string | null;
  listing_price: string | null;
  video: string;
  caption: string;
  views_count: number;
  creator_id: number;
  creator_name: string;
  creator_avatar: string | null;
  likes_count: number;
  comments_count: number;
  is_liked: boolean;
  created_at: string;
}

export interface ReelComment {
  id: number;
  reel: number;
  author_id: number;
  author_name: string;
  body: string;
  created_at: string;
}

export interface ReelLike {
  id: number;
  reel: number;
}

export interface WalletSummary {
  currency: string;
  selling: { released_total: string; held_total: string };
  buying: { held_total: string; spent_total: string };
}

export interface WalletTransaction {
  id: number;
  order: number;
  listing_title: string | null;
  role: "buying" | "selling";
  other_party_name: string;
  amount: string;
  crypto_amount: string | null;
  crypto_currency: string;
  status: string;
  tx_hash: string;
  paid_at: string | null;
  released_at: string | null;
  refunded_at: string | null;
  created_at: string;
}

// --- delivery by independent drivers (dispatch) -------------------------------------------------------------

export interface Area {
  id: number;
  name: string;
}

export interface DriverDocumentStatus {
  kind: string;
  label: string;
  uploaded: boolean;
}

export interface DriverMe {
  id: number;
  status: "pending" | "approved" | "rejected" | "suspended";
  status_label: string;
  review_note: string;
  full_name: string;
  phone: string;
  whatsapp: string;
  vehicle_type: string;
  plate_number: string;
  guarantor_name: string;
  guarantor_phone: string;
  available: boolean;
  documents: DriverDocumentStatus[];
  documents_complete: boolean;
}

export interface RoutePrice {
  id: number;
  from_area: Area;
  to_area: Area;
  price: string;
  is_active?: boolean;
  you_pay?: string;
}

export interface PublicDriver {
  id: number;
  name: string;
  vehicle_type: string;
  routes: RoutePrice[];
}

export interface ListingDeliveryInfo {
  enabled: boolean;
  payer?: "buyer" | "seller" | "split";
  pickup_area?: Area;
  drivers?: PublicDriver[];
}

export interface OrderDelivery {
  id: number;
  order: number;
  status: "awaiting_payment" | "offered" | "accepted" | "picked_up" | "delivered" | "cancelled";
  status_label: string;
  pickup_area: Area;
  dropoff_area: Area;
  payer: "buyer" | "seller" | "split";
  fee: string;
  buyer_share: string;
  seller_share: string;
  driver: { name: string; vehicle_type: string; plate_number: string; phone: string; whatsapp: string } | null;
  handover_code?: string;
  dropoff_note?: string;
  can_cancel_choice?: boolean;
  can_reassign?: boolean;
  drivers_notified?: number;
  you_earn?: string;
  listing_title?: string;
  pickup?: { name: string; phone: string };
  dropoff?: { name: string; phone: string; note: string };
  can_pick_up?: boolean;
  can_deliver?: boolean;
}

export interface JobCard {
  id: number;
  order: number;
  listing_title: string;
  pickup_area: Area;
  dropoff_area: Area;
  you_earn: string;
  state: string;
}

export interface DriverJobs {
  open: JobCard[];
  mine: OrderDelivery[];
}
