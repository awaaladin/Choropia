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
}

export interface User {
  id: number;
  email: string;
  phone_number: string | null;
  first_name: string;
  last_name: string;
  profile?: Profile;
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
  author_name?: string;
  body: string;
  created_at: string;
}

export interface Like {
  id: number;
  listing: number;
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
  created_at: string;
}

export interface Conversation {
  id: number;
  listing: number;
  listing_title?: string;
  other_party_name?: string | null;
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
