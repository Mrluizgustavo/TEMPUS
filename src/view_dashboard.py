import customtkinter as ctk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt


class DashboardWindow(ctk.CTkToplevel):
    def __init__(self, dados_kpi):
        super().__init__()

        self.title("Dashboard de Gestão - Modo Fullscreen")

        # 1. COMANDO PARA MAXIMIZAR A TELA (Windows)
        try:
            self.state("zoomed")
        except:
            # Fallback para Linux/Mac se necessário
            self.attributes("-fullscreen", True)

        self.dados = dados_kpi

        # Cores e Estilo
        self.cor_fundo = '#2b2b2b'
        plt.rcParams['text.color'] = 'white'
        plt.rcParams['axes.labelcolor'] = 'white'
        plt.rcParams['xtick.color'] = 'white'
        plt.rcParams['ytick.color'] = 'white'

        self._criar_layout()

    def _criar_layout(self):
        # --- LINHA 0: Título e KPIs ---
        frame_topo = ctk.CTkFrame(self, fg_color="transparent")
        frame_topo.pack(fill="x", padx=20, pady=(20, 10))

        lbl = ctk.CTkLabel(frame_topo, text="DASHBOARD DE GESTÃO DE PONTO", font=("Roboto", 24, "bold"))
        lbl.pack(anchor="w")

        # KPIs (Cards)
        frame_kpi = ctk.CTkFrame(frame_topo, fg_color="transparent")
        frame_kpi.pack(fill="x", pady=10)

        total = self.dados.get("total", 0)
        ok = self.dados["status_pie"].get("OK", 0)
        erros = self.dados["status_pie"].get("Irregular", 0)
        eficiencia = (ok / total * 100) if total > 0 else 0

        self._criar_cartao(frame_kpi, "Total Processado", total, "#FFFFFF")
        self._criar_cartao(frame_kpi, "Jornadas OK", ok, "#00E676")
        self._criar_cartao(frame_kpi, "Irregularidades", erros, "#FF1744")
        self._criar_cartao(frame_kpi, "Eficiência Global", f"{eficiencia:.1f}%", "#2979FF")

        # --- LINHA 1: DASHBOARD PRINCIPAL (Rosca) ---
        # Frame container com peso para expandir
        frame_linha1 = ctk.CTkFrame(self)
        frame_linha1.pack(fill="both", expand=True, padx=20, pady=5)

        # Título da Seção
        ctk.CTkLabel(frame_linha1, text="VISÃO GERAL DA EMPRESA",
                     font=("Roboto", 16, "bold"), text_color="#AAAAAA").pack(pady=5)

        # Área do Gráfico
        area_rosca = ctk.CTkFrame(frame_linha1, fg_color="transparent")
        area_rosca.pack(fill="both", expand=True)
        self._plotar_rosca(area_rosca)

        # --- LINHA 2: CASOS DE ATENÇÃO (Barras) ---
        frame_linha2 = ctk.CTkFrame(self)
        frame_linha2.pack(fill="both", expand=True, padx=20, pady=(5, 20))

        ctk.CTkLabel(frame_linha2, text="RANKING DE ATENÇÃO (TOP 5)",
                     font=("Roboto", 16, "bold"), text_color="#FF5555").pack(pady=5)

        area_barras = ctk.CTkFrame(frame_linha2, fg_color="transparent")
        area_barras.pack(fill="both", expand=True)
        self._plotar_barras_horizontal_full(area_barras)

    def _criar_cartao(self, parent, titulo, valor, cor):
        # Cartões menores para caber melhor na tela cheia
        card = ctk.CTkFrame(parent, fg_color="#333333")
        card.pack(side="left", expand=True, fill="x", padx=5)

        ctk.CTkLabel(card, text=titulo, font=("Arial", 12, "bold"), text_color="#AAAAAA").pack(pady=(10, 0))
        ctk.CTkLabel(card, text=str(valor), font=("Arial", 26, "bold"), text_color=cor).pack(pady=(0, 10))

    def _plotar_rosca(self, parent):
        fig = Figure(figsize=(8, 3), dpi=100, facecolor=self.cor_fundo)
        ax = fig.add_subplot(111)

        dados = self.dados["status_pie"]
        labels = list(dados.keys())
        valores = list(dados.values())

        # Calculamos o total para poder gerar a porcentagem na legenda
        total = sum(valores)

        # Cores (Verde/Vermelho)
        cores = ['#00E676', '#FF1744'] if "OK" in labels[0] else ['#FF1744', '#00E676']

        # --- MUDANÇA 1: LEGENDA COM PORCENTAGEM ---
        # Em vez de mostrar o valor (Ex: 150), mostramos a % (Ex: 15.5%)
        labels_legenda = []
        for label, valor in zip(labels, valores):
            pct = (valor / total * 100) if total > 0 else 0
            labels_legenda.append(f"{label}: {pct:.1f}%")

        # --- MUDANÇA 2: GRÁFICO LIMPO ---
        # autopct=None: Remove os números de dentro do gráfico
        # labels=None: Remove os textos em volta
        wedges, texts = ax.pie(valores, labels=None, autopct=None,
                               startangle=90, colors=cores,
                               wedgeprops=dict(width=0.4, edgecolor=self.cor_fundo))

        # Cria a Legenda Lateral
        ax.legend(wedges, labels_legenda,
                  title="Distribuição",
                  title_fontsize=10,
                  loc="center left",
                  bbox_to_anchor=(1, 0, 0.5, 1),
                  frameon=False,
                  labelcolor="white")

        # Círculo central (Buraco da Rosca)
        centre_circle = plt.Circle((0, 0), 0.70, fc=self.cor_fundo)
        fig.gca().add_artist(centre_circle)

        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    def _plotar_barras_horizontal_full(self, parent):
        # Aumentei um pouco a largura base da figura
        fig = Figure(figsize=(10, 4), dpi=100, facecolor=self.cor_fundo)
        ax = fig.add_subplot(111)
        ax.set_facecolor(self.cor_fundo)

        dados = self.dados["top_5_erros"]
        nomes = list(dados.keys())
        qtds = list(dados.values())

        if not nomes:
            ax.text(0.5, 0.5, "Nenhuma irregularidade encontrada! 🎉",
                    ha='center', va='center', color='white', fontsize=14)
        else:
            y_pos = range(len(nomes))

            # Escala Dinâmica (igual antes)
            max_valor = max(qtds) if qtds else 1
            ax.set_xlim(0, max_valor * 1.15)

            # Barras
            rects = ax.barh(y_pos, qtds, color='#FF1744', height=0.5)

            # Configuração dos Nomes
            ax.set_yticks(y_pos)
            ax.set_yticklabels(nomes, color="white", fontsize=11, fontweight="bold")
            ax.invert_yaxis()

            # Limpeza Visual
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['bottom'].set_visible(False)
            ax.spines['left'].set_visible(False)
            ax.tick_params(axis='x', length=0, labelsize=0)
            ax.tick_params(axis='y', length=0)

            # Valores nas pontas
            for i, v in enumerate(qtds):
                offset = max_valor * 0.01
                ax.text(v + offset, i, str(v), color='white', va='center', fontweight='bold', fontsize=12)

        # --- A GRANDE MUDANÇA AQUI ---
        # Em vez de tight_layout(), ajustamos as margens manualmente.
        # left=0.30: Deixa 30% da tela na esquerda para os nomes (aumente se cortar)
        # right=0.95: O gráfico vai até 95% da tela na direita
        # top/bottom: Ajustam as margens verticais
        fig.subplots_adjust(left=0.30, right=0.95, top=0.9, bottom=0.1)

        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        # O pack com expand=True garante que o canvas estique para ocupar o espaço
        canvas.get_tk_widget().pack(fill="both", expand=True)