<div align="center">

<img src="app/static/brand/c_dark.svg" alt="ISYOPS" width="420" />

### Painel de automação de manutenção multi-cliente para a frota Isy.One

Executa, de forma controlada, isolada e auditada, os shell scripts de manutenção
dos servidores dos restaurantes parceiros — eliminando o acesso manual via SSH.

[**Demo ao vivo**](https://hackathon-api-production-5f01.up.railway.app/ui) · [**API (Swagger)**](https://hackathon-api-production-5f01.up.railway.app/docs)

`Python 3.11` · `FastAPI` · `SQLAlchemy 2.0` · `PostgreSQL` · `Docker` · `Grafana`

</div>

---

## O problema

O suporte da Isy.One mantém centenas de servidores Linux de restaurantes parceiros
(Agente de Impressão do iFood). Toda manutenção — atualizar o agente, limpar logs de
cupons antigos, checar os containers Docker do banco — exige **acesso manual via SSH**
para rodar shell scripts. É lento, sem rastreabilidade e vira gargalo operacional: não
se sabe quem rodou o quê, quando, com quais parâmetros e qual foi o resultado.

## A solução

Um **painel central multi-cliente** que executa esses scripts por requisição
autenticada, isolada por cliente e registrada como evento imutável. Cada restaurante é
um **tenant** com credencial própria; cada execução vira **auditoria permanente**; e a
**saúde** de cada cliente (verde / amarelo / vermelho) é calculada a partir do histórico
de execuções, sem tabela de status. Tudo dentro de um container Docker, sem ninguém abrir
um terminal SSH.

## Funcionalidades

- **Multi-tenant isolado** — cada cliente opera apenas os próprios scripts, autenticado
  por token próprio; o token de um cliente nunca alcança outro.
- **Execução segura** — `subprocess.run` com lista de argumentos e `shell=False`,
  whitelist por tenant, validação de path e timeout. Parâmetros maliciosos entram como
  argumento literal, sem efeito.
- **Execução remota via SSH** — quando o tenant tem `ssh_host`, o script alcança o
  servidor real do cliente por SSH; sem ele, roda localmente (modo demo).
- **Auditoria por event sourcing** — toda execução é um evento append-only (horário,
  script, parâmetros, status, exit code, duração). Histórico sem furos.
- **Saúde derivada on-read** — o status de cada cliente é uma projeção calculada sobre os
  eventos, sempre coerente com o que de fato rodou.
- **Parametrização estruturada** — scripts declaram um `param_schema` tipado; o console
  gera os inputs corretos para cada execução.
- **Agendamento (cron) por tenant** — execução autônoma recorrente, com estado e próxima
  execução visíveis no painel.
- **Observabilidade** — métricas exportadas para Prometheus e dashboard de frota no
  Grafana (filtro por cliente, status agregado, latência e contagem de execuções).
- **Alertas em tempo real** — notificações no Slack para falhas, sucessos, agendamentos e
  frota em estado crítico (best-effort, nunca bloqueiam a execução).
- **Console web + self-service** — UI de operação da frota em `/ui` e cadastro de novos
  clientes em `/registro`, com a identidade visual da Isy.One.

## Segurança

Bloco mais estratégico do projeto:

- **Auth em dois níveis** — token **admin** (gestão de tenants e catálogo) e token **por
  tenant** (opera só o próprio cliente). Comparação com `secrets.compare_digest`.
- **Whitelist de execução** — nunca se executa string arbitrária do request; só scripts
  cadastrados, ativos e *bindados* ao cliente.
- **Anti command injection** — `subprocess.run` com lista de argumentos e `shell=False`,
  sempre. No caminho SSH, parâmetros remotos são validados por charset seguro.
- **Anti path traversal** — caminho normalizado e obrigado a residir no diretório montado.
- **Timeout** em toda execução; tokens nunca aparecem em logs nem em respostas.

## Arquitetura

```
Operador / curl / Swagger / Console (/ui)
   │  HTTP + header X-Isy-Token  (token admin OU token do tenant)
   ▼
[api]  FastAPI  ──▶  rota → service → repository
   │        ├─▶ local:  subprocess.run([script, *params], shell=False, timeout)
   │        └─▶ remoto: script faz SSH no servidor do cliente (tenant.ssh_host)
   ▼
[banco]  PostgreSQL / SQLite
         tenants · scripts · tenant_scripts · events (auditoria imutável) · config
```

Backend em camadas com dependências apontando só para dentro
(rota → service → repository → core). Persistência via SQLAlchemy 2.0 (PostgreSQL no
deploy, SQLite na demo local), empacotada numa imagem Docker enxuta sobre
`python:3.11-slim`, publicada no Railway.

Aprofundamento:

- **Arquitetura e diagramas** — [`docs/architecture.md`](docs/architecture.md)
- **Escopo / PRD** — [`docs/specs/2026-06-01-isy-shell-automation-api.md`](docs/specs/2026-06-01-isy-shell-automation-api.md)
- **Decisões de arquitetura** — [`docs/adr/`](docs/adr/) (stack, multi-tenant + event sourcing)

## Time

<table>
  <tr>
    <td align="center" width="200">
      <a href="https://www.linkedin.com/in/ana-gabriella-souza-silva-20a5ab241/">
        <img src="https://github.com/AnaGabisz.png" width="96" height="96" alt="Ana Gabriella" /><br />
        <b>Ana Gabriella</b>
      </a><br />
      <a href="https://github.com/AnaGabisz">@AnaGabisz</a>
    </td>
    <td align="center" width="200">
      <a href="https://www.linkedin.com/in/gabriel-reis-3202b823b/">
        <img src="https://github.com/gabibribru.png" width="96" height="96" alt="Gabriel Reis" /><br />
        <b>Gabriel Reis</b>
      </a><br />
      <a href="https://github.com/gabibribru">@gabibribru</a>
    </td>
    <td align="center" width="200">
      <a href="https://www.linkedin.com/in/miguel-s-souza/">
        <img src="https://github.com/lumiguelx.png" width="96" height="96" alt="Luis Miguel" /><br />
        <b>Luis Miguel</b>
      </a><br />
      <a href="https://github.com/lumiguelx">@lumiguelx</a>
    </td>
  </tr>
</table>
