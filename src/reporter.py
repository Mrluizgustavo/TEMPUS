import pandas as pd
import os
from .processador import ResultadoJornada


class ExcelReporter:
    def _criar_dataframe(self, lista_resultados: list[ResultadoJornada]):

        if not lista_resultados:
            return pd.DataFrame()

        # Descobre o máximo de batidas desta lista específica
        max_batidas = max((len(r.batidas) for r in lista_resultados), default=0)

        dados = []
        for r in lista_resultados:
            linha = {
                "NOME": r.nome,
                "DATA": r.data_inicio_str,
                "STATUS": r.status,
                "DURAÇÃO": r.duracao,
                "QTD_BATIDAS": len(r.batidas)
            }
            for i, horario in enumerate(r.batidas):
                linha[f"BATIDA {i + 1}"] = horario

            dados.append(linha)

        df = pd.DataFrame(dados)

        # Organização Visual das Colunas
        colunas_fixas = ["NOME", "DATA", "STATUS", "DURAÇÃO", "QTD_BATIDAS"]
        colunas_batidas = [f"BATIDA {i + 1}" for i in range(max_batidas)]

        # Garante a ordem correta das colunas
        ordem_final = colunas_fixas + colunas_batidas


        df = df.reindex(columns=ordem_final).fillna("")

        # LIMPEZA DE MARCADORES DE DIA
        # Aplica o regex em todas as colunas de batida
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

        # 2. Separação por Status
        lista_ok = []
        lista_batidas_irregulares = []  # Ímpar, Qtd excessiva
        lista_duracao_irregular = []  # Longa, Curta, Intervalo

        for r in resultados:
            status = r.status.upper()

            # Lógica de Classificação
            if "OK" in status:
                lista_ok.append(r)

            elif "IMPAR" in status or "QTD" in status:
                lista_batidas_irregulares.append(r)

            else:
                # Cai aqui: REVISAO_LONGA, REVISAO_CURTA, INTERVALO IRREGULAR
                lista_duracao_irregular.append(r)

        # 3. Criação dos DataFrames usando a função auxiliar
        df_geral = self._criar_dataframe(resultados)  # Aba Geral
        df_batidas = self._criar_dataframe(lista_batidas_irregulares)
        df_duracao = self._criar_dataframe(lista_duracao_irregular)
        df_ok = self._criar_dataframe(lista_ok)

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

                # Aba 3: Duração/Intervalo
                if not df_duracao.empty:
                    df_duracao.to_excel(writer, sheet_name='DURAÇÃO IRREGULAR', index=False)

                # Aba 4: Validadas
                if not df_ok.empty:
                    df_ok.to_excel(writer, sheet_name='OK', index=False)

            print("=" * 60)
            print(f"✅ SUCESSO! Relatório salvo em: {caminho_completo}")
            print(f"   - Faltas de Marcação: {len(lista_batidas_irregulares)}")
            print(f"   - Duração Irregular:   {len(lista_duracao_irregular)}")
            print(f"   - Validadas:           {len(lista_ok)}")
            print("=" * 60)

        except PermissionError:
            print(f"❌ ERRO: O arquivo '{nome_arquivo}' está aberto no Excel. Feche-o e tente novamente.")