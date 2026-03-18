import customtkinter as ctk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.patches as mpatches

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────

COR_FUNDO    = "#2b2b2b"
COR_AZUL     = "#1f77b4"
COR_VERDE    = "#4CAF50"
COR_AMARELO  = "#ff9800"
COR_VERMELHO = "#f44336"
COR_ROXO     = "#9c27b0"

DPI = 80   # Reduzido de 100 — menos memória, renderização mais rápida

HORAS_MINIMAS_INTERJORNADA = 11

COR_RISCO = {
    "Baixo":  "#2e7d32",
    "Médio":  "#e65100",
    "Alto":   "#b71c1c",
}

TOP5_OPCOES_E_CHAVES = {
    "Faltas de Marcação":     "faltas_marcacao",
    "Intervalos Irregulares": "intervalos_irregulares",
    "Horas Extras":           "extras",
    "Jornadas Longas":        "jornadas_longas",
    "Jornadas s/ Intervalo":  "jornadas_longas_sem_intervalo",
    "Interjornada Irregular": "interjornada_irregular",
}

TOP5_COR_POR_OPCAO = {
    "Faltas de Marcação":     COR_VERMELHO,
    "Intervalos Irregulares": COR_AMARELO,
    "Horas Extras":           COR_AZUL,
    "Jornadas Longas":        COR_VERMELHO,
    "Jornadas s/ Intervalo":  COR_AMARELO,
    "Interjornada Irregular": COR_VERMELHO,
}


