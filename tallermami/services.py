from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from .models import (
    Cliente,
    Disponibilidad,
    OrdenTrabajo,
    TrabajoRealizado,
    Turno,
    Vehiculo,
)


def registrar_trabajo_entregado(turno):
    if turno.estado != "entregado":
        return None

    with transaction.atomic():
        cliente = turno.cliente
        if cliente is None and turno.usuario_id:
            criterio_cliente = Q(usuario=turno.usuario)
            if turno.usuario.email:
                criterio_cliente |= Q(email__iexact=turno.usuario.email.strip())
            cliente = Cliente.objects.filter(criterio_cliente).first()

        vehiculo = turno.vehiculo_asociado
        if vehiculo is None:
            vehiculo = Vehiculo.objects.filter(
                patente__iexact=turno.patente.strip(),
            ).first()
        if (
            vehiculo is None
            and cliente is not None
            and turno.patente.strip()
            and turno.vehiculo.strip()
        ):
            vehiculo = Vehiculo.objects.create(
                marca=turno.marca or "No registrado",
                modelo=turno.modelo or turno.vehiculo.strip(),
                anio=turno.anio or 0,
                patente=turno.patente.strip().upper(),
                cliente=cliente,
            )

        faltantes = []
        if cliente is None:
            faltantes.append("asociar un cliente")
        if vehiculo is None:
            faltantes.append("asociar un vehículo registrado")
        if turno.trabajador_id is None:
            faltantes.append("asignar un trabajador")
        if faltantes:
            raise ValidationError(
                "No se puede registrar el trabajo entregado: "
                + ", ".join(faltantes)
                + "."
            )

        campos_turno = []
        if turno.cliente_id is None:
            turno.cliente = cliente
            campos_turno.append("cliente")
        if turno.vehiculo_asociado_id is None:
            turno.vehiculo_asociado = vehiculo
            campos_turno.append("vehiculo_asociado")
        if campos_turno:
            turno.save(update_fields=campos_turno)

        orden, creada = OrdenTrabajo.objects.get_or_create(
            turno=turno,
            defaults={
                "vehiculo": vehiculo,
                "cliente": cliente,
                "servicio": turno.servicio,
                "mecanico": turno.trabajador,
                "fecha_ingreso": timezone.localdate(turno.fecha_turno),
                "estado": "finalizado",
            },
        )
        if not creada:
            campos_orden = []
            if orden.vehiculo_id != vehiculo.pk:
                orden.vehiculo = vehiculo
                campos_orden.append("vehiculo")
            if orden.cliente_id != cliente.pk:
                orden.cliente = cliente
                campos_orden.append("cliente")
            if orden.servicio_id != turno.servicio_id:
                orden.servicio = turno.servicio
                campos_orden.append("servicio")
            if orden.estado != "finalizado":
                orden.estado = "finalizado"
                campos_orden.append("estado")
            if orden.mecanico_id != turno.trabajador_id:
                orden.mecanico = turno.trabajador
                campos_orden.append("mecanico")
            if campos_orden:
                orden.save(update_fields=campos_orden)

        prefijo_descripcion = (
            f"Trabajo entregado del turno #{turno.pk}:"
        )
        trabajo_realizado = TrabajoRealizado.objects.filter(
            orden_trabajo=orden,
            descripcion__startswith=prefijo_descripcion,
        ).first()
        if trabajo_realizado is None:
            trabajo_realizado = TrabajoRealizado.objects.create(
                orden_trabajo=orden,
                descripcion=(
                    f"{prefijo_descripcion} {turno.servicio.nombre}"
                ),
                fecha=timezone.localdate(),
                mecanico=turno.trabajador,
            )
        elif trabajo_realizado.mecanico_id != turno.trabajador_id:
            trabajo_realizado.mecanico = turno.trabajador
            trabajo_realizado.save(update_fields=["mecanico"])
        return trabajo_realizado


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
