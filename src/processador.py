import pandas as pd
from .models import JornadaInconsistente


class ProcessadorPonto:
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()

    #Converte os dados
    def _preparar_dados(self):

        self.df["DATA"] = pd.to_datetime(self.df["DATA"], errors="coerce")
        self.df["HORA_DELTA"] = pd.to_timedelta(self.df["BATIDA"], unit="m")
        self.df["DATETIME"] = self.df["DATA"] + self.df["HORA_DELTA"]

        # 2. ORDENAÇÃO É OBRIGATÓRIA PARA ESSA LÓGICA
        self.df.sort_values(by=["NOME", "DATETIME"], inplace=True)
        self.df.reset_index(drop=True, inplace=True)


    def _agrupar_por_jornada_dinamica(self):
        """
        Mágica do Pandas:
        Cria um ID único para cada jornada baseada no tempo de descanso.
        Se o funcionário descansou mais de 12h, consideramos uma NOVA jornada.
        """

        TOLERANCIA_MAX_GAP = pd.Timedelta(hours=8)

        # Calcula a diferença de tempo entre a linha atual e a anterior
        self.df["DIFF"] = self.df["DATETIME"].diff()

        # Verifica se mudou o nome da pessoa
        self.df["MUDOU_PESSOA"] = self.df["NOME"] != self.df["NOME"].shift(1)

        # Lógica do divisor de águas:
        # É uma nova jornada SE: (Mudou a Pessoa) OU (O intervalo foi maior que 14h)
        condicao_nova_jornada = (self.df["MUDOU_PESSOA"]) | (self.df["DIFF"] > TOLERANCIA_MAX_GAP)

        # Incrementa um contador toda a vez que a condição é True
        # Ex: 1, 1, 1, 2, 2, 3, 3, 3...
        self.df["JORNADA_ID"] = condicao_nova_jornada.cumsum()

    def processar(self):
        self._preparar_dados()
        self._agrupar_por_jornada_dinamica()

    def check_batidas_impares(self) -> list[JornadaInconsistente]:
        erros = []

        # Agora agrupamos pelo ID da Jornada, não mais por data!
        grupos = self.df.groupby("JORNADA_ID")

        for jornada_id, dados in grupos:
            # Pegamos os dados do grupo
            nome = dados["NOME"].iloc[0]

            # Para referência visual, pegamos a data da primeira batida
            data_referencia = dados["DATETIME"].iloc[0].strftime("%d/%m/%Y")

            batidas = dados["DATETIME"].dt.strftime("%H:%M").tolist()

            if len(batidas) % 2 != 0:
                relatorio = JornadaInconsistente(
                    nome_colaborador=nome,
                    data_referencia=f"{data_referencia} (Jornada Dinâmica)",
                    batidas_registradas=batidas
                )
                erros.append(relatorio)

        return erros