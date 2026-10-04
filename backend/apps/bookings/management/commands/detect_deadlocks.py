from django.core.management.base import BaseCommand, CommandError

from apps.bookings.deadlocks import find_cycles, mysql_wait_for_edges


class Command(BaseCommand):
    help = "Inspect MySQL InnoDB wait-for edges and report deadlock cycles without killing transactions."

    def handle(self, *args, **options):
        try:
            edges = mysql_wait_for_edges()
        except Exception as exc:
            raise CommandError(f"Could not inspect performance_schema.data_lock_waits: {exc}") from exc
        cycles = find_cycles(edges)
        self.stdout.write(f"Observed wait edges: {len(edges)}")
        if cycles:
            self.stdout.write(self.style.ERROR(f"Deadlock cycles detected: {cycles}"))
            self.stdout.write("Recovery policy: inspect the oldest transaction and retry the booking request; no transaction is killed automatically.")
        else:
            self.stdout.write(self.style.SUCCESS("No deadlock cycle detected."))
