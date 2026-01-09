import pandas as pd
from dataclasses import dataclass
from datetime import datetime

# CONFIGURAÇÃO DE SEGURANÇA (Sem plantão)
# Se o intervalo for maior que isso, CORTE, não importa se é impar ou par.
LIMITE_CORTE_ABSOLUTO = 15  # Horas


@dataclass
class ResultadoJornada:
    id_jornada: int
    nome: str
    data_inicio_obj: datetime
    data_inicio_str: str
    batidas: list[str]
    status: str
    duracao: str


class Processador:
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()

    def _preparar_timeline(self):
        self.df["DATA"] = pd.to_datetime(self.df["DATA"], errors="coerce")
        self.df["HORA_DELTA"] = pd.to_timedelta(self.df["BATIDA"], unit="m")
        self.df["DATETIME"] = self.df["DATA"] + self.df["HORA_DELTA"]
        self.df.dropna(subset=["DATETIME"], inplace=True)
        # Ordenação absoluta é vital
        self.df.sort_values(by=["NOME", "DATETIME"], inplace=True)
        self.df.reset_index(drop=True, inplace=True)

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

            # Mudou de pessoa? Novo ID.
            if nome_atual != ultimo_nome:
                id_atual += 1
                batidas_na_jornada = 1
                self.df.at[idx, "ID_JORNADA"] = id_atual
                ultimo_nome = nome_atual
                ultima_hora = hora_atual
                continue

            diff_horas = (hora_atual - ultima_hora).total_seconds() / 3600
            nova_jornada = False

            # --- LÓGICA REFINADA ---

            # Se passou de 15h, é impossível ser a mesma jornada na sua empresa.
            # Corta mesmo se estiver ímpar (evita colar dias).
            if diff_horas > LIMITE_CORTE_ABSOLUTO:
                nova_jornada = True

            # REGRA 2: Almoço/Café
            elif diff_horas < 4:
                nova_jornada = False

            # REGRA 3: Zona de Ambiguidade (5h a 15h)
            # Aqui confiamos no Par/Ímpar
            else:
                if batidas_na_jornada % 2 == 0:
                    nova_jornada = True
                else:
                    nova_jornada = False

            if nova_jornada:
                id_atual += 1
                batidas_na_jornada = 1
            else:
                batidas_na_jornada += 1

            self.df.at[idx, "ID_JORNADA"] = id_atual
            ultima_hora = hora_atual

    def _analisar_status(self, batidas_dt: pd.Series) -> tuple[str, str]:
        qtd = len(batidas_dt)
        inicio = batidas_dt.iloc[0]
        fim = batidas_dt.iloc[-1]
        duracao_horas = (fim - inicio).total_seconds() / 3600

        horas_int = int(duracao_horas)
        minutos_int = int((duracao_horas - horas_int) * 60)
        duracao_str = f"{horas_int:02d}:{minutos_int:02d}"

        # Casos de batidas irregulares

        # 1. É Impar?
        if qtd % 2 != 0:
            return "ERRO_IMPAR", duracao_str

        # 2. É Par, mas tem batidas demais?
        if qtd > 4:
            return f"REVISAO_QTD_({qtd})", duracao_str

        # 3. Intervalo estranha
        if duracao_horas < 1:
            return "REVISAO_CURTA", duracao_str

        if duracao_horas > 14:
            return "REVISAO_LONGA", duracao_str

        return "OK", duracao_str

    def executar_analise(self, data_inicio_filtro=None, data_fim_filtro=None) -> list[ResultadoJornada]:
        self._preparar_timeline()
        self._segmentar_jornadas()

        resultados = []
        grupos = self.df.groupby("ID_JORNADA")

        filtro_inicio = pd.to_datetime(data_inicio_filtro) if data_inicio_filtro else None
        filtro_fim = pd.to_datetime(data_fim_filtro) if data_fim_filtro else None

        for id_jornada, dados in grupos:
            batidas_dt = dados["DATETIME"]
            primeira_batida = batidas_dt.iloc[0]

            if filtro_inicio and primeira_batida < filtro_inicio: continue
            if filtro_fim and primeira_batida > filtro_fim: continue

            batidas_texto = []
            dia_ref = primeira_batida.day
            for b in batidas_dt:
                fmt = b.strftime("%H:%M") if b.day == dia_ref else b.strftime("(%d) %H:%M")
                batidas_texto.append(fmt)

            status, duracao = self._analisar_status(batidas_dt)

            resultados.append(ResultadoJornada(
                id_jornada=id_jornada,
                nome=dados["NOME"].iloc[0],
                data_inicio_obj=primeira_batida,
                data_inicio_str=primeira_batida.strftime("%d/%m/%Y"),
                batidas=batidas_texto,
                status=status,
                duracao=duracao
            ))

        return resultados