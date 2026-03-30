import customtkinter as ctk
import tkinter
from tkinter import messagebox, filedialog
import threading
import os
from datetime import datetime
from PIL import Image

from src.loader import ExcelLoader
from src.processador import Processador
from src.reporter import ExcelReporter
from src.reporter_revisao import ExcelReporterRevisao
from src.leitor_revisao import LeitorRevisao
from src.database import BancoDeDados
from src.view_dashboard import DashboardWindow
from src.view_configuracoes import ConfiguracoesWindow


OPCAO_TODAS_LOJAS = "Todas as lojas"
OPCAO_TODOS_MESES = "Todos os meses"


class AppPonto(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.bind("<Control-r>", lambda e: self.reiniciar())

        diretorio_assets = os.path.dirname(os.path.abspath(__file__))
        caminho_icone = os.path.join(diretorio_assets, "IMG/favicon.ico")

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
        self.sidebar_frame.grid_rowconfigure(6, weight=1)

        ctk.CTkLabel(
            self.sidebar_frame, text="TEMPUS",
            font=ctk.CTkFont(size=20, weight="bold")
        ).grid(row=0, column=0, padx=20, pady=(20, 10))

        # Por isso:
        logo_img = ctk.CTkImage(
            light_image=Image.open(caminho_icone),
            dark_image=Image.open(caminho_icone),
            size=(30, 30)
        )
        ctk.CTkLabel(
            self.sidebar_frame,
            text="  TEMPUS",
            image=logo_img,
            compound="left",
            font=ctk.CTkFont(size=20, weight="bold")
        ).grid(row=0, column=0, padx=20, pady=(20, 10))


        ctk.CTkButton(
            self.sidebar_frame, text="Processar Ponto",
            command=self._navegar_para_home
        ).grid(row=1, column=0, padx=20, pady=10)

        ctk.CTkButton(
            self.sidebar_frame, text="Dashboard",
            fg_color="#8A2BE2", hover_color="#4B0082",
            command=self.abrir_tela_dashboard
        ).grid(row=2, column=0, padx=20, pady=10)

        ctk.CTkButton(
            self.sidebar_frame, text="⚙ Configurações",
            fg_color="#3a3a3a", hover_color="#2a2a2a",
            command=self.abrir_tela_configuracoes
        ).grid(row=3, column=0, padx=20, pady=(0, 10))

        self.separador_sidebar = ctk.CTkFrame(self.sidebar_frame, height=1, fg_color="#444")

        # ── Painel de filtros ─────────────────────────────────────────────────
        self.painel_filtros = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")

        ctk.CTkLabel(
            self.painel_filtros, text="FILTROS",
            font=ctk.CTkFont(size=12, weight="bold"), text_color="#aaa"
        ).pack(anchor="w", padx=16, pady=(12, 6))

        ctk.CTkLabel(self.painel_filtros, text="Loja",
                     font=("Roboto", 11)).pack(anchor="w", padx=16)
        self.var_loja_selecionada = ctk.StringVar(value=OPCAO_TODAS_LOJAS)
        self.seletor_loja = ctk.CTkOptionMenu(
            self.painel_filtros,
            variable=self.var_loja_selecionada,
            values=[OPCAO_TODAS_LOJAS],
            width=178
        )
        self.seletor_loja.pack(padx=16, pady=(4, 12))

        ctk.CTkLabel(self.painel_filtros, text="Mês / Ano",
                     font=("Roboto", 11)).pack(anchor="w", padx=16)
        self.var_mes_selecionado = ctk.StringVar(value=OPCAO_TODOS_MESES)
        self.seletor_mes = ctk.CTkOptionMenu(
            self.painel_filtros,
            variable=self.var_mes_selecionado,
            values=[OPCAO_TODOS_MESES],
            width=178
        )
        self.seletor_mes.pack(padx=16, pady=(4, 12))

        self.btn_aplicar_filtros = ctk.CTkButton(
            self.painel_filtros, text="Aplicar Filtros",
            fg_color="#8A2BE2", hover_color="#4B0082",
            command=self._aplicar_filtros_e_recarregar
        )
        self.btn_aplicar_filtros.pack(padx=16, pady=(0, 16), fill="x")

        # ── Container principal ───────────────────────────────────────────────
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.container.grid_columnconfigure(0, weight=1)
        self.container.grid_rowconfigure(0, weight=1)

        self.frames = {}
        self.frames["Home"] = HomeFrame(parent=self.container, controller=self)
        self.frames["Home"].grid(row=0, column=0, sticky="nsew")

        # Frame de carregamento — exibido enquanto o banco e o Matplotlib trabalham
        self.frames["Loading"] = self._criar_frame_de_carregamento()
        self.frames["Loading"].grid(row=0, column=0, sticky="nsew")

        self.show_frame("Home")
        self._configurar_icone()

    # ─────────────────────────────────────────────────────────────────────────
    # FRAME DE CARREGAMENTO
    # ─────────────────────────────────────────────────────────────────────────

    def _criar_frame_de_carregamento(self) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self.container, fg_color="transparent")

        ctk.CTkLabel(
            frame, text="Carregando dashboard...",
            font=("Roboto", 16), text_color="gray"
        ).place(relx=0.5, rely=0.45, anchor="center")

        self.barra_progresso = ctk.CTkProgressBar(frame, mode="indeterminate", width=260)
        self.barra_progresso.place(relx=0.5, rely=0.55, anchor="center")

        return frame

    def _exibir_tela_de_carregamento(self):
        """Mostra o spinner e desabilita o botão para evitar cliques duplos."""
        self.show_frame("Loading")
        self.barra_progresso.start()
        self.btn_aplicar_filtros.configure(state="disabled")

    def _encerrar_tela_de_carregamento(self):
        self.barra_progresso.stop()
        self.btn_aplicar_filtros.configure(state="normal")

    # ─────────────────────────────────────────────────────────────────────────
    # NAVEGAÇÃO
    # ─────────────────────────────────────────────────────────────────────────

    def show_frame(self, page_name):
        self.frames[page_name].tkraise()

    def _navegar_para_home(self):
        self._ocultar_painel_de_filtros()
        self.show_frame("Home")

    # ─────────────────────────────────────────────────────────────────────────
    # PAINEL DE FILTROS DA SIDEBAR
    # ─────────────────────────────────────────────────────────────────────────

    def _exibir_painel_de_filtros(self):
        self.separador_sidebar.grid(row=3, column=0, padx=16, pady=(5, 0), sticky="ew")
        self.painel_filtros.grid(row=4, column=0, sticky="nsew")

    def _ocultar_painel_de_filtros(self):
        self.separador_sidebar.grid_remove()
        self.painel_filtros.grid_remove()

    def _preencher_opcoes_de_filtro(self, filtros_disponiveis: dict):
        lojas = [OPCAO_TODAS_LOJAS] + filtros_disponiveis.get("lojas", [])
        meses = [OPCAO_TODOS_MESES] + filtros_disponiveis.get("meses", [])

        self.seletor_loja.configure(values=lojas)
        self.seletor_mes.configure(values=meses)

        if self.var_loja_selecionada.get() not in lojas:
            self.var_loja_selecionada.set(OPCAO_TODAS_LOJAS)
        if self.var_mes_selecionado.get() not in meses:
            self.var_mes_selecionado.set(OPCAO_TODOS_MESES)

    # ─────────────────────────────────────────────────────────────────────────
    # CARREGAMENTO DO DASHBOARD EM THREAD
    # ─────────────────────────────────────────────────────────────────────────

    def _aplicar_filtros_e_recarregar(self):
        loja    = self.var_loja_selecionada.get()
        mes_ano = self.var_mes_selecionado.get()

        loja_param    = None if loja    == OPCAO_TODAS_LOJAS else loja
        mes_ano_param = None if mes_ano == OPCAO_TODOS_MESES else mes_ano

        self._exibir_tela_de_carregamento()
        threading.Thread(
            target=self._buscar_dados_e_reconstruir_dashboard,
            args=(loja_param, mes_ano_param),
            daemon=True
        ).start()

    def abrir_tela_dashboard(self):
        banco               = BancoDeDados()
        filtros_disponiveis = banco.buscar_filtros_disponiveis()

        if not filtros_disponiveis["lojas"] and not filtros_disponiveis["meses"]:
            messagebox.showwarning(
                "Vazio", "Processe algum arquivo primeiro para alimentar o banco de dados!"
            )
            return

        self._preencher_opcoes_de_filtro(filtros_disponiveis)
        self._exibir_painel_de_filtros()
        self._exibir_tela_de_carregamento()

        threading.Thread(
            target=self._buscar_dados_e_reconstruir_dashboard,
            args=(None, None),
            daemon=True
        ).start()

    def _buscar_dados_e_reconstruir_dashboard(self, loja_param, mes_ano_param):
        """
        Roda em thread separada — busca os dados do banco e agenda a
        reconstrução do dashboard na thread principal via self.after().
        Tkinter não é thread-safe: todo acesso a widgets deve acontecer
        na thread principal, por isso o after() é obrigatório aqui.
        """
        try:
            dados = BancoDeDados().buscar_dados_dashboard(
                loja=loja_param, mes_ano=mes_ano_param
            )
            self.after(0, self._reconstruir_tela_dashboard, dados)
        except Exception as e:
            self.after(0, self._encerrar_tela_de_carregamento)
            self.after(0, lambda: messagebox.showerror("Erro", f"Falha ao carregar dashboard:\n{e}"))

    def _reconstruir_tela_dashboard(self, dados):
        """
        Sempre chamada via self.after() — roda na thread principal do Tkinter.
        """
        self._encerrar_tela_de_carregamento()

        if "Dashboard" in self.frames:
            self.frames["Dashboard"].destroy()

        self.frames["Dashboard"] = DashboardWindow(
            parent=self.container, controller=self, dados=dados
        )
        self.frames["Dashboard"].grid(row=0, column=0, sticky="nsew")
        self.show_frame("Dashboard")

    # ─────────────────────────────────────────────────────────────────────────
    # UTILITÁRIOS
    # ─────────────────────────────────────────────────────────────────────────

    def abrir_tela_configuracoes(self):
        self._ocultar_painel_de_filtros()

        if "Configuracoes" in self.frames:
            self.frames["Configuracoes"].destroy()

        banco = BancoDeDados()
        self.frames["Configuracoes"] = ConfiguracoesWindow(
            parent=self.container, controller=self, banco=banco
        )
        self.frames["Configuracoes"].grid(row=0, column=0, sticky="nsew")
        self.show_frame("Configuracoes")

    def reiniciar(self, event=None):
        self.destroy()
        import sys
        os.startfile(sys.argv[0])

    def _configurar_icone(self):
        try:
            caminho_base = os.path.dirname(os.path.abspath(__file__))
            caminho_ico = os.path.join(caminho_base, "IMG", "favicon.ico")
            if os.path.exists(caminho_ico):
                self.iconbitmap(caminho_ico)
        except Exception as e:
            print(f"Erro ao configurar ícone: {e}")


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
            command=self.iniciar_geracao_planilha_revisao, state="disabled", height=45)
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
            command=self.iniciar_geracao_relatorio_final, state="disabled", height=45,
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
        self.after(0, self._escrever_no_log, mensagem)

    def _escrever_no_log(self, mensagem):
        self.txt_log.insert("end", f"> {mensagem}\n")
        self.txt_log.see("end")

    def converter_data_br_para_iso(self, data_br):
        try:
            return datetime.strptime(data_br, "%d/%m/%Y").strftime("%Y-%m-%d")
        except ValueError:
            return None

    def abrir_pasta_saida(self):
        caminho = os.path.abspath("data/output")
        os.makedirs(caminho, exist_ok=True)
        os.startfile(caminho)

    def iniciar_geracao_planilha_revisao(self):
        dt_ini = dt_fim = None

        if self.chk_usar_filtro.get() == 1:
            dt_ini = self.converter_data_br_para_iso(self.entry_inicio.get())
            dt_fim = self.converter_data_br_para_iso(self.entry_fim.get())
            if not dt_ini or not dt_fim:
                messagebox.showwarning("Formato Inválido", "Use DD/MM/AAAA\nEx: 01/01/2024")
                return
            self.log(f"Filtro ativado: De {self.entry_inicio.get()} até {self.entry_fim.get()}")
        else:
            self.log("Processando todo o período...")

        self.btn_gerar_revisao.configure(state="disabled", text="Processando...")
        self.btn_confirmar.configure(state="disabled")
        threading.Thread(
            target=self._executar_geracao_planilha_revisao,
            args=(dt_ini, dt_fim), daemon=True
        ).start()

    def _executar_geracao_planilha_revisao(self, dt_ini, dt_fim):
        try:
            self.log("Lendo arquivo Excel...")
            df = ExcelLoader(self.arquivo_selecionado).carregar()

            self.log("Segmentando jornadas...")
            resultados = Processador(df).executar_analise(
                data_inicio_filtro=dt_ini, data_fim_filtro=dt_fim)

            if not resultados:
                self.log("⚠️ Nenhum dado encontrado para este período.")
                messagebox.showwarning("Vazio", "Nenhuma jornada encontrada para este período.")
                self.after(0, lambda: self.btn_gerar_revisao.configure(
                    state="normal", text="GERAR PLANILHA DE REVISÃO"))
                return

            self.log(f"Gerando planilha de revisão com {len(resultados)} jornadas...")
            ExcelReporterRevisao().gerar_excel_revisao(resultados)

            self.log("✅ Planilha gerada! Corrija os agrupamentos e clique em 'Revisão Concluída'.")
            self.after(0, self._finalizar_geracao_planilha_revisao)

        except PermissionError:
            self.log("❌ ERRO: Feche o arquivo Excel e tente novamente.")
            self.after(0, lambda: self.btn_gerar_revisao.configure(
                state="normal", text="GERAR PLANILHA DE REVISÃO"))
        except Exception as e:
            self.log(f"❌ ERRO: {e}")
            self.after(0, lambda: self.btn_gerar_revisao.configure(
                state="normal", text="TENTAR NOVAMENTE"))

    def _finalizar_geracao_planilha_revisao(self):
        self.btn_gerar_revisao.configure(state="normal", text="GERAR NOVAMENTE")
        self.btn_confirmar.configure(state="normal")
        self.btn_abrir_pasta.pack(pady=(0, 5))

    def iniciar_geracao_relatorio_final(self):
        caminho_revisao = ExcelReporterRevisao.caminho_revisao()
        if not os.path.exists(caminho_revisao):
            messagebox.showerror(
                "Arquivo não encontrado",
                f"Planilha de revisão não localizada:\n{caminho_revisao}\n\nExecute a Etapa 1 primeiro."
            )
            return

        self.btn_confirmar.configure(state="disabled", text="Processando...")
        threading.Thread(
            target=self._executar_geracao_relatorio_final,
            args=(caminho_revisao,), daemon=True
        ).start()

    def _executar_geracao_relatorio_final(self, caminho_revisao: str):
        try:
            self.log("Relendo planilha de revisão...")
            resultados = LeitorRevisao().carregar_e_recalcular(caminho_revisao)

            if not resultados:
                self.log("⚠️ Nenhuma jornada encontrada na planilha de revisão.")
                self.after(0, lambda: self.btn_confirmar.configure(
                    state="normal", text="REVISÃO CONCLUÍDA — GERAR RELATÓRIO E SALVAR"))
                return

            self.log("Calculando interjornadas...")
            resultados = Processador.calcular_interjornadas(resultados)

            self.log(f"Calculadas {len(resultados)} jornadas. Salvando no banco...")
            BancoDeDados().salvar_jornadas(resultados)

            self.log("Gerando relatório final...")
            ExcelReporter().gerar_relatorio_excel(resultados, "Relatorio_Final.xlsx")

            self.log("✅ SUCESSO! Relatório gerado e dados salvos.")
            self.after(0, self._finalizar_geracao_relatorio_final)

        except PermissionError:
            self.log("❌ ERRO: Feche o arquivo Excel e tente novamente.")
            self.after(0, lambda: self.btn_confirmar.configure(
                state="normal", text="REVISÃO CONCLUÍDA — GERAR RELATÓRIO E SALVAR"))
        except Exception as e:
            self.log(f"❌ ERRO: {e}")
            self.after(0, lambda: self.btn_confirmar.configure(
                state="normal", text="TENTAR NOVAMENTE"))

    def _finalizar_geracao_relatorio_final(self):
        self.btn_confirmar.configure(
            state="normal", text="REVISÃO CONCLUÍDA — GERAR RELATÓRIO E SALVAR")


if __name__ == "__main__":
    app = AppPonto()
    app.mainloop()