# RAVI — PRD

## Problema original
SaaS multi-tenant de atendimento e inteligência para escritórios de advocacia. O RAVI responde automaticamente clientes no WhatsApp sobre andamento de processos, devolvendo tempo ao advogado. "Seu cliente pergunta. O Ravi responde. Você só entra quando realmente precisa." Visão: RAVI Atendimento → Inteligência → Gestão → JARVIS (futuro, fora do MVP).

## Arquitetura
- Frontend: React 19 + Tailwind + shadcn/ui (tema dark premium, gradiente azul/índigo/roxo, fontes Plus Jakarta Sans/Inter/JetBrains Mono)
- Backend: FastAPI modular (auth_routes, core_routes, whatsapp_routes, pipeline, ai, security, utils, seed)
- Banco: MongoDB com `office_id` em toda coleção (isolamento multi-tenant no backend, validado por teste)
- IA: Claude Sonnet 4.6 via emergentintegrations (EMERGENT_LLM_KEY), motor de decisão verde/amarelo/vermelho com fallback de template
- WhatsApp: Meta Cloud API com Embedded Signup v4 (um Meta App → N escritórios), webhook público com verificação e assinatura, roteamento por phone_number_id → office_id

## Modelo de dados
users, offices, clients, processes (parser CNJ: segmento/tribunal/origem/ano), conversations, messages, alerts, whatsapp_connections, audit_logs, login_attempts, password_reset_tokens/requests

## Papéis e permissões
SOCIO_ADMIN (total), ADVOGADO_ASSOCIADO, ESTAGIARIO, SECRETARIA_ATENDIMENTO — 11 módulos com permissões granulares verificadas no backend (`require_permission`).

## Fluxos implementados
- Auth: register → onboarding (cria escritório) → JWT httpOnly (access 15min + refresh 7d) → rota preservada após refresh; forgot/reset password por e-mail; lockout 5 tentativas/15min
- WhatsApp: webhook GET (verify token) / POST (assinatura HMAC, idempotência por meta_message_id); connect via Embedded Signup (code → token → subscribe WABA → WhatsAppConnection)
- Conversas: pipeline central (webhook e simulação), cliente desconhecido → conversa `unidentified` + alerta "Novo contato no WhatsApp" + vincular/criar cliente; Pausar/Assumir/Retomar Ravi
- Motor RAVI: classificação VERDE (responde com contexto do processo), AMARELO (responde + acompanhamento), VERMELHO (escalonamento + alerta, nunca inventa informação)
- Dashboard: KPIs (processos/clientes/resolvidos/precisam de você/tempo estimado economizado), fila de atenção, gráfico por horário
- Auditoria: todos os eventos (mensagens, respostas, intervenções, equipe) em audit_logs
- Normalização de telefone única (utils.normalize_phone): usada em cadastro, webhook, busca e conversas

## Credenciais
- Admin: construcaovilanova@gmail.com / Ravi@2026 (Dr. Carlos Mendes, Silva Advocacia)
- Demo seed: cliente Carlos Eduardo, processo 1001234-56.2025.8.26.0100 (TJSP), conversa demo, alerta vermelho, KPIs 50/63/41/3/3h42

