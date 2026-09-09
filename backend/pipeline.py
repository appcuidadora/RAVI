import logging
import uuid
from datetime import datetime, timezone
from database import db
from utils import normalize_phone
from security import audit
from ai import classify_message, generate_ravi_reply, ESCALATION_REPLY
from whatsapp_meta import graph_send_text

logger = logging.getLogger(__name__)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def save_message(office_id: str, conversation_id: str, sender: str, text: str,
                       risk_level: str = None, sender_user_id: str = None,
                       meta_message_id: str = None, delivered: bool = False) -> dict:
    msg = {
        "id": uuid.uuid4().hex, "office_id": office_id, "conversation_id": conversation_id,
        "sender": sender, "sender_user_id": sender_user_id, "text": text,
        "risk_level": risk_level, "meta_message_id": meta_message_id,
        "delivered": delivered, "created_at": now_iso(),
    }
    await db.messages.insert_one(msg)
    await db.conversations.update_one({"id": conversation_id},
                                      {"$set": {"last_message_at": msg["created_at"],
                                                "last_message_text": text[:120]}})
    return msg


async def create_alert(office_id: str, alert_type: str, title: str, reason: str = "",
                       conversation_id: str = None, client_id: str = None) -> dict:
    alert = {
        "id": uuid.uuid4().hex, "office_id": office_id, "type": alert_type,
        "title": title, "reason": reason, "status": "open",
        "conversation_id": conversation_id, "client_id": client_id,
        "created_at": now_iso(),
    }
    await db.alerts.insert_one(alert)
    return alert


async def handle_inbound_message(office_id: str, phone: str, text: str,
                                 connection: dict = None, source: str = "whatsapp") -> dict:
    """Pipeline central: webhook da Meta e simulação passam por aqui.
    Meta → webhook → phone_number_id → WhatsAppConnection → office_id → cliente → conversa → RAVI."""
    norm = normalize_phone(phone)
    client = await db.clients.find_one({"office_id": office_id, "phone_normalized": norm}, {"_id": 0})
    office = await db.offices.find_one({"id": office_id}, {"_id": 0})

    conv = await db.conversations.find_one(
        {"office_id": office_id, "phone_normalized": norm, "status": {"$ne": "archived"}}, {"_id": 0})
    if not conv:
        conv = {
            "id": uuid.uuid4().hex, "office_id": office_id, "phone_normalized": norm,
            "client_id": client["id"] if client else None,
            "process_id": client.get("process_ids", [None])[0] if client else None,
            "status": "active" if client else "unidentified",
            "risk_level": "green", "ai_enabled": True, "human_control": False,
            "assigned_user_id": None, "created_at": now_iso(), "last_message_at": now_iso(),
        }
        await db.conversations.insert_one(conv)
        if not client:
            await create_alert(office_id, "intervention", "Novo contato no WhatsApp",
                               f"Número +{norm} não está cadastrado como cliente.",
                               conversation_id=conv["id"])
            await audit(office_id, "unidentified_contact", conversation_id=conv["id"], phone=norm)

    await save_message(office_id, conv["id"], "client", text)
    await audit(office_id, "message_received", conversation_id=conv["id"],
                client_id=client["id"] if client else None, text=text[:200])

    if not client:
        return {"conversation_id": conv["id"], "action": "awaiting_client_link"}

    if conv.get("human_control") or not conv.get("ai_enabled", True):
        await audit(office_id, "ai_paused_skip", conversation_id=conv["id"], client_id=client["id"])
        return {"conversation_id": conv["id"], "action": "human_in_control"}

    process = None
    if conv.get("process_id"):
        process = await db.processes.find_one({"id": conv["process_id"], "office_id": office_id}, {"_id": 0})
    if not process:
        process = await db.processes.find_one({"office_id": office_id, "client_id": client["id"]}, {"_id": 0})

    level, reason = classify_message(text)

    if level == "red":
        reply = ESCALATION_REPLY
        await create_alert(office_id, "intervention", "Intervenção necessária", reason,
                           conversation_id=conv["id"], client_id=client["id"])
        await db.conversations.update_one({"id": conv["id"]}, {"$set": {"risk_level": "red"}})
    else:
        history = await db.messages.find({"conversation_id": conv["id"]}, {"_id": 0}).sort("created_at", -1).to_list(6)
        reply = await generate_ravi_reply(office, client, process, history, text)
        if level == "yellow":
            await create_alert(office_id, "monitoring", "Acompanhamento", reason,
                               conversation_id=conv["id"], client_id=client["id"])
            await db.conversations.update_one({"id": conv["id"]}, {"$set": {"risk_level": "yellow"}})
        else:
            await audit(office_id, "auto_resolved", conversation_id=conv["id"],
                        client_id=client["id"], process_id=process["id"] if process else None)

    delivered = False
    meta_id = None
    if connection and connection.get("status") == "connected" and connection.get("access_token"):
        try:
            resp = await graph_send_text(connection, norm, reply)
            delivered = True
            meta_id = (resp.get("messages") or [{}])[0].get("id")
        except Exception as e:
            logger.error(f"Falha ao enviar WhatsApp: {e}")

    await save_message(office_id, conv["id"], "ravi", reply, risk_level=level,
                       meta_message_id=meta_id, delivered=delivered)
    await audit(office_id, "ravi_reply", conversation_id=conv["id"], client_id=client["id"],
                risk_level=level, reason=reason, delivered=delivered)
    return {"conversation_id": conv["id"], "action": "ravi_replied", "risk_level": level, "reply": reply}
