from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from listings.models import Category, Listing
from merchants.models import Merchant, MerchantApplication

User = get_user_model()

CATEGORIES = ["Phones & Tablets", "Electronics", "Fashion", "Home & Furniture", "Vehicles", "Services"]

DEMO_USERS = [
    {"email": "demo.buyer@choropia.test", "first_name": "Aniekan", "last_name": "Udo"},
    {"email": "demo.seller@choropia.test", "first_name": "Ini", "last_name": "Etuk"},
    {"email": "demo.merchant@choropia.test", "first_name": "Uduak", "last_name": "Akpan"},
]

DEMO_PASSWORD = "ChoropiaDemo123!"


class Command(BaseCommand):
    help = "Creates demo categories, users, a merchant storefront, and listings for local testing."

    @transaction.atomic
    def handle(self, *args, **options):
        categories = {}
        for name in CATEGORIES:
            category, _ = Category.objects.get_or_create(name=name)
            categories[name] = category
        self.stdout.write(f"Categories ready: {', '.join(categories)}")

        users = {}
        for data in DEMO_USERS:
            user, created = User.objects.get_or_create(
                email=data["email"],
                defaults={"first_name": data["first_name"], "last_name": data["last_name"]},
            )
            if created:
                user.set_password(DEMO_PASSWORD)
                user.save()
            user.profile.location = "Uyo"
            user.profile.save(update_fields=["location"])
            users[data["email"]] = user
        self.stdout.write(f"Demo users ready (password: {DEMO_PASSWORD})")

        merchant_user = users["demo.merchant@choropia.test"]
        application, _ = MerchantApplication.objects.get_or_create(
            applicant=merchant_user,
            defaults={
                "business_name": "Uyo Gadget Hub",
                "business_description": "Phones, laptops and accessories — new and fairly used.",
                "business_phone": "08000000000",
                "business_address": "Wellington Bassey Way, Uyo",
            },
        )
        merchant = application.approve(reviewer=merchant_user)
        self.stdout.write(f"Merchant storefront ready: {merchant.business_name}")

        seller = users["demo.seller@choropia.test"]
        listings_data = [
            ("iPhone 12, 128GB", "Phones & Tablets", "185000.00", Listing.Condition.USED, seller, None),
            ("Samsung 55\" Smart TV", "Electronics", "310000.00", Listing.Condition.NEW, seller, None),
            ("Ankara Sewing Service", "Services", "15000.00", Listing.Condition.NEW, seller, None),
            ("HP Laptop 8GB RAM", "Electronics", "260000.00", Listing.Condition.USED, merchant_user, merchant),
        ]
        for title, category_name, price, condition, owner, merchant_ref in listings_data:
            Listing.objects.get_or_create(
                title=title,
                owner=owner,
                defaults={
                    "category": categories[category_name],
                    "price": price,
                    "condition": condition,
                    "merchant": merchant_ref,
                    "location": "Uyo",
                },
            )
        self.stdout.write(self.style.SUCCESS(f"Seeded {len(listings_data)} demo listings."))
