"""
import pandas as pd
from .models import JornadaInconsistente


class ExcelReporter:
    def exportar_erros(self, lista_erros: list[JornadaInconsistente], nome_arquivo: str):
        if not lista_erros:
            print("Nenhum erro para exportar.")
            return

        print(f"Gerando relatório expandido com {len(lista_erros)} inconsistências...")

        dados_formatados = []

        for erro in lista_erros:
            # 1. Cria a base da linha
            linha = {
                "NOME": erro.nome_colaborador,
                "DATA": erro.data_referencia,
                "TOTAL": len(erro.batidas_registradas)  # Útil para filtrar depois
            }


            for i, horario in enumerate(erro.batidas_registradas):
                nome_coluna = f"BATIDA {i + 1}"
                linha[nome_coluna] = horario

            dados_formatados.append(linha)


        df_relatorio = pd.DataFrame(dados_formatados)

        colunas_existentes = df_relatorio.columns.tolist()

        colunas_fixas = ["NOME", "DATA", "TOTAL"]
        colunas_batidas = sorted([col for col in colunas_existentes if col.startswith("BATIDA")])

        ordem_final = colunas_fixas + colunas_batidas

        ordem_final = [c for c in ordem_final if c in df_relatorio.columns]

        df_relatorio = df_relatorio[ordem_final]

        # Salva o arquivo
        caminho_completo = f"data/output/{nome_arquivo}"
        df_relatorio.to_excel(caminho_completo, index=False)
        print(f"✅ Relatório salvo com sucesso em: {caminho_completo}")


"""

from .models import JornadaInconsistente


class TextReporter:
    def gerar_texto_copia_cola(self, lista_erros: list[JornadaInconsistente]):
        if not lista_erros:
            print("Nenhum erro encontrado.")
            return

        # 1. Descobrir qual o número MÁXIMO de batidas entre todos os erros
        # Isso serve para criar o cabeçalho dinâmico (Batida 1, Batida 2... Batida N)
        max_batidas = 0
        for erro in lista_erros:
            qtd = len(erro.batidas_registradas)
            if qtd > max_batidas:
                max_batidas = qtd

        # 2. Criar o Cabeçalho
        # Ex: NOME [tab] DATA [tab] BATIDA 1 [tab] BATIDA 2...
        colunas_batidas = [f"BATIDA {i + 1}" for i in range(max_batidas)]
        cabecalho = ["NOME", "DATA"] + colunas_batidas

        # O \t é o código invisível para "Tabulação"
        texto_final = "\t".join(cabecalho) + "\n"

        # 3. Criar as Linhas
        for erro in lista_erros:
            batidas = erro.batidas_registradas

            # Preenche com vazio se a pessoa tiver menos batidas que o máximo
            # Ex: Se o max é 5 e eu tenho 3, adiciona 2 vazios no final
            faltam = max_batidas - len(batidas)
            batidas_preenchidas = batidas + [""] * faltam

            # Monta a linha
            linha = [erro.nome_colaborador, erro.data_referencia] + batidas_preenchidas
            texto_final += "\t".join(linha) + "\n"

        # 4. Imprime no console para o usuário copiar
        print("=" * 60)
        print("COPIE O TEXTO ABAIXO E COLE NO EXCEL (Ctrl+C / Ctrl+V):")
        print("=" * 60)
        print(texto_final)
        print("=" * 60)