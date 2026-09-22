# Choropia

Social buy-and-sell marketplace for Choropia (Uyo pilot). Users post listings, follow people
and merchant storefronts, chat about listings, and complete purchases through an in-platform
escrow payment + courier delivery flow.

This repo is a monorepo with two parts:

- **This directory (root)** — the backend *and* the web frontend, as one Django project served
  from one process/port. `core/` is the web-frontend app (templates + static JS); every other
  app (`accounts`, `listings`, `orders`, ...) is the token-authenticated (JWT) REST API, plus
  WebSocket endpoints (Django Channels) for chat and live notifications. See below for setup.
- **`android/`** — the Kotlin/Jetpack Compose Android app, built against the same API. See
  `android/README.md`.

The web frontend (`core/`) is still a pure API client, even though it now lives in the same
process as the API: its pages hold no database access of their own and every piece of data on
them comes from the page's own JavaScript (`core/static/core/js/api.js`) calling
`/api/v1/...` with a JWT bearer token — the exact same contract the Android app uses. That's a
deliberate discipline, not automatic just because it's one project: nothing stops a future view
from reaching for `request.user`/the ORM directly instead, so if you're adding a page, keep
going through the API rather than querying models directly from a `core` view.

Since everything is one process now, `/api/v1/` and the web pages share one origin — no CORS
needed between them, and `CHOROPIA_API_BASE_URL` defaults to the relative `/api/v1` (see
`config/settings/base.py`).

Currently implemented: feed, marketplace browse/filter, listing detail,
create listing, buy-now → escrow checkout, order status/escrow timeline (pay, assign courier,
confirm receipt, dispute), messaging, notifications, and merchant storefronts. Not yet built —
these need new backend endpoints, not just frontend work — even though Stitch designs exist for
them: banking/wallet dashboard, P2P send money, linked-accounts settings, reels, and Google SSO
login.

## Stack

- Python 3.12, Django 5, Django REST Framework
- PostgreSQL, Redis (cache + Celery broker + Channels layer)
- Celery + Celery Beat for background/scheduled work (escrow auto-release)
- Django Channels for chat and notification WebSockets
- SimpleJWT for auth (access + refresh tokens, no sessions/cookies)
- django-storages (S3-compatible) for listing photos / avatars
- drf-spectacular for OpenAPI schema + Swagger UI
- Gaxtron for payment collection (crypto/ETH, Sepolia testnet), with an escrow-style
  hold-then-release pattern

## Local setup (Docker)

```bash
cp .env.example .env        # fill in real values, especially DJANGO_SECRET_KEY
docker-compose up --build
```

This starts `web` (the API, served over ASGI so WebSockets work), `worker` (Celery), `beat`
(Celery Beat, runs the hourly escrow auto-release task), `db` (Postgres), and `redis`.

Then, in another terminal:

```bash
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py createsuperuser
docker-compose exec web python manage.py seed_demo
```

The API is now at `http://localhost:8000/api/v1/`, interactive docs at
`http://localhost:8000/api/docs/`, and the raw OpenAPI schema at
`http://localhost:8000/api/schema/`.

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

npm install                     # Tailwind CLI, for building core/static/core/dist/output.css
npm run build                   # one-off build; `npm run dev` instead to watch & rebuild on save

python manage.py runserver
```

Then visit `http://localhost:8000/` for the web app, `http://localhost:8000/api/docs/` for the
API docs — both from the same server.

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
| `chat` | Per-listing buyer/seller conversations, over REST and WebSocket |
| `orders` | The Order state machine — the core of the escrow flow |
| `payments` | Gaxtron integration, escrow hold/release/refund, the auto-release + payment-polling Celery tasks |
| `delivery` | Abstract `DeliveryProvider` interface + mock courier implementation |
| `reviews` | Post-completion buyer/seller ratings |
| `notifications` | In-app notifications, delivered live over WebSocket |
| `moderation` | Reporting listings/users, merchant application review |
| `common` | Shared base models, pagination, permissions, the JWT WebSocket auth middleware |
| `core` | The web frontend — Django templates + Tailwind, calling the API via `fetch()` |

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
  parser doesn't support them) kept in sync by hand with `requirements/base.txt`, and static
  files are served by whitenoise directly from each app's `static/` dir
  (`WHITENOISE_USE_FINDERS`) since there's no `npm run build` + `collectstatic` step in a
  serverless build. That does mean `core/static/core/dist/output.css` has to be committed
  (it's no longer gitignored) — rebuild and commit it (`npm run build`) whenever
  `core/static/core/src/input.css` or `tailwind.config.js` change.
