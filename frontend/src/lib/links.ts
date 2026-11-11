/**
 * Addresses for listings, chats and orders. They use each object's random public code, never its sequential number,
 * so nobody can count or walk through Choropia's data from the address bar. When only a number is known (an older
 * notification, a reel's listing id), the old address is used and the page swaps it for the coded one on arrival.
 */
type Ref = { id: number; public_id?: string | null; slug?: string | null };

export function listingPath(item: Ref | number): string {
  if (typeof item === "number") return `/listings/${item}`;
  if (item.slug) return `/listing/${item.slug}`;
  if (item.public_id) return `/listing/${item.public_id}`;
  return `/listings/${item.id}`;
}

export function chatPath(item: Ref | number): string {
  if (typeof item === "number") return `/messages/${item}`;
  return item.public_id ? `/chat/${item.public_id}` : `/messages/${item.id}`;
}

export function orderPath(item: Ref | number): string {
  if (typeof item === "number") return `/orders/${item}`;
  return item.public_id ? `/order/${item.public_id}` : `/orders/${item.id}`;
}
