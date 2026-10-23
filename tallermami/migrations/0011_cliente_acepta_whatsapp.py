from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tallermami", "0010_cliente_dni"),
    ]

    operations = [
        migrations.AddField(
            model_name="cliente",
            name="acepta_whatsapp",
            field=models.BooleanField(
                default=False,
                verbose_name="Acepta recibir mensajes por WhatsApp",
            ),
        ),
    ]
