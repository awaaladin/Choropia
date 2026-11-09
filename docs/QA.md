# QA checklist

## Chat and pairing

- [ ] App -> web image from the same seller opens the same thread, not a duplicate listing-scoped chat.
- [ ] Web -> app image from the same seller opens the same thread, not a duplicate listing-scoped chat.
- [ ] Two different listings from the same seller open one direct thread for the same buyer and seller pair.
- [ ] Message seller from feed, listing detail, profile and comment routes opens the correct thread and focuses composer.

## Media parity

- [ ] App -> web image displays correctly and loads without the loading blob.
- [ ] App -> web voice note plays on web without a spinner loop.
- [ ] Web -> app image displays correctly.
- [ ] Web -> app voice note plays on Android.
- [ ] Failed media states show a friendly message and a retry/download affordance when playback is unsupported.

## Sold and offers

- [ ] Sold duration flow works for 1, 3, 7, 14 and 30 days.
- [ ] Sold listing stays visible until the cutoff and then disappears from public marketplace views.
- [ ] Seller can relist or extend a sold listing without changing list price.
- [ ] Offer creation leaves the catalog price untouched and only records the offer amount in the escrow flow.

## Comments and profiles

- [ ] The author name is always shown instead of the fallback `User 11` text.
- [ ] Guest comments are blocked with `AUTH_REQUIRED` and preserve the draft.
- [ ] Profile entry points open a profile screen with avatar, name, verified badge and public listings.

## Reels

- [ ] When real reels are missing, the feed still renders product-image fallback cards.
- [ ] A newly created reel appears in the feed on both platforms once processing is complete.
