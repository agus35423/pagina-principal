from datetime import date, datetime, time, timedelta
import json
import re
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django import forms
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from unittest.mock import patch
from tallermami.management.commands import enviar_recordatorios

from .forms import ClienteForm, SolicitarTurnoForm, TurnoAdminForm, TurnoForm
from .models import (
    Cliente,
    Disponibilidad,
    OrdenTrabajo,
    OfertaTurno,
    PerfilUsuario,
    Trabajador,
    Trabajo,
    TrabajoRealizado,
    Turno,
    Vehiculo,
)
from .utils import (
    enviar_correo_taller,
    generar_pdf_turno,
    normalizar_telefono_whatsapp,
)


class AdministracionJefeTallerTests(TestCase):
    def setUp(self):
        self.group = Group.objects.create(name="Jefe de taller")
        self.jefe = get_user_model().objects.create_user(
            username="jefe_admin_test",
            password="Test-password-973-Orange",
        )
        self.jefe.groups.add(self.group)
        self.client.force_login(self.jefe)

    def test_panel_muestra_modelos_de_taller_y_autenticacion(self):
        response = self.client.get(reverse("jefe_admin_inicio"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Administración completa")
        self.assertContains(response, "Trabajos")
        self.assertContains(response, "Usuarios")
        self.assertContains(response, "Grupos")

    def test_panel_muestra_estadisticas_de_clientes_y_trabajadores(self):
        cliente_frecuente = Cliente.objects.create(
            nombre="Ana",
            apellido="Frecuente",
            email="ana@example.com",
            telefono="111",
        )
        otro_cliente = Cliente.objects.create(
            nombre="Luis",
            apellido="Cliente",
            email="luis@example.com",
            telefono="222",
        )
        trabajo = Trabajo.objects.create(nombre="Mantenimiento")
        mecanico_destacado = Trabajador.objects.create(
            nombre="Marta",
            apellido="Destacada",
        )
        otro_mecanico = Trabajador.objects.create(
            nombre="Juan",
            apellido="Mecanico",
        )

        for numero, cliente in enumerate(
            [cliente_frecuente, cliente_frecuente, otro_cliente],
            start=1,
        ):
            vehiculo = Vehiculo.objects.create(
                marca="Ford",
                modelo="Focus",
                anio=2018,
                patente=f"AB123C{numero}",
                cliente=cliente,
            )
            orden = OrdenTrabajo.objects.create(
                vehiculo=vehiculo,
                cliente=cliente,
                servicio=trabajo,
                mecanico=mecanico_destacado,
                fecha_ingreso=date.today(),
                estado="finalizado",
            )
            TrabajoRealizado.objects.create(
                orden_trabajo=orden,
                descripcion=f"Trabajo {numero}",
                fecha=date.today(),
                mecanico=(
                    mecanico_destacado if numero < 3 else otro_mecanico
                ),
            )
            if numero == 1:
                TrabajoRealizado.objects.create(
                    orden_trabajo=orden,
                    descripcion="Segundo trabajo",
                    fecha=date.today(),
                    mecanico=mecanico_destacado,
                )

        response = self.client.get(reverse("jefe_admin_inicio"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["clientes_recurrentes"][0],
            cliente_frecuente,
        )
        self.assertEqual(
            response.context["clientes_recurrentes"][0].cantidad_trabajos,
            2,
        )
        self.assertEqual(
            response.context["trabajadores_destacados"][0],
            mecanico_destacado,
        )
        self.assertEqual(
            response.context["trabajadores_destacados"][0].cantidad_trabajos,
            3,
        )
        self.assertContains(response, "Clientes más recurrentes")
        self.assertContains(response, "Trabajadores con más trabajos")

    def test_panel_principal_enlaza_a_la_administracion(self):
        response = self.client.get(reverse("vista_jefe_taller"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("jefe_admin_inicio"))

    def test_todos_los_modelos_registrados_tienen_lista_y_formulario(self):
        for model in admin.site._registry:
            app_label = model._meta.app_label
            model_name = model._meta.model_name
            with self.subTest(model=model._meta.label):
                lista = self.client.get(
                    reverse(
                        "jefe_admin_lista",
                        args=[app_label, model_name],
                    )
                )
                formulario = self.client.get(
                    reverse(
                        "jefe_admin_nuevo",
                        args=[app_label, model_name],
                    )
                )
                self.assertEqual(lista.status_code, 200)
                self.assertEqual(formulario.status_code, 200)

    def test_lista_muestra_acciones_del_admin(self):
        turnos = self.client.get(
            reverse("jefe_admin_lista", args=["tallermami", "turno"])
        )
        presupuestos = self.client.get(
            reverse("jefe_admin_lista", args=["tallermami", "presupuesto"])
        )

        self.assertContains(turnos, "Exportar turnos seleccionados a Excel")
        self.assertContains(presupuestos, "Enviar presupuesto al cliente")

    def test_lista_de_turnos_muestra_diseno_y_resumen_especializados(self):
        trabajo = Trabajo.objects.create(nombre="Diagnóstico")
        turno = Turno.objects.create(
            vehiculo="Ford Focus (2018)",
            marca="Ford",
            modelo="Focus",
            anio=2018,
            patente="AB123CD",
            servicio=trabajo,
            fecha_turno=timezone.now() + timedelta(days=2),
            estado="reparacion",
            porcentaje_reparacion=45,
        )

        response = self.client.get(
            reverse("jefe_admin_lista", args=["tallermami", "turno"])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Gestión de turnos")
        self.assertContains(response, "Turnos registrados")
        self.assertContains(response, "Estado / avance")
        self.assertContains(response, "En reparación")
        self.assertContains(response, 'class="repair-progress-car"')
        self.assertContains(response, 'aria-valuenow="45"')
        self.assertContains(response, "45% de avance")
        self.assertContains(
            response,
            reverse(
                "jefe_admin_editar",
                args=["tallermami", "turno", turno.pk],
            ),
        )

    def test_formulario_admin_del_jefe_ofrece_selector_de_marca_y_anio(self):
        response = self.client.get(
            reverse(
                "jefe_admin_nuevo",
                args=["tallermami", "turno"],
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="marca"')
        self.assertContains(response, '<select name="anio"', html=False)

    def test_jefe_puede_cambiar_estado_del_turno_desde_edicion(self):
        trabajo = Trabajo.objects.create(nombre="Revisión")
        fecha_turno = timezone.now() + timedelta(days=5)
        turno = Turno.objects.create(
            vehiculo="Toyota Corolla (2020)",
            marca="Toyota",
            modelo="Corolla",
            anio=2020,
            patente="AB123CD",
            servicio=trabajo,
            fecha_turno=fecha_turno,
        )
        editar_url = reverse(
            "jefe_admin_editar",
            args=["tallermami", "turno", turno.pk],
        )

        response = self.client.get(editar_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="estado"', html=False)
        self.assertContains(response, "Estado del turno")
        self.assertIn(
            ("esperando_repuesto", "Esperando repuesto"),
            response.context["form"].fields["estado"].choices,
        )
        self.assertContains(
            response,
            '<option value="esperando_repuesto">',
            html=False,
        )

        response = self.client.post(
            editar_url,
            {
                "usuario": "",
                "marca": "Toyota",
                "modelo": "Corolla",
                "anio": "2020",
                "patente": "AB123CD",
                "servicio": str(trabajo.pk),
                "trabajador": "",
                "fecha_turno": fecha_turno.strftime("%Y-%m-%dT%H:%M"),
                "estado": "reparacion",
                "porcentaje_reparacion": "0",
                "observaciones": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        turno.refresh_from_db()
        self.assertEqual(turno.estado, "reparacion")

    def test_panel_de_turnos_del_jefe_enlaza_a_editar_cada_turno(self):
        trabajo = Trabajo.objects.create(nombre="Revisión")
        turno = Turno.objects.create(
            vehiculo="Ford Focus (2018)",
            marca="Ford",
            modelo="Focus",
            anio=2018,
            patente="AB123CD",
            servicio=trabajo,
            fecha_turno=timezone.now() + timedelta(days=5),
        )

        response = self.client.get(reverse("jefe_turnos"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Editar")
        self.assertContains(
            response,
            reverse(
                "jefe_admin_editar",
                args=["tallermami", "turno", turno.pk],
            ),
        )

    def test_jefe_puede_crear_editar_y_eliminar_trabajo(self):
        lista_url = reverse(
            "jefe_admin_lista",
            args=["tallermami", "trabajo"],
        )
        crear_url = reverse(
            "jefe_admin_nuevo",
            args=["tallermami", "trabajo"],
        )

        response = self.client.post(
            crear_url,
            {"nombre": "Cambio de aceite", "descripcion": "Servicio"},
        )
        self.assertRedirects(response, lista_url)
        trabajo = Trabajo.objects.get(nombre="Cambio de aceite")

        editar_url = reverse(
            "jefe_admin_editar",
            args=["tallermami", "trabajo", trabajo.pk],
        )
        response = self.client.post(
            editar_url,
            {
                "nombre": "Cambio de aceite completo",
                "descripcion": "Servicio actualizado",
                "precio_estimado": "",
            },
        )
        self.assertRedirects(response, lista_url)
        trabajo.refresh_from_db()
        self.assertEqual(trabajo.nombre, "Cambio de aceite completo")

        eliminar_url = reverse(
            "jefe_admin_eliminar",
            args=["tallermami", "trabajo", trabajo.pk],
        )
        response = self.client.post(eliminar_url)
        self.assertRedirects(response, lista_url)
        self.assertFalse(Trabajo.objects.filter(pk=trabajo.pk).exists())

    def test_jefe_puede_crear_usuarios_y_cambiar_su_contrasena(self):
        crear_usuario_url = reverse(
            "jefe_admin_nuevo",
            args=["auth", "user"],
        )
        response = self.client.post(
            crear_usuario_url,
            {
                "username": "nuevo_usuario_admin",
                "password1": "Strong-password-862-Blue",
                "password2": "Strong-password-862-Blue",
            },
        )
        lista_url = reverse("jefe_admin_lista", args=["auth", "user"])
        self.assertRedirects(response, lista_url)
        usuario = get_user_model().objects.get(
            username="nuevo_usuario_admin",
        )

        cambiar_contrasena_url = reverse(
            "jefe_admin_contrasena",
            args=[usuario.pk],
        )
        response = self.client.post(
            cambiar_contrasena_url,
            {
                "password1": "Another-strong-password-398-Green",
                "password2": "Another-strong-password-398-Green",
            },
        )
        self.assertRedirects(response, lista_url)
        usuario.refresh_from_db()
        self.assertTrue(
            usuario.check_password("Another-strong-password-398-Green"),
        )


class SeleccionVehiculoTests(TestCase):
    def setUp(self):
        self.trabajo = Trabajo.objects.create(
            nombre="Mantenimiento general",
        )

    def test_formulario_de_turno_ofrece_marca_y_anio_como_selectores(self):
        form = SolicitarTurnoForm()

        self.assertIsInstance(form.fields["marca"].widget, forms.Select)
        self.assertIsInstance(form.fields["anio"].widget, forms.Select)
        self.assertIn("Toyota", dict(form.fields["marca"].choices))
        self.assertIn(2020, [value for value, _label in form.fields["anio"].choices])

    def test_turno_guarda_marca_modelo_anio_y_mantiene_vehiculo(self):
        form = SolicitarTurnoForm(
            data={
                "nombre": "Ana",
                "apellido": "Pérez",
                "dni": "30123456",
                "email": "ana@example.com",
                "telefono": "3511234567",
                "marca": "Toyota",
                "modelo": "Corolla",
                "anio": "2020",
                "patente": "ab 123 cd",
                "servicio": self.trabajo.pk,
                "fecha_turno": "2030-05-10T09:00",
                "observaciones": "",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        turno = form.save()
        self.assertEqual(turno.marca, "Toyota")
        self.assertEqual(turno.modelo, "Corolla")
        self.assertEqual(turno.anio, 2020)
        self.assertEqual(turno.vehiculo, "Toyota Corolla (2020)")

    def test_formulario_exige_dni_numerico_de_7_u_8_digitos(self):
        form = SolicitarTurnoForm(
            data={
                "nombre": "Ana",
                "apellido": "Pérez",
                "dni": "30.123.456",
                "email": "ana@example.com",
                "telefono": "3511234567",
                "marca": "Toyota",
                "modelo": "Corolla",
                "anio": "2020",
                "patente": "AB123CD",
                "servicio": self.trabajo.pk,
                "fecha_turno": "2030-05-10T09:00",
                "observaciones": "",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["dni"], "30123456")

        invalid_form = SolicitarTurnoForm(
            data={
            **form.data,
            "dni": "1234",
            }
        )
        self.assertFalse(invalid_form.is_valid())
        self.assertIn("dni", invalid_form.errors)

    def test_cliente_admin_form_incluye_dni(self):
        self.assertIn("dni", ClienteForm().fields)

    def test_selector_vehiculo_esta_disponible_en_edicion_y_admin(self):
        for form_class in (TurnoForm, TurnoAdminForm):
            with self.subTest(form=form_class.__name__):
                form = form_class()
                self.assertIsInstance(form.fields["marca"].widget, forms.Select)
                self.assertIsInstance(form.fields["anio"].widget, forms.Select)


class ReservaYAvanceTurnoTests(TestCase):
    def setUp(self):
        self.trabajo = Trabajo.objects.create(nombre="Reparación")

    def test_solicitud_muestra_error_si_email_no_es_valido(self):
        response = self.client.post(
            reverse("solicitar_turno"),
            {
                "nombre": "María",
                "apellido": "Gómez",
                "dni": "30123456",
                "email": "mariaexample.com",
                "telefono": "3511234567",
                "marca": "Ford",
                "modelo": "Focus",
                "anio": "2018",
                "patente": "AB123CD",
                "servicio": self.trabajo.pk,
                "fecha_turno": "2030-05-10T09:00",
                "observaciones": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Ingresá un correo válido, por ejemplo nombre@gmail.com.",
        )
        self.assertFalse(Turno.objects.exists())

    def test_cancelar_turno_libera_su_disponibilidad(self):
        usuario = get_user_model().objects.create_user(
            username="cliente_cancelacion",
        )
        fecha_turno = timezone.now() + timedelta(days=2)
        disponibilidad = Disponibilidad.objects.create(
            fecha=fecha_turno.date(),
            hora=fecha_turno.time().replace(tzinfo=None),
            estado=False,
        )
        turno = Turno.objects.create(
            usuario=usuario,
            vehiculo="Ford Focus (2018)",
            marca="Ford",
            modelo="Focus",
            anio=2018,
            patente="AB123CD",
            servicio=self.trabajo,
            fecha_turno=fecha_turno,
            disponibilidad=disponibilidad,
        )
        self.client.force_login(usuario)

        response = self.client.post(
            reverse("cancelar_turno", args=[turno.pk]),
        )

        turno.refresh_from_db()
        disponibilidad.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(turno.estado, "cancelado")
        self.assertIsNone(turno.disponibilidad_id)
        self.assertTrue(disponibilidad.estado)

    def test_editar_turno_mueve_la_reserva_de_disponibilidad(self):
        secretaria_group = Group.objects.create(name="Secretario")
        secretaria = get_user_model().objects.create_user(
            username="secretaria_edita_fecha",
        )
        secretaria.groups.add(secretaria_group)
        fecha_anterior = timezone.make_aware(
            datetime(2032, 5, 10, 9, 0),
        )
        fecha_nueva = timezone.make_aware(
            datetime(2032, 5, 11, 10, 0),
        )
        disponibilidad_anterior = Disponibilidad.objects.create(
            fecha=date(2032, 5, 10),
            hora=time(9, 0),
            estado=False,
        )
        turno = Turno.objects.create(
            vehiculo="Ford Focus (2018)",
            marca="Ford",
            modelo="Focus",
            anio=2018,
            patente="AB123CD",
            servicio=self.trabajo,
            fecha_turno=fecha_anterior,
            disponibilidad=disponibilidad_anterior,
        )
        self.client.force_login(secretaria)

        response = self.client.post(
            reverse("secretario_turno_editar", args=[turno.pk]),
            {
                "marca": "Ford",
                "modelo": "Focus",
                "anio": "2018",
                "patente": "AB123CD",
                "servicio": self.trabajo.pk,
                "trabajador": "",
                "fecha_turno": "2032-05-11T10:00",
                "estado": "pendiente",
                "porcentaje_reparacion": "0",
                "observaciones": "",
            },
        )

        turno.refresh_from_db()
        disponibilidad_anterior.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertTrue(disponibilidad_anterior.estado)
        self.assertEqual(turno.fecha_turno, fecha_nueva)
        self.assertEqual(turno.disponibilidad.fecha, date(2032, 5, 11))
        self.assertFalse(turno.disponibilidad.estado)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    )
    def test_oferta_solo_cambia_el_turno_despues_de_confirmar(self):
        usuario = get_user_model().objects.create_user(
            username="cliente_oferta",
            email="cliente-oferta@example.com",
        )
        fecha_actual = timezone.make_aware(
            datetime(2032, 6, 20, 12, 0),
        )
        fecha_ofrecida = timezone.make_aware(
            datetime(2032, 6, 10, 12, 0),
        )
        disponibilidad_actual = Disponibilidad.objects.create(
            fecha=date(2032, 6, 20),
            hora=time(12, 0),
            estado=False,
        )
        turno = Turno.objects.create(
            usuario=usuario,
            vehiculo="Ford Focus (2018)",
            marca="Ford",
            modelo="Focus",
            anio=2018,
            patente="AB123CD",
            servicio=self.trabajo,
            fecha_turno=fecha_actual,
            disponibilidad=disponibilidad_actual,
        )
        oferta = OfertaTurno.objects.create(
            turno_cliente=turno,
            fecha_disponible=fecha_ofrecida,
        )
        url = reverse("aceptar_oferta_turno", args=[oferta.token])

        response = self.client.get(url)
        turno.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(turno.fecha_turno, fecha_actual)

        response = self.client.post(url, {"confirmar": "si"})

        turno.refresh_from_db()
        disponibilidad_actual.refresh_from_db()
        oferta.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(turno.fecha_turno, fecha_ofrecida)
        self.assertTrue(disponibilidad_actual.estado)
        self.assertEqual(oferta.estado, "aceptada")
        self.assertFalse(turno.disponibilidad.estado)

    def test_panel_secretario_muestra_datos_de_cliente_y_vehiculo(self):
        secretario_group = Group.objects.create(name="Secretario")
        secretario = get_user_model().objects.create_user(
            username="secretario_datos",
            password="Test-password-973-Orange",
        )
        secretario.groups.add(secretario_group)
        usuario = get_user_model().objects.create_user(
            username="cliente_datos",
            first_name="Ana",
            last_name="Pérez",
            email="ana@example.com",
        )
        Cliente.objects.create(
            nombre="Ana",
            apellido="Pérez",
            dni="30123456",
            email="ana@example.com",
            telefono="3511234567",
        )
        Turno.objects.create(
            usuario=usuario,
            vehiculo="Toyota Corolla (2020)",
            marca="Toyota",
            modelo="Corolla",
            anio=2020,
            patente="AB123CD",
            servicio=self.trabajo,
            fecha_turno=timezone.now() + timedelta(days=1),
            porcentaje_reparacion=35,
        )
        self.client.force_login(secretario)

        response = self.client.get(reverse("secretario_turnos"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "DNI")
        self.assertContains(response, "30123456")
        self.assertContains(response, "Toyota")
        self.assertContains(response, "Corolla")
        self.assertContains(response, "35%")

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    )
    @patch("tallermami.views.guardar_turno_en_excel")
    def test_solicitud_guarda_dni_y_envia_confirmacion(
        self,
        guardar_excel,
    ):
        response = self.client.post(
            reverse("solicitar_turno"),
            {
                "nombre": "María",
                "apellido": "Gómez",
                "dni": "30.123.456",
                "email": "maria@example.com",
                "telefono": "3511234567",
                "marca": "Ford",
                "modelo": "Focus",
                "anio": "2018",
                "patente": "AB123CD",
                "servicio": self.trabajo.pk,
                "fecha_turno": "2030-05-10T09:00",
                "observaciones": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        cliente = Cliente.objects.get(email="maria@example.com")
        self.assertEqual(cliente.dni, "30123456")
        turno = Turno.objects.get(cliente=cliente)
        self.assertEqual(turno.vehiculo_asociado.patente, "AB123CD")
        self.assertEqual(turno.vehiculo_asociado.cliente, cliente)
        self.assertEqual(turno.disponibilidad.fecha, date(2030, 5, 10))
        self.assertEqual(turno.disponibilidad.hora, time(9, 0))
        self.assertFalse(turno.disponibilidad.estado)
        self.assertEqual(cliente.usuario, turno.usuario)
        self.assertEqual(len(mail.outbox), 1)
        self.assertNotIn("DNI: 30123456", mail.outbox[0].body)
        guardar_excel.assert_called_once()


class WhatsAppTests(TestCase):
    def setUp(self):
        self.servicio = Trabajo.objects.create(nombre="Diagnóstico")
        self.usuario = get_user_model().objects.create_user(
            username="cliente_whatsapp",
            email="whatsapp@example.com",
        )
        self.cliente = Cliente.objects.create(
            nombre="Ana",
            apellido="Pérez",
            email=self.usuario.email,
            telefono="3511234567",
            acepta_whatsapp=True,
        )
        self.turno = Turno.objects.create(
            usuario=self.usuario,
            vehiculo="Ford Focus (2018)",
            marca="Ford",
            modelo="Focus",
            anio=2018,
            patente="AB123CD",
            servicio=self.servicio,
            fecha_turno=timezone.now() + timedelta(days=10),
        )
        self.jefe = get_user_model().objects.create_user(
            username="secretario_whatsapp",
        )
        self.jefe.groups.add(Group.objects.create(name="Secretario"))
        self.client.force_login(self.jefe)

    def test_normaliza_telefonos_argentinos_a_formato_whatsapp(self):
        self.assertEqual(
            normalizar_telefono_whatsapp("351 123-4567"),
            "5493511234567",
        )
        self.assertEqual(
            normalizar_telefono_whatsapp("+54 9 351 123 4567"),
            "5493511234567",
        )

    @override_settings(
        WHATSAPP_ACCESS_TOKEN="token-de-prueba",
        WHATSAPP_PHONE_NUMBER_ID="12345",
        WHATSAPP_TEMPLATE_NAME="taller_mensaje",
        WHATSAPP_TEMPLATE_LANGUAGE="es_AR",
        PUBLIC_SITE_URL="https://tallermolina.example",
    )
    @patch("tallermami.utils.urlopen")
    def test_solicitud_envia_plantilla_si_hay_consentimiento(
        self,
        mock_urlopen,
    ):
        respuesta = mock_urlopen.return_value.__enter__.return_value
        respuesta.read.return_value = b'{"messages":[{"id":"wamid.test"}]}'

        with patch("tallermami.views.guardar_turno_en_excel"):
            response = self.client.post(
                reverse("solicitar_turno"),
                {
                    "nombre": "Ana",
                    "apellido": "Pérez",
                    "dni": "30123456",
                    "email": "whatsapp@example.com",
                    "telefono": "3511234567",
                    "acepta_whatsapp": "on",
                    "marca": "Ford",
                    "modelo": "Focus",
                    "anio": "2018",
                    "patente": "AB123CD",
                    "servicio": self.servicio.pk,
                    "fecha_turno": "2030-05-10T09:00",
                    "observaciones": "",
                },
            )

        self.assertEqual(response.status_code, 302)
        self.cliente.refresh_from_db()
        self.assertTrue(self.cliente.acepta_whatsapp)
        request = mock_urlopen.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["to"], "5493511234567")
        self.assertEqual(
            payload["template"]["components"][0]["parameters"][1]["text"],
            "https://tallermolina.example/",
        )

    @override_settings(
        WHATSAPP_ACCESS_TOKEN="token-de-prueba",
        WHATSAPP_PHONE_NUMBER_ID="12345",
    )
    @patch("tallermami.utils.urlopen")
    def test_secretario_puede_enviar_mensaje_con_consentimiento(
        self,
        mock_urlopen,
    ):
        respuesta = mock_urlopen.return_value.__enter__.return_value
        respuesta.read.return_value = b'{"messages":[{"id":"wamid.test"}]}'

        response = self.client.post(
            reverse(
                "secretario_turno_whatsapp",
                args=[self.turno.pk],
            ),
            {"mensaje": "Tu vehículo está listo."},
        )

        self.assertEqual(response.status_code, 302)
        mock_urlopen.assert_called_once()

    @patch("tallermami.utils.urlopen")
    def test_secretario_no_envia_si_no_hay_consentimiento(
        self,
        mock_urlopen,
    ):
        self.cliente.acepta_whatsapp = False
        self.cliente.save(update_fields=["acepta_whatsapp"])

        response = self.client.post(
            reverse(
                "secretario_turno_whatsapp",
                args=[self.turno.pk],
            ),
            {"mensaje": "Mensaje no autorizado."},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "no autorizó")
        mock_urlopen.assert_not_called()


class PanelSecretarioTests(TestCase):
    def test_panel_muestra_accesos_de_gestion_con_nueva_presentacion(self):
        secretaria = get_user_model().objects.create_user(
            username="secretaria_panel",
        )
        secretaria.groups.add(Group.objects.create(name="Secretario"))
        self.client.force_login(secretaria)

        response = self.client.get(reverse("vista_secretario"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Panel del Secretario")
        self.assertContains(response, "secretary-dashboard-hero")
        self.assertContains(response, reverse("secretario_clientes"))
        self.assertContains(response, reverse("secretario_presupuestos"))
        self.assertContains(response, reverse("secretario_turnos"))


class PasswordResetTests(TestCase):
    def test_login_shows_styled_fields_and_password_recovery_link(self):
        response = self.client.get(reverse("login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "¿Olvidaste tu contraseña?")
        self.assertContains(response, reverse("password_reset"))
        self.assertContains(
            response,
            'class="form-control"',
            html=False,
        )

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        ALLOWED_HOSTS=["127.0.0.1", "testserver"],
    )
    def test_password_reset_email_completes_the_reset_flow(self):
        user = get_user_model().objects.create_user(
            username="recuperar_clave",
            email="recuperar@example.com",
            password="Original-strong-password-729-Blue",
        )

        response = self.client.post(
            reverse("password_reset"),
            {"email": user.email},
            HTTP_HOST="127.0.0.1:8000",
        )

        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(len(mail.outbox[0].alternatives), 1)
        self.assertIn("Crear nueva contraseña", mail.outbox[0].alternatives[0][0])
        self.assertIn("Taller Molina Henze", mail.outbox[0].alternatives[0][0])
        self.assertIn(
            "http://127.0.0.1:8000/password-reset/",
            mail.outbox[0].alternatives[0][0],
        )
        self.assertIn("http://127.0.0.1:8000/password-reset/", mail.outbox[0].body)
        reset_path = re.search(
            r"http://127\.0\.0\.1:8000(/password-reset/[^\s]+)",
            mail.outbox[0].body,
        ).group(1)

        response = self.client.get(
            reset_path,
            HTTP_HOST="127.0.0.1:8000",
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "```")
        reset_path = response.redirect_chain[-1][0]

        response = self.client.post(
            reset_path,
            {
                "new_password1": "Another-strong-password-398-Green",
                "new_password2": "Another-strong-password-398-Green",
            },
            HTTP_HOST="127.0.0.1:8000",
        )

        self.assertRedirects(response, reverse("password_reset_complete"))
        user.refresh_from_db()
        self.assertTrue(
            user.check_password("Another-strong-password-398-Green")
        )

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend"
    )
    def test_password_reset_done_explains_development_email_delivery(self):
        response = self.client.get(reverse("password_reset_done"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "se imprime en la consola")
        self.assertNotContains(response, "```")


class EmailBrandingTests(TestCase):
    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        PUBLIC_SITE_URL="https://tallermolina.example",
    )
    def test_correo_taller_incluye_version_html_de_marca(self):
        enviado = enviar_correo_taller(
            asunto="Actualización del turno",
            mensaje="Hola, tu turno está listo.",
            destinatarios=["cliente@example.com"],
        )

        self.assertEqual(enviado, 1)
        correo = mail.outbox[-1]
        self.assertEqual(len(correo.alternatives), 1)
        html = correo.alternatives[0][0]
        self.assertIn("Taller Molina Henze", html)
        self.assertIn("https://tallermolina.example/", html)
        self.assertIn("#0d2b4d", html)
        self.assertIn("tu turno está listo", html)


class AvanceTurnoTests(TestCase):
    def setUp(self):
        self.trabajo = Trabajo.objects.create(nombre="Reparación")

    def test_administrador_staff_accede_a_vistas_de_jefe_y_secretario(self):
        administrador = get_user_model().objects.create_user(
            username="administrador_vistas",
            is_staff=True,
        )
        self.client.force_login(administrador)

        jefe_response = self.client.get(reverse("vista_jefe_taller"))
        secretario_response = self.client.get(reverse("vista_secretario"))

        self.assertEqual(jefe_response.status_code, 200)
        self.assertEqual(secretario_response.status_code, 200)

    def test_cada_rol_ve_el_acceso_a_su_panel_despues_de_iniciar_sesion(self):
        usuario_jefe = get_user_model().objects.create_user(
            username="jefe_con_panel",
            password="ClaveSegura-123",
        )
        usuario_jefe.groups.add(Group.objects.create(name="Jefe de taller"))

        usuario_secretario = get_user_model().objects.create_user(
            username="secretario_con_panel",
            password="ClaveSegura-123",
        )
        usuario_secretario.groups.add(
            Group.objects.create(name="Secretario")
        )

        usuario_mecanico = get_user_model().objects.create_user(
            username="mecanico_con_panel",
            password="ClaveSegura-123",
        )
        PerfilUsuario.objects.create(
            usuario=usuario_mecanico,
            rol="mecanico",
        )
        Trabajador.objects.create(
            nombre="Mecánico",
            apellido="Panel",
            usuario=usuario_mecanico,
        )

        accesos = (
            (usuario_jefe, "Panel del jefe de taller", "vista_jefe_taller"),
            (
                usuario_secretario,
                "Panel del secretario",
                "vista_secretario",
            ),
            (usuario_mecanico, "Panel del mecánico", "panel_mecanico"),
        )
        for usuario, etiqueta, vista in accesos:
            with self.subTest(rol=etiqueta):
                response = self.client.post(
                    reverse("login"),
                    {
                        "username": usuario.username,
                        "password": "ClaveSegura-123",
                    },
                )
                self.assertRedirects(response, reverse("inicio"))
                inicio = self.client.get(reverse("inicio"))
                self.assertContains(inicio, etiqueta)
                self.assertContains(inicio, reverse(vista))
                self.client.logout()

    def test_usuario_con_rol_administrador_accede_al_admin_django_al_iniciar_sesion(
        self,
    ):
        administrador = get_user_model().objects.create_user(
            username="administrador_rol",
            password="ClaveSegura-123",
        )
        PerfilUsuario.objects.create(
            usuario=administrador,
            rol="administrador",
        )

        response = self.client.post(
            reverse("login"),
            {
                "username": "administrador_rol",
                "password": "ClaveSegura-123",
            },
        )

        self.assertRedirects(response, reverse("inicio"))
        administrador.refresh_from_db()
        self.assertTrue(administrador.is_staff)
        self.assertTrue(administrador.has_perm("tallermami.change_trabajo"))
        self.assertEqual(
            self.client.get(reverse("admin:index")).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                reverse("admin:tallermami_trabajo_changelist")
            ).status_code,
            200,
        )
        for vista in (
            "vista_jefe_taller",
            "vista_secretario",
            "panel_mecanico",
            "jefe_admin_inicio",
        ):
            with self.subTest(vista=vista):
                self.assertEqual(
                    self.client.get(reverse(vista)).status_code,
                    200,
                )
        self.assertContains(
            self.client.get(reverse("inicio")),
            "Administración Django",
        )

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    )
    def test_administrador_sin_mecanico_accede_y_actualiza_cualquier_turno(self):
        administrador = get_user_model().objects.create_user(
            username="administrador_mecanico",
            is_staff=True,
        )
        mecanico = get_user_model().objects.create_user(
            username="mecanico_asignado",
        )
        turno = self.crear_turno_asignado(mecanico, "EE555EE")
        self.client.force_login(administrador)

        response = self.client.get(reverse("panel_mecanico"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "EE555EE")

        response = self.client.post(
            reverse("mecanico_actualizar_avance", args=[turno.pk]),
            {"porcentaje_reparacion": "75"},
        )

        turno.refresh_from_db()
        self.assertRedirects(response, reverse("panel_mecanico"))
        self.assertEqual(turno.porcentaje_reparacion, 75)

    def test_usuario_sin_trabajador_asociado_recibe_indicacion(self):
        usuario = get_user_model().objects.create_user(
            username="mecanico_sin_vincular",
        )
        self.client.force_login(usuario)

        response = self.client.get(reverse("panel_mecanico"), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Tu cuenta todavía no está asociada a un mecánico.",
        )

    def crear_turno_asignado(self, usuario_mecanico, patente):
        mecanico = Trabajador.objects.create(
            nombre="Juan",
            apellido="Mecánico",
            usuario=usuario_mecanico,
        )
        cliente = get_user_model().objects.create_user(
            username=f"cliente_{patente}",
            email=f"{patente.lower()}@example.com",
        )
        turno = Turno.objects.create(
            usuario=cliente,
            trabajador=mecanico,
            vehiculo="Ford Focus (2018)",
            marca="Ford",
            modelo="Focus",
            anio=2018,
            patente=patente,
            servicio=self.trabajo,
            fecha_turno=timezone.now() + timedelta(days=3),
            porcentaje_reparacion=15,
            observaciones="Revisar frenos",
        )
        return turno

    def test_panel_mecanico_muestra_solo_sus_turnos(self):
        usuario_mecanico = get_user_model().objects.create_user(
            username="mecanico_panel",
        )
        self.crear_turno_asignado(usuario_mecanico, "AA111AA")
        otro_mecanico = get_user_model().objects.create_user(
            username="otro_mecanico",
        )
        self.crear_turno_asignado(otro_mecanico, "BB222BB")
        self.client.force_login(usuario_mecanico)

        response = self.client.get(reverse("panel_mecanico"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "AA111AA")
        self.assertNotContains(response, "BB222BB")

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    )
    def test_mecanico_actualiza_solo_avance_y_notifica_al_cliente(self):
        usuario_mecanico = get_user_model().objects.create_user(
            username="mecanico_avance",
        )
        turno = self.crear_turno_asignado(usuario_mecanico, "CC333CC")
        self.client.force_login(usuario_mecanico)

        response = self.client.post(
            reverse("mecanico_actualizar_avance", args=[turno.pk]),
            {"porcentaje_reparacion": "40"},
        )

        turno.refresh_from_db()
        self.assertRedirects(response, reverse("panel_mecanico"))
        self.assertEqual(turno.porcentaje_reparacion, 40)
        self.assertEqual(turno.estado, "pendiente")
        self.assertEqual(turno.observaciones, "Revisar frenos")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("del 15% al 40%", mail.outbox[0].body)
        estado_cliente = self.client.post(
            reverse("estado_reparacion"),
            {"patente": turno.patente},
        )
        self.assertContains(estado_cliente, "40%")

    def test_mecanico_no_puede_modificar_turno_no_asignado(self):
        usuario_mecanico = get_user_model().objects.create_user(
            username="mecanico_no_asignado",
        )
        Trabajador.objects.create(
            nombre="Pedro",
            apellido="Mecánico",
            usuario=usuario_mecanico,
        )
        turno = self.crear_turno_asignado(
            get_user_model().objects.create_user(username="dueño_turno"),
            "DD444DD",
        )
        self.client.force_login(usuario_mecanico)

        response = self.client.post(
            reverse("mecanico_actualizar_avance", args=[turno.pk]),
            {"porcentaje_reparacion": "90"},
        )

        turno.refresh_from_db()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(turno.porcentaje_reparacion, 15)


    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        WHATSAPP_ACCESS_TOKEN="token-de-prueba",
        WHATSAPP_PHONE_NUMBER_ID="12345",
    )
    @patch("tallermami.utils.urlopen")
    def test_cambio_de_porcentaje_envia_aviso_al_cliente(
        self,
        mock_urlopen,
    ):
        respuesta = mock_urlopen.return_value.__enter__.return_value
        respuesta.read.return_value = b'{"messages":[{"id":"wamid.test"}]}'
        secretario_group = Group.objects.create(name="Secretario")
        jefe_group = Group.objects.create(name="Jefe de taller")
        secretario = get_user_model().objects.create_user(
            username="secretario_avance",
            email="cliente@example.com",
            password="Test-password-973-Orange",
        )
        secretario.groups.add(secretario_group)
        secretario.groups.add(jefe_group)
        Cliente.objects.create(
            nombre="Cliente",
            apellido="Prueba",
            email="cliente@example.com",
            telefono="3511234567",
            acepta_whatsapp=True,
        )
        self.client.force_login(secretario)
        fecha_turno = timezone.now() + timedelta(days=30)
        fecha_turno_form = fecha_turno.strftime("%Y-%m-%dT%H:%M")
        turno = Turno.objects.create(
            usuario=secretario,
            vehiculo="Toyota Corolla (2020)",
            marca="Toyota",
            modelo="Corolla",
            anio=2020,
            patente="AB123CD",
            servicio=self.trabajo,
            fecha_turno=fecha_turno,
            porcentaje_reparacion=20,
        )
        url = reverse("secretario_turno_editar", args=[turno.pk])
        datos = {
            "marca": "Toyota",
            "modelo": "Corolla",
            "anio": "2020",
            "patente": "AB123CD",
            "servicio": str(self.trabajo.pk),
            "trabajador": "",
            "fecha_turno": fecha_turno_form,
            "estado": "reparacion",
            "porcentaje_reparacion": "45",
            "observaciones": "",
        }

        response = self.client.post(url, datos)
        self.assertEqual(response.status_code, 302)
        turno.refresh_from_db()
        self.assertEqual(turno.porcentaje_reparacion, 45)
        self.assertEqual(
            len(mail.outbox),
            1,
            [str(message) for message in response.wsgi_request._messages],
        )
        self.assertIn("del 20% al 45%", mail.outbox[0].body)
        self.assertIn("patente=AB123CD", mail.outbox[0].body)

        self.client.post(url, datos)
        self.assertEqual(len(mail.outbox), 1)

        admin_url = reverse(
            "jefe_admin_editar",
            args=["tallermami", "turno", turno.pk],
        )
        response = self.client.post(
            admin_url,
            {
                "usuario": str(secretario.pk),
                "marca": "Toyota",
                "modelo": "Corolla",
                "anio": "2020",
                "patente": "AB123CD",
                "servicio": str(self.trabajo.pk),
                "trabajador": "",
                "fecha_turno": fecha_turno_form,
                "estado": "reparacion",
                "porcentaje_reparacion": "60",
                "observaciones": "",
            },
        )
        self.assertEqual(
            response.status_code,
            302,
            (
                response.context["form"].errors
                if response.context
                else response.status_code
            ),
        )
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn("del 45% al 60%", mail.outbox[1].body)
        self.assertEqual(mock_urlopen.call_count, 2)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        PUBLIC_SITE_URL="https://tallermolinahenze.example",
    )
    @patch("tallermami.management.commands.enviar_recordatorios.timezone.localdate")
    def test_recordatorio_de_manana_se_envia_una_sola_vez_y_con_link(
        self,
        localdate,
    ):
        manana = date.today() + timedelta(days=1)
        localdate.return_value = manana - timedelta(days=1)
        usuario = get_user_model().objects.create_user(
            username="cliente_recordatorio",
            email="cliente@example.com",
        )
        turno = Turno.objects.create(
            usuario=usuario,
            vehiculo="Ford Focus (2018)",
            marca="Ford",
            modelo="Focus",
            anio=2018,
            patente="AB123CD",
            servicio=self.trabajo,
            fecha_turno=timezone.make_aware(
                datetime.combine(manana, time(10, 30)),
            ),
        )
        turno_cancelado = Turno.objects.create(
            usuario=usuario,
            vehiculo="Ford Ka (2015)",
            marca="Ford",
            modelo="Ka",
            anio=2015,
            patente="CD456EF",
            servicio=self.trabajo,
            fecha_turno=timezone.make_aware(
                datetime.combine(manana, time(11, 30)),
            ),
            estado="cancelado",
        )

        call_command("enviar_recordatorios", stdout=None)
        turno.refresh_from_db()
        turno_cancelado.refresh_from_db()

        self.assertTrue(turno.recordatorio_enviado)
        self.assertFalse(turno_cancelado.recordatorio_enviado)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("mañana tenés un turno", mail.outbox[0].body)
        self.assertIn(
            "https://tallermolinahenze.example/",
            mail.outbox[0].body,
        )
        self.assertIn("Taller Molina Henze", mail.outbox[0].alternatives[0][0])
        call_command("enviar_recordatorios", stdout=None)
        self.assertEqual(len(mail.outbox), 1)


class DescargaComprobantePdfTests(TestCase):
    def test_descarga_pdf_generada_con_datos_y_texto_especial(self):
        usuario = get_user_model().objects.create_user(
            username="cliente_pdf",
            email="cliente@example.com",
            first_name="José",
            last_name="Pérez",
        )
        trabajo = Trabajo.objects.create(nombre="Revisión y diagnóstico")
        turno = Turno.objects.create(
            usuario=usuario,
            vehiculo="Ford Focus (2020)",
            marca="Ford",
            modelo="Focus",
            anio=2020,
            patente="AB123CD",
            servicio=trabajo,
            fecha_turno=timezone.now() + timedelta(days=2),
            porcentaje_reparacion=35,
            observaciones="Revisión <rápida> & cambio de aceite\nListo.",
        )

        response = self.client.get(reverse("descargar_pdf", args=[turno.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn(
            f'filename="comprobante_turno_{turno.pk}.pdf"',
            response["Content-Disposition"],
        )
        self.assertTrue(response.content.startswith(b"%PDF-"))
        self.assertGreater(len(response.content), 500)

    def test_generador_devuelve_un_pdf_descargable(self):
        trabajo = Trabajo.objects.create(nombre="Mantenimiento")
        turno = Turno.objects.create(
            vehiculo="Toyota Corolla",
            marca="Toyota",
            modelo="Corolla",
            anio=2021,
            patente="AA123BB",
            servicio=trabajo,
            fecha_turno=timezone.now() + timedelta(days=1),
            porcentaje_reparacion=0,
        )

        response = generar_pdf_turno(turno)

        self.assertTrue(response.content.startswith(b"%PDF-"))
        self.assertEqual(response["Content-Type"], "application/pdf")
