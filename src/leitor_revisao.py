import pandas as pd
import os
from datetime import datetime
from .processador import Processador, ResultadoJornada
from .reporter_revisao import ExcelReporterRevisao


class LeitorRevisao:

    COLUNAS_FIXAS = ["CHAPA", "LOJA", "NOME", "IDADE", "DATA"]

    def carregar_e_recalcular(self, caminho: str = None) -> list[ResultadoJornada]:
        if not caminho:
            caminho = ExcelReporterRevisao.caminho_revisao()

        df = pd.read_excel(caminho, sheet_name=ExcelReporterRevisao.NOME_ABA, dtype=str)
        self._validar_colunas(df)

        colunas_batidas = [c for c in df.columns if c.startswith("BAT")]

        # Instância vazia só para reutilizar _analisar_status
        processador = Processador(pd.DataFrame())

        resultados = []
        id_jornada  = 0

        for _, row in df.iterrows():
            data_str = str(row["DATA"]).strip()

            # Reconstrói datetimes das batidas
            batidas_dt = []
            for col in colunas_batidas:
                val = str(row[col]).strip()
                if val == "" or val.lower() == "nan":
                    continue
                try:
                    batidas_dt.append(pd.Timestamp(f"{data_str} {val}"))
                except Exception:
                    continue

            if not batidas_dt:
                continue

            batidas_series = pd.Series(batidas_dt)
            idade = int(row["IDADE"]) if str(row["IDADE"]).isdigit() else 0

            status, duracao, intervalo, _ = processador._analisar_status(batidas_series, idade)

            # Reconstrói batidas_texto no formato padrão do sistema
            primeira = batidas_series.iloc[0]
            dia_ref  = primeira.day
            batidas_texto = [
                b.strftime("%H:%M") if b.day == dia_ref else b.strftime("(%d) %H:%M")
                for b in batidas_series
            ]

            data_obj = datetime.strptime(data_str, "%Y-%m-%d")
            id_jornada += 1

            # Recupera a sinalização de múltiplas jornadas gravada na coluna REVISAR,
            # caso ela exista no arquivo. Não vai para o banco — apenas preserva a
            # informação para que o relatório final possa exibi-la corretamente.
            multipla = False
            if "REVISAR" in df.columns:
                val_revisar = str(row.get("REVISAR", "")).strip()
                multipla = val_revisar != "" and val_revisar.lower() != "nan"

            resultados.append(ResultadoJornada(
                id_jornada=id_jornada,
                chapa=str(row["CHAPA"]).strip(),
                loja=str(row["LOJA"]).strip(),
                nome=str(row["NOME"]).strip(),
                idade=idade,
                data_inicio_obj=data_obj,
                data_inicio_str=data_str,
                batidas=batidas_texto,
                status=status,
                duracao=duracao,
                intervalo=intervalo,
                multipla_jornada_no_dia=multipla,
            ))

        return resultados

    def _validar_colunas(self, df: pd.DataFrame):
        faltando = set(self.COLUNAS_FIXAS) - set(df.columns)
        if faltando:
            raise ValueError(
                f"Colunas ausentes no arquivo de revisão: {faltando}\n"
                "Não remova colunas do arquivo gerado pelo sistema."
            )