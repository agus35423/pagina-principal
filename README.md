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

La recuperación de contraseña y los avisos a clientes usan la configuración de correo. Para Gmail por SMTP, definí `EMAIL_HOST_USER` y `EMAIL_HOST_PASSWORD` con una contraseña de aplicación (no la contraseña habitual), y usá `EMAIL_HOST=smtp.gmail.com`, `EMAIL_PORT=587`, `EMAIL_USE_TLS=true` y `EMAIL_USE_SSL=false`.

**Importante para Render Free:** Render bloquea las conexiones SMTP salientes en los puertos 465 y 587. Para enviar desde una cuenta Gmail sin cambiar de plan, la aplicación usa Gmail API por HTTPS. Configurá estas variables en **Render Dashboard → tu Web Service → Environment**:

- `EMAIL_HOST_USER`: dirección Gmail autorizada para enviar.
- `GMAIL_OAUTH_CLIENT_ID`: ID de cliente OAuth de Google.
- `GMAIL_OAUTH_CLIENT_SECRET`: secreto del cliente OAuth.
- `GMAIL_OAUTH_REFRESH_TOKEN`: token de actualización OAuth.
- `PUBLIC_SITE_URL`: URL pública del sitio.

Al completar las tres variables `GMAIL_OAUTH_*`, la aplicación selecciona Gmail API automáticamente. No configures SMTP como `EMAIL_BACKEND` para el plan Free. No guardes estas credenciales en el repositorio ni las compartas; agregalas como variables privadas en Render.

Para obtener las credenciales OAuth, habilitá Gmail API en un proyecto de Google Cloud, configurá el consentimiento OAuth y autorizá el alcance `https://www.googleapis.com/auth/gmail.send` para la misma cuenta indicada en `EMAIL_HOST_USER`. Podés generar un refresh token con [OAuth 2.0 Playground](https://developers.google.com/oauthplayground) usando tus propias credenciales OAuth. Mantené el token privado y revisá el estado de publicación/verificación de la aplicación OAuth; los tokens de aplicaciones externas en modo de prueba pueden vencer a los 7 días.

En un servicio Render pago también se puede usar SMTP de Gmail con la contraseña de aplicación indicada arriba. En producción, configurá las credenciales antes de desplegar. Si no hay configuración SMTP ni OAuth en desarrollo, Django imprime el correo en la consola del servidor.

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