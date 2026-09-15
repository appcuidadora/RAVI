import os
import logging
import uuid
import jwt
import httpx
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Request, Response, Depends
from pydantic import BaseModel, EmailStr
from typing import Optional
from database import db
from security import hash_password, verify_password, get_jwt_secret, audit
from usage import record_usage_event, CATEGORIES, current_period

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])

ADMIN_ROLES = ["SUPER_ADMIN", "ADMIN_FINANCEIRO", "ADMIN_SUPORTE", "ADMIN_OPERACOES",
               "ADMIN_COMERCIAL", "ADMIN_TECNOLOGIA", "ANALISTA"]

SECRET_KEYS = ["META_APP_ID", "META_APP_SECRET", "META_CONFIG_ID", "META_TEST_TOKEN"]


def now():
    return datetime.now(timezone.utc)


def now_iso():
    return now().isoformat()


async def admin_log(admin: dict, action: str, office_id: str = None, motivo: str = None, **details):
    await db.admin_logs.insert_one({
        "id": uuid.uuid4().hex, "admin_email": admin["email"], "admin_role": admin.get("role"),
        "action": action, "office_id": office_id, "motivo": motivo,
        "details": details, "created_at": now_iso(),
    })


def create_admin_token(admin: dict) -> str:
    payload = {"sub": admin["id"], "email": admin["email"], "type": "admin",
               "role": admin["role"], "exp": now() + timedelta(hours=8)}
    return jwt.encode(payload, get_jwt_secret(), algorithm="HS256")


async def get_current_admin(request: Request) -> dict:
    token = request.cookies.get("admin_access_token")
    auth = request.headers.get("Authorization", "")
    if not token and auth.startswith("Bearer "):
        token = auth[7:]
    if not token:
        raise HTTPException(401, "Não autenticado")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=["HS256"])
        if payload.get("type") != "admin":
            raise HTTPException(401, "Token inválido")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Sessão expirada")
    admin = await db.admin_users.find_one({"id": payload["sub"]}, {"_id": 0})
    if not admin:
        raise HTTPException(401, "Administrador não encontrado")
    if not admin.get("active", True):
        raise HTTPException(403, "Administrador desativado")
    return admin


def require_admin_roles(*roles):
    """RBAC do RAVI ADMIN: SUPER_ADMIN sempre passa; demais perfis só acessam funções listadas."""
    async def checker(admin: dict = Depends(get_current_admin)):
        if admin["role"] != "SUPER_ADMIN" and admin["role"] not in roles:
            raise HTTPException(403, "Perfil administrativo sem acesso a esta função")
        return admin
    return checker


async def get_platform_secrets() -> dict:
    doc = await db.platform_settings.find_one({"id": "global"}, {"_id": 0})
    return (doc or {}).get("secrets") or {}


# ---------- AUTH ----------

class AdminLoginIn(BaseModel):
    email: str
    password: str


@router.post("/auth/login")
async def admin_login(data: AdminLoginIn, request: Request, response: Response):
    email = data.email.lower().strip()
    ip = request.client.host if request.client else "unknown"
    identifier = f"admin:{ip}:{email}"
    attempts = await db.login_attempts.count_documents({
        "identifier": identifier,
        "created_at": {"$gt": (now() - timedelta(minutes=15)).isoformat()}})
    if attempts >= 5:
        raise HTTPException(429, "Muitas tentativas. Aguarde 15 minutos.")
    admin = await db.admin_users.find_one({"email": email}, {"_id": 0})
    if not admin or not verify_password(data.password, admin.get("password_hash", "")):
        await db.login_attempts.insert_one({"identifier": identifier, "email": email, "created_at": now_iso()})
        raise HTTPException(401, "E-mail ou senha incorretos")
    if not admin.get("active", True):
        raise HTTPException(403, "Administrador desativado")
    await db.login_attempts.delete_many({"identifier": identifier})
    response.set_cookie("admin_access_token", create_admin_token(admin),
                        httponly=True, secure=True, samesite="none", max_age=28800, path="/")
    await admin_log(admin, "admin_login")
    return {"admin": {"id": admin["id"], "name": admin["name"], "email": admin["email"], "role": admin["role"]}}


@router.get("/auth/me")
async def admin_me(admin: dict = Depends(get_current_admin)):
    return {"admin": {"id": admin["id"], "name": admin["name"], "email": admin["email"],
                      "role": admin["role"], "roles_available": ADMIN_ROLES}}


@router.post("/auth/logout")
async def admin_logout(response: Response):
    response.delete_cookie("admin_access_token", path="/")
    return {"ok": True}


# ---------- DASHBOARD ----------

