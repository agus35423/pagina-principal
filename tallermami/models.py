from django.db import models
from django.contrib.auth.models import User
from django.db.models import Q
from django.core.validators import (
    MaxValueValidator,
    MinValueValidator,
    RegexValidator,
)
import uuid

MARCAS_VEHICULOS = [
    ("Audi", "Audi"),
    ("BMW", "BMW"),
    ("Chevrolet", "Chevrolet"),
    ("Chrysler", "Chrysler"),
    ("Citroën", "Citroën"),
    ("Fiat", "Fiat"),
    ("Ford", "Ford"),
    ("Honda", "Honda"),
    ("Hyundai", "Hyundai"),
    ("Jeep", "Jeep"),
    ("Kia", "Kia"),
    ("Mercedes-Benz", "Mercedes-Benz"),
    ("Mitsubishi", "Mitsubishi"),
    ("Nissan", "Nissan"),
    ("Peugeot", "Peugeot"),
    ("RAM", "RAM"),
    ("Renault", "Renault"),
    ("Subaru", "Subaru"),
    ("Suzuki", "Suzuki"),
    ("Toyota", "Toyota"),
    ("Volkswagen", "Volkswagen"),
    ("Volvo", "Volvo"),
]

# ==========================================================
# TRABAJOS / SERVICIOS
# ==========================================================

class Trabajo(models.Model):

    nombre = models.CharField(
        max_length=150
    )

    descripcion = models.TextField(
        blank=True
    )

    precio_estimado = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )

    def __str__(self):

        return self.nombre

    class Meta:

        verbose_name = "Trabajo"

        verbose_name_plural = "Trabajos"

        ordering = ["nombre"]


# ==========================================================
# TRABAJADORES
# ==========================================================

class Trabajador(models.Model):

    nombre = models.CharField(
        max_length=100
    )

    apellido = models.CharField(
        max_length=100
    )

    especialidad = models.CharField(
        max_length=150,
        blank=True
    )

    telefono = models.CharField(
        max_length=30,
        blank=True
    )

    usuario = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="perfil_mecanico",
        verbose_name="Usuario asociado",
    )

    trabajos = models.ManyToManyField(
        Trabajo,
        blank=True,
        related_name="trabajadores",
        verbose_name="Trabajos asignados"
    )

    def __str__(self):

        return f"{self.nombre} {self.apellido}"

    class Meta:

        verbose_name = "Trabajador"
        verbose_name_plural = "Trabajadores"
        ordering = ["apellido", "nombre"]


class Mecanico(Trabajador):
    class Meta:
        proxy = True
        verbose_name = "Mecánico"
        verbose_name_plural = "Mecánicos"


# ==========================================================
# CLIENTES
# ==========================================================

class Cliente(models.Model):

    nombre = models.CharField(
        max_length=100
    )

    apellido = models.CharField(
        max_length=100
    )

    dni = models.CharField(
        max_length=8,
        blank=True,
        default="",
        verbose_name="DNI",
        validators=[
            RegexValidator(
                regex=r"^\d{7,8}$",
                message="El DNI debe tener 7 u 8 números.",
            )
        ],
    )

    acepta_whatsapp = models.BooleanField(
        default=False,
        verbose_name="Acepta recibir mensajes por WhatsApp",
    )

    email = models.EmailField()

    telefono = models.CharField(
        max_length=30
    )

    usuario = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="perfil_cliente",
        verbose_name="Usuario asociado",
    )

    def __str__(self):

        return f"{self.nombre} {self.apellido}"

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ["apellido", "nombre"]
        permissions = [
            (
                "acceder_panel_secretario",
                "Puede acceder al panel del secretario",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["dni"],
                condition=~Q(dni=""),
                name="cliente_dni_no_vacio_unico",
            ),
        ]


# ==========================================================
# VEHICULOS Y DISPONIBILIDAD
# ==========================================================

class Disponibilidad(models.Model):
    fecha = models.DateField()
    hora = models.TimeField()
    estado = models.BooleanField(
        default=True,
        verbose_name="Disponible",
    )

    def __str__(self):
        estado = "Disponible" if self.estado else "Ocupado"
        return f"{self.fecha:%d/%m/%Y} {self.hora:%H:%M} - {estado}"

    class Meta:
        verbose_name = "Disponibilidad"
        verbose_name_plural = "Disponibilidades"
        ordering = ["fecha", "hora"]
        constraints = [
            models.UniqueConstraint(
                fields=["fecha", "hora"],
                name="disponibilidad_fecha_hora_unica",
            ),
        ]


class Vehiculo(models.Model):
    marca = models.CharField(max_length=50)
    modelo = models.CharField(max_length=100)
    anio = models.PositiveSmallIntegerField(verbose_name="Año")
    patente = models.CharField(max_length=20, unique=True)
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name="vehiculos",
    )

    def __str__(self):
        return f"{self.marca} {self.modelo} ({self.anio}) - {self.patente}"

    class Meta:
        verbose_name = "Vehículo"
        verbose_name_plural = "Vehículos"
        ordering = ["patente"]