## FASE 7 — Segurança, Testes e Produção (14/09/2026) — VALIDADA
- Auditoria de segurança (security_audit_agent): veredito inicial FAIL → todas as correções aplicadas e revalidadas (iteration_15: fase7 20/20, regressão 181 passed / 7 skipped / 0 failed; E2E frontend 100%)
- SEC-001: RBAC do RAVI ADMIN por perfil (require_admin_roles) — impersonate só SUPER_ADMIN; planos/billing/pricing/faturas = ADMIN_FINANCEIRO; secrets/IA = ADMIN_TECNOLOGIA; tickets = SUPORTE/OPERAÇÕES
- SEC-002: fallback hardcoded de ADMIN_PASSWORD removido (env obrigatório, fail-fast)
- SEC-003: webhook fail-closed — 503 sem META_APP_SECRET, 403 sem assinatura HMAC-SHA256 válida; secret resolvido de env ou platform_settings; log do webhook sem PII
- SEC-004: link-client valida posse do client_id (404 cross-office); lookups de client/process com filtro de office
- SEC-005: +8 eventos de auditoria (user_login/logout, password_reset_*, client_deleted, alert_resolved, office_settings_updated, plan_changed)
- P3: logout incrementa token_version (invalida sessão imediatamente); reset-password valida senha antes de consumir token
- Performance: 13 novos índices (create_indexes) + N+1 eliminado em list_conversations e list_alerts
- Produção: GET /api/health, exception handler global sem stack trace, backup diário (mongodump gzip → object storage, 7 cópias locais, cron 06:00 UTC, endpoint /api/cron/backup-database)
- Deploy portátil: Dockerfile.backend, Dockerfile.frontend, docker-compose.yml, nginx.conf, .env.example, docs/DEPLOY_HOSTINGER.md
- Entrega: docs/ENTREGA_FINAL.md (arquitetura, banco, APIs, envs, dependências, riscos, problemas, testes, checklist)
- Testes webhook agora assinam payloads (tests/_webhook_sign.py); segredo de teste em platform_settings (NÃO é o secret real da Meta)

## FASE 6 — Planos, Consumo WhatsApp e Financeiro (10/09/2026) — VALIDADA
- Validação formal (iteration_14): test_phase6_billing.py com 19 testes, 19/19 verdes; regressão global 162 passed / 6 skipped (token Meta 24h) / 0 failed; frontend confirmado via Playwright (/admin/whatsapp/pricing, /admin/relatorios consolidado, /whatsapp painel consumo)
- PlanVersion: versionamento automático a cada alteração comercial (versão anterior encerrada, nunca sobrescrita); GET /admin/plans/{id}/versions
- Subscription: mudança de plano registra assinatura com plan_version_id, opção "immediate" ou "next_cycle" (agendada via pending_plan_id)
- WhatsAppUsageEvent: cada mensagem registrada individualmente com categoria Meta (SERVICE/UTILITY/MARKETING/AUTH*), billable, meta_cost e ravi_price CONGELADOS no evento (histórico imutável); hooks no pipeline (inbound, respostas, lembretes UTILITY faturáveis)
- WhatsAppPricing (custo Meta versionado) + WhatsAppCustomerRate (preço RAVI por plano) — CRUD admin em /admin/whatsapp/pricing, nada fixo em código
- Faturas WhatsApp separadas da assinatura (invoice_number RAVI-WA-*, itens por categoria, pay com payments); ajustes manuais (crédito/desconto/estorno) com motivo obrigatório
- BillingPeriod materializado no faturamento; painel do escritório GET /api/whatsapp/usage (faturáveis, acumulado, faturado, a pagar, histórico diário) na tela /whatsapp
- Consolidado admin /admin/reports/whatsapp (receita, custo Meta, margem, por escritório/categoria/período) em /admin/relatorios
- Alertas de consumo por % do limite do plano (configurável, default 70/80/90, nunca bloqueia)

## FASE 5 — RAVI ADMIN fechamento (10/09/2026)
- /admin/usuarios: CRUD de administradores (roles SUPER_ADMIN/ADMIN_FINANCEIRO/SUPORTE/OPERACOES/COMERCIAL/TECNOLOGIA/ANALISTA), senha temporária, desativar/reativar, apenas SUPER_ADMIN gerencia
- Logs com filtro por período (from_date/to_date) além de tipo/escritório
- Demais itens da fase já existiam (dashboard, escritórios, impersonation, health, suporte, relatórios, config IA)

## FASE 4 — WhatsApp Meta (10/09/2026)
- Já existente e testado: webhook GET/POST público, roteamento phone_number_id→office_id, novo contato→unidentified+alerta+criar/vincular, Embedded Signup com state seguro, admin de secrets write-only
- Novo: criptografia de tokens em repouso (Fernet derivado de JWT_SECRET) — encrypt_token ao salvar (connect-test + callback), conn_token com fallback transparente para legado em texto puro; todos os pontos de leitura migrados (envio, test-connection, health check, download de mídia)
- webhook processa inbound mesmo com token_expired (envio falha graciosamente, recebimento continua)

