import os
import secrets
import hashlib
import logging
import uuid
from html import escape
from urllib.parse import urlparse
from datetime import datetime, timezone, timedelta
import httpx
import jwt
from fastapi import APIRouter, HTTPException, Request, Response, BackgroundTasks, Depends
from pydantic import BaseModel, EmailStr
from database import db
from security import (hash_password, verify_password, set_auth_cookies, public_user,
                      get_current_user, default_permissions, get_jwt_secret,
                      create_access_token)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])

EMAIL_BASE_URL = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip().rstrip("/") or "https://integrations.emergentagent.com"
EMAIL_KEY = os.environ.get("EMERGENT_EMAIL_KEY", "")
EMAIL_FROM_NAME = os.environ.get("EMAIL_FROM_NAME") or "RAVI"


class RegisterIn(BaseModel):
    name: str
    last_name: str = ""
    email: EmailStr
    password: str


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class OnboardingIn(BaseModel):
    office_name: str
    name: str = ""
    last_name: str = ""


class ForgotIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str
    password: str


def now():
    return datetime.now(timezone.utc)


async def get_office_payload(user: dict):
    office = None
    if user.get("office_id"):
        office = await db.offices.find_one({"id": user["office_id"]}, {"_id": 0})
    return office


@router.post("/register")
async def register(data: RegisterIn, response: Response):
    email = data.email.lower().strip()
    if len(data.password) < 6:
        raise HTTPException(400, "A senha deve ter pelo menos 6 caracteres")
    if not data.name.strip():
        raise HTTPException(400, "Informe seu nome")
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "Este e-mail já está cadastrado")
    user = {
        "id": uuid.uuid4().hex, "office_id": None,
        "name": data.name.strip(), "last_name": (data.last_name or "").strip(),
        "email": email, "password_hash": hash_password(data.password),
        "role": "SOCIO_ADMIN", "permissions": default_permissions("SOCIO_ADMIN"),
        "active": True, "onboarding_completed": False, "token_version": 0,
        "created_at": now().isoformat(),
    }
    await db.users.insert_one(user)
    set_auth_cookies(response, user)
    return {"user": public_user(user), "office": None}


@router.post("/login")
async def login(data: LoginIn, request: Request, response: Response):
    email = data.email.lower().strip()
    ip = request.client.host if request.client else "unknown"
    identifier = f"{ip}:{email}"
    attempts = await db.login_attempts.count_documents({
        "identifier": identifier,
        "created_at": {"$gt": (now() - timedelta(minutes=15)).isoformat()}})
    if attempts >= 5:
        raise HTTPException(429, "Muitas tentativas. Aguarde 15 minutos.")
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user or not verify_password(data.password, user.get("password_hash", "")):
        await db.login_attempts.insert_one({"identifier": identifier, "email": email,
                                            "created_at": now().isoformat()})
        raise HTTPException(401, "E-mail ou senha incorretos")
    if not user.get("active", True):
        raise HTTPException(403, "Usuário desativado. Fale com o sócio administrador.")
    await db.login_attempts.delete_many({"identifier": identifier})
    set_auth_cookies(response, user)
    return {"user": public_user(user), "office": await get_office_payload(user)}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return {"ok": True}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return {"user": public_user(user), "office": await get_office_payload(user)}


@router.post("/refresh")
async def refresh(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(401, "Sem sessão")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=["HS256"])
        if payload.get("type") != "refresh":
            raise HTTPException(401, "Token inválido")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Sessão expirada")
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0})
    if not user or payload.get("ver", 0) != user.get("token_version", 0) or not user.get("active", True):
        raise HTTPException(401, "Sessão expirada")
    response.set_cookie("access_token", create_access_token(user["id"], user["email"], user.get("token_version", 0)),
                        httponly=True, secure=True, samesite="none", max_age=900, path="/")
    return {"ok": True}


