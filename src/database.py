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

        #ATIVA A FOREIGN KEY
        conn.execute("PRAGMA foreign_keys = ON")


        print(f"Salvando {len(resultados)} registros no histórico...")

        for r in resultados:

            #formata a duração para decimal
            try:
                h, m = map(int, r.duracao.split(':'))
                duracao_decimal = h + (m / 60)
            except:
                duracao_decimal = 0.0

            chapa_valor = getattr(r, 'chapa', None)


            data_obj = datetime.strptime(r.data_inicio_str, "%Y-%m-%d")
            dia_semana = data_obj.strftime("%A")



            # INSERT
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
                r.nome, chapa_valor, r.idade,r.loja, r.data_inicio_str,
                dia_semana, len(r.batidas),
                duracao_decimal,r.intervalo
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

    def obter_dados_dashboard(self):

        conn = self._conectar()

        try:
            dados = {
                "intervalos": self.obter_dados_intervalos(conn),
                "faltas": self.obter_dados_faltas(conn),
                "menores": self.obter_dados_menores(conn),
                "total_validado": self.obter_jornadas_validadas(conn)
            }
            return dados
        finally:
            conn.close()

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


        if df.empty: return None

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

        if df.empty: return None


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

        if df.empty:return None

        mapeamento_nomes = {
            'INTERVALO_CURTO': 'Curtos',
            'INTERVALO_LONGO': 'Longos'
        }

        #MUDA O NOME DAS LABELS
        df["tipo_status"] = df["tipo_status"].replace(mapeamento_nomes)


        total_jornadas_afetadas = df["id"].nunique()
        tipos_counts = df["tipo_status"].value_counts()

        return {
            "total_intervalos_irregulares": total_jornadas_afetadas,

            # Gráfico de barras (curto x longo)
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

        if df.empty:return None

        #AGRUPANDO POR DATA
        #CONTANDO QUANTIDADES E CRIANDO NOVO ÍNDICE "TOTAL"
        df["data"] = pd.to_datetime(df["data"])
        faltas_grouped = df.groupby("data").size().reset_index(name="total")
        faltas_grouped = faltas_grouped.sort_values("data")

        #TOP 5 FUNCIONARIOS COM FALTAS DE MARCAÇÕES
        nomes_count = df["nome"].value_counts().head(5)

        return {
            "labels_faltas_marcacao": faltas_grouped["data"].dt.strftime("%d/%m").tolist(),
            "values_faltas_marcacao": faltas_grouped["total"].tolist(),
            "total_faltas": int(faltas_grouped["total"].sum()),
            "top_funcionarios_labels": nomes_count.index.tolist(),
            "top_funcionarios_values": nomes_count.values.tolist()
        }

