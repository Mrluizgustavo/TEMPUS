import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import os
from datetime import datetime

from src.loader import ExcelLoader
from src.processador import Processador
from src.reporter import ExcelReporter
from src.database import BancoDeDados
from src.view_dashboard import DashboardWindow

class AppPonto(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.bind("<Control-r>", lambda e: self.reiniciar())

        # 1. Defina o tamanho da janela que você quer
        largura_janela = 1000
        altura_janela = 900

        # 2. Pegue a resolução do monitor do usuário
        largura_tela = self.winfo_screenwidth()
        altura_tela = self.winfo_screenheight()

        # 3. Calcule a posição (X e Y)
        # Para ficar na direita: Largura total da tela menos a largura da janela
        pos_x = largura_tela - largura_janela
        # Para centralizar na vertical: Metade da tela menos metade da janela
        pos_y = (altura_tela // 2) - (altura_janela // 2)

        # 4. Aplica a geometria: "LarguraxAltura+X+Y"
        self.geometry(f"{largura_janela}x{altura_janela}+{pos_x}+{pos_y}")

        self.title("Tempus - Time & Agility")
        ctk.set_appearance_mode("Dark")

        # --- Configuração de Grid Principal ---
        # Coluna 0: Sidebar (fixa) | Coluna 1: Conteúdo (expansível)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- Sidebar ---
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(4, weight=1)  # Espaçador inferior

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="TEMPUS", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        self.btn_nav_home = ctk.CTkButton(self.sidebar_frame, text="Processar Ponto",
                                          command=lambda: self.show_frame("Home"))
        self.btn_nav_home.grid(row=1, column=0, padx=20, pady=10)

        self.btn_nav_dash = ctk.CTkButton(self.sidebar_frame, text="Dashboard",
                                          fg_color="#8A2BE2", hover_color="#4B0082",
                                          command=self.abrir_dashboard)
        self.btn_nav_dash.grid(row=2, column=0, padx=20, pady=10)

        # --- Container de Conteúdo ---
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.container.grid_columnconfigure(0, weight=1)
        self.container.grid_rowconfigure(0, weight=1)

        # Dicionário de frames
        self.frames = {}

        # Instanciando a tela principal (seu código original vai aqui dentro)
        self.frames["Home"] = HomeFrame(parent=self.container, controller=self)
        self.frames["Home"].grid(row=0, column=0, sticky="nsew")

        self.show_frame("Home")
        self._configurar_icone()

    def reiniciar(self, event=None):
        self.destroy()
        import os
        import sys
        os.startfile(sys.argv[0])

    def _configurar_icone(self):
        try:
            caminho_base = os.path.dirname(os.path.abspath(__file__))
            caminho_icone = os.path.join(caminho_base, "IMG", "ICON.png")
            if os.path.exists(caminho_icone):
                self.icone_img = tk.PhotoImage(file=caminho_icone)
                self.iconphoto(False, self.icone_img)
        except:
            pass

    def show_frame(self, page_name):
        frame = self.frames[page_name]
        frame.tkraise()

    def abrir_dashboard(self):

        banco = BancoDeDados()
        dados = banco.obter_dados_dashboard()

        if not dados:
            messagebox.showwarning("Vazio", "Processe algum arquivo primeiro para alimentar o banco de dados!")
            return

        if "Dashboard" in self.frames:
            self.frames["Dashboard"].destroy()

            # 2. Criamos o Dashboard como um Frame dentro do container principal
            # Note que passamos 'dados' para ele
        self.frames["Dashboard"] = DashboardWindow(parent=self.container, controller=self, dados=dados)
        self.frames["Dashboard"].grid(row=0, column=0, sticky="nsew")

        # 3. Alternamos a visualização
        self.show_frame("Dashboard")


class HomeFrame(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.arquivo_selecionado = None

        # 1. Título
        self.lbl_titulo = ctk.CTkLabel(self, text="Tratamento de Ponto Eletrônico", font=("Roboto", 24, "bold"))
        self.lbl_titulo.pack(pady=(10, 20))

        # 2. Área de Seleção de Arquivo
        self.frame_arquivo = ctk.CTkFrame(self)
        self.frame_arquivo.pack(pady=5, fill="x")

        self.btn_selecionar = ctk.CTkButton(self.frame_arquivo, text="Selecionar Excel (.xlsx)",
                                            command=self.selecionar_arquivo)
        self.btn_selecionar.pack(side="left", padx=10, pady=10)

        self.lbl_arquivo = ctk.CTkLabel(self.frame_arquivo, text="Nenhum arquivo selecionado", text_color="gray")
        self.lbl_arquivo.pack(side="left", padx=10)

        # 3. Área de Filtro de Datas
        self.frame_datas = ctk.CTkFrame(self)
        self.frame_datas.pack(pady=10, fill="x")

        self.chk_usar_filtro = ctk.CTkCheckBox(self.frame_datas, text="Filtrar por Período Específico",
                                               command=self.toggle_datas)
        self.chk_usar_filtro.pack(pady=10, anchor="w", padx=10)

        self.subframe_inputs = ctk.CTkFrame(self.frame_datas, fg_color="transparent")
        self.subframe_inputs.pack(fill="x", padx=10, pady=(0, 10))

        self.entry_inicio = ctk.CTkEntry(self.subframe_inputs, placeholder_text="DD/MM/AAAA", width=120)
        self.entry_inicio.pack(side="left", padx=5)

        self.entry_fim = ctk.CTkEntry(self.subframe_inputs, placeholder_text="DD/MM/AAAA", width=120)
        self.entry_fim.pack(side="left", padx=5)

        #BOTÃO PROCESSAR
        self.btn_processar = ctk.CTkButton(self, text="PROCESSAR RELATÓRIO",
                                           command=self.iniciar_processamento,
                                           state="disabled", height=50)
        self.btn_processar.pack(pady=20, fill="x")

        #BOTÃO ABRIR PASTA
        self.btn_abrir_pasta = ctk.CTkButton(self, text="Abrir Pasta de Relatórios", command=self.abrir_pasta_saida,
                                             fg_color="green", hover_color="darkgreen")

        #LOG
        self.txt_log = ctk.CTkTextbox(self, height=200)
        self.txt_log.pack(pady=5, fill="x")
        self.toggle_datas()


    def toggle_datas(self):
        state = "normal" if self.chk_usar_filtro.get() == 1 else "disabled"
        self.entry_inicio.configure(state=state)
        self.entry_fim.configure(state=state)

    def selecionar_arquivo(self):
        caminho = filedialog.askopenfilename(filetypes=[("Arquivos Excel", "*.xlsx")])
        if caminho:
            self.arquivo_selecionado = caminho
            self.lbl_arquivo.configure(text=f"Selecionado: {os.path.basename(caminho)}", text_color="white")
            self.btn_processar.configure(state="normal")

    def iniciar_processamento(self):
        data_ini_iso = None
        data_fim_iso = None

        if self.chk_usar_filtro.get() == 1:
            ini_txt = self.entry_inicio.get()
            fim_txt = self.entry_fim.get()
            data_ini_iso = self.converter_data_br_para_iso(ini_txt)
            data_fim_iso = self.converter_data_br_para_iso(fim_txt)

            if not data_ini_iso or not data_fim_iso:
                messagebox.showwarning("Formato Inválido", "Use DD/MM/AAAA\nEx: 01/01/2024")
                return
            self.log(f"Filtro ativado: De {ini_txt} até {fim_txt}")
        else:
            self.log("Processando todo o período...")

        self.btn_processar.configure(state="disabled", text="Processando...")
        thread = threading.Thread(target=self.rodar_logica_backend, args=(data_ini_iso, data_fim_iso))
        thread.start()

    def rodar_logica_backend(self, dt_ini, dt_fim):
        try:
            self.log("Lendo arquivo Excel...")
            loader = ExcelLoader(self.arquivo_selecionado)
            df = loader.carregar()

            self.log("Calculando jornadas...")
            processador = Processador(df)
            resultados = processador.executar_analise(data_inicio_filtro=dt_ini, data_fim_filtro=dt_fim)

            if not resultados:
                self.log("⚠️ ATENÇÃO: Nenhum dado encontrado!")
                messagebox.showwarning("Vazio", "Nenhuma jornada encontrada para este período.")
                self.finalizar_sucesso()
                return

            # SALVA NO BANCO
            self.log("Salvando no Histórico...")
            banco = BancoDeDados()
            banco.salvar_jornadas(resultados)

            # GERA EXCEL
            self.log(f"Gerando relatório com {len(resultados)} jornadas...")
            reporter = ExcelReporter()

            nome_arquivo = "Relatorio_Final.xlsx"
            if dt_ini:
                nome_arquivo = f"Relatorio_{dt_ini}_ate_{dt_fim}.xlsx"

            reporter.gerar_relatorio_excel(resultados, nome_arquivo)

            self.log("✅ SUCESSO! Relatório gerado.")
            self.finalizar_sucesso()

        except Exception as e:
            self.log(f"❌ ERRO: {str(e)}")
            self.btn_processar.configure(state="normal", text="TENTAR NOVAMENTE")

    def finalizar_sucesso(self):
        self.btn_processar.configure(state="normal", text="PROCESSAR NOVAMENTE")
        self.btn_abrir_pasta.pack(pady=10)

    def abrir_pasta_saida(self):
        # Garante que cria a pasta se ela não existir
        caminho_pasta = os.path.abspath("data/output")
        if not os.path.exists(caminho_pasta):
            os.makedirs(caminho_pasta)

        os.startfile(caminho_pasta)

    def log(self, mensagem):
        """Escreve no log de forma segura para threads"""
        self.after(0, self._atualizar_log_ui, mensagem)

    def _atualizar_log_ui(self, mensagem):
        self.txt_log.insert("end", f"> {mensagem}\n")
        self.txt_log.see("end")

    def converter_data_br_para_iso(self, data_br):
        """Converte DD/MM/AAAA para YYYY-MM-DD"""
        try:
            obj_data = datetime.strptime(data_br, "%d/%m/%Y")
            return obj_data.strftime("%Y-%m-%d")
        except ValueError:
            return None

    def finalizar_sucesso(self):
        """Atualiza a UI após o fim do processamento"""
        self.after(0, lambda: self.btn_processar.configure(state="normal", text="PROCESSAR NOVAMENTE"))
        self.after(0, lambda: self.btn_abrir_pasta.pack(pady=10))


if __name__ == "__main__":
    app = AppPonto()
    app.mainloop()