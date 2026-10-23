from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Disponibilidad, Turno


def guardar_turno_con_disponibilidad(turno, fecha_turno):
    with transaction.atomic():
        turno_actual = Turno.objects.select_for_update().get(pk=turno.pk)
        fecha_local = (
            timezone.localtime(fecha_turno)
            if timezone.is_aware(fecha_turno)
            else fecha_turno
        )
        fecha = fecha_local.date()
        hora = fecha_local.time().replace(tzinfo=None)
        disponibilidad_anterior = turno_actual.disponibilidad
        fecha_anterior_local = (
            timezone.localtime(turno_actual.fecha_turno)
            if timezone.is_aware(turno_actual.fecha_turno)
            else turno_actual.fecha_turno
        )
        misma_hora_anterior = (
            fecha_anterior_local.date() == fecha
            and fecha_anterior_local.time().replace(tzinfo=None) == hora
        )

        hay_otro_turno = (
            Turno.objects.filter(fecha_turno=fecha_turno)
            .exclude(pk=turno.pk)
            .exclude(estado="cancelado")
            .exists()
        )
        if hay_otro_turno:
            raise ValidationError(
                "Ese horario ya está reservado por otro turno."
            )

        misma_disponibilidad = (
            disponibilidad_anterior is not None
            and disponibilidad_anterior.fecha == fecha
            and disponibilidad_anterior.hora == hora
        )
        disponibilidad = (
            Disponibilidad.objects.select_for_update()
            .filter(fecha=fecha, hora=hora)
            .first()
        )

        if disponibilidad is None:
            try:
                with transaction.atomic():
                    disponibilidad = Disponibilidad.objects.create(
                        fecha=fecha,
                        hora=hora,
                        estado=False,
                    )
            except IntegrityError:
                disponibilidad = (
                    Disponibilidad.objects.select_for_update()
                    .get(fecha=fecha, hora=hora)
                )
                if not disponibilidad.estado and not misma_disponibilidad:
                    raise ValidationError(
                        "Ese horario ya no está disponible."
                    )
        elif (
            not disponibilidad.estado
            and not misma_disponibilidad
            and not misma_hora_anterior
        ):
            raise ValidationError(
                "Ese horario ya no está disponible."
            )
        else:
            disponibilidad.estado = False
            disponibilidad.save(update_fields=["estado"])

        if (
            disponibilidad_anterior
            and disponibilidad_anterior.pk != disponibilidad.pk
        ):
            disponibilidad_anterior.estado = True
            disponibilidad_anterior.save(update_fields=["estado"])

        turno.fecha_turno = fecha_turno
        turno.disponibilidad = disponibilidad
        turno.save(update_fields=["fecha_turno", "disponibilidad"])
        return turno
