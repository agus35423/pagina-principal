
from django.conf import settings
from django.urls import path
from django.contrib.auth import views as auth_views

from . import views


class TallerPasswordResetDoneView(auth_views.PasswordResetDoneView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["email_backend_console"] = settings.EMAIL_BACKEND.endswith(
            "console.EmailBackend"
        )
        return context


urlpatterns = [
    # ======================================================
    # INICIO
    # ======================================================

    path("", views.inicio, name="inicio"),
    path("jefe/", views.panel_jefe_compat, name="jefe"),

    # ======================================================
    # PANELES
    # ======================================================
    path(
        "mecanico/",
        views.panel_mecanico,
        name="panel_mecanico",
    ),
    path(
        "mecanico/turnos/<int:turno_id>/avance/",
        views.mecanico_actualizar_avance,
        name="mecanico_actualizar_avance",
    ),
    path(
    "secretario/presupuestos/nuevo/",
    views.secretario_presupuesto_nuevo,
    name="secretario_presupuesto_nuevo",
),
    path(
    "secretario/turnos/<int:turno_id>/editar/",
    views.secretario_turno_editar,
    name="secretario_turno_editar",
    ),
    path(
        "secretario/turnos/<int:turno_id>/whatsapp/",
        views.secretario_turno_whatsapp,
        name="secretario_turno_whatsapp",
    ),

    path(
    "secretario/clientes/nuevo/",
    views.secretario_cliente_nuevo,
    name="secretario_cliente_nuevo",
    ),
    path(
    "secretario/clientes/<int:cliente_id>/editar/",
    views.secretario_cliente_editar,
    name="secretario_cliente_editar",
),
    path(
        "jefe-taller/",
        views.vista_jefe_taller,
        name="vista_jefe_taller",
    ),

    # Alias para compatibilidad con enlaces anteriores.
    path(
        "jefe_taller/",
        views.vista_jefe_taller,
        name="vista_jefe_taller_guion_bajo",
    ),

    path(
        "jefe-taller/trabajos/",
        views.jefe_trabajos,
        name="jefe_trabajos",
    ),
    path(
        "jefe-taller/trabajadores/",
        views.jefe_trabajadores,
        name="jefe_trabajadores",
    ),
    path(
        "jefe-taller/clientes/",
        views.jefe_clientes,
        name="jefe_clientes",
    ),
    path(
        "jefe-taller/turnos/",
        views.jefe_turnos,
        name="jefe_turnos",
    ),
    path(
        "jefe-taller/administracion/",
        views.jefe_admin_inicio,
        name="jefe_admin_inicio",
    ),
    path(
        "jefe-taller/administracion/<str:app_label>/<str:model_name>/",
        views.jefe_admin_lista,
        name="jefe_admin_lista",
    ),
    path(
        "jefe-taller/administracion/<str:app_label>/<str:model_name>/nuevo/",
        views.jefe_admin_formulario,
        name="jefe_admin_nuevo",
    ),
    path(
        "jefe-taller/administracion/<str:app_label>/<str:model_name>/<str:object_id>/editar/",
        views.jefe_admin_formulario,
        name="jefe_admin_editar",
    ),
    path(
        "jefe-taller/administracion/<str:app_label>/<str:model_name>/<str:object_id>/eliminar/",
        views.jefe_admin_eliminar,
        name="jefe_admin_eliminar",
    ),
    path(
        "jefe-taller/administracion/usuarios/<int:object_id>/contrasena/",
        views.jefe_admin_contrasena,
        name="jefe_admin_contrasena",
    ),

    path(
        "secretario/",
        views.vista_secretario,
        name="vista_secretario",
    ),
    path(
    "secretario/presupuestos/",
    views.secretario_presupuestos,
    name="secretario_presupuestos",
    ),
    path(
        "secretario/clientes/",
        views.secretario_clientes,
        name="secretario_clientes",
    ),
    path(
        "secretario/turnos/",
        views.secretario_turnos,
        name="secretario_turnos",
    ),
    
    path(
    "secretario/presupuestos/nuevo/",
    views.secretario_presupuesto_nuevo,
    name="secretario_presupuesto_nuevo",
    ),
    
    path(
    "secretario/presupuestos/<int:presupuesto_id>/final/",
    views.secretario_presupuesto_final,
    name="secretario_presupuesto_final",
),


    # ======================================================
    # AUTENTICACIÓN
    # ======================================================

    path("login/", views.login_view, name="login"),
    path("registro/", views.registro, name="registro"),
    path("logout/", views.logout_view, name="logout"),

    # ======================================================
    # RECUPERACIÓN DE CONTRASEÑA
    # ======================================================

    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="tallermami/password_reset.html",
            email_template_name="tallermami/password_reset_email.txt",
            html_email_template_name=(
                "tallermami/password_reset_email.html"
            ),
            subject_template_name="tallermami/password_reset_subject.txt",
        ),
        name="password_reset",
    ),
    path(
        "password-reset/enviado/",
        TallerPasswordResetDoneView.as_view(
            template_name="tallermami/password_reset_done.html",
        ),
        name="password_reset_done",
    ),
    path(
        "password-reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="tallermami/password_reset_confirm.html"
        ),
        name="password_reset_confirm",
    ),
    path(
        "password-reset/completo/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="tallermami/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),

    # ======================================================
    # TURNOS
    # ======================================================

    path(
        "solicitar-turno/",
        views.solicitar_turno,
        name="solicitar_turno",
    ),
    path(
        "turno-exitoso/<int:turno_id>/",
        views.turno_exitoso,
        name="turno_exitoso",
    ),
    path("mis-turnos/", views.mis_turnos, name="mis_turnos"),
    path(
        "turnos/cancelar/<int:turno_id>/",
        views.cancelar_turno,
        name="cancelar_turno",
    ),

    # ======================================================
    # OFERTAS PARA ADELANTAR TURNOS
    # ======================================================

    path(
        "oferta-turno/<uuid:token>/",
        views.aceptar_oferta_turno,
        name="aceptar_oferta_turno",
    ),

    # ======================================================
    # ESTADO DEL VEHÍCULO
    # ======================================================

    path(
        "estado-reparacion/",
        views.estado_reparacion,
        name="estado_reparacion",
    ),

    # ======================================================
    # PDF Y PRESUPUESTOS
    # ======================================================

    path(
        "descargar-pdf/<int:turno_id>/",
        views.descargar_pdf,
        name="descargar_pdf",
    ),
    path(
        "presupuesto/<uuid:token>/<str:decision>/",
        views.responder_presupuesto,
        name="responder_presupuesto",
    ),

    # ======================================================
    # EXCEL
    # ======================================================

    path(
        "exportar-excel/",
        views.exportar_excel,
        name="exportar_excel",
    ),
    path(
        "descargar-excel-turnos/",
        views.descargar_excel_turnos,
        name="descargar_excel_turnos",
    ),
]
