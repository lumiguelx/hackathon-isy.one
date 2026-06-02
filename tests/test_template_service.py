import pytest

from app.services import template_service as ts


def test_validate_aceita_placeholders_conhecidos():
    ts.validate("docker restart {{container:agent}} {{slug}}")
    ts.validate("find {{logdir}} -mtime +{{param:dias:int}} -delete")


def test_validate_rejeita_placeholder_desconhecido():
    with pytest.raises(ts.TemplateError):
        ts.validate("echo {{container:web}}")
    with pytest.raises(ts.TemplateError):
        ts.validate("echo {{nao_existe}}")
    with pytest.raises(ts.TemplateError):
        ts.validate("echo {{param:x:float}}")


def test_validate_rejeita_metacaractere_no_texto_fixo():
    for ruim in [
        "docker restart {{container:agent}}; rm -rf /",
        "echo {{slug}} && reboot",
        "cat {{logdir}} | sh",
        "echo $(id) {{slug}}",
        "echo `id`",
        "echo {{slug}} > /etc/x",
    ]:
        with pytest.raises(ts.TemplateError):
            ts.validate(ruim)


def test_validate_rejeita_vazio():
    with pytest.raises(ts.TemplateError):
        ts.validate("   ")


def test_validate_rejeita_quebra_de_linha():
    with pytest.raises(ts.TemplateError):
        ts.validate("echo {{slug}}\nrm -rf /")
    with pytest.raises(ts.TemplateError):
        ts.validate("echo {{slug}}\n")


from types import SimpleNamespace


def _tenant(slug="tux-burger"):
    return SimpleNamespace(slug=slug, ssh_host=None)


def test_extract_params_dedup_por_nome_em_ordem():
    params = ts.extract_params("a {{param:dias:int}} {{slug}} {{param:dias:int}}")
    assert params == [{"nome": "dias", "tipo": "int"}]


def test_extract_params_tipo_conflitante():
    with pytest.raises(ts.TemplateError):
        ts.extract_params("{{param:x:int}} {{param:x:slug}}")


def test_render_resolve_container_do_tenant():
    out = ts.render("docker restart {{container:agent}}", _tenant(), [])
    assert out == "docker restart isyone-tux-burger-ifood-agent"


def test_render_db_e_logdir():
    assert ts.render("{{db}}", _tenant("tux-burger"), []) == "db_tux_burger"
    assert ts.render("{{logdir}}", _tenant("tux-burger"), []) == (
        "/opt/isyone/clientes/tux-burger/logs/cupons"
    )


def test_render_valida_param_int():
    assert ts.render("limpa {{param:dias:int}}", _tenant(), ["30"]) == "limpa 30"
    with pytest.raises(ts.TemplateError):
        ts.render("limpa {{param:dias:int}}", _tenant(), ["abc"])


def test_render_faltando_valor():
    with pytest.raises(ts.TemplateError):
        ts.render("limpa {{param:dias:int}}", _tenant(), [])