@router.get("/dashboard")
async def admin_dashboard(admin: dict = Depends(get_current_admin)):
    offices = await db.offices.find({}, {"_id": 0}).to_list(1000)
    by_status = {"trial": 0, "active": 0, "past_due": 0, "suspended": 0, "canceled": 0}
    for o in offices:
        by_status[o.get("status", "active")] = by_status.get(o.get("status", "active"), 0) + 1
    plans = {p["id"]: p for p in await db.plans.find({}, {"_id": 0}).to_list(100)}
    proc_counts = {}
    async for row in db.processes.aggregate([{"$group": {"_id": "$office_id", "n": {"$sum": 1}}}]):
        proc_counts[row["_id"]] = row["n"]

    users_active = await db.users.count_documents({"active": True})
    processos = await db.processes.count_documents({})
    clientes = await db.clients.count_documents({})
    msgs_in = await db.messages.count_documents({"sender": "client"})
    msgs_out = await db.messages.count_documents({"sender": "ravi"})
    resolvidas = await db.audit_logs.count_documents({"event": "auto_resolved"})
    escaladas = await db.alerts.count_documents({"type": "intervention"})

    wa = {"connected": 0, "disconnected": 0, "token_expired": 0, "pending": 0, "error": 0}
    wa_expired_offices = []
    async for c in db.whatsapp_connections.find({}, {"_id": 0}):
        wa[c.get("status", "pending")] = wa.get(c.get("status", "pending"), 0) + 1
        if c.get("status") == "token_expired":
            wa_expired_offices.append(c["office_id"])

    charges = await db.charges.find({}, {"_id": 0}).to_list(5000)
    today = now().date().isoformat()
    recebido = sum(c.get("valor_final", c["valor"]) for c in charges if c["status"] == "paid")
    pendente = sum(c.get("valor_final", c["valor"]) for c in charges if c["status"] == "pending")
    vencidas = [c for c in charges if c["status"] == "pending" and c["vencimento"] < today]
    mrr = round(sum(o.get("valor_mensal") or 0 for o in offices if o.get("status") == "active"), 2)
    ativos = by_status.get("active", 0)

    atencao = []
    office_names = {o["id"]: o["name"] for o in offices}
    for oid in wa_expired_offices:
        atencao.append({"tipo": "whatsapp", "texto": f"WhatsApp com autorização expirada — {office_names.get(oid, oid)}", "gravidade": "alta"})
    for c in vencidas[:5]:
        atencao.append({"tipo": "financeiro", "texto": f"Cobrança vencida ({c['vencimento']}) — {office_names.get(c['office_id'], '')} — R$ {c.get('valor_final', c['valor'])}", "gravidade": "media"})
    for o in offices:
        plan = plans.get(o.get("plan_id") or "")
        limit = (plan or {}).get("process_limit")
        if limit:
            pct = round(proc_counts.get(o["id"], 0) / limit * 100)
            if pct >= 90:
                atencao.append({"tipo": "limite", "texto": f"{o['name']} utilizando {pct}% do limite de processos", "gravidade": "media"})
    for o in offices:
        if o.get("status") == "suspended":
            atencao.append({"tipo": "conta", "texto": f"Conta suspensa — {o['name']}", "gravidade": "alta"})

    return {
        "kpis": {
            "escritorios_ativos": ativos, "escritorios_suspensos": by_status["suspended"],
            "escritorios_trial": by_status["trial"], "usuarios_ativos": users_active,
            "processos_monitorados": processos, "clientes_atendidos": clientes,
            "mensagens_recebidas": msgs_in, "mensagens_respondidas": msgs_out,
            "conversas_resolvidas": resolvidas, "conversas_escaladas": escaladas,
            "tempo_economizado_min": round(resolvidas * 5.4),
            "whatsapp_conectados": wa["connected"],
            "whatsapp_desconectados": wa["disconnected"] + wa["token_expired"],
            "pagamentos_recebidos": round(recebido, 2), "pagamentos_pendentes": round(pendente, 2),
            "inadimplencia": len(vencidas), "mrr": mrr, "arr": round(mrr * 12, 2),
            "ticket_medio": round(mrr / ativos, 2) if ativos else 0,
            "cancelamentos": by_status["canceled"],
        },
        "atencao": atencao[:12],
    }


# ---------- ESCRITÓRIOS ----------

@router.get("/offices")
async def list_offices(admin: dict = Depends(get_current_admin)):
    offices = await db.offices.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    plans = {p["id"]: p for p in await db.plans.find({}, {"_id": 0}).to_list(100)}
    out = []
    for o in offices:
        users = await db.users.count_documents({"office_id": o["id"]})
        procs = await db.processes.count_documents({"office_id": o["id"]})
        responsavel = await db.users.find_one({"office_id": o["id"], "role": "SOCIO_ADMIN"},
                                              {"_id": 0, "name": 1, "last_name": 1, "email": 1})
        conn = await db.whatsapp_connections.find_one({"office_id": o["id"]},
                                                      {"_id": 0, "status": 1, "display_phone_number": 1})
        last_msg = await db.messages.find_one({"office_id": o["id"]}, {"_id": 0, "created_at": 1},
                                              sort=[("created_at", -1)])
        plan = plans.get(o.get("plan_id") or "")
        limit = (plan or {}).get("process_limit")
        out.append({
            "id": o["id"], "name": o["name"], "status": o.get("status", "active"),
            "plan_id": o.get("plan_id"), "plan_name": (plan or {}).get("name", "Sem plano"),
            "valor_mensal": o.get("valor_mensal") or 0, "valor_anual": o.get("valor_anual") or 0,
            "ciclo": o.get("ciclo", "mensal"), "vencimento": o.get("vencimento", ""),
            "observacoes": o.get("observacoes", ""), "created_at": o.get("created_at"),
            "responsavel": f"{responsavel['name']} {responsavel.get('last_name','')}".strip() if responsavel else "—",
            "responsavel_email": responsavel["email"] if responsavel else "—",
            "usuarios": users, "processos": procs,
            "process_limit": limit, "uso_pct": round(procs / limit * 100) if limit else None,
            "whatsapp_status": (conn or {}).get("status", "não conectado"),
            "whatsapp_numero": (conn or {}).get("display_phone_number", ""),
            "ultima_atividade": (last_msg or {}).get("created_at"),
        })
    return {"offices": out, "plans": [{"id": p["id"], "name": p["name"]} for p in plans.values()]}


