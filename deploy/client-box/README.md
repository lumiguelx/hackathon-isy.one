# Teste real: painel no Railway -> servidor do cliente por SSH

Como ligar o painel (deploy no Railway) a um servidor de cliente real e executar
manutencao de verdade por SSH. Comecamos com **1 cliente**; escalar para N e so
repetir o passo do VPS e cadastrar mais tenants.

```
[Painel no Railway]  --ssh-->  [VPS = servidor do cliente]  (roda docker ps / backup LA)
```

O painel injeta o endpoint SSH do tenant no ambiente do script (`ISY_SSH_HOST`,
`ISY_SSH_PORT`, `ISY_SSH_USER`) e usa a chave privada do secret `ISY_SSH_KEY`. Se o
tenant nao tiver `ssh_host`, o script roda localmente (modo demo).

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

Num VPS com Docker instalado, como root:

```bash
# copie provision.sh e a chave publica para o VPS, entao:
sudo bash provision.sh "$(cat isyone_deploy.pub)" cliente1
```

Isso cria o usuario `isyone` com a chave autorizada, da acesso ao Docker e sobe
dois containers de exemplo (`isyone-cliente1-db`, `isyone-cliente1-odoo`).
Garanta que a porta 22 do VPS esteja aberta para a internet.

## 4. Apontar o tenant para o VPS (via API do painel)

```bash
PAINEL=https://SEU-APP.up.railway.app
ADMIN=seu-token-admin

curl -X PUT "$PAINEL/api/v1/admin/tenants/cliente-1" \
  -H "X-Isy-Token: $ADMIN" -H "Content-Type: application/json" \
  -d '{"ssh_host":"<IP_DO_VPS>","ssh_port":22}'
```

## 5. Executar de verdade

Pela UI (card do Cliente 1 -> docker_status -> executar) ou via API:

```bash
curl -X POST "$PAINEL/api/v1/tenants/cliente-1/scripts/<SID>/run" \
  -H "X-Isy-Token: tok-cliente-1-000000" -H "Content-Type: application/json" \
  -d '{"parametros":[]}'
```

O `stdout` traz o `docker ps` **real do VPS**, gravado no event store e refletido no
dashboard. O log comeca com `[remoto isyone@<IP>:22]`.

## Escalar para 5 clientes

- **Mais barato:** mais VPSs, um por cliente (cada um roda `provision.sh` com seu slug);
  cadastre `ssh_host` de cada tenant.
- **Um VPS so:** rode varios containers `sshd` em portas diferentes (2201, 2202, ...) e
  use `ssh_port` por tenant. Cada container precisa de acesso ao Docker (montar o socket)
  ou expor comandos reais sem Docker (`uptime`, `df`, `systemctl`).

## Seguranca

- A chave privada vive so como secret no Railway; o script a materializa em arquivo
  temporario (chmod 600) e apaga ao fim.
- Use um usuario dedicado (`isyone`) com o minimo necessario. Em producao, restrinja os
  comandos permitidos (ex.: `command=` no authorized_keys) e evite dar grupo docker se
  nao precisar.
