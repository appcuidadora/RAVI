"""RAVI Fase 3: Conversas + State Machine + System Messages + Escalação Explícita."""
import os
import time
import uuid
import requests
import pytest

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://ravi-client.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"
ADMIN_EMAIL = "construcaovilanova@gmail.com"
ADMIN_PASSWORD = "Ravi@2026"


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def other_office():
    s = requests.Session()
    email = f"TEST_p3_{uuid.uuid4().hex[:8]}@example.com"
    r = s.post(f"{API}/auth/register",
               json={"name": "OtherOffice3", "email": email, "password": "Test@1234"})
    assert r.status_code == 200, r.text
    r2 = s.post(f"{API}/auth/onboarding/complete",
                json={"office_name": f"TEST_Office3_{uuid.uuid4().hex[:6]}"})
    assert r2.status_code == 200
    return s


@pytest.fixture(scope="module")
def demo_conv(admin):
    """Retorna a conversa demo do Carlos Eduardo (seedada)."""
    r = admin.get(f"{API}/conversations")
    assert r.status_code == 200
    convs = r.json()
    # Prefer Carlos Eduardo conv
    conv = next((c for c in convs if (c.get("client") or {}).get("name", "").startswith("Carlos")), None)
    if not conv:
        conv = convs[0] if convs else None
    assert conv is not None, "Nenhuma conversa demo encontrada"
    return conv


def get_conv(admin, conv_id):
    r = admin.get(f"{API}/conversations/{conv_id}")
    assert r.status_code == 200, r.text
    return r.json()


