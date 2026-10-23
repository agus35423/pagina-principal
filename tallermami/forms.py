from datetime import date

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.forms import inlineformset_factory
from django.utils import timezone

from .models import (
    Cliente,
    Disponibilidad,
    MARCAS_VEHICULOS,
    Presupuesto,
    RepuestoPresupuestado,
    Turno,
    Trabajo,
)


def opciones_anios_vehiculo():
    anio_actual = date.today().year
    return [
        ("", "Seleccioná un año"),
        *[
            (anio, str(anio))
            for anio in range(anio_actual, 1949, -1)
        ],
    ]


def campos_vehiculo_formulario():
    return {
        "marca": forms.ChoiceField(
            choices=[("", "Seleccioná una marca"), *MARCAS_VEHICULOS],
            label="Marca",
            widget=forms.Select(attrs={"class": "form-select"}),
        ),
        "modelo": forms.CharField(
            max_length=100,
            label="Modelo",
            widget=forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Ej: Corolla",
                }
            ),
        ),
        "anio": forms.TypedChoiceField(
            choices=opciones_anios_vehiculo,
            coerce=int,
            label="Año",
            widget=forms.Select(attrs={"class": "form-select"}),
        ),
    }


def validar_fecha_y_hora_turno(fecha_turno, instance=None):
    if not fecha_turno:
        return

    turnos_del_dia = Turno.objects.filter(
        fecha_turno__date=fecha_turno.date()
    ).exclude(estado="cancelado")
    turnos_del_horario = Turno.objects.filter(
        fecha_turno=fecha_turno
    ).exclude(estado="cancelado")
    disponibilidad_actual_id = None
    mismo_horario_actual = False

    if instance and instance.pk:
        turnos_del_dia = turnos_del_dia.exclude(pk=instance.pk)
        turnos_del_horario = turnos_del_horario.exclude(pk=instance.pk)
        disponibilidad_actual_id = instance.disponibilidad_id
        fecha_actual = instance.fecha_turno
        if fecha_actual:
            fecha_actual_local = (
                timezone.localtime(fecha_actual)
                if timezone.is_aware(fecha_actual)
                else fecha_actual
            )
            fecha_solicitada_local = (
                timezone.localtime(fecha_turno)
                if timezone.is_aware(fecha_turno)
                else fecha_turno
            )
            mismo_horario_actual = (
                fecha_actual_local.date() == fecha_solicitada_local.date()
                and fecha_actual_local.time().replace(tzinfo=None)
                == fecha_solicitada_local.time().replace(tzinfo=None)
            )

    if turnos_del_dia.count() >= 3:
        raise forms.ValidationError(
            "Esta fecha ya está completa. "
            "Hay 3 turnos activos para ese día. "
            "Por favor, seleccioná otra fecha."
        )

    if turnos_del_horario.exists():
        raise forms.ValidationError(
            "Ese horario ya está reservado. Seleccioná otro."
        )

    fecha_local = (
        timezone.localtime(fecha_turno)
        if timezone.is_aware(fecha_turno)
        else fecha_turno
    )
    disponibilidad = Disponibilidad.objects.filter(
        fecha=fecha_local.date(),
        hora=fecha_local.time().replace(tzinfo=None),
        estado=False,
    ).first()
    if (
        disponibilidad
        and disponibilidad.pk != disponibilidad_actual_id
        and not mismo_horario_actual
    ):
        raise forms.ValidationError(
            "Ese horario ya no está disponible. Seleccioná otro."
        )


# ==========================================================
# FORMULARIO PARA SOLICITAR TURNO
# ==========================================================