class OfficePatch(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    plan_id: Optional[str] = None
    plan_apply: Optional[str] = None
    valor_mensal: Optional[float] = None
    valor_anual: Optional[float] = None
    ciclo: Optional[str] = None
    vencimento: Optional[str] = None
    observacoes: Optional[str] = None


@router.patch("/offices/{office_id}")
async def update_office(office_id: str, data: OfficePatch, admin: dict = Depends(require_admin_roles("ADMIN_OPERACOES", "ADMIN_FINANCEIRO"))):
    office = await db.offices.find_one({"id": office_id}, {"_id": 0})
    if not office:
        raise HTTPException(404, "Escritório não encontrado")
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    plan_apply = updates.pop("plan_apply", None) or "immediate"
    if "status" in updates and updates["status"] not in ("trial", "active", "past_due", "suspended", "canceled"):
        raise HTTPException(400, "Status inválido")
    if updates.get("plan_id") and updates["plan_id"] != office.get("plan_id"):
        old_plan = await db.plans.find_one({"id": office.get("plan_id")}, {"_id": 0})
        new_plan = await db.plans.find_one({"id": updates["plan_id"]}, {"_id": 0})
        direction = "alteração"
        if old_plan and new_plan:
            op = old_plan.get("process_limit") or 10**9
            np_ = new_plan.get("process_limit") or 10**9
            direction = "upgrade" if np_ > op else "downgrade" if np_ < op else "alteração"
        await db.plan_changes.insert_one({"id": uuid.uuid4().hex, "office_id": office_id,
                                          "de": (old_plan or {}).get("name"), "para": (new_plan or {}).get("name"),
                                          "direction": direction, "admin": admin["email"], "created_at": now_iso()})
        target_plan = updates.get("plan_id")
        new_version = await db.plan_versions.find_one({"plan_id": target_plan, "effective_until": None},
                                                      {"_id": 0}, sort=[("version", -1)])
        if plan_apply == "next_cycle":
            updates["pending_plan_id"] = target_plan
            del updates["plan_id"]
        await db.subscriptions.insert_one({
            "id": uuid.uuid4().hex, "office_id": office_id, "plan_id": target_plan,
            "plan_version_id": (new_version or {}).get("id"),
            "status": "scheduled" if plan_apply == "next_cycle" else "active",
            "effective_from": None if plan_apply == "next_cycle" else now_iso()[:10],
            "created_by": admin["email"], "created_at": now_iso()})
        await admin_log(admin, "subscription_changed", office_id=office_id,
                        plan=(new_plan or {}).get("name"), apply=plan_apply)
        await audit(office_id, "plan_changed", actor=f"admin:{admin['email']}",
                    de=(old_plan or {}).get("name"), para=(new_plan or {}).get("name"), apply=plan_apply)
    if updates.get("status") == "canceled":
        await db.cancellations.insert_one({"id": uuid.uuid4().hex, "office_id": office_id,
                                           "plano_anterior": office.get("plan_id"),
                                           "receita_perdida_estimada": office.get("valor_mensal") or 0,
                                           "responsavel": admin["email"], "created_at": now_iso()})
    if updates:
        await db.offices.update_one({"id": office_id}, {"$set": updates})
        await admin_log(admin, "office_updated", office_id=office_id, changes=updates)
    return await db.offices.find_one({"id": office_id}, {"_id": 0, "demo_metrics": 0})


class ImpersonateIn(BaseModel):
    motivo: str


@router.post("/offices/{office_id}/impersonate")
async def impersonate(office_id: str, data: ImpersonateIn, admin: dict = Depends(require_admin_roles())):
    """Visualizar como escritório: sessão auditada, sem compartilhar senha."""
    if not data.motivo.strip():
        raise HTTPException(400, "Informe o motivo do acesso")
    office = await db.offices.find_one({"id": office_id}, {"_id": 0, "name": 1})
    if not office:
        raise HTTPException(404, "Escritório não encontrado")
    socio = await db.users.find_one({"office_id": office_id, "role": "SOCIO_ADMIN", "active": True}, {"_id": 0})
    if not socio:
        raise HTTPException(400, "Escritório sem sócio ativo")
    from security import create_access_token
    token = create_access_token(socio["id"], socio["email"], socio.get("token_version", 0))
    log_id = uuid.uuid4().hex
    await db.admin_logs.insert_one({
        "id": log_id, "admin_email": admin["email"], "admin_role": admin.get("role"),
        "action": "impersonation_start", "office_id": office_id, "motivo": data.motivo.strip(),
        "details": {"impersonated_user": socio["email"]}, "created_at": now_iso(), "ended_at": None,
    })
    return {"token": token, "log_id": log_id, "office_name": office["name"], "user_name": socio["name"]}


# ---------- PLANOS ----------

class PlanIn(BaseModel):
    name: str
    process_limit: Optional[int] = None
    user_limit: Optional[int] = None
    message_limit: Optional[int] = None
    ai_quota: Optional[int] = None
    features: Optional[str] = ""
    price_monthly: Optional[float] = 0
    price_yearly: Optional[float] = 0
    overage_pct: Optional[float] = 10
    status: Optional[str] = "ativo"


@router.get("/plans")
async def list_plans(admin: dict = Depends(get_current_admin)):
    return await db.plans.find({}, {"_id": 0}).sort("process_limit", 1).to_list(100)


@router.post("/plans")
async def create_plan(data: PlanIn, admin: dict = Depends(require_admin_roles("ADMIN_FINANCEIRO"))):
    plan = {"id": uuid.uuid4().hex, **data.model_dump(), "created_at": now_iso()}
    await db.plans.insert_one(plan)
    await db.plan_versions.insert_one(_plan_version(plan, 1, admin))
    await admin_log(admin, "plan_created", plan=data.name)
    plan.pop("_id", None)
    return plan


def _plan_version(plan: dict, version: int, admin: dict) -> dict:
    return {"id": uuid.uuid4().hex, "plan_id": plan["id"], "version": version,
            "process_limit": plan.get("process_limit"), "monthly_price": plan.get("price_monthly"),
            "annual_price": plan.get("price_yearly"), "user_limit": plan.get("user_limit"),
            "resource_limits": {"message_limit": plan.get("message_limit"), "ai_quota": plan.get("ai_quota"),
                                "overage_pct": plan.get("overage_pct")},
            "effective_from": now_iso()[:10], "effective_until": None,
            "created_by": admin["email"], "status": "ativo", "created_at": now_iso()}


COMMERCIAL_FIELDS = ("process_limit", "price_monthly", "price_yearly", "user_limit", "message_limit", "ai_quota", "overage_pct")


@router.get("/plans/{plan_id}/versions")
async def list_plan_versions(plan_id: str, admin: dict = Depends(get_current_admin)):
    return await db.plan_versions.find({"plan_id": plan_id}, {"_id": 0}).sort("version", -1).to_list(50)


@router.patch("/plans/{plan_id}")
async def update_plan(plan_id: str, data: PlanIn, admin: dict = Depends(require_admin_roles("ADMIN_FINANCEIRO"))):
    old = await db.plans.find_one({"id": plan_id}, {"_id": 0})
    if not old:
        raise HTTPException(404, "Plano não encontrado")
    new_data = data.model_dump()
    await db.plans.update_one({"id": plan_id}, {"$set": new_data})
    commercial_changed = any(old.get(k) != new_data.get(k) for k in COMMERCIAL_FIELDS)
    if commercial_changed:
        last_v = await db.plan_versions.find_one({"plan_id": plan_id, "effective_until": None},
                                                 {"_id": 0}, sort=[("version", -1)])
        if last_v:
            await db.plan_versions.update_one({"id": last_v["id"]},
                                              {"$set": {"effective_until": now_iso()[:10], "status": "encerrada"}})
        merged = {**old, **new_data}
        await db.plan_versions.insert_one(_plan_version(merged, (last_v["version"] + 1) if last_v else 1, admin))
        await admin_log(admin, "plan_version_created", plan=data.name,
                        version=(last_v["version"] + 1) if last_v else 1)
    await admin_log(admin, "plan_updated", plan=data.name)
    return await db.plans.find_one({"id": plan_id}, {"_id": 0})


# ---------- FINANCEIRO ----------

@router.get("/billing/overview")
async def billing_overview(admin: dict = Depends(get_current_admin)):
    charges = await db.charges.find({}, {"_id": 0}).to_list(5000)
    today = now().date().isoformat()
    month = today[:7]
    paid_all = [c for c in charges if c["status"] == "paid"]
    pend = [c for c in charges if c["status"] == "pending"]
    overdue = [c for c in pend if c["vencimento"] < today]
    aging = {"1-7": 0, "8-30": 0, "31-60": 0, "61-90": 0, "90+": 0}
    for c in overdue:
        dias = (now().date() - datetime.fromisoformat(c["vencimento"]).date()).days
        if dias <= 7: aging["1-7"] += c.get("valor_final", c["valor"])
        elif dias <= 30: aging["8-30"] += c.get("valor_final", c["valor"])
        elif dias <= 60: aging["31-60"] += c.get("valor_final", c["valor"])
        elif dias <= 90: aging["61-90"] += c.get("valor_final", c["valor"])
        else: aging["90+"] += c.get("valor_final", c["valor"])
    offices = await db.offices.find({"status": "active"}, {"_id": 0, "valor_mensal": 1}).to_list(1000)
    mrr = round(sum(o.get("valor_mensal") or 0 for o in offices), 2)
    return {
        "faturado_mes": round(sum(c.get("valor_final", c["valor"]) for c in charges if c["competencia"] == month), 2),
        "recebido_total": round(sum(c.get("valor_final", c["valor"]) for c in paid_all), 2),
        "a_receber": round(sum(c.get("valor_final", c["valor"]) for c in pend), 2),
        "vencido": round(sum(c.get("valor_final", c["valor"]) for c in overdue), 2),
        "contas_vencidas": len(overdue), "aging": aging,
        "mrr": mrr, "arr": round(mrr * 12, 2),
        "ticket_medio": round(mrr / len(offices), 2) if offices else 0,
        "descontos_concedidos": round(sum(c.get("desconto") or 0 for c in charges), 2),
    }


@router.get("/billing/charges")
async def list_charges(status: str = "all", office_id: str = "", admin: dict = Depends(get_current_admin)):
    q = {}
    if status != "all":
        q["status"] = status
    if office_id:
        q["office_id"] = office_id
    charges = await db.charges.find(q, {"_id": 0}).sort("vencimento", -1).to_list(500)
    names = {o["id"]: o["name"] for o in await db.offices.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)}
    today = now().date().isoformat()
    for c in charges:
        c["office_name"] = names.get(c["office_id"], "—")
        c["dias_atraso"] = max(0, (now().date() - datetime.fromisoformat(c["vencimento"]).date()).days) \
            if c["status"] == "pending" and c["vencimento"] < today else 0
    return {"charges": charges, "offices": [{"id": k, "name": v} for k, v in names.items()]}


