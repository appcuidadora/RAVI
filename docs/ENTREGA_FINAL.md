# RAVI — Entrega Final (FASE 7: Segurança, Testes e Produção)

Data: 14/09/2026 · Versão: MVP pronto para produção (pré-lançamento)

---

## 1. Arquitetura final

```
┌─────────────┐     HTTPS      ┌──────────────────┐
│   Cliente   │ ◄────────────► │  Frontend React  │  (nginx :80, build estático CRA/craco)
│  (browser)  │                │  + proxy /api/*  │
└─────────────┘                └────────┬─────────┘
                                        ▼
                              ┌──────────────────┐      ┌─────────────┐
                              │  Backend FastAPI  │ ───► │   MongoDB   │ (multi-tenant por office_id)
                              │     (:8001)       │      └─────────────┘
                              └────────┬─────────┘
                                       ▼
        Meta WhatsApp Cloud API · Claude Sonnet 4.6 (texto) · Whisper (áudio) · Object Storage · E-mail
```

- **Dois ambientes**: RAVI APP (escritórios, cookie `access_token`) × RAVI ADMIN (`/admin`, cookie `admin_access_token`, RBAC por perfil).
- **Multi-tenant nativo**: toda coleção de domínio tem `office_id`; todo acesso passa por `office_filter(user)`; testes automatizados de isolamento Office A × Office B.
- **Motor de IA**: classificação VERDE/AMARELO/VERMELHO (Claude), transcrição de áudio (Whisper + ffmpeg), memória das últimas 50 mensagens, fallback de template.
- **WhatsApp**: Meta Cloud API com Embedded Signup, webhook público com verificação HMAC obrigatória, roteamento `phone_number_id → office_id`, tokens Meta criptografados em repouso (Fernet).
- **Financeiro SaaS**: planos versionados, assinaturas (immediate/next_cycle), consumo WhatsApp com preço congelado por evento, faturas RAVI-WA separadas, ajustes com motivo, consolidado admin.
- **Crons da plataforma** (`.emergent/crons.yml`): lembretes de cobrança (12:00 UTC) e backup diário (06:00 UTC).
- **Deploy portátil**: `Dockerfile.backend`, `Dockerfile.frontend`, `docker-compose.yml`, `nginx.conf` — ver `docs/DEPLOY_HOSTINGER.md`.

## 2. Banco de dados (MongoDB)

| Coleção | Propósito | Índices principais |
|---|---|---|
| users / offices | contas e escritórios | email (unique), office_id |
| clients / processes / process_documents | domínio jurídico | (office_id, phone_normalized), (office_id, client_id) |
| conversations / messages / alerts | atendimento e IA | (office_id, phone_normalized), (office_id, last_message_at), (conversation_id, created_at), meta_message_id, (office_id, status) |
| whatsapp_connections | conexões Meta (token cifrado) | office_id (unique), phone_number_id |
| plans / plan_versions / subscriptions | planos versionados e assinaturas | name, office_id |
| whatsapp_pricing / whatsapp_customer_rates | tarifas Meta e preços RAVI | effective_from |
| whatsapp_usage_events / whatsapp_invoices / billing_periods | consumo e faturamento | (office_id, billing_period), invoice_id, (office_id, issue_date) |
| charges / receipts / payments / billing_adjustments | financeiro | (office_id, status) |
| audit_logs / admin_logs | trilha de auditoria tenant/admin | (office_id, created_at), (created_at) |
| admin_users / login_attempts / password_reset_* | segurança | token_hash (unique), TTL em resets/requests |
| tickets / platform_settings / cron_runs | suporte e plataforma | office_id |

## 3. APIs