class SolicitarTurnoForm(forms.ModelForm):
    marca = campos_vehiculo_formulario()["marca"]
    modelo = campos_vehiculo_formulario()["modelo"]
    anio = campos_vehiculo_formulario()["anio"]

    nombre = forms.CharField(
        max_length=100,
        label="Nombre",
    )

    apellido = forms.CharField(
        max_length=100,
        label="Apellido",
    )

    email = forms.EmailField(
        label="Correo electrónico",
        error_messages={
            "required": "Ingresá tu correo electrónico.",
            "invalid": (
                "Ingresá un correo válido, por ejemplo "
                "nombre@gmail.com."
            ),
        },
    )

    telefono = forms.CharField(
        max_length=30,
        label="Teléfono",
    )

    dni = forms.CharField(
        max_length=10,
        label="DNI",
        help_text="Ingresá los 7 u 8 números del DNI, sin puntos.",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "inputmode": "numeric",
                "placeholder": "Ej: 30123456",
            }
        ),
    )

    acepta_whatsapp = forms.BooleanField(
        required=False,
        label="Acepto recibir confirmaciones y actualizaciones por WhatsApp.",
        widget=forms.CheckboxInput(
            attrs={"class": "form-check-input"}
        ),
    )

    class Meta:
        model = Turno

        fields = [
            "marca",
            "modelo",
            "anio",
            "patente",
            "servicio",
            "fecha_turno",
            "observaciones",
        ]

        widgets = {
            "patente": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Ej: AB123CD",
                "style": "text-transform: uppercase;",
            }),

            "servicio": forms.Select(attrs={
                "class": "form-select",
            }),

            "fecha_turno": forms.DateTimeInput(attrs={
                "class": "form-control",
                "type": "datetime-local",
            }),

            "observaciones": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": (
                    "Contanos qué problema tiene el vehículo..."
                ),
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["servicio"].queryset = Trabajo.objects.all()

        self.fields["nombre"].widget.attrs.update({
            "class": "form-control",
            "placeholder": "Tu nombre",
        })

        self.fields["apellido"].widget.attrs.update({
            "class": "form-control",
            "placeholder": "Tu apellido",
        })

        self.fields["email"].widget.attrs.update({
            "class": "form-control",
            "type": "email",
            "placeholder": "nombre@gmail.com",
        })

        self.fields["telefono"].widget.attrs.update({
            "class": "form-control",
            "placeholder": "351...",
        })

    def clean_dni(self):
        dni_ingresado = self.cleaned_data["dni"].strip()
        dni = "".join(dni_ingresado.split()).replace(".", "")
        if not dni.isdecimal() or len(dni) not in (7, 8):
            raise forms.ValidationError(
                "El DNI debe tener 7 u 8 números."
            )
        return dni

    def clean(self):
        cleaned_data = super().clean()
        dni = cleaned_data.get("dni")
        email = cleaned_data.get("email")
        if dni and email and Cliente.objects.filter(dni=dni).exclude(
            email__iexact=email
        ).exists():
            self.add_error(
                "dni",
                "Ya existe un cliente registrado con ese DNI.",
            )
        return cleaned_data

    def clean_patente(self):
        patente = self.cleaned_data["patente"]
        return patente.upper().replace(" ", "").replace("-", "")

    def clean_fecha_turno(self):
        fecha = self.cleaned_data.get("fecha_turno")
        validar_fecha_y_hora_turno(fecha, self.instance)
        return fecha


class AvanceReparacionForm(forms.Form):
    porcentaje_reparacion = forms.IntegerField(
        label="Avance de reparación",
        min_value=0,
        max_value=100,
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "min": 0,
                "max": 100,
                "step": 1,
            }
        ),
        error_messages={
            "required": "Ingresá el porcentaje de avance.",
            "min_value": "El avance no puede ser menor que 0%.",
            "max_value": "El avance no puede superar el 100%.",
            "invalid": "Ingresá un porcentaje entero entre 0 y 100.",
        },
    )


class EnviarWhatsAppForm(forms.Form):
    mensaje = forms.CharField(
        label="Mensaje",
        max_length=900,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 5,
                "maxlength": 900,
            }
        ),
    )


# ==========================================================
# FORMULARIO DE REGISTRO
# ==========================================================

class RegistroForm(UserCreationForm):

    email = forms.EmailField(
        required=True,
        label="Correo electrónico",
    )

    class Meta:
        model = User

        fields = [
            "username",
            "email",
            "password1",
            "password2",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            field.widget.attrs.update({
                "class": "form-control",
            })

# ==========================================================
# FORMULARIO PARA CREAR CLIENTES
# ==========================================================

class ClienteForm(forms.ModelForm):
    dni = forms.CharField(
        max_length=10,
        required=False,
        label="DNI",
        help_text="Ingresá 7 u 8 números; podés escribirlos con puntos.",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "inputmode": "numeric",
            }
        ),
    )

    class Meta:
        model = Cliente
        fields = [
            "nombre",
            "apellido",
            "dni",
            "email",
            "telefono",
            "acepta_whatsapp",
        ]
        widgets = {
            "nombre": forms.TextInput(attrs={
                "class": "form-control",
            }),
            "apellido": forms.TextInput(attrs={
                "class": "form-control",
            }),
            "dni": forms.TextInput(attrs={
                "class": "form-control",
                "inputmode": "numeric",
            }),
            "email": forms.EmailInput(attrs={
                "class": "form-control",
            }),
            "telefono": forms.TextInput(attrs={
                "class": "form-control",
            }),
        }

    def clean_dni(self):
        dni_ingresado = self.cleaned_data.get("dni", "").strip()
        if not dni_ingresado:
            return ""
        dni = "".join(dni_ingresado.split()).replace(".", "")
        if not dni.isdecimal() or len(dni) not in (7, 8):
            raise forms.ValidationError(
                "El DNI debe tener 7 u 8 números."
            )
        return dni


# ==========================================================
# FORMULARIO PARA CREAR PRESUPUESTOS
# ==========================================================