## FASE 3 — Conversas e Inteligência (10/09/2026)
- Máquina de estados formal: OPEN/AI_HANDLING/WAITING_HUMAN/RESOLVED/PAUSED (RED → WAITING_HUMAN; takeover → WAITING_HUMAN; pause → PAUSED; resume → AI_HANDLING; resolve → RESOLVED)
- Mensagens SYSTEM na timeline (pause/assume/retoma/resolve) com render próprio centralizado
- RED_SIGNALS + pedido explícito de humano ("quero falar com o advogado") escala automaticamente
- POST /conversations/{id}/resolve fecha alertas abertos e registra alerta tipo "resolved"
- conversation.updated_at em toda mensagem; badge de estado na UI; botão Resolver

## FASE 2 — Clientes e Processos (10/09/2026)
- Clientes: cpf, notes, updated_at, arquivar/reativar (oculto por padrão), detalhe /clientes/:id (dados + processos + histórico de conversas), busca
- Processos: title/subject/court/unit/restricted/last_movement_at; partes estruturadas {tipo: cliente|parte_contraria|advogado|outro, nome}
- Importação inteligente de PDF: POST /api/processes/import-pdf → pypdf + regex CNJ + Claude (JSON estruturado, nunca inventa; campos ausentes em nao_identificados); segredo de justiça → restricted=true sem contornar; documento no object storage com office_id
- Testes validados via curl: PDF normal extraiu número/tribunal/assunto/3 partes/4 movimentações/última mov; PDF restrito detectado corretamente com campos explicitamente não identificados
- Fixtures: /app/tests/fixtures/ravi_processo_teste_01.pdf e ravi_processo_teste_02_restrito.pdf (gerados; os do usuário não foram anexados)

## RAVI ADMIN (entrega 10/09/2026)
- Dois ambientes: RAVI APP (escritórios) × RAVI ADMIN (/admin, SUPER_ADMIN seed, cookie próprio admin_access_token, roles futuras preparadas)
- Dashboard admin: 20 KPIs reais + bloco ⚠️ Atenção (tokens expirados, cobranças vencidas, uso de limite, suspensos)
- Escritórios: listagem enriquecida, edição (status/plano/valores/vencimento/obs), suspensão bloqueia API do tenant (403) sem apagar dados, histórico upgrade/downgrade, churn em cancelamento, **impersonation auditada** (motivo obrigatório, banner âmbar no app, fim registrado)
- Planos: STARTER(25)/PROFESSIONAL(100)/OFFICE(500)/ENTERPRISE configuráveis, overage_pct (padrão 10%) — limite gera alerta; hard limit bloqueia com 402 amigável
- Mini-financeiro: cobranças/recebimentos, aging de inadimplência, MRR/ARR/ticket, descontos; camada de abstração para gateway futuro (Stripe/MP/Asaas)
- Meta admin: secrets write-only (platform_settings + env), ambiente, conexões por escritório, health check de 9 componentes
- Logs: admin_logs + audit_logs unificados com filtros; Suporte: chamados do escritório → gestão no admin
- Config global de IA: regras inegociáveis no system prompt (hierarquia global > escritório > usuário > conversa), modo restrito
- Relatórios: 6 blocos consolidados (/admin/relatorios)

