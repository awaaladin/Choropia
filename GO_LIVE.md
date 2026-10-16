# Go-live checklist

Verified against the live site on 16 Oct 2026 with the Vercel CLI (`vercel logs`) and a throwaway
account (since deleted). Sign-up, login, feed, profile, notifications, orders, wallet summary,
categories, listings, reels (read), all SPA routes and static assets worked. Two things did not.

## What was broken, and its status

| # | Symptom | Cause (from the production log) | Status |
|---|---|---|---|
| 1 | Posting a listing **with a photo** returned 500. Same for avatars, reel videos, chat attachments. A photo-less listing was left behind. | `OSError: [Errno 30] Read-only file system: '/var/task/mediafiles'`. Vercel's disk is read-only and no object storage was configured. | **Fixed.** A Vercel Blob store (`choropia-media`) is connected and `common/blob_storage.py` stores uploads there. A storage outage now answers 503 with a message and rolls the listing back. |
| 2 | "Forgot password" returned 500 for real accounts. | `SMTPServerDisconnected`: no working `EMAIL_*` settings on Vercel. | **Code fixed** (no more 500; failure is logged, reply stays 200). **Emails still won't send until you add SMTP credentials (section A).** |
| 3 | Paying for an order will fail. | No Gaxtron variables on Vercel; `GAXTRON_BASE_URL` defaults to `127.0.0.1`. | **Open** (section B). |

## How uploads are stored now

`BLOB_READ_WRITE_TOKEN` (set automatically when the store was connected) switches Django's file
storage to Vercel Blob. `BLOB_PUBLIC_BASE_URL` is the store's public host. Files get an
unguessable random suffix and are served from Vercel's CDN. To use Supabase/S3 instead, set
`USE_S3=true` and the `AWS_*` variables (`AWS_DEFAULT_ACL=none`, `AWS_S3_ADDRESSING_STYLE=path` for
Supabase); S3 wins if both are configured.

Limits: Vercel rejects request bodies over about **4.5 MB**. Photos are compressed on the phone;
**reel videos will exceed that** and need a direct-to-Blob upload before reels accept real videos.

## A. Email for password reset (needs your credentials)

Pick an SMTP provider (Resend, Brevo, Mailgun, or Gmail with an app password) and set on Vercel:

```
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=...   EMAIL_PORT=587   EMAIL_USE_TLS=true
EMAIL_HOST_USER=...   EMAIL_HOST_PASSWORD=...
DEFAULT_FROM_EMAIL="Choropia <no-reply@your-domain>"
```

`PASSWORD_RESET_URL_BASE` has been set to `https://choropia.vercel.app/reset-password`.
Use `vercel env update NAME production` for names that already exist, then redeploy.
Test with a real account's address and check `vercel logs --project choropia --level error`.

## B. Payments (Gaxtron) — wallet/web session

Set on Vercel: `GAXTRON_BASE_URL` (publicly reachable), `GAXTRON_API_KEY`,
`GAXTRON_WEBHOOK_SECRET`, `GAXTRON_CALLBACK_URL`
(`https://choropia.vercel.app/api/v1/payments/webhook/gaxtron/`). Remove the old `PAYSTACK_*`.
The values in the local `.env` are development values (localhost, httpbin) and must not be copied.

## C. Optional

- Google sign-in: set `GOOGLE_OAUTH_CLIENT_ID` (the endpoint returns 503 until then).
- Starter content: `python manage.py seed_launch` adds 8 labelled "Demo:" listings from sellers
  that cannot log in, and the API refuses to buy or message them. `seed_launch --remove` deletes
  them. **Do not use `seed_demo` on production**: it creates logins with a password written in the repo.
- Migrations are already applied on production (`accounts 0002`, `chat 0002`, `reels 0001`).

## Useful commands

```bash
vercel logs --project choropia --environment production --since 15m --level error -x
vercel logs --project choropia --environment production --status-code 500 --since 1h -x
vercel env ls production            # names only; values are hidden
```

Runtime logs are only kept for a short window, so reproduce first, then read them.
