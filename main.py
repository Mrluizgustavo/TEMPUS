from src.loader import ExcelLoader
from src.processador import Processador
from src.reporter import ExcelReporter  # Importe a nova classe


def main():
    # 1. Carrega (Lembre-se da estratégia de carregar dias a mais para garantir a borda)
    loader = ExcelLoader("data/input/Batidas 01 - 15.xlsx")
    try:
        df = loader.carregar()
    except Exception as e:
        print(f"Erro ao carregar: {e}")
        return

    # 2. Processa (Blindado contra erros de 5 batidas, dobras, etc)
    processador = Processador(df)

    # Aqui você pode filtrar o período que você quer VER no relatório
    # Ex: Quero ver tudo de Janeiro
    resultados = processador.executar_analise(
        data_inicio_filtro="2025-12-02",
        data_fim_filtro="2025-12-04"
        # Se quiser tudo, tire os filtros ou passe None
    )

    # 3. Gera o Excel
    reporter = ExcelReporter()
    reporter.gerar_relatorio_excel(resultados, "Relatorio_Final_RH.xlsx")


if __name__ == "__main__":
    main()