class ChargeIn(BaseModel):
    office_id: str
    competencia: str
    vencimento: str
    valor: float
    desconto: Optional[float] = 0


@router.post("/billing/charges")
async def create_charge(data: ChargeIn, admin: dict = Depends(require_admin_roles("ADMIN_FINANCEIRO"))):
    if not await db.offices.find_one({"id": data.office_id}):
        raise HTTPException(404, "Escritório não encontrado")
    charge = {"id": uuid.uuid4().hex, **data.model_dump(), "juros": 0, "multa": 0,
              "valor_final": round(data.valor - (data.desconto or 0), 2),
              "status": "pending", "created_at": now_iso()}
    await db.charges.insert_one(charge)
    await admin_log(admin, "charge_created", office_id=data.office_id, valor=data.valor)
    charge.pop("_id", None)
    return charge


class PayIn(BaseModel):
    valor: float
    metodo: str
    referencia: Optional[str] = ""


@router.post("/billing/charges/{charge_id}/pay")
async def pay_charge(charge_id: str, data: PayIn, admin: dict = Depends(require_admin_roles("ADMIN_FINANCEIRO"))):
    charge = await db.charges.find_one({"id": charge_id}, {"_id": 0})
    if not charge:
        raise HTTPException(404, "Cobrança não encontrada")
    if charge["status"] != "pending":
        raise HTTPException(400, "Cobrança não está pendente")
    await db.charges.update_one({"id": charge_id},
                                {"$set": {"status": "paid", "valor_recebido": data.valor, "paid_at": now_iso()}})
    await db.receipts.insert_one({"id": uuid.uuid4().hex, "charge_id": charge_id,
                                  "office_id": charge["office_id"], "valor": data.valor,
                                  "metodo": data.metodo, "referencia": data.referencia or "",
                                  "created_at": now_iso()})
    await admin_log(admin, "charge_paid", office_id=charge["office_id"], valor=data.valor)
    return {"ok": True}


@router.post("/billing/charges/{charge_id}/cancel")
async def cancel_charge(charge_id: str, admin: dict = Depends(require_admin_roles("ADMIN_FINANCEIRO"))):
    res = await db.charges.update_one({"id": charge_id, "status": "pending"}, {"$set": {"status": "canceled"}})
    if not res.matched_count:
        raise HTTPException(404, "Cobrança pendente não encontrada")
    await admin_log(admin, "charge_canceled", charge_id=charge_id)
    return {"ok": True}


# ---------- WHATSAPP / META ----------

@router.get("/meta/status")
async def meta_status(admin: dict = Depends(get_current_admin)):
    secrets_db = await get_platform_secrets()
    def cfg(key):
        return bool(os.environ.get(key) or secrets_db.get(key))
    conns = await db.whatsapp_connections.find({}, {"_id": 0, "access_token": 0}).to_list(500)
    names = {o["id"]: o["name"] for o in await db.offices.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)}
    for c in conns:
        c["office_name"] = names.get(c["office_id"], "—")
    doc = await db.platform_settings.find_one({"id": "global"}, {"_id": 0})
    test_meta = (doc or {}).get("secrets_meta", {})
    return {
        "secrets": {k: cfg(k) for k in ["META_APP_ID", "META_APP_SECRET", "META_CONFIG_ID", "META_WEBHOOK_VERIFY_TOKEN", "META_TEST_TOKEN"]},
        "ambiente": "produção" if cfg("META_APP_ID") else "teste",
        "app_id_masked": (os.environ.get("META_APP_ID") or secrets_db.get("META_APP_ID") or "")[:6] + "…" if cfg("META_APP_ID") else None,
        "connections": conns,
        "test_token_meta": {"updated_at": test_meta.get("META_TEST_TOKEN_at"), "status": test_meta.get("META_TEST_TOKEN_status")},
    }


class SecretsIn(BaseModel):
    meta_app_id: Optional[str] = ""
    meta_app_secret: Optional[str] = ""
    meta_config_id: Optional[str] = ""
    meta_test_token: Optional[str] = ""


