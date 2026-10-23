
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from tallermami.models import Turno
from tallermami.utils import enviar_correo_taller


class Command(BaseCommand):
    help = "Envía recordatorios de turnos para el día siguiente"

    def handle(self, *args, **options):
        manana = timezone.localdate() + timedelta(days=1)

        turnos = Turno.objects.filter(
            fecha_turno__date=manana,
        ).exclude(
            estado="cancelado",
        ).filter(
            recordatorio_enviado=False,
        ).select_related("usuario", "servicio")

        enviados = 0

        for turno in turnos:
            if not turno.usuario or not turno.usuario.email:
                self.stdout.write(
                    f"Turno #{turno.pk}: no tiene correo asociado."
                )
                continue

            usuario = turno.usuario

            asunto = "Recordatorio de tu turno - Taller Molina Henze"

            mensaje = (
                f"Hola {usuario.get_full_name() or usuario.username}.\n\n"
                "Te recordamos que mañana tenés un turno "
                "en Taller Molina Henze.\n\n"
                f"Fecha: {timezone.localtime(turno.fecha_turno):%d/%m/%Y}\n"
                f"Hora: {timezone.localtime(turno.fecha_turno):%H:%M}\n"
                f"Vehículo: {turno.vehiculo}\n"
                f"Patente: {turno.patente}\n"
                f"Servicio: {turno.servicio}\n\n"
                "Si necesitás modificar tu turno, contactate con el taller.\n\n"
                "¡Te esperamos!\n"
                "Taller Molina Henze - Servicio Integral"
            )

            try:
                enviado = enviar_correo_taller(
                    asunto=asunto,
                    mensaje=mensaje,
                    destinatarios=[usuario.email],
                    fail_silently=False,
                )

                if not enviado:
                    self.stderr.write(
                        self.style.ERROR(
                            f"El servidor no confirmó el envío del turno "
                            f"#{turno.pk}; se volverá a intentar en la "
                            "próxima ejecución."
                        )
                    )
                    continue

                turno.recordatorio_enviado = True
                turno.save(update_fields=["recordatorio_enviado"])
                enviados += 1

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Recordatorio enviado para el turno #{turno.pk}"
                    )
                )

            except Exception as error:
                self.stderr.write(
                    self.style.ERROR(
                        f"Error en turno #{turno.pk}: {error}"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Proceso terminado. Correos enviados: {enviados}"
            )
        )
