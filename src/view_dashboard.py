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

HORAS_MINIMAS_INTERJORNADA = 11  # CLT

TOP5_OPCOES_E_CHAVES = {
    "Faltas de Marcação":      "faltas_marcacao",
    "Intervalos Irregulares":  "intervalos_irregulares",
    "Horas Extras":            "extras",
    "Jornadas Longas":         "jornadas_longas",
    "Jornadas s/ Intervalo":   "jornadas_longas_sem_intervalo",
    "Interjornada Irregular":  "interjornada_irregular",
}

TOP5_COR_POR_OPCAO = {
    "Faltas de Marcação":      COR_VERMELHO,
    "Intervalos Irregulares":  COR_AMARELO,
    "Horas Extras":            COR_AZUL,
    "Jornadas Longas":         COR_VERMELHO,
    "Jornadas s/ Intervalo":   COR_AMARELO,
    "Interjornada Irregular":  COR_VERMELHO,
}


class DashboardWindow(ctk.CTkFrame):

    def __init__(self, parent, controller, dados):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.dados      = dados
        self._construir_layout()

    # ─────────────────────────────────────────────────────────────────────────
    # ESTRUTURA PRINCIPAL
    # ─────────────────────────────────────────────────────────────────────────

    def _construir_layout(self):
        ctk.CTkLabel(
            self, text="DASHBOARD DE GESTÃO",
            font=("Roboto", 20, "bold")
        ).pack(pady=(15, 5))

        area_rolavel = ctk.CTkScrollableFrame(self, fg_color="transparent")
        area_rolavel.pack(expand=True, fill="both", padx=10, pady=5)

        if not self.dados:
            ctk.CTkLabel(area_rolavel, text="Nenhum dado disponível.",
                         text_color="gray").pack(pady=40)
            return

        self._construir_cards_kpi(area_rolavel)

        linha1 = self._criar_linha_de_graficos(area_rolavel)
        self._grafico_pizza_intervalos(
            ctk.CTkFrame(linha1), self.dados.get("intervalos"), self.dados.get("total_validado")
        )
        self._grafico_barras_distribuicao_jornada(
            ctk.CTkFrame(linha1), self.dados.get("distribuicao")
        )

        linha2 = self._criar_linha_de_graficos(area_rolavel)
        self._grafico_linha_evolucao_extras(
            ctk.CTkFrame(linha2), self.dados.get("horas_extras")
        )
        self._grafico_barras_irregularidades_por_tipo(
            ctk.CTkFrame(linha2), self.dados.get("irregularidades")
        )

        linha3 = self._criar_linha_de_graficos(area_rolavel)
        self._grafico_linha_faltas_marcacao(
            ctk.CTkFrame(linha3), self.dados.get("faltas")
        )
        self._tabela_menores_irregulares(
            ctk.CTkFrame(linha3), self.dados.get("menores")
        )

        # Interjornada ocupa linha inteira — scatter à esquerda, tabela à direita
        linha4 = self._criar_linha_de_graficos(area_rolavel)
        self._grafico_scatter_interjornada(
            ctk.CTkFrame(linha4), self.dados.get("interjornada")
        )
        self._tabela_interjornadas_irregulares(
            ctk.CTkFrame(linha4), self.dados.get("interjornada")
        )

        linha5 = self._criar_linha_de_graficos(area_rolavel)
        self._tabela_jornadas_acima_10h(
            ctk.CTkFrame(linha5), self.dados.get("jornadas_longas")
        )

        linha6 = self._criar_linha_de_graficos(area_rolavel)
        self._grafico_top5_com_seletor(
            ctk.CTkFrame(linha6), self.dados.get("top5")
        )

    # ─────────────────────────────────────────────────────────────────────────
    # HELPERS DE LAYOUT
    # ─────────────────────────────────────────────────────────────────────────

    def _criar_linha_de_graficos(self, parent):
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
        return Figure(figsize=(largura, altura), dpi=100, facecolor=COR_FUNDO)

    def _configurar_eixo_escuro(self, figura):
        ax = figura.add_subplot(111)
        ax.patch.set_facecolor(COR_FUNDO)
        ax.tick_params(axis="x", colors="white", labelsize=8)
        ax.tick_params(axis="y", colors="white", labelsize=8)
        for spine in ax.spines.values():
            spine.set_visible(False)
        return ax

    def _criar_tooltip(self, ax):
        tooltip = ax.annotate(
            "", xy=(0, 0), xytext=(10, 10), textcoords="offset points",
            bbox=dict(boxstyle="round", fc="white", ec="black", alpha=0.9),
            fontsize=9, color="black"
        )
        tooltip.set_visible(False)
        return tooltip

    def _registrar_evento_hover(self, canvas, ax, barras, nomes_completos, valores, tooltip):
        def _atualizar_posicao_tooltip(i):
            tooltip.xy = (
                barras[i].get_x() + barras[i].get_width() / 2,
                barras[i].get_height()
            )
            tooltip.set_text(f"{nomes_completos[i]}: {valores[i]}")

        def _on_mouse_move(event):
            tooltip_visivel = tooltip.get_visible()
            if event.inaxes == ax:
                for i, barra in enumerate(barras):
                    if barra.contains(event)[0]:
                        _atualizar_posicao_tooltip(i)
                        tooltip.set_visible(True)
                        canvas.draw_idle()
                        return
            if tooltip_visivel:
                tooltip.set_visible(False)
                canvas.draw_idle()

        canvas.mpl_connect("motion_notify_event", _on_mouse_move)

    # ─────────────────────────────────────────────────────────────────────────
    # KPI CARDS
    # ─────────────────────────────────────────────────────────────────────────

    def _construir_cards_kpi(self, parent):
        kpis = self.dados.get("kpis")

        definicoes_cards = [
            ("👥 Funcionários\nanalisados",    kpis["total_funcionarios"]              if kpis else "—", "#1565C0"),
            ("⏱ Horas extras\nno período",     f'{kpis["total_horas_extras"]}h'        if kpis else "—", "#6A1B9A"),
            ("🔔 Intervalos\nirregulares",      kpis["total_intervalos_irregulares"]    if kpis else "—", COR_AMARELO),
            ("❌ Faltas de\nmarcação",           kpis["total_faltas_marcacao"]           if kpis else "—", COR_VERMELHO),
            ("🌙 Interjornadas\nirregulares",   kpis["total_interjornadas_irregulares"] if kpis else "—", "#B71C1C"),
        ]

        linha_cards = ctk.CTkFrame(parent, fg_color="transparent")
        linha_cards.pack(fill="x", pady=(5, 10))

        for coluna, (titulo, valor, cor_fundo) in enumerate(definicoes_cards):
            linha_cards.grid_columnconfigure(coluna, weight=1)
            card = ctk.CTkFrame(linha_cards, fg_color=cor_fundo, corner_radius=12)
            card.grid(row=0, column=coluna, padx=8, pady=5, sticky="nsew")
            ctk.CTkLabel(card, text=str(valor), font=("Roboto", 28, "bold"),
                         text_color="white").pack(pady=(14, 2))
            ctk.CTkLabel(card, text=titulo, font=("Roboto", 10),
                         text_color="white", justify="center").pack(pady=(0, 14))

    # ─────────────────────────────────────────────────────────────────────────
    # GRÁFICO — scatter de interjornadas com linha de referência em 11h
    # ─────────────────────────────────────────────────────────────────────────

    def _grafico_scatter_interjornada(self, frame, dados_interjornada):
        frame.grid(row=0, column=0, padx=8, pady=5, sticky="nsew")

        if not dados_interjornada:
            self._exibir_mensagem_sem_dados(frame, "Sem dados de interjornada")
            return

        datas     = dados_interjornada["scatter_datas"]
        horas     = dados_interjornada["scatter_horas"]
        nomes     = dados_interjornada["scatter_nomes"]
        irregular = dados_interjornada["scatter_irregular"]

        cores_pontos = [COR_VERMELHO if irr else COR_VERDE for irr in irregular]

        figura = self._criar_figura_escura(4, 3)
        ax     = self._configurar_eixo_escuro(figura)

        # Índices numéricos no eixo X para posicionar os pontos
        x_pos = list(range(len(datas)))

        scatter = ax.scatter(x_pos, horas, c=cores_pontos, s=40, zorder=3, alpha=0.85)

        # Linha de referência legal — 11h
        ax.axhline(
            y=HORAS_MINIMAS_INTERJORNADA,
            color=COR_AMARELO, linewidth=1.2, linestyle="--", zorder=2
        )
        ax.text(
            len(datas) - 1, HORAS_MINIMAS_INTERJORNADA + 0.3,
            "mín. 11h", color=COR_AMARELO, fontsize=7, ha="right"
        )

        # Eixo X — mostra datas em intervalos regulares para não poluir
        passo = max(1, len(datas) // 8)
        ax.set_xticks(x_pos[::passo])
        ax.set_xticklabels(datas[::passo], rotation=45, fontsize=7)

        ax.set_ylabel("Horas", fontsize=8, color="white")
        ax.set_title("Interjornada por Ocorrência", fontsize=10, color="white", pad=8)
        ax.grid(True, linestyle="--", color="#444", alpha=0.4, zorder=1)

        # Legenda
        legenda = [
            mpatches.Patch(color=COR_VERDE,   label="Regular (≥ 11h)"),
            mpatches.Patch(color=COR_VERMELHO, label="Irregular (< 11h)"),
        ]
        ax.legend(handles=legenda, fontsize=7, facecolor=COR_FUNDO,
                  labelcolor="white", framealpha=0.6, loc="upper left")

        figura.tight_layout(pad=1.5)

        # Tooltip hover no scatter
        canvas  = self._renderizar_grafico_no_frame(figura, frame)
        tooltip = self._criar_tooltip(ax)

        def _on_mouse_move(event):
            tooltip_visivel = tooltip.get_visible()
            if event.inaxes == ax:
                contido, info = scatter.contains(event)
                if contido and len(info["ind"]) > 0:
                    idx        = info["ind"][0]
                    horas_fmt  = f"{int(horas[idx]):02d}:{int((horas[idx] % 1) * 60):02d}"
                    tooltip.xy = (x_pos[idx], horas[idx])
                    tooltip.set_text(f"{nomes[idx]}\n{datas[idx]} — {horas_fmt}h")
                    tooltip.set_visible(True)
                    canvas.draw_idle()
                    return
            if tooltip_visivel:
                tooltip.set_visible(False)
                canvas.draw_idle()

        canvas.mpl_connect("motion_notify_event", _on_mouse_move)

    # ─────────────────────────────────────────────────────────────────────────
    # TABELA — interjornadas abaixo do mínimo legal
    # ─────────────────────────────────────────────────────────────────────────

    def _tabela_interjornadas_irregulares(self, frame, dados_interjornada):
        frame.grid(row=0, column=1, padx=8, pady=5, sticky="nsew")

        ctk.CTkLabel(
            frame, text="🌙 Interjornadas Irregulares (< 11h)",
            font=("Roboto", 11, "bold"), text_color=COR_VERMELHO
        ).pack(anchor="w", padx=10, pady=(8, 4))

        if not dados_interjornada or not dados_interjornada.get("tabela"):
            self._exibir_mensagem_sem_dados(frame, "Nenhuma interjornada irregular")
            return

        self._renderizar_tabela_generica(frame, dados_interjornada["tabela"], altura=200)

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

    def _grafico_barras_distribuicao_jornada(self, frame, dados_distribuicao):
        frame.grid(row=0, column=1, padx=8, pady=5, sticky="nsew")

        if not dados_distribuicao:
            self._exibir_mensagem_sem_dados(frame, "Sem dados de distribuição")
            return

        figura = self._criar_figura_escura()
        ax     = self._configurar_eixo_escuro(figura)

        barras = ax.bar(
            dados_distribuicao["labels"], dados_distribuicao["values"],
            color=dados_distribuicao["colors"], width=0.5, edgecolor=COR_FUNDO
        )
        for barra, val in zip(barras, dados_distribuicao["values"]):
            ax.text(
                barra.get_x() + barra.get_width() / 2,
                barra.get_height() + max(dados_distribuicao["values"]) * 0.02,
                str(val), ha="center", va="bottom", color="white", fontsize=8
            )

        ax.set_title("Distribuição de Jornada", fontsize=10, color="white", pad=8)
        ax.set_ylabel("Jornadas", fontsize=8, color="white")
        figura.tight_layout(pad=1.5)
        self._renderizar_grafico_no_frame(figura, frame)

    # ─────────────────────────────────────────────────────────────────────────
    # GRÁFICO — linha de evolução de horas extras
    # ─────────────────────────────────────────────────────────────────────────

    def _grafico_linha_evolucao_extras(self, frame, dados_evolucao_extras):
        frame.grid(row=0, column=0, padx=8, pady=5, sticky="nsew")

        if not dados_evolucao_extras:
            self._exibir_mensagem_sem_dados(frame, "Sem horas extras registradas")
            return

        figura = self._criar_figura_escura()
        ax     = self._configurar_eixo_escuro(figura)

        ax.plot(dados_evolucao_extras["labels"], dados_evolucao_extras["values"],
                marker="o", color=COR_ROXO, linewidth=2, markersize=5)
        ax.fill_between(dados_evolucao_extras["labels"], dados_evolucao_extras["values"],
                        alpha=0.15, color=COR_ROXO)
        ax.set_title("Evolução de Horas Extras", fontsize=10, color="white", pad=8)
        ax.set_xlabel("Mês", fontsize=8, color="white")
        ax.set_ylabel("Horas", fontsize=8, color="white")
        ax.tick_params(axis="x", rotation=45)
        ax.grid(True, linestyle="--", color="#444", alpha=0.6)
        figura.tight_layout(pad=1.5)
        self._renderizar_grafico_no_frame(figura, frame)

    # ─────────────────────────────────────────────────────────────────────────
    # GRÁFICO — barras horizontais de irregularidades por tipo
    # ─────────────────────────────────────────────────────────────────────────

    def _grafico_barras_irregularidades_por_tipo(self, frame, dados_irregularidades):
        frame.grid(row=0, column=1, padx=8, pady=5, sticky="nsew")

        if not dados_irregularidades:
            self._exibir_mensagem_sem_dados(frame, "Sem irregularidades registradas")
            return

        labels = dados_irregularidades["labels"]
        values = dados_irregularidades["values"]
        paleta = {
            "Falta de Marcação":    COR_VERMELHO, "Intervalo Curto":       COR_AMARELO,
            "Intervalo Longo":      COR_AMARELO,  "Jornada Longa":         COR_VERMELHO,
            "Jornada s/ Intervalo": COR_VERMELHO, "Jornada Curta":         COR_AMARELO,
            "Hora Extra":           COR_AZUL,     "Menor Irregular":       "#e91e63",
            "Interjornada Irregular": "#B71C1C",
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

        for barra, val in zip(barras, values):
            ax.text(barra.get_width() + max(values) * 0.02,
                    barra.get_y() + barra.get_height() / 2,
                    str(val), va="center", color="white", fontsize=8)

        ax.set_title("Irregularidades por Tipo", fontsize=10, color="white", pad=8)
        figura.tight_layout(pad=1.5)
        self._renderizar_grafico_no_frame(figura, frame)

    # ─────────────────────────────────────────────────────────────────────────
    # GRÁFICO — linha de faltas de marcação por data
    # ─────────────────────────────────────────────────────────────────────────

    def _grafico_linha_faltas_marcacao(self, frame, dados_faltas):
        frame.grid(row=0, column=0, padx=8, pady=5, sticky="nsew")

        if not dados_faltas:
            self._exibir_mensagem_sem_dados(frame, "Sem faltas de marcação")
            return

        figura = self._criar_figura_escura()
        ax     = self._configurar_eixo_escuro(figura)

        ax.plot(dados_faltas["labels_faltas_marcacao"], dados_faltas["values_faltas_marcacao"],
                marker="o", color=COR_VERMELHO, linewidth=2, markersize=5)
        ax.fill_between(dados_faltas["labels_faltas_marcacao"],
                        dados_faltas["values_faltas_marcacao"],
                        alpha=0.12, color=COR_VERMELHO)
        ax.set_title("Faltas de Marcação por Data", fontsize=10, color="white", pad=8)
        ax.set_xlabel("Data", fontsize=8, color="white")
        ax.set_ylabel("Quantidade", fontsize=8, color="white")
        ax.tick_params(axis="x", rotation=45)
        ax.grid(True, linestyle="--", color="#444", alpha=0.6)
        figura.tight_layout(pad=1.5)
        self._renderizar_grafico_no_frame(figura, frame)

    # ─────────────────────────────────────────────────────────────────────────
    # TABELA — menores com jornada fora do horário permitido
    # ─────────────────────────────────────────────────────────────────────────

    def _tabela_menores_irregulares(self, frame, dados_menores):
        frame.grid(row=0, column=1, padx=8, pady=5, sticky="nsew")
        ctk.CTkLabel(frame, text="⚠ Jornada Irregular de Menores",
                     font=("Roboto", 11, "bold"), text_color=COR_AMARELO
                     ).pack(anchor="w", padx=10, pady=(8, 4))

        if not dados_menores:
            self._exibir_mensagem_sem_dados(frame, "Sem registros de menores irregulares")
            return

        self._renderizar_tabela_generica(frame, dados_menores, altura=200)

    # ─────────────────────────────────────────────────────────────────────────
    # TABELA — jornadas com duração acima de 10 horas
    # ─────────────────────────────────────────────────────────────────────────

    def _tabela_jornadas_acima_10h(self, frame, dados_jornadas_longas):
        frame.grid(row=0, column=0, columnspan=2, padx=8, pady=5, sticky="nsew")
        ctk.CTkLabel(frame, text="🕐 Jornadas Acima de 10 Horas",
                     font=("Roboto", 11, "bold"), text_color=COR_VERMELHO
                     ).pack(anchor="w", padx=10, pady=(8, 4))

        if not dados_jornadas_longas:
            self._exibir_mensagem_sem_dados(frame, "Nenhuma jornada acima de 10h registrada")
            return

        self._renderizar_tabela_generica(frame, dados_jornadas_longas, altura=220)

    # ─────────────────────────────────────────────────────────────────────────
    # HELPER — renderiza qualquer list[dict] como tabela com scroll
    # ─────────────────────────────────────────────────────────────────────────

    def _renderizar_tabela_generica(self, parent, registros: list[dict], altura: int = 200):
        colunas = list(registros[0].keys())

        area_scroll = ctk.CTkScrollableFrame(parent, height=altura, fg_color="transparent")
        area_scroll.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        for i, col in enumerate(colunas):
            area_scroll.grid_columnconfigure(i, weight=1)
            ctk.CTkLabel(
                area_scroll, text=col,
                font=("Roboto", 10, "bold"), fg_color="#3a3a3a",
                corner_radius=4, text_color="#ccc"
            ).grid(row=0, column=i, padx=2, pady=(2, 1), sticky="ew")

        for linha_i, registro in enumerate(registros, start=1):
            cor_linha = "#2e2e2e" if linha_i % 2 == 0 else "transparent"
            for col_i, col in enumerate(colunas):
                ctk.CTkLabel(
                    area_scroll,
                    text=str(registro.get(col, "")),
                    font=("Roboto", 10), fg_color=cor_linha,
                    corner_radius=0, text_color="white", anchor="w"
                ).grid(row=linha_i, column=col_i, padx=2, pady=1, sticky="ew")

    # ─────────────────────────────────────────────────────────────────────────
    # GRÁFICO — top 5 com seletor de tipo de irregularidade
    # ─────────────────────────────────────────────────────────────────────────

    def _grafico_top5_com_seletor(self, frame, dados_top5):
        frame.grid(row=0, column=0, columnspan=2, padx=8, pady=5, sticky="nsew")

        if not dados_top5:
            self._exibir_mensagem_sem_dados(frame, "Sem dados para o ranking")
            return

        barra_seletor = ctk.CTkFrame(frame, fg_color="transparent")
        barra_seletor.pack(fill="x", padx=8, pady=(8, 4))

        ctk.CTkLabel(barra_seletor, text="Top 5 — ",
                     font=("Roboto", 11, "bold")).pack(side="left")

        opcoes         = list(TOP5_OPCOES_E_CHAVES.keys())
        self._var_top5 = ctk.StringVar(value=opcoes[0])

        ctk.CTkOptionMenu(
            barra_seletor, variable=self._var_top5, values=opcoes, width=240,
            command=lambda _: self._atualizar_grafico_top5(dados_top5)
        ).pack(side="left", padx=6)

        self._frame_grafico_top5 = ctk.CTkFrame(frame, fg_color="transparent")
        self._frame_grafico_top5.pack(fill="both", expand=True)

        self._atualizar_grafico_top5(dados_top5)

    def _atualizar_grafico_top5(self, dados_top5: dict):
        for widget in self._frame_grafico_top5.winfo_children():
            widget.destroy()

        opcao_selecionada = self._var_top5.get()
        chave_dados       = TOP5_OPCOES_E_CHAVES[opcao_selecionada]
        cor_barras        = TOP5_COR_POR_OPCAO[opcao_selecionada]
        dados_categoria   = dados_top5.get(chave_dados)

        if not dados_categoria or not dados_categoria["labels"]:
            self._exibir_mensagem_sem_dados(
                self._frame_grafico_top5, f"Sem registros para '{opcao_selecionada}'"
            )
            return

        nomes_completos = dados_categoria["labels"]
        valores         = dados_categoria["values"]
        primeiros_nomes = [n.split()[0] for n in nomes_completos]

        figura = self._criar_figura_escura(7, 3)
        ax     = self._configurar_eixo_escuro(figura)

        barras = ax.bar(
            range(len(nomes_completos)), valores,
            color=cor_barras, width=0.5,
            tick_label=primeiros_nomes, edgecolor=COR_FUNDO
        )
        for barra, val in zip(barras, valores):
            ax.text(
                barra.get_x() + barra.get_width() / 2,
                barra.get_height() + max(valores) * 0.02,
                str(val), ha="center", va="bottom", color="white", fontsize=9
            )

        ax.set_title(f"Top 5 — {opcao_selecionada}", fontsize=11, color="white", pad=8)
        figura.tight_layout(pad=1.5)

        tooltip = self._criar_tooltip(ax)
        canvas  = self._renderizar_grafico_no_frame(figura, self._frame_grafico_top5)
        self._registrar_evento_hover(canvas, ax, barras, nomes_completos, valores, tooltip)