@router.post("/meta/secrets")
async def update_secrets(data: SecretsIn, admin: dict = Depends(require_admin_roles("ADMIN_TECNOLOGIA"))):
    """Secrets são write-only: salvos no servidor, nunca devolvidos ao frontend."""
    mapping = {"META_APP_ID": data.meta_app_id, "META_APP_SECRET": data.meta_app_secret,
               "META_CONFIG_ID": data.meta_config_id, "META_TEST_TOKEN": data.meta_test_token}
    updates, meta_updates = {}, {}
    for k, v in mapping.items():
        if v and v.strip():
            updates[f"secrets.{k}"] = v.strip()
            meta_updates[f"secrets_meta.{k}_at"] = now_iso()
            os.environ[k] = v.strip()
    if not updates:
        raise HTTPException(400, "Nada para atualizar")
    if "secrets.META_TEST_TOKEN" in updates:
        try:
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.get(f"https://graph.facebook.com/{os.environ.get('META_GRAPH_VERSION', 'v25.0')}/me",
                                headers={"Authorization": f"Bearer {mapping['META_TEST_TOKEN'].strip()}"})
            meta_updates["secrets_meta.META_TEST_TOKEN_status"] = "valid" if not r.is_error else "invalid"
        except Exception:
            meta_updates["secrets_meta.META_TEST_TOKEN_status"] = "unknown"
    await db.platform_settings.update_one({"id": "global"}, {"$set": {**updates, **meta_updates}}, upsert=True)
    await admin_log(admin, "secrets_updated", keys=[k for k, v in mapping.items() if v and v.strip()])
    return {"ok": True, "configurados": list(mapping.keys())}


@router.get("/health")
async def health_check(admin: dict = Depends(get_current_admin)):
    checks = {}
    try:
        await db.command("ping")
        checks["banco"] = {"ok": True, "label": "Banco de dados"}
    except Exception as e:
        checks["banco"] = {"ok": False, "label": "Banco de dados", "erro": str(e)[:100]}
    secrets_db = await get_platform_secrets()
    token = os.environ.get("META_TEST_TOKEN") or secrets_db.get("META_TEST_TOKEN")
    conn = await db.whatsapp_connections.find_one({"status": {"$in": ["connected", "token_expired"]}}, {"_id": 0})
    meta_ok = token_ok = False
    if conn and conn.get("access_token"):
        try:
            from whatsapp_meta import conn_token
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.get(f"https://graph.facebook.com/{os.environ.get('META_GRAPH_VERSION', 'v25.0')}/{conn['phone_number_id']}",
                                params={"fields": "display_phone_number"},
                                headers={"Authorization": f"Bearer {conn_token(conn)}"})
            meta_ok = True
            token_ok = not r.is_error
        except Exception:
            meta_ok = False
    checks["meta_api"] = {"ok": meta_ok, "label": "WhatsApp API"}
    checks["token"] = {"ok": token_ok, "label": "Token"}
    last_msg_in = await db.messages.find_one({"sender": "client", "meta_message_id": {"$ne": None}},
                                             {"_id": 0, "created_at": 1}, sort=[("created_at", -1)])
    last_msg_out = await db.messages.find_one({"sender": "ravi", "delivered": True},
                                              {"_id": 0, "created_at": 1}, sort=[("created_at", -1)])
    checks["webhook"] = {"ok": bool(last_msg_in), "label": "Webhook",
                         "ultimo_evento": (last_msg_in or {}).get("created_at")}
    checks["recebimento"] = {"ok": bool(last_msg_in), "label": "Recebimento",
                             "ultima_mensagem": (last_msg_in or {}).get("created_at")}
    checks["envio"] = {"ok": bool(last_msg_out), "label": "Envio",
                       "ultima_resposta": (last_msg_out or {}).get("created_at")}
    checks["ia"] = {"ok": bool(os.environ.get("EMERGENT_LLM_KEY")), "label": "IA"}
    try:
        from storage import init_storage
        init_storage()
        checks["storage"] = {"ok": True, "label": "Storage"}
    except Exception:
        checks["storage"] = {"ok": False, "label": "Storage"}
    checks["fila"] = {"ok": True, "label": "Fila", "detalhe": "processamento inline (BackgroundTasks)"}
    await db.platform_settings.update_one({"id": "global"}, {"$set": {"health_last": now_iso()}}, upsert=True)
    return {"checks": checks, "verificado_em": now_iso()}


# ---------- USUÁRIOS ADMINISTRATIVOS ----------

async def require_super_admin(admin: dict = Depends(get_current_admin)) -> dict:
    if admin["role"] != "SUPER_ADMIN":
        raise HTTPException(403, "Apenas SUPER_ADMIN pode gerenciar administradores")
    return admin


@router.get("/users")
async def list_admin_users(admin: dict = Depends(require_super_admin)):
    users = await db.admin_users.find({}, {"_id": 0, "password_hash": 0}).sort("created_at", -1).to_list(100)
    return {"users": users, "roles": ADMIN_ROLES}


class AdminUserIn(BaseModel):
    name: str
    email: EmailStr
    role: str


@router.post("/users")
async def create_admin_user(data: AdminUserIn, admin: dict = Depends(require_super_admin)):
    import secrets as _secrets
    email = data.email.lower().strip()
    if data.role not in ADMIN_ROLES:
        raise HTTPException(400, "Perfil inválido")
    if not data.name.strip():
        raise HTTPException(400, "Informe o nome")
    if await db.admin_users.find_one({"email": email}):
        raise HTTPException(400, "Este e-mail já está cadastrado")
    temp_password = "RaviAdmin-" + _secrets.token_urlsafe(6)
    user = {"id": uuid.uuid4().hex, "name": data.name.strip(), "email": email,
            "password_hash": hash_password(temp_password), "role": data.role,
            "active": True, "totp_secret": None, "created_at": now_iso()}
    await db.admin_users.insert_one(user)
    await admin_log(admin, "admin_user_created", admin_email=email, role=data.role)
    user.pop("_id", None)
    user.pop("password_hash", None)
    user["temp_password"] = temp_password
    return user


