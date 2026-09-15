import uuid
import secrets
import os
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, Request, BackgroundTasks, UploadFile, File, Form
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
    cpf: Optional[str] = ""
    notes: Optional[str] = ""
    responsible_user_id: Optional[str] = None


@router.get("/clients")
async def list_clients(include_archived: bool = False, user: dict = Depends(require_permission("clientes"))):
    q = office_filter(user)
    if not include_archived:
        q["status"] = {"$ne": "arquivado"}
    clients = await db.clients.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
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
              "cpf": data.cpf or "", "notes": data.notes or "", "status": "ativo",
              "responsible_user_id": data.responsible_user_id or user["id"],
              "created_at": now_iso(), "updated_at": now_iso()}
    await db.clients.insert_one(client)
    await audit(user["office_id"], "client_created", actor=user["email"], client_id=client["id"])
    client.pop("_id", None)
    return client


@router.patch("/clients/{client_id}")
async def update_client(client_id: str, data: ClientIn, user: dict = Depends(require_permission("clientes"))):
    f = {**office_filter(user), "id": client_id}
    updates = {"name": data.name.strip(), "phone": data.phone,
               "phone_normalized": normalize_phone(data.phone), "email": data.email or "",
               "cpf": data.cpf or "", "notes": data.notes or "", "updated_at": now_iso()}
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
    await audit(user["office_id"], "client_deleted", actor=user["email"], client_id=client_id)
    return {"ok": True}


@router.get("/clients/{client_id}")
async def get_client(client_id: str, user: dict = Depends(require_permission("clientes"))):
    client = await db.clients.find_one({**office_filter(user), "id": client_id}, {"_id": 0})
    if not client:
        raise HTTPException(404, "Cliente não encontrado")
    client["processes"] = await db.processes.find(
        {"office_id": user["office_id"], "client_id": client_id}, {"_id": 0, "documentos": 0}).to_list(50)
    client["conversations"] = await db.conversations.find(
        {"office_id": user["office_id"], "client_id": client_id},
        {"_id": 0}).sort("last_message_at", -1).to_list(10)
    if client.get("responsible_user_id"):
        u = await db.users.find_one({"id": client["responsible_user_id"]}, {"_id": 0, "name": 1})
        client["responsible_name"] = u["name"] if u else None
    return client


@router.post("/clients/{client_id}/archive")
async def archive_client(client_id: str, user: dict = Depends(require_permission("clientes"))):
    client = await db.clients.find_one({**office_filter(user), "id": client_id}, {"_id": 0})
    if not client:
        raise HTTPException(404, "Cliente não encontrado")
    new_status = "arquivado" if client.get("status") != "arquivado" else "ativo"
    await db.clients.update_one({"id": client_id}, {"$set": {"status": new_status, "updated_at": now_iso()}})
    await audit(user["office_id"], "client_archived" if new_status == "arquivado" else "client_unarchived",
                actor=user["email"], client_id=client_id)
    return {"ok": True, "status": new_status}


# ---------- PROCESSOS ----------

class CobrancaIn(BaseModel):
    valor: float
    data_vencimento: str
    descricao: Optional[str] = ""


class ProcessIn(BaseModel):
    number: str
    client_id: Optional[str] = None
    new_client_name: Optional[str] = None
    new_client_phone: Optional[str] = None
    status: Optional[str] = "Em andamento"
    ultima_movimentacao: Optional[str] = ""
    notes: Optional[str] = ""
    title: Optional[str] = ""
    subject: Optional[str] = ""
    valor_causa: Optional[float] = None
    forma_pagamento: Optional[str] = ""
    cobrancas: Optional[list] = None


