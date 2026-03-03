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

        self.container_principal.grid_columnconfigure((0,1), weight=1)
        self.container_principal.grid_rowconfigure((0,1), weight=1)

        #FRAMES PARA OS GRÁFICOS
        self.frame_grafico_esquerda = ctk.CTkFrame(self.container_principal)
        self.frame_grafico_esquerda.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        self.frame_grafico_direita = ctk.CTkFrame(self.container_principal)
        self.frame_grafico_direita.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")


        if self.dados:
            self._create_pie_intervalos(self.dados.get("intervalos"))
            self._create_pie_faltas(self.dados.get("faltas"))

    def _mostrar_mensagem_vazio(self, master, mensagem):
        """Exibe um aviso caso não existam dados para o gráfico."""
        lbl = ctk.CTkLabel(master, text=mensagem, font=("Roboto", 14, "italic"), text_color="gray")
        lbl.pack(expand=True)


    def _create_pie_faltas(self, dados_faltas):
        if not dados_faltas:
            self._mostrar_mensagem_vazio(self.frame_grafico_direita, "Sem faltas de marcação")
            return

        fig = Figure(figsize=(3, 2), dpi=100, facecolor=None)
        ax = fig.add_subplot(111)

        ax.pie(
            dados_faltas["values"],
            labels=dados_faltas["labels"],
            autopct="%1.1f%%",
            startangle=140,
            colors=["#673ab7", "#3f51b5"]
        )
        ax.set_title("Faltas de Marcação", fontsize=12)

        canvas = FigureCanvasTkAgg(fig, master=self.frame_grafico_direita)
        canvas.draw()
        canvas.get_tk_widget().pack(expand=True, fill="both", padx=5, pady=5)


    def _create_pie_intervalos(self, dados_intervalo):
        if not dados_intervalo:
            self._mostrar_mensagem_vazio(self.frame_grafico_esquerda, "Sem irregularidades de intervalo")
            return

        fig = Figure(figsize=(3, 2), dpi=100, facecolor=None)
        ax = fig.add_subplot(111)

        ax.pie(
            dados_intervalo["values"],
            labels=dados_intervalo["labels"],
            autopct="%1.1f%%",
            startangle=90,
            colors=["#ff9800", "#f44336"]
        )
        ax.set_title("Intervalos Irregulares", fontsize=12)

        canvas = FigureCanvasTkAgg(fig, master=self.frame_grafico_esquerda)
        canvas.draw()
        canvas.get_tk_widget().pack(expand=True, fill="both", padx=5, pady=5)