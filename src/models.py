from dataclasses import dataclass

@dataclass
class JornadaInconsistente:
    """
    Representa um dia onde as batidas não fecharam par (entrada/saída).
    Ex: Só bateu entrada e esqueceu a saída.
    """
    nome_colaborador: str
    data_referencia: str
    batidas_registradas: list[str]