def _cobranca_doc(c) -> dict:
    return {"id": uuid.uuid4().hex, "valor": float(c["valor"]),
            "data_vencimento": c["data_vencimento"], "descricao": c.get("descricao") or "",
            "status": "pendente", "lembrete_5d_em": None, "lembrete_dia_em": None}


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
    client_id = data.client_id
    if not client_id and data.new_client_name and data.new_client_phone:
        norm = normalize_phone(data.new_client_phone)
        if not norm:
            raise HTTPException(400, "WhatsApp do novo cliente inválido")
        existing = await db.clients.find_one({"office_id": user["office_id"], "phone_normalized": norm}, {"_id": 0})
        if existing:
            client_id = existing["id"]
        else:
            client_id = uuid.uuid4().hex
            await db.clients.insert_one({
                "id": client_id, "office_id": user["office_id"], "name": data.new_client_name.strip(),
                "phone": data.new_client_phone, "phone_normalized": norm, "email": "",
                "notes": "Criado no cadastro do processo", "status": "ativo",
                "responsible_user_id": user["id"], "created_at": now_iso()})
            await audit(user["office_id"], "client_created", actor=user["email"], client_id=client_id)
    limite_alerta = False
    office = await db.offices.find_one({"id": user["office_id"]}, {"_id": 0, "plan_id": 1})
    if office and office.get("plan_id"):
        plan = await db.plans.find_one({"id": office["plan_id"]}, {"_id": 0})
        if plan and plan.get("process_limit"):
            count = await db.processes.count_documents({"office_id": user["office_id"]})
            limit = plan["process_limit"]
            hard_limit = int(limit * (1 + (plan.get("overage_pct", 10)) / 100))
            if count >= hard_limit:
                raise HTTPException(402, f"Limite do plano excedido ({count}/{limit} processos). Fale com o suporte RAVI para ampliar seu plano.")
            limite_alerta = count >= limit
    proc = {
        "id": uuid.uuid4().hex, "office_id": user["office_id"],
        "number": data.number.strip(), "client_id": client_id,
        "status": data.status or "Em andamento",
        "ultima_movimentacao": data.ultima_movimentacao or "",
        "notes": data.notes or "", "movimentacoes": [], "partes": [],
        "title": data.title or "", "subject": data.subject or "",
        "restricted": False, "last_movement_at": data.ultima_movimentacao or "",
        "fontes": fontes, "acesso_restrito": False, "documentos": [],
        "valor_causa": data.valor_causa, "forma_pagamento": data.forma_pagamento or "",
        "cobrancas": [_cobranca_doc(c) for c in (data.cobrancas or []) if c.get("valor") and c.get("data_vencimento")],
        "created_at": now_iso(),
    }
    if parsed:
        proc.update({k: parsed[k] for k in ("segmento", "tribunal", "unidade_origem", "ano", "numero_formatado")})
        proc["court"] = parsed["tribunal"]
        proc["unit"] = parsed["unidade_origem"]
        fontes.append("Número CNJ identificado automaticamente")
    if data.ultima_movimentacao:
        proc["movimentacoes"] = [{"data": data.ultima_movimentacao,
                                  "descricao": "Movimentação registrada pelo escritório",
                                  "fonte": "Informação cadastrada pelo advogado"}]
    await db.processes.insert_one(proc)
    await audit(user["office_id"], "process_created", actor=user["email"], process_id=proc["id"])
    proc.pop("_id", None)
    proc["limite_alerta"] = limite_alerta
    return proc


@router.get("/processes/{process_id}")
async def get_process(process_id: str, user: dict = Depends(require_permission("processos"))):
    proc = await db.processes.find_one({**office_filter(user), "id": process_id}, {"_id": 0})
    if not proc:
        raise HTTPException(404, "Processo não encontrado")
    if proc.get("client_id"):
        proc["client"] = await db.clients.find_one(
            {"id": proc["client_id"], "office_id": user["office_id"]}, {"_id": 0})
    proc["conversations_count"] = await db.conversations.count_documents(
        {"office_id": user["office_id"], "process_id": process_id})
    for d in proc.get("documentos", []):
        d.pop("texto", None)
    return proc


