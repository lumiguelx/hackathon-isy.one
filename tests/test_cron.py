"""Testa o avaliador de cron (app.services.cron)."""

from datetime import datetime, timezone

import pytest

from app.services import cron


def _dt(ano, mes, dia, hora, minuto):
    return datetime(ano, mes, dia, hora, minuto, tzinfo=timezone.utc)


def test_validate_aceita_presets():
    for expr in ("* * * * *", "0 * * * *", "30 3 * * *", "0 18 * * 5", "*/15 * * * *"):
        cron.validate(expr)


@pytest.mark.parametrize(
    "expr",
    [
        "* * * *",  # campos de menos
        "* * * * * *",  # campos de mais
        "60 * * * *",  # minuto fora da faixa
        "* 24 * * *",  # hora fora da faixa
        "* * * * 7",  # diasem fora da faixa (0-6)
        "*/0 * * * *",  # passo invalido
        "5-2 * * * *",  # intervalo invertido
        "abc * * * *",  # token invalido
    ],
)
def test_validate_rejeita_invalidos(expr):
    with pytest.raises(ValueError):
        cron.validate(expr)


def test_matches_a_cada_minuto():
    assert cron.matches("* * * * *", _dt(2026, 6, 3, 14, 7))


def test_matches_horario_diario():
    expr = "30 3 * * *"  # 03:30 todo dia
    assert cron.matches(expr, _dt(2026, 6, 3, 3, 30))
    assert not cron.matches(expr, _dt(2026, 6, 3, 3, 31))
    assert not cron.matches(expr, _dt(2026, 6, 3, 4, 30))


def test_matches_a_cada_hora():
    expr = "0 * * * *"
    assert cron.matches(expr, _dt(2026, 6, 3, 9, 0))
    assert not cron.matches(expr, _dt(2026, 6, 3, 9, 1))


def test_matches_passo():
    expr = "*/15 * * * *"  # 0,15,30,45
    assert cron.matches(expr, _dt(2026, 6, 3, 9, 0))
    assert cron.matches(expr, _dt(2026, 6, 3, 9, 45))
    assert not cron.matches(expr, _dt(2026, 6, 3, 9, 10))


def test_matches_dia_da_semana_domingo_e_zero():
    # 2026-06-07 e um domingo -> cron dow 0.
    expr = "0 12 * * 0"
    assert cron.matches(expr, _dt(2026, 6, 7, 12, 0))  # domingo
    assert not cron.matches(expr, _dt(2026, 6, 8, 12, 0))  # segunda


def test_matches_sexta_feira():
    # 2026-06-05 e uma sexta -> cron dow 5.
    expr = "0 18 * * 5"
    assert cron.matches(expr, _dt(2026, 6, 5, 18, 0))  # sexta
    assert not cron.matches(expr, _dt(2026, 6, 4, 18, 0))  # quinta


def test_next_run_a_cada_minuto():
    assert cron.next_run("* * * * *", _dt(2026, 6, 3, 14, 30)) == _dt(2026, 6, 3, 14, 31)


def test_next_run_diario():
    # as 03:30; agora 14:00 -> proxima e amanha 03:30.
    assert cron.next_run("30 3 * * *", _dt(2026, 6, 3, 14, 0)) == _dt(2026, 6, 4, 3, 30)


def test_next_run_a_cada_hora():
    assert cron.next_run("0 * * * *", _dt(2026, 6, 3, 14, 30)) == _dt(2026, 6, 3, 15, 0)
