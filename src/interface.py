import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog
import threading
import os
from datetime import datetime

from src.loader import ExcelLoader
from src.processador import Processador
from src.reporter import ExcelReporter
from src.reporter_revisao import ExcelReporterRevisao
from src.leitor_revisao import LeitorRevisao
from src.database import BancoDeDados
from src.view_dashboard import DashboardWindow


OPCAO_TODAS = "Todas as lojas"
OPCAO_TODOS = "Todos os meses"


class AppPonto(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.bind("<Control-r>", lambda e: self.reiniciar())

        largura_janela = 1000
        altura_janela  = 900
        largura_tela   = self.winfo_screenwidth()
        altura_tela    = self.winfo_screenheight()
        pos_x = largura_tela - largura_janela
        pos_y = (altura_tela // 2) - (altura_janela // 2)
        self.geometry(f"{largura_janela}x{altura_janela}+{pos_x}+{pos_y}")

        self.title("Tempus - Time & Agility")
        ctk.set_appearance_mode("Dark")

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ── Sidebar ───────────────────────────────────────────────────────────
        self.sidebar_frame = ctk.CTkFrame(self, width=210, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_propagate(False)
        self.sidebar_frame.grid_rowconfigure(5, weight=1)

        ctk.CTkLabel(
            self.sidebar_frame, text="TEMPUS",
            font=ctk.CTkFont(size=20, weight="bold")
        ).grid(row=0, column=0, padx=20, pady=(20, 10))

        ctk.CTkButton(
            self.sidebar_frame, text="Processar Ponto",
            command=self._ir_para_home
        ).grid(row=1, column=0, padx=20, pady=10)

        ctk.CTkButton(
            self.sidebar_frame, text="Dashboard",
            fg_color="#8A2BE2", hover_color="#4B0082",
            command=self.abrir_dashboard
        ).grid(row=2, column=0, padx=20, pady=10)

        # ── Separador visual ──────────────────────────────────────────────────
        # Criado aqui mas inserido no grid só quando o dashboard abre
        self.sep = ctk.CTkFrame(self.sidebar_frame, height=1, fg_color="#444")

        # ── Bloco de filtros ──────────────────────────────────────────────────
        self.filtros_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")

        ctk.CTkLabel(
            self.filtros_frame, text="FILTROS",
            font=ctk.CTkFont(size=12, weight="bold"), text_color="#aaa"
        ).pack(anchor="w", padx=16, pady=(12, 6))

        # Seletor de Loja
        ctk.CTkLabel(
            self.filtros_frame, text="Loja", font=("Roboto", 11)
        ).pack(anchor="w", padx=16)

        self.var_loja = ctk.StringVar(value=OPCAO_TODAS)
        self.opt_loja = ctk.CTkOptionMenu(
            self.filtros_frame,
            variable=self.var_loja,
            values=[OPCAO_TODAS],
            width=178,
            # SEM command — não atualiza automaticamente
        )
        self.opt_loja.pack(padx=16, pady=(4, 12))

        # Seletor de Mês/Ano
        ctk.CTkLabel(
            self.filtros_frame, text="Mês / Ano", font=("Roboto", 11)
        ).pack(anchor="w", padx=16)

        self.var_mes = ctk.StringVar(value=OPCAO_TODOS)
        self.opt_mes = ctk.CTkOptionMenu(
            self.filtros_frame,
            variable=self.var_mes,
            values=[OPCAO_TODOS],
            width=178,
            # SEM command — não atualiza automaticamente
        )
        self.opt_mes.pack(padx=16, pady=(4, 12))

        # Botão Aplicar — único gatilho de atualização
        ctk.CTkButton(
            self.filtros_frame, text="Aplicar Filtros",
            fg_color="#8A2BE2", hover_color="#4B0082",
            command=self._aplicar_filtros
        ).pack(padx=16, pady=(0, 16), fill="x")

        # ── Container principal ───────────────────────────────────────────────
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.container.grid_columnconfigure(0, weight=1)
        self.container.grid_rowconfigure(0, weight=1)

        self.frames = {}
        self.frames["Home"] = HomeFrame(parent=self.container, controller=self)
        self.frames["Home"].grid(row=0, column=0, sticky="nsew")

        self.show_frame("Home")
        self._configurar_icone()

    # ─────────────────────────────────────────────────────────────────────────
    # NAVEGAÇÃO
    # ─────────────────────────────────────────────────────────────────────────

    def show_frame(self, page_name):
        self.frames[page_name].tkraise()

    def _ir_para_home(self):
        self._esconder_filtros_sidebar()
        self.show_frame("Home")

    # ─────────────────────────────────────────────────────────────────────────
    # VISIBILIDADE DOS FILTROS
    # ─────────────────────────────────────────────────────────────────────────

    def _mostrar_filtros_sidebar(self):
        self.sep.grid(row=3, column=0, padx=16, pady=(5, 0), sticky="ew")
        self.filtros_frame.grid(row=4, column=0, sticky="nsew")

    def _esconder_filtros_sidebar(self):
        self.sep.grid_remove()
        self.filtros_frame.grid_remove()

    def _popular_filtros(self, filtros: dict):
        lojas = [OPCAO_TODAS] + filtros.get("lojas", [])
        meses = [OPCAO_TODOS] + filtros.get("meses", [])

        self.opt_loja.configure(values=lojas)
        self.opt_mes.configure(values=meses)

        if self.var_loja.get() not in lojas:
            self.var_loja.set(OPCAO_TODAS)
        if self.var_mes.get() not in meses:
            self.var_mes.set(OPCAO_TODOS)

    # ─────────────────────────────────────────────────────────────────────────
    # APLICAR FILTROS — acionado APENAS pelo botão
    # ─────────────────────────────────────────────────────────────────────────

    def _aplicar_filtros(self):
        loja    = self.var_loja.get()
        mes_ano = self.var_mes.get()

        loja_param    = None if loja    == OPCAO_TODAS else loja
        mes_ano_param = None if mes_ano == OPCAO_TODOS else mes_ano

        banco = BancoDeDados()
        dados = banco.obter_dados_dashboard(loja=loja_param, mes_ano=mes_ano_param)
        self._reconstruir_dashboard(dados)

    def _reconstruir_dashboard(self, dados):
        if "Dashboard" in self.frames:
            self.frames["Dashboard"].destroy()

        self.frames["Dashboard"] = DashboardWindow(
            parent=self.container, controller=self, dados=dados
        )
        self.frames["Dashboard"].grid(row=0, column=0, sticky="nsew")
        self.show_frame("Dashboard")

    # ─────────────────────────────────────────────────────────────────────────
    # ABRIR DASHBOARD
    # ─────────────────────────────────────────────────────────────────────────

    def abrir_dashboard(self):
        banco   = BancoDeDados()
        filtros = banco.obter_filtros_disponiveis()

        if not filtros["lojas"] and not filtros["meses"]:
            messagebox.showwarning(
                "Vazio", "Processe algum arquivo primeiro para alimentar o banco de dados!"
            )
            return

        self._popular_filtros(filtros)
        self._mostrar_filtros_sidebar()

        dados = banco.obter_dados_dashboard()
        self._reconstruir_dashboard(dados)

    # ─────────────────────────────────────────────────────────────────────────
    # UTILITÁRIOS
    # ─────────────────────────────────────────────────────────────────────────

    def reiniciar(self, event=None):
        self.destroy()
        import sys
        os.startfile(sys.argv[0])

    def _configurar_icone(self):
        try:
            caminho_base  = os.path.dirname(os.path.abspath(__file__))
            caminho_icone = os.path.join(caminho_base, "IMG", "ICON.png")
            if os.path.exists(caminho_icone):
                self.icone_img = tk.PhotoImage(file=caminho_icone)
                self.iconphoto(False, self.icone_img)
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# HOME FRAME
# ─────────────────────────────────────────────────────────────────────────────

class HomeFrame(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.arquivo_selecionado = None

        ctk.CTkLabel(self, text="Tratamento de Ponto Eletrônico",
                     font=("Roboto", 24, "bold")).pack(pady=(10, 20))

        frame_arquivo = ctk.CTkFrame(self)
        frame_arquivo.pack(pady=5, fill="x")

        ctk.CTkButton(frame_arquivo, text="Selecionar Excel (.xlsx)",
                      command=self.selecionar_arquivo).pack(side="left", padx=10, pady=10)

        self.lbl_arquivo = ctk.CTkLabel(frame_arquivo, text="Nenhum arquivo selecionado",
                                        text_color="gray")
        self.lbl_arquivo.pack(side="left", padx=10)

        frame_datas = ctk.CTkFrame(self)
        frame_datas.pack(pady=10, fill="x")

        self.chk_usar_filtro = ctk.CTkCheckBox(frame_datas, text="Filtrar por Período Específico",
                                               command=self.toggle_datas)
        self.chk_usar_filtro.pack(pady=10, anchor="w", padx=10)

        subframe = ctk.CTkFrame(frame_datas, fg_color="transparent")
        subframe.pack(fill="x", padx=10, pady=(0, 10))

        self.entry_inicio = ctk.CTkEntry(subframe, placeholder_text="DD/MM/AAAA", width=120)
        self.entry_inicio.pack(side="left", padx=5)

        self.entry_fim = ctk.CTkEntry(subframe, placeholder_text="DD/MM/AAAA", width=120)
        self.entry_fim.pack(side="left", padx=5)

        frame_etapa1 = ctk.CTkFrame(self, border_width=1, border_color="#444")
        frame_etapa1.pack(fill="x", pady=(10, 5))

        ctk.CTkLabel(frame_etapa1, text="ETAPA 1 — Gerar Planilha de Revisão",
                     font=("Roboto", 13, "bold")).pack(anchor="w", padx=12, pady=(10, 2))
        ctk.CTkLabel(frame_etapa1,
                     text="Segmenta as jornadas e gera um Excel para revisão. Corrija agrupamentos antes de confirmar.",
                     text_color="gray", font=("Roboto", 11)).pack(anchor="w", padx=12, pady=(0, 6))

        self.btn_gerar_revisao = ctk.CTkButton(
            frame_etapa1, text="GERAR PLANILHA DE REVISÃO",
            command=self.iniciar_etapa1, state="disabled", height=45)
        self.btn_gerar_revisao.pack(padx=12, pady=(0, 12), fill="x")

        frame_etapa2 = ctk.CTkFrame(self, border_width=1, border_color="#444")
        frame_etapa2.pack(fill="x", pady=(5, 10))

        ctk.CTkLabel(frame_etapa2, text="ETAPA 2 — Confirmar e Gerar Relatório Final",
                     font=("Roboto", 13, "bold")).pack(anchor="w", padx=12, pady=(10, 2))
        ctk.CTkLabel(frame_etapa2,
                     text="Após revisar a planilha, clique aqui para calcular, gerar o relatório e salvar no banco.",
                     text_color="gray", font=("Roboto", 11)).pack(anchor="w", padx=12, pady=(0, 6))

        self.btn_confirmar = ctk.CTkButton(
            frame_etapa2, text="REVISÃO CONCLUÍDA — GERAR RELATÓRIO E SALVAR",
            command=self.iniciar_etapa2, state="disabled", height=45,
            fg_color="#1a7a1a", hover_color="#145214")
        self.btn_confirmar.pack(padx=12, pady=(0, 12), fill="x")

        self.btn_abrir_pasta = ctk.CTkButton(
            self, text="Abrir Pasta de Relatórios",
            command=self.abrir_pasta_saida,
            fg_color="green", hover_color="darkgreen")

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
            self.lbl_arquivo.configure(text=f"Selecionado: {os.path.basename(caminho)}",
                                       text_color="white")
            self.btn_gerar_revisao.configure(state="normal")

    def log(self, mensagem):
        self.after(0, self._atualizar_log_ui, mensagem)

    def _atualizar_log_ui(self, mensagem):
        self.txt_log.insert("end", f"> {mensagem}\n")
        self.txt_log.see("end")

    def converter_data_br_para_iso(self, data_br):
        try:
            return datetime.strptime(data_br, "%d/%m/%Y").strftime("%Y-%m-%d")
        except ValueError:
            return None

    def abrir_pasta_saida(self):
        caminho_pasta = os.path.abspath("data/output")
        os.makedirs(caminho_pasta, exist_ok=True)
        os.startfile(caminho_pasta)

    def iniciar_etapa1(self):
        data_ini_iso = data_fim_iso = None

        if self.chk_usar_filtro.get() == 1:
            data_ini_iso = self.converter_data_br_para_iso(self.entry_inicio.get())
            data_fim_iso = self.converter_data_br_para_iso(self.entry_fim.get())
            if not data_ini_iso or not data_fim_iso:
                messagebox.showwarning("Formato Inválido", "Use DD/MM/AAAA\nEx: 01/01/2024")
                return
            self.log(f"Filtro ativado: De {self.entry_inicio.get()} até {self.entry_fim.get()}")
        else:
            self.log("Processando todo o período...")

        self.btn_gerar_revisao.configure(state="disabled", text="Processando...")
        self.btn_confirmar.configure(state="disabled")
        threading.Thread(target=self._rodar_etapa1, args=(data_ini_iso, data_fim_iso)).start()

    def _rodar_etapa1(self, dt_ini, dt_fim):
        try:
            self.log("Lendo arquivo Excel...")
            loader = ExcelLoader(self.arquivo_selecionado)
            df     = loader.carregar()

            self.log("Segmentando jornadas...")
            processador = Processador(df)
            resultados  = processador.executar_analise(
                data_inicio_filtro=dt_ini, data_fim_filtro=dt_fim)

            if not resultados:
                self.log("⚠️ Nenhum dado encontrado para este período.")
                messagebox.showwarning("Vazio", "Nenhuma jornada encontrada para este período.")
                self.after(0, lambda: self.btn_gerar_revisao.configure(
                    state="normal", text="GERAR PLANILHA DE REVISÃO"))
                return

            self.log(f"Gerando planilha de revisão com {len(resultados)} jornadas...")
            reporter = ExcelReporterRevisao()
            reporter.gerar_excel_revisao(resultados)

            self.log("✅ Planilha de revisão gerada! Corrija os agrupamentos e clique em 'Revisão Concluída'.")
            self.after(0, self._finalizar_etapa1)

        except PermissionError:
            self.log("❌ ERRO: Feche o arquivo Excel e tente novamente.")
            self.after(0, lambda: self.btn_gerar_revisao.configure(
                state="normal", text="GERAR PLANILHA DE REVISÃO"))
        except Exception as e:
            self.log(f"❌ ERRO: {str(e)}")
            self.after(0, lambda: self.btn_gerar_revisao.configure(
                state="normal", text="TENTAR NOVAMENTE"))

    def _finalizar_etapa1(self):
        self.btn_gerar_revisao.configure(state="normal", text="GERAR NOVAMENTE")
        self.btn_confirmar.configure(state="normal")
        self.btn_abrir_pasta.pack(pady=(0, 5))

    def iniciar_etapa2(self):
        caminho = ExcelReporterRevisao.caminho_revisao()
        if not os.path.exists(caminho):
            messagebox.showerror(
                "Arquivo não encontrado",
                f"Planilha de revisão não localizada:\n{caminho}\n\nExecute a Etapa 1 primeiro."
            )
            return

        self.btn_confirmar.configure(state="disabled", text="Processando...")
        threading.Thread(target=self._rodar_etapa2, args=(caminho,)).start()

    def _rodar_etapa2(self, caminho: str):
        try:
            self.log("Relendo planilha de revisão...")
            leitor     = LeitorRevisao()
            resultados = leitor.carregar_e_recalcular(caminho)

            if not resultados:
                self.log("⚠️ Nenhuma jornada encontrada na planilha de revisão.")
                self.after(0, lambda: self.btn_confirmar.configure(
                    state="normal", text="REVISÃO CONCLUÍDA — GERAR RELATÓRIO E SALVAR"))
                return

            self.log(f"Calculadas {len(resultados)} jornadas. Salvando no banco...")
            banco = BancoDeDados()
            banco.salvar_jornadas(resultados)

            self.log("Gerando relatório final com abas...")
            reporter = ExcelReporter()
            reporter.gerar_relatorio_excel(resultados, "Relatorio_Final.xlsx")

            self.log("✅ SUCESSO! Relatório gerado e dados salvos no banco.")
            self.after(0, self._finalizar_etapa2)

        except PermissionError:
            self.log("❌ ERRO: Feche o arquivo Excel e tente novamente.")
            self.after(0, lambda: self.btn_confirmar.configure(
                state="normal", text="REVISÃO CONCLUÍDA — GERAR RELATÓRIO E SALVAR"))
        except Exception as e:
            self.log(f"❌ ERRO: {str(e)}")
            self.after(0, lambda: self.btn_confirmar.configure(
                state="normal", text="TENTAR NOVAMENTE"))

    def _finalizar_etapa2(self):
        self.btn_confirmar.configure(
            state="normal", text="REVISÃO CONCLUÍDA — GERAR RELATÓRIO E SALVAR")


if __name__ == "__main__":
    app = AppPonto()
    app.mainloop()