class PresupuestoForm(forms.ModelForm):
    class Meta:
        model = Presupuesto
        fields = [
            "turno",
            "mano_obra_estimada",
            "observaciones",
        ]
        widgets = {
            "turno": forms.Select(attrs={
                "class": "form-select",
            }),
            "mano_obra_estimada": forms.NumberInput(attrs={
                "class": "form-control",
                "min": "0",
                "step": "0.01",
            }),
            "observaciones": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 4,
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["turno"].queryset = (
            Turno.objects
            .exclude(estado="cancelado")
            .filter(presupuesto__isnull=True)
            .select_related("usuario", "servicio")
            .order_by("-fecha_turno")
        )


# ==========================================================
# FORMULARIO PARA REPUESTOS PRESUPUESTADOS
# ==========================================================

class RepuestoPresupuestadoForm(forms.ModelForm):
    class Meta:
        model = RepuestoPresupuestado
        fields = ["nombre", "cantidad", "precio_unitario"]
        widgets = {
            "nombre": forms.TextInput(attrs={
                "class": "form-control",
            }),
            "cantidad": forms.NumberInput(attrs={
                "class": "form-control",
                "min": "1",
            }),
            "precio_unitario": forms.NumberInput(attrs={
                "class": "form-control",
                "min": "0",
                "step": "0.01",
            }),
        }


RepuestosPresupuestadosFormSet = inlineformset_factory(
    Presupuesto,
    RepuestoPresupuestado,
    form=RepuestoPresupuestadoForm,
    extra=1,
    can_delete=True,
)
# ==========================================================
# FORMULARIO PARA EDITAR TURNOS DESDE EL PANEL
# ==========================================================

class TurnoForm(forms.ModelForm):
    marca = campos_vehiculo_formulario()["marca"]
    modelo = campos_vehiculo_formulario()["modelo"]
    anio = campos_vehiculo_formulario()["anio"]

    class Meta:
        model = Turno

        fields = [
            "marca",
            "modelo",
            "anio",
            "patente",
            "servicio",
            "trabajador",
            "fecha_turno",
            "estado",
            "porcentaje_reparacion",
            "observaciones",
        ]

        widgets = {
            "patente": forms.TextInput(attrs={
                "class": "form-control",
                "style": "text-transform: uppercase;",
            }),

            "servicio": forms.Select(attrs={
                "class": "form-select",
            }),

            "trabajador": forms.Select(attrs={
                "class": "form-select",
            }),

            "fecha_turno": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M",
                attrs={
                    "class": "form-control",
                    "type": "datetime-local",
                },
            ),

            "estado": forms.Select(attrs={
                "class": "form-select",
            }),

            "porcentaje_reparacion": forms.NumberInput(attrs={
                "class": "form-control",
                "min": 0,
                "max": 100,
            }),

            "observaciones": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 4,
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and not (
            self.instance.marca
            and self.instance.modelo
            and self.instance.anio
        ):
            for field_name in ("marca", "modelo", "anio"):
                self.fields[field_name].required = False

    def clean_patente(self):
        patente = self.cleaned_data.get("patente", "")
        return patente.upper().replace(" ", "").replace("-", "")

    def clean_fecha_turno(self):
        fecha = self.cleaned_data.get("fecha_turno")
        validar_fecha_y_hora_turno(fecha, self.instance)
        return fecha


class TurnoAdminForm(TurnoForm):
    class Meta(TurnoForm.Meta):
        fields = "__all__"
    
from django import forms
from .models import Presupuesto, Turno


class PresupuestoForm(forms.ModelForm):
    class Meta:
        model = Presupuesto
        fields = [
            "turno",
            "mano_obra_estimada",
            "observaciones",
        ]

        widgets = {
            "turno": forms.Select(
                attrs={"class": "form-select"}
            ),
            "mano_obra_estimada": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": "0",
                    "step": "0.01",
                    "placeholder": "Ej.: 85000.00",
                }
            ),
            "observaciones": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Detalle del trabajo que se realizará...",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["turno"].queryset = (
            Turno.objects
            .filter(presupuesto__isnull=True)
            .order_by("-fecha_turno")
        )

        self.fields["turno"].label = "Turno del cliente"
        self.fields["mano_obra_estimada"].label = "Mano de obra estimada"
        self.fields["observaciones"].label = "Observaciones"

# ==========================================================
# FORMULARIOS PARA EL PRESUPUESTO FINAL
# ==========================================================

from django.forms import inlineformset_factory

from .models import (
    Presupuesto,
    RepuestoUtilizado,
)


class RepuestoUtilizadoForm(forms.ModelForm):
    class Meta:
        model = RepuestoUtilizado
        fields = ["nombre", "cantidad", "precio_unitario"]

        widgets = {
            "nombre": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Nombre del repuesto",
            }),
            "cantidad": forms.NumberInput(attrs={
                "class": "form-control",
                "min": "1",
                "step": "1",
            }),
            "precio_unitario": forms.NumberInput(attrs={
                "class": "form-control",
                "min": "0",
                "step": "0.01",
            }),
        }


RepuestosUtilizadosFormSet = inlineformset_factory(
    Presupuesto,
    RepuestoUtilizado,
    form=RepuestoUtilizadoForm,
    extra=1,
    can_delete=True,
)


class PresupuestoFinalForm(forms.ModelForm):
    class Meta:
        model = Presupuesto
        fields = [
            "mano_obra_final",
            "detalle_final",
        ]

        widgets = {
            "mano_obra_final": forms.NumberInput(attrs={
                "class": "form-control",
                "min": "0",
                "step": "0.01",
            }),
            "detalle_final": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 5,
                "placeholder": (
                    "Describí el trabajo realizado, "
                    "las reparaciones y las observaciones finales."
                ),
            }),
        }
