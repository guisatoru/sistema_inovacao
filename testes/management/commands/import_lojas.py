from django.core.management.base import BaseCommand
from testes.models import Loja, Regiao
import pandas as pd

def norm(v):
    return str(v).strip() if v is not None else ""

class Command(BaseCommand):
    help = "Importa Lojas e Regiões (UF) a partir de um Excel (.xlsx/.xlsm)"

    def add_arguments(self, parser):
        parser.add_argument("arquivo", type=str, help="Caminho do arquivo .xlsm/.xlsx")
        parser.add_argument("--aba", type=str, default=None, help="Nome da aba (opcional)")

    def handle(self, *args, **options):
        arquivo = options["arquivo"]
        aba = options["aba"]

        # 👉 Se aba for informada, usa ela
        # 👉 Se não, lê a PRIMEIRA aba
        if aba:
            df = pd.read_excel(arquivo, sheet_name=aba)
        else:
            df = pd.read_excel(arquivo)  # primeira aba automaticamente

        df.columns = [str(c).strip() for c in df.columns]

        if "Loja" not in df.columns or "UF" not in df.columns:
            raise Exception(
                f"Não achei as colunas obrigatórias. Preciso de: Loja, UF. "
                f"Colunas encontradas: {list(df.columns)}"
            )

        lojas_criadas = 0
        lojas_atualizadas = 0
        regioes_criadas = 0

        for _, row in df.iterrows():
            loja_nome = norm(row.get("Loja"))
            uf = norm(row.get("UF")).upper()

            if not loja_nome or not uf:
                continue

            regiao, created = Regiao.objects.get_or_create(nome=uf)
            if created:
                regioes_criadas += 1

            loja, created = Loja.objects.get_or_create(
                nome=loja_nome,
                defaults={"regiao": regiao}
            )

            if created:
                lojas_criadas += 1
            else:
                if loja.regiao_id != regiao.id:
                    loja.regiao = regiao
                    loja.save(update_fields=["regiao"])
                    lojas_atualizadas += 1

        self.stdout.write(self.style.SUCCESS(
            f"Importação finalizada com sucesso!\n"
            f"Lojas criadas: {lojas_criadas}\n"
            f"Lojas atualizadas: {lojas_atualizadas}\n"
            f"Regiões (UF) criadas: {regioes_criadas}"
        ))
