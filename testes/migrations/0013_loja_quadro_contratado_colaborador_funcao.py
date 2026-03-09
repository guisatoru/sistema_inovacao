from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("testes", "0012_alter_colaborador_ativo_alter_loja_ativo"),
    ]

    operations = [
        migrations.AddField(
            model_name="loja",
            name="quadro_contratado",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="colaborador",
            name="funcao",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="colaboradores",
                to="testes.funcao",
            ),
        ),
    ]
