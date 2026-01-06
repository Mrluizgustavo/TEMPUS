import pandas as pd
import os


class ExcelLoader:
    def __init__(self, caminho_arquivo: str):
        # Guardando o caminho na "memória" do objeto
        self.caminho = caminho_arquivo

    def carregar(self) -> pd.DataFrame:
        """Lê o arquivo Excel e valida se existe."""
        print(f"Tentando ler arquivo em: {self.caminho}")

        if not os.path.exists(self.caminho):
            # É boa prática lançar erro se o arquivo não existir
            raise FileNotFoundError(f"O arquivo não foi encontrado: {self.caminho}")

        try:
            df = pd.read_excel(self.caminho)
            print("Arquivo carregado com sucesso!")
            return df
        except Exception as e:
            raise ValueError(f"Erro ao ler o Excel. Verifique o formato. Detalhe: {e}")