@router.post("/processes/import-pdf")
async def import_process_pdf(file: UploadFile = File(...), client_id: Optional[str] = Form(None),
                             user: dict = Depends(require_permission("processos"))):
    """Importação inteligente: lê o PDF, identifica número CNJ, tribunal, partes, movimentações
    e status. Nunca inventa: campos não identificados são reportados explicitamente."""
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(400, "Apenas arquivos PDF")
    data = await file.read()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(400, "PDF deve ter no máximo 10MB")
    import io as _io
    from pypdf import PdfReader
    texto = ""
    try:
        reader = PdfReader(_io.BytesIO(data))
        texto = "\n".join((p.extract_text() or "") for p in reader.pages)
    except Exception:
        raise HTTPException(400, "Não consegui ler o conteúdo deste PDF")
    if not texto.strip():
        raise HTTPException(400, "Não consegui ler o texto deste PDF (pode ser digitalizado como imagem)")

    import re as _re
    from ai import extract_process_from_pdf
    extracted = await extract_process_from_pdf(texto)
    cnj_found = None
    for m in _re.finditer(r"\d{7}-?\d{2}\.?\d{4}\.?\d\.?\d{2}\.?\d{4}", texto):
        parsed = parse_cnj(m.group(0))
        if parsed:
            cnj_found = parsed
            break
    numero = (extracted.get("numero_cnj") or "").strip()
    if cnj_found:
        numero = cnj_found["numero_formatado"]
    if not numero:
        numero = f"SEM-NUMERO-{uuid.uuid4().hex[:8]}"

    restricted = bool(extracted.get("restricted"))
    partes = [{"tipo": p.get("tipo", "outro"), "nome": p.get("nome", "")}
              for p in (extracted.get("partes") or []) if p.get("nome")]
    movs = [{"data": m.get("data", ""), "descricao": m.get("descricao", ""),
             "fonte": "Documento fornecido pelo escritório"}
            for m in (extracted.get("movimentacoes") or []) if m.get("descricao")]
    last_mov = extracted.get("ultima_movimentacao") or (movs[0]["data"] if movs else "")

    nao_identificados = []
    for campo, valor in [("número CNJ", numero if not numero.startswith("SEM-NUMERO") else None),
                         ("tribunal", extracted.get("tribunal") or (cnj_found or {}).get("tribunal")),
                         ("assunto", extracted.get("assunto")), ("partes", partes or None),
                         ("movimentações", movs or None), ("status", extracted.get("status"))]:
        if not valor:
            nao_identificados.append(campo)

    proc = {
        "id": uuid.uuid4().hex, "office_id": user["office_id"],
        "number": numero, "numero_formatado": numero if not numero.startswith("SEM-NUMERO") else "",
        "client_id": client_id or None,
        "title": extracted.get("titulo") or "", "subject": extracted.get("assunto") or "",
        "status": "Restrito (segredo de justiça)" if restricted else (extracted.get("status") or "Em andamento"),
        "restricted": restricted, "acesso_restrito": restricted,
        "tribunal": (cnj_found or {}).get("tribunal") or extracted.get("tribunal"),
        "court": (cnj_found or {}).get("tribunal") or extracted.get("tribunal"),
        "segmento": (cnj_found or {}).get("segmento"),
        "unidade_origem": (cnj_found or {}).get("unidade_origem"),
        "unit": (cnj_found or {}).get("unidade_origem"),
        "ano": (cnj_found or {}).get("ano"),
        "ultima_movimentacao": last_mov, "last_movement_at": last_mov,
        "notes": "", "movimentacoes": movs, "partes": partes,
        "fontes": ["Documento fornecido pelo escritório"] + (["Número CNJ identificado automaticamente"] if cnj_found else []),
        "documentos": [], "valor_causa": None, "forma_pagamento": "", "cobrancas": [],
        "created_at": now_iso(),
    }
    from storage import put_object
    result = put_object(f"ravi/processos/{user['office_id']}/{uuid.uuid4().hex}.pdf", data, "application/pdf")
    proc["documentos"] = [{"id": uuid.uuid4().hex, "filename": file.filename, "storage_path": result["path"],
                           "size": result.get("size", len(data)), "texto": texto[:8000],
                           "uploaded_by": user["email"], "created_at": now_iso()}]
    await db.processes.insert_one(proc)
    await audit(user["office_id"], "process_imported_pdf", actor=user["email"],
                process_id=proc["id"], restricted=restricted, nao_identificados=nao_identificados)
    proc.pop("_id", None)
    for d in proc["documentos"]:
        d.pop("texto", None)
    return {"process": proc, "nao_identificados": nao_identificados, "restricted": restricted}


