"""Avaliador de cron de 5 campos (min hora dia mes diasem), sem dependencia externa.

Suporta por campo: '*', inteiro, lista 'a,b', intervalo 'a-b' e passo '*/n' ou 'a-b/n'.
Dia-da-semana segue o padrao cron: 0=domingo .. 6=sabado.

Semantica de dia: dia-do-mes e dia-da-semana sao combinados com AND (nao com o OR
classico do cron). Os presets da UI restringem no maximo um dos dois, entao o AND e
suficiente e mais previsivel.
"""

from datetime import datetime

# Faixa valida (lo, hi) de cada campo, na ordem do cron.
_RANGES = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 6)]


def _parse_field(field: str, lo: int, hi: int) -> set[int]:
    valores: set[int] = set()
    for parte in field.split(","):
        parte = parte.strip()
        if not parte:
            raise ValueError("campo cron vazio")
        passo = 1
        if "/" in parte:
            base, _, p = parte.partition("/")
            if not p.isdigit() or int(p) < 1:
                raise ValueError(f"passo invalido em '{parte}'")
            passo = int(p)
            parte = base
        if parte == "*":
            inicio, fim = lo, hi
        elif "-" in parte:
            a, _, b = parte.partition("-")
            if not (a.isdigit() and b.isdigit()):
                raise ValueError(f"intervalo invalido em '{parte}'")
            inicio, fim = int(a), int(b)
        elif parte.isdigit():
            inicio = fim = int(parte)
        else:
            raise ValueError(f"valor invalido em '{parte}'")
        if inicio < lo or fim > hi or inicio > fim:
            raise ValueError(f"fora do intervalo [{lo},{hi}] em '{parte}'")
        valores.update(range(inicio, fim + 1, passo))
    return valores


def _campos(expr: str) -> list[set[int]]:
    partes = expr.split()
    if len(partes) != 5:
        raise ValueError("cron deve ter 5 campos: min hora dia mes diasem")
    return [_parse_field(p, lo, hi) for p, (lo, hi) in zip(partes, _RANGES)]


def validate(expr: str) -> None:
    """Levanta ValueError se a expressao nao for um cron de 5 campos valido."""
    _campos(expr)


def matches(expr: str, dt: datetime) -> bool:
    """True se o cron casa o minuto de dt (diasem cron: 0=domingo)."""
    minuto, hora, dia, mes, diasem = _campos(expr)
    cron_dow = dt.isoweekday() % 7  # isoweekday seg=1..dom=7 -> dom=0..sab=6
    return (
        dt.minute in minuto
        and dt.hour in hora
        and dt.day in dia
        and dt.month in mes
        and cron_dow in diasem
    )
