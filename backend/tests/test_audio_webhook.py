"""Tests para feature de mensagem de VOZ no WhatsApp.

Cobre:
- Webhook type=audio com media_id fake: retorna 200, NÃO cria mensagem/conversa
  (get_media_bytes falha → evento descartado com log, comportamento esperado)
- Webhook type=image/video/document/sticker: retorna 200, loga 'não suportado',
  não cria nada
- Regressão type=text: cria msg kind='text' e resposta RAVI
- transcribe_audio + classify_message em ai.py estão íntegros (importáveis, chamáveis)
"""
import os
import time
import uuid
import requests
import pytest

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://ravi-client.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"
ADMIN_EMAIL = "construcaovilanova@gmail.com"
ADMIN_PASSWORD = "Ravi@2026"
PHONE_NUMBER_ID = "1266842309849495"
CARLOS_PHONE = "5511954452425"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return s


def _envelope(msg: dict) -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "1074967048515451",
            "changes": [{
                "field": "messages",
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"display_phone_number": "15556653479",
                                 "phone_number_id": PHONE_NUMBER_ID},
                    "contacts": [{"profile": {"name": "Carlos Eduardo"},
                                  "wa_id": CARLOS_PHONE}],
                    "messages": [msg],
                },
            }],
        }],
    }


def _snapshot_msgs(admin_session):
    convs = admin_session.get(f"{API}/conversations").json()
    conv = next((c for c in convs
                 if (c.get("client") or {}).get("name") == "Carlos Eduardo"
                 and c.get("phone_normalized") == CARLOS_PHONE), None)
    if not conv:
        return None, 0
    detail = admin_session.get(f"{API}/conversations/{conv['id']}").json()
    return conv["id"], len(detail["messages"])


class TestAudioWebhook:
    def test_audio_with_fake_media_id_returns_200_no_message_created(self, admin_session):
        conv_id, count_before = _snapshot_msgs(admin_session)
        msg_id = f"wamid.audio-{uuid.uuid4().hex}"
        payload = _envelope({
            "from": CARLOS_PHONE, "id": msg_id,
            "timestamp": str(int(time.time())),
            "type": "audio",
            "audio": {"id": "fake-media-id-does-not-exist-999",
                      "mime_type": "audio/ogg; codecs=opus", "voice": True},
        })
        r = requests.post(f"{API}/webhooks/whatsapp", json=payload)
        assert r.status_code == 200
        assert r.json() == {"ok": True}
        time.sleep(3)
        _, count_after = _snapshot_msgs(admin_session)
        assert count_after == count_before, (
            f"Áudio com media_id inválido criou msg: {count_before}→{count_after}")

    @pytest.mark.parametrize("mtype,body", [
        ("image", {"image": {"id": "x", "mime_type": "image/jpeg"}}),
        ("video", {"video": {"id": "x", "mime_type": "video/mp4"}}),
        ("document", {"document": {"id": "x", "filename": "f.pdf"}}),
        ("sticker", {"sticker": {"id": "x"}}),
    ])
    def test_unsupported_types_are_ignored(self, admin_session, mtype, body):
        conv_id, count_before = _snapshot_msgs(admin_session)
        msg = {"from": CARLOS_PHONE, "id": f"wamid.{mtype}-{uuid.uuid4().hex}",
               "timestamp": str(int(time.time())), "type": mtype, **body}
        r = requests.post(f"{API}/webhooks/whatsapp", json=_envelope(msg))
        assert r.status_code == 200
        time.sleep(1)
        _, count_after = _snapshot_msgs(admin_session)
        assert count_after == count_before, f"tipo {mtype} não deveria criar msg"

    def test_text_regression_creates_text_message_and_ravi_reply(self, admin_session):
        conv_id_before, count_before = _snapshot_msgs(admin_session)
        marker = f"regressao-texto-{uuid.uuid4().hex[:6]}"
        msg_id = f"wamid.text-{uuid.uuid4().hex}"
        payload = _envelope({
            "from": CARLOS_PHONE, "id": msg_id,
            "timestamp": str(int(time.time())),
            "type": "text", "text": {"body": f"Oi doutor, {marker}"},
        })
        r = requests.post(f"{API}/webhooks/whatsapp", json=payload)
        assert r.status_code == 200
        # aguarda pipeline
        deadline = time.time() + 25
        found_client = found_ravi = False
        conv_id = None
        while time.time() < deadline:
            conv_id, cnt = _snapshot_msgs(admin_session)
            if conv_id and cnt >= count_before + 2:
                detail = admin_session.get(f"{API}/conversations/{conv_id}").json()
                found_client = any(m["sender"] == "client" and marker in m["text"]
                                   for m in detail["messages"])
                found_ravi = any(m["sender"] == "ravi" and m["created_at"] > detail["messages"][0]["created_at"]
                                 for m in detail["messages"])
                if found_client and found_ravi:
                    # verifica kind='text' na msg do cliente
                    client_msg = next(m for m in detail["messages"]
                                      if m["sender"] == "client" and marker in m["text"])
                    assert client_msg.get("kind", "text") == "text"
                    break
            time.sleep(1)
        assert found_client, "Msg text do cliente não persistida"
        assert found_ravi, "Resposta RAVI não persistida"


class TestAiModuleIntegrity:
    def test_classify_and_transcribe_importable(self):
        import sys, importlib
        sys.path.insert(0, "/app/backend")
        ai = importlib.import_module("ai")
        assert callable(ai.classify_message)
        assert callable(ai.transcribe_audio)
        # classify smoke
        level, _ = ai.classify_message("bom dia doutor, teve novidade?")
        assert level == "green"
        level, _ = ai.classify_message("qual o prazo para eu recorrer?")
        assert level == "red"
        level, _ = ai.classify_message("blablabla xpto")
        assert level == "yellow"
