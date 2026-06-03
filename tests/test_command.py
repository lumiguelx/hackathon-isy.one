"""Testa o montador de comando estruturado (app.services.command)."""

import pytest

from app.models import Script
from app.services import command


def _script(param_schema):
    return Script(nome="s", caminho="x.sh", tipo="arquivo", param_schema=param_schema)


def test_validate_schema_ok():
    command.validate_schema(
        [
            {"nome": "acao", "tipo": "select", "choices": ["a", "b"], "arg": "--acao"},
            {"nome": "n", "tipo": "int", "minimo": 1, "maximo": 9},
        ]
    )


@pytest.mark.parametrize(
    "schema, erro",
    [
        ([{"nome": "a", "tipo": "select", "choices": []}], "choices"),
        ([{"nome": "a", "tipo": "xxx"}], "Tipo"),
        ([{"nome": "a", "tipo": "int", "minimo": 5, "maximo": 1}], "min"),
        ([{"nome": "a", "tipo": "text", "arg": "in valido"}], "Arg"),
        ([{"nome": "a", "tipo": "text"}, {"nome": "a", "tipo": "int"}], "duplicado"),
    ],
)
def test_validate_schema_rejeita(schema, erro):
    with pytest.raises(command.ParamError) as ei:
        command.validate_schema(schema)
    assert erro.lower() in str(ei.value).lower()


def test_build_flag_e_posicional():
    s = _script(
        [
            {"nome": "acao", "tipo": "select", "choices": ["restart"], "arg": "--acao"},
            {"nome": "alvo", "tipo": "text"},  # posicional
        ]
    )
    argv, env, audit = command.build_invocation(s, {"acao": "restart", "alvo": "odoo"})
    assert argv == ["--acao", "restart", "odoo"]
    assert env == {}
    assert audit == "--acao restart odoo"


def test_build_sem_valor_e_env_e_constante():
    s = _script(
        [
            {"nome": "v", "tipo": "bool", "arg": "--verbose", "sem_valor": True},
            {"nome": "t", "tipo": "text", "env": "ISY_ALVO"},
            {"nome": "fixo", "tipo": "text", "constante": "sempre"},
        ]
    )
    argv, env, _ = command.build_invocation(s, {"v": "true", "t": "logs"})
    assert argv == ["--verbose", "sempre"]
    assert env == {"ISY_ALVO": "logs"}
    # bool false nao inclui a flag
    argv2, _, _ = command.build_invocation(s, {"v": "false", "t": "logs"})
    assert "--verbose" not in argv2


def test_build_mascara_secret():
    s = _script([{"nome": "senha", "tipo": "text", "arg": "-p", "secret": True}])
    argv, _, audit = command.build_invocation(s, {"senha": "abc123"})
    assert argv == ["-p", "abc123"]  # valor real vai pro comando
    assert "abc123" not in audit and "***" in audit  # auditoria mascarada


def test_build_valida_int_faixa():
    s = _script([{"nome": "n", "tipo": "int", "arg": "-n", "minimo": 1, "maximo": 10}])
    with pytest.raises(command.ParamError):
        command.build_invocation(s, {"n": "99"})
    with pytest.raises(command.ParamError):
        command.build_invocation(s, {"n": "abc"})
    argv, _, _ = command.build_invocation(s, {"n": "5"})
    assert argv == ["-n", "5"]


def test_build_rejeita_metacaractere_shell():
    s = _script([{"nome": "x", "tipo": "text", "arg": "-x"}])
    with pytest.raises(command.ParamError):
        command.build_invocation(s, {"x": "a; rm -rf /"})


def test_build_select_fora_das_opcoes():
    s = _script([{"nome": "a", "tipo": "select", "arg": "--a", "choices": ["x", "y"]}])
    with pytest.raises(command.ParamError):
        command.build_invocation(s, {"a": "z"})


def test_build_obrigatorio_vazio():
    s = _script([{"nome": "a", "tipo": "text", "arg": "-a", "obrigatorio": True}])
    with pytest.raises(command.ParamError):
        command.build_invocation(s, {})
