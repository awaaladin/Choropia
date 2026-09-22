# Choropia — Android app

Native Android client for Choropia, written in Kotlin with Jetpack Compose. Talks to the same
backend API (`../choropia`) as the web frontend, over the same JWT bearer-token contract — no
cookies, no sessions, matching the backend's "token auth for every client" design.

## Opening the project

This was scaffolded by hand (no Android Studio available in this environment to generate it), so
the Gradle wrapper jar itself isn't included:

1. Open the `choropia app` folder in Android Studio (Koala/2024.1+).
2. Let it prompt you to generate the Gradle wrapper, or run `gradle wrapper` once you have a
   local Gradle install, then sync the project.
3. Run on an emulator or device.

## Backend connection

`app/build.gradle.kts` sets `API_BASE_URL`/`WS_BASE_URL` as `BuildConfig` fields, defaulting to:

- `http://10.0.2.2:8000/api/v1/` — `10.0.2.2` is the Android emulator's alias for your host
  machine's `localhost`, so this points at `../choropia` running via `manage.py runserver` or
  docker-compose on the same machine.
- `ws://10.0.2.2:8000` for the chat/notification WebSocket endpoints.

Point these at a real deployed API URL for a release build (override `buildConfigField` per
build type, or move them into `local.properties`/`gradle.properties` once you have a real
staging/production URL).

## Architecture

- `data/network/` — Retrofit interface (`ApiService.kt`) + `ApiClient.kt`, which attaches the
  JWT bearer header on every request and auto-refreshes once on a 401 (via an OkHttp
  `Authenticator`), and `ChatSocket.kt`, a small OkHttp WebSocket wrapper for `/ws/chat/<id>/`.
- `data/TokenManager.kt` — persists the access/refresh pair in DataStore Preferences.
- `data/repository/ChoropiaRepository.kt` — the one place screens talk to; wraps the raw
  Retrofit calls and keeps token persistence out of the UI layer.
- `ui/screens/` — one Composable per screen (login, register, feed, listing detail, chat,
  orders, profile), each managing its own state directly with `remember`/`LaunchedEffect`
  rather than separate ViewModel classes — kept intentionally simple for this first pass.
- `navigation/ChoropiaNavHost.kt` — single-Activity Compose navigation graph.

## What's stubbed

This covers the same core buyer journey as the web frontend: browse listings → view a listing →
message the seller → chat → see your orders → profile. Not yet built: posting a listing,
merchant storefront screens, reviews, push notifications, and image upload — the backend already
exposes all of those endpoints (see `../choropia/README.md` and `/api/docs/`), so extending this
is mostly repeating the pattern already in `FeedScreen.kt`/`ListingDetailScreen.kt`.
