import customtkinter as ctk
from customtkinter import CTkFrame
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt


class DashboardWindow(ctk.CTkFrame):

    # CONFIGURAÇÃO DO FRAME
    def __init__(self, parent, controller, dados):
        # Agora o parent é o container do App principal
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.dados = dados
        self._setup_ui()


    def _setup_ui(self):
        label = ctk.CTkLabel(self, text="DASHBOARD DE GESTÃO", font=("Roboto", 20, "bold"))
        label.pack(pady=20)
        # Adicione aqui seus gráficos e indicadores usando 'self.dados'

        # CONTAINER PRINCIPAL
        self.container_principal = ctk.CTkFrame(self)
        self.container_principal.pack(expand=True, fill="both", padx=20, pady=10)

        #CONFIGURAÇÃO DAS COLUNAS E LINHAS
        self.container_principal.grid_columnconfigure(0, weight=4)
        self.container_principal.grid_columnconfigure(1, weight=2)
        self.container_principal.grid_rowconfigure(0, weight=1)
        self.container_principal.grid_rowconfigure(1, weight=3)

        #FRAMES PARA OS GRÁFICOS
        self.frame_row_0_column_0 = ctk.CTkFrame(self.container_principal)
        self.frame_row_0_column_0.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        self.frame_row_0_column_1 = ctk.CTkFrame(self.container_principal)
        self.frame_row_0_column_1.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

        self.frame_row_1_column_0 = ctk.CTkFrame(self.container_principal)
        self.frame_row_1_column_0.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")

        self.frame_row_1_column_1 = ctk.CTkFrame(self.container_principal)
        self.frame_row_1_column_1.grid(row=1, column=1, padx=10, pady=10, sticky="nsew")


        if self.dados:
            self._create_pie_intervalos(self.dados.get("intervalos"), self.dados.get("total_validado"))
            self._create_line_faltas_marcacao(self.dados.get("faltas"))
            self._create_bar_top_5_funcionarios_faltas_marcacao(self.dados.get("faltas"))
            self._create_bar_horinzontal_menores(self.dados.get("menores"))

    def _mostrar_mensagem_vazio(self, master, mensagem):
        """Exibe um aviso caso não existam dados para o gráfico."""
        lbl = ctk.CTkLabel(master, text=mensagem, font=("Roboto", 14, "italic"), text_color="gray")
        lbl.pack(expand=True)

    def _create_line_faltas_marcacao(self, dados):
        if not dados:
            self._mostrar_mensagem_vazio(self.frame_row_1_column_0, "Sem faltas de marcação")
            return

        dark_bg_color = "#2b2b2b"  # fundo escuro seguro para Matplotlib

        fig = Figure(figsize=(3, 2), dpi=100, facecolor=dark_bg_color)
        ax = fig.add_subplot(111)
        ax.patch.set_facecolor(dark_bg_color)  # fundo do eixo
        ax.plot(
            dados["labels_faltas_marcacao"],
            dados["values_faltas_marcacao"],
            marker="o"
        )


        ax.set_title("Faltas de Marcação", fontsize=10, color="white")
        ax.set_xlabel("Data", fontsize=10, color="white")
        ax.set_ylabel("Quantidade", fontsize=8, color="white")

        ax.tick_params(axis="x", colors="white")
        ax.tick_params(axis="y", colors="white")
        ax.grid(True, linestyle="--", color="gray")

        canvas = FigureCanvasTkAgg(fig, master=self.frame_row_1_column_0)
        canvas.draw()
        canvas.get_tk_widget().pack(expand=True, fill="both", padx=5, pady=5)


    def _create_pie_intervalos(self, dados, total):
        if not dados:
            self._mostrar_mensagem_vazio(self.frame_row_0_column_0, "Sem irregularidades de intervalo")
            return

        dark_bg_color = "#2b2b2b"

        fig = Figure(figsize=(3, 2), dpi=100, facecolor=dark_bg_color)
        ax = fig.add_subplot(111)
        ax.patch.set_facecolor(dark_bg_color)

        total_ok = total["Total_validado"]

        labels = list(dados["labels"])
        values = list(dados["values"])

        labels.append("Regulares")
        values.append(total_ok)

        ax.pie(
            values,
            labels=labels,
            autopct="%1.1f%%",
            startangle=140,
            colors=["#ff9800", "#f44336", "#4CAF50"],
            textprops={'color': 'white', 'fontsize': 8}
        )

        ax.set_title("Intervalos Irregulares x Regulares", fontsize=10, color="white")

        canvas = FigureCanvasTkAgg(fig, master=self.frame_row_0_column_0)
        canvas.draw()
        canvas.get_tk_widget().pack(expand=True, fill="both", padx=5, pady=5)

    def _create_bar_top_5_funcionarios_faltas_marcacao(self, dados):
        if not dados:
            self._mostrar_mensagem_vazio(self.frame_row_0_column_1, "Sem faltas de marcação")
            return

        dark_bg_color = "#2b2b2b"
        full_names = [str(n) for n in dados["top_funcionarios_labels"]]
        x_indexes = list(range(len(full_names)))
        short_labels = [n.split()[0] + f" {i + 1}" if "Pessoa" in n else n.split()[0] for i, n in enumerate(full_names)]
        values = dados["top_funcionarios_values"]

        fig = Figure(figsize=(4, 3), dpi=100, facecolor=dark_bg_color)
        ax = fig.add_subplot(111)
        ax.patch.set_facecolor(dark_bg_color)

        bars = ax.bar(x_indexes, values, color="#1f77b4", width=0.6, tick_label=short_labels)

        ax.set_title("Top 5 funcionários: Faltas de Marcação", fontsize=10, color="white")
        ax.tick_params(axis='x', colors='white', labelsize=8)
        ax.tick_params(axis='y', colors='white', labelsize=8)

        # REMOVE BORDAS DO GRAFICO
        for spine in ax.spines.values():
            spine.set_visible(False)

        annot = ax.annotate(
            "",
            xy=(0, 0),
            xytext=(10, 10),
            textcoords="offset points",
            bbox=dict(boxstyle="round", fc="white", ec="black", alpha=0.9),
            fontsize=9,
            color="black"
        )
        annot.set_visible(False)

        canvas = FigureCanvasTkAgg(fig, master=self.frame_row_0_column_1)
        canvas.draw()
        canvas.get_tk_widget().pack(expand=True, fill="both", padx=5, pady=5)

        def update_annot(bar_index):
            x = bars[bar_index].get_x() + bars[bar_index].get_width() / 2
            y = bars[bar_index].get_height()
            annot.xy = (x, y)
            text = f"{full_names[bar_index]}: {values[bar_index]}"
            annot.set_text(text)
            annot.get_bbox_patch().set_alpha(0.8)

        def hover(event):
            vis = annot.get_visible()
            if event.inaxes == ax:
                for i, bar in enumerate(bars):
                    cont, _ = bar.contains(event)
                    if cont:
                        update_annot(i)
                        annot.set_visible(True)
                        canvas.draw_idle()
                        return
            if vis:
                annot.set_visible(False)
                canvas.draw_idle()

        canvas.mpl_connect("motion_notify_event", hover)
        canvas.draw()

    def _create_bar_horinzontal_menores(self, dados):
        if not dados:
            self._mostrar_mensagem_vazio(self.frame_row_1_column_1, "Sem jornadas irregulares de menores")
            return

        #CONFIGURAÇÕES
        dark_bg_color = "#2b2b2b"
        full_names = [str(n) for n in dados["labels_menores"]]
        values = dados["values_menores"]
        y_positions = list(range(len(full_names)))
        first_names = [n.split()[0] for n in full_names]

        fig = Figure(figsize=(3, 2), dpi=100, facecolor=dark_bg_color)
        ax = fig.add_subplot(111)
        ax.patch.set_facecolor(dark_bg_color)

        bars = ax.barh(y_positions, values, color="#1f77b4", height=0.4)

        ax.set_yticks(y_positions)
        ax.set_yticklabels(first_names)
        ax.invert_yaxis()
        ax.set_title("Jornada Irregular de Menores", fontsize=10, color="white")
        ax.tick_params(axis='x', colors='white', labelsize=8)
        ax.tick_params(axis='y', colors='white', labelsize=8)

        for spine in ax.spines.values():
            spine.set_visible(False)

        annot = ax.annotate(
            "",
            xy=(0, 0),
            xytext=(10, 10),
            textcoords="offset points",
            bbox=dict(boxstyle="round", fc="white", ec="black", alpha=0.9),
            fontsize=9,
            color="black"
        )
        annot.set_visible(False)

        fig.tight_layout(pad=1.0)

        canvas = FigureCanvasTkAgg(fig, master=self.frame_row_1_column_1)
        canvas.draw()
        canvas.get_tk_widget().pack(expand=True, fill="both", padx=2, pady=2)

        def update_annot(bar_index):
            x = bars[bar_index].get_width()
            y = bars[bar_index].get_y() + bars[bar_index].get_height() / 2

            if x > ax.get_xlim()[1] * 0.8:
                annot.set_position((-10, 10))
                annot.set_ha('right')
            else:
                annot.set_position((10, 10))
                annot.set_ha('left')

            text = f"Nome: {full_names[bar_index]}\nTotal: {values[bar_index]}"
            annot.set_text(text)

        def hover(event):
            vis = annot.get_visible()
            if event.inaxes == ax:
                for i, bar in enumerate(bars):
                    cont, _ = bar.contains(event)
                    if cont:
                        update_annot(i)
                        annot.set_visible(True)
                        canvas.draw_idle()
                        return
            if vis:
                annot.set_visible(False)
                canvas.draw_idle()

        canvas.mpl_connect("motion_notify_event", hover)
        canvas.draw()