"""Agregacao da nota e regra do gate PASS/FAIL."""

from .checks import CRITICAL, FAIL, CheckResult


def total_score(results: list[CheckResult]) -> int:
    return round(sum(r.score for r in results))


def passed(results: list[CheckResult], score: int, min_score: int) -> bool:
    """PASS se a nota atinge o minimo e nenhum check critico falhou."""
    if score < min_score:
        return False
    return not any(r.status == FAIL and r.label in CRITICAL for r in results)
