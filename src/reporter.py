import pandas as pd
import os
from .processador import ResultadoJornada


class ExcelReporter:
    def _criar_dataframe(self, lista_resultados: list[ResultadoJornada], categoria=None):

        if not lista_resultados:
            return pd.DataFrame()

        max_batidas = max((len(r.batidas) for r in lista_resultados), default=0)

        dados = []

        for r in lista_resultados:

            # 🔎 Se for aba específica, filtra os status
            if categoria:
                status_filtrado = [
                    s for s in r.status
                    if self.mapa_categorias.get(s.upper()) == categoria
                ]
                status_exibicao = " | ".join(status_filtrado)
            else:
                # Aba geral → mostra tudo
                status_exibicao = " | ".join(r.status)

            linha = {
                "NOME": r.nome,
                "DATA": r.data_inicio_str,
                "STATUS": status_exibicao,
                "QTD_BATIDAS": len(r.batidas),
                "DURAÇÃO": r.duracao

            }

            for i, horario in enumerate(r.batidas):
                linha[f"BATIDA {i + 1}"] = horario

            dados.append(linha)

        df = pd.DataFrame(dados)

        colunas_fixas = ["NOME", "DATA", "STATUS", "QTD_BATIDAS", "DURAÇÃO" ]
        colunas_batidas = [f"BATIDA {i + 1}" for i in range(max_batidas)]

        ordem_final = colunas_fixas + colunas_batidas
        df = df.reindex(columns=ordem_final).fillna("")

        for col in colunas_batidas:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace(r"\(\d+\)\s*", "", regex=True)

        return df

    def gerar_relatorio_excel(self, resultados: list[ResultadoJornada], nome_arquivo: str = "Relatorio.xlsx"):
        """
        Gera o Excel com múltiplas abas baseadas no Status.
        """
        # 1. Validação
        if not resultados:
            print("⚠️ Nenhum dado para gerar relatório.")
            return

        print(f"Classificando {len(resultados)} jornadas em abas...")

        self.mapa_categorias = {
            "OK": "OK",
            "EXTRA": "EXTRA",

            "FALTA_DE_MARCACAO": "FALTA_DE_MARCACAO",

            "INTERVALO_CURTO": "INTERVALOS_IRREGULARES",
            "INTERVALO_LONGO": "INTERVALOS_IRREGULARES",

            "JORNADA_LONGA": "JORNADAS_IRREGULARES",
            "JORNADA_CURTA": "JORNADAS_IRREGULARES",
            "JORNADA_LONGA_SEM_INTERVALO": "JORNADAS_IRREGULARES"
        }

        abas = {
            "OK": [],
            "EXTRA": [],
            "FALTA_DE_MARCACAO": [],
            "INTERVALOS_IRREGULARES": [],
            "JORNADAS_IRREGULARES": []
        }

        for r in resultados:
            status_list = [s.upper() for s in r.status]

            categorias_adicionadas = set()

            for status in status_list:
                categoria = self.mapa_categorias.get(status)

                if categoria and categoria not in categorias_adicionadas:
                    abas[categoria].append(r)
                    categorias_adicionadas.add(categoria)

        df_geral = self._criar_dataframe(resultados)

        df_ok = self._criar_dataframe(
            abas["OK"],
            categoria="OK"
        )

        df_extra = self._criar_dataframe(
            abas["EXTRA"],
            categoria="EXTRA"
        )

        df_batidas = self._criar_dataframe(
            abas["FALTA_DE_MARCACAO"],
            categoria="FALTA_DE_MARCACAO"
        )

        df_intervalo = self._criar_dataframe(
            abas["INTERVALOS_IRREGULARES"],
            categoria="INTERVALOS_IRREGULARES"
        )

        df_duracao = self._criar_dataframe(
            abas["JORNADAS_IRREGULARES"],
            categoria="JORNADAS_IRREGULARES"
        )

        # 4. Gravação do Arquivo com Abas
        caminho_pasta = "data/output"
        os.makedirs(caminho_pasta, exist_ok=True)
        caminho_completo = os.path.join(caminho_pasta, nome_arquivo)

        try:
            with pd.ExcelWriter(caminho_completo, engine='openpyxl') as writer:

                # Aba 1: Visão Geral (Tudo junto)
                if not df_geral.empty:
                    df_geral.to_excel(writer, sheet_name='VISÃO GERAL', index=False)

                # Aba 2: Batidas Irregulares (Prioridade Alta)
                if not df_batidas.empty:
                    df_batidas.to_excel(writer, sheet_name='FALTAS DE MARCAÇÃO', index=False)

                # Aba 3: Duração
                if not df_duracao.empty:
                    df_duracao.to_excel(writer, sheet_name='JORNADAS IRREGULARES', index=False)

                # Aba 4: Intervalo
                if not df_intervalo.empty:
                    df_intervalo.to_excel(writer, sheet_name='INTERVALO IRREGULAR', index=False)

                # Aba 5: Extra
                if not df_extra.empty:
                    df_extra.to_excel(writer, sheet_name='EXTRA', index=False)

                # Aba 6: Validadas
                if not df_ok.empty:
                    df_ok.to_excel(writer, sheet_name='JORNADAS VALIDADAS', index=False)

            print("=" * 60)
            print(f"✅ SUCESSO! Relatório salvo em: {caminho_completo}")
            print(f"   - Faltas de Marcação: {len(abas["FALTA_DE_MARCACAO"])}")
            print(f"   - Durações Irregulares:   {len(abas["JORNADAS_IRREGULARES"])}")
            print(f"   - Intervalos Irregulares:   {len(abas["INTERVALOS_IRREGULARES"])}")
            print(f"   - Validadas:           {len(abas["OK"])}")
            print("=" * 60)

        except PermissionError:
            print(f"❌ ERRO: O arquivo '{nome_arquivo}' está aberto no Excel. Feche-o e tente novamente.")