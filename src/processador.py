import pandas as pd
from dataclasses import dataclass
from datetime import datetime

# CONFIGURAÇÃO DE SEGURANÇA
LIMITE_CORTE_ABSOLUTO = 13  # Horas


@dataclass
class ResultadoJornada:
    id_jornada: int
    nome: str  # Voltamos a usar apenas o Nome
    data_inicio_obj: datetime
    data_inicio_str: str
    batidas: list[str]
    status: str
    duracao: str


class Processador:
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()

    def _preparar_timeline(self):
        # Conversão de Data e Hora
        self.df["DATA"] = pd.to_datetime(self.df["DATA"], errors="coerce")
        self.df["HORA_DELTA"] = pd.to_timedelta(self.df["BATIDA"], unit="m")
        self.df["DATETIME"] = self.df["DATA"] + self.df["HORA_DELTA"]

        self.df.dropna(subset=["DATETIME"], inplace=True)

        # ORDENAÇÃO POR NOME (Essencial para agrupar as batidas da mesma pessoa)
        self.df.sort_values(by=["NOME", "DATETIME"], inplace=True)

        self._remover_duplicatas()
        self.df.reset_index(drop=True, inplace=True)

    def _remover_duplicatas(self):
        # Verifica se é a mesma pessoa (NOME) e se o tempo é curto (< 3 min)
        mesma_pessoa = self.df["NOME"] == self.df["NOME"].shift(1)
        diff_tempo = self.df["DATETIME"].diff()
        tolerancia = pd.Timedelta(minutes=3)
        mascara_duplicadas = mesma_pessoa & (diff_tempo < tolerancia)

        if mascara_duplicadas.sum() > 0:
            self.df = self.df[~mascara_duplicadas].copy()

    def _segmentar_jornadas(self):
        self.df["ID_JORNADA"] = 0
        id_atual = 1
        batidas_na_jornada = 0
        ultimo_nome = ""
        ultima_hora = None

        for row in self.df.itertuples():
            idx = row.Index
            nome_atual = row.NOME
            hora_atual = row.DATETIME

            # Mudou de pessoa? Nova Jornada.
            if nome_atual != ultimo_nome:
                id_atual += 1
                batidas_na_jornada = 1
                self.df.at[idx, "ID_JORNADA"] = id_atual
                ultimo_nome = nome_atual
                ultima_hora = hora_atual
                continue

            # Cálculo de Gaps
            diff_horas = 0
            if ultima_hora:
                diff_horas = (hora_atual - ultima_hora).total_seconds() / 3600

            nova_jornada = False

            # Regras de Quebra de Jornada
            if diff_horas > LIMITE_CORTE_ABSOLUTO:
                nova_jornada = True
            elif diff_horas < 4:
                nova_jornada = False
            else:
                # Zona de ambiguidade (entre 4h e 13h)
                if batidas_na_jornada % 2 == 0:
                    nova_jornada = True  # Par fechado, nova jornada
                else:
                    nova_jornada = False  # Ímpar aberto, continuação (almoço longo)

            if nova_jornada:
                id_atual += 1
                batidas_na_jornada = 1
            else:
                batidas_na_jornada += 1

            self.df.at[idx, "ID_JORNADA"] = id_atual
            ultima_hora = hora_atual

    def _analisar_status(self, batidas_dt: pd.Series) -> tuple[str, str]:
        if not pd.api.types.is_datetime64_any_dtype(batidas_dt):
            batidas_dt = pd.to_datetime(batidas_dt, errors='coerce')

        batidas_dt = batidas_dt.dropna()
        qtd = len(batidas_dt)

        # Regra básica: Ímpar é erro
        if qtd % 2 != 0:
            return f"ERRO_IMPAR ({qtd})", "--:--"

        batidas_dt = batidas_dt.sort_values()
        entradas = batidas_dt.iloc[::2].reset_index(drop=True)
        saidas = batidas_dt.iloc[1::2].reset_index(drop=True)

        tempo_total = (saidas - entradas).sum()
        total_segundos = tempo_total.total_seconds()
        duracao_horas = total_segundos / 3600

        horas_int = int(total_segundos // 3600)
        minutos_int = int(round((total_segundos % 3600) / 60))
        duracao_str = f"{horas_int:02d}:{minutos_int:02d}"

        alertas = []
        min_intervalo = 50 / 60
        max_intervalo = 70 / 60

        # Verifica Intervalo apenas se tiver 4 batidas (padrão)
        if qtd == 4:
            saida_almoco = batidas_dt.iloc[1]
            volta_almoco = batidas_dt.iloc[2]
            intervalo = (volta_almoco - saida_almoco).total_seconds() / 3600

            if intervalo < min_intervalo or intervalo > max_intervalo:
                alertas.append("INTERVALO IRREGULAR")

        if duracao_horas > 10: alertas.append("REVISAO_LONGA")
        if duracao_horas < 4: alertas.append("JORNADA CURTA")
        if qtd > 4: alertas.append("(EXTRA)")

        if not alertas:
            return "OK", duracao_str
        else:
            return " ".join(alertas), duracao_str

    def executar_analise(self, data_inicio_filtro=None, data_fim_filtro=None) -> list[ResultadoJornada]:
        self._preparar_timeline()
        self._segmentar_jornadas()

        resultados = []
        grupos = self.df.groupby("ID_JORNADA")

        filtro_inicio = pd.to_datetime(data_inicio_filtro) if data_inicio_filtro else None

        # Filtro de Fim com +1 dia (para pegar o dia final completo)
        if data_fim_filtro:
            filtro_fim = pd.to_datetime(data_fim_filtro) + pd.Timedelta(days=1)
        else:
            filtro_fim = None

        for id_jornada, dados in grupos:
            batidas_dt = dados["DATETIME"]
            primeira_batida = batidas_dt.iloc[0]

            # Filtros de Data
            if filtro_inicio and primeira_batida < filtro_inicio: continue
            if filtro_fim and primeira_batida >= filtro_fim: continue

            batidas_texto = []
            dia_ref = primeira_batida.day
            for b in batidas_dt:
                fmt = b.strftime("%H:%M") if b.day == dia_ref else b.strftime("(%d) %H:%M")
                batidas_texto.append(fmt)

            status, duracao = self._analisar_status(batidas_dt)

            resultados.append(ResultadoJornada(
                id_jornada=id_jornada,
                # Chapa removida daqui
                nome=dados["NOME"].iloc[0],
                data_inicio_obj=primeira_batida,
                data_inicio_str=primeira_batida.strftime("%Y-%m-%d"),
                batidas=batidas_texto,
                status=status,
                duracao=duracao
            ))

        return resultados