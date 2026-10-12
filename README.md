# Choropia

Social buy-and-sell marketplace for Choropia (Uyo pilot). Users post listings, follow people
and merchant storefronts, chat about listings, and complete purchases through an in-platform
escrow payment + courier delivery flow.

This repo is a monorepo with three parts:

- **This directory (root)** — the Django backend: token-authenticated (JWT) REST API apps
  (`accounts`, `listings`, `orders`, ...) plus WebSocket endpoints (Django Channels) for chat
  and live notifications.
- **`frontend/`** — the web app: a React + TypeScript SPA (Vite, Tailwind v4, React Router,
  TanStack Query), built from the "fluid-ui-polish" redesign. See `frontend/` below.
- **`android/`** — the Kotlin/Jetpack Compose Android app, built against the same API. See
  `android/README.md`.

The web frontend is a pure API client: it holds no database access of its own, and every piece
of data comes from `frontend/src/lib/api.ts` calling `/api/v1/...` with a JWT bearer token — the
exact same contract the Android app uses.

In production (and in the Docker realtime host) Django serves the frontend's built output
directly — `core/views.py`'s `SPAView` returns `frontend/dist/index.html` for any route that
isn't `/api/`, `/admin/`, or a real static file (which WhiteNoise serves straight from
`frontend/dist/`, see `WHITENOISE_ROOT` in `config/settings/base.py`) — so the API and the web
app are one deployment, one origin, no CORS needed. In local dev they run as two processes
instead (Vite's dev server for instant HMR, proxying `/api` and `/ws` to Django) — see
`frontend/`'s setup below.

Currently implemented: feed, marketplace browse/filter, listing detail,
create listing, buy-now → escrow checkout, order status/escrow timeline (pay, assign courier,
confirm receipt, dispute), messaging, notifications, and merchant storefronts. Not yet built —
these need new backend endpoints, not just frontend work — even though Stitch designs exist for
them: banking/wallet dashboard, P2P send money, linked-accounts settings, reels, and Google SSO
login.

## Stack

- Python 3.12, Django 5, Django REST Framework
- React 19, TypeScript, Vite, Tailwind v4, React Router, TanStack Query (`frontend/`)
- PostgreSQL, Redis (cache + Celery broker + Channels layer)
- Celery + Celery Beat for background/scheduled work (escrow auto-release)
- Django Channels for chat and notification WebSockets
- SimpleJWT for auth (access + refresh tokens, no sessions/cookies)
- django-storages (S3-compatible) for listing photos / avatars
- drf-spectacular for OpenAPI schema + Swagger UI
- Gaxtron for payment collection (crypto/ETH, Sepolia testnet), with an escrow-style
  hold-then-release pattern

## Web frontend (`frontend/`)

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173 — proxies /api and /ws to Django on :8000
```

`npm run build` produces `frontend/dist/`, which **must be committed** — Vercel's Python
builder only runs `pip install`, not `npm run build`, so the compiled app has to already be in
the repo for the deployed site to have anything to serve. Rebuild and commit it whenever
`frontend/src/` changes you want live. `npm run typecheck` runs `tsc --noEmit` on its own,
faster than a full build, for catching type errors while iterating.

Design tokens, fonts (Manrope/Sora) and motion (`frontend/src/styles.css`) are ported from the
"fluid-ui-polish" redesign. `frontend/src/lib/prefs.tsx` holds the user's theme/layout/density/
motion preferences (persisted to `localStorage`, synced to `profile.theme_preference` for
logged-in users) — the Settings drawer in the header edits them. `frontend/src/components/
BrandLoader.tsx` is the real-logo loading screen: a "full" variant (pulsing mark + reflection +
the wordmark sliding in from the side and back out) on app boot and during login/signup, and a
"simple" variant (the mark alone) on ordinary in-app navigation — see `AppBoot.tsx` and
`AppShell.tsx`'s `useRouteTransition`.

## Realtime host (Docker)

`docker-compose.yml` runs the parts Vercel can't: `web` (daphne/ASGI, holding the chat and
notification WebSockets), `worker` (Celery) and `beat` (escrow auto-release, gaxtron payment
polling). It uses the Supabase Postgres and the shared Upstash Redis from `.env`
(`DATABASE_URL` / `REDIS_URL`) — the same ones the Vercel site uses, which is what lets a
message sent through a Vercel request reach a WebSocket held here. There are no local db/redis
containers, so `.env` must hold real values (`.env.example` lists them).

```bash
docker compose up --build -d                 # http://localhost:8000
docker compose run --rm web python manage.py migrate   # after model changes
```

To serve the WebSockets to the Vercel site you need a public host with a domain, since browsers
block `ws://` from an https page. On that host:

```bash
SITE_ADDRESS=realtime.example.com docker compose --profile tls up --build -d   # adds Caddy (auto-TLS)
```

Then in Vercel set `CHOROPIA_WS_BASE_URL=wss://realtime.example.com` and `REDIS_URL` (same value
as this host), and add the domain to `DJANGO_ALLOWED_HOSTS` here.

The API is at `/api/v1/`, interactive docs at `/api/docs/`, the OpenAPI schema at
`/api/schema/`.

## Local setup (without Docker)

By default `DATABASE_URL` in `.env.example` points at Postgres, but if you leave `DATABASE_URL`
unset entirely, `config/settings/base.py` falls back to a local `db.sqlite3` — handy for a quick
native run without standing up Postgres/Redis.

```bash
python -m venv venv
source venv/Scripts/activate   # venv\Scripts\activate on native Windows shells
pip install -r requirements/dev.txt

python manage.py migrate
python manage.py createsuperuser
python manage.py seed_demo      # demo categories, users, a merchant, and listings

python manage.py runserver      # :8000 — just the API now; see frontend/ for the web app
```

Then, in another terminal, start the frontend (see "Web frontend" above) — visit
`http://localhost:5173/` for the web app, `http://localhost:8000/api/docs/` for the API docs.

Note: without Redis running, Channels/Celery-backed features (chat delivery, live
notifications, escrow auto-release) won't work — the REST endpoints for those apps still work,
they just won't push realtime updates or run the background task.

## Running tests

```bash
python manage.py test --settings=config.settings.test
```

`config/settings/test.py` runs against an in-memory SQLite database, eager (synchronous) Celery
tasks, and an in-memory Channels layer, so the full suite runs with no external services up.

The two test modules worth reading first are the ones covering the highest-risk logic in the
app — money and delivery state must never end up invalid:

- `orders/tests/test_state_machine.py` — the Order status graph: valid transitions, that states
  can't be skipped or reversed, and that an invalid transition leaves the order and its audit
  history untouched.
- `payments/tests/test_escrow_release.py` — `release_escrow` idempotency, and the
  `auto_release_escrow_task` Celery Beat task: orders past the escrow window get auto-completed
  and released, orders within the window or in a dispute are left alone, and a manually-confirmed
  order isn't double-processed.

## Project layout

Each business area is its own Django app rather than one big app:

| App | Responsibility |
|---|---|
| `accounts` | Custom User (email or phone login), Profile, theme preference |
| `social` | Follows (User or Merchant), likes/comments on listings, the feed |
| `listings` | Categories, Listings, photos, search/filter |
| `merchants` | Merchant applications and approved storefronts |
| `reels` | Short vertical videos, optionally tied to a Listing ("shoppable"); likes/comments |
| `chat` | Per-listing buyer/seller conversations, over REST and WebSocket |
| `orders` | The Order state machine — the core of the escrow flow |
| `payments` | Gaxtron integration, escrow hold/release/refund, the auto-release + payment-polling Celery tasks |
| `delivery` | Abstract `DeliveryProvider` interface + mock courier implementation |
| `reviews` | Post-completion buyer/seller ratings |
| `notifications` | In-app notifications, delivered live over WebSocket |
| `moderation` | Reporting listings/users, merchant application review |
| `common` | Shared base models, pagination, permissions, the JWT WebSocket auth middleware |
| `core` | `SPAView` — serves `frontend/dist/index.html` for every non-API route |

Settings are split into `config/settings/{base,dev,prod,test}.py` — all secrets come from
environment variables (`.env` locally, real env vars in production), never hardcoded.

## Swapping in a real courier

`delivery/providers/base.py` defines the `DeliveryProvider` interface
(`create_shipment` / `get_status` / `cancel_shipment`). `delivery/providers/mock.py` is the only
implementation right now. To go live with a real courier, implement the same interface and point
`DELIVERY_PROVIDER` in `.env` at it — nothing in the Order state machine changes.

## Escrow model

Gaxtron has no native "hold funds" primitive, so escrow is emulated: the buyer's payment is
collected into a wallet gaxtron custodies for that payment (see `payments/gaxtron.py` and
`payments/services.py`), and the "hold" is simply that Choropia doesn't move money to the
seller until the order reaches `confirmed`/`completed` — Choropia itself is the hold. Gaxtron
also has no payout/transfer endpoint, so — same as it was under Paystack, which needed a
transfer-recipient onboarding flow that was never built — `release_escrow`/`refund_escrow`
record the status change without moving crypto. `payments/tasks.py` runs on Celery Beat and
auto-releases escrow `ESCROW_AUTO_RELEASE_DAYS` (default 3) after delivery if the buyer
neither confirms nor disputes; it also polls gaxtron for payment confirmation
(`poll_gaxtron_payments_task`), since gaxtron's webhook can't reach a localhost/private-IP
deployment (see `payments/gaxtron.py` for why).

Choropia lists prices in NGN; gaxtron settles in ETH only. `GAXTRON_NGN_PER_USD` plus gaxtron's
own `/markets/prices` (ETH/USD) convert an order's price at checkout time — there's no live
forex feed wired in, so treat that rate as an approximation to update by hand.

## Deploying

- **Docker** (full stack — web + API + WebSockets + Celery worker/beat): `Dockerfile` /
  `docker-compose.yml`, served over ASGI via daphne so chat/notification WebSockets work.
- **Vercel** (`vercel.json` / `api/index.py`): serverless HTTP only — Vercel's Python runtime
  can't host Channels' WebSocket consumers or Celery workers/beat, so chat/notification
  WebSockets and background jobs (escrow auto-release, gaxtron payment polling) don't run
  there. It's the web frontend + non-realtime API only; the Docker stack is what should be
  running the WebSocket/Celery pieces in production regardless of where else this is deployed.
  Vercel needs its own root-level `requirements.txt` (flattened, no `-r` includes — its
  parser doesn't support them) kept in sync by hand with `requirements/base.txt`. Since
  there's no `npm run build` step in a serverless build either, `frontend/dist/` has to already
  be committed (see "Web frontend" above) — WhiteNoise serves it directly
  (`WHITENOISE_ROOT`), and Django admin's own static files are served the same way
  (`WHITENOISE_USE_FINDERS`), with no `collectstatic` step needed for either.
