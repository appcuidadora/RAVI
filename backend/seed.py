import os
import uuid
import logging
from datetime import datetime, timezone
from database import db
from security import hash_password, default_permissions
from utils import normalize_phone, parse_cnj

logger = logging.getLogger(__name__)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


async def create_indexes():
    await db.users.create_index("email", unique=True)
    await db.users.create_index("office_id")
    await db.clients.create_index([("office_id", 1), ("phone_normalized", 1)])
    await db.processes.create_index("office_id")
    await db.conversations.create_index([("office_id", 1), ("phone_normalized", 1)])
    await db.messages.create_index("conversation_id")
    await db.messages.create_index("meta_message_id")
    await db.alerts.create_index("office_id")
    await db.audit_logs.create_index("office_id")
    await db.whatsapp_connections.create_index("office_id", unique=True)
    await db.whatsapp_connections.create_index("phone_number_id")
    await db.password_reset_tokens.create_index("token_hash", unique=True)
    await db.password_reset_tokens.create_index("expires_at", expireAfterSeconds=0)
    await db.login_attempts.create_index("identifier")
    await db.login_attempts.create_index("email")
    await db.password_reset_requests.create_index("email")
    await db.password_reset_requests.create_index("created_at", expireAfterSeconds=900)
    await db.processes.create_index([("office_id", 1), ("client_id", 1)])
    await db.conversations.create_index([("office_id", 1), ("last_message_at", -1)])
    await db.messages.create_index([("conversation_id", 1), ("created_at", 1)])
    await db.alerts.create_index([("office_id", 1), ("status", 1)])
    await db.audit_logs.create_index([("office_id", 1), ("created_at", -1)])
    await db.admin_logs.create_index([("created_at", -1)])
    await db.charges.create_index([("office_id", 1), ("status", 1)])
    await db.subscriptions.create_index("office_id")
    await db.tickets.create_index("office_id")
    await db.whatsapp_usage_events.create_index([("office_id", 1), ("billing_period", 1)])
    await db.whatsapp_usage_events.create_index("invoice_id")
    await db.whatsapp_invoices.create_index([("office_id", 1), ("issue_date", -1)])
    await db.plans.create_index("name")


async def seed_platform():
    """SUPER_ADMIN + planos padrão + campos comerciais dos escritórios."""
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@ravi.app").lower()
    if not await db.admin_users.find_one({"email": admin_email}):
        await db.admin_users.insert_one({
            "id": uuid.uuid4().hex, "name": "RAVI Admin", "email": admin_email,
            "password_hash": hash_password(os.environ["ADMIN_PASSWORD"]),
            "role": "SUPER_ADMIN", "active": True, "totp_secret": None, "created_at": now_iso(),
        })
        logger.info("SUPER_ADMIN criado")
    default_plans = [
        {"name": "STARTER", "process_limit": 25, "user_limit": 3, "message_limit": 2000, "ai_quota": 2000},
        {"name": "PROFESSIONAL", "process_limit": 100, "user_limit": 10, "message_limit": 10000, "ai_quota": 10000},
        {"name": "OFFICE", "process_limit": 500, "user_limit": 30, "message_limit": 50000, "ai_quota": 50000},
        {"name": "ENTERPRISE", "process_limit": None, "user_limit": None, "message_limit": None, "ai_quota": None},
    ]
    for p in default_plans:
        if not await db.plans.find_one({"name": p["name"]}):
            await db.plans.insert_one({"id": uuid.uuid4().hex, **p, "features": "",
                                       "price_monthly": 0, "price_yearly": 0, "overage_pct": 10,
                                       "status": "ativo", "created_at": now_iso()})
    starter = await db.plans.find_one({"name": "STARTER"}, {"_id": 0})
    await db.offices.update_many(
        {"status": {"$exists": False}},
        {"$set": {"status": "active", "plan_id": starter["id"] if starter else None,
                  "valor_mensal": 0, "ciclo": "mensal", "observacoes": ""}})
    await db.offices.update_many(
        {"plan_id": {"$exists": False}},
        {"$set": {"plan_id": starter["id"] if starter else None}})
    office_plan = await db.plans.find_one({"name": "OFFICE"}, {"_id": 0})
    if office_plan:
        await db.offices.update_one({"name": "Silva Advocacia"}, {"$set": {"plan_id": office_plan["id"]}})