class DashboardWindow(ctk.CTkFrame):

    def __init__(self, parent, controller, dados):
        super().__init__(parent, fg_color="transparent")
        self.controller  = controller
        self.dados       = dados
        # Controla quais abas já foram renderizadas (lazy loading)
        self._abas_renderizadas: set[str] = set()
        self._construir_layout()

    # ─────────────────────────────────────────────────────────────────────────
    # ESTRUTURA — CTkTabview com 3 abas
    # ─────────────────────────────────────────────────────────────────────────

    def _construir_layout(self):
        ctk.CTkLabel(
            self, text="DASHBOARD DE GESTÃO",
            font=("Roboto", 20, "bold")
        ).pack(pady=(15, 5))

        if not self.dados:
            ctk.CTkLabel(self, text="Nenhum dado disponível.",
                         text_color="gray").pack(pady=40)
            return

        self.tabview = ctk.CTkTabview(self, fg_color="#1e1e1e")
        self.tabview.pack(expand=True, fill="both", padx=10, pady=5)

        self.tabview.add("📊 Visão Geral")
        self.tabview.add("⚖ Risco Trabalhista")
        self.tabview.add("🏆 Ranking")

        # Renderiza a primeira aba imediatamente
        self._renderizar_aba_visao_geral()

        # As outras duas são construídas apenas quando o usuário clicar
        self.tabview.configure(command=self._ao_trocar_aba)

    def _ao_trocar_aba(self):
        aba_atual = self.tabview.get()

        if aba_atual == "⚖ Risco Trabalhista" and "risco" not in self._abas_renderizadas:
            self._renderizar_aba_risco_trabalhista()
            self._abas_renderizadas.add("risco")

        elif aba_atual == "🏆 Ranking" and "ranking" not in self._abas_renderizadas:
            self._renderizar_aba_ranking()
            self._abas_renderizadas.add("ranking")

    # ─────────────────────────────────────────────────────────────────────────
    # ABA 1 — VISÃO GERAL
    # ─────────────────────────────────────────────────────────────────────────

    def _renderizar_aba_visao_geral(self):
        self._abas_renderizadas.add("geral")
        parent = ctk.CTkScrollableFrame(
            self.tabview.tab("📊 Visão Geral"), fg_color="transparent"
        )
        parent.pack(expand=True, fill="both")

        self._construir_cards_kpi(parent)

        linha1 = self._criar_linha(parent)
        self._grafico_pizza_intervalos(
            ctk.CTkFrame(linha1), self.dados.get("intervalos"), self.dados.get("total_validado")
        )
        self._grafico_barras_distribuicao_jornada(
            ctk.CTkFrame(linha1), self.dados.get("distribuicao")
        )

        linha2 = self._criar_linha(parent)
        self._grafico_linha_evolucao_extras(
            ctk.CTkFrame(linha2), self.dados.get("horas_extras")
        )
        self._grafico_barras_irregularidades_por_tipo(
            ctk.CTkFrame(linha2), self.dados.get("irregularidades")
        )

    # ─────────────────────────────────────────────────────────────────────────
    # ABA 2 — RISCO TRABALHISTA
    # ─────────────────────────────────────────────────────────────────────────

    def _renderizar_aba_risco_trabalhista(self):
        parent = ctk.CTkScrollableFrame(
            self.tabview.tab("⚖ Risco Trabalhista"), fg_color="transparent"
        )
        parent.pack(expand=True, fill="both")

        # Card de score de risco — ocupa toda a largura no topo
        self._card_score_de_risco(parent, self.dados.get("risco"))

        # Scatter de interjornada + tabela de irregulares
        linha1 = self._criar_linha(parent)
        self._grafico_scatter_interjornada(
            ctk.CTkFrame(linha1), self.dados.get("interjornada")
        )
        self._tabela_interjornadas_irregulares(
            ctk.CTkFrame(linha1), self.dados.get("interjornada")
        )

        # Jornadas longas — tabela largura total
        linha2 = self._criar_linha(parent)
        self._tabela_jornadas_acima_10h(
            ctk.CTkFrame(linha2), self.dados.get("jornadas_longas")
        )

        # Faltas de marcação + menores
        linha3 = self._criar_linha(parent)
        self._grafico_linha_faltas_marcacao(
            ctk.CTkFrame(linha3), self.dados.get("faltas")
        )
        self._tabela_menores_irregulares(
            ctk.CTkFrame(linha3), self.dados.get("menores")
        )

    # ─────────────────────────────────────────────────────────────────────────
    # ABA 3 — RANKING
    # ─────────────────────────────────────────────────────────────────────────

    def _renderizar_aba_ranking(self):
        parent = ctk.CTkScrollableFrame(
            self.tabview.tab("🏆 Ranking"), fg_color="transparent"
        )
        parent.pack(expand=True, fill="both")

        # Gráfico de barras do ranking de risco por funcionário
        linha1 = self._criar_linha(parent)
        self._grafico_barras_ranking_por_risco(
            ctk.CTkFrame(linha1), self.dados.get("ranking")
        )
        self._tabela_ranking_de_funcionarios(
            ctk.CTkFrame(linha1), self.dados.get("ranking")
        )

        # Top 5 selecionável
        linha2 = self._criar_linha(parent)
        self._grafico_top5_com_seletor(
            ctk.CTkFrame(linha2), self.dados.get("top5")
        )

    # ─────────────────────────────────────────────────────────────────────────
    # HELPERS DE LAYOUT
    # ─────────────────────────────────────────────────────────────────────────

    def _criar_linha(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", pady=5)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=1)
        return frame

    def _exibir_mensagem_sem_dados(self, master, texto):
        ctk.CTkLabel(master, text=texto, font=("Roboto", 13, "italic"),
                     text_color="gray").pack(expand=True, pady=20)

    def _renderizar_grafico_no_frame(self, figura, frame_destino):
        canvas = FigureCanvasTkAgg(figura, master=frame_destino)
        canvas.draw()
        canvas.get_tk_widget().pack(expand=True, fill="both", padx=5, pady=5)
        return canvas

    def _criar_figura_escura(self, largura=4, altura=3):
        # DPI reduzido para 80 — renderiza mais rápido sem perda visual perceptível
        return Figure(figsize=(largura, altura), dpi=DPI, facecolor=COR_FUNDO)

    def _configurar_eixo_escuro(self, figura):
        ax = figura.add_subplot(111)
        ax.patch.set_facecolor(COR_FUNDO)
        ax.tick_params(axis="x", colors="white", labelsize=8)
        ax.tick_params(axis="y", colors="white", labelsize=8)
        for spine in ax.spines.values():
            spine.set_visible(False)
        return ax

    def _criar_tooltip(self, ax):
        t = ax.annotate("", xy=(0, 0), xytext=(10, 10), textcoords="offset points",
                        bbox=dict(boxstyle="round", fc="white", ec="black", alpha=0.9),
                        fontsize=9, color="black")
        t.set_visible(False)
        return t

    def _registrar_evento_hover(self, canvas, ax, barras, nomes_completos, valores, tooltip):
        def _atualizar(i):
            tooltip.xy = (barras[i].get_x() + barras[i].get_width() / 2, barras[i].get_height())
            tooltip.set_text(f"{nomes_completos[i]}: {valores[i]}")

        def _mover(event):
            vis = tooltip.get_visible()
            if event.inaxes == ax:
                for i, b in enumerate(barras):
                    if b.contains(event)[0]:
                        _atualizar(i)
                        tooltip.set_visible(True)
                        canvas.draw_idle()
                        return
            if vis:
                tooltip.set_visible(False)
                canvas.draw_idle()

        canvas.mpl_connect("motion_notify_event", _mover)

    def _renderizar_tabela_generica(self, parent, registros: list[dict],
                                    total_real: int = 0, altura: int = 200):
        if not registros:
            return

        colunas = list(registros[0].keys())
        area    = ctk.CTkScrollableFrame(parent, height=altura, fg_color="transparent")
        area.pack(fill="both", expand=True, padx=8, pady=(0, 2))

        for i, col in enumerate(colunas):
            area.grid_columnconfigure(i, weight=1)
            ctk.CTkLabel(area, text=col, font=("Roboto", 10, "bold"),
                         fg_color="#3a3a3a", corner_radius=4, text_color="#ccc"
                         ).grid(row=0, column=i, padx=2, pady=(2, 1), sticky="ew")

        for li, reg in enumerate(registros, start=1):
            bg = "#2e2e2e" if li % 2 == 0 else "transparent"
            for ci, col in enumerate(colunas):
                ctk.CTkLabel(area, text=str(reg.get(col, "")),
                             font=("Roboto", 10), fg_color=bg,
                             corner_radius=0, text_color="white", anchor="w"
                             ).grid(row=li, column=ci, padx=2, pady=1, sticky="ew")

        if total_real > len(registros):
            ctk.CTkLabel(
                parent,
                text=f"Exibindo 10 de {total_real} registros — veja o relatório completo para todos os casos",
                font=("Roboto", 9, "italic"), text_color="#888"
            ).pack(anchor="e", padx=10, pady=(0, 6))

    # ─────────────────────────────────────────────────────────────────────────
    # KPI CARDS
    # ─────────────────────────────────────────────────────────────────────────

    def _construir_cards_kpi(self, parent):
        kpis = self.dados.get("kpis")

        cards = [
            ("👥 Funcionários\nanalisados",   kpis["total_funcionarios"]              if kpis else "—", "#1565C0"),
            ("⏱ Horas extras\nno período",    f'{kpis["total_horas_extras"]}h'        if kpis else "—", "#6A1B9A"),
            ("🔔 Intervalos\nirregulares",     kpis["total_intervalos_irregulares"]    if kpis else "—", COR_AMARELO),
            ("❌ Faltas de\nmarcação",          kpis["total_faltas_marcacao"]           if kpis else "—", COR_VERMELHO),
            ("🌙 Interjornadas\nirregulares",  kpis["total_interjornadas_irregulares"] if kpis else "—", "#B71C1C"),
        ]

        linha = ctk.CTkFrame(parent, fg_color="transparent")
        linha.pack(fill="x", pady=(5, 10))

        for col, (titulo, valor, cor) in enumerate(cards):
            linha.grid_columnconfigure(col, weight=1)
            card = ctk.CTkFrame(linha, fg_color=cor, corner_radius=12)
            card.grid(row=0, column=col, padx=8, pady=5, sticky="nsew")
            ctk.CTkLabel(card, text=str(valor), font=("Roboto", 28, "bold"),
                         text_color="white").pack(pady=(14, 2))
            ctk.CTkLabel(card, text=titulo, font=("Roboto", 10),
                         text_color="white", justify="center").pack(pady=(0, 14))

    # ─────────────────────────────────────────────────────────────────────────
    # CARD DE SCORE DE RISCO
    # ─────────────────────────────────────────────────────────────────────────

    def _card_score_de_risco(self, parent, dados_risco):
        if not dados_risco:
            return

        score         = dados_risco["score"]
        classificacao = dados_risco["classificacao"]
        detalhes      = dados_risco["detalhes"]
        cor           = COR_RISCO.get(classificacao, "#555")

        container = ctk.CTkFrame(parent, fg_color="#1e1e1e", corner_radius=12)
        container.pack(fill="x", padx=8, pady=(5, 10))

        # Lado esquerdo — número e classificação
        lado_esq = ctk.CTkFrame(container, fg_color="transparent")
        lado_esq.pack(side="left", padx=20, pady=16)

        ctk.CTkLabel(lado_esq, text="Score de Risco Trabalhista",
                     font=("Roboto", 12), text_color="#aaa").pack(anchor="w")
        ctk.CTkLabel(lado_esq, text=str(score),
                     font=("Roboto", 42, "bold"), text_color=cor).pack(anchor="w")
        ctk.CTkLabel(lado_esq, text=f"Risco {classificacao}",
                     font=("Roboto", 14, "bold"), text_color=cor).pack(anchor="w")

        # Separador vertical
        ctk.CTkFrame(container, width=1, fg_color="#444").pack(
            side="left", fill="y", padx=10, pady=10
        )

        # Lado direito — tabela de detalhes
        lado_dir = ctk.CTkFrame(container, fg_color="transparent")
        lado_dir.pack(side="left", fill="both", expand=True, padx=10, pady=12)

        cabecalhos = ["Irregularidade", "Ocorrências", "Peso", "Pontos"]
        for ci, cab in enumerate(cabecalhos):
            lado_dir.grid_columnconfigure(ci, weight=1)
            ctk.CTkLabel(lado_dir, text=cab, font=("Roboto", 9, "bold"),
                         text_color="#aaa").grid(row=0, column=ci, sticky="w", padx=6, pady=(0, 4))

        for li, d in enumerate(detalhes, start=1):
            valores_celula = [d["irregularidade"], d["ocorrencias"], d["peso"], d["pontos"]]
            for ci, val in enumerate(valores_celula):
                cor_txt = COR_VERMELHO if ci == 3 and d["pontos"] > 20 else "white"
                ctk.CTkLabel(lado_dir, text=str(val), font=("Roboto", 10),
                             text_color=cor_txt).grid(row=li, column=ci, sticky="w", padx=6, pady=1)

    # ─────────────────────────────────────────────────────────────────────────
    # GRÁFICO — pizza de intervalos
    # ─────────────────────────────────────────────────────────────────────────

    def _grafico_pizza_intervalos(self, frame, dados_intervalos, dados_total_validado):
        frame.grid(row=0, column=0, padx=8, pady=5, sticky="nsew")

        if not dados_intervalos or not dados_total_validado:
            self._exibir_mensagem_sem_dados(frame, "Sem irregularidades de intervalo")
            return

        figura = self._criar_figura_escura()
        ax     = figura.add_subplot(111)
        ax.patch.set_facecolor(COR_FUNDO)

        labels = list(dados_intervalos["labels"]) + ["Regulares"]
        values = list(dados_intervalos["values"]) + [dados_total_validado["Total_validado"]]
        colors = [COR_AMARELO, COR_VERMELHO, COR_VERDE][:len(labels)]

        _, _, autotexts = ax.pie(
            values, labels=labels, autopct="%1.1f%%", startangle=140,
            colors=colors,
            textprops={"color": "white", "fontsize": 8},
            wedgeprops={"linewidth": 0.5, "edgecolor": COR_FUNDO},
        )
        for at in autotexts:
            at.set_fontsize(7)

        ax.set_title("Intervalos Irregulares x Regulares", fontsize=10, color="white", pad=8)
        self._renderizar_grafico_no_frame(figura, frame)

    # ─────────────────────────────────────────────────────────────────────────
    # GRÁFICO — barras de distribuição de jornada
    # ─────────────────────────────────────────────────────────────────────────

    def _grafico_barras_distribuicao_jornada(self, frame, dados):
        frame.grid(row=0, column=1, padx=8, pady=5, sticky="nsew")

        if not dados:
            self._exibir_mensagem_sem_dados(frame, "Sem dados de distribuição")
            return

        figura = self._criar_figura_escura()
        ax     = self._configurar_eixo_escuro(figura)

        barras = ax.bar(dados["labels"], dados["values"],
                        color=dados["colors"], width=0.5, edgecolor=COR_FUNDO)

        for b, v in zip(barras, dados["values"]):
            ax.text(b.get_x() + b.get_width() / 2,
                    b.get_height() + max(dados["values"]) * 0.02,
                    str(v), ha="center", va="bottom", color="white", fontsize=8)

        ax.set_title("Distribuição de Jornada", fontsize=10, color="white", pad=8)
        ax.set_ylabel("Jornadas", fontsize=8, color="white")
        figura.tight_layout(pad=1.2)
        self._renderizar_grafico_no_frame(figura, frame)

    # ─────────────────────────────────────────────────────────────────────────
    # GRÁFICO — linha de evolução de horas extras
    # ─────────────────────────────────────────────────────────────────────────

    def _grafico_linha_evolucao_extras(self, frame, dados):
        frame.grid(row=0, column=0, padx=8, pady=5, sticky="nsew")

        if not dados:
            self._exibir_mensagem_sem_dados(frame, "Sem horas extras registradas")
            return

        figura = self._criar_figura_escura()
        ax     = self._configurar_eixo_escuro(figura)

        ax.plot(dados["labels"], dados["values"],
                marker="o", color=COR_ROXO, linewidth=2, markersize=5)
        ax.fill_between(dados["labels"], dados["values"], alpha=0.15, color=COR_ROXO)
        ax.set_title("Evolução de Horas Extras", fontsize=10, color="white", pad=8)
        ax.set_xlabel("Mês", fontsize=8, color="white")
        ax.set_ylabel("Horas", fontsize=8, color="white")
        ax.tick_params(axis="x", rotation=45)
        ax.grid(True, linestyle="--", color="#444", alpha=0.6)
        figura.tight_layout(pad=1.2)
        self._renderizar_grafico_no_frame(figura, frame)

    # ─────────────────────────────────────────────────────────────────────────
    # GRÁFICO — barras horizontais de irregularidades por tipo
    # ─────────────────────────────────────────────────────────────────────────

    def _grafico_barras_irregularidades_por_tipo(self, frame, dados):
        frame.grid(row=0, column=1, padx=8, pady=5, sticky="nsew")

        if not dados:
            self._exibir_mensagem_sem_dados(frame, "Sem irregularidades")
            return

        labels = dados["labels"]
        values = dados["values"]
        paleta = {
            "Falta de Marcação":     COR_VERMELHO, "Intervalo Curto":       COR_AMARELO,
            "Intervalo Longo":       COR_AMARELO,  "Jornada Longa":         COR_VERMELHO,
            "Jornada s/ Intervalo":  COR_VERMELHO, "Jornada Curta":         COR_AMARELO,
            "Hora Extra":            COR_AZUL,     "Menor Irregular":       "#e91e63",
            "Interjornada Irregular":"#B71C1C",
        }

        figura = self._criar_figura_escura(4, max(2.5, len(labels) * 0.45))
        ax     = self._configurar_eixo_escuro(figura)

        posicoes = list(range(len(labels)))
        barras   = ax.barh(posicoes, values,
                           color=[paleta.get(l, COR_AZUL) for l in labels],
                           height=0.55, edgecolor=COR_FUNDO)
        ax.set_yticks(posicoes)
        ax.set_yticklabels(labels, fontsize=8)
        ax.invert_yaxis()

        for b, v in zip(barras, values):
            ax.text(b.get_width() + max(values) * 0.02,
                    b.get_y() + b.get_height() / 2,
                    str(v), va="center", color="white", fontsize=8)

        ax.set_title("Irregularidades por Tipo", fontsize=10, color="white", pad=8)
        figura.tight_layout(pad=1.2)
        self._renderizar_grafico_no_frame(figura, frame)

    # ─────────────────────────────────────────────────────────────────────────
    # GRÁFICO — scatter de interjornadas
    # ─────────────────────────────────────────────────────────────────────────

    def _grafico_scatter_interjornada(self, frame, dados):
        frame.grid(row=0, column=0, padx=8, pady=5, sticky="nsew")

        if not dados:
            self._exibir_mensagem_sem_dados(frame, "Sem dados de interjornada")
            return

        datas     = dados["scatter_datas"]
        horas     = dados["scatter_horas"]
        nomes     = dados["scatter_nomes"]
        irregular = dados["scatter_irregular"]
        cores     = [COR_VERMELHO if i else COR_VERDE for i in irregular]

        figura  = self._criar_figura_escura()
        ax      = self._configurar_eixo_escuro(figura)
        x_pos   = list(range(len(datas)))
        scatter = ax.scatter(x_pos, horas, c=cores, s=35, zorder=3, alpha=0.85)

        ax.axhline(y=HORAS_MINIMAS_INTERJORNADA, color=COR_AMARELO,
                   linewidth=1.2, linestyle="--", zorder=2)
        ax.text(len(datas) - 1, HORAS_MINIMAS_INTERJORNADA + 0.3,
                "mín. 11h", color=COR_AMARELO, fontsize=7, ha="right")

        passo = max(1, len(datas) // 8)
        ax.set_xticks(x_pos[::passo])
        ax.set_xticklabels(datas[::passo], rotation=45, fontsize=7)
        ax.set_ylabel("Horas", fontsize=8, color="white")
        ax.set_title("Interjornada por Ocorrência", fontsize=10, color="white", pad=8)
        ax.grid(True, linestyle="--", color="#444", alpha=0.4, zorder=1)

        legenda = [
            mpatches.Patch(color=COR_VERDE,   label="Regular (≥ 11h)"),
            mpatches.Patch(color=COR_VERMELHO, label="Irregular (< 11h)"),
        ]
        ax.legend(handles=legenda, fontsize=7, facecolor=COR_FUNDO,
                  labelcolor="white", framealpha=0.6, loc="upper left")
        figura.tight_layout(pad=1.2)

        canvas  = self._renderizar_grafico_no_frame(figura, frame)
        tooltip = self._criar_tooltip(ax)

        def _mover(event):
            vis = tooltip.get_visible()
            if event.inaxes == ax:
                contido, info = scatter.contains(event)
                if contido and len(info["ind"]) > 0:
                    idx = info["ind"][0]
                    hf  = f"{int(horas[idx]):02d}:{int((horas[idx]%1)*60):02d}"
                    tooltip.xy = (x_pos[idx], horas[idx])
                    tooltip.set_text(f"{nomes[idx]}\n{datas[idx]} — {hf}h")
                    tooltip.set_visible(True)
                    canvas.draw_idle()
                    return
            if vis:
                tooltip.set_visible(False)
                canvas.draw_idle()

        canvas.mpl_connect("motion_notify_event", _mover)

    # ─────────────────────────────────────────────────────────────────────────
    # TABELA — interjornadas irregulares
    # ─────────────────────────────────────────────────────────────────────────

    def _tabela_interjornadas_irregulares(self, frame, dados):
        frame.grid(row=0, column=1, padx=8, pady=5, sticky="nsew")
        ctk.CTkLabel(frame, text="🌙 Interjornadas Irregulares (< 11h)",
                     font=("Roboto", 11, "bold"), text_color=COR_VERMELHO
                     ).pack(anchor="w", padx=10, pady=(8, 4))

        if not dados or not dados.get("tabela"):
            self._exibir_mensagem_sem_dados(frame, "Nenhuma interjornada irregular")
            return

        self._renderizar_tabela_generica(
            frame, dados["tabela"], total_real=dados["total_real"], altura=200
        )

    # ─────────────────────────────────────────────────────────────────────────
    # TABELA — jornadas acima de 10h
    # ─────────────────────────────────────────────────────────────────────────

    def _tabela_jornadas_acima_10h(self, frame, dados):
        frame.grid(row=0, column=0, columnspan=2, padx=8, pady=5, sticky="nsew")
        ctk.CTkLabel(frame, text="🕐 Jornadas Acima de 10 Horas",
                     font=("Roboto", 11, "bold"), text_color=COR_VERMELHO
                     ).pack(anchor="w", padx=10, pady=(8, 4))

        if not dados:
            self._exibir_mensagem_sem_dados(frame, "Nenhuma jornada acima de 10h")
            return

        self._renderizar_tabela_generica(
            frame, dados["registros"], total_real=dados["total_real"], altura=200
        )

    # ─────────────────────────────────────────────────────────────────────────
    # GRÁFICO — linha de faltas de marcação
    # ─────────────────────────────────────────────────────────────────────────

    def _grafico_linha_faltas_marcacao(self, frame, dados):
        frame.grid(row=0, column=0, padx=8, pady=5, sticky="nsew")

        if not dados:
            self._exibir_mensagem_sem_dados(frame, "Sem faltas de marcação")
            return

        figura = self._criar_figura_escura()
        ax     = self._configurar_eixo_escuro(figura)

        ax.plot(dados["labels_faltas_marcacao"], dados["values_faltas_marcacao"],
                marker="o", color=COR_VERMELHO, linewidth=2, markersize=5)
        ax.fill_between(dados["labels_faltas_marcacao"], dados["values_faltas_marcacao"],
                        alpha=0.12, color=COR_VERMELHO)
        ax.set_title("Faltas de Marcação por Data", fontsize=10, color="white", pad=8)
        ax.set_xlabel("Data", fontsize=8, color="white")
        ax.set_ylabel("Quantidade", fontsize=8, color="white")
        ax.tick_params(axis="x", rotation=45)
        ax.grid(True, linestyle="--", color="#444", alpha=0.6)
        figura.tight_layout(pad=1.2)
        self._renderizar_grafico_no_frame(figura, frame)

    # ─────────────────────────────────────────────────────────────────────────
    # TABELA — menores irregulares
    # ─────────────────────────────────────────────────────────────────────────

    def _tabela_menores_irregulares(self, frame, dados):
        frame.grid(row=0, column=1, padx=8, pady=5, sticky="nsew")
        ctk.CTkLabel(frame, text="⚠ Jornada Irregular de Menores",
                     font=("Roboto", 11, "bold"), text_color=COR_AMARELO
                     ).pack(anchor="w", padx=10, pady=(8, 4))

        if not dados:
            self._exibir_mensagem_sem_dados(frame, "Sem registros de menores irregulares")
            return

        self._renderizar_tabela_generica(
            frame, dados["registros"], total_real=dados["total_real"], altura=200
        )

    # ─────────────────────────────────────────────────────────────────────────
    # GRÁFICO — barras de ranking de risco por funcionário
    # ─────────────────────────────────────────────────────────────────────────

    def _grafico_barras_ranking_por_risco(self, frame, dados_ranking):
        frame.grid(row=0, column=0, padx=8, pady=5, sticky="nsew")

        if not dados_ranking:
            self._exibir_mensagem_sem_dados(frame, "Sem dados de ranking")
            return

        labels = dados_ranking["grafico_labels"]
        nomes  = dados_ranking["grafico_nomes"]
        values = dados_ranking["grafico_valores"]

        figura = self._criar_figura_escura(4, 3)
        ax     = self._configurar_eixo_escuro(figura)

        # Gradiente de cor por pontuação — maior = mais vermelho
        max_v  = max(values) if values else 1
        cores  = [
            (COR_AMARELO if v <= max_v * 0.4 else
             "#e65100"   if v <= max_v * 0.7 else
             COR_VERMELHO)
            for v in values
        ]

        barras = ax.bar(range(len(labels)), values, color=cores,
                        width=0.6, tick_label=labels, edgecolor=COR_FUNDO)

        for b, v in zip(barras, values):
            ax.text(b.get_x() + b.get_width() / 2,
                    b.get_height() + max_v * 0.02,
                    str(v), ha="center", va="bottom", color="white", fontsize=8)

        ax.set_title("Risco por Funcionário (pontos)", fontsize=10, color="white", pad=8)
        ax.tick_params(axis="x", colors="white", labelsize=7, rotation=30)
        figura.tight_layout(pad=1.2)

        tooltip = self._criar_tooltip(ax)
        canvas  = self._renderizar_grafico_no_frame(figura, frame)
        self._registrar_evento_hover(canvas, ax, barras, nomes, values, tooltip)

    # ─────────────────────────────────────────────────────────────────────────
    # TABELA — ranking detalhado de funcionários
    # ─────────────────────────────────────────────────────────────────────────

    def _tabela_ranking_de_funcionarios(self, frame, dados_ranking):
        frame.grid(row=0, column=1, padx=8, pady=5, sticky="nsew")
        ctk.CTkLabel(frame, text="🏆 Top 10 — Maior Risco Individual",
                     font=("Roboto", 11, "bold"), text_color=COR_VERMELHO
                     ).pack(anchor="w", padx=10, pady=(8, 4))

        if not dados_ranking:
            self._exibir_mensagem_sem_dados(frame, "Sem dados de ranking")
            return

        self._renderizar_tabela_generica(
            frame, dados_ranking["tabela"],
            total_real=dados_ranking["total_real"], altura=280
        )

    # ─────────────────────────────────────────────────────────────────────────
    # GRÁFICO — top 5 com seletor
    # ─────────────────────────────────────────────────────────────────────────

    def _grafico_top5_com_seletor(self, frame, dados_top5):
        frame.grid(row=0, column=0, columnspan=2, padx=8, pady=5, sticky="nsew")

        if not dados_top5:
            self._exibir_mensagem_sem_dados(frame, "Sem dados para o ranking")
            return

        topo = ctk.CTkFrame(frame, fg_color="transparent")
        topo.pack(fill="x", padx=8, pady=(8, 4))

        ctk.CTkLabel(topo, text="Top 5 — ",
                     font=("Roboto", 11, "bold")).pack(side="left")

        opcoes         = list(TOP5_OPCOES_E_CHAVES.keys())
        self._var_top5 = ctk.StringVar(value=opcoes[0])

        ctk.CTkOptionMenu(
            topo, variable=self._var_top5, values=opcoes, width=240,
            command=lambda _: self._atualizar_grafico_top5(dados_top5)
        ).pack(side="left", padx=6)

        self._frame_top5 = ctk.CTkFrame(frame, fg_color="transparent")
        self._frame_top5.pack(fill="both", expand=True)

        self._atualizar_grafico_top5(dados_top5)

    def _atualizar_grafico_top5(self, dados_top5: dict):
        for w in self._frame_top5.winfo_children():
            w.destroy()

        opcao  = self._var_top5.get()
        chave  = TOP5_OPCOES_E_CHAVES[opcao]
        cor    = TOP5_COR_POR_OPCAO[opcao]
        dados  = dados_top5.get(chave)

        if not dados or not dados["labels"]:
            self._exibir_mensagem_sem_dados(self._frame_top5, f"Sem registros para '{opcao}'")
            return

        nomes  = dados["labels"]
        values = dados["values"]

        figura = self._criar_figura_escura(7, 3)
        ax     = self._configurar_eixo_escuro(figura)

        barras = ax.bar(range(len(nomes)), values, color=cor, width=0.5,
                        tick_label=[n.split()[0] for n in nomes], edgecolor=COR_FUNDO)

        for b, v in zip(barras, values):
            ax.text(b.get_x() + b.get_width() / 2,
                    b.get_height() + max(values) * 0.02,
                    str(v), ha="center", va="bottom", color="white", fontsize=9)

        ax.set_title(f"Top 5 — {opcao}", fontsize=11, color="white", pad=8)
        figura.tight_layout(pad=1.2)

        tooltip = self._criar_tooltip(ax)
        canvas  = self._renderizar_grafico_no_frame(figura, self._frame_top5)
        self._registrar_evento_hover(canvas, ax, barras, nomes, values, tooltip)