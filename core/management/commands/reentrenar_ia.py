"""Bloque D: incorpora al modelo lo aprendido del uso (IASugerencia).

Limpia el caché del clasificador para que el próximo predecir_categoria
entrene con EJEMPLOS + muestras de usuarios. No borra nada.
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Reentrena el clasificador incluyendo muestras aprendidas del uso."

    def handle(self, *args, **options):
        from core.ia import reiniciar_modelo, predecir_categoria
        from core.models import IASugerencia

        n = IASugerencia.objects.exclude(categoria_final__isnull=True).count()
        reiniciar_modelo()
        cat, conf = predecir_categoria("Hay una fuga de agua bajo el lavaplatos")
        self.stdout.write(
            f"Muestras aprendidas: {n}. Modelo reiniciado; "
            f"prueba: {cat} ({conf:.0%}).")
