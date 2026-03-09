from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("testes", "0013_loja_quadro_contratado_colaborador_funcao"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="TesteControlePeriodo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("competencia", models.DateField(help_text="Primeiro dia do mês de referência do ciclo 20-19.")),
                ("questionado_em", models.DateField(blank=True, null=True)),
                ("decisao_supervisor", models.CharField(blank=True, choices=[("PAUSA", "Pausa"), ("PAGAR_PREMIO", "Pagar prêmio"), ("PROMOVER", "Promover"), ("CANCELAR", "Cancelar")], max_length=20)),
                ("respondido_em", models.DateField(blank=True, null=True)),
                ("executado_em", models.DateField(blank=True, null=True)),
                ("observacao", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("executado_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="controles_periodo_executados", to=settings.AUTH_USER_MODEL)),
                ("teste", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="controles_periodo", to="testes.testepromocao")),
            ],
            options={
                "verbose_name": "Controle mensal do teste",
                "verbose_name_plural": "Controles mensais do teste",
                "ordering": ["-competencia", "-id"],
            },
        ),
        migrations.AddConstraint(
            model_name="testecontroleperiodo",
            constraint=models.UniqueConstraint(fields=("teste", "competencia"), name="uniq_controle_periodo_por_teste"),
        ),
    ]
