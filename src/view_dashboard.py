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
        self.container_principal.grid_columnconfigure(0, weight=3)
        self.container_principal.grid_columnconfigure(1, weight=1)
        self.container_principal.grid_rowconfigure(0, weight=1)
        self.container_principal.grid_rowconfigure(1, weight=3)

        #FRAMES PARA OS GRÁFICOS
        self.frame_grafico_esquerda = ctk.CTkFrame(self.container_principal)
        self.frame_grafico_esquerda.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        self.frame_grafico_direita = ctk.CTkFrame(self.container_principal)
        self.frame_grafico_direita.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

        self.frame_grafico_main = ctk.CTkFrame(self.container_principal)
        self.frame_grafico_main.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")


        if self.dados:
            self._create_pie_intervalos(self.dados.get("intervalos"))
            self._create_line_faltas_marcacao(self.dados.get("faltas"))
            self._create_bar_top_5_funcionarios_faltas_marcacao(self.dados.get("faltas"))

    def _mostrar_mensagem_vazio(self, master, mensagem):
        """Exibe um aviso caso não existam dados para o gráfico."""
        lbl = ctk.CTkLabel(master, text=mensagem, font=("Roboto", 14, "italic"), text_color="gray")
        lbl.pack(expand=True)

    def _create_line_faltas_marcacao(self, dados):
        if not dados:
            self._mostrar_mensagem_vazio(self.frame_grafico_main, "Sem faltas de marcação")
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

        canvas = FigureCanvasTkAgg(fig, master=self.frame_grafico_main)
        canvas.draw()
        canvas.get_tk_widget().pack(expand=True, fill="both", padx=5, pady=5)


    def _create_pie_intervalos(self, dados):
        if not dados:
            self._mostrar_mensagem_vazio(self.frame_grafico_esquerda, "Sem irregularidades de intervalo")
            return

        dark_bg_color = "#2b2b2b"

        fig = Figure(figsize=(3, 2), dpi=100, facecolor=dark_bg_color)
        ax = fig.add_subplot(111)
        ax.patch.set_facecolor(dark_bg_color)

        ax.pie(
            dados["values"],
            labels=dados["labels"],
            autopct="%1.1f%%",
            startangle=90,
            colors=["#ff9800", "#f44336"],
            textprops={'color': 'white', 'fontsize': 10}
        )

        ax.set_title("Intervalos Irregulares", fontsize=10, color="white")

        canvas = FigureCanvasTkAgg(fig, master=self.frame_grafico_esquerda)
        canvas.draw()
        canvas.get_tk_widget().pack(expand=True, fill="both", padx=5, pady=5)

    def _create_bar_top_5_funcionarios_faltas_marcacao(self, dados):
        if not dados:
            self._mostrar_mensagem_vazio(self.frame_grafico_direita, "Sem faltas de marcação")
            return

        dark_bg_color = "#2b2b2b"

        fig = Figure(figsize=(3, 2), dpi=100, facecolor=dark_bg_color)
        ax = fig.add_subplot(111)
        ax.patch.set_facecolor(dark_bg_color)

        ax.bar(
            dados["top_funcionarios_labels"],
            dados["top_funcionarios_values"],
            color="#1f77b4"

        )

        ax.set_title("Top 5 funcionários: Faltas de Marcação", fontsize=10, color="white")
        ax.tick_params(axis='x', colors='white', labelsize=8)
        ax.tick_params(axis='y', colors='white', labelsize=8)

        # REMOVE BORDAS DO GRAFICO
        for spine in ax.spines.values():
            spine.set_visible(False)

        canvas = FigureCanvasTkAgg(fig, master=self.frame_grafico_direita)
        canvas.draw()
        canvas.get_tk_widget().pack(expand=True, fill="both", padx=5, pady=5)

