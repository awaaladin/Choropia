"""
Production-safe starter content so a brand-new marketplace isn't an empty page.

Unlike `seed_demo` (local testing only: it creates logins with a password written in the repo),
this command:
  * creates demo sellers that CANNOT log in (unusable password, reserved email domain);
  * labels every listing "Demo:" and says so in the description;
  * generates a placeholder photo per listing and stores it through the configured file storage;
  * is idempotent, and `--remove` deletes everything it created.

Orders and chats on demo listings are refused by the API (see accounts/demo.py).
"""
import io
import textwrap

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from PIL import Image, ImageDraw, ImageFont

from accounts.demo import DEMO_EMAIL_DOMAIN, DEMO_LISTING_MESSAGE
from listings.models import Category, Listing, ListingPhoto

User = get_user_model()

SELLERS = [
    ("demo.seller.one", "Demo", "Seller"),
    ("demo.seller.two", "Demo", "Store"),
]

# (title, category, price NGN, condition, seller index, description)
ITEMS = [
    ("iPhone 12, 128GB", "Phones & Tablets", "185000.00", "used", 0, "Clean, fully working, battery health 86%. Comes with charger."),
    ("Samsung Galaxy A54, 256GB", "Phones & Tablets", "245000.00", "new", 1, "Brand new, sealed box. 1-year warranty."),
    ("HP EliteBook 840, 16GB RAM", "Electronics", "320000.00", "used", 0, "Core i7, 512GB SSD. Great for work and school."),
    ("43-inch Smart TV", "Electronics", "210000.00", "new", 1, "4K, built-in streaming apps, wall mount included."),
    ("Tailored Ankara shirt", "Fashion", "12000.00", "new", 0, "Made to measure in Uyo. Ready in 3 days."),
    ("Leather handbag", "Fashion", "18500.00", "new", 1, "Genuine leather, two compartments, gold hardware."),
    ("3-seater sofa set", "Home & Furniture", "150000.00", "used", 0, "Comfortable and in good condition. Pickup in Uyo."),
    ("Event photography (full day)", "Services", "80000.00", "new", 1, "Weddings, birthdays and corporate events. Edited photos within a week."),
]

CATEGORY_COLORS = {
    "Phones & Tablets": ("#0B192C", "#1E3E62"),
    "Electronics": ("#132B47", "#426086"),
    "Fashion": ("#3B1F4A", "#7A4A8C"),
    "Home & Furniture": ("#3D2B1F", "#8A6445"),
    "Services": ("#14392B", "#2F7A5A"),
    "Vehicles": ("#2B2B2B", "#5C5C5C"),
}


def _hex(value):
    return tuple(int(value[i : i + 2], 16) for i in (1, 3, 5))


def placeholder_photo(title, category):
    """A simple branded 4:3 card (gradient + title) used when a seller has no real photo."""
    width, height = 1000, 750
    top, bottom = (_hex(c) for c in CATEGORY_COLORS.get(category, ("#0B192C", "#1E3E62")))
    image = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(image)
    for y in range(height):
        t = y / (height - 1)
        draw.line([(0, y), (width, y)], fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))

    big = ImageFont.load_default(size=64)
    small = ImageFont.load_default(size=34)
    draw.text((60, 60), "DEMO LISTING", font=small, fill=(255, 255, 255, 160))
    wrapped = textwrap.fill(title, width=18)
    draw.multiline_text((60, 280), wrapped, font=big, fill="white", spacing=14)
    draw.text((60, height - 90), category, font=small, fill=(255, 255, 255, 190))

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=82)
    return buffer.getvalue()


class Command(BaseCommand):
    help = "Seeds production-safe demo listings (non-loginable sellers, labelled, not purchasable). --remove undoes it."

    def add_arguments(self, parser):
        parser.add_argument("--remove", action="store_true", help="Delete all demo sellers, listings and photos.")

    def handle(self, *args, **options):
        if options["remove"]:
            return self._remove()
        self._seed()

    @transaction.atomic
    def _seed(self):
        sellers = []
        for handle, first, last in SELLERS:
            user, created = User.objects.get_or_create(
                email=f"{handle}@{DEMO_EMAIL_DOMAIN}",
                defaults={"first_name": first, "last_name": last},
            )
            if created:
                user.set_unusable_password()  # nobody can ever log in as a demo seller
                user.save()
            user.profile.location = "Uyo"
            user.profile.save(update_fields=["location"])
            sellers.append(user)

        created_count = 0
        for title, category_name, price, condition, seller_index, description in ITEMS:
            category, _ = Category.objects.get_or_create(name=category_name)
            full_title = f"Demo: {title}"
            listing, created = Listing.objects.get_or_create(
                title=full_title,
                owner=sellers[seller_index],
                defaults={
                    "category": category,
                    "price": price,
                    "condition": condition,
                    "location": "Uyo",
                    "description": f"{description}\n\n{DEMO_LISTING_MESSAGE}",
                },
            )
            if created:
                created_count += 1
            if not listing.photos.exists():
                ListingPhoto.objects.create(
                    listing=listing,
                    image=ContentFile(placeholder_photo(title, category_name), name="demo.jpg"),
                    order=0,
                )
        self.stdout.write(self.style.SUCCESS(f"Demo content ready: {created_count} new listings ({len(ITEMS)} total)."))

    @transaction.atomic
    def _remove(self):
        users = User.objects.filter(email__endswith="@" + DEMO_EMAIL_DOMAIN)
        photos = ListingPhoto.objects.filter(listing__owner__in=users)
        for photo in photos:
            photo.image.delete(save=False)  # also removes the stored file, not just the row
        listings = Listing.objects.filter(owner__in=users).count()
        users.delete()
        self.stdout.write(self.style.SUCCESS(f"Removed demo content ({listings} listings)."))
