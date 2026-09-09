import uuid
import secrets
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from database import db
from utils import normalize_phone, parse_cnj
from security import (get_current_user, require_permission, require_socio, office_filter,
                      default_permissions, hash_password, audit, ROLE_LABELS, MODULES)
from pipeline import handle_inbound_message, save_message, create_alert
from whatsapp_meta import graph_send_text

router = APIRouter(prefix="/api", tags=["core"])


def now_iso():
    return datetime.now(timezone.utc).isoformat()


# ---------- DASHBOARD ----------

@router.get("/dashboard/stats")
async def dashboard_stats(user: dict = Depends(require_permission("dashboard"))):
    f = office_filter(user)
    office = await db.offices.find_one({"id": user["office_id"]}, {"_id": 0}) or {}
    open_interventions = await db.alerts.count_documents({**f, "type": "intervention", "status": "open"})
    if office.get("demo_metrics"):
        m = office["demo_metrics"]
        stats = {
            "processos": m["processos"], "clientes": m["clientes"],
            "resolvidos": m["resolvidos"], "precisam_de_voce": open_interventions or m["precisam_de_voce"],
            "tempo_economizado_min": m["tempo_economizado_min"],
        }
    else:
        processos = await db.processes.count_documents(f)
        clientes = await db.clients.count_documents(f)
        resolvidos = await db.audit_logs.count_documents({**f, "event": "auto_resolved"})
        minutes = resolvidos * float(office.get("minutes_per_attendance", 5.4))
        stats = {"processos": processos, "clientes": clientes, "resolvidos": resolvidos,
                 "precisam_de_voce": open_interventions, "tempo_economizado_min": round(minutes)}
    attention = await db.alerts.find({**f, "status": "open", "type": {"$in": ["intervention", "monitoring"]}},
                                     {"_id": 0}).sort("created_at", -1).to_list(8)
    for a in attention:
        if a.get("client_id"):
            c = await db.clients.find_one({"id": a["client_id"]}, {"_id": 0, "name": 1})
            a["client_name"] = c["name"] if c else None
    hourly = await db.messages.aggregate([
        {"$match": f}, {"$group": {"_id": {"$substr": ["$created_at", 0, 13]}, "total": {"$sum": 1}}},
        {"$sort": {"_id": 1}}, {"$limit": 24}
    ]).to_list(24)
    chart = [{"hora": h["_id"][11:] + "h", "atendimentos": h["total"]} for h in hourly]
    if office.get("demo_metrics") or len(chart) < 3:
        chart = [{"hora": f"{h}h", "atendimentos": v} for h, v in
                 [(8, 3), (9, 7), (10, 12), (11, 9), (12, 5), (13, 4), (14, 10), (15, 14), (16, 11), (17, 8), (18, 4)]]
    return {"stats": stats, "attention": attention, "chart": chart,
            "office_name": office.get("name", ""), "tone": office.get("tone", "acolhedor")}


# ---------- CLIENTES ----------

class ClientIn(BaseModel):
    name: str
    phone: str
    email: Optional[str] = ""
    notes: Optional[str] = ""
    responsible_user_id: Optional[str] = None


@router.get("/clients")
async def list_clients(user: dict = Depends(require_permission("clientes"))):
    clients = await db.clients.find(office_filter(user), {"_id": 0}).sort("created_at", -1).to_list(500)
    for c in clients:
        c["processes"] = await db.processes.find(
            {"office_id": user["office_id"], "client_id": c["id"]},
            {"_id": 0, "id": 1, "numero_formatado": 1, "number": 1, "status": 1}).to_list(20)
        if c.get("responsible_user_id"):
            u = await db.users.find_one({"id": c["responsible_user_id"]}, {"_id": 0, "name": 1})
            c["responsible_name"] = u["name"] if u else None
    return clients


