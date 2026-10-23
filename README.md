# Taller Molina Henze

Proyecto web del taller mecánico **Taller Molina Henze – Servicio Integral**.

## Pendientes

- Mejorar el diseño visual de la página.
- Revisar y quitar los repuestos de la base de datos, según los requerimientos del proyecto.

## Recordatorios y correos

Los correos del taller usan el diseño de la página y enlazan al sitio. En producción, configurá la variable de entorno `PUBLIC_SITE_URL` con la dirección pública del sitio (por ejemplo, `https://www.tudominio.com`).

El recordatorio de turnos consulta cada día los turnos del día siguiente y evita enviar dos veces el mismo aviso. Para que salga automáticamente, programá la ejecución diaria de:

```powershell
python .\manage.py enviar_recordatorios
```

Configurá la tarea con el directorio de trabajo de la aplicación como carpeta de inicio. En Windows se puede hacer desde el Programador de tareas; también se puede ejecutar diariamente desde cron o el scheduler del entorno de producción.

La recuperación de contraseña usa la configuración SMTP. Definí `EMAIL_HOST_USER` y `EMAIL_HOST_PASSWORD` con la cuenta de envío. Para Gmail, usá una contraseña de aplicación, no la contraseña de acceso habitual. Se pueden cambiar `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS` y `EMAIL_USE_SSL` según el proveedor.

Si esas credenciales no están configuradas en modo desarrollo, Django imprime el correo con el enlace de recuperación en la consola del servidor. En producción, configurá el SMTP antes de desplegar.

## Mensajes por WhatsApp

La integración utiliza WhatsApp Business Cloud API. Configurá estas variables de entorno en el servidor y no guardes el token en el código:

- `WHATSAPP_ACCESS_TOKEN`: token de acceso de Meta.
- `WHATSAPP_PHONE_NUMBER_ID`: identificador del número de WhatsApp Business.
- `WHATSAPP_GRAPH_API_VERSION`: versión de Graph API (por defecto `v22.0`).
- `WHATSAPP_TEMPLATE_NAME`: plantilla aprobada (por defecto `taller_mensaje`).
- `WHATSAPP_TEMPLATE_LANGUAGE`: idioma de la plantilla (por defecto `es_AR`).

En Meta, aprobá una plantilla con dos variables de cuerpo, en este orden:

- `{{1}}`: mensaje.
- `{{2}}`: enlace público del taller.

El nombre y el idioma deben coincidir con las variables configuradas. Las confirmaciones de turno y novedades de reparación se envían automáticamente solo si el cliente marcó la casilla de consentimiento al solicitar el turno.

El secretario también puede enviar mensajes manuales desde la sección de turnos, siempre que exista ese consentimiento. El número debe ser válido e incluir el código de país; los números argentinos nacionales de 10 dígitos se convierten a formato `+549`.