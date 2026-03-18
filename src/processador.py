import pandas as pd
from dataclasses import dataclass, field
from datetime import datetime


MINUTOS_INTERJORNADA_MINIMA = 11 * 60  # 660 min — exigência CLT


@dataclass
class ResultadoJornada:
    id_jornada:          int
    chapa:               str
    loja:                str
    nome:                str
    idade:               int
    data_inicio_obj:     datetime
    data_inicio_str:     str
    batidas:             list[str]
    status:              list[str]
    duracao:             str
    intervalo:           str
    # Tempo entre o fim desta jornada e o início da próxima do mesmo funcionário.
    # None significa que não há jornada anterior para comparar (primeira do período).
    minutos_interjornada: int | None = field(default=None)


class Processador:
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()

    def _preparar_timeline(self):
        self.df["DATA"]       = pd.to_datetime(self.df["DATA"], errors="coerce")
        self.df["HORA_DELTA"] = pd.to_timedelta(self.df["BATIDA"], unit="m")
        self.df["DATETIME"]   = self.df["DATA"] + self.df["HORA_DELTA"]

        self.df.dropna(subset=["DATETIME"], inplace=True)
        self.df.sort_values(by=["NOME", "DATETIME"], inplace=True)
        self._remover_duplicatas()
        self.df.reset_index(drop=True, inplace=True)

    def _remover_duplicatas(self):
        mesma_pessoa      = self.df["NOME"] == self.df["NOME"].shift(1)
        diff_tempo        = self.df["DATETIME"].diff()
        tolerancia        = pd.Timedelta(minutes=5)
        mascara_duplicadas = mesma_pessoa & (diff_tempo < tolerancia)

        if mascara_duplicadas.sum() > 0:
            self.df = self.df[~mascara_duplicadas].copy()

    def _segmentar_jornadas(self):
        self.df["ID_JORNADA"] = 0

        id_atual        = 0
        ultimo_nome     = None
        ultima_hora     = None
        ultima_natureza = None
        inicio_jornada  = None

        MAX_GAP_HORAS       = 12
        MAX_DURACAO_JORNADA = 16

        for row in self.df.itertuples():
            idx      = row.Index
            nome     = row.NOME
            hora     = row.DATETIME
            natureza = row.NATUREZA

            if nome != ultimo_nome:
                id_atual += 1
                self.df.at[idx, "ID_JORNADA"] = id_atual
                ultimo_nome     = nome
                ultima_hora     = hora
                ultima_natureza = natureza
                inicio_jornada  = hora
                continue

            gap_horas     = (hora - ultima_hora).total_seconds() / 3600
            duracao_total = (hora - inicio_jornada).total_seconds() / 3600
            nova_jornada  = False

            if gap_horas > MAX_GAP_HORAS or duracao_total > MAX_DURACAO_JORNADA:
                nova_jornada = True

            if nova_jornada:
                id_atual        += 1
                inicio_jornada   = hora
                ultima_natureza  = natureza

            self.df.at[idx, "ID_JORNADA"] = id_atual
            ultima_hora = hora

    def _corrigir_ordem_noturna(self, batidas_dt: pd.Series) -> pd.Series:
        batidas = batidas_dt.sort_values().reset_index(drop=True)

        for i in range(1, len(batidas)):
            diff = (batidas.iloc[i] - batidas.iloc[i - 1]).total_seconds() / 3600
            if diff > 12:
                parte_seguinte = batidas.iloc[:i].copy() + pd.Timedelta(days=1)
                parte_atual    = batidas.iloc[i:].copy()
                batidas = pd.concat([parte_atual, parte_seguinte]).reset_index(drop=True)
                break

        return batidas

    def _analisar_status(self, batidas_dt: pd.Series, idade: int) -> tuple[list[str], str, str, int]:
        if not pd.api.types.is_datetime64_any_dtype(batidas_dt):
            batidas_dt = pd.to_datetime(batidas_dt, errors="coerce")

        batidas_dt = batidas_dt.dropna()
        batidas_dt = self._corrigir_ordem_noturna(batidas_dt)
        qtd        = len(batidas_dt)

        alertas       = []
        duracao_str   = "00:00"
        intervalo_str = "0.0"

        if idade < 18:
            for batida in batidas_dt:
                if batida.hour >= 22 or batida.hour < 5:
                    alertas.append("JORNADA_IRREGULAR_MENOR")
                    break

        if qtd % 2 != 0:
            alertas.append("FALTA_DE_MARCACAO")
            return alertas, duracao_str, intervalo_str, idade

        entradas        = batidas_dt.iloc[::2].reset_index(drop=True)
        saidas          = batidas_dt.iloc[1::2].reset_index(drop=True)
        total_timedelta = (saidas - entradas).sum()
        total_segundos  = total_timedelta.total_seconds()
        duracao_horas   = total_segundos / 3600

        horas_int   = int(total_segundos // 3600)
        minutos_int = int((total_segundos % 3600) // 60)
        duracao_str = f"{horas_int:02d}:{minutos_int:02d}"

        if qtd == 4:
            intervalo     = (batidas_dt.iloc[2] - batidas_dt.iloc[1]).total_seconds() / 3600
            intervalo_str = str(round(intervalo, 2))

            if intervalo < (50 / 60): alertas.append("INTERVALO_CURTO")
            if intervalo > (70 / 60): alertas.append("INTERVALO_LONGO")

        if 7.35 < duracao_horas < 10:       alertas.append("EXTRA")
        if duracao_horas > 10:              alertas.append("JORNADA_LONGA")
        if qtd == 2 and duracao_horas > 6:  alertas.append("JORNADA_SEM_INTERVALO")
        if duracao_horas < 4:               alertas.append("JORNADA_CURTA")

        if not alertas:
            alertas.append("OK")

        return alertas, duracao_str, intervalo_str, idade

    def _calcular_interjornadas(self, resultados: list[ResultadoJornada]) -> list[ResultadoJornada]:
        """
        Para cada funcionário, percorre suas jornadas em ordem cronológica e
        calcula o tempo entre o fim de uma e o início da próxima.

        A interjornada é atribuída à jornada que CHEGA — ou seja, a que sofre
        a consequência de ter descansado menos que o mínimo legal.

        Jornadas com FALTA_DE_MARCACAO são ignoradas no cálculo porque não
        temos a hora de saída real, o que tornaria o resultado inválido.
        """
        # Agrupa por funcionário preservando a ordem de inserção (já cronológica)
        jornadas_por_funcionario: dict[str, list[ResultadoJornada]] = {}
        for resultado in resultados:
            jornadas_por_funcionario.setdefault(resultado.chapa, []).append(resultado)

        for chapa, jornadas in jornadas_por_funcionario.items():
            # Ordena pelo datetime de início para garantir sequência correta
            jornadas.sort(key=lambda j: j.data_inicio_obj)

            for i in range(1, len(jornadas)):
                jornada_anterior = jornadas[i - 1]
                jornada_atual    = jornadas[i]

                # Não calcula se a jornada anterior tem falta de marcação —
                # sem saída real não é possível saber quando terminou
                if "FALTA_DE_MARCACAO" in jornada_anterior.status:
                    continue

                # Reconstrói o datetime da última batida da jornada anterior
                # a partir da duração, somando ao início
                try:
                    h, m = map(int, jornada_anterior.duracao.split(":"))
                    fim_jornada_anterior = (
                        jornada_anterior.data_inicio_obj + pd.Timedelta(hours=h, minutes=m)
                    )
                except:
                    continue

                inicio_jornada_atual  = jornada_atual.data_inicio_obj
                minutos_interjornada  = int(
                    (inicio_jornada_atual - fim_jornada_anterior).total_seconds() / 60
                )

                # Só registra interjornadas positivas — negativo indica dado inconsistente
                if minutos_interjornada < 0:
                    continue

                jornada_atual.minutos_interjornada = minutos_interjornada

                if minutos_interjornada < MINUTOS_INTERJORNADA_MINIMA:
                    if "INTERJORNADA_IRREGULAR" not in jornada_atual.status:
                        # Remove OK se estava lá, pois agora há irregularidade
                        jornada_atual.status = [
                            s for s in jornada_atual.status if s != "OK"
                        ]
                        jornada_atual.status.append("INTERJORNADA_IRREGULAR")

        return resultados

    def executar_analise(self, data_inicio_filtro=None, data_fim_filtro=None) -> list[ResultadoJornada]:
        self._preparar_timeline()
        self._segmentar_jornadas()

        filtro_inicio = pd.Timestamp(pd.to_datetime(data_inicio_filtro)) if data_inicio_filtro else None
        filtro_fim    = (
            pd.Timestamp(pd.to_datetime(data_fim_filtro)) + pd.Timedelta(days=1)
            if data_fim_filtro else None
        )

        resultados = []
        for id_jornada, dados in self.df.groupby("ID_JORNADA"):
            batidas_dt      = dados["DATETIME"]
            primeira_batida = batidas_dt.iloc[0]

            if filtro_inicio is not None and primeira_batida < filtro_inicio: continue
            if filtro_fim    is not None and primeira_batida >= filtro_fim:   continue

            dia_ref       = primeira_batida.day
            batidas_texto = [
                b.strftime("%H:%M") if b.day == dia_ref else b.strftime("(%d) %H:%M")
                for b in batidas_dt
            ]

            status, duracao, intervalo, idade = self._analisar_status(
                batidas_dt, dados["IDADE"].iloc[0]
            )

            resultados.append(ResultadoJornada(
                id_jornada       = id_jornada,
                nome             = dados["NOME"].iloc[0],
                chapa            = dados["CHAPA"].iloc[0],
                idade            = idade,
                loja             = dados["LOJA"].iloc[0],
                data_inicio_obj  = primeira_batida,
                data_inicio_str  = primeira_batida.strftime("%Y-%m-%d"),
                batidas          = batidas_texto,
                status           = status,
                duracao          = duracao,
                intervalo        = intervalo,
            ))

        # Calcula interjornadas após ter todas as jornadas do período montadas
        resultados = self._calcular_interjornadas(resultados)

        return resultados