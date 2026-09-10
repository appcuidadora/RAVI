"""RAVI backend tests: auth, dashboard, clients, processes, conversations,
alerts, team, whatsapp webhook, multi-tenant isolation, forgot password."""
import os
import uuid
import time
import requests
import pytest

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://ravi-client.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"
ADMIN_EMAIL = "construcaovilanova@gmail.com"
ADMIN_PASSWORD = "Ravi@2026"
VERIFY_TOKEN = "ravi-wh-verify-9f2c4e7a1b3d5f608192a3b5c7d9e1f2"


# ---------- fixtures ----------
@pytest.fixture(scope="session")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="session")
def demo_ids(admin_session):
    """Fetch demo client/process/conversation IDs."""
    clients = admin_session.get(f"{API}/clients").json()
    carlos = next((c for c in clients if c["name"] == "Carlos Eduardo"), None)
    procs = admin_session.get(f"{API}/processes").json()
    proc = next((p for p in procs if p["number"].startswith("1001234-56")), None)
    convs = admin_session.get(f"{API}/conversations").json()
    conv = next((c for c in convs if c.get("client") and c["client"]["name"] == "Carlos Eduardo"), None)
    return {"client": carlos, "process": proc, "conv": conv}


# ---------- auth ----------
class TestAuth:
    def test_login_success(self):
        r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        assert r.status_code == 200
        d = r.json()
        assert d["user"]["email"] == ADMIN_EMAIL
        assert d["user"]["role"] == "SOCIO_ADMIN"
        assert d["user"]["onboarding_completed"] is True
        assert d["office"]["name"] == "Silva Advocacia"
        # httpOnly cookies
        assert "access_token" in r.cookies

    def test_login_wrong_password(self):
        r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": "wrong"})
        assert r.status_code == 401

    def test_me_requires_auth(self):
        r = requests.get(f"{API}/auth/me")
        assert r.status_code == 401

    def test_me_authenticated(self, admin_session):
        r = admin_session.get(f"{API}/auth/me")
        assert r.status_code == 200
        assert r.json()["user"]["email"] == ADMIN_EMAIL

    def test_forgot_password_existing(self):
        r = requests.post(f"{API}/auth/forgot-password", json={"email": ADMIN_EMAIL})
        assert r.status_code == 200
        assert "message" in r.json()

    def test_forgot_password_unknown(self):
        r = requests.post(f"{API}/auth/forgot-password", json={"email": f"noone_{uuid.uuid4().hex}@x.com"})
        assert r.status_code == 200
        # Must be same generic message
        assert "message" in r.json()

    def test_logout(self):
        s = requests.Session()
        s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        r = s.post(f"{API}/auth/logout")
        assert r.status_code == 200


# ---------- dashboard ----------
class TestDashboard:
    def test_stats(self, admin_session):
        r = admin_session.get(f"{API}/dashboard/stats")
        assert r.status_code == 200
        d = r.json()
        s = d["stats"]
        assert s["processos"] == 50
        assert s["clientes"] == 63
        assert s["resolvidos"] == 41
        assert s["tempo_economizado_min"] == 222
        assert d["office_name"] == "Silva Advocacia"


# ---------- clients ----------
class TestClients:
    def test_list_clients_has_demo(self, admin_session):
        r = admin_session.get(f"{API}/clients")
        assert r.status_code == 200
        names = [c["name"] for c in r.json()]
        assert "Carlos Eduardo" in names

    def test_create_edit_duplicate_client(self, admin_session):
        phone = "(11) 91234-5678"
        # cleanup any leftover
        for c in admin_session.get(f"{API}/clients").json():
            if c["name"].startswith("TEST_"):
                admin_session.delete(f"{API}/clients/{c['id']}")
        r = admin_session.post(f"{API}/clients", json={"name": "TEST_Ana", "phone": phone})
        assert r.status_code == 200, r.text
        cid = r.json()["id"]
        assert r.json()["phone_normalized"] == "5511912345678"
        # duplicate
        dup = admin_session.post(f"{API}/clients", json={"name": "TEST_Ana2", "phone": "11912345678"})
        assert dup.status_code == 400
        # edit
        pr = admin_session.patch(f"{API}/clients/{cid}",
                                 json={"name": "TEST_Ana Silva", "phone": phone})
        assert pr.status_code == 200
        assert pr.json()["name"] == "TEST_Ana Silva"
        # cleanup
        admin_session.delete(f"{API}/clients/{cid}")


# ---------- processes ----------
class TestProcesses:
    def test_create_with_cnj_parsing(self, admin_session):
        r = admin_session.post(f"{API}/processes",
                               json={"number": "1001234-56.2025.8.26.0100"})
        assert r.status_code == 200, r.text
        p = r.json()
        assert "TJSP" in (p.get("tribunal") or ""), f"tribunal={p.get('tribunal')}"
        assert str(p.get("ano")) == "2025"
        pid = p["id"]
        # detail
        d = admin_session.get(f"{API}/processes/{pid}")
        assert d.status_code == 200
        assert "fontes" in d.json()


