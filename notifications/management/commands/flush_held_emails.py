from django.core.management.base import BaseCommand

from notifications import emails


class Command(BaseCommand):
    help = "Send emails that were held back by the daily sending limit, oldest first."

    def handle(self, *args, **options):
        sent = emails.flush_held(200)
        self.stdout.write(f"Sent {sent}; still held: {emails.held_count()}")
