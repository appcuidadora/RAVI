import os
import hmac
import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request, Query, Depends, BackgroundTasks
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from database import db
from security import get_current_user, require_permission, office_filter, audit
from whatsapp_meta import (meta_configured, exchange_code_for_token, subscribe_waba,
                           fetch_phone_display)
from pipeline import handle_inbound_message

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["whatsapp"])


@router.get("/whatsapp/status")
async def whatsapp_status(user: dict = Depends(get_current_user)):
    conn = None
    if user.get("office_id"):
        conn = await db.whatsapp_connections.find_one({"office_id": user["office_id"]}, {"_id": 0})
    return {
        "meta_configured": meta_configured(),
        "meta_test_available": bool(os.environ.get("META_TEST_PHONE_NUMBER_ID")),
        "app_id": os.environ.get("META_APP_ID") or None,
        "config_id": os.environ.get("META_CONFIG_ID") or None,
        "graph_version": os.environ.get("META_GRAPH_VERSION", "v25.0"),
        "webhook_url": "/api/webhooks/whatsapp",
        "connection": ({
            "status": conn.get("status"), "display_phone_number": conn.get("display_phone_number"),
            "phone_number_id": conn.get("phone_number_id"),
            "business_account_id": conn.get("business_account_id"),
            "updated_at": conn.get("updated_at"),
        } if conn else None),
    }


class ConnectIn(BaseModel):
    code: str
    waba_id: str
    phone_number_id: str


@router.post("/whatsapp/connect")
async def whatsapp_connect(data: ConnectIn, user: dict = Depends(require_permission("whatsapp"))):
    """Conclusão do Meta Embedded Signup: troca o code por token, inscreve a WABA e salva a conexão."""
    if not meta_configured():
        raise HTTPException(503, "Integração Meta ainda não configurada no servidor")
    try:
        token = await exchange_code_for_token(data.code)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not await subscribe_waba(data.waba_id, token):
        raise HTTPException(400, "Falha ao inscrever a conta do WhatsApp no app")
    display = await fetch_phone_display(data.phone_number_id, token)
    now = datetime.now(timezone.utc).isoformat()
    await db.whatsapp_connections.update_one(
        {"office_id": user["office_id"]},
        {"$set": {"id": uuid.uuid4().hex, "office_id": user["office_id"],
                  "business_account_id": data.waba_id, "phone_number_id": data.phone_number_id,
                  "display_phone_number": display, "status": "connected",
                  "access_token": token, "updated_at": now},
         "$setOnInsert": {"created_at": now}},
        upsert=True)
    await audit(user["office_id"], "whatsapp_connected", actor=user["email"],
                phone_number_id=data.phone_number_id)
    return {"ok": True, "status": "connected", "display_phone_number": display}


@router.post("/whatsapp/disconnect")
async def whatsapp_disconnect(user: dict = Depends(require_permission("whatsapp"))):
    await db.whatsapp_connections.update_one(
        {"office_id": user["office_id"]},
        {"$set": {"status": "disconnected", "access_token": "",
                  "updated_at": datetime.now(timezone.utc).isoformat()}})
    await audit(user["office_id"], "whatsapp_disconnected", actor=user["email"])
    return {"ok": True, "status": "disconnected"}


class ConnectTestIn(BaseModel):
    access_token: str


