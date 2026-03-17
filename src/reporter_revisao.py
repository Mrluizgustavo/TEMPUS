import pandas as pd
import os
from openpyxl.styles import Font, PatternFill, Alignment
from .processador import ResultadoJornada


class ExcelReporterRevisao:
    """
    Gera o Excel intermediário de revisão humana.
    Contém apenas a segmentação das jornadas — sem status, duração ou intervalo.
    O usuário corrige os agrupamentos e depois confirma na Etapa 2.
    """

    NOME_ARQUIVO  = "Revisao_Jornadas.xlsx"
    NOME_ABA      = "REVISÃO"
    CAMINHO_PASTA = "data/output"

    @classmethod
    def caminho_revisao(cls) -> str:
        return os.path.abspath(os.path.join(cls.CAMINHO_PASTA, cls.NOME_ARQUIVO))

    def gerar_excel_revisao(self, resultados: list[ResultadoJornada]) -> str:
        if not resultados:
            print("⚠️ Nenhum dado para gerar revisão.")
            return ""

        max_batidas = max((len(r.batidas) for r in resultados), default=0)

        linhas = []
        for r in resultados:
            linha = {
                "CHAPA": r.chapa,
                "LOJA": r.loja,
                "NOME":  r.nome,
                "IDADE": r.idade,
                "DATA":  r.data_inicio_str,
            }
            for i, horario in enumerate(r.batidas):
                # Remove prefixo de dia seguinte "(DD) " para deixar só "HH:MM"
                horario_limpo = horario
                if horario.startswith("("):
                    horario_limpo = horario[6:].strip()
                linha[f"BAT{i + 1}"] = horario_limpo

            linhas.append(linha)

        df = pd.DataFrame(linhas)

        # Garante todas as colunas de batida mesmo que algumas jornadas tenham menos
        colunas_fixas  = ["CHAPA", "LOJA", "NOME",  "IDADE", "DATA"]
        colunas_batidas = [f"BAT{i + 1}" for i in range(max_batidas)]
        df = df.reindex(columns=colunas_fixas + colunas_batidas).fillna("")

        os.makedirs(self.CAMINHO_PASTA, exist_ok=True)
        caminho_completo = os.path.join(self.CAMINHO_PASTA, self.NOME_ARQUIVO)

        try:
            with pd.ExcelWriter(caminho_completo, engine="openpyxl") as writer:
                df.to_excel(writer, sheet_name=self.NOME_ABA, index=False)
                ws = writer.sheets[self.NOME_ABA]

                # Congela cabeçalho
                ws.freeze_panes = "A2"

            print(f"✅ Excel de revisão gerado: {caminho_completo}")
            return caminho_completo

        except PermissionError:
            raise PermissionError(
                f"O arquivo '{self.NOME_ARQUIVO}' está aberto. Feche-o e tente novamente."
            )