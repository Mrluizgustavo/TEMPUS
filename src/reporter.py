import pandas as pd
import os
from .processador import ResultadoJornada


class ExcelReporter:
    def gerar_relatorio_excel(self, resultados: list[ResultadoJornada], nome_arquivo: str = "Relatorio_Completo.xlsx"):
        """
        Recebe os dados processados e gera um arquivo Excel real na pasta data/output.
        """

        # 1. Validação de Segurança
        if not resultados:
            print("⚠️ Nenhum dado para gerar relatório.")
            return

        print(f"Gerando Excel com {len(resultados)} jornadas...")

        # 2. Descobre o número máximo de batidas para criar as colunas (Batida 1, 2, 3...)
        # Se o recordista tiver 8 batidas, o Excel terá 8 colunas de batida.
        max_batidas = max((len(r.batidas) for r in resultados), default=0)

        # 3. Transforma a lista de Objetos em lista de Dicionários (formato do Pandas)
        dados_para_dataframe = []

        for r in resultados:
            # Dados base da linha
            linha = {
                "NOME": r.nome,
                "DATA": r.data_inicio_str,
                "STATUS": r.status,
                "DURAÇÃO": r.duracao,
                "QTD_BATIDAS": len(r.batidas)  # Coluna extra útil para filtro
            }

            # Preenchimento Dinâmico das Batidas
            # Se a pessoa tem 3 batidas, preenche Batida 1, 2 e 3.
            for i, horario in enumerate(r.batidas):
                coluna = f"BATIDA {i + 1}"
                linha[coluna] = horario

            dados_para_dataframe.append(linha)

        # 4. Cria o DataFrame
        df = pd.DataFrame(dados_para_dataframe)

        # 5. Organização Visual das Colunas
        # O Pandas pode bagunçar a ordem, então forçamos a ordem correta
        colunas_fixas = ["NOME", "DATA", "STATUS", "DURAÇÃO", "QTD_BATIDAS"]
        colunas_batidas = [f"BATIDA {i + 1}" for i in range(max_batidas)]

        # Garante que só vamos ordenar colunas que realmente existem no dataframe
        ordem_final = colunas_fixas + colunas_batidas

        # Reordena e preenche vazios com "" (estético)
        df = df.reindex(columns=ordem_final).fillna("")

        # 6. Salva o Arquivo
        caminho_pasta = "data/output"
        os.makedirs(caminho_pasta, exist_ok=True)  # Cria a pasta se não existir

        caminho_completo = os.path.join(caminho_pasta, nome_arquivo)

        try:
            df.to_excel(caminho_completo, index=False)
            print("=" * 60)
            print(f"✅ SUCESSO! Relatório salvo em: {caminho_completo}")
            print("=" * 60)
        except PermissionError:
            print(f"❌ ERRO: O arquivo '{nome_arquivo}' está aberto no Excel. Feche-o e tente novamente.")