@router.post("/whatsapp/connect-test")
async def whatsapp_connect_test(data: ConnectTestIn, user: dict = Depends(require_permission("whatsapp"))):
    """Conexão com o número de teste da Meta (painel API Setup). O token temporário (24h)
    é informado manualmente uma única vez e fica apenas no servidor."""
    phone_id = os.environ.get("META_TEST_PHONE_NUMBER_ID")
    waba_id = os.environ.get("META_TEST_WABA_ID")
    if not phone_id or not waba_id:
        raise HTTPException(503, "Número de teste não configurado no servidor")
    if not data.access_token.strip():
        raise HTTPException(400, "Informe o token de acesso temporário")
    display = await fetch_phone_display(phone_id, data.access_token.strip())
    if not display:
        raise HTTPException(400, "Token inválido ou expirado. Gere um novo no painel da Meta (WhatsApp → Configuração da API).")
    if not await subscribe_waba(waba_id, data.access_token.strip()):
        logger.warning("Falha ao inscrever app na WABA de teste — eventos de webhook podem não chegar")
    now = datetime.now(timezone.utc).isoformat()
    await db.whatsapp_connections.update_one(
        {"office_id": user["office_id"]},
        {"$set": {"id": uuid.uuid4().hex, "office_id": user["office_id"],
                  "business_account_id": waba_id, "phone_number_id": phone_id,
                  "display_phone_number": display, "status": "connected",
                  "access_token": data.access_token.strip(), "mode": "test", "updated_at": now},
         "$setOnInsert": {"created_at": now}},
        upsert=True)
    await audit(user["office_id"], "whatsapp_connected_test", actor=user["email"], phone_number_id=phone_id)
    return {"ok": True, "status": "connected", "display_phone_number": display}


# ---------- WEBHOOK PÚBLICO (sem sessão de usuário) ----------

@router.get("/webhooks/whatsapp")
async def webhook_verify(hub_mode: str = Query(None, alias="hub.mode"),
                         hub_verify_token: str = Query(None, alias="hub.verify_token"),
                         hub_challenge: str = Query(None, alias="hub.challenge")):
    verify = os.environ.get("META_WEBHOOK_VERIFY_TOKEN", "")
    if hub_mode == "subscribe" and verify and hmac.compare_digest(hub_verify_token or "", verify):
        return PlainTextResponse(hub_challenge or "", status_code=200)
    raise HTTPException(403, "Falha na verificação do webhook")


@router.post("/webhooks/whatsapp")
async def webhook_receive(request: Request, background_tasks: BackgroundTasks):
    raw = await request.body()
    app_secret = os.environ.get("META_APP_SECRET", "")
    if app_secret:
        sig = request.headers.get("x-hub-signature-256", "")
        expected = "sha256=" + hmac.new(app_secret.encode(), raw, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            raise HTTPException(403, "Assinatura inválida")
    try:
        payload = json.loads(raw)
    except Exception:
        raise HTTPException(400, "Payload inválido")
    logger.info(f"Webhook Meta recebido: {raw[:2000].decode('utf-8', 'replace')}")

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") != "messages":
                continue
            value = change.get("value", {})
            phone_number_id = (value.get("metadata") or {}).get("phone_number_id")
            if not phone_number_id:
                continue
            # phone_number_id identifica o escritório; desconhecido → não associa a nenhum tenant
            connection = await db.whatsapp_connections.find_one(
                {"phone_number_id": phone_number_id, "status": "connected"}, {"_id": 0})
            if not connection:
                logger.warning(f"Webhook: phone_number_id desconhecido {phone_number_id}")
                continue
            for msg in value.get("messages", []):
                # processa em background para dar ack rápido à Meta (transcrição de áudio pode demorar)
                background_tasks.add_task(process_meta_message, connection, msg)
    return {"ok": True}


async def process_meta_message(connection: dict, msg: dict):
    try:
        mtype = msg.get("type")
        if mtype not in ("text", "audio"):
            logger.info(f"Webhook: tipo de mensagem não suportado ({mtype})")
            return
        if await db.messages.find_one({"meta_message_id": msg.get("id")}):
            return  # idempotência: Meta reenvia eventos
        kind = "text"
        if mtype == "text":
            text = (msg.get("text") or {}).get("body", "")
        else:
            media_id = (msg.get("audio") or {}).get("id")
            if not media_id:
                return
            try:
                from whatsapp_meta import get_media_bytes
                from ai import transcribe_audio
                audio_bytes, _mime = await get_media_bytes(media_id, connection.get("access_token", ""))
                text = await transcribe_audio(audio_bytes)
                kind = "audio"
                if not text:
                    return
            except Exception as e:
                logger.error(f"Falha ao transcrever áudio {media_id}: {e}")
                return
        await handle_inbound_message(connection["office_id"], msg.get("from", ""),
                                     text, connection=connection,
                                     meta_message_id=msg.get("id"), kind=kind)
    except Exception as e:
        logger.error(f"Webhook processamento falhou: {e}")