@router.post("/clients")
async def create_client(data: ClientIn, user: dict = Depends(require_permission("clientes"))):
    norm = normalize_phone(data.phone)
    if not data.name.strip() or not norm:
        raise HTTPException(400, "Nome e WhatsApp são obrigatórios")
    existing = await db.clients.find_one({"office_id": user["office_id"], "phone_normalized": norm})
    if existing:
        raise HTTPException(400, "Já existe um cliente com este WhatsApp")
    client = {"id": uuid.uuid4().hex, "office_id": user["office_id"], "name": data.name.strip(),
              "phone": data.phone, "phone_normalized": norm, "email": data.email or "",
              "notes": data.notes or "", "status": "ativo",
              "responsible_user_id": data.responsible_user_id or user["id"],
              "created_at": now_iso()}
    await db.clients.insert_one(client)
    await audit(user["office_id"], "client_created", actor=user["email"], client_id=client["id"])
    client.pop("_id", None)
    return client


@router.patch("/clients/{client_id}")
async def update_client(client_id: str, data: ClientIn, user: dict = Depends(require_permission("clientes"))):
    f = {**office_filter(user), "id": client_id}
    updates = {"name": data.name.strip(), "phone": data.phone,
               "phone_normalized": normalize_phone(data.phone), "email": data.email or "",
               "notes": data.notes or ""}
    if data.responsible_user_id:
        updates["responsible_user_id"] = data.responsible_user_id
    res = await db.clients.update_one(f, {"$set": updates})
    if not res.matched_count:
        raise HTTPException(404, "Cliente não encontrado")
    return await db.clients.find_one(f, {"_id": 0})


@router.delete("/clients/{client_id}")
async def delete_client(client_id: str, user: dict = Depends(require_permission("clientes"))):
    res = await db.clients.delete_one({**office_filter(user), "id": client_id})
    if not res.deleted_count:
        raise HTTPException(404, "Cliente não encontrado")
    return {"ok": True}


# ---------- PROCESSOS ----------

class ProcessIn(BaseModel):
    number: str
    client_id: Optional[str] = None
    status: Optional[str] = "Em andamento"
    ultima_movimentacao: Optional[str] = ""
    notes: Optional[str] = ""


@router.get("/processes")
async def list_processes(user: dict = Depends(require_permission("processos"))):
    procs = await db.processes.find(office_filter(user), {"_id": 0}).sort("created_at", -1).to_list(500)
    for p in procs:
        if p.get("client_id"):
            c = await db.clients.find_one({"id": p["client_id"]}, {"_id": 0, "name": 1})
            p["client_name"] = c["name"] if c else None
    return procs


@router.post("/processes")
async def create_process(data: ProcessIn, user: dict = Depends(require_permission("processos"))):
    parsed = parse_cnj(data.number)
    fontes = ["Informação cadastrada pelo advogado"]
    proc = {
        "id": uuid.uuid4().hex, "office_id": user["office_id"],
        "number": data.number.strip(), "client_id": data.client_id,
        "status": data.status or "Em andamento",
        "ultima_movimentacao": data.ultima_movimentacao or "",
        "notes": data.notes or "", "movimentacoes": [], "partes": [],
        "fontes": fontes, "acesso_restrito": False, "created_at": now_iso(),
    }
    if parsed:
        proc.update({k: parsed[k] for k in ("segmento", "tribunal", "unidade_origem", "ano", "numero_formatado")})
        fontes.append("Número CNJ identificado automaticamente")
    if data.ultima_movimentacao:
        proc["movimentacoes"] = [{"data": data.ultima_movimentacao,
                                  "descricao": "Movimentação registrada pelo escritório",
                                  "fonte": "Informação cadastrada pelo advogado"}]
    await db.processes.insert_one(proc)
    await audit(user["office_id"], "process_created", actor=user["email"], process_id=proc["id"])
    proc.pop("_id", None)
    return proc


