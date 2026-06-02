"""Parse, validacao e render seguro de templates de comando de manutencao.

Um template e uma linha de comando com placeholders tipados. O texto literal nao
pode conter metacaracteres de shell; os placeholders sao resolvidos a partir do
tenant vinculado (slug/container/db/logdir) ou de parametros tipados fornecidos no
run. O resultado e uma string livre de metacaracteres -- segura para interpolar no
comando SSH remoto -- e nunca executa nada por conta propria.
"""

import re

# Conjunto permitido em segmentos literais e na string final renderizada. Exclui
# todos os metacaracteres de shell (; & | ` $ ( ) { } < > \\ " ' * ? [ ]).
_SAFE_CHARS = r"A-Za-z0-9 _.,/=:+-"
_LITERAL_RE = re.compile(rf"^[{_SAFE_CHARS}]*\Z")
_RENDERED_RE = re.compile(rf"^[{_SAFE_CHARS}]+\Z")
_PLACEHOLDER_RE = re.compile(r"\{\{\s*([^{}]*?)\s*\}\}")
_PARAM_RE = re.compile(r"^param:([a-z][a-z0-9_]*):(int|slug)$")

_CONTAINER_ROLES = {"db": "db", "odoo": "odoo", "agent": "ifood-agent"}
_PARAM_VALIDADORES = {
    "int": re.compile(r"^[0-9]+$"),
    "slug": re.compile(r"^[a-z0-9-]+$"),
}
_MAX_LEN = 2000


class TemplateError(ValueError):
    """Template invalido ou valor de parametro fora do tipo declarado."""


def _check_placeholder(inner: str) -> None:
    if inner in ("slug", "db", "logdir"):
        return
    if inner.startswith("container:"):
        role = inner.split(":", 1)[1]
        if role not in _CONTAINER_ROLES:
            raise TemplateError(f"Container invalido: '{role}'.")
        return
    if _PARAM_RE.match(inner):
        return
    raise TemplateError(f"Placeholder invalido: '{{{{{inner}}}}}'.")


def validate(template: str | None) -> None:
    """Valida tamanho, placeholders conhecidos e literais sem metacaractere."""
    if not template or not template.strip():
        raise TemplateError("Template vazio.")
    if len(template) > _MAX_LEN:
        raise TemplateError(f"Template excede {_MAX_LEN} caracteres.")
    pos = 0
    for m in _PLACEHOLDER_RE.finditer(template):
        if not _LITERAL_RE.match(template[pos : m.start()]):
            raise TemplateError("Texto fixo contem caractere proibido.")
        _check_placeholder(m.group(1))
        pos = m.end()
    if not _LITERAL_RE.match(template[pos:]):
        raise TemplateError("Texto fixo contem caractere proibido.")


def extract_params(template: str) -> list[dict]:
    """Params {nome, tipo} deduplicados por nome, na ordem de primeira aparicao."""
    params: list[dict] = []
    vistos: dict[str, str] = {}
    for m in _PLACEHOLDER_RE.finditer(template):
        pm = _PARAM_RE.match(m.group(1))
        if not pm:
            continue
        nome, tipo = pm.group(1), pm.group(2)
        if nome in vistos:
            if vistos[nome] != tipo:
                raise TemplateError(f"Parametro '{nome}' com tipos divergentes.")
            continue
        vistos[nome] = tipo
        params.append({"nome": nome, "tipo": tipo})
    return params


def _db_name(slug: str) -> str:
    return "db_" + slug.replace("-", "_")


def render(template: str, tenant, valores: list[str]) -> str:
    """Renderiza o template para uma string segura, resolvendo placeholders.

    Tenant (slug/container/db/logdir) vem do tenant vinculado; params vem de
    `valores` (posicional, na ordem declarada). Levanta TemplateError em qualquer
    inconsistencia.
    """
    validate(template)
    params = extract_params(template)
    if len(valores) != len(params):
        raise TemplateError(
            f"Numero de parametros invalido: esperado {len(params)}, recebido {len(valores)}."
        )
    valor_por_nome: dict[str, str] = {}
    for i, p in enumerate(params):
        valor = valores[i]
        if not _PARAM_VALIDADORES[p["tipo"]].match(valor):
            raise TemplateError(
                f"Parametro '{p['nome']}' invalido para tipo {p['tipo']}: '{valor}'."
            )
        valor_por_nome[p["nome"]] = valor

    def _sub(m: "re.Match") -> str:
        inner = m.group(1)
        if inner == "slug":
            return tenant.slug
        if inner == "db":
            return _db_name(tenant.slug)
        if inner == "logdir":
            return f"/opt/isyone/clientes/{tenant.slug}/logs/cupons"
        if inner.startswith("container:"):
            role = inner.split(":", 1)[1]
            return f"isyone-{tenant.slug}-{_CONTAINER_ROLES[role]}"
        return valor_por_nome[_PARAM_RE.match(inner).group(1)]

    rendered = _PLACEHOLDER_RE.sub(_sub, template).strip()
    if not _RENDERED_RE.match(rendered):
        raise TemplateError("Comando renderizado contem caractere inesperado.")
    return rendered
