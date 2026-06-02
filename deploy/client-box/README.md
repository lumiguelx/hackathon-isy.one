# Teste real: painel no Railway -> servidor do cliente por SSH

Como ligar o painel (deploy no Railway) a um servidor de cliente real e executar
manutencao de verdade por SSH. Usamos **1 cliente** (`tux-burger`); escalar para N
e so repetir o passo do VPS e cadastrar mais tenants.

```
[Painel no Railway]  --ssh-->  [VPS = servidor do cliente]
                                 roda cleanup_logs / update_agent /
                                 backup_db / docker_status LA
```

O painel injeta no ambiente do script o slug do tenant (`ISY_TENANT_SLUG`) e o
endpoint SSH (`ISY_SSH_HOST`, `ISY_SSH_PORT`, `ISY_SSH_USER`), e usa a chave privada
do secret `ISY_SSH_KEY`. Os scripts do repo sao finos: validam os argumentos
(charset) e chamam os helpers reais em `/opt/isyone/bin` do VPS via `_ssh.sh`. Sem
`ssh_host`, o script roda localmente (modo demo com saida simulada).

## 1. Gerar a chave de deploy (na sua maquina)

```bash
ssh-keygen -t ed25519 -f isyone_deploy -N "" -C "isyone-painel"
# gera isyone_deploy (privada) e isyone_deploy.pub (publica)
```

## 2. Configurar o painel no Railway

No painel do servico, em Variables:

- `ISY_SSH_KEY` = conteudo **inteiro** de `isyone_deploy` (a chave privada, multilinha)
- `ISY_SSH_USER` = `isyone` (opcional; ja e o default)

Mantenha tambem `ISY_TOKEN`, `ISY_DATABASE_URL` (Postgres) e `ISY_SEED_DEMO=true`.
Redeploy apos salvar.

## 3. Preparar o VPS (o "servidor do cliente")

Num VPS Ubuntu, com sudo (o `provision.sh` instala o Docker se faltar):

```bash
# copie provision.sh e a chave publica para o VPS, entao:
sudo bash provision.sh "$(cat isyone_deploy.pub)" tux-burger
```

Isso:

- instala o Docker (se ausente) e cria o usuario `isyone` com a chave autorizada e
  acesso ao Docker;
- instala os helpers de manutencao em `/opt/isyone/bin`
  (`cleanup_logs`, `update_agent`, `backup_db`);
- sobe os containers `isyone-tux-burger-db` (Postgres), `isyone-tux-burger-odoo`
  (nginx) e `isyone-tux-burger-ifood-agent` (deixado **parado** de proposito, para
  o dashboard comecar VERMELHO);
- semeia milhares de logs de cupons iFood antigos em
  `/opt/isyone/clientes/tux-burger/logs/cupons` para o `cleanup_logs` ter o que
  remover de verdade.

Garanta que a porta 22 do VPS esteja aberta para a internet.

## 4. Apontar o tenant para o VPS (via API do painel)

```bash
PAINEL=https://SEU-APP.up.railway.app
ADMIN=seu-token-admin

curl -X PUT "$PAINEL/api/v1/admin/tenants/tux-burger" \
  -H "X-Isy-Token: $ADMIN" -H "Content-Type: application/json" \
  -d '{"ssh_host":"<IP_DO_VPS>","ssh_port":22}'
```

## 5. Executar de verdade (sequencia da demo)

Pela UI (card do Tux Burger -> executar) ou via API. A saude sai de VERMELHO para
VERDE conforme a manutencao roda:

1. `docker_status` -> mostra o agente `Exited` (cliente VERMELHO)
2. `update_agent` -> reinicia o agente iFood (volta `Up`)
3. `backup_db` -> gera um `.sql.gz` real (backup recente)
4. `cleanup_logs` -> remove os cupons antigos e reporta espaco liberado real
5. `docker_status` de novo -> tudo `Up` (cliente VERDE)

O `stdout` de cada execucao e real, gravado no event store e refletido no dashboard.
Os logs remotos comecam com `[remoto isyone@<IP>:22]`.

## Escalar para N clientes

- **Mais barato:** mais VPSs, um por cliente (cada um roda `provision.sh` com seu
  slug); cadastre `ssh_host` de cada tenant.
- **Um VPS so:** rode varios containers `sshd` em portas diferentes (2201, 2202, ...)
  e use `ssh_port` por tenant.

## Seguranca

- A chave privada vive so como secret no Railway; o `_ssh.sh` a materializa em
  arquivo temporario (chmod 600) e apaga ao fim.
- Os scripts do repo validam todo argumento interpolado no comando remoto (charset),
  barrando injecao no host do cliente.
- Usuario dedicado (`isyone`). Em producao, restrinja ainda mais os comandos
  permitidos (ex.: `command=` no authorized_keys).
