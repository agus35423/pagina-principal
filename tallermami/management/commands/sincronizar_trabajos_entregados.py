from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand

from tallermami.models import Turno
from tallermami.services import registrar_trabajo_entregado


class Command(BaseCommand):
    help = (
        "Registra en Trabajos realizados los turnos entregados que "
        "todavía no tienen un registro."
    )

    def handle(self, *args, **options):
        registrados = 0
        omitidos = []
        turnos = (
            Turno.objects.filter(estado="entregado")
            .select_related(
                "cliente",
                "usuario",
                "vehiculo_asociado",
                "trabajador",
                "servicio",
            )
            .order_by("pk")
        )

        for turno in turnos.iterator():
            try:
                registro_anterior = registrar_trabajo_entregado(turno)
            except ValidationError as error:
                omitidos.append((turno.pk, error.messages[0]))
            else:
                if registro_anterior:
                    registrados += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Trabajos registrados o sincronizados: {registrados}."
            )
        )
        if omitidos:
            self.stdout.write(
                self.style.WARNING(
                    f"Turnos omitidos por datos incompletos: {len(omitidos)}."
                )
            )
            for turno_id, motivo in omitidos:
                self.stdout.write(f"Turno #{turno_id}: {motivo}")
