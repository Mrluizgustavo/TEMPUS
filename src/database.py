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
        conn = self._conectar()
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

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_data ON jornadas(data)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_nome ON jornadas(nome)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_status_composto ON status_jornada(tipo_status, id_jornada)")

        conn.commit()
        conn.close()

    def salvar_jornadas(self, resultados: list[ResultadoJornada]):
        conn = self._conectar()
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

            data_obj = datetime.strptime(r.data_inicio_str, "%Y-%m-%d")
            dia_semana = data_obj.strftime("%A")

            cursor.execute("""
                INSERT INTO jornadas
                (nome, chapa, idade, loja, data, dia_semana, qtd_batidas, horas_trabalhadas,
                 tempo_intervalo)
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
                dia_semana, len(r.batidas),
                duracao_decimal, r.intervalo
            ))

            id_jornada = cursor.fetchone()[0]

            cursor.execute("""DELETE FROM status_jornada WHERE id_jornada = ?""", (id_jornada,))

            for status in r.status:
                if status != "OK":
                    cursor.execute("""
                                    INSERT INTO status_jornada
                                    (id_jornada, tipo_status)
                                    VALUES (?, ?)
                                """, (
                        id_jornada, status
                    ))

        conn.commit()
        conn.close()
        print("✅ Dados salvos com sucesso!")

    # ─────────────────────────────────────────────────────────────────────────
    # DASHBOARD — ORQUESTRADOR
    # ─────────────────────────────────────────────────────────────────────────

    def obter_dados_dashboard(self):
        conn = self._conectar()
        try:
            dados = {
                "kpis":           self.obter_kpis(conn),
                "intervalos":     self.obter_dados_intervalos(conn),
                "faltas":         self.obter_dados_faltas(conn),
                "menores":        self.obter_dados_menores(conn),
                "total_validado": self.obter_jornadas_validadas(conn),
                "distribuicao":   self.obter_distribuicao_jornada(conn),
                "horas_extras":   self.obter_evolucao_horas_extras(conn),
                "irregularidades":self.obter_irregularidades_por_tipo(conn),
            }
            return dados
        finally:
            conn.close()

    # ─────────────────────────────────────────────────────────────────────────
    # KPI CARDS
    # ─────────────────────────────────────────────────────────────────────────

    def obter_kpis(self, conn):
        """
        Retorna os 4 números dos cards do topo:
        - total de funcionários distintos
        - total de horas extras acumuladas
        - total de jornadas com intervalo irregular
        - total de faltas de marcação
        """

        # Funcionários distintos
        df_func = pd.read_sql_query(
            "SELECT COUNT(DISTINCT nome) as total FROM jornadas", conn
        )
        total_funcionarios = int(df_func["total"].iloc[0])

        # Horas extras: soma de horas_trabalhadas que excedem 7h35 (7.583h)
        # Consideramos extra o excedente acima de 7h35 por jornada
        df_extra = pd.read_sql_query("""
            SELECT j.horas_trabalhadas
            FROM jornadas j
            INNER JOIN status_jornada s ON s.id_jornada = j.id
            WHERE s.tipo_status IN ('EXTRA', 'JORNADA_LONGA')
        """, conn)

        if df_extra.empty:
            total_horas_extras = 0.0
        else:
            # Excedente acima de 7h35 por jornada
            excedente = (df_extra["horas_trabalhadas"] - 7.583).clip(lower=0)
            total_horas_extras = round(excedente.sum(), 1)

        # Intervalos irregulares (jornadas únicas afetadas)
        df_int = pd.read_sql_query("""
            SELECT COUNT(DISTINCT id_jornada) as total
            FROM status_jornada
            WHERE tipo_status IN ('INTERVALO_CURTO', 'INTERVALO_LONGO')
        """, conn)
        total_intervalos = int(df_int["total"].iloc[0])

        # Faltas de marcação
        df_faltas = pd.read_sql_query("""
            SELECT COUNT(*) as total
            FROM status_jornada
            WHERE tipo_status = 'FALTA_DE_MARCACAO'
        """, conn)
        total_faltas = int(df_faltas["total"].iloc[0])

        return {
            "total_funcionarios": total_funcionarios,
            "total_horas_extras": total_horas_extras,
            "total_intervalos_irregulares": total_intervalos,
            "total_faltas_marcacao": total_faltas,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # DISTRIBUIÇÃO DE JORNADA (barras empilhadas)
    # ─────────────────────────────────────────────────────────────────────────

    def obter_distribuicao_jornada(self, conn):
        """
        Classifica cada jornada em 3 faixas:
        - Até 8h
        - 8h – 10h
        - Acima de 10h
        Retorna contagem por faixa.
        """
        df = pd.read_sql_query(
            "SELECT horas_trabalhadas FROM jornadas WHERE horas_trabalhadas > 0", conn
        )

        if df.empty:
            return None

        faixas = pd.cut(
            df["horas_trabalhadas"],
            bins=[0, 8, 10, float("inf")],
            labels=["Até 8h", "8h – 10h", ">10h"],
            right=True
        )

        contagem = faixas.value_counts().reindex(["Até 8h", "8h – 10h", ">10h"], fill_value=0)

        return {
            "labels": contagem.index.tolist(),
            "values": contagem.values.tolist(),
            # Cores semânticas: verde / amarelo / vermelho
            "colors": ["#4CAF50", "#ff9800", "#f44336"],
        }

    # ─────────────────────────────────────────────────────────────────────────
    # EVOLUÇÃO DE HORAS EXTRAS POR MÊS (linha)
    # ─────────────────────────────────────────────────────────────────────────

    def obter_evolucao_horas_extras(self, conn):
        """
        Agrupa por mês o total de horas extras (excedente > 7h35).
        Retorna labels de mês e valores acumulados.
        """
        df = pd.read_sql_query("""
            SELECT
                j.data,
                j.horas_trabalhadas
            FROM jornadas j
            INNER JOIN status_jornada s ON s.id_jornada = j.id
            WHERE s.tipo_status IN ('EXTRA', 'JORNADA_LONGA')
        """, conn)

        if df.empty:
            return None

        df["data"] = pd.to_datetime(df["data"])
        df["excedente"] = (df["horas_trabalhadas"] - 7.583).clip(lower=0)
        df["mes"] = df["data"].dt.to_period("M")

        agrupado = df.groupby("mes")["excedente"].sum().reset_index()
        agrupado = agrupado.sort_values("mes")

        return {
            "labels": agrupado["mes"].astype(str).tolist(),          # "2025-01"
            "values": [round(v, 1) for v in agrupado["excedente"].tolist()],
        }

    # ─────────────────────────────────────────────────────────────────────────
    # IRREGULARIDADES POR TIPO (barra horizontal)
    # ─────────────────────────────────────────────────────────────────────────

    def obter_irregularidades_por_tipo(self, conn):
        """
        Conta ocorrências de cada tipo de status (exceto OK).
        Usado para o gráfico de barras horizontais de qualidade de marcação.
        """
        df = pd.read_sql_query("""
            SELECT tipo_status, COUNT(*) as total
            FROM status_jornada
            GROUP BY tipo_status
            ORDER BY total DESC
        """, conn)

        if df.empty:
            return None

        # Traduz os tipos para rótulos legíveis
        traducao = {
            "FALTA_DE_MARCACAO":        "Falta de Marcação",
            "INTERVALO_CURTO":          "Intervalo Curto",
            "INTERVALO_LONGO":          "Intervalo Longo",
            "JORNADA_LONGA":            "Jornada Longa",
            "JORNADA_LONGA_SEM_INTERVALO": "Jornada s/ Intervalo",
            "JORNADA_CURTA":            "Jornada Curta",
            "EXTRA":                    "Hora Extra",
            "JORNADA_IRREGULAR_MENOR":  "Menor Irregular",
        }

        df["tipo_status"] = df["tipo_status"].replace(traducao)

        return {
            "labels": df["tipo_status"].tolist(),
            "values": df["total"].tolist(),
        }

    # ─────────────────────────────────────────────────────────────────────────
    # MÉTODOS EXISTENTES (mantidos sem alteração)
    # ─────────────────────────────────────────────────────────────────────────

    def obter_dados_menores(self, conn):
        query = """
            SELECT
                j.id,
                j.nome,
                s.tipo_status
            FROM jornadas j
            INNER JOIN status_jornada s ON s.id_jornada = j.id
            WHERE s.tipo_status = "JORNADA_IRREGULAR_MENOR"
        """
        df = pd.read_sql_query(query, conn)

        if df.empty:
            return None

        nomes_count = df["nome"].value_counts().head(5)

        return {
            "labels_menores": nomes_count.index.tolist(),
            "values_menores": nomes_count.values.tolist()
        }

    def obter_jornadas_validadas(self, conn):
        query = """
            SELECT
                COUNT(j.id) as total
            FROM jornadas j
            LEFT JOIN status_jornada s ON s.id_jornada = j.id
            WHERE s.id_jornada IS NULL
            """

        df = pd.read_sql_query(query, conn)

        if df.empty:
            return None

        total = df["total"].iloc[0]

        return {
            "Total_validado": total
        }

    def obter_dados_intervalos(self, conn):
        query = """
            SELECT 
                j.id,
                j.nome,
                s.tipo_status
            FROM jornadas j
            INNER JOIN status_jornada s ON s.id_jornada = j.id
            WHERE s.tipo_status IN ('INTERVALO_CURTO', 'INTERVALO_LONGO')
        """

        df = pd.read_sql_query(query, conn)

        if df.empty:
            return None

        mapeamento_nomes = {
            'INTERVALO_CURTO': 'Curtos',
            'INTERVALO_LONGO': 'Longos'
        }

        df["tipo_status"] = df["tipo_status"].replace(mapeamento_nomes)

        total_jornadas_afetadas = df["id"].nunique()
        tipos_counts = df["tipo_status"].value_counts()

        return {
            "total_intervalos_irregulares": total_jornadas_afetadas,
            "labels": tipos_counts.index.tolist(),
            "values": tipos_counts.values.tolist(),
        }

    def obter_dados_faltas(self, conn):
        query = """
            SELECT
                j.nome,
                DATE(j.data) as data
            FROM jornadas j
            INNER JOIN status_jornada s ON s.id_jornada = j.id
            WHERE s.tipo_status = 'FALTA_DE_MARCACAO'
        """

        df = pd.read_sql_query(query, conn)

        if df.empty:
            return None

        df["data"] = pd.to_datetime(df["data"])
        faltas_grouped = df.groupby("data").size().reset_index(name="total")
        faltas_grouped = faltas_grouped.sort_values("data")

        nomes_count = df["nome"].value_counts().head(5)

        return {
            "labels_faltas_marcacao": faltas_grouped["data"].dt.strftime("%d/%m").tolist(),
            "values_faltas_marcacao": faltas_grouped["total"].tolist(),
            "total_faltas": int(faltas_grouped["total"].sum()),
            "top_funcionarios_labels": nomes_count.index.tolist(),
            "top_funcionarios_values": nomes_count.values.tolist()
        }