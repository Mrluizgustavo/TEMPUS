import sqlite3
import os

import pandas as pd

from src.processador import ResultadoJornada

MINUTOS_JORNADA_NORMAL      = 7 * 60 + 35   # 455 min
MINUTOS_INTERJORNADA_MINIMA = 11 * 60        # 660 min — mínimo legal CLT

# Pesos de risco por tipo de irregularidade (conforme tabela definida)
PESOS_RISCO = {
    "INTERVALO_CURTO":             2,   # Intervalo < 1h
    "JORNADA_SEM_INTERVALO": 4,   # Intervalo inexistente
    "INTERJORNADA_IRREGULAR":      3,   # Descanso < 11h
    "JORNADA_LONGA":               2,   # Jornada > 10h (base)
    # Jornada > 12h recebe peso 4 — tratado separadamente no cálculo
    "JORNADA_IRREGULAR_MENOR":     5,   # Menor após 22h
    # FALTA_DE_MARCACAO removida do score de risco trabalhista
}

# Faixas do score de risco para classificação visual
FAIXA_RISCO_BAIXO  = 50
FAIXA_RISCO_MEDIO  = 150


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
                minutos_interjornada  INTEGER,
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

        cur.execute("CREATE INDEX IF NOT EXISTS idx_func_chapa      ON funcionarios(chapa)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_func_loja       ON funcionarios(loja)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_jornada_func    ON jornadas(id_funcionario)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_jornada_ano_mes ON jornadas(ano_mes)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_status_tipo     ON status_jornada(tipo_status, id_jornada)")

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

        cur.executemany("""
            INSERT INTO funcionarios (chapa, nome, loja, idade)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(chapa) DO UPDATE SET
                nome  = excluded.nome,
                loja  = excluded.loja,
                idade = excluded.idade
        """, [(r.chapa, r.nome, r.loja, r.idade) for r in resultados])

        chapas = list({r.chapa for r in resultados})
        cur.execute(
            f"SELECT chapa, id FROM funcionarios WHERE chapa IN ({','.join('?'*len(chapas))})",
            chapas
        )
        id_por_chapa = dict(cur.fetchall())

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
                # Aba 1 — Visão Geral
                "kpis":            self.calcular_kpis(conn, loja, ano_mes),
                "intervalos":      self.buscar_intervalos_irregulares(conn, loja, ano_mes),
                "distribuicao":    self.calcular_distribuicao_jornadas(conn, loja, ano_mes),
                "horas_extras":    self.calcular_evolucao_horas_extras(conn, loja, ano_mes),
                "irregularidades": self.contar_irregularidades_por_tipo(conn, loja, ano_mes),
                "total_validado":  self.contar_jornadas_sem_irregularidade(conn, loja, ano_mes),

                # Aba 2 — Risco Trabalhista
                "risco":           self.calcular_score_de_risco_trabalhista(conn, loja, ano_mes),
                "interjornada":    self.buscar_dados_interjornada(conn, loja, ano_mes),
                "jornadas_longas": self.buscar_jornadas_acima_de_10h(conn, loja, ano_mes),
                "menores":         self.buscar_jornadas_irregulares_de_menores(conn, loja, ano_mes),
                "faltas":          self.buscar_faltas_de_marcacao(conn, loja, ano_mes),

                # Aba 3 — Ranking
                "top5":            self.buscar_top5_por_tipo_de_irregularidade(conn, loja, ano_mes),
                "ranking":         self.buscar_ranking_de_funcionarios_por_irregularidades(conn, loja, ano_mes),
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
                        THEN MAX(0, j.minutos_trabalhados - {MINUTOS_JORNADA_NORMAL})
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

        return {
            "total_funcionarios":              int(row["funcionarios"] or 0),
            "total_horas_extras":              round(float(row["horas_extras"] or 0), 1),
            "total_intervalos_irregulares":    int(row["intervalos_irreg"] or 0),
            "total_faltas_marcacao":           int(row["faltas"] or 0),
            "total_interjornadas_irregulares": int(row["interjornadas_irreg"] or 0),
        }

    # ─────────────────────────────────────────────────────────────────────────
    # SCORE DE RISCO TRABALHISTA
    # Pesos conforme tabela definida. Jornada > 12h recebe peso 4 (diferente
    # de jornada > 10h que recebe peso 2), calculado pela duração em minutos.
    # ─────────────────────────────────────────────────────────────────────────

    def calcular_score_de_risco_trabalhista(self, conn, loja, ano_mes) -> dict:
        where, p = self._montar_filtro_sql(loja, ano_mes)

        df = pd.read_sql_query(f"""
            SELECT
                s.tipo_status,
                COUNT(*) AS total,
                j.minutos_trabalhados
            FROM jornadas j
            JOIN funcionarios f ON f.id = j.id_funcionario
            JOIN status_jornada s ON s.id_jornada = j.id
            {where}
            GROUP BY s.tipo_status, j.minutos_trabalhados
        """, conn, params=p)

        if df.empty:
            return {"score": 0, "classificacao": "Baixo", "detalhes": []}

        score = 0
        detalhes = []

        for tipo, grupo in df.groupby("tipo_status"):
            # FALTA_DE_MARCACAO não entra no score de risco trabalhista
            if tipo == "FALTA_DE_MARCACAO":
                continue

            # Jornada sem intervalo só é irregularidade acima de 6h trabalhadas (360 min)
            if tipo == "JORNADA_SEM_INTERVALO":
                grupo = grupo[grupo["minutos_trabalhados"] > 360]
                if grupo.empty:
                    continue

            contagem = int(grupo["total"].sum())

            if tipo == "JORNADA_LONGA":
                # Separa > 10h (peso 2) de > 12h (peso 4)
                acima_12h = int(grupo[grupo["minutos_trabalhados"] > 720]["total"].sum())
                entre_10_12h = contagem - acima_12h

                if entre_10_12h > 0:
                    pts = entre_10_12h * 2
                    score += pts
                    detalhes.append(("Jornada > 10h", entre_10_12h, 2, pts))
                if acima_12h > 0:
                    pts = acima_12h * 4
                    score += pts
                    detalhes.append(("Jornada > 12h", acima_12h, 4, pts))
                continue

            peso = PESOS_RISCO.get(tipo)
            if peso is None:
                continue

            pts = contagem * peso
            score += pts

            nomes_legiveis = {
                "INTERVALO_CURTO":             "Intervalo < 1h",
                "JORNADA_SEM_INTERVALO": "JORNADA_SEM_INTERVALO_ACIMA_6H",
                "INTERJORNADA_IRREGULAR":      "Descanso < 11h",
                "JORNADA_IRREGULAR_MENOR":     "Menor após 22h",
            }
            detalhes.append((nomes_legiveis.get(tipo, tipo), contagem, peso, pts))

        # Ordena pelos pontos gerados (maior risco primeiro)
        detalhes.sort(key=lambda x: x[3], reverse=True)

        if score <= FAIXA_RISCO_BAIXO:
            classificacao = "Baixo"
        elif score <= FAIXA_RISCO_MEDIO:
            classificacao = "Médio"
        else:
            classificacao = "Alto"

        return {
            "score":          score,
            "classificacao":  classificacao,
            "detalhes": [
                {"irregularidade": d[0], "ocorrencias": d[1], "peso": d[2], "pontos": d[3]}
                for d in detalhes
            ],
        }

    # ─────────────────────────────────────────────────────────────────────────
    # RANKING DE FUNCIONÁRIOS — pontuação de risco por pessoa
    # ─────────────────────────────────────────────────────────────────────────

    def buscar_ranking_de_funcionarios_por_irregularidades(self, conn, loja, ano_mes) -> dict | None:
        """
        Calcula o score de risco individual de cada funcionário aplicando
        os mesmos pesos do score geral. Retorna top 15 para o gráfico
        e top 10 para a tabela detalhada.
        """
        where, p = self._montar_filtro_sql(loja, ano_mes)

        df = pd.read_sql_query(f"""
            SELECT
                f.nome,
                s.tipo_status,
                COUNT(*) AS total,
                SUM(j.minutos_trabalhados) AS min_trab
            FROM jornadas j
            JOIN funcionarios f ON f.id = j.id_funcionario
            JOIN status_jornada s ON s.id_jornada = j.id
            {where}
            GROUP BY f.nome, s.tipo_status
        """, conn, params=p)

        if df.empty:
            return None

        # Aplica pesos — jornada longa > 12h recebe peso diferenciado
        def calcular_pontos(row):
            tipo = row["tipo_status"]
            n    = row["total"]

            if tipo == "JORNADA_LONGA":
                # Aproximação: usa minutos médios por ocorrência
                min_medio = (row["min_trab"] / n) if n > 0 else 0
                return n * (4 if min_medio > 720 else 2)

            return n * PESOS_RISCO.get(tipo, 0)

        df["pontos"] = df.apply(calcular_pontos, axis=1)

        ranking = (
            df.groupby("nome")["pontos"]
            .sum()
            .reset_index()
            .sort_values("pontos", ascending=False)
        )

        # Contagem de tipos distintos de irregularidade por funcionário
        tipos_por_nome = (
            df[df["pontos"] > 0]
            .groupby("nome")["tipo_status"]
            .nunique()
            .reset_index()
            .rename(columns={"tipo_status": "tipos_distintos"})
        )
        ranking = ranking.merge(tipos_por_nome, on="nome", how="left").fillna(0)
        ranking["tipos_distintos"] = ranking["tipos_distintos"].astype(int)

        top15 = ranking.head(15)
        top10 = ranking.head(10)

        nomes_legiveis = {
            "INTERVALO_CURTO":             "Intervalo < 1h",
            "INTERVALO_LONGO":             "Intervalo Longo",
            "JORNADA_SEM_INTERVALO": "Intervalo inexistente",
            "INTERJORNADA_IRREGULAR":      "Descanso < 11h",
            "JORNADA_LONGA":               "Jornada Longa",
            "JORNADA_IRREGULAR_MENOR":     "Menor após 22h",
            "FALTA_DE_MARCACAO":           "Falta de marcação",
            "EXTRA":                       "Hora Extra",
            "JORNADA_CURTA":               "Jornada Curta",
        }

        # Detalhamento por funcionário — para o painel de clique na tabela
        detalhamento_por_nome: dict[str, list[dict]] = {}
        for nome, grupo in df[df["pontos"] > 0].groupby("nome"):
            itens = (
                grupo[["tipo_status", "total", "pontos"]]
                .sort_values("pontos", ascending=False)
                .to_dict(orient="records")
            )
            detalhamento_por_nome[nome] = [
                {
                    "irregularidade": nomes_legiveis.get(i["tipo_status"], i["tipo_status"]),
                    "ocorrencias":    int(i["total"]),
                    "pontos":         int(i["pontos"]),
                }
                for i in itens
            ]

        return {
            "grafico_labels":         top15["nome"].apply(lambda n: n.split()[0]).tolist(),
            "grafico_nomes":          top15["nome"].tolist(),
            "grafico_valores":        top15["pontos"].astype(int).tolist(),
            "tabela": [
                {
                    "Nome":   row["nome"],
                    "Pontos": int(row["pontos"]),
                    "Tipos":  int(row["tipos_distintos"]),
                }
                for _, row in top10.iterrows()
            ],
            "total_real":             len(ranking),
            "detalhamento_por_nome":  detalhamento_por_nome,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # INTERVALOS IRREGULARES
    # ─────────────────────────────────────────────────────────────────────────

    def buscar_intervalos_irregulares(self, conn, loja, ano_mes) -> dict | None:
        where, p = self._montar_filtro_sql(
            loja, ano_mes, "s.tipo_status IN ('INTERVALO_CURTO','INTERVALO_LONGO')"
        )

        df = pd.read_sql_query(f"""
            SELECT
                s.tipo_status,
                COUNT(*)             AS total,
                COUNT(DISTINCT j.id) AS jornadas_unicas
            FROM jornadas j
            JOIN funcionarios f ON f.id = j.id_funcionario
            JOIN status_jornada s ON s.id_jornada = j.id
            {where}
            GROUP BY s.tipo_status
        """, conn, params=p)

        if df.empty:
            return None

        total_afetadas = int(df["jornadas_unicas"].sum())
        df["tipo_status"] = df["tipo_status"].replace({
            "INTERVALO_CURTO": "Curtos",
            "INTERVALO_LONGO": "Longos",
        })

        return {
            "total_intervalos_irregulares": total_afetadas,
            "labels": df["tipo_status"].tolist(),
            "values": df["total"].tolist(),
        }

    # ─────────────────────────────────────────────────────────────────────────
    # FALTAS DE MARCAÇÃO
    # ─────────────────────────────────────────────────────────────────────────

    def buscar_faltas_de_marcacao(self, conn, loja, ano_mes) -> dict | None:
        where, p = self._montar_filtro_sql(loja, ano_mes, "s.tipo_status = 'FALTA_DE_MARCACAO'")

        df = pd.read_sql_query(f"""
            SELECT f.nome, j.data
            FROM jornadas j
            JOIN funcionarios f ON f.id = j.id_funcionario
            JOIN status_jornada s ON s.id_jornada = j.id
            {where}
            ORDER BY j.data
        """, conn, params=p)

        if df.empty:
            return None

        df["data"] = pd.to_datetime(df["data"])
        por_data   = df.groupby("data").size().reset_index(name="total")
        por_nome   = df.groupby("nome").size().reset_index(name="total") \
                       .sort_values("total", ascending=False).head(5)

        return {
            "labels_faltas_marcacao":  por_data["data"].dt.strftime("%d/%m").tolist(),
            "values_faltas_marcacao":  por_data["total"].tolist(),
            "total_faltas":            int(por_data["total"].sum()),
            "top_funcionarios_labels": por_nome["nome"].tolist(),
            "top_funcionarios_values": por_nome["total"].tolist(),
        }

    # ─────────────────────────────────────────────────────────────────────────
    # TOP 5 — uma query, pivot em Python
    # ─────────────────────────────────────────────────────────────────────────

    def buscar_top5_por_tipo_de_irregularidade(self, conn, loja, ano_mes) -> dict:
        where, p = self._montar_filtro_sql(loja, ano_mes)

        df = pd.read_sql_query(f"""
            SELECT s.tipo_status, f.nome, COUNT(*) AS total
            FROM jornadas j
            JOIN funcionarios f ON f.id = j.id_funcionario
            JOIN status_jornada s ON s.id_jornada = j.id
            {where}
            GROUP BY s.tipo_status, f.nome
            ORDER BY s.tipo_status, total DESC
        """, conn, params=p)

        mapeamento = {
            "FALTA_DE_MARCACAO":           "faltas_marcacao",
            "EXTRA":                       "extras",
            "JORNADA_LONGA":               "jornadas_longas",
            "JORNADA_SEM_INTERVALO": "jornadas_sem_intervalo",
            "INTERVALO_CURTO":             "intervalos_irregulares",
            "INTERVALO_LONGO":             "intervalos_irregulares",
            "INTERJORNADA_IRREGULAR":      "interjornada_irregular",
        }

        resultado = {chave: {"labels": [], "values": []} for chave in set(mapeamento.values())}

        if df.empty:
            return resultado

        df["categoria"] = df["tipo_status"].map(mapeamento)
        df = df.dropna(subset=["categoria"])

        for categoria, grupo in df.groupby("categoria"):
            top = (
                grupo.groupby("nome")["total"].sum()
                .reset_index()
                .sort_values("total", ascending=False)
                .head(5)
            )
            resultado[categoria] = {
                "labels": top["nome"].tolist(),
                "values": top["total"].tolist(),
            }

        return resultado

    # ─────────────────────────────────────────────────────────────────────────
    # INTERJORNADA
    # ─────────────────────────────────────────────────────────────────────────

    def buscar_dados_interjornada(self, conn, loja, ano_mes) -> dict | None:
        where, p = self._montar_filtro_sql(loja, ano_mes, "j.minutos_interjornada IS NOT NULL")

        df = pd.read_sql_query(f"""
            SELECT f.nome, j.data, j.minutos_interjornada
            FROM jornadas j
            JOIN funcionarios f ON f.id = j.id_funcionario
            {where}
            ORDER BY j.data
        """, conn, params=p)

        if df.empty:
            return None

        df["horas"]     = df["minutos_interjornada"] / 60
        df["irregular"] = df["minutos_interjornada"] < MINUTOS_INTERJORNADA_MINIMA
        df["data_fmt"]  = pd.to_datetime(df["data"]).dt.strftime("%d/%m")

        df_irreg          = df[df["irregular"]].copy()
        df_irreg["Horas"] = df_irreg["horas"].apply(lambda h: f"{int(h):02d}:{int((h%1)*60):02d}")
        df_irreg          = df_irreg.rename(columns={"nome": "Nome", "data_fmt": "Data"})

        total_real = len(df_irreg)

        return {
            "scatter_datas":     df["data_fmt"].tolist(),
            "scatter_horas":     [round(h, 2) for h in df["horas"].tolist()],
            "scatter_nomes":     df["nome"].tolist(),
            "scatter_irregular": df["irregular"].tolist(),
            "tabela":            df_irreg[["Nome", "Data", "Horas"]].head(10).to_dict(orient="records")
                                 if not df_irreg.empty else [],
            "total_real":        total_real,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # DISTRIBUIÇÃO DE JORNADA
    # ─────────────────────────────────────────────────────────────────────────

    def calcular_distribuicao_jornadas(self, conn, loja, ano_mes) -> dict | None:
        where, p = self._montar_filtro_sql(loja, ano_mes, "j.minutos_trabalhados > 0")

        df = pd.read_sql_query(f"""
            SELECT
                CASE
                    WHEN minutos_trabalhados <=  480 THEN 'Até 8h'
                    WHEN minutos_trabalhados <=  600 THEN '8h – 10h'
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

        ordem  = ["Até 8h", "8h – 10h", ">10h"]
        lookup = dict(zip(df["faixa"], df["total"]))

        return {
            "labels": ordem,
            "values": [int(lookup.get(f, 0)) for f in ordem],
            "colors": ["#4CAF50", "#ff9800", "#f44336"],
        }

    # ─────────────────────────────────────────────────────────────────────────
    # EVOLUÇÃO DE HORAS EXTRAS
    # ─────────────────────────────────────────────────────────────────────────

    def calcular_evolucao_horas_extras(self, conn, loja, ano_mes) -> dict | None:
        where, p = self._montar_filtro_sql(
            loja, ano_mes, "s.tipo_status IN ('EXTRA','JORNADA_LONGA')"
        )

        df = pd.read_sql_query(f"""
            SELECT
                j.ano_mes,
                SUM(MAX(0, j.minutos_trabalhados - {MINUTOS_JORNADA_NORMAL})) / 60.0 AS horas
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
            "JORNADA_SEM_INTERVALO": "Jornada s/ Intervalo",
            "JORNADA_CURTA":               "Jornada Curta",
            "EXTRA":                       "Hora Extra",
            "JORNADA_IRREGULAR_MENOR":     "Menor Irregular",
            "INTERJORNADA_IRREGULAR":      "Interjornada Irregular",
        }
        df["tipo_status"] = df["tipo_status"].replace(nomes_legiveis)

        return {"labels": df["tipo_status"].tolist(), "values": df["total"].tolist()}

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

    def buscar_jornadas_irregulares_de_menores(self, conn, loja, ano_mes) -> dict | None:
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

        total_real = len(df)
        df         = df.head(10)
        df["Data"] = pd.to_datetime(df["Data"]).dt.strftime("%d/%m/%Y")
        return {"registros": df.to_dict(orient="records"), "total_real": total_real}

    # ─────────────────────────────────────────────────────────────────────────
    # JORNADAS ACIMA DE 10H
    # ─────────────────────────────────────────────────────────────────────────

    def buscar_jornadas_acima_de_10h(self, conn, loja, ano_mes) -> dict | None:
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

        total_real  = len(df)
        df          = df.head(10)
        df["Data"]  = pd.to_datetime(df["Data"]).dt.strftime("%d/%m/%Y")
        df["Horas"] = df["minutos"].apply(lambda m: f"{m // 60:02d}:{m % 60:02d}")
        return {
            "registros":  df[["Nome", "Data", "Horas", "Loja"]].to_dict(orient="records"),
            "total_real": total_real,
        }