- **Auth** `/api/auth/*`: register, login (lockout 5/15min), logout (invalida sessão via token_version), me, refresh, onboarding, forgot/reset password (token uso único, 1h, hash SHA-256).
- **Core** `/api/*`: clients (CRUD, arquivar), processes (CRUD, import-pdf com IA, documentos, cobranças), conversations (timeline, simular, enviar, pausar/assumir/retomar/resolver, link-client validado), alerts, team (RBAC por módulo), office/settings, tickets.
- **WhatsApp** `/api/whatsapp/*`: connect (Embedded Signup com state seguro), status, test-connection, disconnect, usage (painel de consumo).
- **Webhook público** `/api/webhooks/whatsapp`: GET (verify token) / POST (HMAC-SHA256 obrigatório, idempotência por meta_message_id, processamento em background).
- **Crons** `/api/cron/*`: billing-reminders, backup-database (Bearer WEBHOOK_CRON_SECRET, idempotente por run_id).
- **Admin** `/api/admin/*`: auth próprio, dashboard (20 KPIs), offices (edição, suspensão, impersonation auditada SUPER_ADMIN-only), plans+versions, billing (cobranças, faturas WhatsApp, ajustes), pricing (Meta/RAVI), meta/secrets (write-only), health (9 componentes), users (SUPER_ADMIN), logs unificados, tickets, settings/ai, settings/consumption, reports.
- **Saúde** `GET /api/health`: liveness (mongo ping).

## 4. Variáveis de ambiente

Backend (`backend/.env`, modelo em `.env.example`): `MONGO_URL`, `DB_NAME`, `JWT_SECRET`, `ADMIN_EMAIL`, `ADMIN_PASSWORD` (obrigatória, sem default), `FRONTEND_URL`, `CORS_ORIGINS`, `WEBHOOK_CRON_SECRET`, `EMERGENT_LLM_KEY`, `EMERGENT_EMAIL_KEY`, `INTEGRATION_PROXY_URL`, `EMAIL_FROM_NAME`, `META_APP_ID`, `META_APP_SECRET`, `META_CONFIG_ID`, `META_GRAPH_VERSION`, `META_WEBHOOK_VERIFY_TOKEN`, `META_TEST_PHONE_NUMBER_ID`, `META_TEST_WABA_ID`.

Frontend (`frontend/.env`): `REACT_APP_BACKEND_URL`, `REACT_APP_META_APP_ID`, `REACT_APP_META_CONFIG_ID`, `REACT_APP_META_GRAPH_VERSION`.

**Nenhum secret é commitado; secrets Meta são write-only no admin; tokens de conexão são cifrados com Fernet (derivado de JWT_SECRET).**

## 5. Dependências externas

| Serviço | Uso | Observação |
|---|---|---|
| Meta WhatsApp Cloud API | mensagens | requer Meta App próprio (P0) |
| Claude Sonnet 4.6 (Emergent LLM Key) | motor de decisão IA | texto |
| OpenAI Whisper (Emergent LLM Key) | transcrição de áudios | ffmpeg no container |
| Emergent Object Storage | PDFs e backups | via integration proxy |
| Emergent E-mail | reset de senha | — |
| mongodump (mongodb-database-tools) | backup | presente no ambiente |

## 6. Riscos conhecidos

1. **Token de teste da Meta expira em 24h** — em produção, usar System User Token (não expira).
2. **Credenciais do Meta App pendentes** (P0): sem META_APP_ID/SECRET/CONFIG_ID reais, Embedded Signup e webhook real ficam inativos (webhook responde 503 fail-closed — comportamento seguro).
3. **Senha do super-admin** precisa ser rotacionada no go-live (fallback hardcoded removido nesta fase; valor atual é de teste).
4. **Cookies SameSite=None** (necessário para o fluxo cross-origin atual); em produção com frontend e API no mesmo domínio, avaliar `Strict/Lax` + CSRF token.
5. **Semântica dos alertas de consumo**: o contador considera todos os eventos (inbound+outbound) contra o limite do plano — decisão de produto pendente.
6. **login_attempts cresce sem TTL** (created_at é string ISO; TTL exigiria migração para BSON date) — baixo volume, sem impacto prático.

## 7. Problemas encontrados e corrigidos nesta fase

