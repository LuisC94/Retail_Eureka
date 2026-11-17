from django.core.management.base import BaseCommand, CommandError

from dashboard.models import LedgerEntry
from dashboard.services.local_ledger_service import LocalLedgerService


class Command(BaseCommand):
    help = "Verifica a integridade da cadeia de hashes do ledger local (LedgerEntry)."

    def handle(self, *args, **options):
        total = LedgerEntry.objects.count()
        ok, problems = LocalLedgerService().verify_chain()
        if ok:
            self.stdout.write(self.style.SUCCESS(f"Ledger íntegro: {total} blocos verificados."))
            return
        for p in problems:
            self.stderr.write(self.style.ERROR(p))
        raise CommandError(f"Ledger comprometido: {len(problems)} problema(s) em {total} blocos.")
