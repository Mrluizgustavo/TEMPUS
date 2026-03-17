import sqlite3
import os
from datetime import datetime

import pandas as pd

from src.processador import ResultadoJornada


class BancoDeDados:
    def __init__(self, nome_banco="historico_ponto.db"):
        os.makedirs("data", exist_ok=True)
        self.caminho = os.path.join("data", nome_banco)
        self._inicializar_tabelas()

    def _conectar(self):
        return sqlite3.connect(self.caminho)

    def _inicializar_tabelas(self):
        conn   = self._conectar()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS jornadas(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT,
                idade INTEGER,
                chapa TEXT,
                loja TEXT,
                data DATE,
                dia_semana TEXT,
                qtd_batidas INTEGER,
                horas_trabalhadas REAL,
                tempo_intervalo REAL,
                data_processamento TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(chapa, data)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS status_jornada(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_jornada INTEGER NOT NULL,
                tipo_status TEXT NOT NULL,
                FOREIGN KEY (id_jornada) REFERENCES jornadas(id) ON DELETE CASCADE
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_data  ON jornadas(data)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_nome  ON jornadas(nome)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_loja  ON jornadas(loja)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_status_composto ON status_jornada(tipo_status, id_jornada)")

        conn.commit()
        conn.close()

    def salvar_jornadas(self, resultados: list[ResultadoJornada]):
        conn   = self._conectar()
        cursor = conn.cursor()
        conn.execute("PRAGMA foreign_keys = ON")

        print(f"Salvando {len(resultados)} registros no histórico...")

        for r in resultados:
            try:
                h, m = map(int, r.duracao.split(':'))
                duracao_decimal = h + (m / 60)
            except:
                duracao_decimal = 0.0

            chapa_valor = getattr(r, 'chapa', None)
            data_obj    = datetime.strptime(r.data_inicio_str, "%Y-%m-%d")
            dia_semana  = data_obj.strftime("%A")

            cursor.execute("""
                INSERT INTO jornadas
                (nome, chapa, idade, loja, data, dia_semana, qtd_batidas,
                 horas_trabalhadas, tempo_intervalo)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(chapa, data) DO UPDATE SET
                    nome = excluded.nome,
                    idade = excluded.idade,
                    loja = excluded.loja,
                    dia_semana = excluded.dia_semana,
                    qtd_batidas = excluded.qtd_batidas,
                    horas_trabalhadas = excluded.horas_trabalhadas,
                    tempo_intervalo = excluded.tempo_intervalo,
                    data_processamento = CURRENT_TIMESTAMP
                RETURNING id
            """, (
                r.nome, chapa_valor, r.idade, r.loja, r.data_inicio_str,
                dia_semana, len(r.batidas), duracao_decimal, r.intervalo
            ))

            id_jornada = cursor.fetchone()[0]
            cursor.execute("DELETE FROM status_jornada WHERE id_jornada = ?", (id_jornada,))

            for status in r.status:
                if status != "OK":
                    cursor.execute(
                        "INSERT INTO status_jornada (id_jornada, tipo_status) VALUES (?, ?)",
                        (id_jornada, status)
                    )

        conn.commit()
        conn.close()
        print("✅ Dados salvos com sucesso!")

    # ─────────────────────────────────────────────────────────────────────────
    # FILTROS DISPONÍVEIS
    # ─────────────────────────────────────────────────────────────────────────

    def obter_filtros_disponiveis(self) -> dict:
        conn = self._conectar()
        try:
            df_lojas = pd.read_sql_query(
                "SELECT DISTINCT loja FROM jornadas WHERE loja IS NOT NULL ORDER BY loja", conn
            )
            df_meses = pd.read_sql_query(
                "SELECT DISTINCT strftime('%Y-%m', data) AS mes_ano FROM jornadas ORDER BY mes_ano", conn
            )
            meses = [f"{m[5:7]}/{m[:4]}" for m in df_meses["mes_ano"].tolist()]

            return {
                "lojas": df_lojas["loja"].tolist(),
                "meses": meses,
            }
        finally:
            conn.close()

    # ─────────────────────────────────────────────────────────────────────────
    # DASHBOARD — ORQUESTRADOR
    # ─────────────────────────────────────────────────────────────────────────

    def obter_dados_dashboard(self,
                              loja: str | None = None,
                              mes_ano: str | None = None) -> dict:
        conn = self._conectar()
        try:
            mes_sql = None
            if mes_ano:
                p = mes_ano.split("/")
                mes_sql = f"{p[1]}-{p[0]}"

            return {
                "kpis":             self.obter_kpis(conn, loja, mes_sql),
                "intervalos":       self.obter_dados_intervalos(conn, loja, mes_sql),
                "faltas":           self.obter_dados_faltas(conn, loja, mes_sql),
                "menores":          self.obter_tabela_menores(conn, loja, mes_sql),
                "jornadas_longas":  self.obter_tabela_jornadas_longas(conn, loja, mes_sql),
                "total_validado":   self.obter_jornadas_validadas(conn, loja, mes_sql),
                "distribuicao":     self.obter_distribuicao_jornada(conn, loja, mes_sql),
                "horas_extras":     self.obter_evolucao_horas_extras(conn, loja, mes_sql),
                "irregularidades":  self.obter_irregularidades_por_tipo(conn, loja, mes_sql),
                "top5":             self.obter_top5_por_status(conn, loja, mes_sql),
            }
        finally:
            conn.close()

    # ─────────────────────────────────────────────────────────────────────────
    # HELPER — WHERE dinâmico
    # ─────────────────────────────────────────────────────────────────────────

    def _clausulas(self, loja, mes_sql, extra: str = "", prefixo: str = "j") -> tuple[str, list]:
        partes = []
        params = []

        if loja:
            partes.append(f"{prefixo}.loja = ?")
            params.append(loja)

        if mes_sql:
            partes.append(f"strftime('%Y-%m', {prefixo}.data) = ?")
            params.append(mes_sql)

        if extra:
            partes.append(extra)

        where = ("WHERE " + " AND ".join(partes)) if partes else ""
        return where, params

    # ─────────────────────────────────────────────────────────────────────────
    # KPI CARDS
    # ─────────────────────────────────────────────────────────────────────────

    def obter_kpis(self, conn, loja, mes_sql):
        where, p = self._clausulas(loja, mes_sql)
        total_func = pd.read_sql_query(
            f"SELECT COUNT(DISTINCT nome) as total FROM jornadas j {where}", conn, params=p
        )["total"].iloc[0]

        where_e, p_e = self._clausulas(loja, mes_sql, "s.tipo_status IN ('EXTRA','JORNADA_LONGA')")
        df_extra = pd.read_sql_query(
            f"""SELECT j.horas_trabalhadas FROM jornadas j
                INNER JOIN status_jornada s ON s.id_jornada = j.id {where_e}""",
            conn, params=p_e
        )
        total_extra = round((df_extra["horas_trabalhadas"] - 7.583).clip(lower=0).sum(), 1) \
                      if not df_extra.empty else 0.0

        where_i, p_i = self._clausulas(loja, mes_sql, "s.tipo_status IN ('INTERVALO_CURTO','INTERVALO_LONGO')")
        total_int = pd.read_sql_query(
            f"""SELECT COUNT(DISTINCT s.id_jornada) as total FROM jornadas j
                INNER JOIN status_jornada s ON s.id_jornada = j.id {where_i}""",
            conn, params=p_i
        )["total"].iloc[0]

        where_f, p_f = self._clausulas(loja, mes_sql, "s.tipo_status = 'FALTA_DE_MARCACAO'")
        total_falta = pd.read_sql_query(
            f"""SELECT COUNT(*) as total FROM jornadas j
                INNER JOIN status_jornada s ON s.id_jornada = j.id {where_f}""",
            conn, params=p_f
        )["total"].iloc[0]

        return {
            "total_funcionarios":           int(total_func),
            "total_horas_extras":           total_extra,
            "total_intervalos_irregulares": int(total_int),
            "total_faltas_marcacao":        int(total_falta),
        }

    # ─────────────────────────────────────────────────────────────────────────
    # TABELA — MENORES IRREGULARES
    # ─────────────────────────────────────────────────────────────────────────

    def obter_tabela_menores(self, conn, loja, mes_sql):
        """
        Retorna lista de dicts com as colunas que a tabela vai exibir:
        Nome | Data | Loja
        """
        where, p = self._clausulas(loja, mes_sql, 's.tipo_status = "JORNADA_IRREGULAR_MENOR"')
        df = pd.read_sql_query(
            f"""
            SELECT j.nome AS "Nome",
                   DATE(j.data) AS "Data",
                   j.loja AS "Loja"
            FROM jornadas j
            INNER JOIN status_jornada s ON s.id_jornada = j.id
            {where}
            ORDER BY j.data DESC
            """,
            conn, params=p
        )

        if df.empty:
            return None

        df["Data"] = pd.to_datetime(df["Data"]).dt.strftime("%d/%m/%Y")
        return df.to_dict(orient="records")

    # ─────────────────────────────────────────────────────────────────────────
    # TABELA — JORNADAS LONGAS (> 10h)
    # ─────────────────────────────────────────────────────────────────────────

    def obter_tabela_jornadas_longas(self, conn, loja, mes_sql):
        """
        Retorna lista de dicts com as colunas:
        Nome | Data | Horas | Loja
        """
        where, p = self._clausulas(loja, mes_sql, "s.tipo_status = 'JORNADA_LONGA'")
        df = pd.read_sql_query(
            f"""
            SELECT j.nome AS "Nome",
                   DATE(j.data) AS "Data",
                   ROUND(j.horas_trabalhadas, 2) AS "Horas",
                   j.loja AS "Loja"
            FROM jornadas j
            INNER JOIN status_jornada s ON s.id_jornada = j.id
            {where}
            ORDER BY j.horas_trabalhadas DESC
            """,
            conn, params=p
        )

        if df.empty:
            return None

        df["Data"]  = pd.to_datetime(df["Data"]).dt.strftime("%d/%m/%Y")
        # Formata horas como "11:30"
        df["Horas"] = df["Horas"].apply(
            lambda h: f"{int(h):02d}:{int((h % 1) * 60):02d}"
        )
        return df.to_dict(orient="records")

    # ─────────────────────────────────────────────────────────────────────────
    # TOP 5 POR STATUS — para o gráfico de barras com seletor
    # ─────────────────────────────────────────────────────────────────────────

    def obter_top5_por_status(self, conn, loja, mes_sql) -> dict:
        """
        Retorna um dict com uma entrada por categoria, cada uma com:
          { "labels": [...], "values": [...] }

        Categorias disponíveis:
          - faltas_marcacao
          - intervalos_irregulares  (CURTO + LONGO juntos)
          - extras
          - jornadas_longas
          - jornadas_longas_sem_intervalo
        """
        mapa = {
            "faltas_marcacao":              "FALTA_DE_MARCACAO",
            "extras":                       "EXTRA",
            "jornadas_longas":              "JORNADA_LONGA",
            "jornadas_longas_sem_intervalo":"JORNADA_LONGA_SEM_INTERVALO",
        }
        resultado = {}

        for chave, status_sql in mapa.items():
            where, p = self._clausulas(loja, mes_sql, f"s.tipo_status = '{status_sql}'")
            df = pd.read_sql_query(
                f"""SELECT j.nome, COUNT(*) as total
                    FROM jornadas j
                    INNER JOIN status_jornada s ON s.id_jornada = j.id
                    {where}
                    GROUP BY j.nome ORDER BY total DESC LIMIT 5""",
                conn, params=p
            )
            resultado[chave] = {
                "labels": df["nome"].tolist() if not df.empty else [],
                "values": df["total"].tolist() if not df.empty else [],
            }

        # Intervalos irregulares = CURTO + LONGO somados por funcionário
        where_ii, p_ii = self._clausulas(
            loja, mes_sql, "s.tipo_status IN ('INTERVALO_CURTO','INTERVALO_LONGO')"
        )
        df_ii = pd.read_sql_query(
            f"""SELECT j.nome, COUNT(*) as total
                FROM jornadas j
                INNER JOIN status_jornada s ON s.id_jornada = j.id
                {where_ii}
                GROUP BY j.nome ORDER BY total DESC LIMIT 5""",
            conn, params=p_ii
        )
        resultado["intervalos_irregulares"] = {
            "labels": df_ii["nome"].tolist() if not df_ii.empty else [],
            "values": df_ii["total"].tolist() if not df_ii.empty else [],
        }

        return resultado

    # ─────────────────────────────────────────────────────────────────────────
    # DISTRIBUIÇÃO DE JORNADA
    # ─────────────────────────────────────────────────────────────────────────

    def obter_distribuicao_jornada(self, conn, loja, mes_sql):
        where, p = self._clausulas(loja, mes_sql, "j.horas_trabalhadas > 0")
        df = pd.read_sql_query(
            f"SELECT horas_trabalhadas FROM jornadas j {where}", conn, params=p
        )

        if df.empty:
            return None

        faixas   = pd.cut(df["horas_trabalhadas"],
                          bins=[0, 8, 10, float("inf")],
                          labels=["Até 8h", "8h – 10h", ">10h"])
        contagem = faixas.value_counts().reindex(["Até 8h", "8h – 10h", ">10h"], fill_value=0)

        return {
            "labels": contagem.index.tolist(),
            "values": contagem.values.tolist(),
            "colors": ["#4CAF50", "#ff9800", "#f44336"],
        }

    # ─────────────────────────────────────────────────────────────────────────
    # EVOLUÇÃO DE HORAS EXTRAS
    # ─────────────────────────────────────────────────────────────────────────

    def obter_evolucao_horas_extras(self, conn, loja, mes_sql):
        where, p = self._clausulas(loja, mes_sql, "s.tipo_status IN ('EXTRA','JORNADA_LONGA')")
        df = pd.read_sql_query(
            f"""SELECT j.data, j.horas_trabalhadas FROM jornadas j
                INNER JOIN status_jornada s ON s.id_jornada = j.id {where}""",
            conn, params=p
        )

        if df.empty:
            return None

        df["data"]      = pd.to_datetime(df["data"])
        df["excedente"] = (df["horas_trabalhadas"] - 7.583).clip(lower=0)
        df["mes"]       = df["data"].dt.to_period("M")

        agrupado = df.groupby("mes")["excedente"].sum().reset_index().sort_values("mes")

        return {
            "labels": agrupado["mes"].astype(str).tolist(),
            "values": [round(v, 1) for v in agrupado["excedente"].tolist()],
        }

    # ─────────────────────────────────────────────────────────────────────────
    # IRREGULARIDADES POR TIPO
    # ─────────────────────────────────────────────────────────────────────────

    def obter_irregularidades_por_tipo(self, conn, loja, mes_sql):
        where, p = self._clausulas(loja, mes_sql)

        if where:
            query = f"""
                SELECT s.tipo_status, COUNT(*) as total
                FROM jornadas j
                INNER JOIN status_jornada s ON s.id_jornada = j.id
                {where}
                GROUP BY s.tipo_status ORDER BY total DESC
            """
        else:
            query = """
                SELECT tipo_status, COUNT(*) as total
                FROM status_jornada
                GROUP BY tipo_status ORDER BY total DESC
            """

        df = pd.read_sql_query(query, conn, params=p)
        if df.empty:
            return None

        traducao = {
            "FALTA_DE_MARCACAO":           "Falta de Marcação",
            "INTERVALO_CURTO":             "Intervalo Curto",
            "INTERVALO_LONGO":             "Intervalo Longo",
            "JORNADA_LONGA":               "Jornada Longa",
            "JORNADA_LONGA_SEM_INTERVALO": "Jornada s/ Intervalo",
            "JORNADA_CURTA":               "Jornada Curta",
            "EXTRA":                       "Hora Extra",
            "JORNADA_IRREGULAR_MENOR":     "Menor Irregular",
        }
        df["tipo_status"] = df["tipo_status"].replace(traducao)

        return {"labels": df["tipo_status"].tolist(), "values": df["total"].tolist()}

    # ─────────────────────────────────────────────────────────────────────────
    # JORNADAS VALIDADAS
    # ─────────────────────────────────────────────────────────────────────────

    def obter_jornadas_validadas(self, conn, loja, mes_sql):
        where, p = self._clausulas(loja, mes_sql)
        sem_status = "s.id_jornada IS NULL"

        if where:
            query = f"""
                SELECT COUNT(j.id) as total FROM jornadas j
                LEFT JOIN status_jornada s ON s.id_jornada = j.id
                {where} AND {sem_status}
            """
        else:
            query = f"""
                SELECT COUNT(j.id) as total FROM jornadas j
                LEFT JOIN status_jornada s ON s.id_jornada = j.id
                WHERE {sem_status}
            """

        df = pd.read_sql_query(query, conn, params=p)
        if df.empty:
            return None

        return {"Total_validado": int(df["total"].iloc[0])}

    # ─────────────────────────────────────────────────────────────────────────
    # INTERVALOS
    # ─────────────────────────────────────────────────────────────────────────

    def obter_dados_intervalos(self, conn, loja, mes_sql):
        where, p = self._clausulas(loja, mes_sql, "s.tipo_status IN ('INTERVALO_CURTO','INTERVALO_LONGO')")
        df = pd.read_sql_query(
            f"""SELECT j.id, s.tipo_status FROM jornadas j
                INNER JOIN status_jornada s ON s.id_jornada = j.id {where}""",
            conn, params=p
        )

        if df.empty:
            return None

        df["tipo_status"] = df["tipo_status"].replace({
            "INTERVALO_CURTO": "Curtos",
            "INTERVALO_LONGO": "Longos",
        })
        tipos_counts = df["tipo_status"].value_counts()

        return {
            "total_intervalos_irregulares": df["id"].nunique(),
            "labels": tipos_counts.index.tolist(),
            "values": tipos_counts.values.tolist(),
        }

    # ─────────────────────────────────────────────────────────────────────────
    # FALTAS DE MARCAÇÃO
    # ─────────────────────────────────────────────────────────────────────────

    def obter_dados_faltas(self, conn, loja, mes_sql):
        where, p = self._clausulas(loja, mes_sql, "s.tipo_status = 'FALTA_DE_MARCACAO'")
        df = pd.read_sql_query(
            f"""SELECT j.nome, DATE(j.data) as data FROM jornadas j
                INNER JOIN status_jornada s ON s.id_jornada = j.id {where}""",
            conn, params=p
        )

        if df.empty:
            return None

        df["data"]     = pd.to_datetime(df["data"])
        faltas_grouped = df.groupby("data").size().reset_index(name="total").sort_values("data")
        nomes_count    = df["nome"].value_counts().head(5)

        return {
            "labels_faltas_marcacao":  faltas_grouped["data"].dt.strftime("%d/%m").tolist(),
            "values_faltas_marcacao":  faltas_grouped["total"].tolist(),
            "total_faltas":            int(faltas_grouped["total"].sum()),
            "top_funcionarios_labels": nomes_count.index.tolist(),
            "top_funcionarios_values": nomes_count.values.tolist(),
        }