async def seed_demo():
    """Dados demo: Dr. Carlos Mendes / Silva Advocacia / Carlos Eduardo / processo 1001234-56.2025.8.26.0100."""
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@ravi.app").lower()
    admin_password = os.environ["ADMIN_PASSWORD"]
    existing = await db.users.find_one({"email": admin_email})
    if existing and not existing.get("demo_seeded"):
        return
    if existing:
        if not __import__("security").verify_password(admin_password, existing["password_hash"]):
            await db.users.update_one({"email": admin_email},
                                      {"$set": {"password_hash": hash_password(admin_password)}})
        return

    office_id = uuid.uuid4().hex
    user_id = uuid.uuid4().hex
    await db.offices.insert_one({
        "id": office_id, "name": "Silva Advocacia", "tone": "acolhedor",
        "minutes_per_attendance": 5.4, "welcome_message": "", "onboarding_completed": True,
        "demo_metrics": {"processos": 50, "clientes": 63, "resolvidos": 41,
                         "precisam_de_voce": 3, "tempo_economizado_min": 222},
        "created_at": now_iso(),
    })
    await db.users.insert_one({
        "id": user_id, "office_id": office_id, "name": "Carlos", "last_name": "Mendes",
        "email": admin_email, "password_hash": hash_password(admin_password),
        "role": "SOCIO_ADMIN", "permissions": default_permissions("SOCIO_ADMIN"),
        "active": True, "onboarding_completed": True, "token_version": 0,
        "demo_seeded": True, "created_at": now_iso(),
    })

    client_id = uuid.uuid4().hex
    phone = "+55 11 98765-4321"
    await db.clients.insert_one({
        "id": client_id, "office_id": office_id, "name": "Carlos Eduardo",
        "phone": phone, "phone_normalized": normalize_phone(phone),
        "email": "carlos.eduardo@email.com", "notes": "", "status": "ativo",
        "responsible_user_id": user_id, "created_at": now_iso(),
    })

    number = "1001234-56.2025.8.26.0100"
    parsed = parse_cnj(number) or {}
    process_id = uuid.uuid4().hex
    await db.processes.insert_one({
        "id": process_id, "office_id": office_id, "number": number,
        "numero_formatado": parsed.get("numero_formatado", number),
        "segmento": parsed.get("segmento"), "tribunal": parsed.get("tribunal"),
        "unidade_origem": parsed.get("unidade_origem"), "ano": parsed.get("ano"),
        "client_id": client_id, "status": "Aguardando decisão",
        "ultima_movimentacao": "18/08/2026",
        "movimentacoes": [
            {"data": "02/06/2026", "descricao": "Conclusos para decisão", "fonte": "Fonte processual integrada"},
            {"data": "18/08/2026", "descricao": "Juntada de petição de manifestação", "fonte": "Documento fornecido pelo escritório"},
        ],
        "partes": ["Carlos Eduardo (Autor)", "Instituto de Previdência (Réu)"],
        "fontes": ["Fonte processual integrada", "Documento fornecido pelo escritório",
                   "Histórico de conversas", "Informação cadastrada pelo advogado"],
        "acesso_restrito": False, "created_at": now_iso(),
    })

    conv_id = uuid.uuid4().hex
    base = datetime.now(timezone.utc)
    await db.conversations.insert_one({
        "id": conv_id, "office_id": office_id, "phone_normalized": normalize_phone(phone),
        "client_id": client_id, "process_id": process_id, "status": "active",
        "risk_level": "red", "ai_enabled": True, "human_control": False,
        "assigned_user_id": None, "created_at": now_iso(), "last_message_at": now_iso(),
        "last_message_text": "Essa é uma questão que precisa ser analisada pelo advogado responsável...",
    })
    msgs = [
        ("client", "Boa tarde, doutor. Teve alguma novidade?", None, -40),
        ("ravi", "Olá, Carlos! Consultei as informações disponíveis do seu processo. No momento, ele continua aguardando decisão. A última movimentação registrada foi em 18/08. Até agora não identifiquei nenhuma nova providência que você precise tomar.", "green", -39),
        ("client", "Mas pode fazer alguma coisa para acelerar?", None, -12),
        ("ravi", "Essa é uma questão que precisa ser analisada pelo advogado responsável pelo processo. Vou encaminhar sua mensagem para ele.", "red", -11),
    ]
    from datetime import timedelta
    for sender, text, risk, mins in msgs:
        await db.messages.insert_one({
            "id": uuid.uuid4().hex, "office_id": office_id, "conversation_id": conv_id,
            "sender": sender, "sender_user_id": None, "text": text, "risk_level": risk,
            "meta_message_id": None, "delivered": True,
            "created_at": (base + timedelta(minutes=mins)).isoformat(),
        })
    await db.alerts.insert_one({
        "id": uuid.uuid4().hex, "office_id": office_id, "type": "intervention",
        "title": "Intervenção necessária", "reason": "Orientação jurídica/estratégica.",
        "status": "open", "conversation_id": conv_id, "client_id": client_id,
        "created_at": now_iso(),
    })
    await db.audit_logs.insert_one({
        "id": uuid.uuid4().hex, "office_id": office_id, "event": "demo_seeded",
        "actor": "system", "details": {"process": number}, "created_at": now_iso(),
    })
    logger.info("Dados demo do RAVI criados (Silva Advocacia)")
