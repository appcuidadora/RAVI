"""
Iteration 8 — RAVI ADMIN / RAVI APP separation.
Covers: admin auth, dashboard KPIs, escritorios CRUD + suspensão + impersonation,
planos CRUD, financeiro (charges/pay/cancel/overview/aging), Meta secrets write-only,
health checks, tickets, AI global config, overage on process creation.
"""
import os
import uuid
import time
import requests
import pytest

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://ravi-client.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"

ADMIN_EMAIL = "construcaovilanova@gmail.com"
ADMIN_PASS = "Ravi@2026"


# ---------- fixtures ----------

@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/admin/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=15)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    assert "admin_access_token" in s.cookies
    return s


@pytest.fixture(scope="module")
def app_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=15)
    assert r.status_code == 200, f"app login failed: {r.text}"
    return s


@pytest.fixture(scope="module")
def test_office(admin_session):
    """Create a TEST_* office with STARTER plan + a socio user for destructive tests."""
    # find STARTER plan
    plans = admin_session.get(f"{API}/admin/plans", timeout=15).json()
    starter = next((p for p in plans if p["name"].upper() == "STARTER"), None)
    assert starter, "STARTER plan not seeded"

    # register a new socio
    email = f"TEST_socio_{uuid.uuid4().hex[:8]}@example.com"
    password = "TestPass@2026"
    reg = requests.post(f"{API}/auth/register", json={
        "name": "Test", "last_name": "Socio", "email": email, "password": password
    }, timeout=15)
    assert reg.status_code in (200, 201), reg.text

    # onboarding — create office
    s = requests.Session()
    lg = s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert lg.status_code == 200, lg.text
    ob = s.post(f"{API}/auth/onboarding/complete", json={
        "office_name": f"TEST_Office_{uuid.uuid4().hex[:6]}",
        "oab_number": "SP-000000", "phone": "+5511999999999", "city": "São Paulo", "state": "SP"
    }, timeout=15)
    assert ob.status_code in (200, 201), ob.text
    me = s.get(f"{API}/auth/me", timeout=15).json()
    office_id = me["user"]["office_id"] or me.get("office", {}).get("id")

    # patch: assign STARTER plan
    p = admin_session.patch(f"{API}/admin/offices/{office_id}", json={
        "plan_id": starter["id"], "status": "active", "valor_mensal": 100.0
    }, timeout=15)
    assert p.status_code == 200, p.text

    return {"office_id": office_id, "email": email, "password": password,
            "plan": starter, "session": s}


# ---------- Admin AUTH ----------

class TestAdminAuth:
    def test_login_bad_pw(self):
        r = requests.post(f"{API}/admin/auth/login",
                          json={"email": ADMIN_EMAIL, "password": "wrong"}, timeout=15)
        assert r.status_code == 401

    def test_admin_endpoints_require_auth(self):
        r = requests.get(f"{API}/admin/dashboard", timeout=15)
        assert r.status_code == 401

    def test_app_cookie_does_not_authorize_admin(self, app_session):
        # app cookie must NOT open /api/admin
        r = app_session.get(f"{API}/admin/dashboard", timeout=15)
        assert r.status_code == 401, f"leak: app cookie opened admin ({r.status_code})"

    def test_admin_cookie_does_not_authorize_app(self, admin_session):
        r = admin_session.get(f"{API}/auth/me", timeout=15)
        assert r.status_code == 401, f"leak: admin cookie opened app ({r.status_code})"

    def test_admin_me(self, admin_session):
        r = admin_session.get(f"{API}/admin/auth/me", timeout=15)
        assert r.status_code == 200
        assert r.json()["admin"]["role"] == "SUPER_ADMIN"


# ---------- DASHBOARD ----------

class TestDashboard:
    def test_kpis(self, admin_session):
        r = admin_session.get(f"{API}/admin/dashboard", timeout=20)
        assert r.status_code == 200
        data = r.json()
        assert "kpis" in data and "atencao" in data
        k = data["kpis"]
        expected = ["escritorios_ativos", "usuarios_ativos", "processos_monitorados",
                    "mensagens_recebidas", "mrr", "arr", "ticket_medio", "cancelamentos"]
        for key in expected:
            assert key in k, f"kpi {key} missing"
        assert isinstance(data["atencao"], list)


# ---------- ESCRITORIOS / SUSPENSION / PLAN CHANGE ----------

