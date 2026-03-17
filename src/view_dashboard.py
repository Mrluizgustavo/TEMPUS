import customtkinter as ctk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES VISUAIS
# ─────────────────────────────────────────────────────────────────────────────

BG       = "#2b2b2b"   # fundo dos gráficos Matplotlib
COR_AZUL = "#1f77b4"
COR_VERD = "#4CAF50"
COR_AMAR = "#ff9800"
COR_VERM = "#f44336"
COR_ROXA = "#9c27b0"


class DashboardWindow(ctk.CTkFrame):

    def __init__(self, parent, controller, dados):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.dados = dados
        self._setup_ui()

    # ─────────────────────────────────────────────────────────────────────────
    # ESTRUTURA PRINCIPAL
    # ─────────────────────────────────────────────────────────────────────────

    def _setup_ui(self):
        ctk.CTkLabel(
            self, text="DASHBOARD DE GESTÃO",
            font=("Roboto", 20, "bold")
        ).pack(pady=(15, 5))

        # Área rolável para o conteúdo inteiro
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(expand=True, fill="both", padx=10, pady=5)

        if not self.dados:
            ctk.CTkLabel(scroll, text="Nenhum dado disponível.", text_color="gray").pack(pady=40)
            return

        # ── Linha 0: KPI Cards ────────────────────────────────────────────────
        self._build_kpi_row(scroll)

        # ── Linha 1: Pizza + Barras empilhadas ───────────────────────────────
        row1 = self._row_frame(scroll)
        self._create_pie_intervalos(
            ctk.CTkFrame(row1), self.dados.get("intervalos"), self.dados.get("total_validado")
        )
        self._create_bar_distribuicao_jornada(
            ctk.CTkFrame(row1), self.dados.get("distribuicao")
        )

        # ── Linha 2: Linha horas extras + Barra horiz irregularidades ─────────
        row2 = self._row_frame(scroll)
        self._create_line_horas_extras(
            ctk.CTkFrame(row2), self.dados.get("horas_extras")
        )
        self._create_bar_irregularidades_por_tipo(
            ctk.CTkFrame(row2), self.dados.get("irregularidades")
        )

        # ── Linha 3: Linha faltas marcação + Barra horiz menores ─────────────
        row3 = self._row_frame(scroll)
        self._create_line_faltas_marcacao(
            ctk.CTkFrame(row3), self.dados.get("faltas")
        )
        self._create_bar_horinzontal_menores(
            ctk.CTkFrame(row3), self.dados.get("menores")
        )

        # ── Linha 4: Top 5 faltas (barra vertical — largura total) ───────────
        row4 = self._row_frame(scroll)
        self._create_bar_top_5_funcionarios_faltas_marcacao(
            ctk.CTkFrame(row4, width=900), self.dados.get("faltas")
        )

    # ─────────────────────────────────────────────────────────────────────────
    # HELPERS DE LAYOUT
    # ─────────────────────────────────────────────────────────────────────────

    def _row_frame(self, parent):
        """Cria uma linha horizontal que divide o espaço igualmente entre filhos."""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", pady=5)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=1)
        return frame

    def _embed_child(self, child_frame, parent_row, col):
        """Coloca um CTkFrame dentro do grid de uma row."""
        child_frame.grid(row=0, column=col, padx=8, pady=5, sticky="nsew")

    def _mostrar_mensagem_vazio(self, master, mensagem):
        lbl = ctk.CTkLabel(master, text=mensagem, font=("Roboto", 13, "italic"), text_color="gray")
        lbl.pack(expand=True, pady=20)

    def _make_canvas(self, fig, master):
        canvas = FigureCanvasTkAgg(fig, master=master)
        canvas.draw()
        canvas.get_tk_widget().pack(expand=True, fill="both", padx=5, pady=5)
        return canvas

    def _base_ax(self, fig):
        """Aplica estilo escuro padrão a um eixo recém-criado."""
        ax = fig.add_subplot(111)
        ax.patch.set_facecolor(BG)
        ax.tick_params(colors="white")
        ax.tick_params(axis="x", colors="white", labelsize=8)
        ax.tick_params(axis="y", colors="white", labelsize=8)
        for spine in ax.spines.values():
            spine.set_visible(False)
        return ax

    def _base_fig(self, w=4, h=3):
        return Figure(figsize=(w, h), dpi=100, facecolor=BG)

    # ─────────────────────────────────────────────────────────────────────────
    # KPI CARDS
    # ─────────────────────────────────────────────────────────────────────────

    def _build_kpi_row(self, parent):
        kpis = self.dados.get("kpis")

        cards_info = [
            ("👥 Funcionários\nanalisados",  kpis["total_funcionarios"]             if kpis else "—", "#1565C0"),
            ("⏱ Horas extras\nno período",   f'{kpis["total_horas_extras"]}h'       if kpis else "—", "#6A1B9A"),
            ("🔔 Intervalos\nirregulares",    kpis["total_intervalos_irregulares"]   if kpis else "—", COR_AMAR),
            ("❌ Faltas de\nmarcação",         kpis["total_faltas_marcacao"]          if kpis else "—", COR_VERM),
        ]

        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(5, 10))

        for col, (titulo, valor, cor) in enumerate(cards_info):
            row.grid_columnconfigure(col, weight=1)
            card = ctk.CTkFrame(row, fg_color=cor, corner_radius=12)
            card.grid(row=0, column=col, padx=8, pady=5, sticky="nsew")

            ctk.CTkLabel(
                card, text=str(valor),
                font=("Roboto", 30, "bold"), text_color="white"
            ).pack(pady=(14, 2))

            ctk.CTkLabel(
                card, text=titulo,
                font=("Roboto", 11), text_color="white", justify="center"
            ).pack(pady=(0, 14))

    # ─────────────────────────────────────────────────────────────────────────
    # GRÁFICO 1 — Pizza: Intervalos
    # ─────────────────────────────────────────────────────────────────────────

    def _create_pie_intervalos(self, frame, dados, total):
        frame.grid(row=0, column=0, padx=8, pady=5, sticky="nsew")

        if not dados or not total:
            self._mostrar_mensagem_vazio(frame, "Sem irregularidades de intervalo")
            return

        fig = self._base_fig(4, 3)
        ax  = fig.add_subplot(111)
        ax.patch.set_facecolor(BG)

        labels = list(dados["labels"]) + ["Regulares"]
        values = list(dados["values"]) + [total["Total_validado"]]
        colors = [COR_AMAR, COR_VERM, COR_VERD][:len(labels)]

        wedges, texts, autotexts = ax.pie(
            values,
            labels=labels,
            autopct="%1.1f%%",
            startangle=140,
            colors=colors,
            textprops={"color": "white", "fontsize": 8},
            wedgeprops={"linewidth": 0.5, "edgecolor": BG},
        )
        for at in autotexts:
            at.set_fontsize(7)

        ax.set_title("Intervalos Irregulares x Regulares", fontsize=10, color="white", pad=8)
        self._make_canvas(fig, frame)

    # ─────────────────────────────────────────────────────────────────────────
    # GRÁFICO 2 — Barra empilhada: Distribuição de jornada
    # ─────────────────────────────────────────────────────────────────────────

    def _create_bar_distribuicao_jornada(self, frame, dados):
        frame.grid(row=0, column=1, padx=8, pady=5, sticky="nsew")

        if not dados:
            self._mostrar_mensagem_vazio(frame, "Sem dados de distribuição de jornada")
            return

        fig = self._base_fig(4, 3)
        ax  = self._base_ax(fig)

        labels = dados["labels"]
        values = dados["values"]
        colors = dados["colors"]

        bars = ax.bar(labels, values, color=colors, width=0.5,
                      edgecolor=BG, linewidth=0.5)

        # Rótulo em cima de cada barra
        for bar, val in zip(bars, values):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + max(values) * 0.02,
                str(val),
                ha="center", va="bottom", color="white", fontsize=8
            )

        ax.set_title("Distribuição de Jornada", fontsize=10, color="white", pad=8)
        ax.set_ylabel("Jornadas", fontsize=8, color="white")
        ax.yaxis.label.set_color("white")
        ax.tick_params(axis="x", colors="white", labelsize=9)
        ax.tick_params(axis="y", colors="white", labelsize=8)
        fig.tight_layout(pad=1.5)
        self._make_canvas(fig, frame)

    # ─────────────────────────────────────────────────────────────────────────
    # GRÁFICO 3 — Linha: Evolução de horas extras
    # ─────────────────────────────────────────────────────────────────────────

    def _create_line_horas_extras(self, frame, dados):
        frame.grid(row=0, column=0, padx=8, pady=5, sticky="nsew")

        if not dados:
            self._mostrar_mensagem_vazio(frame, "Sem horas extras registradas")
            return

        fig = self._base_fig(4, 3)
        ax  = self._base_ax(fig)

        ax.plot(dados["labels"], dados["values"],
                marker="o", color=COR_ROXA, linewidth=2, markersize=5)
        ax.fill_between(dados["labels"], dados["values"],
                        alpha=0.15, color=COR_ROXA)

        ax.set_title("Evolução de Horas Extras", fontsize=10, color="white", pad=8)
        ax.set_xlabel("Mês", fontsize=8, color="white")
        ax.set_ylabel("Horas", fontsize=8, color="white")
        ax.tick_params(axis="x", rotation=45)
        ax.grid(True, linestyle="--", color="#444", alpha=0.6)
        fig.tight_layout(pad=1.5)
        self._make_canvas(fig, frame)

    # ─────────────────────────────────────────────────────────────────────────
    # GRÁFICO 4 — Barra horizontal: Irregularidades por tipo
    # ─────────────────────────────────────────────────────────────────────────

    def _create_bar_irregularidades_por_tipo(self, frame, dados):
        frame.grid(row=0, column=1, padx=8, pady=5, sticky="nsew")

        if not dados:
            self._mostrar_mensagem_vazio(frame, "Sem irregularidades registradas")
            return

        labels = dados["labels"]
        values = dados["values"]
        n = len(labels)

        # Cores semânticas por tipo
        palette = {
            "Falta de Marcação":     COR_VERM,
            "Intervalo Curto":       COR_AMAR,
            "Intervalo Longo":       COR_AMAR,
            "Jornada Longa":         COR_VERM,
            "Jornada s/ Intervalo":  COR_VERM,
            "Jornada Curta":         COR_AMAR,
            "Hora Extra":            COR_AZUL,
            "Menor Irregular":       "#e91e63",
        }
        colors = [palette.get(l, COR_AZUL) for l in labels]

        height = max(2.5, n * 0.45)
        fig = self._base_fig(4, height)
        ax  = self._base_ax(fig)

        y_pos = list(range(n))
        bars = ax.barh(y_pos, values, color=colors, height=0.55, edgecolor=BG)

        ax.set_yticks(y_pos)
        ax.set_yticklabels(labels, fontsize=8)
        ax.invert_yaxis()

        # Rótulo no final de cada barra
        for bar, val in zip(bars, values):
            ax.text(
                bar.get_width() + max(values) * 0.02,
                bar.get_y() + bar.get_height() / 2,
                str(val),
                va="center", color="white", fontsize=8
            )

        ax.set_title("Irregularidades por Tipo", fontsize=10, color="white", pad=8)
        fig.tight_layout(pad=1.5)
        self._make_canvas(fig, frame)

    # ─────────────────────────────────────────────────────────────────────────
    # GRÁFICO 5 — Linha: Faltas de marcação por data
    # ─────────────────────────────────────────────────────────────────────────

    def _create_line_faltas_marcacao(self, frame, dados):
        frame.grid(row=0, column=0, padx=8, pady=5, sticky="nsew")

        if not dados:
            self._mostrar_mensagem_vazio(frame, "Sem faltas de marcação")
            return

        fig = self._base_fig(4, 3)
        ax  = self._base_ax(fig)

        ax.plot(
            dados["labels_faltas_marcacao"],
            dados["values_faltas_marcacao"],
            marker="o", color=COR_VERM, linewidth=2, markersize=5
        )
        ax.fill_between(
            dados["labels_faltas_marcacao"],
            dados["values_faltas_marcacao"],
            alpha=0.12, color=COR_VERM
        )

        ax.set_title("Faltas de Marcação por Data", fontsize=10, color="white", pad=8)
        ax.set_xlabel("Data", fontsize=8, color="white")
        ax.set_ylabel("Quantidade", fontsize=8, color="white")
        ax.tick_params(axis="x", rotation=45)
        ax.grid(True, linestyle="--", color="#444", alpha=0.6)
        fig.tight_layout(pad=1.5)
        self._make_canvas(fig, frame)

    # ─────────────────────────────────────────────────────────────────────────
    # GRÁFICO 6 — Barra horizontal: Menores irregulares
    # ─────────────────────────────────────────────────────────────────────────

    def _create_bar_horinzontal_menores(self, frame, dados):
        frame.grid(row=0, column=1, padx=8, pady=5, sticky="nsew")

        if not dados:
            self._mostrar_mensagem_vazio(frame, "Sem jornadas irregulares de menores")
            return

        full_names  = [str(n) for n in dados["labels_menores"]]
        values      = dados["values_menores"]
        first_names = [n.split()[0] for n in full_names]
        y_pos       = list(range(len(full_names)))

        fig = self._base_fig(4, 3)
        ax  = self._base_ax(fig)

        bars = ax.barh(y_pos, values, color="#e91e63", height=0.45, edgecolor=BG)
        ax.set_yticks(y_pos)
        ax.set_yticklabels(first_names, fontsize=8)
        ax.invert_yaxis()
        ax.set_title("Jornada Irregular de Menores", fontsize=10, color="white", pad=8)

        # Tooltip hover
        annot = ax.annotate(
            "", xy=(0, 0), xytext=(10, 10), textcoords="offset points",
            bbox=dict(boxstyle="round", fc="white", ec="black", alpha=0.9),
            fontsize=9, color="black"
        )
        annot.set_visible(False)
        fig.tight_layout(pad=1.5)

        canvas = self._make_canvas(fig, frame)

        def update_annot(i):
            x = bars[i].get_width()
            y = bars[i].get_y() + bars[i].get_height() / 2
            annot.xy = (x, y)
            if x > ax.get_xlim()[1] * 0.8:
                annot.set_position((-10, 10)); annot.set_ha("right")
            else:
                annot.set_position((10, 10));  annot.set_ha("left")
            annot.set_text(f"Nome: {full_names[i]}\nTotal: {values[i]}")

        def hover(event):
            vis = annot.get_visible()
            if event.inaxes == ax:
                for i, bar in enumerate(bars):
                    if bar.contains(event)[0]:
                        update_annot(i)
                        annot.set_visible(True)
                        canvas.draw_idle()
                        return
            if vis:
                annot.set_visible(False)
                canvas.draw_idle()

        canvas.mpl_connect("motion_notify_event", hover)

    # ─────────────────────────────────────────────────────────────────────────
    # GRÁFICO 7 — Barra vertical: Top 5 funcionários com faltas
    # ─────────────────────────────────────────────────────────────────────────

    def _create_bar_top_5_funcionarios_faltas_marcacao(self, frame, dados):
        frame.grid(row=0, column=0, columnspan=2, padx=8, pady=5, sticky="nsew")

        if not dados:
            self._mostrar_mensagem_vazio(frame, "Sem faltas de marcação")
            return

        full_names   = [str(n) for n in dados["top_funcionarios_labels"]]
        values       = dados["top_funcionarios_values"]
        short_labels = [n.split()[0] for n in full_names]
        x_indexes    = list(range(len(full_names)))

        fig = self._base_fig(7, 3)
        ax  = self._base_ax(fig)

        bars = ax.bar(x_indexes, values, color=COR_VERM, width=0.5,
                      tick_label=short_labels, edgecolor=BG)

        # Rótulo em cima
        for bar, val in zip(bars, values):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + max(values) * 0.02,
                str(val),
                ha="center", va="bottom", color="white", fontsize=9
            )

        ax.set_title("Top 5 Funcionários — Faltas de Marcação", fontsize=11, color="white", pad=8)
        ax.tick_params(axis="x", colors="white", labelsize=9)
        ax.tick_params(axis="y", colors="white", labelsize=8)

        # Tooltip hover
        annot = ax.annotate(
            "", xy=(0, 0), xytext=(10, 10), textcoords="offset points",
            bbox=dict(boxstyle="round", fc="white", ec="black", alpha=0.9),
            fontsize=9, color="black"
        )
        annot.set_visible(False)
        fig.tight_layout(pad=1.5)

        canvas = self._make_canvas(fig, frame)

        def update_annot(i):
            x = bars[i].get_x() + bars[i].get_width() / 2
            y = bars[i].get_height()
            annot.xy = (x, y)
            annot.set_text(f"{full_names[i]}: {values[i]}")
            annot.get_bbox_patch().set_alpha(0.85)

        def hover(event):
            vis = annot.get_visible()
            if event.inaxes == ax:
                for i, bar in enumerate(bars):
                    if bar.contains(event)[0]:
                        update_annot(i)
                        annot.set_visible(True)
                        canvas.draw_idle()
                        return
            if vis:
                annot.set_visible(False)
                canvas.draw_idle()

        canvas.mpl_connect("motion_notify_event", hover)