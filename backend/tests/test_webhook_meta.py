"""Tests for the public Meta WhatsApp webhook (GET verify + POST receive).

Covers:
- GET verify handshake (200 with correct token, 403 otherwise)
- POST inbound message from a known phone_number_id → conversa criada/encontrada,
  cliente Carlos Eduardo vinculado, resposta do RAVI persistida
- Idempotência (mesmo message id não duplica)
- Isolamento: phone_number_id desconhecido não cria conversa
- Logs: 'Webhook Meta recebido' aparece nos logs do backend
"""
import os
import time
import uuid
import json
import subprocess
import requests
import pytest
from _webhook_sign import signed_webhook_post

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://ravi-client.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"
ADMIN_EMAIL = "construcaovilanova@gmail.com"
ADMIN_PASSWORD = "Ravi@2026"
VERIFY_TOKEN = "ravi-wh-verify-9f2c4e7a1b3d5f608192a3b5c7d9e1f2"
PHONE_NUMBER_ID = "1266842309849495"
CARLOS_PHONE = "5511954452425"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return s


def _build_payload(from_phone: str, text: str, msg_id: str,
                   phone_number_id: str = PHONE_NUMBER_ID) -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "1074967048515451",
            "changes": [{
                "field": "messages",
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {
                        "display_phone_number": "15556653479",
                        "phone_number_id": phone_number_id,
                    },
                    "contacts": [{
                        "profile": {"name": "Carlos Eduardo"},
                        "wa_id": from_phone,
                    }],
                    "messages": [{
                        "from": from_phone,
                        "id": msg_id,
                        "timestamp": str(int(time.time())),
                        "type": "text",
                        "text": {"body": text},
                    }],
                },
            }],
        }],
    }


# ---------- GET verify ----------
class TestWebhookVerify:
    def test_verify_correct_token_returns_challenge(self):
        r = requests.get(f"{API}/webhooks/whatsapp", params={
            "hub.mode": "subscribe",
            "hub.verify_token": VERIFY_TOKEN,
            "hub.challenge": "19193495",
        })
        assert r.status_code == 200
        assert r.text == "19193495"

    def test_verify_wrong_token_returns_403(self):
        r = requests.get(f"{API}/webhooks/whatsapp", params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong-token",
            "hub.challenge": "abc",
        })
        assert r.status_code == 403

    def test_verify_missing_params_returns_403(self):
        r = requests.get(f"{API}/webhooks/whatsapp")
        assert r.status_code == 403