## Estado do MVP (09/09/2026)
- Suíte completa: 78 passed / 0 falhas (7 skips ambientais de token Meta 24h) — /app/test_reports/iteration_8.json
- Pós-review it8: crash de startup corrigido (secrets_meta sibling field + isinstance guard), webhook processa inbound mesmo com token_expired, pay_charge guarda valor_recebido separado, Silva Advocacia no plano OFFICE, testes dependentes de token viram skip ambiental
- WhatsApp conectado com número de teste da Meta (+1 555-665-3479, phone_number_id 1266842309849495); fluxo real confirmado pelo usuário (inbound + outbound)
- Webhook público verificado pela Meta; app RAVI_API inscrito na WABA (subscribe_waba automático em novas conexões)
- Feature 1: cadastro inline de cliente no processo + upload de PDF (object storage Emergent + extração pypdf) — IA lê o documento e responde com o conteúdo (validado: audiência 20/10 respondida a partir do PDF)
- Feature 2: valor da causa + forma de pagamento + cobranças no processo; cron diário `.emergent/crons.yml` (12:00 UTC = 9h BRT) → POST /api/cron/billing-reminders (Bearer WEBHOOK_CRON_SECRET, idempotente por run_id) envia lembretes 5 dias antes (janela com retry) e no dia via WhatsApp; flag só marcada com entrega confirmada
- Feature 3: memória de conversa com as últimas 50 mensagens no contexto da IA
- Feature 4 (áudio): webhook aceita type=audio → baixa mídia via Graph API → ffmpeg ogg→mp3 → Whisper whisper-1 (pt) → pipeline normal; msg salva com kind='audio' e badge "áudio transcrito" na UI; processamento do webhook em BackgroundTasks (ack rápido à Meta); demais tipos (imagem/vídeo/doc/sticker) são ignorados com log
- Feature 5 (conexão SaaS): fluxo Embedded Signup sem credenciais para o advogado — POST /whatsapp/connect/start (state seguro: aleatório, uso único, expira 10min, office_id do JWT) → redirect OAuth oficial da Meta (config_id) → GET /whatsapp/connect/callback (valida state atomicamente, troca code→token, resolve WABA+phone via debug_token, inscreve WABA, salva conexão) → /whatsapp?connected=1; QR Code (react-qr-code) para conectar pelo celular com o mesmo state; POST /whatsapp/test-connection com mensagens amigáveis; desconexão com confirmação mantendo histórico; página sem dados técnicos; BLOQUEIO: precisa META_APP_ID/META_APP_SECRET/META_CONFIG_ID (Meta App do RAVI) para ativar
- Detecção de token Meta expirado: falha OAuth 190 no envio → conexão vira "token_expired" + alerta de intervenção "WhatsApp precisa ser reconectado" (não falha mais em silêncio)
- Regressão: `pytest /app/backend/tests/ -n0`

## Pendências para produção
- P0: credenciais da Meta App (META_APP_ID, META_APP_SECRET, META_CONFIG_ID) para ativar Embedded Signup real; App Review Meta (whatsapp_business_management/messaging); registrar webhook na Meta com a URL pública
- P1: criptografia do access_token da Meta em repouso (KMS); migrar startup/shutdown para lifespan; timeout explícito no LLM; CORS com lista explícita em produção
- P2: integrações de tribunais (fontes públicas/autenticadas), importação de PDF de processos, RAVI Inteligência (consulta conversacional ao advogado), RAVI Gestão (prazos, agenda, financeiro)

## Próximas tarefas
1. Go-live P0 (ver checklist em docs/ENTREGA_FINAL.md §9): Meta App real (META_APP_ID/SECRET/CONFIG_ID + App Review + webhook registrado), rotacionar ADMIN_PASSWORD e segredos de teste, System User Token no lugar do token de 24h
2. Gateway de pagamento real (Stripe/Mercado Pago/Asaas) sobre a camada de abstração existente
3. FASE 8: RAVI INTELIGÊNCIA (consulta conversacional ao advogado, resumo de andamentos) / RAVI GESTÃO (prazos, agenda)

## Backlog menor (action items iteration_15 — opcionais, sem impacto funcional)
- Semântica do contador de alertas de consumo: hoje conta TODOS os eventos (inbound+outbound, faturáveis ou não) contra o message_limit — confirmar com produto se deve contar só outbound/faturáveis
- Validar unicidade de fatura WhatsApp pendente por (office_id, período) antes de gerar nova
- PATCH de tarifas Meta/RAVI sobrescreve in-place; planos versionam — considerar versionamento explícito de tarifas
- Trocar <input type='date'> nativo por Popover+Calendar shadcn em /admin/whatsapp/pricing e /admin/logs (formato pt-BR)