class AdminUserPatch(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None


@router.patch("/users/{user_id}")
async def update_admin_user(user_id: str, data: AdminUserPatch, admin: dict = Depends(require_super_admin)):
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    if "role" in updates and updates["role"] not in ADMIN_ROLES:
        raise HTTPException(400, "Perfil inválido")
    if not updates:
        raise HTTPException(400, "Nada para atualizar")
    res = await db.admin_users.update_one({"id": user_id}, {"$set": updates})
    if not res.matched_count:
        raise HTTPException(404, "Administrador não encontrado")
    await admin_log(admin, "admin_user_updated", target=user_id, **updates)
    return {"ok": True}


@router.post("/users/{user_id}/toggle-active")
async def toggle_admin_user(user_id: str, admin: dict = Depends(require_super_admin)):
    if user_id == admin["id"]:
        raise HTTPException(400, "Você não pode desativar a si mesmo")
    target = await db.admin_users.find_one({"id": user_id}, {"_id": 0})
    if not target:
        raise HTTPException(404, "Administrador não encontrado")
    new_state = not target.get("active", True)
    await db.admin_users.update_one({"id": user_id}, {"$set": {"active": new_state}})
    await admin_log(admin, "admin_user_toggled", target=target["email"], active=new_state)
    return {"ok": True, "active": new_state}


# ---------- LOGS ----------

@router.get("/logs")
async def list_logs(tipo: str = "all", office_id: str = "", from_date: str = "", to_date: str = "",
                    admin: dict = Depends(get_current_admin)):
    out = []
    date_q = {}
    if from_date:
        date_q["$gte"] = from_date
    if to_date:
        date_q["$lte"] = to_date + "T23:59:59"
    q = {}
    if office_id:
        q["office_id"] = office_id
    if date_q:
        q["created_at"] = date_q
    if tipo in ("all", "tenant"):
        async for l in db.audit_logs.find(q, {"_id": 0}).sort("created_at", -1).limit(120):
            l["origem"] = "tenant"
            out.append(l)
    if tipo in ("all", "admin"):
        q2 = {}
        if office_id:
            q2["office_id"] = office_id
        if date_q:
            q2["created_at"] = date_q
        async for l in db.admin_logs.find(q2, {"_id": 0}).sort("created_at", -1).limit(120):
            l["origem"] = "admin"
            out.append(l)
    out.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    offices = await db.offices.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)
    return {"logs": out[:200], "offices": offices}


# ---------- SUPORTE ----------

@router.get("/tickets")
async def list_tickets(status: str = "all", admin: dict = Depends(get_current_admin)):
    q = {} if status == "all" else {"status": status}
    tickets = await db.tickets.find(q, {"_id": 0}).sort("created_at", -1).to_list(300)
    names = {o["id"]: o["name"] for o in await db.offices.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)}
    for t in tickets:
        t["office_name"] = names.get(t["office_id"], "—")
    return tickets


class TicketPatch(BaseModel):
    status: Optional[str] = None
    responsavel: Optional[str] = None


@router.patch("/tickets/{ticket_id}")
async def update_ticket(ticket_id: str, data: TicketPatch, admin: dict = Depends(require_admin_roles("ADMIN_SUPORTE", "ADMIN_OPERACOES"))):
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "Nada para atualizar")
    res = await db.tickets.update_one({"id": ticket_id}, {"$set": updates})
    if not res.matched_count:
        raise HTTPException(404, "Chamado não encontrado")
    await admin_log(admin, "ticket_updated", ticket_id=ticket_id, **updates)
    return {"ok": True}


# ---------- CONFIG GLOBAL DE IA ----------

class AIConfigIn(BaseModel):
    rules: Optional[list] = None
    tom_padrao: Optional[str] = None
    autonomia: Optional[str] = None
    limite_resposta: Optional[int] = None


@router.get("/settings/ai")
async def get_ai_settings(admin: dict = Depends(get_current_admin)):
    doc = await db.platform_settings.find_one({"id": "global"}, {"_id": 0})
    return (doc or {}).get("ai_config") or {"rules": [], "tom_padrao": "acolhedor", "autonomia": "padrao", "limite_resposta": 400}


@router.put("/settings/ai")
async def put_ai_settings(data: AIConfigIn, admin: dict = Depends(require_admin_roles("ADMIN_TECNOLOGIA"))):
    updates = {f"ai_config.{k}": v for k, v in data.model_dump().items() if v is not None}
    if updates:
        await db.platform_settings.update_one({"id": "global"}, {"$set": updates}, upsert=True)
        await admin_log(admin, "ai_config_updated", keys=list(data.model_dump(exclude_none=True).keys()))
    return await get_ai_settings(admin)


# ---------- CONSUMO WHATSAPP: TARIFAS, FATURAS, AJUSTES ----------

class MetaPricingIn(BaseModel):
    category: str
    meta_rate: float
    country: Optional[str] = "BR"
    currency: Optional[str] = "BRL"
    pricing_unit: Optional[str] = "MESSAGE"
    effective_from: str
    effective_until: Optional[str] = None
    status: Optional[str] = "ativo"


@router.get("/pricing/meta")
async def list_meta_pricing(admin: dict = Depends(get_current_admin)):
    return await db.whatsapp_pricing.find({}, {"_id": 0}).sort("effective_from", -1).to_list(200)


@router.post("/pricing/meta")
async def create_meta_pricing(data: MetaPricingIn, admin: dict = Depends(require_admin_roles("ADMIN_FINANCEIRO"))):
    if data.category not in CATEGORIES:
        raise HTTPException(400, f"Categoria inválida. Use: {', '.join(CATEGORIES)}")
    row = {"id": uuid.uuid4().hex, **data.model_dump(), "created_by": admin["email"], "created_at": now_iso()}
    await db.whatsapp_pricing.insert_one(row)
    await admin_log(admin, "meta_pricing_created", category=data.category, meta_rate=data.meta_rate)
    row.pop("_id", None)
    return row


@router.patch("/pricing/meta/{rate_id}")
async def update_meta_pricing(rate_id: str, data: MetaPricingIn, admin: dict = Depends(require_admin_roles("ADMIN_FINANCEIRO"))):
    res = await db.whatsapp_pricing.update_one({"id": rate_id}, {"$set": data.model_dump()})
    if not res.matched_count:
        raise HTTPException(404, "Tarifa não encontrada")
    await admin_log(admin, "meta_pricing_updated", rate_id=rate_id, meta_rate=data.meta_rate)
    return {"ok": True}


class CustomerRateIn(BaseModel):
    plan_id: str
    category: str
    customer_rate: float
    currency: Optional[str] = "BRL"
    effective_from: str
    effective_until: Optional[str] = None
    status: Optional[str] = "ativo"


@router.get("/pricing/customer")
async def list_customer_rates(admin: dict = Depends(get_current_admin)):
    rates = await db.whatsapp_customer_rates.find({}, {"_id": 0}).sort("effective_from", -1).to_list(300)
    plans = {p["id"]: p["name"] for p in await db.plans.find({}, {"_id": 0}).to_list(100)}
    for r in rates:
        r["plan_name"] = plans.get(r["plan_id"], "—")
    return {"rates": rates, "plans": [{"id": pid, "name": name} for pid, name in plans.items()]}


@router.post("/pricing/customer")
async def create_customer_rate(data: CustomerRateIn, admin: dict = Depends(require_admin_roles("ADMIN_FINANCEIRO"))):
    if data.category not in CATEGORIES:
        raise HTTPException(400, f"Categoria inválida. Use: {', '.join(CATEGORIES)}")
    if not await db.plans.find_one({"id": data.plan_id}):
        raise HTTPException(404, "Plano não encontrado")
    row = {"id": uuid.uuid4().hex, **data.model_dump(), "created_by": admin["email"], "created_at": now_iso()}
    await db.whatsapp_customer_rates.insert_one(row)
    await admin_log(admin, "customer_rate_created", plan_id=data.plan_id,
                    category=data.category, customer_rate=data.customer_rate)
    row.pop("_id", None)
    return row