# ---------- PROCESSOS: DOCUMENTOS + FINANCEIRO ----------

@router.post("/processes/{process_id}/document")
async def upload_process_document(process_id: str, file: UploadFile = File(...),
                                  user: dict = Depends(require_permission("processos"))):
    proc = await db.processes.find_one({**office_filter(user), "id": process_id}, {"_id": 0})
    if not proc:
        raise HTTPException(404, "Processo não encontrado")
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(400, "Apenas arquivos PDF")
    data = await file.read()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(400, "PDF deve ter no máximo 10MB")
    from storage import put_object
    result = put_object(f"ravi/processos/{user['office_id']}/{uuid.uuid4().hex}.pdf", data, "application/pdf")
    texto = ""
    try:
        import io as _io
        from pypdf import PdfReader
        reader = PdfReader(_io.BytesIO(data))
        texto = "\n".join((p.extract_text() or "") for p in reader.pages)[:8000]
    except Exception:
        texto = ""
    doc = {"id": uuid.uuid4().hex, "filename": file.filename, "storage_path": result["path"],
           "size": result.get("size", len(data)), "texto": texto,
           "uploaded_by": user["email"], "created_at": now_iso()}
    push = {"documentos": doc}
    if "Documento fornecido pelo escritório" not in (proc.get("fontes") or []):
        push["fontes"] = "Documento fornecido pelo escritório"
    await db.processes.update_one({"id": process_id}, {"$push": push})
    await audit(user["office_id"], "process_document_uploaded", actor=user["email"],
                process_id=process_id, filename=file.filename, texto_extraido=bool(texto))
    out = {k: v for k, v in doc.items() if k != "texto"}
    return {"ok": True, "document": out, "texto_extraido": bool(texto)}


