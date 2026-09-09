# RAVI — Notas de teste de autenticação

- Credenciais em /app/memory/test_credentials.md
- Cookies httpOnly (access_token 15min + refresh_token 7d); o frontend usa axios withCredentials e interceptor de refresh.
- Proteção brute-force: 5 tentativas / 15 min por IP+email.
- Reset de senha: POST /api/auth/forgot-password (resposta genérica) → e-mail via proxy Emergent → POST /api/auth/reset-password com token de 1 uso / 1h, que incrementa token_version e limpa lockouts.
- Cadastro: POST /api/auth/register cria usuário sem escritório → frontend redireciona para /onboarding → POST /api/auth/onboarding/complete cria o escritório e marca onboarding_completed=true.
- Guards: RequireAuth preserva rota (location.state.from); /onboarding nunca é fallback global.
- Webhook público: GET /api/webhooks/whatsapp (verify token) e POST /api/webhooks/whatsapp (assinatura X-Hub-Signature-256 quando META_APP_SECRET configurado).
