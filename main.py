from src.loader import ExcelLoader
from src.processador import ProcessadorPonto
from src.reporter import TextReporter # Mudamos para TextReporter

def main():
    # 1. INPUT
    loader = ExcelLoader("data/input/Batidas 17-18.xlsx")
    try:
        df = loader.carregar()
    except Exception as e:
        print(e)
        return

    # 2. CORE
    sistema = ProcessadorPonto(df)
    sistema.processar()
    erros = sistema.check_batidas_impares()

    # 3. OUTPUT (Texto para copiar)
    reporter = TextReporter()
    if erros:
        reporter.gerar_texto_copia_cola(erros)
    else:
        print("Tudo certo! Nenhuma inconsistência encontrada.")

if __name__ == "__main__":
    main()