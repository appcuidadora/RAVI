"""Fase 5 — RAVI ADMIN /users CRUD, logs com filtro de data, e segurança."""
import os
import uuid
import pytest
import requests
from datetime import datetime, timedelta, timezone

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://ravi-client.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"

SUPER_EMAIL = "construcaovilanova@gmail.com"
SUPER_PASS = "Ravi@2026"


def _admin_session():
    s = requests.Session()
    r = s.post(f"{API}/admin/auth/login", json={"email": SUPER_EMAIL, "password": SUPER_PASS}, timeout=15)
    assert r.status_code == 200, f"super admin login failed: {r.status_code} {r.text}"
    return s


def _app_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": SUPER_EMAIL, "password": SUPER_PASS}, timeout=15)
    assert r.status_code == 200, f"app login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def super_admin():
    return _admin_session()


# ---------- Segurança (401 sem auth, 401 com cookie de app) ----------

class TestAdminUsersSecurity:
    def test_get_users_without_auth_401(self):
        r = requests.get(f"{API}/admin/users", timeout=10)
        assert r.status_code == 401, r.text

    def test_get_users_with_app_cookie_401(self):
        app = _app_session()  # cookie access_token de tenant, NÃO admin_access_token
        r = app.get(f"{API}/admin/users", timeout=10)
        assert r.status_code == 401, r.text

    def test_app_user_never_hits_admin_dashboard(self):
        app = _app_session()
        r = app.get(f"{API}/admin/dashboard", timeout=10)
        assert r.status_code == 401


# ---------- CRUD /admin/users ----------

