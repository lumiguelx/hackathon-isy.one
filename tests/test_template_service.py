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
