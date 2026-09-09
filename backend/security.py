import os
import bcrypt
import jwt
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, Request, Depends
from database import db

JWT_ALGORITHM = "HS256"

MODULES = [
    "dashboard", "clientes", "processos", "conversas", "alertas",
    "equipe", "configuracoes", "whatsapp", "documentos", "ia", "financeiro",
]

ROLE_DEFAULTS = {
    "SOCIO_ADMIN": {m: True for m in MODULES},
    "ADVOGADO_ASSOCIADO": {
        "dashboard": True, "clientes": True, "processos": True, "conversas": True,
        "alertas": True, "equipe": False, "configuracoes": False, "whatsapp": True,
        "documentos": True, "ia": True, "financeiro": False,
    },
    "ESTAGIARIO": {
        "dashboard": True, "clientes": True, "processos": True, "conversas": True,
        "alertas": True, "equipe": False, "configuracoes": False, "whatsapp": False,
        "documentos": True, "ia": False, "financeiro": False,
    },
    "SECRETARIA_ATENDIMENTO": {
        "dashboard": True, "clientes": True, "processos": False, "conversas": True,
        "alertas": True, "equipe": False, "configuracoes": False, "whatsapp": False,
        "documentos": False, "ia": False, "financeiro": False,
    },
}

ROLE_LABELS = {
    "SOCIO_ADMIN": "Sócio Administrador",
    "ADVOGADO_ASSOCIADO": "Advogado Associado",
    "ESTAGIARIO": "Estagiário",
    "SECRETARIA_ATENDIMENTO": "Secretária/Atendimento",
}


def default_permissions(role: str) -> dict:
    return dict(ROLE_DEFAULTS.get(role, ROLE_DEFAULTS["ESTAGIARIO"]))


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def get_jwt_secret() -> str:
    return os.environ["JWT_SECRET"]


def create_access_token(user_id: str, email: str, token_version: int = 0) -> str:
    payload = {"sub": user_id, "email": email, "ver": token_version,
               "exp": datetime.now(timezone.utc) + timedelta(minutes=15), "type": "access"}
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str, token_version: int = 0) -> str:
    payload = {"sub": user_id, "ver": token_version,
               "exp": datetime.now(timezone.utc) + timedelta(days=7), "type": "refresh"}
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def set_auth_cookies(response, user: dict):
    ver = user.get("token_version", 0)
    response.set_cookie("access_token", create_access_token(user["id"], user["email"], ver),
                        httponly=True, secure=True, samesite="none", max_age=900, path="/")
    response.set_cookie("refresh_token", create_refresh_token(user["id"], ver),
                        httponly=True, secure=True, samesite="none", max_age=604800, path="/")


def public_user(user: dict) -> dict:
    return {
        "id": user["id"], "name": user.get("name", ""), "last_name": user.get("last_name", ""),
        "email": user["email"], "role": user["role"],
        "permissions": user.get("permissions") or default_permissions(user["role"]),
        "active": user.get("active", True),
        "office_id": user.get("office_id"),
        "onboarding_completed": user.get("onboarding_completed", False),
    }


async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(401, "Não autenticado")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(401, "Tipo de token inválido")
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Sessão expirada")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Token inválido")
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0})
    if not user:
        raise HTTPException(401, "Usuário não encontrado")
    if payload.get("ver", 0) != user.get("token_version", 0):
        raise HTTPException(401, "Sessão expirada")
    if not user.get("active", True):
        raise HTTPException(403, "Usuário desativado")
    return user


def require_permission(module: str):
    async def checker(user: dict = Depends(get_current_user)):
        if user["role"] == "SOCIO_ADMIN":
            return user
        perms = user.get("permissions") or default_permissions(user["role"])
        if not perms.get(module):
            raise HTTPException(403, "Sem permissão para este módulo")
        return user
    return checker


async def require_socio(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != "SOCIO_ADMIN":
        raise HTTPException(403, "Apenas o sócio administrador")
    return user


def office_filter(user: dict) -> dict:
    """Isolamento multi-tenant: toda consulta passa por aqui."""
    if not user.get("office_id"):
        raise HTTPException(400, "Escritório não configurado")
    return {"office_id": user["office_id"]}


async def audit(office_id: str, event: str, actor: str = "ravi", **details):
    await db.audit_logs.insert_one({
        "id": __import__("uuid").uuid4().hex,
        "office_id": office_id, "event": event, "actor": actor,
        "details": details, "created_at": datetime.now(timezone.utc).isoformat(),
    })