@router.get("/processes/{process_id}/document/{doc_id}")
async def download_process_document(process_id: str, doc_id: str,
                                    user: dict = Depends(require_permission("processos"))):
    proc = await db.processes.find_one({**office_filter(user), "id": process_id}, {"_id": 0})
    doc = next((d for d in (proc or {}).get("documentos", []) if d["id"] == doc_id), None)
    if not doc:
        raise HTTPException(404, "Documento não encontrado")
    from storage import get_object
    from fastapi.responses import Response
    data, _ = get_object(doc["storage_path"])
    return Response(content=data, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{doc["filename"]}"'})


class BillingIn(BaseModel):
    valor_causa: Optional[float] = None
    forma_pagamento: Optional[str] = None
    cobrancas: Optional[list] = None


@router.patch("/processes/{process_id}")
async def update_process_billing(process_id: str, data: BillingIn,
                                 user: dict = Depends(require_permission("processos"))):
    proc = await db.processes.find_one({**office_filter(user), "id": process_id}, {"_id": 0})
    if not proc:
        raise HTTPException(404, "Processo não encontrado")
    updates = {}
    if data.valor_causa is not None:
        updates["valor_causa"] = data.valor_causa
    if data.forma_pagamento is not None:
        updates["forma_pagamento"] = data.forma_pagamento
    if data.cobrancas is not None:
        existing = {c["id"]: c for c in proc.get("cobrancas", [])}
        merged = []
        for raw in data.cobrancas:
            old = existing.get(raw.get("id", ""))
            if old:
                old.update({"valor": float(raw.get("valor", old["valor"])),
                            "data_vencimento": raw.get("data_vencimento", old["data_vencimento"]),
                            "descricao": raw.get("descricao", old.get("descricao", ""))})
                merged.append(old)
            elif raw.get("valor") and raw.get("data_vencimento"):
                merged.append(_cobranca_doc(raw))
        updates["cobrancas"] = merged
    if updates:
        await db.processes.update_one({"id": process_id}, {"$set": updates})
        await audit(user["office_id"], "process_billing_updated", actor=user["email"], process_id=process_id)
    return await db.processes.find_one({"id": process_id}, {"_id": 0, "documentos.texto": 0})


@router.post("/processes/{process_id}/cobrancas/{cob_id}/pago")
async def mark_cobranca_paid(process_id: str, cob_id: str,
                             user: dict = Depends(require_permission("processos"))):
    res = await db.processes.update_one(
        {**office_filter(user), "id": process_id, "cobrancas.id": cob_id},
        {"$set": {"cobrancas.$.status": "pago"}})
    if not res.matched_count:
        raise HTTPException(404, "Cobrança não encontrada")
    await audit(user["office_id"], "cobranca_paid", actor=user["email"], process_id=process_id)
    return {"ok": True}


# ---------- CRON: LEMBRETES DE COBRANÇA ----------

@router.post("/cron/billing-reminders")
async def cron_billing_reminders(request: Request, background_tasks: BackgroundTasks):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    import hmac as _hmac
    secret = os.environ.get("WEBHOOK_CRON_SECRET", "")
    auth = request.headers.get("Authorization", "")
    token = auth[7:] if auth.startswith("Bearer ") else ""
    if not secret or not _hmac.compare_digest(token, secret):
        raise HTTPException(401, "Não autorizado")
    try:
        envelope = await request.json()
    except Exception:
        raise HTTPException(400, "Envelope inválido")
    run_id = envelope.get("run_id") or request.headers.get("X-Webhook-Id") or uuid.uuid4().hex
    if await db.cron_runs.find_one({"run_id": run_id}):
        return {"ok": True, "duplicate": True}
    await db.cron_runs.insert_one({"run_id": run_id, "job": "billing-reminders", "created_at": now_iso()})
    background_tasks.add_task(send_billing_reminders)
    return {"ok": True}


@router.post("/cron/backup-database")
async def cron_backup_database(request: Request, background_tasks: BackgroundTasks):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    import hmac as _hmac
    secret = os.environ.get("WEBHOOK_CRON_SECRET", "")
    auth = request.headers.get("Authorization", "")
    token = auth[7:] if auth.startswith("Bearer ") else ""
    if not secret or not _hmac.compare_digest(token, secret):
        raise HTTPException(401, "Não autorizado")
    try:
        envelope = await request.json()
    except Exception:
        raise HTTPException(400, "Envelope inválido")
    run_id = envelope.get("run_id") or request.headers.get("X-Webhook-Id") or uuid.uuid4().hex
    if await db.cron_runs.find_one({"run_id": run_id}):
        return {"ok": True, "duplicate": True}
    await db.cron_runs.insert_one({"run_id": run_id, "job": "backup-database", "created_at": now_iso()})
    from backup import run_backup
    background_tasks.add_task(run_backup)
    return {"ok": True, "started": True}


async def send_billing_reminders():
    from zoneinfo import ZoneInfo
    from datetime import date as _date
    today = datetime.now(ZoneInfo("America/Sao_Paulo")).date()
    async for proc in db.processes.find({"cobrancas": {"$elemMatch": {"status": "pendente"}}}):
        client = None
        if proc.get("client_id"):
            client = await db.clients.find_one({"id": proc["client_id"]}, {"_id": 0})
        if not client:
            continue
        connection = await db.whatsapp_connections.find_one(
            {"office_id": proc["office_id"], "status": "connected"}, {"_id": 0})
        for cob in proc.get("cobrancas", []):
            if cob.get("status") != "pendente":
                continue
            try:
                venc = _date.fromisoformat(cob["data_vencimento"])
            except Exception:
                continue
            dias = (venc - today).days
            flag, prazo = None, None
            if 0 < dias <= 5 and not cob.get("lembrete_5d_em"):
                flag, prazo = "lembrete_5d_em", f"vence em {dias} dias ({venc.strftime('%d/%m/%Y')})"
            elif dias == 0 and not cob.get("lembrete_dia_em"):
                flag, prazo = "lembrete_dia_em", "vence hoje"
            if not flag:
                continue
            first = client["name"].split()[0]
            valor = f"R$ {cob['valor']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            desc = f" ({cob['descricao']})" if cob.get("descricao") else ""
            text = (f"Olá, {first}! Passando para lembrar que a parcela de {valor}{desc} "
                    f"referente ao seu processo {prazo}. ")
            if proc.get("forma_pagamento"):
                text += f"Forma de pagamento combinada: {proc['forma_pagamento']}. "
            text += "Qualquer dúvida, é só responder por aqui."
            conv = await db.conversations.find_one(
                {"office_id": proc["office_id"], "phone_normalized": client["phone_normalized"],
                 "status": {"$ne": "archived"}}, {"_id": 0})
            if not conv:
                conv = {"id": uuid.uuid4().hex, "office_id": proc["office_id"],
                        "phone_normalized": client["phone_normalized"], "client_id": client["id"],
                        "process_id": proc["id"], "status": "active", "risk_level": "green",
                        "ai_enabled": True, "human_control": False, "assigned_user_id": None,
                        "created_at": now_iso(), "last_message_at": now_iso()}
                await db.conversations.insert_one(conv)
            delivered = False
            if connection and connection.get("access_token"):
                try:
                    await graph_send_text(connection, client["phone_normalized"], text)
                    delivered = True
                except Exception:
                    delivered = False
            if not delivered and connection:
                # Falha de entrega com conexão ativa (ex: token expirado): não marca flag — o cron tenta de novo amanhã
                await audit(proc["office_id"], "billing_reminder_failed", client_id=client["id"],
                            process_id=proc["id"], cobranca_id=cob["id"], tipo=flag)
                continue
            await save_message(proc["office_id"], conv["id"], "ravi", text,
                               risk_level="green", delivered=delivered)
            from usage import record_usage_event
            await record_usage_event(proc["office_id"], "outbound", "UTILITY", True,
                                     connection_id=(connection or {}).get("id"),
                                     conversation_id=conv["id"])
            await db.processes.update_one({"id": proc["id"], "cobrancas.id": cob["id"]},
                                          {"$set": {f"cobrancas.$.{flag}": now_iso()}})
            await audit(proc["office_id"], "billing_reminder_sent", client_id=client["id"],
                        process_id=proc["id"], cobranca_id=cob["id"], tipo=flag, delivered=delivered)


# ---------- CONVERSAS ----------

@router.get("/conversations")
async def list_conversations(user: dict = Depends(require_permission("conversas"))):
    convs = await db.conversations.find(office_filter(user), {"_id": 0}).sort("last_message_at", -1).to_list(200)
    client_ids = list({c["client_id"] for c in convs if c.get("client_id")})
    user_ids = list({c["assigned_user_id"] for c in convs if c.get("assigned_user_id")})
    clients = {}
    if client_ids:
        clients = {c["id"]: c for c in await db.clients.find(
            {"office_id": user["office_id"], "id": {"$in": client_ids}},
            {"_id": 0, "id": 1, "name": 1, "phone": 1}).to_list(500)}
    users = {}
    if user_ids:
        users = {u["id"]: u["name"] for u in await db.users.find(
            {"office_id": user["office_id"], "id": {"$in": user_ids}},
            {"_id": 0, "id": 1, "name": 1}).to_list(200)}
    for c in convs:
        c["client"] = clients.get(c.get("client_id"))
        c["assigned_user_name"] = users.get(c.get("assigned_user_id"))
    return convs


@router.get("/conversations/{conv_id}")
async def get_conversation(conv_id: str, user: dict = Depends(require_permission("conversas"))):
    conv = await db.conversations.find_one({**office_filter(user), "id": conv_id}, {"_id": 0})
    if not conv:
        raise HTTPException(404, "Conversa não encontrada")
    conv["messages"] = await db.messages.find({"conversation_id": conv_id}, {"_id": 0}).sort("created_at", 1).to_list(200)
    conv["client"] = None
    if conv.get("client_id"):
        conv["client"] = await db.clients.find_one(
            {"id": conv["client_id"], "office_id": user["office_id"]}, {"_id": 0})
    conv["process"] = None
    if conv.get("process_id"):
        conv["process"] = await db.processes.find_one(
            {"id": conv["process_id"], "office_id": user["office_id"]}, {"_id": 0})
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
    from usage import record_usage_event
    await record_usage_event(user["office_id"], "outbound", "SERVICE", False,
                             connection_id=(connection or {}).get("id"), conversation_id=conv_id)
    msg.pop("_id", None)
    await audit(user["office_id"], "human_reply", actor=user["email"],
                conversation_id=conv_id, delivered=delivered)
    return msg


@router.post("/conversations/{conv_id}/pause-ravi")
async def pause_ravi(conv_id: str, user: dict = Depends(require_permission("conversas"))):
    res = await db.conversations.update_one({**office_filter(user), "id": conv_id},
                                      {"$set": {"ai_enabled": False, "state": "PAUSED", "updated_at": now_iso()}})
    if not res.matched_count:
        raise HTTPException(404, "Conversa não encontrada")
    await save_message(user["office_id"], conv_id, "system", "Ravi pausado pelo escritório.")
    await audit(user["office_id"], "ravi_paused", actor=user["email"], conversation_id=conv_id)
    return {"ok": True, "ai_enabled": False, "state": "PAUSED"}


@router.post("/conversations/{conv_id}/takeover")
async def takeover(conv_id: str, user: dict = Depends(require_permission("conversas"))):
    res = await db.conversations.update_one({**office_filter(user), "id": conv_id},
                                      {"$set": {"human_control": True, "ai_enabled": False,
                                                "state": "WAITING_HUMAN", "updated_at": now_iso(),
                                                "assigned_user_id": user["id"], "status": "active"}})
    if not res.matched_count:
        raise HTTPException(404, "Conversa não encontrada")
    await save_message(user["office_id"], conv_id, "system",
                       f"Dr(a). {user.get('name', '')} assumiu o atendimento.")
    await audit(user["office_id"], "human_takeover", actor=user["email"], conversation_id=conv_id)
    return {"ok": True, "human_control": True, "state": "WAITING_HUMAN"}


@router.post("/conversations/{conv_id}/resume-ravi")
async def resume_ravi(conv_id: str, user: dict = Depends(require_permission("conversas"))):
    res = await db.conversations.update_one({**office_filter(user), "id": conv_id},
                                      {"$set": {"human_control": False, "ai_enabled": True,
                                                "state": "AI_HANDLING", "updated_at": now_iso(),
                                                "assigned_user_id": None, "risk_level": "green"}})
    if not res.matched_count:
        raise HTTPException(404, "Conversa não encontrada")
    await save_message(user["office_id"], conv_id, "system", "Ravi retomou o atendimento automático.")
    await audit(user["office_id"], "ravi_resumed", actor=user["email"], conversation_id=conv_id)
    return {"ok": True, "ai_enabled": True, "human_control": False, "state": "AI_HANDLING"}


@router.post("/conversations/{conv_id}/resolve")
async def resolve_conversation(conv_id: str, user: dict = Depends(require_permission("conversas"))):
    res = await db.conversations.update_one({**office_filter(user), "id": conv_id},
                                      {"$set": {"state": "RESOLVED", "updated_at": now_iso()}})
    if not res.matched_count:
        raise HTTPException(404, "Conversa não encontrada")
    await save_message(user["office_id"], conv_id, "system",
                       f"Conversa marcada como resolvida por {user.get('name', '')}.")
    await create_alert(user["office_id"], "resolved", "Conversa resolvida",
                       f"Resolvida por {user.get('name', '')}.", conversation_id=conv_id)
    await db.alerts.update_many({"office_id": user["office_id"], "conversation_id": conv_id,
                                 "status": "open"},
                                {"$set": {"status": "resolved", "resolved_by": user["email"],
                                          "resolved_at": now_iso()}})
    await audit(user["office_id"], "conversation_resolved", actor=user["email"], conversation_id=conv_id)
    return {"ok": True, "state": "RESOLVED"}


class LinkClientIn(BaseModel):
    client_id: Optional[str] = None
    new_client_name: Optional[str] = None


@router.post("/conversations/{conv_id}/link-client")
async def link_client(conv_id: str, data: LinkClientIn, user: dict = Depends(require_permission("conversas"))):
    conv = await db.conversations.find_one({**office_filter(user), "id": conv_id}, {"_id": 0})
    if not conv:
        raise HTTPException(404, "Conversa não encontrada")
    client_id = data.client_id
    if client_id:
        if not await db.clients.find_one({**office_filter(user), "id": client_id}, {"_id": 0, "id": 1}):
            raise HTTPException(404, "Cliente não encontrado")
    else:
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
    client_ids = list({a["client_id"] for a in alerts if a.get("client_id")})
    clients = {}
    if client_ids:
        clients = {c["id"]: c["name"] for c in await db.clients.find(
            {"office_id": user["office_id"], "id": {"$in": client_ids}},
            {"_id": 0, "id": 1, "name": 1}).to_list(500)}
    for a in alerts:
        a["client_name"] = clients.get(a.get("client_id"))
    return alerts


@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: str, user: dict = Depends(require_permission("alertas"))):
    res = await db.alerts.update_one({**office_filter(user), "id": alert_id},
                                     {"$set": {"status": "resolved", "resolved_by": user["email"],
                                               "resolved_at": now_iso()}})
    if not res.matched_count:
        raise HTTPException(404, "Alerta não encontrado")
    await audit(user["office_id"], "alert_resolved", actor=user["email"], alert_id=alert_id)
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
        await audit(user["office_id"], "office_settings_updated", actor=user["email"],
                    campos=list(updates.keys()))
    return await db.offices.find_one({"id": user["office_id"]}, {"_id": 0, "demo_metrics": 0})


