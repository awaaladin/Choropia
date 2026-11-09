from django.apps import apps
from django.core.management.base import BaseCommand

from chat.thread_merge import merge_conversations


class Command(BaseCommand):
    help = "Merge conversations for the same pair of people before enabling direct-thread uniqueness."

    def add_arguments(self, parser):
        mode = parser.add_mutually_exclusive_group(required=True)
        mode.add_argument("--dry-run", action="store_true", help="Print the merge plan without changing data.")
        mode.add_argument("--apply", action="store_true", help="Apply the reported conversation merges.")

    def handle(self, *args, **options):
        Conversation = apps.get_model("chat", "Conversation")
        unnormalized = Conversation.objects.filter(user_low__isnull=True).count()
        def report(row):
            self.stdout.write(
                "pair={pair} keep={keeper} merge={duplicates} messages={messages} offers={offers} orders={orders}".format(
                    **row
                )
            )

        plan = merge_conversations(apps, dry_run=options["dry_run"], write=report)
        if options["dry_run"]:
            self.stdout.write(f"{unnormalized} thread(s) need canonical participant IDs.")
        if not plan:
            if not options["dry_run"]:
                self.stdout.write("No duplicate direct conversations found.")
            elif unnormalized == 0:
                self.stdout.write("No duplicate or unnormalized direct conversations found.")
        elif options["dry_run"]:
            self.stdout.write(f"Dry run: {len(plan)} pair(s) would be merged; no data was changed.")
        else:
            self.stdout.write(f"Merged {len(plan)} duplicate pair(s).")
