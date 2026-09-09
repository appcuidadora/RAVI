import os
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
