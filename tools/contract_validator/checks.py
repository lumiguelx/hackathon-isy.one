"""Checks de qualidade do contrato OpenAPI.

Cada check recebe o dict do spec e devolve um CheckResult com label, status
(pass|warn|fail), mensagem e a pontuacao obtida (0..weight). Os pesos somam 100.
"""

import re
from dataclasses import dataclass

PASS = "pass"
WARN = "warn"
FAIL = "fail"

_HTTP_METHODS = ("get", "put", "post", "delete", "patch", "options", "head", "trace")

# Versionamento semantico (https://semver.org), com prefixo "v" opcional.
_SEMVER = re.compile(
    r"^v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)


@dataclass
class CheckResult:
    label: str
    status: str
    message: str
    score: float
    weight: float


def _operations(spec: dict) -> list[tuple[str, str, dict]]:
    """Lista (path, metodo, operacao) de todas as rotas do spec."""
    ops: list[tuple[str, str, dict]] = []
    for path, item in (spec.get("paths") or {}).items():
        if not isinstance(item, dict):
            continue
        for method, op in item.items():
            if method.lower() in _HTTP_METHODS and isinstance(op, dict):
                ops.append((path, method.lower(), op))
    return ops


def check_routes(spec: dict, weight: float = 20.0) -> CheckResult:
    """Rotas documentadas: operacao com summary ou description."""
    ops = _operations(spec)
    total = len(ops)
    documented = sum(1 for _, _, op in ops if op.get("summary") or op.get("description"))
    status = PASS if documented == total and total else (FAIL if total == 0 else WARN)
    msg = (
        "nenhuma rota no spec" if total == 0 else f"{documented}/{total} rotas documentadas"
    )
    score = weight * (documented / total) if total else 0.0
    return CheckResult("routes", status, msg, score, weight)


def check_auth(spec: dict, weight: float = 20.0) -> CheckResult:
    """Scheme de auth declarado em components.securitySchemes e referenciado."""
    schemes = (spec.get("components") or {}).get("securitySchemes") or {}
    global_security = spec.get("security")
    op_security = any(op.get("security") for _, _, op in _operations(spec))
    if schemes and (global_security or op_security):
        nomes = ", ".join(schemes.keys())
        tipos = {s.get("type") for s in schemes.values() if isinstance(s, dict)}
        return CheckResult(
            "auth", PASS, f"scheme de auth definido ({nomes}: {', '.join(sorted(tipos))})", weight, weight
        )
    if schemes:
        return CheckResult(
            "auth", WARN, "securityScheme declarado mas nenhuma rota o referencia", weight * 0.5, weight
        )
    return CheckResult(
        "auth", FAIL, "nenhum securityScheme declarado no spec", 0.0, weight
    )


def check_responses(spec: dict, weight: float = 20.0) -> CheckResult:
    """Toda operacao deve declarar >=1 resposta 2xx e cobertura de erro (4xx/5xx)."""
    ops = _operations(spec)
    total = len(ops)
    if total == 0:
        return CheckResult("responses", FAIL, "nenhuma operacao no spec", 0.0, weight)

    conformes = 0
    sem_erro = 0
    for _, _, op in ops:
        codes = [str(c) for c in (op.get("responses") or {})]
        tem_2xx = any(c.startswith("2") for c in codes)
        tem_erro = any(c[:1] in ("4", "5") for c in codes)
        if tem_2xx and tem_erro:
            conformes += 1
        elif tem_2xx:
            conformes += 0.5
            sem_erro += 1

    score = weight * (conformes / total)
    if conformes == total:
        status, msg = PASS, "todos os codigos 2xx/4xx/5xx"
    elif sem_erro:
        status, msg = WARN, f"{sem_erro} rota(s) sem resposta de erro declarada"
    else:
        status, msg = FAIL, "ha operacao sem resposta 2xx declarada"
    return CheckResult("responses", status, msg, score, weight)


def check_semver(spec: dict, weight: float = 15.0) -> CheckResult:
    """info.version deve ser um semver valido."""
    version = (spec.get("info") or {}).get("version", "")
    if version and _SEMVER.match(version):
        return CheckResult("semver", PASS, f"v{version.lstrip('v')} (semver valido)", weight, weight)
    return CheckResult(
        "semver", FAIL, f"version '{version or '(vazio)'}' nao e semver valido", 0.0, weight
    )


def check_descriptions(spec: dict, weight: float = 15.0) -> CheckResult:
    """Operacoes sem description (warning, nao zera o gate)."""
    ops = _operations(spec)
    total = len(ops)
    com_desc = sum(1 for _, _, op in ops if (op.get("description") or "").strip())
    faltando = total - com_desc
    score = weight * (com_desc / total) if total else 0.0
    if faltando == 0 and total:
        return CheckResult("descriptions", PASS, "todas as rotas com description", score, weight)
    return CheckResult(
        "descriptions", WARN, f"{faltando} rota(s) sem description", score, weight
    )


def check_deprecations(spec: dict, weight: float = 10.0) -> CheckResult:
    """Rotas marcadas como deprecated (informativo)."""
    deprecadas = [
        f"{method.upper()} {path}"
        for path, method, op in _operations(spec)
        if op.get("deprecated")
    ]
    if not deprecadas:
        return CheckResult("deprecations", PASS, "nenhuma rota depreciada", weight, weight)
    return CheckResult(
        "deprecations", WARN, f"{len(deprecadas)} rota(s) depreciada(s): {', '.join(deprecadas)}", weight, weight
    )


# Checks na ordem de exibicao. Checks "criticos" reprovam o gate se status==FAIL.
ALL_CHECKS = (check_routes, check_auth, check_responses, check_semver, check_descriptions, check_deprecations)
CRITICAL = {"auth", "semver"}


def run_all(spec: dict) -> list[CheckResult]:
    return [check(spec) for check in ALL_CHECKS]
