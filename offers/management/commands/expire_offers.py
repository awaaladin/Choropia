from django.core.management.base import BaseCommand

from offers.services import expire_due_offers


class Command(BaseCommand):
    help = "Marks pending chat offers whose time is up as EXPIRED (and updates both people's chat cards)."

    def handle(self, *args, **options):
        result = expire_due_offers()
        self.stdout.write(f"Expired {result['expired']} offer(s).")