# ==========================================================
# TURNOS
# ==========================================================

class Turno(models.Model):

    ESTADOS = [

        ("pendiente", "Pendiente"),

        ("recibido", "Vehículo recibido"),

        ("diagnostico", "En diagnóstico"),

        ("reparacion", "En reparación"),

        ("esperando_repuesto", "Esperando repuesto"),

        ("finalizado", "Finalizado"),

        ("entregado", "Entregado"),

        ("cancelado", "Cancelado"),
        ("presupuesto_pendiente", "Presupuesto pendiente de aprobación"),
        ("presupuesto_aceptado", "Presupuesto aceptado"),
        ("presupuesto_rechazado", "Presupuesto rechazado"),
    ]


    # Usuario de Django
    usuario = models.ForeignKey(

        User,

        on_delete=models.CASCADE,

        related_name="turnos",

        null=True,

        blank=True
    )

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="turnos",
        verbose_name="Cliente",
    )

    vehiculo_asociado = models.ForeignKey(
        Vehiculo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="turnos",
        verbose_name="Vehículo registrado",
    )

    disponibilidad = models.OneToOneField(
        Disponibilidad,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="turno",
    )


    # Datos del vehículo
    vehiculo = models.CharField(
        max_length=150,
        verbose_name="Vehículo"
    )

    marca = models.CharField(
        max_length=30,
        choices=MARCAS_VEHICULOS,
        blank=True,
        default="",
        verbose_name="Marca",
    )

    modelo = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="Modelo",
    )

    anio = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name="Año",
    )


    patente = models.CharField(

        max_length=20,

        verbose_name="Patente"
    )


    # Servicio solicitado
    servicio = models.ForeignKey(

        Trabajo,

        on_delete=models.PROTECT,

        related_name="turnos",

        verbose_name="Servicio"
    )
        # Trabajador asignado
    # Trabajador asignado al turno
    trabajador = models.ForeignKey(

    Trabajador,

    on_delete=models.SET_NULL,

    null=True,

    blank=True,

    related_name="turnos_asignados",

    verbose_name="Trabajador asignado"
)

    # Fecha y hora
    fecha_turno = models.DateTimeField(

        verbose_name="Fecha y hora del turno"
    )


    # Estado
    estado = models.CharField(

        max_length=30,

        choices=ESTADOS,

        default="pendiente"
    )


    # Porcentaje de reparación
    porcentaje_reparacion = models.PositiveIntegerField(

        default=0,

        validators=[
            MinValueValidator(0),
            MaxValueValidator(100)
        ]
    )


    # Observaciones
    observaciones = models.TextField(

        blank=True
    )


    # Fecha de creación
    fecha_creacion = models.DateTimeField(

        auto_now_add=True
    )
        # Control del recordatorio por correo
    recordatorio_enviado = models.BooleanField(
        default=False,
        verbose_name="Recordatorio enviado"
    )

    def __str__(self):

        return (
            f"Turno #{self.id} - "
            f"{self.vehiculo} - "
            f"{self.patente}"
        )

    def save(self, *args, **kwargs):
        if self.marca and self.modelo and self.anio:
            self.vehiculo = f"{self.marca} {self.modelo} ({self.anio})"
        super().save(*args, **kwargs)


    class Meta:

        verbose_name = "Turno"

        verbose_name_plural = "Turnos"

        ordering = ["-fecha_turno"]
        # ==========================================================
# OFERTA DE TURNO ANTERIOR
# ==========================================================

class OfertaTurno(models.Model):

    ESTADOS = [
        ("pendiente", "Pendiente"),
        ("aceptada", "Aceptada"),
        ("rechazada", "Rechazada"),
        ("vencida", "Vencida"),
    ]

    turno_cliente = models.ForeignKey(
        Turno,
        on_delete=models.CASCADE,
        related_name="ofertas_recibidas"
    )

    fecha_disponible = models.DateTimeField()

    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default="pendiente"
    )

    token = models.UUIDField(
        unique=True,
        editable=False,
        default=uuid.uuid4
    )

    fecha_creacion = models.DateTimeField(
        auto_now_add=True
    )
       # Fecha de creación
    fecha_creacion = models.DateTimeField(
        auto_now_add=True
    )

    # Control del recordatorio por correo
    recordatorio_enviado = models.BooleanField(
        default=False,
        verbose_name="Recordatorio enviado"
    )
    def __str__(self):
        return (
            f"Oferta para turno #{self.turno_cliente.id} "
            f"- {self.fecha_disponible.strftime('%d/%m/%Y %H:%M')}"
        )

    class Meta:
        verbose_name = "Oferta de turno anterior"
        verbose_name_plural = "Ofertas de turnos anteriores"
        ordering = ["fecha_creacion"]

       # ==========================================================
# PRESUPUESTOS Y REPARACIONES
# ==========================================================