@router.get("/processes/{process_id}")
async def get_process(process_id: str, user: dict = Depends(require_permission("processos"))):
    proc = await db.processes.find_one({**office_filter(user), "id": process_id}, {"_id": 0})
    if not proc:
        raise HTTPException(404, "Processo não encontrado")
    if proc.get("client_id"):
        proc["client"] = await db.clients.find_one({"id": proc["client_id"]}, {"_id": 0})
    proc["conversations_count"] = await db.conversations.count_documents(
        {"office_id": user["office_id"], "process_id": process_id})
    return proc


# ---------- CONVERSAS ----------

@router.get("/conversations")
async def list_conversations(user: dict = Depends(require_permission("conversas"))):
    convs = await db.conversations.find(office_filter(user), {"_id": 0}).sort("last_message_at", -1).to_list(200)
    for c in convs:
        c["client"] = None
        if c.get("client_id"):
            c["client"] = await db.clients.find_one({"id": c["client_id"]}, {"_id": 0, "id": 1, "name": 1, "phone": 1})
        if c.get("assigned_user_id"):
            u = await db.users.find_one({"id": c["assigned_user_id"]}, {"_id": 0, "name": 1})
            c["assigned_user_name"] = u["name"] if u else None
    return convs


@router.get("/conversations/{conv_id}")
async def get_conversation(conv_id: str, user: dict = Depends(require_permission("conversas"))):
    conv = await db.conversations.find_one({**office_filter(user), "id": conv_id}, {"_id": 0})
    if not conv:
        raise HTTPException(404, "Conversa não encontrada")
    conv["messages"] = await db.messages.find({"conversation_id": conv_id}, {"_id": 0}).sort("created_at", 1).to_list(200)
    conv["client"] = None
    if conv.get("client_id"):
        conv["client"] = await db.clients.find_one({"id": conv["client_id"]}, {"_id": 0})
    conv["process"] = None
    if conv.get("process_id"):
        conv["process"] = await db.processes.find_one({"id": conv["process_id"]}, {"_id": 0})
    return conv


class TextIn(BaseModel):
    text: str


@router.post("/conversations/{conv_id}/client-message")
async def simulate_client_message(conv_id: str, data: TextIn, user: dict = Depends(require_permission("conversas"))):
    """Simula uma mensagem recebida do cliente (demo/teste do motor RAVI sem depender da Meta)."""
    conv = await db.conversations.find_one({**office_filter(user), "id": conv_id}, {"_id": 0})
    if not conv:
        raise HTTPException(404, "Conversa não encontrada")
    connection = await db.whatsapp_connections.find_one({"office_id": user["office_id"]}, {"_id": 0})
    return await handle_inbound_message(user["office_id"], conv["phone_normalized"], data.text,
                                        connection=connection, source="simulation")


@router.post("/conversations/{conv_id}/send")
async def send_human_message(conv_id: str, data: TextIn, user: dict = Depends(require_permission("conversas"))):
    conv = await db.conversations.find_one({**office_filter(user), "id": conv_id}, {"_id": 0})
    if not conv:
        raise HTTPException(404, "Conversa não encontrada")
    delivered = False
    connection = await db.whatsapp_connections.find_one(
        {"office_id": user["office_id"], "status": "connected"}, {"_id": 0})
    if connection and connection.get("access_token"):
        try:
            await graph_send_text(connection, conv["phone_normalized"], data.text)
            delivered = True
        except Exception:
            delivered = False
    msg = await save_message(user["office_id"], conv_id, "user", data.text,
                             sender_user_id=user["id"], delivered=delivered)
    msg.pop("_id", None)
    await audit(user["office_id"], "human_reply", actor=user["email"],
                conversation_id=conv_id, delivered=delivered)
    return msg


@router.post("/conversations/{conv_id}/pause-ravi")
async def pause_ravi(conv_id: str, user: dict = Depends(require_permission("conversas"))):
    await db.conversations.update_one({**office_filter(user), "id": conv_id},
                                      {"$set": {"ai_enabled": False}})
    await audit(user["office_id"], "ravi_paused", actor=user["email"], conversation_id=conv_id)
    return {"ok": True, "ai_enabled": False}


