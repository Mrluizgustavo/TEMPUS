import sqlite3
import os
import pandas as pd
from datetime import datetime
from .processador import ResultadoJornada


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

        # ESTRUTURA BLINDADA (Wide Table)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS jornadas_analiticas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                nome TEXT,
                chapa TEXT,
                data_inicio DATE,
                dia_semana TEXT,

                status TEXT,
                tem_erro BOOLEAN,

                horas_trabalhadas REAL,
                tempo_intervalo REAL,
                
                log_batidas_originais TEXT,
                
                data_processamento TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                UNIQUE(chapa, data_inicio) ON CONFLICT REPLACE
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_data ON jornadas_analiticas(data_inicio)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_nome ON jornadas_analiticas(nome)")

        conn.commit()
        conn.close()

    def salvar_jornadas(self, resultados: list[ResultadoJornada]):
        conn = self._conectar()
        cursor = conn.cursor()

        print(f"Salvando {len(resultados)} registros no histórico...")

        for r in resultados:
            # 1. Preparação
            tem_erro = 1 if "OK" not in r.status.upper() else 0

            try:
                h, m = map(int, r.duracao.split(':'))
                duracao_decimal = h + (m / 60)
            except:
                duracao_decimal = 0.0

            # 2. Separação das Batidas
            e1, s1, e2, s2 = None, None, None, None
            log_extra = None

            qtd = len(r.batidas)

            if qtd >= 1: e1 = r.batidas[0]
            if qtd >= 2: s1 = r.batidas[1]
            if qtd >= 3: e2 = r.batidas[2]
            if qtd >= 4: s2 = r.batidas[3]

            if qtd > 4 or tem_erro:
                log_extra = ", ".join(r.batidas)

            try:
                dia_sem = pd.to_datetime(r.data_inicio_str).day_name()
            except:
                dia_sem = ""

            chapa_valor = getattr(r, 'chapa', None)

            # 3. INSERT (Agora os nomes batem com o CREATE acima)
            cursor.execute("""
                INSERT INTO jornadas_analiticas 
                (nome, chapa, data_inicio, dia_semana, status, duracao_decimal, qtd_batidas, tem_erro,
                 entrada_1, saida_1, entrada_2, saida_2, batidas_extra_log)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                r.nome, chapa_valor, r.data_inicio_str, dia_sem, r.status, duracao_decimal, qtd, tem_erro,
                e1, s1, e2, s2, log_extra
            ))

        conn.commit()
        conn.close()
        print("✅ Dados salvos com sucesso!")

    def obter_kpis_dashboard(self):
        conn = self._conectar()
        # Busca apenas as colunas necessárias
        query = "SELECT status, nome FROM jornadas_analiticas"

        try:
            df = pd.read_sql_query(query, conn)
        except:
            conn.close()
            return None

        conn.close()

        if df.empty:
            return None

        df["tipo"] = df["status"].apply(lambda x: "OK" if "OK" in str(x).upper() else "Irregular")

        return {
            "total": len(df),
            "status_pie": df["tipo"].value_counts().to_dict(),
            "top_5_erros": df[df["tipo"] == "Irregular"]["nome"].value_counts().head(5).to_dict()
        }