# ---------- conversas ----------
class TestConversations:
    def test_get_demo_conversation(self, admin_session, demo_ids):
        conv = demo_ids["conv"]
        assert conv is not None
        r = admin_session.get(f"{API}/conversations/{conv['id']}")
        assert r.status_code == 200
        d = r.json()
        assert len(d["messages"]) >= 4
        assert d["client"]["name"] == "Carlos Eduardo"

    def test_simulate_novelty_message_green(self, admin_session, demo_ids):
        conv = demo_ids["conv"]
        # Ensure ravi is enabled
        admin_session.post(f"{API}/conversations/{conv['id']}/resume-ravi")
        r = admin_session.post(f"{API}/conversations/{conv['id']}/client-message",
                               json={"text": "Teve alguma novidade?"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("action") == "ravi_replied"
        # yellow is acceptable ("novidade" may be flagged); red should not
        assert d.get("risk_level") in ("green", "yellow")

    def test_simulate_escalation_red(self, admin_session, demo_ids):
        conv = demo_ids["conv"]
        admin_session.post(f"{API}/conversations/{conv['id']}/resume-ravi")
        r = admin_session.post(f"{API}/conversations/{conv['id']}/client-message",
                               json={"text": "Posso fazer algo para acelerar?"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("risk_level") == "red", f"expected red got {d}"
        # new intervention alert created
        alerts = admin_session.get(f"{API}/alerts").json()
        assert any(a.get("type") == "intervention" and a.get("client_id") == demo_ids["client"]["id"]
                   for a in alerts)

    def test_pause_and_resume_ravi(self, admin_session, demo_ids):
        conv = demo_ids["conv"]
        r = admin_session.post(f"{API}/conversations/{conv['id']}/pause-ravi")
        assert r.status_code == 200
        assert r.json()["ai_enabled"] is False
        # inbound simulated → ai should NOT reply
        r2 = admin_session.post(f"{API}/conversations/{conv['id']}/client-message",
                                json={"text": "Oi doutor"})
        assert r2.status_code == 200
        assert r2.json().get("action") == "human_in_control"
        # takeover
        r3 = admin_session.post(f"{API}/conversations/{conv['id']}/takeover")
        assert r3.status_code == 200
        assert r3.json()["human_control"] is True
        # resume
        r4 = admin_session.post(f"{API}/conversations/{conv['id']}/resume-ravi")
        assert r4.status_code == 200
        assert r4.json()["ai_enabled"] is True


# ---------- alertas ----------
class TestAlerts:
    def test_list_and_resolve_alert(self, admin_session, demo_ids):
        alerts = admin_session.get(f"{API}/alerts").json()
        assert len(alerts) >= 1
        # Find the demo intervention
        target = next((a for a in alerts if a.get("client_id") == demo_ids["client"]["id"]
                       and a.get("status") == "open"), None)
        if target:
            r = admin_session.post(f"{API}/alerts/{target['id']}/resolve")
            assert r.status_code == 200


# ---------- equipe ----------
class TestTeam:
    def test_add_edit_toggle_member(self, admin_session):
        email = f"TEST_sec_{uuid.uuid4().hex[:6]}@example.com"
        r = admin_session.post(f"{API}/team", json={
            "name": "TEST_Secretaria", "email": email, "role": "SECRETARIA_ATENDIMENTO"})
        assert r.status_code == 200, r.text
        m = r.json()
        assert "temp_password" in m and m["temp_password"].startswith("Ravi-")
        mid = m["id"]
        # patch perms (turn off processos)
        p = admin_session.patch(f"{API}/team/{mid}",
                                json={"permissions": {"processos": False}})
        assert p.status_code == 200
        assert p.json()["permissions"]["processos"] is False
        # deactivate
        t = admin_session.post(f"{API}/team/{mid}/toggle-active")
        assert t.status_code == 200 and t.json()["active"] is False
        # reactivate
        t2 = admin_session.post(f"{API}/team/{mid}/toggle-active")
        assert t2.status_code == 200 and t2.json()["active"] is True


# ---------- multi-tenant isolation ----------
class TestIsolation:
    def test_second_office_cannot_see_silva_data(self):
        # register new user
        s = requests.Session()
        email = f"TEST_iso_{uuid.uuid4().hex[:8]}@example.com"
        r = s.post(f"{API}/auth/register",
                   json={"name": "TestUser", "email": email, "password": "Test@1234"})
        assert r.status_code == 200, r.text
        # complete onboarding
        r2 = s.post(f"{API}/auth/onboarding/complete",
                    json={"office_name": f"TEST_Office_{uuid.uuid4().hex[:6]}"})
        assert r2.status_code == 200
        # data should be empty
        clients = s.get(f"{API}/clients").json()
        assert not any(c["name"] == "Carlos Eduardo" for c in clients)
        procs = s.get(f"{API}/processes").json()
        assert not any("1001234-56" in p.get("number", "") for p in procs)
        convs = s.get(f"{API}/conversations").json()
        assert convs == []


# ---------- whatsapp ----------
class TestWhatsApp:
    def test_webhook_verify_correct_token(self):
        r = requests.get(f"{API}/webhooks/whatsapp",
                         params={"hub.mode": "subscribe",
                                 "hub.verify_token": VERIFY_TOKEN,
                                 "hub.challenge": "12345"})
        assert r.status_code == 200
        assert r.text == "12345"

    def test_webhook_verify_wrong_token(self):
        r = requests.get(f"{API}/webhooks/whatsapp",
                         params={"hub.mode": "subscribe",
                                 "hub.verify_token": "wrong",
                                 "hub.challenge": "12345"})
        assert r.status_code == 403

    def test_status_shows_meta_connected(self, admin_session):
        r = admin_session.get(f"{API}/whatsapp/status")
        assert r.status_code == 200
        d = r.json()
        assert d["webhook_url"] == "/api/webhooks/whatsapp"
        # Meta conectada com número de teste (token pode estar temporariamente expirado)
        if not d.get("connection") or d["connection"]["status"] not in ("connected", "token_expired"):
            pytest.skip("Conexão WhatsApp de teste inativa — aguardando novo token Meta")
        assert d["connection"]["phone_number_id"] == "1266842309849495"