@router.post("/onboarding/complete")
async def complete_onboarding(data: OnboardingIn, user: dict = Depends(get_current_user)):
    if not data.office_name.strip():
        raise HTTPException(400, "Informe o nome do escritório")
    if user.get("onboarding_completed") and user.get("office_id"):
        return {"user": public_user(user), "office": await get_office_payload(user)}
    office = {
        "id": uuid.uuid4().hex, "name": data.office_name.strip(),
        "tone": "acolhedor", "minutes_per_attendance": 5.4,
        "welcome_message": "", "onboarding_completed": True,
        "created_at": now().isoformat(),
    }
    await db.offices.insert_one(office)
    updates = {"office_id": office["id"], "onboarding_completed": True}
    if data.name.strip():
        updates["name"] = data.name.strip()
        updates["last_name"] = (data.last_name or "").strip()
    await db.users.update_one({"id": user["id"]}, {"$set": updates})
    user.update(updates)
    office.pop("_id", None)
    return {"user": public_user(user), "office": office}


async def send_password_reset_email(to_email: str, token: str) -> bool:
    base = os.environ.get("FRONTEND_URL", "").rstrip("/")
    link = f"{base}/reset-password?token={token}"
    if not EMAIL_KEY or EMAIL_KEY.startswith("{") or not base.startswith("https://"):
        if urlparse(base).hostname in ("localhost", "127.0.0.1", "::1"):
            logger.warning("Email não configurado; link de reset: %s", link)
        else:
            logger.error("Reset de senha não configurado (EMERGENT_EMAIL_KEY / FRONTEND_URL)")
        return False
    brand = escape(EMAIL_FROM_NAME)
    html = (
        f'<table role="presentation" width="100%"><tr><td style="padding:24px;font-family:Arial,sans-serif">'
        f'<p>Recebemos uma solicitação para redefinir sua senha do {brand}.</p>'
        f'<p><a href="{escape(link)}">Redefinir minha senha</a></p>'
        f'<p>Este link expira em 1 hora e só pode ser usado uma vez. Se você não solicitou, ignore este e-mail.</p>'
        f'<p style="font-size:12px;color:#888">Enviado por {brand}. Nunca pedimos sua senha por e-mail.</p>'
        f'</td></tr></table>'
    )
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{EMAIL_BASE_URL}/api/v1/email/send",
                                     headers={"X-Email-Key": EMAIL_KEY},
                                     json={"to": [to_email], "subject": f"Redefina sua senha do {EMAIL_FROM_NAME}",
                                           "html": html, "from_name": EMAIL_FROM_NAME})
        resp.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Falha ao enviar e-mail de reset: {e}")
        return False


GENERIC_RESET_RESPONSE = {"message": "Se este e-mail estiver cadastrado, um link de redefinição foi enviado."}


@router.post("/forgot-password")
async def forgot_password(data: ForgotIn, background_tasks: BackgroundTasks):
    email = data.email.lower().strip()
    recent = await db.password_reset_requests.count_documents({
        "email": email, "created_at": {"$gt": (now() - timedelta(minutes=15)).isoformat()}})
    if recent >= 5:
        return GENERIC_RESET_RESPONSE
    await db.password_reset_requests.insert_one({"email": email, "created_at": now().isoformat()})
    user = await db.users.find_one({"email": email})
    if not user:
        return GENERIC_RESET_RESPONSE
    token = secrets.token_urlsafe(32)
    await db.password_reset_tokens.insert_one({
        "token_hash": hashlib.sha256(token.encode()).hexdigest(),
        "user_id": user["id"], "email": email,
        "expires_at": now() + timedelta(hours=1), "used": False})
    background_tasks.add_task(send_password_reset_email, user["email"], token)
    return GENERIC_RESET_RESPONSE


@router.post("/reset-password")
async def reset_password(data: ResetIn):
    h = hashlib.sha256(data.token.encode()).hexdigest()
    doc = await db.password_reset_tokens.find_one_and_update(
        {"token_hash": h, "used": False, "expires_at": {"$gt": now()}}, {"$set": {"used": True}})
    if not doc:
        raise HTTPException(400, "Link inválido ou expirado")
    if len(data.password) < 6:
        raise HTTPException(400, "A senha deve ter pelo menos 6 caracteres")
    await db.users.update_one({"id": doc["user_id"]},
                              {"$set": {"password_hash": hash_password(data.password)},
                               "$inc": {"token_version": 1}})
    await db.password_reset_tokens.delete_many({"user_id": doc["user_id"], "used": False})
    await db.login_attempts.delete_many({"email": doc["email"]})
    return {"message": "Senha redefinida com sucesso"}
