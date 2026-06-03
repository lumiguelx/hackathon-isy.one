"""Renderizacao do relatorio do validador (tabela colorida + nota + PASS/FAIL)."""

from .checks import FAIL, PASS, WARN, CheckResult

_GLYPH = {PASS: "✓", WARN: "⚠", FAIL: "✗"}
_COLOR = {PASS: "\033[32m", WARN: "\033[33m", FAIL: "\033[31m"}
_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"


def _paint(text: str, code: str, color: bool) -> str:
    return f"{code}{text}{_RESET}" if color else text


def render(results: list[CheckResult], score: int, passed: bool, color: bool = True) -> str:
    lines = ["Validating OpenAPI contract...", ""]
    label_w = max((len(f"[{r.label}]") for r in results), default=0)
    for r in results:
        label = f"[{r.label}]".ljust(label_w)
        glyph = _paint(_GLYPH[r.status], _COLOR[r.status], color)
        msg = _paint(r.message, _COLOR[r.status], color)
        lines.append(f"{label}  {glyph}  {msg}")

    lines.append("")
    lines.append(_paint("-" * (label_w + 24), _DIM, color))
    verdict = "PASS " + _GLYPH[PASS] if passed else "FAIL " + _GLYPH[FAIL]
    verdict = _paint(verdict, _BOLD + (_COLOR[PASS] if passed else _COLOR[FAIL]), color)
    lines.append(f"{_paint('Score: ' + str(score) + '/100', _BOLD, color)}   →   {verdict}")
    return "\n".join(lines)
