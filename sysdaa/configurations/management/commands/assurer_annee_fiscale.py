from django.core.management.base import BaseCommand
from configurations.services import assurer_annee_fiscale_active_auto


class Command(BaseCommand):
    help = "Assure l'année fiscale active automatiquement (1 Oct -> 30 Sep)."

    def handle(self, *args, **options):
        af = assurer_annee_fiscale_active_auto()
        self.stdout.write(
            self.style.SUCCESS(
                f"OK: Année fiscale active = {af.annee_debut}-{af.annee_fin}"
            )
        )