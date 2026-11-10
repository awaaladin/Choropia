# Parity and root-cause audit

## Feature matrix

| Area | Web | Android | Notes |
|---|---:|---:|---|
| Listings browse | Yes | Yes | Completed |
| Listing detail and seller card | Yes | Yes | Completed |
| Chat direct thread | Yes | Yes | Pair-based thread fix landed |
| Listing reference cards in chat | Yes | Yes | A listing reference can be opened from the canonical direct thread |
| Escrow offers in chat | Yes | Yes | Private offer checkout creates an escrow order at the locked offer price |
| Media attachments | Yes | Yes | Images and voice notes use the chat attachment API and the returned storage URL |
| Sold state and duration | Partial | Partial | Backend concepts exist; UI/QA remains to be completed |
| Comments author payload | Yes | Yes | Authors resolved with profile metadata |
| Profiles | Partial | Partial | Public profile endpoints and deep links are present |
| Reels | Partial | Partial | Feed fallback for image cards remains available |

## Root-cause findings

- Chat threads were unique on `(listing, buyer)`, which forced a separate conversation for the same pair of people on each listing. This caused the raw DRF uniqueness error when a buyer clicked Message seller from a different listing for the same seller.
- The direct-thread fix normalizes conversation lookup so the same two people share one chat regardless of the listing they are viewing. The underlying database constraint now enforces one thread per buyer/seller pair.
- A chat offer is private to the conversation. Checkout uses the amount locked on the offer to create a standard escrow order and does not change the public listing price.
- Web chat can upload images and record voice notes; Android and web render attachment URLs returned by the same message serializer.

## Remaining gaps and rough effort

- Sold duration and visibility flows: 3–5 days
- Guest comments and anonymous likes: 2–3 days
- Profile deep-linking and privacy enforcement: 3–4 days
- Full reels upload/composer flow: 4–6 days
