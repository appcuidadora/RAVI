import os
import re
import logging
import httpx

logger = logging.getLogger(__name__)


def graph_base() -> str:
    return f"https://graph.facebook.com/{os.environ.get('META_GRAPH_VERSION', 'v25.0')}"


def meta_configured() -> bool:
    return bool(os.environ.get("META_APP_ID") and os.environ.get("META_APP_SECRET"))


async def exchange_code_for_token(code: str) -> str:
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get(f"{graph_base()}/oauth/access_token", params={
            "client_id": os.environ["META_APP_ID"],
            "client_secret": os.environ["META_APP_SECRET"],
            "code": code,
        })
        if r.is_error:
            raise ValueError(f"Falha na troca do código: {r.text}")
        return r.json()["access_token"]


async def subscribe_waba(waba_id: str, token: str) -> bool:
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(f"{graph_base()}/{waba_id}/subscribed_apps",
                         headers={"Authorization": f"Bearer {token}"})
        return not r.is_error


async def fetch_phone_display(phone_number_id: str, token: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get(f"{graph_base()}/{phone_number_id}",
                            params={"fields": "display_phone_number"},
                            headers={"Authorization": f"Bearer {token}"})
            if not r.is_error:
                return r.json().get("display_phone_number", "")
    except Exception as e:
        logger.error(f"fetch_phone_display: {e}")
    return ""


async def resolve_waba_and_phone(user_token: str, intended_phone: str = None) -> tuple:
    """Pós Embedded Signup: descobre a WABA (via debug_token) e o phone_number_id.
    Se o advogado informou um número, prioriza o telefone correspondente."""
    app_id = os.environ["META_APP_ID"]
    app_secret = os.environ["META_APP_SECRET"]
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get(f"{graph_base()}/debug_token", params={"input_token": user_token},
                        headers={"Authorization": f"Bearer {app_id}|{app_secret}"})
        r.raise_for_status()
        waba_ids = []
        for gs in (r.json().get("data") or {}).get("granular_scopes", []):
            if gs.get("scope") in ("whatsapp_business_management", "whatsapp_business_messaging"):
                waba_ids.extend(gs.get("target_ids") or [])
        if not waba_ids:
            return None, None, ""
        waba_id = waba_ids[0]
        r2 = await c.get(f"{graph_base()}/{waba_id}/phone_numbers",
                         headers={"Authorization": f"Bearer {user_token}"})
        r2.raise_for_status()
        phones = r2.json().get("data", [])
        if not phones:
            return waba_id, None, ""
        chosen = phones[0]
        if intended_phone:
            for p in phones:
                digits = re.sub(r"\D", "", p.get("display_phone_number", ""))
                if digits.endswith(intended_phone[-8:]):
                    chosen = p
                    break
        return waba_id, chosen["id"], chosen.get("display_phone_number", "")


async def get_media_bytes(media_id: str, token: str) -> tuple:
    """Baixa mídia (áudio/imagem) da Meta: primeiro resolve a URL, depois baixa com o token."""
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as c:
        r = await c.get(f"{graph_base()}/{media_id}", headers={"Authorization": f"Bearer {token}"})
        r.raise_for_status()
        info = r.json()
        r2 = await c.get(info["url"], headers={"Authorization": f"Bearer {token}"})
        r2.raise_for_status()
        return r2.content, info.get("mime_type", "audio/ogg")


async def graph_send_text(connection: dict, to: str, body: str) -> dict:
    """Envia mensagem de texto via Cloud API. Retorna resposta da Meta ou lança exceção."""
    payload = {
        "messaging_product": "whatsapp", "recipient_type": "individual",
        "to": to, "type": "text", "text": {"preview_url": False, "body": body},
    }
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(
            f"{graph_base()}/{connection['phone_number_id']}/messages",
            headers={"Authorization": f"Bearer {connection['access_token']}",
                     "Content-Type": "application/json"},
            json=payload,
        )
        if r.is_error:
            raise ValueError(f"Meta Graph API: {r.text}")
        return r.json()