| ID | Severidade | Problema | Correção |
|---|---|---|---|
| SEC-001 | HIGH | Qualquer perfil admin podia impersonar escritórios e alterar billing/secrets | RBAC por perfil (`require_admin_roles`): impersonate = SUPER_ADMIN; financeiro/planos/pricing = ADMIN_FINANCEIRO; secrets/IA = ADMIN_TECNOLOGIA |
| SEC-002 | HIGH | Senha do super-admin com fallback hardcoded | Fallback removido; `ADMIN_PASSWORD` obrigatório via env |
| SEC-003 | MEDIUM | Webhook aceitava eventos sem assinatura quando secret vazio | Fail-closed: 503 sem secret, 403 sem assinatura válida |
| SEC-004 | MEDIUM | link-client aceitava client_id de outro escritório (BOLA) | Validação de posse + lookups com filtro de office |
| SEC-005 | MEDIUM | Auditoria sem login/logout/reset/delete/settings/plano | 8 novos eventos de auditoria |
| P3 | Baixa | Logout não invalidava o access token (15min residual) | token_version incrementado no logout |
| P3 | Baixa | Payload do webhook (com PII) era logado | Log redigido (apenas metadados) |
| P3 | Baixa | Token de reset consumido antes de validar a senha | Validação reordenada |
| PERF | — | N+1 em listagens de conversas/alertas; índices faltantes | Batch `$in` + 13 novos índices |
| TEST | — | test_process_reuses_existing_client_by_phone não idempotente | Limpeza prévia no teste |

## 8. Testes executados

- **Regressão completa**: `pytest /app/backend/tests/ -n0` → **181 passed / 7 skipped / 0 failed** (skips ambientais: token Meta 24h).
- **Nova suíte Fase 7** (`test_phase7_security.py`, 20 testes): isolamento multi-tenant A×B (9), RBAC admin (6), assinatura do webhook (3), sessão/logout (1), cobertura de auditoria (1).
- **Cobertura por domínio**: Auth, RBAC (tenant + admin), Multi-tenant, Clientes, Processos, Documentos/PDF (2 fixtures: normal + segredo de justiça), Conversas, Alertas, IA, WhatsApp (webhook, roteamento, áudio), Admin, Financeiro/Faturamento.
- **E2E frontend** (Playwright via testing agent): rotas /login, /onboarding, /dashboard, /clientes, /processos, /conversas, /admin com refresh, acesso direto, sessão expirada e permissões — ver `test_reports/iteration_15.json`.
- **Verificações manuais**: webhook 403/200 (sem/com assinatura), backup cron 401/200 + arquivo gzip + upload ao object storage, /api/health ok.

## 9. Checklist de produção

**P0 — bloqueantes de go-live:**
- [ ] Criar Meta App do RAVI, configurar `META_APP_ID`, `META_APP_SECRET`, `META_CONFIG_ID` e registrar o webhook público na Meta
- [ ] App Review da Meta (whatsapp_business_management/messaging)
- [ ] Rotacionar `ADMIN_PASSWORD` (e demais segredos de teste)
- [ ] Substituir token de teste Meta por System User Token
- [ ] `FRONTEND_URL`/`CORS_ORIGINS` com o domínio final (HTTPS obrigatório — cookies Secure)

**P1 — recomendados:**
- [ ] Agendar backup no host (self-hosted) conforme `docs/DEPLOY_HOSTINGER.md` §6 e testar uma restauração
- [ ] Monitoramento externo de `GET /api/health`
- [ ] Migrar startup/shutdown para lifespan do FastAPI
- [ ] Avaliar SameSite=Strict/Lax quando frontend e API estiverem no mesmo domínio
- [ ] Decidir semântica do contador de alertas de consumo (todos os eventos × só enviados)

**P2 — evolução:** MFA para admins (campo `totp_secret` já existe), versionamento explícito de tarifas no PATCH, trava de fatura duplicada por período, date pickers pt-BR no admin, integração de gateway de pagamento (Stripe/Mercado Pago/Asaas).