@router.patch("/pricing/customer/{rate_id}")
async def update_customer_rate(rate_id: str, data: CustomerRateIn, admin: dict = Depends(require_admin_roles("ADMIN_FINANCEIRO"))):
    res = await db.whatsapp_customer_rates.update_one({"id": rate_id}, {"$set": data.model_dump()})
    if not res.matched_count:
        raise HTTPException(404, "Tarifa não encontrada")
    await admin_log(admin, "customer_rate_updated", rate_id=rate_id, customer_rate=data.customer_rate)
    return {"ok": True}


class UsageEventIn(BaseModel):
    office_id: str
    category: str
    billable: bool = True
    quantity: int = 1


@router.post("/usage-events")
async def create_usage_events(data: UsageEventIn, admin: dict = Depends(require_admin_roles("ADMIN_FINANCEIRO"))):
    """Registro administrativo de eventos de consumo (testes, backfill, ajustes operacionais)."""
    if not await db.offices.find_one({"id": data.office_id}):
        raise HTTPException(404, "Escritório não encontrado")
    if data.category not in CATEGORIES:
        raise HTTPException(400, f"Categoria inválida. Use: {', '.join(CATEGORIES)}")
    if not (1 <= data.quantity <= 500):
        raise HTTPException(400, "Quantidade deve ser entre 1 e 500")
    for _ in range(data.quantity):
        await record_usage_event(data.office_id, "outbound", data.category, data.billable)
    await admin_log(admin, "usage_events_recorded", office_id=data.office_id,
                    category=data.category, quantity=data.quantity, billable=data.billable)
    return {"ok": True, "recorded": data.quantity}


class WaInvoiceGenIn(BaseModel):
    office_id: str
    period: str
    due_date: Optional[str] = None
    discount: Optional[float] = 0
    tax: Optional[float] = 0


@router.post("/billing/whatsapp-invoices/generate")
async def generate_wa_invoice(data: WaInvoiceGenIn, admin: dict = Depends(require_admin_roles("ADMIN_FINANCEIRO"))):
    events = await db.whatsapp_usage_events.find(
        {"office_id": data.office_id, "billing_period": data.period, "billable": True, "invoice_id": None},
        {"_id": 0}).to_list(20000)
    if not events:
        raise HTTPException(400, "Sem consumo faturável no período")
    by_cat = {}
    for e in events:
        c = e["billing_category"]
        by_cat.setdefault(c, {"category": c, "quantity": 0, "unit_price": e["ravi_price"], "amount": 0.0})
        by_cat[c]["quantity"] += 1
        by_cat[c]["amount"] = round(by_cat[c]["amount"] + e["ravi_price"], 4)
    items = [{**v, "reference": f"Consumo WhatsApp {v['category']} — {data.period}"} for v in by_cat.values()]
    subtotal = round(sum(i["amount"] for i in items), 2)
    total = round(subtotal - (data.discount or 0) + (data.tax or 0), 2)
    seq = await db.whatsapp_invoices.count_documents({}) + 1
    invoice = {
        "id": uuid.uuid4().hex, "office_id": data.office_id, "billing_period": data.period,
        "invoice_number": f"RAVI-WA-{data.period.replace('-', '')}-{seq:04d}",
        "issue_date": now_iso()[:10],
        "due_date": data.due_date or (datetime.now(timezone.utc) + timedelta(days=10)).date().isoformat(),
        "subtotal": subtotal, "discount": data.discount or 0, "tax": data.tax or 0,
        "total": total, "status": "pending", "items": items,
        "created_by": admin["email"], "created_at": now_iso(),
    }
    await db.whatsapp_invoices.insert_one(invoice)
    await db.whatsapp_usage_events.update_many({"id": {"$in": [e["id"] for e in events]}},
                                               {"$set": {"invoice_id": invoice["id"]}})
    await db.billing_periods.update_one(
        {"office_id": data.office_id, "period": data.period},
        {"$set": {"id": uuid.uuid4().hex, "office_id": data.office_id, "start_date": f"{data.period}-01",
                  "end_date": data.period, "message_count": len(events), "billable_count": len(events),
                  "total_amount": subtotal, "invoiced_amount": total, "paid_amount": 0,
                  "status": "invoiced", "updated_at": now_iso()},
         "$setOnInsert": {"created_at": now_iso()}},
        upsert=True)
    await admin_log(admin, "whatsapp_invoice_generated", office_id=data.office_id,
                    period=data.period, total=total, number=invoice["invoice_number"])
    invoice.pop("_id", None)
    return invoice


@router.get("/billing/whatsapp-invoices")
async def list_wa_invoices(office_id: str = "", status: str = "all", admin: dict = Depends(get_current_admin)):
    q = {}
    if office_id:
        q["office_id"] = office_id
    if status != "all":
        q["status"] = status
    invoices = await db.whatsapp_invoices.find(q, {"_id": 0}).sort("issue_date", -1).to_list(300)
    names = {o["id"]: o["name"] for o in await db.offices.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)}
    for inv in invoices:
        inv["office_name"] = names.get(inv["office_id"], "—")
    return invoices


@router.post("/billing/whatsapp-invoices/{invoice_id}/pay")
async def pay_wa_invoice(invoice_id: str, data: PayIn, admin: dict = Depends(get_current_admin)):
    inv = await db.whatsapp_invoices.find_one({"id": invoice_id}, {"_id": 0})
    if not inv:
        raise HTTPException(404, "Fatura não encontrada")
    if inv["status"] != "pending":
        raise HTTPException(400, "Fatura não está pendente")
    await db.whatsapp_invoices.update_one({"id": invoice_id}, {"$set": {"status": "paid", "paid_at": now_iso()}})
    await db.payments.insert_one({"id": uuid.uuid4().hex, "invoice_id": invoice_id,
                                  "office_id": inv["office_id"], "valor": data.valor,
                                  "metodo": data.metodo, "referencia": data.referencia or "",
                                  "created_by": admin["email"], "created_at": now_iso()})
    await admin_log(admin, "whatsapp_invoice_paid", office_id=inv["office_id"], valor=data.valor)
    return {"ok": True}


class AdjustmentIn(BaseModel):
    office_id: str
    tipo: str
    valor: float
    motivo: str
    referencia: Optional[str] = ""