class TestOffices:
    def test_list(self, admin_session):
        r = admin_session.get(f"{API}/admin/offices", timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert "offices" in d and len(d["offices"]) >= 1
        # enrichment fields
        first = d["offices"][0]
        for f in ("responsavel", "plan_name", "whatsapp_status", "usuarios", "processos"):
            assert f in first

    def test_suspend_blocks_tenant_and_reactivate(self, admin_session, test_office):
        oid = test_office["office_id"]
        s = test_office["session"]
        # baseline works
        r = s.get(f"{API}/auth/me", timeout=15)
        assert r.status_code == 200
        # suspend
        p = admin_session.patch(f"{API}/admin/offices/{oid}",
                                json={"status": "suspended"}, timeout=15)
        assert p.status_code == 200
        # blocked
        r = s.get(f"{API}/auth/me", timeout=15)
        assert r.status_code == 403 and "suspenso" in r.text.lower()
        # reactivate
        p = admin_session.patch(f"{API}/admin/offices/{oid}",
                                json={"status": "active"}, timeout=15)
        assert p.status_code == 200
        r = s.get(f"{API}/auth/me", timeout=15)
        assert r.status_code == 200

    def test_plan_change_direction(self, admin_session, test_office):
        oid = test_office["office_id"]
        plans = admin_session.get(f"{API}/admin/plans", timeout=15).json()
        pro = next((p for p in plans if p["name"].upper() == "PROFESSIONAL"), None)
        starter = test_office["plan"]
        assert pro
        # upgrade
        r = admin_session.patch(f"{API}/admin/offices/{oid}",
                                json={"plan_id": pro["id"]}, timeout=15)
        assert r.status_code == 200
        # downgrade back
        r = admin_session.patch(f"{API}/admin/offices/{oid}",
                                json={"plan_id": starter["id"]}, timeout=15)
        assert r.status_code == 200


# ---------- IMPERSONATION ----------

class TestImpersonation:
    def test_impersonate_requires_motivo(self, admin_session, test_office):
        r = admin_session.post(f"{API}/admin/offices/{test_office['office_id']}/impersonate",
                               json={"motivo": ""}, timeout=15)
        assert r.status_code == 400

    def test_impersonate_flow(self, admin_session, test_office):
        r = admin_session.post(f"{API}/admin/offices/{test_office['office_id']}/impersonate",
                               json={"motivo": "TEST support check"}, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "token" in data and "log_id" in data
        token = data["token"]; log_id = data["log_id"]
        # bearer-first: must return the impersonated user
        me = requests.get(f"{API}/auth/me",
                          headers={"Authorization": f"Bearer {token}"}, timeout=15)
        assert me.status_code == 200
        assert me.json()["user"]["email"].lower() == test_office["email"].lower()
        # end impersonation
        end = requests.post(f"{API}/impersonation/end",
                            headers={"Authorization": f"Bearer {token}"},
                            json={"log_id": log_id}, timeout=15)
        assert end.status_code == 200


# ---------- PLANOS ----------

class TestPlans:
    def test_seeded_four_plans(self, admin_session):
        plans = admin_session.get(f"{API}/admin/plans", timeout=15).json()
        names = {p["name"].upper() for p in plans}
        for req in ("STARTER", "PROFESSIONAL", "OFFICE", "ENTERPRISE"):
            assert req in names, f"missing plan {req}"

    def test_plan_crud(self, admin_session):
        payload = {"name": f"TEST_PLAN_{uuid.uuid4().hex[:6]}", "process_limit": 10,
                   "price_monthly": 9.9, "overage_pct": 10, "status": "ativo"}
        c = admin_session.post(f"{API}/admin/plans", json=payload, timeout=15)
        assert c.status_code == 200
        pid = c.json()["id"]
        u = admin_session.patch(f"{API}/admin/plans/{pid}",
                                json={**payload, "price_monthly": 19.9}, timeout=15)
        assert u.status_code == 200 and u.json()["price_monthly"] == 19.9


# ---------- FINANCEIRO ----------

class TestBilling:
    def test_charge_lifecycle(self, admin_session, test_office):
        oid = test_office["office_id"]
        today = time.strftime("%Y-%m-%d")
        month = today[:7]
        # create
        c = admin_session.post(f"{API}/admin/billing/charges", json={
            "office_id": oid, "competencia": month, "vencimento": today,
            "valor": 250.00, "desconto": 0
        }, timeout=15)
        assert c.status_code == 200
        cid = c.json()["id"]
        # list with office_name
        lst = admin_session.get(f"{API}/admin/billing/charges", timeout=15).json()
        found = next((x for x in lst["charges"] if x["id"] == cid), None)
        assert found and found["office_name"]
        # pay
        p = admin_session.post(f"{API}/admin/billing/charges/{cid}/pay",
                               json={"valor": 250.00, "metodo": "PIX", "referencia": "TEST"}, timeout=15)
        assert p.status_code == 200
        # cannot cancel a paid one
        cancel = admin_session.post(f"{API}/admin/billing/charges/{cid}/cancel", timeout=15)
        assert cancel.status_code == 404
        # create another and cancel it
        c2 = admin_session.post(f"{API}/admin/billing/charges", json={
            "office_id": oid, "competencia": month, "vencimento": today,
            "valor": 100.0, "desconto": 0}, timeout=15).json()
        cn = admin_session.post(f"{API}/admin/billing/charges/{c2['id']}/cancel", timeout=15)
        assert cn.status_code == 200

    def test_overview_has_aging(self, admin_session):
        r = admin_session.get(f"{API}/admin/billing/overview", timeout=15)
        assert r.status_code == 200
        d = r.json()
        for k in ("mrr", "arr", "aging", "vencido", "contas_vencidas", "ticket_medio"):
            assert k in d


# ---------- META SECRETS (write-only) ----------

class TestSecrets:
    def test_write_only(self, admin_session):
        fake = f"fake_{uuid.uuid4().hex[:6]}"
        r = admin_session.post(f"{API}/admin/meta/secrets",
                               json={"meta_test_token": fake}, timeout=20)
        assert r.status_code == 200
        # ensure the value NEVER appears in ANY response
        st = admin_session.get(f"{API}/admin/meta/status", timeout=15)
        assert st.status_code == 200
        assert fake not in st.text, "SECRET LEAK in /admin/meta/status"
        data = st.json()
        assert data["secrets"]["META_TEST_TOKEN"] is True

    def test_health(self, admin_session):
        r = admin_session.get(f"{API}/admin/health", timeout=30)
        assert r.status_code == 200
        checks = r.json()["checks"]
        for k in ("banco", "meta_api", "token", "webhook", "recebimento",
                  "envio", "ia", "storage", "fila"):
            assert k in checks and "ok" in checks[k]


# ---------- TICKETS ----------

class TestTickets:
    def test_office_creates_ticket_admin_manages(self, admin_session, test_office):
        s = test_office["session"]
        r = s.post(f"{API}/support/tickets", json={
            "categoria": "duvida", "assunto": "TEST_Assunto",
            "descricao": "TEST descricao", "prioridade": "media"
        }, timeout=15)
        assert r.status_code in (200, 201)
        tid = r.json()["id"]
        lst = admin_session.get(f"{API}/admin/tickets", timeout=15).json()
        found = next((t for t in lst if t["id"] == tid), None)
        assert found and found["office_name"]
        u = admin_session.patch(f"{API}/admin/tickets/{tid}",
                                json={"status": "em atendimento"}, timeout=15)
        assert u.status_code == 200


# ---------- AI CONFIG ----------

class TestAIConfig:
    def test_rules_persist(self, admin_session):
        rule = {"regra": "RAVI nunca deve inventar informação processual.", "ativa": True}
        r = admin_session.put(f"{API}/admin/settings/ai", json={"rules": [rule]}, timeout=15)
        assert r.status_code == 200
        got = admin_session.get(f"{API}/admin/settings/ai", timeout=15).json()
        assert got["rules"] and got["rules"][0]["regra"].startswith("RAVI nunca")


# ---------- OVERAGE ----------

class TestOverage:
    def test_overage_alert_and_hard_block(self, admin_session, test_office):
        """STARTER=25 procs. Passar de 25 → limite_alerta; passar de 27 → 402."""
        s = test_office["session"]
        oid = test_office["office_id"]
        # ensure STARTER
        admin_session.patch(f"{API}/admin/offices/{oid}",
                            json={"plan_id": test_office["plan"]["id"], "status": "active"}, timeout=15)
        # count existing procs to know how many to create
        me = s.get(f"{API}/auth/me", timeout=15).json()
        limit = 25
        hard = 27
        # create a client
        cli = s.post(f"{API}/clients", json={
            "name": "TEST Client", "whatsapp": "+5511900000000",
            "phone": "+5511900000000", "email": "testcli@example.com",
        }, timeout=15)
        assert cli.status_code in (200, 201), cli.text
        client_id = cli.json()["id"]

        created = 0
        alerta_seen = False
        blocked = False
        for i in range(hard + 2):
            r = s.post(f"{API}/processes", json={
                "number": f"1000000-{i:02d}.2025.8.26.0100",
                "client_id": client_id, "tribunal": "TJSP",
                "status": "Em andamento", "titulo": f"TEST Proc {i}"
            }, timeout=15)
            if r.status_code in (200, 201):
                created += 1
                body = r.json()
                if body.get("limite_alerta"):
                    alerta_seen = True
            elif r.status_code == 402:
                blocked = True
                assert "limite" in r.text.lower() or "plano" in r.text.lower()
                break
            else:
                pytest.fail(f"unexpected status {r.status_code}: {r.text}")

        assert alerta_seen, f"limite_alerta never returned (created={created})"
        assert blocked, f"402 hard block never triggered (created={created})"
