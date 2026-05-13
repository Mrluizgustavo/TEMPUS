import customtkinter as ctk
import tkinter
import matplotlib.pyplot as plt
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
from src.auth import sessao_atual


OPCAO_TODAS_LOJAS = "Todas as lojas"
OPCAO_TODOS_MESES = "Todos os meses"


# ─────────────────────────────────────────────────────────────────────────────
# TELA DE LOGIN
# ─────────────────────────────────────────────────────────────────────────────

class TelaLogin(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Tempus — Login")
        self.geometry("420x520")
        self.resizable(False, False)
        ctk.set_appearance_mode("Dark")

        self.banco = BancoDeDados()
        self._construir_ui()

    def _construir_ui(self):
        # Logo / ícone no topo
        logo_img = None
        try:
            caminho_base = os.path.dirname(os.path.abspath(__file__))
            caminho_ico  = os.path.join(caminho_base, "src", "IMG", "favicon.ico")
            if not os.path.exists(caminho_ico):
                caminho_ico = os.path.join(caminho_base, "IMG", "favicon.ico")
            logo_img = ctk.CTkImage(
                light_image=Image.open(caminho_ico),
                dark_image=Image.open(caminho_ico),
                size=(52, 52)
            )
        except Exception:
            pass

        if logo_img:
            ctk.CTkLabel(self, image=logo_img, text="").pack(pady=(40, 4))
        else:
            ctk.CTkLabel(self, text="⏱", font=("Roboto", 40)).pack(pady=(40, 4))

        ctk.CTkLabel(self, text="TEMPUS", font=("Roboto", 32, "bold")).pack(pady=(0, 4))
        ctk.CTkLabel(self, text="Sistema de Gestão de Ponto",
                     font=("Roboto", 12), text_color="#aaa").pack(pady=(0, 32))

        ctk.CTkLabel(self, text="Usuário", anchor="w").pack(fill="x", padx=70)
        self.entry_email = ctk.CTkEntry(self, width=280, placeholder_text="Seu nome de usuário")
        self.entry_email.pack(padx=70, pady=(4, 18))

        ctk.CTkLabel(self, text="Senha", anchor="w").pack(fill="x", padx=70)
        self.entry_senha = ctk.CTkEntry(self, width=280, placeholder_text="••••••••", show="•")
        self.entry_senha.pack(padx=70, pady=(4, 28))
        self.entry_senha.bind("<Return>", lambda e: self._fazer_login())

        self.btn_login = ctk.CTkButton(
            self, text="ENTRAR", width=280,
            fg_color="#8A2BE2", hover_color="#4B0082",
            command=self._fazer_login
        )
        self.btn_login.pack(padx=70)

        self.lbl_erro = ctk.CTkLabel(self, text="", text_color="#ff6b6b", font=("Roboto", 11))
        self.lbl_erro.pack(pady=(14, 0))

    def _fazer_login(self):
        nome = self.entry_email.get().strip()
        senha = self.entry_senha.get()

        if not nome or not senha:
            self.lbl_erro.configure(text="Preencha usuário e senha.")
            return

        self.lbl_erro.configure(text="")
        self.btn_login.configure(state="disabled", text="Verificando...")
        threading.Thread(target=self._validar, args=(nome, senha), daemon=True).start()
        # Sem self.after() aqui — a thread já cuida do resto

    def _validar(self, nome, senha):
        # Roda na thread de background — APENAS trabalho pesado, zero UI
        dados = self.banco.autenticar_usuario(nome, senha)

        if not dados:
            self.banco.registrar_log("LOGIN_FALHOU", f"Tentativa inválida para: {nome}", email=nome)

        # Agenda o resultado de volta na thread principal — único ponto de contato com a UI
        self.after(0, self._aplicar_resultado_login, dados, nome)

    def _aplicar_resultado_login(self, dados, nome):
        # Roda na thread principal via self.after() — pode tocar em widgets livremente
        if not dados:
            self.lbl_erro.configure(text="Usuário ou senha incorretos.")
            self.btn_login.configure(state="normal", text="ENTRAR")
            return

        self.banco.registrar_log("LOGIN", "Login realizado com sucesso",
                                 id_usuario=dados["id"], email=dados["nome"])
        sessao_atual.logar(dados)
        self.destroy()

        if dados["trocar_senha"]:
            TelaTrocarSenha(self.banco).mainloop()
        else:
            AppPonto(self.banco).mainloop()

# ─────────────────────────────────────────────────────────────────────────────
# TELA DE TROCA DE SENHA (primeiro acesso obrigatório)
# ─────────────────────────────────────────────────────────────────────────────

class TelaTrocarSenha(ctk.CTk):
    def __init__(self, banco: BancoDeDados):
        super().__init__()
        self.banco = banco
        self.title("Tempus — Defina sua senha")
        self.geometry("420x420")
        self.resizable(False, False)
        ctk.set_appearance_mode("Dark")

        ctk.CTkLabel(self, text="Defina sua nova senha",
                     font=("Roboto", 22, "bold")).pack(pady=(50, 8))
        ctk.CTkLabel(self, text="Obrigatório no primeiro acesso.",
                     text_color="#aaa", font=("Roboto", 12)).pack(pady=(0, 30))

        self.entry_nova     = ctk.CTkEntry(self, placeholder_text="Nova senha (mín. 5 caracteres)",
                                           show="•", width=300)
        self.entry_nova.pack(pady=8)
        self.entry_confirma = ctk.CTkEntry(self, placeholder_text="Confirme a nova senha",
                                           show="•", width=300)
        self.entry_confirma.pack(pady=8)

        self.lbl_erro = ctk.CTkLabel(self, text="", text_color="#ff6b6b", font=("Roboto", 11))
        self.lbl_erro.pack(pady=10)

        ctk.CTkButton(self, text="SALVAR E ENTRAR", width=300,
                      fg_color="#1a7a1a", hover_color="#145214",
                      command=self._salvar).pack(pady=8)

    def _salvar(self):
        nova     = self.entry_nova.get()
        confirma = self.entry_confirma.get()

        if len(nova) < 5:
            self.lbl_erro.configure(text="A senha deve ter pelo menos 5 caracteres.")
            return
        if nova != confirma:
            self.lbl_erro.configure(text="As senhas não coincidem.")
            return

        self.banco.alterar_senha(sessao_atual.id, nova)
        self.banco.registrar_log(
            "SENHA_ALTERADA",
            "Troca obrigatória no primeiro acesso",
            id_usuario=sessao_atual.id,
            email=sessao_atual.nome
        )
        self.destroy()
        AppPonto(self.banco).mainloop()


# ─────────────────────────────────────────────────────────────────────────────
# APP PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

class AppPonto(ctk.CTk):
    def __init__(self, banco: BancoDeDados = None):
        super().__init__()
        self.banco = banco or BancoDeDados()

        self.bind("<Control-r>", lambda e: self.reiniciar())

        diretorio_assets = os.path.dirname(os.path.abspath(__file__))
        caminho_icone    = os.path.join(diretorio_assets, "IMG/favicon.ico")

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
        self.sidebar_frame.grid_rowconfigure(10, weight=1)

        logo_img = None
        try:
            logo_img = ctk.CTkImage(
                light_image=Image.open(caminho_icone),
                dark_image=Image.open(caminho_icone),
                size=(30, 30)
            )
        except Exception:
            pass

        ctk.CTkLabel(
            self.sidebar_frame,
            text="  TEMPUS",
            image=logo_img,
            compound="left" if logo_img else "none",
            font=ctk.CTkFont(size=20, weight="bold")
        ).grid(row=0, column=0, padx=20, pady=(20, 10))

        # Exibe nome do usuário logado com badge de role
        badge = {"master": "👑", "admin": "🔧", "operador": "👤"}.get(sessao_atual.role, "👤")
        ctk.CTkLabel(
            self.sidebar_frame,
            text=f"{badge} {sessao_atual.nome}",
            font=("Roboto", 10), text_color="#aaa"
        ).grid(row=1, column=0, padx=20, pady=(0, 6))

        linha_btn = 2

        # Processar Ponto — todos os roles
        ctk.CTkButton(
            self.sidebar_frame, text="Processar Ponto",
            command=self._navegar_para_home
        ).grid(row=linha_btn, column=0, padx=20, pady=6)
        linha_btn += 1

        # Dashboard — todos os roles
        ctk.CTkButton(
            self.sidebar_frame, text="Dashboard",
            fg_color="#8A2BE2", hover_color="#4B0082",
            command=self.abrir_tela_dashboard
        ).grid(row=linha_btn, column=0, padx=20, pady=6)
        linha_btn += 1

        # Configurações — master e admin
        if sessao_atual.pode_configuracoes:
            ctk.CTkButton(
                self.sidebar_frame, text="⚙ Configurações",
                fg_color="#3a3a3a", hover_color="#2a2a2a",
                command=self.abrir_tela_configuracoes
            ).grid(row=linha_btn, column=0, padx=20, pady=6)
            linha_btn += 1

        # Usuários — master e admin
        if sessao_atual.pode_gerenciar_usuarios:
            ctk.CTkButton(
                self.sidebar_frame, text="👥 Usuários",
                fg_color="#1a4a7a", hover_color="#123355",
                command=self.abrir_tela_usuarios
            ).grid(row=linha_btn, column=0, padx=20, pady=6)
            linha_btn += 1

        # Logs de Auditoria — somente master
        if sessao_atual.pode_ver_logs:
            ctk.CTkButton(
                self.sidebar_frame, text="📋 Logs de Auditoria",
                fg_color="#4a3a1a", hover_color="#332a12",
                command=self.abrir_tela_logs
            ).grid(row=linha_btn, column=0, padx=20, pady=6)
            linha_btn += 1

        # Botão sair (sempre no final)
        ctk.CTkButton(
            self.sidebar_frame, text="Sair",
            fg_color="#5a1a1a", hover_color="#3d1111",
            command=self._sair
        ).grid(row=9, column=0, padx=20, pady=(0, 20), sticky="s")

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
            frame, text="Carregando...",
            font=("Roboto", 16), text_color="gray"
        ).place(relx=0.5, rely=0.45, anchor="center")
        self.barra_progresso = ctk.CTkProgressBar(frame, mode="indeterminate", width=260)
        self.barra_progresso.place(relx=0.5, rely=0.55, anchor="center")
        return frame

    def _exibir_tela_de_carregamento(self):
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

    def _exibir_painel_de_filtros(self):
        self.separador_sidebar.grid(row=7, column=0, padx=16, pady=(5, 0), sticky="ew")
        self.painel_filtros.grid(row=8, column=0, sticky="nsew")

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
    # DASHBOARD
    # ─────────────────────────────────────────────────────────────────────────

    def _aplicar_filtros_e_recarregar(self):
        loja    = self.var_loja_selecionada.get()
        mes_ano = self.var_mes_selecionado.get()
        loja_param    = None if loja    == OPCAO_TODAS_LOJAS else loja
        mes_ano_param = None if mes_ano == OPCAO_TODOS_MESES else mes_ano
        self._exibir_tela_de_carregamento()
        threading.Thread(
            target=self._buscar_dados_e_reconstruir_dashboard,
            args=(loja_param, mes_ano_param), daemon=True
        ).start()

    def abrir_tela_dashboard(self):
        filtros_disponiveis = self.banco.buscar_filtros_disponiveis()
        if not filtros_disponiveis["lojas"] and not filtros_disponiveis["meses"]:
            messagebox.showwarning("Vazio", "Processe algum arquivo primeiro!")
            return
        self._preencher_opcoes_de_filtro(filtros_disponiveis)
        self._exibir_painel_de_filtros()
        self._exibir_tela_de_carregamento()
        threading.Thread(
            target=self._buscar_dados_e_reconstruir_dashboard,
            args=(None, None), daemon=True
        ).start()
        self.banco.registrar_log(
            "ABRIU_DASHBOARD", "",
            id_usuario=sessao_atual.id, email=sessao_atual.nome
        )

    def _buscar_dados_e_reconstruir_dashboard(self, loja_param, mes_ano_param):
        try:
            dados = self.banco.buscar_dados_dashboard(loja=loja_param, mes_ano=mes_ano_param)
            self.after(0, self._reconstruir_tela_dashboard, dados)
        except Exception as e:
            self.after(0, self._encerrar_tela_de_carregamento)
            self.after(0, lambda: messagebox.showerror("Erro", f"Falha ao carregar dashboard:\n{e}"))

    def _reconstruir_tela_dashboard(self, dados):
        self._encerrar_tela_de_carregamento()
        if "Dashboard" in self.frames:
            plt.close("all")
            self.frames["Dashboard"].destroy()
        self.frames["Dashboard"] = DashboardWindow(
            parent=self.container, controller=self, dados=dados
        )
        self.frames["Dashboard"].grid(row=0, column=0, sticky="nsew")
        self.show_frame("Dashboard")

    # ─────────────────────────────────────────────────────────────────────────
    # CONFIGURAÇÕES
    # ─────────────────────────────────────────────────────────────────────────

    def abrir_tela_configuracoes(self):
        self._ocultar_painel_de_filtros()
        if "Configuracoes" in self.frames:
            self.frames["Configuracoes"].destroy()
        self.frames["Configuracoes"] = ConfiguracoesWindow(
            parent=self.container, controller=self, banco=self.banco
        )
        self.frames["Configuracoes"].grid(row=0, column=0, sticky="nsew")
        self.show_frame("Configuracoes")

    # ─────────────────────────────────────────────────────────────────────────
    # GERENCIAMENTO DE USUÁRIOS (admin only)
    # ─────────────────────────────────────────────────────────────────────────

    def abrir_tela_usuarios(self):
        if not sessao_atual.pode_gerenciar_usuarios:
            messagebox.showerror("Acesso negado", "Sem permissão para acessar esta área.")
            return
        self._ocultar_painel_de_filtros()
        if "Usuarios" in self.frames:
            self.frames["Usuarios"].destroy()
        self.frames["Usuarios"] = TelaUsuarios(
            parent=self.container, controller=self, banco=self.banco
        )
        self.frames["Usuarios"].grid(row=0, column=0, sticky="nsew")
        self.show_frame("Usuarios")

    # ─────────────────────────────────────────────────────────────────────────
    # LOGS DE AUDITORIA (admin only)
    # ─────────────────────────────────────────────────────────────────────────

    def abrir_tela_logs(self):
        if not sessao_atual.pode_ver_logs:
            messagebox.showerror("Acesso negado", "Apenas o Master pode ver os logs de auditoria.")
            return
        self._ocultar_painel_de_filtros()
        if "Logs" in self.frames:
            self.frames["Logs"].destroy()
        self.frames["Logs"] = TelaLogs(
            parent=self.container, controller=self, banco=self.banco
        )
        self.frames["Logs"].grid(row=0, column=0, sticky="nsew")
        self.show_frame("Logs")

    # ─────────────────────────────────────────────────────────────────────────
    # SAIR
    # ─────────────────────────────────────────────────────────────────────────

    def _sair(self):
        self.banco.registrar_log(
            "LOGOUT", "Sessão encerrada pelo usuário",
            id_usuario=sessao_atual.id, email=sessao_atual.nome
        )
        sessao_atual.encerrar()
        self.destroy()
        TelaLogin().mainloop()

    # ─────────────────────────────────────────────────────────────────────────
    # UTILITÁRIOS
    # ─────────────────────────────────────────────────────────────────────────

    def reiniciar(self, event=None):
        import sys
        import subprocess
        self.destroy()
        subprocess.Popen([sys.executable] + sys.argv)

    def _configurar_icone(self):
        try:
            caminho_base = os.path.dirname(os.path.abspath(__file__))
            caminho_ico  = os.path.join(caminho_base, "IMG", "favicon.ico")
            if os.path.exists(caminho_ico):
                self.iconbitmap(caminho_ico)
        except Exception as e:
            print(f"Erro ao configurar ícone: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# TELA DE GERENCIAMENTO DE USUÁRIOS (admin only)
# ─────────────────────────────────────────────────────────────────────────────

class TelaUsuarios(ctk.CTkFrame):
    def __init__(self, parent, controller, banco: BancoDeDados):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.banco      = banco
        self._construir_layout()

    def _construir_layout(self):
        ctk.CTkLabel(self, text="GERENCIAMENTO DE USUÁRIOS",
                     font=("Roboto", 20, "bold")).pack(pady=(15, 5))
        ctk.CTkLabel(self, text="Cadastre operadores e gerencie acessos ao sistema.",
                     font=("Roboto", 11), text_color="#aaa").pack(pady=(0, 15))

        # ── Formulário de cadastro ────────────────────────────────────────────
        frame_form = ctk.CTkFrame(self, border_width=1, border_color="#444")
        frame_form.pack(fill="x", padx=20, pady=(0, 12))

        ctk.CTkLabel(frame_form, text="Novo Usuário", font=("Roboto", 13, "bold")).pack(
            anchor="w", padx=12, pady=(10, 6))

        linha1 = ctk.CTkFrame(frame_form, fg_color="transparent")
        linha1.pack(fill="x", padx=12, pady=(0, 6))

        ctk.CTkLabel(linha1, text="Nome:", width=60, anchor="w").pack(side="left")
        self.entry_nome = ctk.CTkEntry(linha1, placeholder_text="Nome do usuário", width=240)
        self.entry_nome.pack(side="left", padx=(0, 16))

        linha2 = ctk.CTkFrame(frame_form, fg_color="transparent")
        linha2.pack(fill="x", padx=12, pady=(0, 10))

        ctk.CTkLabel(linha2, text="Senha:", width=60, anchor="w").pack(side="left")
        self.entry_senha = ctk.CTkEntry(linha2, placeholder_text="Senha provisória (mín. 5)", show="•", width=200)
        self.entry_senha.pack(side="left", padx=(0, 16))

        ctk.CTkLabel(linha2, text="Perfil:", width=60, anchor="w").pack(side="left")
        self.var_role = ctk.StringVar(value="operador")
        # master pode criar qualquer role; admin só pode criar operador
        roles_disponiveis = ["operador", "admin", "master"] if sessao_atual.eh_master else ["operador"]
        ctk.CTkOptionMenu(linha2, variable=self.var_role,
                          values=roles_disponiveis, width=140).pack(side="left", padx=(0, 16))

        ctk.CTkButton(linha2, text="+ Cadastrar", fg_color="#1a7a1a", hover_color="#145214",
                      command=self._cadastrar).pack(side="left")

        self.lbl_form_msg = ctk.CTkLabel(frame_form, text="", font=("Roboto", 11))
        self.lbl_form_msg.pack(pady=(0, 8))

        # ── Lista de usuários ─────────────────────────────────────────────────
        ctk.CTkLabel(self, text="Usuários cadastrados",
                     font=("Roboto", 13, "bold")).pack(anchor="w", padx=20, pady=(0, 4))

        self.frame_lista = ctk.CTkScrollableFrame(self, fg_color="#1e1e1e", corner_radius=10)
        self.frame_lista.pack(fill="both", expand=True, padx=20, pady=(0, 16))

        self._recarregar_lista()

    def _cadastrar(self):
        nome  = self.entry_nome.get().strip()
        senha = self.entry_senha.get()
        role  = self.var_role.get()

        if not nome or not senha:
            self._msg("Preencha todos os campos.", cor="#ff6b6b")
            return
        if len(senha) < 5:
            self._msg("Senha muito curta (mínimo 5 caracteres).", cor="#ff6b6b")
            return

        try:
            self.banco.cadastrar_usuario(nome, senha, role)
            self.banco.registrar_log(
                "USUARIO_CADASTRADO",
                f"Novo {role} cadastrado: {nome}",
                id_usuario=sessao_atual.id,
                email=sessao_atual.nome
            )
            self._msg(f"✅ Usuário '{nome}' cadastrado com sucesso.", cor="#6bff6b")
            self.entry_nome.delete(0, "end")
            self.entry_senha.delete(0, "end")
            self._recarregar_lista()
        except Exception as e:
            if "UNIQUE" in str(e):
                self._msg("Este nome já está cadastrado.", cor="#ff6b6b")
            else:
                self._msg(f"Erro: {e}", cor="#ff6b6b")

    def _msg(self, texto: str, cor: str = "white"):
        self.lbl_form_msg.configure(text=texto, text_color=cor)

    def _recarregar_lista(self):
        for widget in self.frame_lista.winfo_children():
            widget.destroy()

        # Cabeçalho
        cab = ctk.CTkFrame(self.frame_lista, fg_color="#2a2a2a")
        cab.pack(fill="x", pady=(0, 2))
        for texto, largura in [("Nome", 260), ("Perfil", 100),
                                ("Status", 80), ("Cadastro", 140), ("Ações", 120)]:
            ctk.CTkLabel(cab, text=texto, width=largura,
                         font=("Roboto", 10, "bold"), text_color="#aaa").pack(side="left", padx=4)

        usuarios = self.banco.listar_usuarios(role_solicitante=sessao_atual.role)
        for u in usuarios:
            linha = ctk.CTkFrame(self.frame_lista, fg_color="transparent")
            linha.pack(fill="x", pady=1)

            ctk.CTkLabel(linha, text=u["nome"], width=260, anchor="w").pack(side="left", padx=4)
            ctk.CTkLabel(linha, text=u["role"], width=100, anchor="center").pack(side="left", padx=4)

            status_txt = "Ativo" if u["ativo"] else "Inativo"
            status_cor = "#6bff6b" if u["ativo"] else "#ff6b6b"
            ctk.CTkLabel(linha, text=status_txt, width=80,
                         text_color=status_cor, anchor="center").pack(side="left", padx=4)

            criado = str(u["criado_em"])[:10] if u["criado_em"] else "—"
            ctk.CTkLabel(linha, text=criado, width=140, anchor="center").pack(side="left", padx=4)

            # Botão ativar/desativar (não permite desativar a si próprio)
            if u["id"] != sessao_atual.id:
                texto_btn = "Desativar" if u["ativo"] else "Reativar"
                cor_btn   = "#7a1a1a" if u["ativo"] else "#1a5a1a"
                ctk.CTkButton(
                    linha, text=texto_btn, width=100,
                    fg_color=cor_btn, hover_color="#333",
                    command=lambda uid=u["id"], ativo=u["ativo"], nome=u["nome"]:
                        self._toggle_ativo(uid, ativo, nome)
                ).pack(side="left", padx=4)

    def _toggle_ativo(self, id_usuario: int, ativo_atual: bool, nome: str):
        nova_acao = "desativar" if ativo_atual else "reativar"
        if not messagebox.askyesno("Confirmar", f"Deseja {nova_acao} o usuário {nome}?"):
            return
        self.banco.ativar_desativar_usuario(id_usuario, not ativo_atual)
        self.banco.registrar_log(
            "USUARIO_" + ("DESATIVADO" if ativo_atual else "REATIVADO"),
            f"Usuário {nome} {'desativado' if ativo_atual else 'reativado'}",
            id_usuario=sessao_atual.id,
            email=sessao_atual.nome
        )
        self._recarregar_lista()


# ─────────────────────────────────────────────────────────────────────────────
# TELA DE LOGS DE AUDITORIA (admin only)
# ─────────────────────────────────────────────────────────────────────────────

NOMES_ACOES = {
    "LOGIN":                "Login",
    "LOGIN_FALHOU":         "Tentativa de login falhou",
    "LOGOUT":               "Saiu do sistema",
    "SENHA_ALTERADA":       "Senha alterada",
    "USUARIO_CADASTRADO":   "Usuário cadastrado",
    "USUARIO_DESATIVADO":   "Usuário desativado",
    "USUARIO_REATIVADO":    "Usuário reativado",
    "ANALISE_PONTO":        "Análise de ponto gerada",
    "RELATORIO_FINAL":      "Relatório final gerado",
    "CONFIG_PESOS":         "Configurações de risco alteradas",
    "ABRIU_DASHBOARD":      "Abriu o dashboard",
}

CORES_ACOES = {
    "LOGIN":              "#6bff6b",
    "LOGIN_FALHOU":       "#ff6b6b",
    "LOGOUT":             "#aaa",
    "SENHA_ALTERADA":     "#ffdd6b",
    "USUARIO_CADASTRADO": "#6bb8ff",
    "USUARIO_DESATIVADO": "#ff6b6b",
    "USUARIO_REATIVADO":  "#6bff6b",
    "ANALISE_PONTO":      "#c06bff",
    "RELATORIO_FINAL":    "#6bffdd",
    "CONFIG_PESOS":       "#ffb06b",
    "ABRIU_DASHBOARD":    "#aaa",
}


class TelaLogs(ctk.CTkFrame):
    def __init__(self, parent, controller, banco: BancoDeDados):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.banco      = banco
        self._construir_layout()

    def _construir_layout(self):
        topo = ctk.CTkFrame(self, fg_color="transparent")
        topo.pack(fill="x", padx=20, pady=(15, 0))

        ctk.CTkLabel(topo, text="LOGS DE AUDITORIA",
                     font=("Roboto", 20, "bold")).pack(side="left")
        ctk.CTkButton(topo, text="↻ Atualizar", width=110,
                      fg_color="#3a3a3a", hover_color="#2a2a2a",
                      command=self._recarregar).pack(side="right")

        ctk.CTkLabel(self, text="Registro de todas as ações realizadas no sistema.",
                     font=("Roboto", 11), text_color="#aaa").pack(anchor="w", padx=20, pady=(4, 12))

        # ── Filtros ───────────────────────────────────────────────────────────
        frame_filtros = ctk.CTkFrame(self, fg_color="#1e1e1e", corner_radius=8)
        frame_filtros.pack(fill="x", padx=20, pady=(0, 10))

        linha = ctk.CTkFrame(frame_filtros, fg_color="transparent")
        linha.pack(fill="x", padx=12, pady=10)

        ctk.CTkLabel(linha, text="Filtrar por e-mail:", anchor="w").pack(side="left")
        self.entry_filtro_email = ctk.CTkEntry(linha, placeholder_text="usuario@email.com", width=240)
        self.entry_filtro_email.pack(side="left", padx=(8, 20))

        ctk.CTkLabel(linha, text="Ação:", anchor="w").pack(side="left")
        self.var_filtro_acao = ctk.StringVar(value="Todas")
        opcoes = ["Todas"] + list(NOMES_ACOES.keys())
        ctk.CTkOptionMenu(linha, variable=self.var_filtro_acao,
                          values=opcoes, width=200).pack(side="left", padx=(8, 20))

        ctk.CTkButton(linha, text="Filtrar", width=90,
                      fg_color="#8A2BE2", hover_color="#4B0082",
                      command=self._recarregar).pack(side="left")

        # ── Tabela de logs ────────────────────────────────────────────────────
        self.frame_lista = ctk.CTkScrollableFrame(self, fg_color="#1e1e1e", corner_radius=10)
        self.frame_lista.pack(fill="both", expand=True, padx=20, pady=(0, 16))

        self._recarregar()

    def _recarregar(self):
        for widget in self.frame_lista.winfo_children():
            widget.destroy()

        filtro_email = self.entry_filtro_email.get().strip() or None
        filtro_acao  = self.var_filtro_acao.get()
        filtro_acao  = None if filtro_acao == "Todas" else filtro_acao

        logs = self.banco.buscar_logs(limite=300, filtro_acao=filtro_acao,
                                      filtro_email=filtro_email)

        # Cabeçalho
        cab = ctk.CTkFrame(self.frame_lista, fg_color="#2a2a2a")
        cab.pack(fill="x", pady=(0, 4))
        for texto, largura in [("Data/Hora", 160), ("Usuário", 200),
                                ("Ação", 200), ("Detalhe", 260), ("Máquina", 120)]:
            ctk.CTkLabel(cab, text=texto, width=largura,
                         font=("Roboto", 10, "bold"), text_color="#aaa").pack(side="left", padx=4)

        if not logs:
            ctk.CTkLabel(self.frame_lista, text="Nenhum log encontrado.",
                         text_color="#aaa").pack(pady=20)
            return

        for log in logs:
            linha = ctk.CTkFrame(self.frame_lista, fg_color="transparent")
            linha.pack(fill="x", pady=1)

            # Formata timestamp
            ts = str(log["timestamp"])[:19].replace("T", " ")

            acao_key  = log["acao"]
            acao_nome = NOMES_ACOES.get(acao_key, acao_key)
            acao_cor  = CORES_ACOES.get(acao_key, "white")

            ctk.CTkLabel(linha, text=ts,            width=160, anchor="w",
                         font=("Roboto", 10), text_color="#aaa").pack(side="left", padx=4)
            ctk.CTkLabel(linha, text=log["email"],  width=200, anchor="w",
                         font=("Roboto", 10)).pack(side="left", padx=4)
            ctk.CTkLabel(linha, text=acao_nome,     width=200, anchor="w",
                         font=("Roboto", 10, "bold"), text_color=acao_cor).pack(side="left", padx=4)
            ctk.CTkLabel(linha, text=log["detalhe"][:60], width=260, anchor="w",
                         font=("Roboto", 10), text_color="#ccc").pack(side="left", padx=4)
            ctk.CTkLabel(linha, text=log["maquina"], width=120, anchor="w",
                         font=("Roboto", 10), text_color="#888").pack(side="left", padx=4)


# ─────────────────────────────────────────────────────────────────────────────
# HOME FRAME
# ─────────────────────────────────────────────────────────────────────────────

class HomeFrame(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller          = controller
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
        self.entry_fim    = ctk.CTkEntry(subframe, placeholder_text="DD/MM/AAAA", width=120)
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
        banco = self.controller.banco
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

            banco.registrar_log(
                "ANALISE_PONTO",
                f"Planilha de revisão gerada: {len(resultados)} jornadas | arquivo: {os.path.basename(self.arquivo_selecionado)}",
                id_usuario=sessao_atual.id,
                email=sessao_atual.nome
            )

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
        banco = self.controller.banco
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
            banco.salvar_jornadas(resultados)

            self.log("Gerando relatório final...")
            ExcelReporter().gerar_relatorio_excel(resultados, "Relatorio_Final.xlsx")

            banco.registrar_log(
                "RELATORIO_FINAL",
                f"Relatório final gerado e salvo: {len(resultados)} jornadas",
                id_usuario=sessao_atual.id,
                email=sessao_atual.nome
            )

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
    from src.interface import TelaLogin
    TelaLogin().mainloop()