@router.post("/conversations/{conv_id}/takeover")
async def takeover(conv_id: str, user: dict = Depends(require_permission("conversas"))):
    await db.conversations.update_one({**office_filter(user), "id": conv_id},
                                      {"$set": {"human_control": True, "ai_enabled": False,
                                                "assigned_user_id": user["id"], "status": "active"}})
    await audit(user["office_id"], "human_takeover", actor=user["email"], conversation_id=conv_id)
    return {"ok": True, "human_control": True}


@router.post("/conversations/{conv_id}/resume-ravi")
async def resume_ravi(conv_id: str, user: dict = Depends(require_permission("conversas"))):
    await db.conversations.update_one({**office_filter(user), "id": conv_id},
                                      {"$set": {"human_control": False, "ai_enabled": True,
                                                "assigned_user_id": None, "risk_level": "green"}})
    await audit(user["office_id"], "ravi_resumed", actor=user["email"], conversation_id=conv_id)
    return {"ok": True, "ai_enabled": True, "human_control": False}


class LinkClientIn(BaseModel):
    client_id: Optional[str] = None
    new_client_name: Optional[str] = None


@router.post("/conversations/{conv_id}/link-client")
async def link_client(conv_id: str, data: LinkClientIn, user: dict = Depends(require_permission("conversas"))):
    conv = await db.conversations.find_one({**office_filter(user), "id": conv_id}, {"_id": 0})
    if not conv:
        raise HTTPException(404, "Conversa não encontrada")
    client_id = data.client_id
    if not client_id:
        if not data.new_client_name:
            raise HTTPException(400, "Informe o cliente")
        client_id = uuid.uuid4().hex
        await db.clients.insert_one({
            "id": client_id, "office_id": user["office_id"], "name": data.new_client_name.strip(),
            "phone": "+" + conv["phone_normalized"], "phone_normalized": conv["phone_normalized"],
            "email": "", "notes": "Criado a partir de conversa não identificada", "status": "ativo",
            "responsible_user_id": user["id"], "created_at": now_iso()})
    proc = await db.processes.find_one({"office_id": user["office_id"], "client_id": client_id}, {"_id": 0})
    await db.conversations.update_one({"id": conv_id},
                                      {"$set": {"client_id": client_id, "status": "active",
                                                "process_id": proc["id"] if proc else None}})
    await audit(user["office_id"], "client_linked", actor=user["email"],
                conversation_id=conv_id, client_id=client_id)
    return {"ok": True, "client_id": client_id}


# ---------- ALERTAS ----------

@router.get("/alerts")
async def list_alerts(status: str = "open", user: dict = Depends(require_permission("alertas"))):
    q = office_filter(user)
    if status != "all":
        q["status"] = status
    alerts = await db.alerts.find(q, {"_id": 0}).sort("created_at", -1).to_list(200)
    for a in alerts:
        a["client_name"] = None
        if a.get("client_id"):
            c = await db.clients.find_one({"id": a["client_id"]}, {"_id": 0, "name": 1})
            a["client_name"] = c["name"] if c else None
    return alerts


@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: str, user: dict = Depends(require_permission("alertas"))):
    res = await db.alerts.update_one({**office_filter(user), "id": alert_id},
                                     {"$set": {"status": "resolved", "resolved_by": user["email"],
                                               "resolved_at": now_iso()}})
    if not res.matched_count:
        raise HTTPException(404, "Alerta não encontrado")
    return {"ok": True}


# ---------- EQUIPE ----------

class MemberIn(BaseModel):
    name: str
    email: str
    role: str
    permissions: Optional[dict] = None


