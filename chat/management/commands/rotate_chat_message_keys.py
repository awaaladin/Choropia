from django.core.management.base import BaseCommand

from chat.crypto import encrypt_message
from chat.models import Message


class Command(BaseCommand):
    help = "Re-encrypt stored chat message bodies with the first configured Fernet key."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Rewrite message bodies. Without this option, only report the number of messages.",
        )

    def handle(self, *args, **options):
        encrypt_message("key validation")
        messages = Message.objects.exclude(body="").only("pk", "body")
        count = messages.count()
        if not options["apply"]:
            self.stdout.write(f"{count} non-empty message body/bodies are eligible for key rotation.")
            self.stdout.write("Run again with --apply to re-encrypt them.")
            return

        for message in messages.iterator(chunk_size=500):
            message.save(update_fields=["body"])
        self.stdout.write(self.style.SUCCESS(f"Re-encrypted {count} message body/bodies."))
