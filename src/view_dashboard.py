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

        self.frame_grafico_esquerda = ctk.CTkFrame(self.container_principal)
        self.frame_grafico_esquerda.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        self.frame_grafico_direita = ctk.CTkFrame(self.container_principal)
        self.frame_grafico_direita.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

        self._create_bar()


    def _create_bar(self):
        fig = Figure(figsize=(5, 5), dpi=100)
        ax = fig.add_subplot(111)


        nomes = ["João", "Maria", "José"]
        valores = [10, 20, 15]

        ax.bar(nomes, valores)
        ax.set_title("Dados")


        canvas = FigureCanvasTkAgg(fig, master=self.frame_grafico_direita)
        canvas.draw()
        canvas.get_tk_widget().pack(expand=True, fill="both", padx=5, pady=5)

