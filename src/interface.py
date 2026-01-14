import customtkinter as ctk
import tkinter as tk  # Necessário para o PhotoImage
from tkinter import filedialog, messagebox
import threading
import os
from datetime import datetime

# Importando as suas classes
from src.loader import ExcelLoader
from src.processador import Processador
from src.reporter import ExcelReporter
from src.database import BancoDeDados
from src.view_dashboard import DashboardWindow


class AppPonto(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- Configurações da Janela ---
        self.title("Tempus - Time & Agility")
        self.geometry("800x650")
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        # --- CONFIGURAÇÃO DO ÍCONE (Corrigido) ---
        try:
            # 1. Define o caminho exato
            caminho_base = os.path.dirname(os.path.abspath(__file__))
            caminho_icone = os.path.join(caminho_base, "IMG", "ICON.png")

            # 2. Carrega a imagem salvando no SELF (Essencial!)
            if os.path.exists(caminho_icone):
                self.icone_img = tk.PhotoImage(file=caminho_icone)  # <--- O SEGREDO ESTÁ AQUI
                self.iconphoto(False, self.icone_img)

                # 3. Força o Windows a reconhecer o ícone na barra de tarefas
                try:
                    from ctypes import windll
                    myappid = 'empresa.tempus.rh.1.0'
                    windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
                except:
                    pass
            else:
                print(f"⚠️ Aviso: Arquivo não encontrado em: {caminho_icone}")

        except Exception as e:
            print(f"⚠️ Erro ao carregar ícone: {e}")

        # --- Inicialização das Variáveis ---
        self.arquivo_selecionado = None
        self._criar_elementos()

    def _criar_elementos(self):
        # 1. Título
        self.lbl_titulo = ctk.CTkLabel(self, text="Tratamento de Ponto Eletrônico", font=("Roboto", 24, "bold"))
        self.lbl_titulo.pack(pady=(20, 10))

        # 2. Botão Dashboard (Destaque)
        self.btn_dash = ctk.CTkButton(self, text="📊 ABRIR DASHBOARD DE GESTÃO",
                                      command=self.abrir_dashboard,
                                      fg_color="#8A2BE2", hover_color="#4B0082",
                                      height=40, font=("Roboto", 14, "bold"))
        self.btn_dash.pack(pady=(0, 20))

        # 3. Área de Seleção de Arquivo
        self.frame_arquivo = ctk.CTkFrame(self)
        self.frame_arquivo.pack(pady=5, padx=20, fill="x")

        self.btn_selecionar = ctk.CTkButton(self.frame_arquivo, text="Selecionar Excel (.xlsx)",
                                            command=self.selecionar_arquivo)
        self.btn_selecionar.pack(side="left", padx=10, pady=10)

        self.lbl_arquivo = ctk.CTkLabel(self.frame_arquivo, text="Nenhum arquivo selecionado", text_color="gray")
        self.lbl_arquivo.pack(side="left", padx=10)

        # 4. Área de Filtro de Datas
        self.frame_datas = ctk.CTkFrame(self)
        self.frame_datas.pack(pady=10, padx=20, fill="x")

        self.chk_usar_filtro = ctk.CTkCheckBox(self.frame_datas, text="Filtrar por Período Específico",
                                               command=self.toggle_datas)
        self.chk_usar_filtro.pack(pady=10, anchor="w", padx=10)

        self.subframe_inputs = ctk.CTkFrame(self.frame_datas, fg_color="transparent")
        self.subframe_inputs.pack(fill="x", padx=10, pady=(0, 10))

        self.lbl_inicio = ctk.CTkLabel(self.subframe_inputs, text="Data Início:")
        self.lbl_inicio.pack(side="left", padx=(0, 5))

        self.entry_inicio = ctk.CTkEntry(self.subframe_inputs, placeholder_text="DD/MM/AAAA", width=100)
        self.entry_inicio.pack(side="left", padx=(0, 20))

        self.lbl_fim = ctk.CTkLabel(self.subframe_inputs, text="Data Fim:")
        self.lbl_fim.pack(side="left", padx=(0, 5))

        self.entry_fim = ctk.CTkEntry(self.subframe_inputs, placeholder_text="DD/MM/AAAA", width=100)
        self.entry_fim.pack(side="left")

        # Inicia desativado
        self.toggle_datas()

        # 5. Botão de Processar
        self.btn_processar = ctk.CTkButton(self, text="PROCESSAR RELATÓRIO", command=self.iniciar_processamento,
                                           state="disabled", height=50, font=("Roboto", 16))
        self.btn_processar.pack(pady=20, padx=50, fill="x")

        # 6. Log
        self.txt_log = ctk.CTkTextbox(self, height=120)
        self.txt_log.pack(pady=5, padx=20, fill="x")
        self.log("Sistema pronto. Aguardando arquivo...")

        # 7. Botão Abrir Pasta (Inicialmente oculto ou criado sob demanda, aqui deixei criado)
        self.btn_abrir_pasta = ctk.CTkButton(self, text="Abrir Pasta de Relatórios", command=self.abrir_pasta_saida,
                                             fg_color="green", hover_color="darkgreen")
        # Ele só aparece no pack() quando finaliza sucesso

    def toggle_datas(self):
        """Ativa/Desativa inputs de data"""
        if self.chk_usar_filtro.get() == 1:
            self.entry_inicio.configure(state="normal", text_color="white")
            self.entry_fim.configure(state="normal", text_color="white")
        else:
            self.entry_inicio.configure(state="disabled", text_color="gray")
            self.entry_fim.configure(state="disabled", text_color="gray")

    def log(self, mensagem):
        self.txt_log.insert("end", f"> {mensagem}\n")
        self.txt_log.see("end")

    def selecionar_arquivo(self):
        caminho = filedialog.askopenfilename(filetypes=[("Arquivos Excel", "*.xlsx")])
        if caminho:
            self.arquivo_selecionado = caminho
            self.lbl_arquivo.configure(text=f"Selecionado: {os.path.basename(caminho)}", text_color="white")
            self.btn_processar.configure(state="normal")
            self.log(f"Arquivo carregado.")

    def converter_data_br_para_iso(self, data_br):
        try:
            obj_data = datetime.strptime(data_br, "%d/%m/%Y")
            return obj_data.strftime("%Y-%m-%d")
        except ValueError:
            return None

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

    def abrir_dashboard(self):
        banco = BancoDeDados()
        dados = banco.obter_kpis_dashboard()

        if not dados:
            messagebox.showwarning("Vazio", "Processe algum arquivo primeiro para alimentar o banco de dados!")
            return

        dash = DashboardWindow(dados)
        dash.grab_set()


if __name__ == "__main__":
    app = AppPonto()
    app.mainloop()