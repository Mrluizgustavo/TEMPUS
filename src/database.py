import sqlite3
import os

import pandas as pd

from src.processador import ResultadoJornada

MINUTOS_JORNADA_NORMAL      = 7 * 60 + 20   # 440 min — base de desconto do excedente
MINUTOS_GATILHO_EXTRA       = 7 * 60 + 30   # 450 min — só conta como extra acima disto
MINUTOS_INTERJORNADA_MINIMA = 11 * 60        # 660 min — mínimo legal CLT


class BancoDeDados:
    def __init__(self, nome_banco="historico_ponto.db"):
        os.makedirs("data", exist_ok=True)
        self.caminho = os.path.join("data", nome_banco)
        self._inicializar_banco()

    def _conectar(self):
        conn = sqlite3.connect(self.caminho)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    # ─────────────────────────────────────────────────────────────────────────
    # SCHEMA
    # ─────────────────────────────────────────────────────────────────────────

    def _inicializar_banco(self):
        conn = self._conectar()
        cur  = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS funcionarios (
                id    INTEGER PRIMARY KEY AUTOINCREMENT,
                chapa TEXT    NOT NULL UNIQUE,
                nome  TEXT    NOT NULL,
                loja  TEXT,
                idade INTEGER
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS jornadas (
                id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                id_funcionario        INTEGER NOT NULL,
                data                  DATE    NOT NULL,
                ano_mes               TEXT    NOT NULL,
                minutos_trabalhados   INTEGER NOT NULL,
                minutos_intervalo     INTEGER NOT NULL DEFAULT 0,
                minutos_interjornada  INTEGER,          -- NULL = sem jornada anterior no período
                qtd_batidas           INTEGER NOT NULL,
                data_processamento    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(id_funcionario, data),
                FOREIGN KEY (id_funcionario) REFERENCES funcionarios(id)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS status_jornada (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                id_jornada  INTEGER NOT NULL,
                tipo_status TEXT    NOT NULL,
                FOREIGN KEY (id_jornada) REFERENCES jornadas(id) ON DELETE CASCADE
            )
        """)

        cur.execute("CREATE INDEX IF NOT EXISTS idx_func_chapa        ON funcionarios(chapa)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_func_loja         ON funcionarios(loja)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_jornada_func      ON jornadas(id_funcionario)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_jornada_ano_mes   ON jornadas(ano_mes)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_status_tipo       ON status_jornada(tipo_status, id_jornada)")

        # Migração silenciosa — adiciona a coluna se o banco já existia sem ela
        try:
            cur.execute("ALTER TABLE jornadas ADD COLUMN minutos_interjornada INTEGER")
        except:
            pass

        conn.commit()
        conn.close()

    # ─────────────────────────────────────────────────────────────────────────
    # SALVAR
    # ─────────────────────────────────────────────────────────────────────────

    def salvar_jornadas(self, resultados: list[ResultadoJornada]):
        if not resultados:
            return

        conn = self._conectar()
        cur  = conn.cursor()

        # 1. Upsert de funcionários em batch
        cur.executemany("""
            INSERT INTO funcionarios (chapa, nome, loja, idade)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(chapa) DO UPDATE SET
                nome  = excluded.nome,
                loja  = excluded.loja,
                idade = excluded.idade
        """, [(r.chapa, r.nome, r.loja, r.idade) for r in resultados])

        # 2. Busca ids dos funcionários em uma única query
        chapas = list({r.chapa for r in resultados})
        cur.execute(
            f"SELECT chapa, id FROM funcionarios WHERE chapa IN ({','.join('?'*len(chapas))})",
            chapas
        )
        id_por_chapa = dict(cur.fetchall())

        # 3. Upsert de jornadas em batch
        cur.executemany("""
            INSERT INTO jornadas
                (id_funcionario, data, ano_mes, minutos_trabalhados,
                 minutos_intervalo, minutos_interjornada, qtd_batidas)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id_funcionario, data) DO UPDATE SET
                ano_mes              = excluded.ano_mes,
                minutos_trabalhados  = excluded.minutos_trabalhados,
                minutos_intervalo    = excluded.minutos_intervalo,
                minutos_interjornada = excluded.minutos_interjornada,
                qtd_batidas          = excluded.qtd_batidas,
                data_processamento   = CURRENT_TIMESTAMP
        """, [
            (
                id_por_chapa[r.chapa],
                r.data_inicio_str,
                r.data_inicio_str[:7],
                self._converter_duracao_para_minutos(r.duracao),
                self._converter_intervalo_para_minutos(r.intervalo),
                r.minutos_interjornada,
                len(r.batidas),
            )
            for r in resultados
        ])

        # 4. Busca ids das jornadas recém salvas
        chaves = [f"{id_por_chapa[r.chapa]}|{r.data_inicio_str}" for r in resultados]
        cur.execute(
            f"""SELECT id_funcionario || '|' || data AS chave, id
                FROM jornadas
                WHERE id_funcionario || '|' || data IN ({','.join('?'*len(chaves))})""",
            chaves
        )
        id_por_jornada = {
            (int(c.split("|")[0]), c.split("|")[1]): jid
            for c, jid in cur.fetchall()
        }

        # 5. Limpa status antigos e insere novos em batch
        ids = list(id_por_jornada.values())
        cur.execute(
            f"DELETE FROM status_jornada WHERE id_jornada IN ({','.join('?'*len(ids))})", ids
        )
        novos_status = [
            (id_por_jornada[(id_por_chapa[r.chapa], r.data_inicio_str)], s)
            for r in resultados
            for s in r.status
            if s != "OK"
        ]
        if novos_status:
            cur.executemany(
                "INSERT INTO status_jornada (id_jornada, tipo_status) VALUES (?, ?)",
                novos_status
            )

        conn.commit()
        conn.close()
        print(f"✅ {len(resultados)} jornadas salvas.")

    # ─────────────────────────────────────────────────────────────────────────
    # HELPERS INTERNOS
    # ─────────────────────────────────────────────────────────────────────────

    def _converter_duracao_para_minutos(self, duracao: str) -> int:
        try:
            h, m = map(int, duracao.split(":"))
            return h * 60 + m
        except:
            return 0

    def _converter_intervalo_para_minutos(self, intervalo: str) -> int:
        try:
            return round(float(intervalo) * 60)
        except:
            return 0

    def _montar_filtro_sql(self, loja, ano_mes, condicao_extra: str = "") -> tuple[str, list]:
        partes = []
        params = []

        if loja:
            partes.append("f.loja = ?")
            params.append(loja)
        if ano_mes:
            partes.append("j.ano_mes = ?")
            params.append(ano_mes)
        if condicao_extra:
            partes.append(condicao_extra)

        where = ("WHERE " + " AND ".join(partes)) if partes else ""
        return where, params

    def _converter_mes_para_sql(self, mes_ano: str | None) -> str | None:
        if not mes_ano:
            return None
        p = mes_ano.split("/")
        return f"{p[1]}-{p[0]}"

    # ─────────────────────────────────────────────────────────────────────────
    # FILTROS
    # ─────────────────────────────────────────────────────────────────────────

    def buscar_filtros_disponiveis(self) -> dict:
        conn = self._conectar()
        try:
            lojas = pd.read_sql_query(
                "SELECT DISTINCT loja FROM funcionarios WHERE loja IS NOT NULL ORDER BY loja", conn
            )["loja"].tolist()

            meses_raw = pd.read_sql_query(
                "SELECT DISTINCT ano_mes FROM jornadas ORDER BY ano_mes", conn
            )["ano_mes"].tolist()

            return {"lojas": lojas, "meses": [f"{m[5:7]}/{m[:4]}" for m in meses_raw]}
        finally:
            conn.close()

    # ─────────────────────────────────────────────────────────────────────────
    # DASHBOARD — orquestrador
    # ─────────────────────────────────────────────────────────────────────────

    def buscar_dados_dashboard(self, loja: str | None = None, mes_ano: str | None = None) -> dict:
        conn    = self._conectar()
        ano_mes = self._converter_mes_para_sql(mes_ano)
        try:
            return {
                "kpis":                self.calcular_kpis(conn, loja, ano_mes),
                "intervalos":          self.buscar_intervalos_irregulares(conn, loja, ano_mes),
                "faltas":              self.buscar_faltas_de_marcacao(conn, loja, ano_mes),
                "menores":             self.buscar_jornadas_irregulares_de_menores(conn, loja, ano_mes),
                "jornadas_longas":     self.buscar_jornadas_acima_de_10h(conn, loja, ano_mes),
                "total_validado":      self.contar_jornadas_sem_irregularidade(conn, loja, ano_mes),
                "distribuicao":        self.calcular_distribuicao_jornadas(conn, loja, ano_mes),
                "horas_extras":        self.calcular_evolucao_horas_extras(conn, loja, ano_mes),
                "irregularidades":     self.contar_irregularidades_por_tipo(conn, loja, ano_mes),
                "top5":                self.buscar_top5_por_tipo_de_irregularidade(conn, loja, ano_mes),
                "interjornada":        self.buscar_dados_interjornada(conn, loja, ano_mes),
            }
        finally:
            conn.close()

    # ─────────────────────────────────────────────────────────────────────────
    # KPIs
    # ─────────────────────────────────────────────────────────────────────────

    def calcular_kpis(self, conn, loja, ano_mes) -> dict:
        where, p = self._montar_filtro_sql(loja, ano_mes)

        row = pd.read_sql_query(f"""
            SELECT
                COUNT(DISTINCT j.id_funcionario)                           AS funcionarios,
                SUM(CASE
                        WHEN s.tipo_status IN ('EXTRA','JORNADA_LONGA')
                         AND j.minutos_trabalhados > {MINUTOS_GATILHO_EXTRA}
                        THEN j.minutos_trabalhados - {MINUTOS_JORNADA_NORMAL}
                        ELSE 0
                    END) / 60.0                                            AS horas_extras,
                COUNT(DISTINCT CASE
                        WHEN s.tipo_status IN ('INTERVALO_CURTO','INTERVALO_LONGO')
                        THEN j.id END)                                     AS intervalos_irreg,
                SUM(CASE WHEN s.tipo_status = 'FALTA_DE_MARCACAO'
                        THEN 1 ELSE 0 END)                                AS faltas,
                SUM(CASE WHEN s.tipo_status = 'INTERJORNADA_IRREGULAR'
                        THEN 1 ELSE 0 END)                                AS interjornadas_irreg
            FROM jornadas j
            JOIN funcionarios f ON f.id = j.id_funcionario
            LEFT JOIN status_jornada s ON s.id_jornada = j.id
            {where}
        """, conn, params=p).iloc[0]

        _minutos = round(float(row["horas_extras"] or 0) * 60)

        return {
            "total_funcionarios":              int(row["funcionarios"] or 0),
            "total_horas_extras": f"{_minutos // 60:02d}:{_minutos % 60:02d}",
            "total_intervalos_irregulares":    int(row["intervalos_irreg"] or 0),
            "total_faltas_marcacao":           int(row["faltas"] or 0),
            "total_interjornadas_irregulares": int(row["interjornadas_irreg"] or 0),
        }

    # ─────────────────────────────────────────────────────────────────────────
    # INTERJORNADA — scatter + tabela de irregulares
    # ─────────────────────────────────────────────────────────────────────────

    def buscar_dados_interjornada(self, conn, loja, ano_mes) -> dict | None:
        """
        Retorna dois conjuntos:
        - scatter: todos os pontos de interjornada (data, horas, nome, irregular)
        - tabela:  apenas as interjornadas abaixo de 11h, para exibição detalhada
        """
        where, p = self._montar_filtro_sql(loja, ano_mes, "j.minutos_interjornada IS NOT NULL")

        df = pd.read_sql_query(f"""
            SELECT
                f.nome,
                j.data,
                j.minutos_interjornada
            FROM jornadas j
            JOIN funcionarios f ON f.id = j.id_funcionario
            {where}
            ORDER BY j.data
        """, conn, params=p)

        if df.empty:
            return None

        df["horas_interjornada"] = df["minutos_interjornada"] / 60
        df["irregular"]          = df["minutos_interjornada"] < MINUTOS_INTERJORNADA_MINIMA
        df["data_fmt"]           = pd.to_datetime(df["data"]).dt.strftime("%d/%m")

        # Tabela apenas das irregulares
        df_irreg = df[df["irregular"]].copy()
        df_irreg["Horas"] = df_irreg["horas_interjornada"].apply(
            lambda h: f"{int(h):02d}:{int((h % 1) * 60):02d}"
        )
        df_irreg = df_irreg.rename(columns={"nome": "Nome", "data_fmt": "Data"})

        return {
            # Scatter — todos os pontos
            "scatter_datas":    df["data_fmt"].tolist(),
            "scatter_horas":    [round(h, 2) for h in df["horas_interjornada"].tolist()],
            "scatter_nomes":    df["nome"].tolist(),
            "scatter_irregular":df["irregular"].tolist(),   # bool por ponto

            # Tabela de irregulares
            "tabela": df_irreg[["Nome", "Data", "Horas"]].to_dict(orient="records")
                      if not df_irreg.empty else [],
        }

    # ─────────────────────────────────────────────────────────────────────────
    # DISTRIBUIÇÃO
    # ─────────────────────────────────────────────────────────────────────────

    def calcular_distribuicao_jornadas(self, conn, loja, ano_mes) -> dict | None:
        where, p = self._montar_filtro_sql(loja, ano_mes, "j.minutos_trabalhados > 0")

        df = pd.read_sql_query(f"""
            SELECT
                CASE
                    WHEN minutos_trabalhados <=  440 THEN 'Até 07:20h'
                    WHEN minutos_trabalhados <=  600 THEN '07:20h – 10h'
                    ELSE '>10h'
                END AS faixa,
                COUNT(*) AS total
            FROM jornadas j
            JOIN funcionarios f ON f.id = j.id_funcionario
            {where}
            GROUP BY faixa
        """, conn, params=p)

        if df.empty:
            return None

        ordem  = ["Até 07:20h", "07:20h – 10h", ">10h"]
        lookup = dict(zip(df["faixa"], df["total"]))

        return {
            "labels": ordem,
            "values": [int(lookup.get(f, 0)) for f in ordem],
            "colors": ["#4CAF50", "#ff9800", "#f44336"],
        }

    # ─────────────────────────────────────────────────────────────────────────
    # EVOLUÇÃO DE EXTRAS
    # ─────────────────────────────────────────────────────────────────────────

    def calcular_evolucao_horas_extras(self, conn, loja, ano_mes) -> dict | None:
        where, p = self._montar_filtro_sql(
            loja, ano_mes, "s.tipo_status IN ('EXTRA', 'JORNADA_LONGA')"
        )

        df = pd.read_sql_query(f"""
            SELECT
                j.ano_mes,
                SUM(
                    CASE
                        WHEN j.minutos_trabalhados > {MINUTOS_GATILHO_EXTRA}
                        THEN j.minutos_trabalhados - {MINUTOS_JORNADA_NORMAL}
                        ELSE 0
                    END
                ) / 60.0 AS horas
            FROM jornadas j
            JOIN funcionarios f ON f.id = j.id_funcionario
            JOIN status_jornada s ON s.id_jornada = j.id
            {where}
            GROUP BY j.ano_mes
            ORDER BY j.ano_mes
        """, conn, params=p)

        if df.empty:
            return None

        return {
            "labels": df["ano_mes"].tolist(),
            "values": [round(v, 1) for v in df["horas"].tolist()],
        }

    # ─────────────────────────────────────────────────────────────────────────
    # IRREGULARIDADES POR TIPO
    # ─────────────────────────────────────────────────────────────────────────

    def contar_irregularidades_por_tipo(self, conn, loja, ano_mes) -> dict | None:
        where, p = self._montar_filtro_sql(loja, ano_mes)

        df = pd.read_sql_query(f"""
            SELECT s.tipo_status, COUNT(*) AS total
            FROM jornadas j
            JOIN funcionarios f ON f.id = j.id_funcionario
            JOIN status_jornada s ON s.id_jornada = j.id
            {where}
            GROUP BY s.tipo_status
            ORDER BY total DESC
        """, conn, params=p)

        if df.empty:
            return None

        nomes_legiveis = {
            "FALTA_DE_MARCACAO":           "Falta de Marcação",
            "INTERVALO_CURTO":             "Intervalo Curto",
            "INTERVALO_LONGO":             "Intervalo Longo",
            "JORNADA_LONGA":               "Jornada Longa",
            "JORNADA_6HORAS_SEM_INTERVALO": "Jornada s/ Intervalo",
            "JORNADA_CURTA":               "Jornada Curta",
            "EXTRA":                       "Hora Extra",
            "JORNADA_IRREGULAR_MENOR":     "Menor Irregular",
            "INTERJORNADA_IRREGULAR":      "Interjornada Irregular",
        }
        df["tipo_status"] = df["tipo_status"].replace(nomes_legiveis)

        return {"labels": df["tipo_status"].tolist(), "values": df["total"].tolist()}

    # ─────────────────────────────────────────────────────────────────────────
    # INTERVALOS IRREGULARES
    # ─────────────────────────────────────────────────────────────────────────

    def buscar_intervalos_irregulares(self, conn, loja, ano_mes) -> dict | None:
        where, p = self._montar_filtro_sql(
            loja, ano_mes, "s.tipo_status IN ('INTERVALO_CURTO','INTERVALO_LONGO')"
        )

        df = pd.read_sql_query(f"""
            SELECT s.tipo_status, COUNT(*) AS total
            FROM jornadas j
            JOIN funcionarios f ON f.id = j.id_funcionario
            JOIN status_jornada s ON s.id_jornada = j.id
            {where}
            GROUP BY s.tipo_status
        """, conn, params=p)

        if df.empty:
            return None

        df["tipo_status"] = df["tipo_status"].replace({
            "INTERVALO_CURTO": "Curtos",
            "INTERVALO_LONGO": "Longos",
        })

        total_afetadas = int(df["total"].sum())

        # Base correta para a pizza: jornadas com 4 batidas (única situação onde
        # o intervalo é calculado). Usa filtro só de loja/mês, sem filtro de status.
        where_base, p_base = self._montar_filtro_sql(loja, ano_mes, "j.qtd_batidas = 4")
        total_base = pd.read_sql_query(f"""
            SELECT COUNT(*) AS total
            FROM jornadas j
            JOIN funcionarios f ON f.id = j.id_funcionario
            {where_base}
        """, conn, params=p_base)["total"].iloc[0]

        return {
            "total_intervalos_irregulares": total_afetadas,
            "total_base_intervalo":         int(total_base),
            "labels":                       df["tipo_status"].tolist(),
            "values":                       df["total"].tolist(),
        }

    # ─────────────────────────────────────────────────────────────────────────
    # FALTAS DE MARCAÇÃO
    # ─────────────────────────────────────────────────────────────────────────

    def buscar_faltas_de_marcacao(self, conn, loja, ano_mes) -> dict | None:
        where, p = self._montar_filtro_sql(loja, ano_mes, "s.tipo_status = 'FALTA_DE_MARCACAO'")

        df_datas = pd.read_sql_query(f"""
            SELECT j.data, COUNT(*) AS total
            FROM jornadas j
            JOIN funcionarios f ON f.id = j.id_funcionario
            JOIN status_jornada s ON s.id_jornada = j.id
            {where}
            GROUP BY j.data ORDER BY j.data
        """, conn, params=p)

        df_top = pd.read_sql_query(f"""
            SELECT f.nome, COUNT(*) AS total
            FROM jornadas j
            JOIN funcionarios f ON f.id = j.id_funcionario
            JOIN status_jornada s ON s.id_jornada = j.id
            {where}
            GROUP BY f.nome ORDER BY total DESC LIMIT 5
        """, conn, params=p)

        if df_datas.empty:
            return None

        df_datas["data"] = pd.to_datetime(df_datas["data"]).dt.strftime("%d/%m")

        return {
            "labels_faltas_marcacao":  df_datas["data"].tolist(),
            "values_faltas_marcacao":  df_datas["total"].tolist(),
            "total_faltas":            int(df_datas["total"].sum()),
            "top_funcionarios_labels": df_top["nome"].tolist(),
            "top_funcionarios_values": df_top["total"].tolist(),
        }

    # ─────────────────────────────────────────────────────────────────────────
    # JORNADAS SEM IRREGULARIDADE
    # ─────────────────────────────────────────────────────────────────────────

    def contar_jornadas_sem_irregularidade(self, conn, loja, ano_mes) -> dict | None:
        where, p = self._montar_filtro_sql(loja, ano_mes)
        conector  = "AND" if where else "WHERE"

        total = pd.read_sql_query(f"""
            SELECT COUNT(j.id) AS total
            FROM jornadas j
            JOIN funcionarios f ON f.id = j.id_funcionario
            LEFT JOIN status_jornada s ON s.id_jornada = j.id
            {where} {conector} s.id_jornada IS NULL
        """, conn, params=p)["total"].iloc[0]

        return {"Total_validado": int(total)}

    # ─────────────────────────────────────────────────────────────────────────
    # MENORES IRREGULARES
    # ─────────────────────────────────────────────────────────────────────────

    def buscar_jornadas_irregulares_de_menores(self, conn, loja, ano_mes) -> list[dict] | None:
        where, p = self._montar_filtro_sql(
            loja, ano_mes, 's.tipo_status = "JORNADA_IRREGULAR_MENOR"'
        )

        df = pd.read_sql_query(f"""
            SELECT f.nome AS "Nome", j.data AS "Data", f.loja AS "Loja"
            FROM jornadas j
            JOIN funcionarios f ON f.id = j.id_funcionario
            JOIN status_jornada s ON s.id_jornada = j.id
            {where}
            ORDER BY j.data DESC
        """, conn, params=p)

        if df.empty:
            return None

        df["Data"] = pd.to_datetime(df["Data"]).dt.strftime("%d/%m/%Y")
        return df.to_dict(orient="records")

    # ─────────────────────────────────────────────────────────────────────────
    # JORNADAS ACIMA DE 10H
    # ─────────────────────────────────────────────────────────────────────────

    def buscar_jornadas_acima_de_10h(self, conn, loja, ano_mes) -> list[dict] | None:
        where, p = self._montar_filtro_sql(loja, ano_mes, "s.tipo_status = 'JORNADA_LONGA'")

        df = pd.read_sql_query(f"""
            SELECT f.nome AS "Nome", j.data AS "Data",
                   j.minutos_trabalhados AS minutos, f.loja AS "Loja"
            FROM jornadas j
            JOIN funcionarios f ON f.id = j.id_funcionario
            JOIN status_jornada s ON s.id_jornada = j.id
            {where}
            ORDER BY j.minutos_trabalhados DESC
        """, conn, params=p)

        if df.empty:
            return None

        df["Data"]  = pd.to_datetime(df["Data"]).dt.strftime("%d/%m/%Y")
        df["Horas"] = df["minutos"].apply(lambda m: f"{m // 60:02d}:{m % 60:02d}")
        return df[["Nome", "Data", "Horas", "Loja"]].to_dict(orient="records")

    # ─────────────────────────────────────────────────────────────────────────
    # TOP 5
    # ─────────────────────────────────────────────────────────────────────────

    def buscar_top5_por_tipo_de_irregularidade(self, conn, loja, ano_mes) -> dict:
        categorias = {
            "faltas_marcacao":               "s.tipo_status = 'FALTA_DE_MARCACAO'",
            "extras":                        "s.tipo_status = 'EXTRA'",
            "jornadas_longas":               "s.tipo_status = 'JORNADA_LONGA'",
            "jornadas_longas_sem_intervalo": "s.tipo_status = 'JORNADA_6HORAS_SEM_INTERVALO'",
            "intervalos_irregulares":        "s.tipo_status IN ('INTERVALO_CURTO','INTERVALO_LONGO')",
            "interjornada_irregular":        "s.tipo_status = 'INTERJORNADA_IRREGULAR'",
        }

        resultado = {}
        for chave, condicao in categorias.items():
            where, p = self._montar_filtro_sql(loja, ano_mes, condicao)
            df = pd.read_sql_query(f"""
                SELECT f.nome, COUNT(*) AS total
                FROM jornadas j
                JOIN funcionarios f ON f.id = j.id_funcionario
                JOIN status_jornada s ON s.id_jornada = j.id
                {where}
                GROUP BY f.nome ORDER BY total DESC LIMIT 5
            """, conn, params=p)

            resultado[chave] = {
                "labels": df["nome"].tolist() if not df.empty else [],
                "values": df["total"].tolist() if not df.empty else [],
            }

        return resultado