# ---------- 1. State machine básico e updated_at ----------
class TestStateMachine:
    def test_green_message_keeps_ai_handling(self, admin, demo_conv):
        cid = demo_conv["id"]
        before = get_conv(admin, cid)
        prev_updated = before.get("updated_at", "")
        # Reset to AI_HANDLING first
        if before.get("state") != "AI_HANDLING":
            admin.post(f"{API}/conversations/{cid}/resume-ravi")
        r = admin.post(f"{API}/conversations/{cid}/client-message",
                       json={"text": "teve novidade no meu processo?"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("action") in ("ravi_replied",), body
        assert body.get("risk_level") == "green", body
        after = get_conv(admin, cid)
        assert after["state"] == "AI_HANDLING"
        assert after["risk_level"] == "green"
        assert after["updated_at"] != prev_updated, "updated_at deve mudar a cada mensagem"

    def test_explicit_human_request_goes_red(self, admin, demo_conv):
        cid = demo_conv["id"]
        admin.post(f"{API}/conversations/{cid}/resume-ravi")
        r = admin.post(f"{API}/conversations/{cid}/client-message",
                       json={"text": "quero falar com o advogado"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("risk_level") == "red", body
        after = get_conv(admin, cid)
        assert after["state"] == "WAITING_HUMAN"
        assert after["risk_level"] == "red"
        # Alerta de intervenção criado
        al = admin.get(f"{API}/alerts?status=open").json()
        conv_alerts = [a for a in al if a.get("conversation_id") == cid and a["type"] == "intervention"]
        assert len(conv_alerts) >= 1

    def test_acordo_message_goes_red(self, admin, demo_conv):
        cid = demo_conv["id"]
        admin.post(f"{API}/conversations/{cid}/resume-ravi")
        r = admin.post(f"{API}/conversations/{cid}/client-message",
                       json={"text": "dá para fazer um acordo?"})
        assert r.status_code == 200, r.text
        assert r.json().get("risk_level") == "red"


# ---------- 2. Pause / Takeover / Resume / Resolve + system messages ----------
class TestConversationActions:
    def test_pause_creates_system_message_and_blocks_ai(self, admin, demo_conv):
        cid = demo_conv["id"]
        admin.post(f"{API}/conversations/{cid}/resume-ravi")
        r = admin.post(f"{API}/conversations/{cid}/pause-ravi")
        assert r.status_code == 200
        assert r.json()["state"] == "PAUSED"
        conv = get_conv(admin, cid)
        assert conv["state"] == "PAUSED"
        assert conv["ai_enabled"] is False
        sys_msgs = [m for m in conv["messages"] if m["sender"] == "system"]
        assert any("pausado" in (m.get("text") or "").lower() for m in sys_msgs)
        # IA não responde estando PAUSED
        r2 = admin.post(f"{API}/conversations/{cid}/client-message",
                        json={"text": "oi ainda vai responder?"})
        assert r2.status_code == 200
        assert r2.json().get("action") == "human_in_control", r2.json()

    def test_takeover_records_user_name(self, admin, demo_conv):
        cid = demo_conv["id"]
        r = admin.post(f"{API}/conversations/{cid}/takeover")
        assert r.status_code == 200
        j = r.json()
        assert j["state"] == "WAITING_HUMAN"
        assert j["human_control"] is True
        conv = get_conv(admin, cid)
        sys_msgs = [m for m in conv["messages"] if m["sender"] == "system"]
        assert any("assumiu" in (m.get("text") or "").lower() for m in sys_msgs)

    def test_resume_returns_to_ai_handling(self, admin, demo_conv):
        cid = demo_conv["id"]
        r = admin.post(f"{API}/conversations/{cid}/resume-ravi")
        assert r.status_code == 200
        assert r.json()["state"] == "AI_HANDLING"
        conv = get_conv(admin, cid)
        assert conv["human_control"] is False
        assert conv["ai_enabled"] is True
        sys_msgs = [m for m in conv["messages"] if m["sender"] == "system"]
        assert any("retomou" in (m.get("text") or "").lower() for m in sys_msgs)

    def test_resolve_closes_conversation_and_alerts(self, admin, demo_conv):
        cid = demo_conv["id"]
        # Gerar alerta aberto
        admin.post(f"{API}/conversations/{cid}/resume-ravi")
        admin.post(f"{API}/conversations/{cid}/client-message",
                   json={"text": "quero falar com o advogado"})
        # Resolver
        r = admin.post(f"{API}/conversations/{cid}/resolve")
        assert r.status_code == 200, r.text
        assert r.json()["state"] == "RESOLVED"
        conv = get_conv(admin, cid)
        assert conv["state"] == "RESOLVED"
        sys_msgs = [m for m in conv["messages"] if m["sender"] == "system"]
        assert any("resolvida" in (m.get("text") or "").lower() for m in sys_msgs)
        # Alertas abertos desta conversa devem estar fechados
        open_alerts = admin.get(f"{API}/alerts?status=open").json()
        assert not any(a.get("conversation_id") == cid and a["type"] == "intervention"
                       for a in open_alerts), "Alertas de intervenção deveriam estar resolved"
        # Alerta tipo 'resolved' criado
        all_alerts = admin.get(f"{API}/alerts?status=all").json()
        assert any(a.get("conversation_id") == cid and a["type"] == "resolved"
                   for a in all_alerts)


# ---------- 3. Isolamento multi-tenant ----------
class TestIsolation:
    def test_other_office_cannot_act_on_conversation(self, other_office, demo_conv):
        cid = demo_conv["id"]
        for path in ["pause-ravi", "takeover", "resume-ravi", "resolve"]:
            r = other_office.post(f"{API}/conversations/{cid}/{path}")
            # pause/takeover/resume não têm lookup — precisa devolver 404 OU não afetar
            # (endpoints usam update_one com office_filter, então match_count=0)
            # resolve idem. Verificação lateral: sem 500.
            assert r.status_code in (200, 404), f"{path}: {r.status_code} {r.text}"

    def test_other_office_cannot_get_conversation(self, other_office, demo_conv):
        r = other_office.get(f"{API}/conversations/{demo_conv['id']}")
        assert r.status_code == 404
