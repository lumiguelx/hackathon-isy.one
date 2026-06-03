"""Validacao do schema de parametros e montagem segura da invocacao do script.

Cada parametro estruturado (ver schemas.ParamSpec) vira parte do argv ou do env
da execucao. Como o valor pode acabar dentro de um comando remoto via _ssh.sh, o
backend valida tipo/faixa/choices e proibe metacaracteres de shell ANTES de chegar
no SSH (defense-in-depth; os scripts continuam validando por conta tambem).
"""

import re

from app.models import Script

# Charset seguro para valores 'text': sem ; | & $ ` ( ) < > etc. (anti command injection).
_TEXT_SEGURO = re.compile(r"^[A-Za-z0-9._@/:= -]*$")
_INT_RE = re.compile(r"^-?\d+$")
_ARG_RE = re.compile(r"^-{0,2}[A-Za-z0-9][A-Za-z0-9-]*$")
_ENV_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
_TIPOS = {"int", "text", "select", "bool"}
_BOOL_TRUE = {"true", "1", "yes", "on"}
_BOOL_FALSE = {"false", "0", "no", "off", ""}


class ParamError(ValueError):
    """Schema de parametros invalido ou valor fora das regras."""


def _as_dicts(param_schema) -> list[dict]:
    out = []
    for p in param_schema or []:
        out.append(p if isinstance(p, dict) else p.model_dump())
    return out


def validate_schema(param_schema) -> None:
    """Valida a coerencia do schema (sem valores). Levanta ParamError."""
    vistos: set[str] = set()
    for p in _as_dicts(param_schema):
        nome = p.get("nome", "")
        if not nome:
            raise ParamError("Parametro sem nome.")
        if nome in vistos:
            raise ParamError(f"Parametro duplicado: '{nome}'.")
        vistos.add(nome)
        if p.get("tipo") not in _TIPOS:
            raise ParamError(f"Tipo invalido em '{nome}': {p.get('tipo')!r}.")
        if p.get("tipo") == "select" and not p.get("choices"):
            raise ParamError(f"Parametro select '{nome}' sem choices.")
        mn, mx = p.get("minimo"), p.get("maximo")
        if mn is not None and mx is not None and mn > mx:
            raise ParamError(f"min > max em '{nome}'.")
        if p.get("arg") and not _ARG_RE.match(p["arg"]):
            raise ParamError(f"Arg invalido em '{nome}': {p['arg']!r}.")
        if p.get("env") and not _ENV_RE.match(p["env"]):
            raise ParamError(f"Env var invalida em '{nome}': {p['env']!r}.")


def _valor_resolvido(p: dict, valores: dict) -> str:
    if p.get("constante"):
        return str(p["constante"])
    if p["nome"] in valores and valores[p["nome"]] is not None:
        return str(valores[p["nome"]])
    return str(p.get("default", ""))


def _validar_valor(p: dict, valor: str) -> str:
    tipo = p.get("tipo", "text")
    nome = p["nome"]
    if tipo == "bool":
        v = valor.strip().lower()
        if v in _BOOL_TRUE:
            return "true"
        if v in _BOOL_FALSE:
            return "false"
        raise ParamError(f"'{nome}' deve ser booleano.")
    if valor == "":
        if p.get("obrigatorio"):
            raise ParamError(f"'{nome}' e obrigatorio.")
        return ""
    if tipo == "int":
        if not _INT_RE.match(valor):
            raise ParamError(f"'{nome}' deve ser inteiro.")
        n = int(valor)
        if p.get("minimo") is not None and n < p["minimo"]:
            raise ParamError(f"'{nome}' < minimo ({p['minimo']}).")
        if p.get("maximo") is not None and n > p["maximo"]:
            raise ParamError(f"'{nome}' > maximo ({p['maximo']}).")
        return valor
    if tipo == "select":
        if valor not in p.get("choices", []):
            raise ParamError(f"'{nome}' fora das opcoes permitidas.")
        return valor
    # text
    if not _TEXT_SEGURO.match(valor):
        raise ParamError(f"'{nome}' contem caractere nao permitido.")
    return valor


def build_invocation(script: Script, valores: dict) -> tuple[list[str], dict, str]:
    """Monta (argv_extra, env_extra, audit_params) a partir do param_schema do script.

    argv_extra: argumentos posicionais/flags a anexar depois do caminho do script.
    env_extra: variaveis de ambiente a injetar (parametros com 'env').
    audit_params: string para a auditoria, com 'secret' mascarado.
    """
    argv: list[str] = []
    env: dict[str, str] = {}
    audit: list[str] = []
    for p in _as_dicts(script.param_schema):
        bruto = _valor_resolvido(p, valores)
        valor = _validar_valor(p, bruto)
        mostrado = "***" if p.get("secret") else valor

        if p.get("env"):
            env[p["env"]] = valor
            audit.append(f"{p['env']}={mostrado}")
            continue
        if p.get("tipo") == "bool" and p.get("sem_valor"):
            if valor == "true" and p.get("arg"):
                argv.append(p["arg"])
                audit.append(p["arg"])
            continue
        if valor == "" and not p.get("obrigatorio") and not p.get("constante"):
            continue
        if p.get("arg"):
            argv.extend([p["arg"], valor])
            audit.append(f"{p['arg']} {mostrado}")
        else:
            argv.append(valor)
            audit.append(mostrado)
    return argv, env, " ".join(audit)
