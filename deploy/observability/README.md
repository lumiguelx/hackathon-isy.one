# Observabilidade da frota Docker (OTel + Prometheus + Grafana)

Monitora a **saude dos containers Docker** dos servidores de cliente de forma
continua e escalavel, complementando o `docker_status` sob demanda (via SSH) do
painel.

```
[servidor do cliente]                              [central]
  cAdvisor (metricas dos containers)
  node-exporter (disco/CPU do host)
        | scrape local
  OTel Collector  --remote-write-->  Prometheus  -->  Grafana
   (1 por cliente, na borda)         (recebe push)     (paineis)
```

## Por que OTel na borda escala melhor

- **Push do cliente:** nao preciso abrir porta de scrape nem manter lista de N alvos
  no Prometheus central; cada cliente empurra.
- **Um agente padrao por cliente** (cadvisor + node-exporter + collector) que no
  futuro tambem carrega logs/traces — vendor-neutral.
- **Batch, retry, mTLS e relabel** no Collector; trocar o backend e so reconfigurar
  o Collector, sem tocar nos clientes.

## Subir (na VM do cliente)

```bash
cd deploy/observability
docker compose up -d
```

## Acessar o Grafana

- **Gravacao/local (recomendado):** tunel SSH, sem expor nada na internet:
  ```bash
  ssh -i ~/.ssh/isyone_deploy -L 3000:localhost:3000 isyone@<IP_DA_VM>
  # abra http://localhost:3000  (login desabilitado, acesso anonimo Viewer)
  ```
- **Publico (opcional):** abrir a porta 3000 no security group e acessar
  `http://<IP_DA_VM>:3000`. So faca isso de forma temporaria (Grafana publico).

O dashboard "IsyOne — Saude da Frota Docker" ja vem provisionado como home. Ao rodar
`update_agent` pelo painel, o painel "Inicio do container" mostra o salto (restart);
ao rodar `cleanup_logs`, o "Disco livre no host" sobe.
