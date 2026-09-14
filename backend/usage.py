import uuid
import logging
from datetime import datetime, timezone
from database import db
from security import audit

logger = logging.getLogger(__name__)

CATEGORIES = ["SERVICE", "UTILITY", "MARKETING", "AUTHENTICATION", "AUTHENTICATION_INTERNATIONAL", "OTHER"]


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def current_period() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


async def get_customer_rate(office_id: str, category: str) -> float:
    """Preço RAVI vigente para o plano do escritório + categoria (versionado por data)."""
    office = await db.offices.find_one({"id": office_id}, {"_id": 0, "plan_id": 1})
    plan_id = (office or {}).get("plan_id")
    if not plan_id:
        return 0.0
    today = now_iso()[:10]
    rate = await db.whatsapp_customer_rates.find_one(
        {"plan_id": plan_id, "category": category, "status": "ativo", "effective_from": {"$lte": today}},
        {"_id": 0}, sort=[("effective_from", -1)])
    return float(rate["customer_rate"]) if rate else 0.0


async def get_meta_rate(category: str, country: str = "BR") -> float:
    """Custo de referência Meta vigente (versionado por data)."""
    today = now_iso()[:10]
    rate = await db.whatsapp_pricing.find_one(
        {"country": country, "category": category, "status": "ativo", "effective_from": {"$lte": today}},
        {"_id": 0}, sort=[("effective_from", -1)])
    return float(rate["meta_rate"]) if rate else 0.0


async def record_usage_event(office_id: str, direction: str, category: str, billable: bool,
                             connection_id: str = None, conversation_id: str = None,
                             message_id: str = None, meta_message_id: str = None,
                             message_type: str = "text") -> dict:
    """Registra cada evento de consumo individualmente, com preços CONGELADOS no momento
    do evento (histórico de preços nunca é alterado retroativamente)."""
    customer_rate = await get_customer_rate(office_id, category)
    meta_rate = await get_meta_rate(category)
    event = {
        "id": uuid.uuid4().hex, "office_id": office_id, "whatsapp_connection_id": connection_id,
        "conversation_id": conversation_id, "message_id": message_id, "meta_message_id": meta_message_id,
        "direction": direction, "message_type": message_type,
        "billing_category": category, "billable": billable,
        "meta_cost": round(meta_rate, 6) if billable else 0.0,
        "ravi_price": round(customer_rate, 6) if billable else 0.0,
        "currency": "BRL", "exchange_rate": None,
        "billing_period": current_period(), "invoice_id": None, "created_at": now_iso(),
    }
    await db.whatsapp_usage_events.insert_one(event)
    await check_consumption_alerts(office_id)
    event.pop("_id", None)
    return event


async def check_consumption_alerts(office_id: str):
    """Alertas por percentual do limite de mensagens do plano (configurável, nunca bloqueia)."""
    office = await db.offices.find_one({"id": office_id}, {"_id": 0, "plan_id": 1})
    if not office or not office.get("plan_id"):
        return
    plan = await db.plans.find_one({"id": office["plan_id"]}, {"_id": 0})
    limit = (plan or {}).get("message_limit")
    if not limit:
        return
    period = current_period()
    used = await db.whatsapp_usage_events.count_documents({"office_id": office_id, "billing_period": period})
    doc = await db.platform_settings.find_one({"id": "global"}, {"_id": 0})
    pcts = (doc or {}).get("consumption_alert_pcts") or [70, 80, 90]
    for pct in pcts:
        if used >= limit * pct / 100:
            mark = await db.usage_alert_marks.find_one({"office_id": office_id, "period": period, "pct": pct})
            if not mark:
                await db.usage_alert_marks.insert_one({"office_id": office_id, "period": period, "pct": pct,
                                                       "created_at": now_iso()})
                await db.alerts.insert_one({
                    "id": uuid.uuid4().hex, "office_id": office_id, "type": "monitoring",
                    "title": f"Consumo WhatsApp atingiu {pct}% do plano",
                    "reason": f"{used} de {limit} mensagens no período {period}. Nenhum bloqueio foi aplicado.",
                    "status": "open", "conversation_id": None, "client_id": None, "created_at": now_iso()})
                await audit(office_id, "consumption_alert", pct=pct, used=used, limit=limit)