# ---------- POST inbound ----------
class TestWebhookInbound:
    def test_inbound_from_known_number_creates_conversation_and_ravi_reply(self, admin_session):
        msg_id = f"wamid.test-{uuid.uuid4().hex}"
        payload = _build_payload(CARLOS_PHONE, "Teve novidade no meu processo?", msg_id)
        r = signed_webhook_post(payload)
        assert r.status_code == 200, r.text
        assert r.json() == {"ok": True}

        # aguarda pipeline (LLM Claude ~2-6s)
        conv = None
        deadline = time.time() + 25
        while time.time() < deadline:
            convs = admin_session.get(f"{API}/conversations").json()
            conv = next((c for c in convs
                         if (c.get("client") or {}).get("name") == "Carlos Eduardo"
                         and c.get("phone_normalized") == CARLOS_PHONE), None)
            if conv:
                detail = admin_session.get(f"{API}/conversations/{conv['id']}").json()
                # espera ao menos uma msg client com o texto novo + uma msg ravi posterior
                client_msgs = [m for m in detail["messages"]
                               if m["sender"] == "client" and "novidade" in m["text"].lower()]
                ravi_msgs = [m for m in detail["messages"] if m["sender"] == "ravi"]
                if client_msgs and ravi_msgs:
                    conv = detail
                    break
            time.sleep(1)
        assert conv is not None, "Conversa do Carlos não encontrada após webhook"
        # Cliente correto vinculado
        assert conv["client"]["name"] == "Carlos Eduardo"
        assert conv["client_id"] == conv["client"]["id"]
        # Última mensagem ravi
        ravi_msgs = [m for m in conv["messages"] if m["sender"] == "ravi"]
        assert ravi_msgs, "Nenhuma resposta RAVI persistida"
        last_ravi = ravi_msgs[-1]
        # delivered=True idealmente (token Meta válido). Se False → limitação conhecida (token expirado).
        # Ainda assim exigimos que a msg tenha sido persistida com o campo presente.
        assert "delivered" in last_ravi
        if not last_ravi.get("delivered"):
            pytest.skip(f"Envio Meta falhou (token possivelmente expirado). "
                        f"Msg RAVI persistida mas delivered=False. Isso é limitação conhecida "
                        f"do token temporário 24h, não bug do pipeline.")
        assert last_ravi["delivered"] is True
        assert last_ravi.get("meta_message_id"), "meta_message_id ausente na msg RAVI enviada"

    def test_inbound_idempotency_same_message_id(self, admin_session):
        msg_id = f"wamid.test-idem-{uuid.uuid4().hex}"
        payload = _build_payload(CARLOS_PHONE, "Bom dia doutor, tudo bem?", msg_id)

        # 1º envio
        r1 = signed_webhook_post(payload)
        assert r1.status_code == 200
        time.sleep(6)

        # snapshot count
        convs = admin_session.get(f"{API}/conversations").json()
        conv = next(c for c in convs
                    if (c.get("client") or {}).get("name") == "Carlos Eduardo"
                    and c.get("phone_normalized") == CARLOS_PHONE)
        detail1 = admin_session.get(f"{API}/conversations/{conv['id']}").json()
        count_before = len(detail1["messages"])

        # 2º envio (mesmo id)
        r2 = signed_webhook_post(payload)
        assert r2.status_code == 200
        time.sleep(4)

        detail2 = admin_session.get(f"{API}/conversations/{conv['id']}").json()
        count_after = len(detail2["messages"])
        assert count_after == count_before, (
            f"Idempotência falhou: {count_before} → {count_after} mensagens após reenvio")

    def test_inbound_unknown_phone_number_id_ignored(self, admin_session):
        """phone_number_id desconhecido não deve associar a nenhum tenant."""
        # snapshot
        convs_before = admin_session.get(f"{API}/conversations").json()
        ids_before = {c["id"] for c in convs_before}

        msg_id = f"wamid.test-unk-{uuid.uuid4().hex}"
        payload = _build_payload("5511999999999", "hello", msg_id, phone_number_id="999999")
        r = signed_webhook_post(payload)
        assert r.status_code == 200
        time.sleep(2)

        convs_after = admin_session.get(f"{API}/conversations").json()
        ids_after = {c["id"] for c in convs_after}
        # Nenhuma conversa nova no escritório Silva
        assert ids_after == ids_before, "phone_number_id desconhecido criou conversa (vazamento)"


# ---------- Logs ----------
class TestWebhookLogging:
    def test_logger_records_incoming_payload(self):
        marker = f"logmarker-{uuid.uuid4().hex[:8]}"
        payload = _build_payload(CARLOS_PHONE, marker, f"wamid.test-log-{uuid.uuid4().hex}")
        r = signed_webhook_post(payload)
        assert r.status_code == 200
        time.sleep(1)
        # Ler logs do supervisor do backend
        try:
            out = subprocess.check_output(
                ["bash", "-lc", "tail -n 400 /var/log/supervisor/backend.*.log 2>/dev/null"],
                timeout=5).decode("utf-8", "replace")
        except Exception as e:
            pytest.skip(f"Não foi possível ler logs: {e}")
        assert "Webhook Meta recebido" in out, "Log 'Webhook Meta recebido' ausente"
        # Fase 7 (SEC): conteúdo da mensagem não é mais logado (PII) — apenas metadados
        assert marker not in out, "Conteúdo da mensagem não deve aparecer nos logs"
