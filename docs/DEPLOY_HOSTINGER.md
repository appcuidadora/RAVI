# Deploy do RAVI — Hostinger (Docker)

O RAVI é composto por 3 serviços: **MongoDB**, **backend FastAPI** (porta 8001) e **frontend React** (nginx, porta 80). O empacotamento via Docker torna o deploy portátil para Hostinger VPS, Hostinger Cloud ou qualquer outra infraestrutura com Docker.

> Nota: o plano "Web App Unlimited" da Hostinger é voltado a sites estáticos/Node gerenciado e **não executa Python + MongoDB persistentes**. Para o RAVI completo, use **Hostinger VPS** (ou Cloud) com Docker — é o alvo deste guia.

## Pré-requisitos

- VPS Hostinger (Ubuntu 22.04+) com Docker e Docker Compose instalados
- Domínio apontado para o IP do VPS (registros A: `@` e/ou `app`)
- Credenciais do Meta App (META_APP_ID, META_APP_SECRET, META_CONFIG_ID) — ver seção WhatsApp

## Passo a passo

### 1. Clonar o código no VPS

```bash
git clone <seu-repo> ravi && cd ravi
```

### 2. Configurar variáveis de ambiente

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
nano backend/.env
```

Preencha **todas** as variáveis (o backend falha rápido se faltar config — é intencional):

| Variável | Como gerar |
|---|---|
| `JWT_SECRET` | `openssl rand -hex 32` |
| `ADMIN_PASSWORD` | senha forte única (não reutilizar) |
| `WEBHOOK_CRON_SECRET` | `openssl rand -hex 32` |
| `META_WEBHOOK_VERIFY_TOKEN` | `openssl rand -hex 24` |
| `FRONTEND_URL` / `CORS_ORIGINS` | `https://app.seudominio.com` |
| `EMERGENT_LLM_KEY` | chave universal (Profile → Manage plan → Universal Key) |

### 3. Subir os serviços

```bash
PUBLIC_BACKEND_URL=https://app.seudominio.com docker compose up -d --build
```

- O frontend é servido pelo nginx na porta 80 e faz proxy de `/api/*` para o backend.
- O MongoDB roda em volume nomeado `mongo_data` (persistente).

### 4. HTTPS (obrigatório — cookies são `Secure`)

Cookies de sessão usam `Secure; HttpOnly`, então **HTTPS é obrigatório**. Opção simples com Caddy na frente:

```
app.seudominio.com {
    reverse_proxy localhost:80
}
```

Ou configure o nginx do host com Certbot (`sudo certbot --nginx`).

### 5. WhatsApp (Meta)

1. No Meta App do RAVI, registre o webhook: `https://app.seudominio.com/api/webhooks/whatsapp` com o `META_WEBHOOK_VERIFY_TOKEN` configurado.
2. Preencha `META_APP_ID`, `META_APP_SECRET`, `META_CONFIG_ID` no `.env` (ou pela tela admin → Meta, que grava em `platform_settings`).
3. O webhook **rejeita eventos sem assinatura válida** (HMAC-SHA256 com META_APP_SECRET) — sem o secret configurado, o endpoint responde 503.

### 6. Backup

Na Emergent, o backup roda diário via cron da plataforma (`POST /api/cron/backup-database`, 06:00 UTC). **Self-hosted**: agende no crontab do host:

```bash
# crontab -e (03:00 diário)
0 3 * * * curl -s -X POST http://localhost/api/cron/backup-database -H "Authorization: Bearer $WEBHOOK_CRON_SECRET" -H "Content-Type: application/json" -d '{}'
```

O backup gera `mongodump --gzip`, envia ao object storage (`backups/`) e mantém 7 cópias locais em `/app/backups`. Resultado registrado em `admin_logs` (`backup_completed` / `backup_failed`).

**Restauração:**

```bash
# Baixe o arquivo desejado do object storage e execute:
docker exec -i ravi-mongo-1 mongorestore --uri="mongodb://localhost:27017" \
  --db=ravi_producao --archive --gzip < ravi-AAAAMMDD-HHMMSS.archive.gz
```

### 7. Monitoramento

- Liveness: `GET /api/health` → `{"status":"ok","mongo":"ok"}` (use no monitoramento do VPS/UptimeRobot)
- Health check completo (9 componentes): painel admin → WhatsApp/Meta

## Portabilidade

A mesma composição roda em qualquer infra com Docker (Hostinger Cloud, AWS, Hetzner, DigitalOcean). Para provedores com Mongo gerenciado (Atlas), basta apontar `MONGO_URL` e remover o serviço `mongo` do compose.