class MemberPatch(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    permissions: Optional[dict] = None


@router.get("/team")
async def list_team(user: dict = Depends(require_permission("equipe"))):
    members = await db.users.find(office_filter(user), {"_id": 0, "password_hash": 0}).to_list(100)
    for m in members:
        m["role_label"] = ROLE_LABELS.get(m["role"], m["role"])
    return {"members": members, "modules": MODULES, "roles": ROLE_LABELS}


@router.post("/team")
async def add_member(data: MemberIn, user: dict = Depends(require_socio)):
    email = data.email.lower().strip()
    if data.role not in ROLE_LABELS:
        raise HTTPException(400, "Função inválida")
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "Este e-mail já está cadastrado")
    temp_password = "Ravi-" + secrets.token_urlsafe(6)
    perms = default_permissions(data.role)
    if data.permissions:
        perms.update({k: bool(v) for k, v in data.permissions.items() if k in MODULES})
    member = {"id": uuid.uuid4().hex, "office_id": user["office_id"], "name": data.name.strip(),
              "last_name": "", "email": email, "password_hash": hash_password(temp_password),
              "role": data.role, "permissions": perms, "active": True,
              "onboarding_completed": True, "token_version": 0, "created_at": now_iso()}
    await db.users.insert_one(member)
    await audit(user["office_id"], "member_added", actor=user["email"], member_email=email)
    member.pop("_id", None)
    member.pop("password_hash", None)
    member["temp_password"] = temp_password
    return member


@router.patch("/team/{member_id}")
async def update_member(member_id: str, data: MemberPatch, user: dict = Depends(require_socio)):
    f = {**office_filter(user), "id": member_id}
    updates = {}
    if data.name:
        updates["name"] = data.name.strip()
    if data.role and data.role in ROLE_LABELS:
        updates["role"] = data.role
    if data.permissions:
        member = await db.users.find_one(f, {"_id": 0})
        perms = member.get("permissions") or default_permissions(member["role"])
        perms.update({k: bool(v) for k, v in data.permissions.items() if k in MODULES})
        updates["permissions"] = perms
    if not updates:
        raise HTTPException(400, "Nada para atualizar")
    await db.users.update_one(f, {"$set": updates})
    await audit(user["office_id"], "member_updated", actor=user["email"], member_id=member_id)
    return await db.users.find_one(f, {"_id": 0, "password_hash": 0})


@router.post("/team/{member_id}/toggle-active")
async def toggle_member(member_id: str, user: dict = Depends(require_socio)):
    if member_id == user["id"]:
        raise HTTPException(400, "Você não pode desativar a si mesmo")
    f = {**office_filter(user), "id": member_id}
    member = await db.users.find_one(f, {"_id": 0})
    if not member:
        raise HTTPException(404, "Membro não encontrado")
    new_state = not member.get("active", True)
    await db.users.update_one(f, {"$set": {"active": new_state}, "$inc": {"token_version": 1}})
    await audit(user["office_id"], "member_toggled", actor=user["email"],
                member_id=member_id, active=new_state)
    return {"ok": True, "active": new_state}


# ---------- CONFIGURAÇÕES ----------

class OfficeSettingsIn(BaseModel):
    name: Optional[str] = None
    tone: Optional[str] = None
    minutes_per_attendance: Optional[float] = None
    welcome_message: Optional[str] = None


@router.get("/office/settings")
async def get_settings(user: dict = Depends(require_permission("configuracoes"))):
    office = await db.offices.find_one({"id": user["office_id"]}, {"_id": 0, "demo_metrics": 0})
    return office


@router.patch("/office/settings")
async def update_settings(data: OfficeSettingsIn, user: dict = Depends(require_socio)):
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    if updates:
        await db.offices.update_one({"id": user["office_id"]}, {"$set": updates})
    return await db.offices.find_one({"id": user["office_id"]}, {"_id": 0, "demo_metrics": 0})


# ---------- AUDITORIA ----------

@router.get("/audit")
async def list_audit(user: dict = Depends(require_permission("configuracoes"))):
    return await db.audit_logs.find(office_filter(user), {"_id": 0}).sort("created_at", -1).to_list(100)
