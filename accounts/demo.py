"""
Demo content support.

Demo sellers are ordinary rows in the users table but with a reserved, non-routable email domain
and an unusable password, so nobody can ever log in as one. Anything they "own" is display-only:
the order and chat endpoints refuse to act on a demo listing, so a real buyer can never pay a
seller who doesn't exist.
"""

DEMO_EMAIL_DOMAIN = "demo.choropia.invalid"
DEMO_LISTING_MESSAGE = "This is a demo listing for illustration. It can't be bought or messaged."


def is_demo_user(user) -> bool:
    email = getattr(user, "email", "") or ""
    return email.lower().endswith("@" + DEMO_EMAIL_DOMAIN)