class Presupuesto(models.Model):

    ESTADOS = [
        ("pendiente", "Pendiente de respuesta"),
        ("aceptado", "Aceptado"),
        ("rechazado", "Rechazado"),
    ]

    turno = models.OneToOneField(
        Turno,
        on_delete=models.CASCADE,
        related_name="presupuesto",
        verbose_name="Turno"
    )

    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default="pendiente"
    )

    mano_obra_estimada = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)]
    )

    observaciones = models.TextField(blank=True)

    token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False
    )

    fecha_envio = models.DateTimeField(
        null=True,
        blank=True
    )

    fecha_respuesta = models.DateTimeField(
        null=True,
        blank=True
    )

    mano_obra_final = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)]
    )

    detalle_final = models.TextField(blank=True)

    fecha_finalizacion = models.DateTimeField(
        null=True,
        blank=True
    )

    final_enviado = models.BooleanField(default=False)

    def total_estimado(self):
        return sum(
            (item.subtotal() for item in self.repuestos_estimados.all()),
            start=0
        ) + self.mano_obra_estimada

    def total_final(self):
        return sum(
            (item.subtotal() for item in self.repuestos_utilizados.all()),
            start=0
        ) + self.mano_obra_final

    def __str__(self):
        return f"Presupuesto del turno #{self.turno_id}"

    class Meta:
        verbose_name = "Presupuesto"
        verbose_name_plural = "Presupuestos"


class RepuestoPresupuestado(models.Model):

    presupuesto = models.ForeignKey(
        Presupuesto,
        on_delete=models.CASCADE,
        related_name="repuestos_estimados"
    )

    nombre = models.CharField(max_length=150)

    cantidad = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)]
    )

    precio_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )

    def subtotal(self):
        return self.cantidad * self.precio_unitario

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Repuesto presupuestado"
        verbose_name_plural = "Repuestos presupuestados"


class RepuestoUtilizado(models.Model):

    presupuesto = models.ForeignKey(
        Presupuesto,
        on_delete=models.CASCADE,
        related_name="repuestos_utilizados"
    )

    orden_trabajo = models.ForeignKey(
        "OrdenTrabajo",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="repuestos_utilizados",
    )

    repuesto = models.ForeignKey(
        "Repuesto",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="usos",
    )

    fecha = models.DateField(
        null=True,
        blank=True,
    )

    nombre = models.CharField(max_length=150)

    cantidad = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)]
    )

    precio_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )

    def subtotal(self):
        return self.cantidad * self.precio_unitario

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Repuesto utilizado"
        verbose_name_plural = "Repuestos utilizados" 


# ==========================================================
# ORDENES, REPUESTOS Y TRABAJOS REALIZADOS
# ==========================================================

class OrdenTrabajo(models.Model):
    vehiculo = models.ForeignKey(
        Vehiculo,
        on_delete=models.PROTECT,
        related_name="ordenes_trabajo",
    )
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name="ordenes_trabajo",
    )
    servicio = models.ForeignKey(
        Trabajo,
        on_delete=models.PROTECT,
        related_name="ordenes_trabajo",
    )
    mecanico = models.ForeignKey(
        Trabajador,
        on_delete=models.PROTECT,
        related_name="ordenes_trabajo",
    )
    turno = models.OneToOneField(
        Turno,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orden_trabajo",
    )
    fecha_ingreso = models.DateField()
    estado = models.CharField(max_length=50)

    def __str__(self):
        return f"Orden de trabajo #{self.pk}"

    class Meta:
        verbose_name = "Orden de trabajo"
        verbose_name_plural = "Órdenes de trabajo"
        ordering = ["-fecha_ingreso", "-id"]


class Repuesto(models.Model):
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True)
    stock = models.PositiveIntegerField(default=0)
    precio = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Repuesto"
        verbose_name_plural = "Repuestos"
        ordering = ["nombre"]


class TrabajoRealizado(models.Model):
    orden_trabajo = models.ForeignKey(
        OrdenTrabajo,
        on_delete=models.CASCADE,
        related_name="trabajos_realizados",
    )
    descripcion = models.TextField()
    fecha = models.DateField()
    mecanico = models.ForeignKey(
        Trabajador,
        on_delete=models.PROTECT,
        related_name="trabajos_realizados",
    )

    def __str__(self):
        return f"Trabajo realizado #{self.pk}"

    class Meta:
        verbose_name = "Trabajo realizado"
        verbose_name_plural = "Trabajos realizados"
        ordering = ["-fecha", "-id"]


class PerfilUsuario(models.Model):
    ROLES = [
        ("cliente", "Cliente"),
        ("mecanico", "Mecánico"),
        ("administrador", "Administrador"),
    ]

    usuario = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="perfil_taller",
    )
    rol = models.CharField(max_length=20, choices=ROLES)

    def __str__(self):
        return f"{self.usuario.get_username()} - {self.get_rol_display()}"

    class Meta:
        verbose_name = "Perfil de usuario"
        verbose_name_plural = "Perfiles de usuario"