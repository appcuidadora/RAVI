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

## Estado do MVP (09/09/2026)
- 100% dos testes passando (backend 45/45: auth, CRUD, permissões, isolamento, webhook Meta, idempotência, novas features) — /app/test_reports/iteration_1..5.json
- WhatsApp conectado com número de teste da Meta (+1 555-665-3479, phone_number_id 1266842309849495); fluxo real confirmado pelo usuário (inbound + outbound)
- Webhook público verificado pela Meta; app RAVI_API inscrito na WABA (subscribe_waba automático em novas conexões)
- Feature 1: cadastro inline de cliente no processo + upload de PDF (object storage Emergent + extração pypdf) — IA lê o documento e responde com o conteúdo (validado: audiência 20/10 respondida a partir do PDF)
- Feature 2: valor da causa + forma de pagamento + cobranças no processo; cron diário `.emergent/crons.yml` (12:00 UTC = 9h BRT) → POST /api/cron/billing-reminders (Bearer WEBHOOK_CRON_SECRET, idempotente por run_id) envia lembretes 5 dias antes (janela com retry) e no dia via WhatsApp; flag só marcada com entrega confirmada
- Feature 3: memória de conversa com as últimas 50 mensagens no contexto da IA
- Feature 4 (áudio): webhook aceita type=audio → baixa mídia via Graph API → ffmpeg ogg→mp3 → Whisper whisper-1 (pt) → pipeline normal; msg salva com kind='audio' e badge "áudio transcrito" na UI; processamento do webhook em BackgroundTasks (ack rápido à Meta); demais tipos (imagem/vídeo/doc/sticker) são ignorados com log
- Regressão: `pytest /app/backend/tests/ -n0`

## Pendências para produção
- P0: credenciais da Meta App (META_APP_ID, META_APP_SECRET, META_CONFIG_ID) para ativar Embedded Signup real; App Review Meta (whatsapp_business_management/messaging); registrar webhook na Meta com a URL pública
- P1: criptografia do access_token da Meta em repouso (KMS); migrar startup/shutdown para lifespan; timeout explícito no LLM; CORS com lista explícita em produção
- P2: integrações de tribunais (fontes públicas/autenticadas), importação de PDF de processos, RAVI Inteligência (consulta conversacional ao advogado), RAVI Gestão (prazos, agenda, financeiro)

## Próximas tarefas
1. Usuário fornece credenciais Meta → ativar conexão WhatsApp real
2. Testar envio/recebimento real Meta→webhook→RAVI→Meta
3. Importação de processo por PDF