@router.post("/billing/adjustments")
async def create_adjustment(data: AdjustmentIn, admin: dict = Depends(get_current_admin)):
    if data.tipo not in ("credito", "desconto", "estorno", "ajuste_consumo"):
        raise HTTPException(400, "Tipo inválido")
    if not data.motivo.strip():
        raise HTTPException(400, "Informe o motivo do ajuste")
    adj = {"id": uuid.uuid4().hex, **data.model_dump(), "created_by": admin["email"], "created_at": now_iso()}
    await db.billing_adjustments.insert_one(adj)
    await admin_log(admin, "billing_adjustment", office_id=data.office_id, tipo=data.tipo, valor=data.valor)
    adj.pop("_id", None)
    return adj


@router.get("/billing/adjustments")
async def list_adjustments(office_id: str = "", admin: dict = Depends(get_current_admin)):
    q = {"office_id": office_id} if office_id else {}
    return await db.billing_adjustments.find(q, {"_id": 0}).sort("created_at", -1).to_list(200)


@router.get("/reports/whatsapp")
async def whatsapp_consolidated_report(admin: dict = Depends(get_current_admin)):
    events = await db.whatsapp_usage_events.find({}, {"_id": 0}).to_list(50000)
    billable = [e for e in events if e["billable"]]
    names = {o["id"]: o["name"] for o in await db.offices.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)}
    by_office, by_cat, by_period = {}, {}, {}
    for e in billable:
        by_office.setdefault(names.get(e["office_id"], e["office_id"]), {"mensagens": 0, "valor": 0.0, "custo_meta": 0.0})
        by_office[names.get(e["office_id"], e["office_id"])]["mensagens"] += 1
        by_office[names.get(e["office_id"], e["office_id"])]["valor"] = round(by_office[names.get(e["office_id"], e["office_id"])]["valor"] + e["ravi_price"], 4)
        by_office[names.get(e["office_id"], e["office_id"])]["custo_meta"] = round(by_office[names.get(e["office_id"], e["office_id"])]["custo_meta"] + e["meta_cost"], 4)
        by_cat.setdefault(e["billing_category"], 0)
        by_cat[e["billing_category"]] += 1
        by_period.setdefault(e["billing_period"], {"mensagens": 0, "valor": 0.0})
        by_period[e["billing_period"]]["mensagens"] += 1
        by_period[e["billing_period"]]["valor"] = round(by_period[e["billing_period"]]["valor"] + e["ravi_price"], 4)
    receita = round(sum(e["ravi_price"] for e in billable), 2)
    custo = round(sum(e["meta_cost"] for e in billable), 2)
    return {
        "mensagens_faturaveis": len(billable),
        "mensagens_gratuitas": len(events) - len(billable),
        "receita_whatsapp": receita, "custo_meta_estimado": custo,
        "margem_estimada": round(receita - custo, 2),
        "por_escritorio": by_office, "por_categoria": by_cat, "por_periodo": by_period,
    }


@router.get("/settings/consumption")
async def get_consumption_settings(admin: dict = Depends(get_current_admin)):
    doc = await db.platform_settings.find_one({"id": "global"}, {"_id": 0})
    return {"alert_pcts": (doc or {}).get("consumption_alert_pcts") or [70, 80, 90]}


class ConsumptionSettingsIn(BaseModel):
    alert_pcts: list


@router.put("/settings/consumption")
async def put_consumption_settings(data: ConsumptionSettingsIn, admin: dict = Depends(get_current_admin)):
    pcts = [int(p) for p in data.alert_pcts if 1 <= int(p) <= 100]
    if not pcts:
        raise HTTPException(400, "Informe percentuais entre 1 e 100")
    await db.platform_settings.update_one({"id": "global"}, {"$set": {"consumption_alert_pcts": pcts}}, upsert=True)
    await admin_log(admin, "consumption_alerts_configured", pcts=pcts)
    return {"alert_pcts": pcts}


# ---------- RELATÓRIOS ----------

@router.get("/reports")
async def admin_reports(admin: dict = Depends(get_current_admin)):
    offices = await db.offices.find({}, {"_id": 0}).to_list(1000)
    plans = {p["id"]: p["name"] for p in await db.plans.find({}, {"_id": 0}).to_list(100)}
    por_plano = {}
    for o in offices:
        nome = plans.get(o.get("plan_id") or "", "Sem plano")
        por_plano[nome] = por_plano.get(nome, 0) + 1
    por_status = {}
    for o in offices:
        por_status[o.get("status", "active")] = por_status.get(o.get("status", "active"), 0) + 1
    msgs_in = await db.messages.count_documents({"sender": "client"})
    msgs_out_ravi = await db.messages.count_documents({"sender": "ravi"})
    msgs_out_human = await db.messages.count_documents({"sender": "user"})
    resolvidas = await db.audit_logs.count_documents({"event": "auto_resolved"})
    escaladas = await db.alerts.count_documents({"type": "intervention"})
    total_atendimentos = resolvidas + escaladas
    conns = await db.whatsapp_connections.find({}, {"_id": 0, "status": 1}).to_list(500)
    wa = {}
    for c in conns:
        wa[c.get("status", "?")] = wa.get(c.get("status", "?"), 0) + 1
    charges = await db.charges.find({}, {"_id": 0}).to_list(5000)
    receita = sum(c.get("valor_final", c["valor"]) for c in charges if c["status"] == "paid")
    changes = await db.plan_changes.find({}, {"_id": 0}).to_list(500)
    cancels = await db.cancellations.count_documents({})
    return {
        "escritorios": {"por_status": por_status, "por_plano": por_plano, "total": len(offices)},
        "utilizacao": {"processos": await db.processes.count_documents({}),
                       "clientes": await db.clients.count_documents({}),
                       "conversas": await db.conversations.count_documents({}),
                       "mensagens": msgs_in + msgs_out_ravi + msgs_out_human},
        "atendimento": {"recebidas": msgs_in, "respostas_ravi": msgs_out_ravi,
                        "respostas_humanas": msgs_out_human, "resolvidas": resolvidas,
                        "escaladas": escaladas},
        "whatsapp": wa,
        "financeiro": {"receita_recebida": round(receita, 2),
                       "cobrancas": len(charges),
                       "cancelamentos": cancels,
                       "upgrades": len([c for c in changes if c["direction"] == "upgrade"]),
                       "downgrades": len([c for c in changes if c["direction"] == "downgrade"])},
        "ia": {"perguntas": msgs_in, "respostas": msgs_out_ravi, "escalonamentos": escaladas,
               "taxa_resolucao": round(resolvidas / total_atendimentos * 100) if total_atendimentos else 0},
    }