class TestAdminUsersCRUD:
    created_id = None
    created_email = None
    temp_password = None

    def test_list_users_super(self, super_admin):
        r = super_admin.get(f"{API}/admin/users", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert "users" in data and "roles" in data
        assert "SUPER_ADMIN" in data["roles"]
        # não devolve password_hash
        for u in data["users"]:
            assert "password_hash" not in u
            assert "temp_password" not in u

    def test_create_admin_invalid_role_400(self, super_admin):
        r = super_admin.post(f"{API}/admin/users",
                             json={"name": "X", "email": f"test_{uuid.uuid4().hex[:6]}@ravi.app", "role": "GOD"},
                             timeout=10)
        assert r.status_code == 400

    def test_create_admin_valid_returns_temp_password(self, super_admin):
        email = f"test_admin_{uuid.uuid4().hex[:8]}@ravi.app"
        r = super_admin.post(f"{API}/admin/users",
                             json={"name": "TEST Fase5 Admin", "email": email, "role": "ADMIN_SUPORTE"},
                             timeout=10)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["email"] == email
        assert data["role"] == "ADMIN_SUPORTE"
        assert data["active"] is True
        assert "temp_password" in data and data["temp_password"].startswith("RaviAdmin-")
        assert "password_hash" not in data
        TestAdminUsersCRUD.created_id = data["id"]
        TestAdminUsersCRUD.created_email = email
        TestAdminUsersCRUD.temp_password = data["temp_password"]

    def test_temp_password_not_returned_in_get(self, super_admin):
        assert TestAdminUsersCRUD.created_email, "prereq"
        r = super_admin.get(f"{API}/admin/users", timeout=10)
        assert r.status_code == 200
        u = next((x for x in r.json()["users"] if x["email"] == TestAdminUsersCRUD.created_email), None)
        assert u is not None
        assert "temp_password" not in u
        assert "password_hash" not in u

    def test_duplicate_email_400(self, super_admin):
        assert TestAdminUsersCRUD.created_email, "prereq"
        r = super_admin.post(f"{API}/admin/users",
                             json={"name": "dup", "email": TestAdminUsersCRUD.created_email, "role": "ANALISTA"},
                             timeout=10)
        assert r.status_code == 400

    def test_new_admin_can_login(self):
        assert TestAdminUsersCRUD.created_email and TestAdminUsersCRUD.temp_password
        s = requests.Session()
        r = s.post(f"{API}/admin/auth/login",
                   json={"email": TestAdminUsersCRUD.created_email, "password": TestAdminUsersCRUD.temp_password},
                   timeout=10)
        assert r.status_code == 200, r.text
        me = s.get(f"{API}/admin/auth/me", timeout=10)
        assert me.status_code == 200
        assert me.json()["admin"]["role"] == "ADMIN_SUPORTE"

    def test_non_super_forbidden_from_users(self):
        assert TestAdminUsersCRUD.created_email
        s = requests.Session()
        r = s.post(f"{API}/admin/auth/login",
                   json={"email": TestAdminUsersCRUD.created_email, "password": TestAdminUsersCRUD.temp_password},
                   timeout=10)
        assert r.status_code == 200
        r2 = s.get(f"{API}/admin/users", timeout=10)
        assert r2.status_code == 403, r2.text
        # também não pode criar
        r3 = s.post(f"{API}/admin/users",
                    json={"name": "z", "email": "z@z.z", "role": "ANALISTA"}, timeout=10)
        assert r3.status_code == 403

    def test_toggle_active_deactivates_then_login_403(self, super_admin):
        assert TestAdminUsersCRUD.created_id
        r = super_admin.post(f"{API}/admin/users/{TestAdminUsersCRUD.created_id}/toggle-active", timeout=10)
        assert r.status_code == 200
        assert r.json()["active"] is False
        # login do desativado
        s = requests.Session()
        r2 = s.post(f"{API}/admin/auth/login",
                    json={"email": TestAdminUsersCRUD.created_email, "password": TestAdminUsersCRUD.temp_password},
                    timeout=10)
        assert r2.status_code == 403, r2.text

    def test_toggle_active_reactivates(self, super_admin):
        assert TestAdminUsersCRUD.created_id
        r = super_admin.post(f"{API}/admin/users/{TestAdminUsersCRUD.created_id}/toggle-active", timeout=10)
        assert r.status_code == 200
        assert r.json()["active"] is True
        s = requests.Session()
        r2 = s.post(f"{API}/admin/auth/login",
                    json={"email": TestAdminUsersCRUD.created_email, "password": TestAdminUsersCRUD.temp_password},
                    timeout=10)
        assert r2.status_code == 200

    def test_cannot_self_deactivate(self, super_admin):
        me = super_admin.get(f"{API}/admin/auth/me", timeout=10).json()["admin"]
        r = super_admin.post(f"{API}/admin/users/{me['id']}/toggle-active", timeout=10)
        assert r.status_code == 400


# ---------- Logs com filtro de data ----------

class TestAdminLogsDateFilter:
    def test_logs_no_dates_returns_all(self, super_admin):
        r = super_admin.get(f"{API}/admin/logs", timeout=15)
        assert r.status_code == 200
        assert "logs" in r.json()

    def test_logs_future_range_empty(self, super_admin):
        future = (datetime.now(timezone.utc) + timedelta(days=30)).date().isoformat()
        r = super_admin.get(f"{API}/admin/logs", params={"from_date": future, "to_date": future}, timeout=15)
        assert r.status_code == 200
        assert r.json()["logs"] == []

    def test_logs_today_range_includes_recent(self, super_admin):
        # cria um log admin agora (login já criou; toggle também). Executa uma ação simples:
        super_admin.get(f"{API}/admin/dashboard", timeout=10)
        today = datetime.now(timezone.utc).date().isoformat()
        r = super_admin.get(f"{API}/admin/logs",
                            params={"from_date": today, "to_date": today, "tipo": "admin"},
                            timeout=15)
        assert r.status_code == 200
        logs = r.json()["logs"]
        # deve ter pelo menos o admin_login recente
        assert any(l.get("origem") == "admin" for l in logs), "esperava logs admin de hoje"

    def test_logs_tipo_admin_only(self, super_admin):
        r = super_admin.get(f"{API}/admin/logs", params={"tipo": "admin"}, timeout=15)
        assert r.status_code == 200
        for l in r.json()["logs"]:
            assert l.get("origem") == "admin"

    def test_logs_tipo_tenant_only(self, super_admin):
        r = super_admin.get(f"{API}/admin/logs", params={"tipo": "tenant"}, timeout=15)
        assert r.status_code == 200
        for l in r.json()["logs"]:
            assert l.get("origem") == "tenant"


# ---------- Regressão: dashboard / offices / impersonate ----------

class TestRegression:
    def test_dashboard(self, super_admin):
        r = super_admin.get(f"{API}/admin/dashboard", timeout=15)
        assert r.status_code == 200
        assert "kpis" in r.json() and "atencao" in r.json()

    def test_offices(self, super_admin):
        r = super_admin.get(f"{API}/admin/offices", timeout=15)
        assert r.status_code == 200
        assert "offices" in r.json()

    def test_impersonate(self, super_admin):
        offices = super_admin.get(f"{API}/admin/offices", timeout=15).json()["offices"]
        if not offices:
            pytest.skip("sem escritórios")
        oid = offices[0]["id"]
        r = super_admin.post(f"{API}/admin/offices/{oid}/impersonate",
                             json={"motivo": "teste fase5"}, timeout=15)
        assert r.status_code == 200
        assert "token" in r.json()