# ---------- SUPORTE (lado do escritório) ----------

class TicketIn(BaseModel):
    categoria: str
    assunto: str
    descricao: str
    prioridade: Optional[str] = "media"


@router.post("/support/tickets")
async def create_ticket(data: TicketIn, user: dict = Depends(get_current_user)):
    if not data.assunto.strip() or not data.descricao.strip():
        raise HTTPException(400, "Informe assunto e descrição")
    ticket = {"id": uuid.uuid4().hex, "office_id": user["office_id"],
              "user_email": user["email"], "user_name": user.get("name", ""),
              "categoria": data.categoria, "assunto": data.assunto.strip(),
              "descricao": data.descricao.strip(), "prioridade": data.prioridade,
              "status": "aberto", "responsavel": None, "created_at": now_iso()}
    await db.tickets.insert_one(ticket)
    await audit(user["office_id"], "ticket_created", actor=user["email"], assunto=ticket["assunto"])
    ticket.pop("_id", None)
    return ticket


@router.get("/support/tickets")
async def list_my_tickets(user: dict = Depends(get_current_user)):
    return await db.tickets.find(office_filter(user), {"_id": 0}).sort("created_at", -1).to_list(100)


# ---------- IMPERSONATION (encerrar sessão de suporte) ----------

class ImpEndIn(BaseModel):
    log_id: str


@router.post("/impersonation/end")
async def impersonation_end(data: ImpEndIn, user: dict = Depends(get_current_user)):
    await db.admin_logs.update_one({"id": data.log_id, "action": "impersonation_start"},
                                   {"$set": {"ended_at": now_iso()}})
    return {"ok": True}


# ---------- AUDITORIA ----------

@router.get("/audit")
async def list_audit(user: dict = Depends(require_permission("configuracoes"))):
    return await db.audit_logs.find(office_filter(user), {"_id": 0}).sort("created_at", -1).to_list(100)
