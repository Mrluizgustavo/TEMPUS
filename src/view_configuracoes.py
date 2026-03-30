import customtkinter as ctk
from tkinter import messagebox


# Descrições amigáveis para exibição na tela
DESCRICOES_PESO = {
    "INTERVALO_CURTO":         ("Intervalo curto",         "Intervalo entre batidas menor que 50 min"),
    "INTERVALO_LONGO":         ("Intervalo longo",         "Intervalo entre batidas maior que 70 min"),
    "JORNADA_SEM_INTERVALO":   ("Jornada sem intervalo",   "2 batidas com mais de 6h trabalhadas"),
    "INTERJORNADA_IRREGULAR":  ("Interjornada irregular",  "Menos de 11h de descanso entre jornadas"),
    "JORNADA_IRREGULAR_MENOR": ("Menor após 22h",          "Funcionário menor de 18 anos em horário noturno"),
    "JORNADA_LONGA_10":        ("Jornada +10h",            "Jornada entre 10h e 12h trabalhadas"),
    "JORNADA_LONGA_12":        ("Jornada +12h",            "Jornada acima de 12h trabalhadas"),
}


class ConfiguracoesWindow(ctk.CTkFrame):

    def __init__(self, parent, controller, banco):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.banco      = banco
        self._entradas: dict[str, ctk.CTkEntry] = {}
        self._construir_layout()

    # ─────────────────────────────────────────────────────────────────────────
    # LAYOUT
    # ─────────────────────────────────────────────────────────────────────────

    def _construir_layout(self):
        ctk.CTkLabel(
            self, text="CONFIGURAÇÕES DE RISCO",
            font=("Roboto", 20, "bold")
        ).pack(pady=(15, 5))

        ctk.CTkLabel(
            self,
            text="Ajuste os pesos utilizados no cálculo do Score de Risco Trabalhista.",
            font=("Roboto", 11), text_color="#aaa"
        ).pack(pady=(0, 15))

        # ── Tabela de pesos ───────────────────────────────────────────────────
        container = ctk.CTkScrollableFrame(self, fg_color="#1e1e1e", corner_radius=12)
        container.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        # Cabeçalho
        cabecalhos = ["Irregularidade", "Descrição", "Peso atual", "Novo peso"]
        larguras   = [3, 5, 1, 1]
        for ci, (cab, w) in enumerate(zip(cabecalhos, larguras)):
            container.grid_columnconfigure(ci, weight=w)
            ctk.CTkLabel(
                container, text=cab,
                font=("Roboto", 10, "bold"), text_color="#aaa",
                fg_color="#2a2a2a", corner_radius=4
            ).grid(row=0, column=ci, padx=4, pady=(6, 2), sticky="ew")

        # Lê pesos atuais do banco
        pesos_atuais = self.banco.buscar_pesos_risco()

        for li, (chave, (nome, descricao)) in enumerate(DESCRICOES_PESO.items(), start=1):
            peso_atual = pesos_atuais.get(chave, "—")
            bg = "#2e2e2e" if li % 2 == 0 else "transparent"

            ctk.CTkLabel(
                container, text=nome,
                font=("Roboto", 11, "bold"), fg_color=bg,
                corner_radius=0, anchor="w"
            ).grid(row=li, column=0, padx=8, pady=4, sticky="ew")

            ctk.CTkLabel(
                container, text=descricao,
                font=("Roboto", 10), text_color="#aaa", fg_color=bg,
                corner_radius=0, anchor="w"
            ).grid(row=li, column=1, padx=8, pady=4, sticky="ew")

            ctk.CTkLabel(
                container, text=str(peso_atual),
                font=("Roboto", 11), fg_color=bg,
                corner_radius=0, anchor="center"
            ).grid(row=li, column=2, padx=8, pady=4, sticky="ew")

            entrada = ctk.CTkEntry(
                container, width=70,
                placeholder_text=str(peso_atual),
                justify="center"
            )
            entrada.grid(row=li, column=3, padx=8, pady=4)
            self._entradas[chave] = entrada

        # ── Botões ────────────────────────────────────────────────────────────
        rodape = ctk.CTkFrame(self, fg_color="transparent")
        rodape.pack(fill="x", padx=20, pady=(5, 15))

        ctk.CTkButton(
            rodape, text="Restaurar Padrões",
            fg_color="#555", hover_color="#444",
            command=self._restaurar_padroes
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            rodape, text="Salvar Configurações",
            fg_color="#1a7a1a", hover_color="#145214",
            command=self._salvar
        ).pack(side="right")

    # ─────────────────────────────────────────────────────────────────────────
    # AÇÕES
    # ─────────────────────────────────────────────────────────────────────────

    def _salvar(self):
        novos_pesos = {}
        erros       = []

        for chave, entrada in self._entradas.items():
            valor_txt = entrada.get().strip()
            if not valor_txt:
                continue  # campo vazio = não alterar

            try:
                valor = int(valor_txt)
                if valor < 0:
                    raise ValueError
                novos_pesos[chave] = valor
            except ValueError:
                nome = DESCRICOES_PESO[chave][0]
                erros.append(f"• {nome}: '{valor_txt}' não é um número inteiro válido (mínimo 0)")

        if erros:
            messagebox.showerror(
                "Valores inválidos",
                "Corrija os seguintes campos antes de salvar:\n\n" + "\n".join(erros)
            )
            return

        if not novos_pesos:
            messagebox.showinfo("Nada alterado", "Nenhum valor foi modificado.")
            return

        self.banco.salvar_pesos_risco(novos_pesos)

        messagebox.showinfo(
            "Salvo",
            f"{len(novos_pesos)} peso(s) atualizado(s) com sucesso.\n"
            "O dashboard usará os novos valores na próxima atualização."
        )

        # Recarrega a tela para mostrar os novos valores na coluna "Peso atual"
        self._reconstruir()

    def _restaurar_padroes(self):
        confirmar = messagebox.askyesno(
            "Restaurar padrões",
            "Deseja restaurar todos os pesos para os valores padrão do sistema?"
        )
        if not confirmar:
            return

        self.banco.restaurar_pesos_padrao()
        messagebox.showinfo("Restaurado", "Pesos restaurados para os valores padrão.")
        self._reconstruir()

    def _reconstruir(self):
        """Destroi e recria a tela para refletir os novos pesos salvos."""
        for widget in self.winfo_children():
            widget.destroy()
        self._entradas.clear()
        self._construir_layout()