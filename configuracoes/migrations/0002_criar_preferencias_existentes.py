from django.conf import settings
from django.db import migrations


def criar_preferencias(apps, schema_editor):
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    Preferencias = apps.get_model("configuracoes", "PreferenciasUsuario")
    Preferencias.objects.bulk_create(
        [Preferencias(usuario_id=pk) for pk in User.objects.values_list("pk", flat=True)],
        ignore_conflicts=True,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("configuracoes", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(criar_preferencias, migrations.RunPython.noop),
    ]
