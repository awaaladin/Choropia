# Parity and root-cause audit

## Feature matrix

| Area | Web | Android | Notes |
|---|---:|---:|---|
| Listings browse | Yes | Yes | Completed |
| Listing detail and seller card | Yes | Yes | Completed |
| Chat direct thread | Yes | Yes | Pair-based thread fix landed |
| Listing reference cards in chat | Partial | Partial | Backend model field and API support added; UI still needs final card polish |
| Escrow offers in chat | Yes | Yes | Existing offer flow continues to be the source of truth |
| Media attachments | Yes | Yes | Web and mobile image/voice exchange rely on signed read URLs |
| Sold state and duration | Partial | Partial | Backend concepts exist; UI/QA remains to be completed |
| Comments author payload | Yes | Yes | Authors resolved with profile metadata |
| Profiles | Partial | Partial | Public profile endpoints and deep links are present |
| Reels | Partial | Partial | Feed fallback for image cards remains available |

## Root-cause findings

- Chat threads were unique on `(listing, buyer)`, which forced a separate conversation for the same pair of people on each listing. This caused the raw DRF uniqueness error when a buyer clicked Message seller from a different listing for the same seller.
- The direct-thread fix normalizes conversation lookup so the same two people share one chat regardless of the listing they are viewing. The underlying database constraint now enforces one thread per buyer/seller pair.
- This work preserves the existing offer and messaging flow while preventing duplicate conversations from being created by listing-click entry points.

## Remaining gaps and rough effort

- Listing-reference chat cards: 2–4 days
- Audit and final media-signing parity: 2–3 days
- Sold duration and visibility flows: 3–5 days
- Guest comments and anonymous likes: 2–3 days
- Profile deep-linking and privacy enforcement: 3–4 days
- Full reels upload/composer flow: 4–6 days
