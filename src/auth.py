import bcrypt
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class UsuarioLogado:
    id: int
    nome: str
    email: str
    role: str  # 'master', 'admin' ou 'operador'


@dataclass
class Sessao:
    """Singleton simples de sessão em memória."""
    id: int = None
    nome: str = ""
    email: str = ""
    role: str = ""
    ativo: bool = False

    def logar(self, dados: dict):
        self.id    = dados["id"]
        self.nome  = dados["nome"]
        self.email = dados["email"]
        self.role  = dados["role"]
        self.ativo = True

    def encerrar(self):
        self.__init__()

    # ── Permissões ────────────────────────────────────────────────────────────

    @property
    def eh_master(self) -> bool:
        return self.role == "master"

    @property
    def eh_admin(self) -> bool:
        """master também herda todos os privilégios de admin."""
        return self.role in ("master", "admin")

    @property
    def pode_processar_ponto(self) -> bool:
        return self.role in ("master", "admin", "operador")

    @property
    def pode_ver_dashboard(self) -> bool:
        return self.role in ("master", "admin", "operador")

    @property
    def pode_configuracoes(self) -> bool:
        return self.role in ("master", "admin")

    @property
    def pode_gerenciar_usuarios(self) -> bool:
        return self.role in ("master", "admin")

    @property
    def pode_ver_logs(self) -> bool:
        """Logs de auditoria: somente master."""
        return self.role == "master"


# Instância única compartilhada por todo o app
sessao_atual = Sessao()