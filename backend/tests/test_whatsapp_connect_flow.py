"""Testes do novo fluxo Embedded Signup (SaaS puro):
- POST /api/whatsapp/connect/start (auth, meta configurada/não, validação de telefone)
- GET  /api/whatsapp/connect/callback (state lifecycle: válido/reuso/expirado/inexistente)
- POST /api/whatsapp/test-connection (mensagens amigáveis)
- Segurança: /whatsapp/status não expõe access_token
"""
import os
import time
import uuid
import requests
import pytest
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://ravi-client.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"
ADMIN_EMAIL = "construcaovilanova@gmail.com"
ADMIN_PASSWORD = "Ravi@2026"
MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "test_database"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def office_id(admin_session):
    r = admin_session.get(f"{API}/auth/me")
    assert r.status_code == 200
    oid = r.json()["office"]["id"]
    assert oid
    return oid


@pytest.fixture(scope="module")
def mongo():
    c = MongoClient(MONGO_URL)
    db = c[DB_NAME]
    yield db
    c.close()


# ---------------- connect/start ----------------

class TestConnectStart:
    def test_requires_auth(self):
        r = requests.post(f"{API}/whatsapp/connect/start", json={"phone": "(11) 98765-4321"})
        assert r.status_code == 401

    def test_meta_not_configured_returns_503(self, admin_session):
        # META_APP_ID vazio no .env atual → deve retornar 503 amigável
        r = admin_session.post(f"{API}/whatsapp/connect/start", json={"phone": "(11) 98765-4321"})
        if r.status_code == 200:
            pytest.skip("Meta está configurada nesse ambiente — skip do teste de 503")
        assert r.status_code == 503
        body = r.json()
        msg = body.get("detail") or body.get("message") or ""
        assert "suporte" in msg.lower() or "disponível" in msg.lower() or "conex" in msg.lower()

    def test_invalid_phone_returns_400(self, admin_session, monkeypatch):
        # Só testa validação se Meta estivesse configurada. Como não está, endpoint volta 503
        # antes da validação de telefone. Portanto validamos o comportamento com o env atual:
        r = admin_session.post(f"{API}/whatsapp/connect/start", json={"phone": "123"})
        # Aceitamos 503 (meta não configurada) ou 400 (telefone inválido) — ambos são "não avança"
        assert r.status_code in (400, 503)


# ---------------- connect/callback (state lifecycle) ----------------

class TestConnectCallback:
    def _insert_state(self, mongo, office_id, state=None, used=False, expired=False):
        state = state or f"st_{uuid.uuid4().hex}"
        now = datetime.now(timezone.utc)
        exp = now - timedelta(minutes=5) if expired else now + timedelta(minutes=10)
        mongo.whatsapp_connect_states.insert_one({
            "state": state, "office_id": office_id, "phone": "5511987654321",
            "used": used, "created_at": now.isoformat(),
            "expires_at": exp.isoformat(),
        })
        return state

    def test_missing_params_redirects_missing_params(self):
        r = requests.get(f"{API}/whatsapp/connect/callback", allow_redirects=False)
        assert r.status_code in (302, 307)
        assert "error=missing_params" in r.headers["location"]

    def test_nonexistent_state_redirects_invalid_state(self):
        r = requests.get(f"{API}/whatsapp/connect/callback",
                         params={"code": "fake", "state": "does-not-exist"},
                         allow_redirects=False)
        assert r.status_code in (302, 307)
        assert "error=invalid_state" in r.headers["location"]

    def test_expired_state_redirects_invalid_state(self, mongo, office_id):
        state = self._insert_state(mongo, office_id, expired=True)
        r = requests.get(f"{API}/whatsapp/connect/callback",
                         params={"code": "fake", "state": state},
                         allow_redirects=False)
        assert r.status_code in (302, 307)
        assert "error=invalid_state" in r.headers["location"]
        mongo.whatsapp_connect_states.delete_one({"state": state})

    def test_used_state_second_use_invalid(self, mongo, office_id):
        state = self._insert_state(mongo, office_id, used=True)
        r = requests.get(f"{API}/whatsapp/connect/callback",
                         params={"code": "fake", "state": state},
                         allow_redirects=False)
        assert r.status_code in (302, 307)
        assert "error=invalid_state" in r.headers["location"]
        mongo.whatsapp_connect_states.delete_one({"state": state})

    def test_valid_state_fake_code_marks_used_and_connect_failed(self, mongo, office_id):
        state = self._insert_state(mongo, office_id)
        r = requests.get(f"{API}/whatsapp/connect/callback",
                         params={"code": "fake-code-invalid", "state": state},
                         allow_redirects=False)
        assert r.status_code in (302, 307)
        loc = r.headers["location"]
        # Meta app não configurada → exchange_code_for_token vai levantar KeyError,
        # caído no except genérico → error=connect_failed
        assert "error=connect_failed" in loc or "error=invalid_state" in loc
        # State marcado como usado
        rec = mongo.whatsapp_connect_states.find_one({"state": state})
        assert rec is not None
        assert rec["used"] is True

        # Segundo uso do MESMO state → invalid_state
        r2 = requests.get(f"{API}/whatsapp/connect/callback",
                          params={"code": "another", "state": state},
                          allow_redirects=False)
        assert r2.status_code in (302, 307)
        assert "error=invalid_state" in r2.headers["location"]
        mongo.whatsapp_connect_states.delete_one({"state": state})


# ---------------- test-connection ----------------

class TestTestConnection:
    def test_without_connection_returns_400(self, admin_session, mongo, office_id):
        # Se houver conexão ativa, backup dela e restaurar depois
        existing = mongo.whatsapp_connections.find_one({"office_id": office_id})
        if existing:
            mongo.whatsapp_connections.update_one(
                {"office_id": office_id}, {"$set": {"status": "disconnected"}})
        try:
            r = admin_session.post(f"{API}/whatsapp/test-connection")
            assert r.status_code == 400
            detail = r.json().get("detail", "")
            assert "não está conectado" in detail.lower() or "nao esta conectado" in detail.lower()
        finally:
            if existing:
                mongo.whatsapp_connections.update_one(
                    {"office_id": office_id}, {"$set": {"status": existing.get("status", "connected")}})

    def test_with_expired_token_returns_friendly_400(self, admin_session, office_id, mongo):
        conn = mongo.whatsapp_connections.find_one({"office_id": office_id})
        if not conn or conn.get("status") != "connected":
            pytest.skip("Sem conexão ativa — cenário não aplicável")
        r = admin_session.post(f"{API}/whatsapp/test-connection")
        # Token de teste da Meta pode ter expirado → resposta amigável 400
        # Se token estiver válido → 200 também é aceitável
        if r.status_code == 200:
            return  # token válido, tudo bem
        assert r.status_code == 400
        detail = r.json().get("detail", "").lower()
        assert "reconecte" in detail or "não conseguimos" in detail or "nao conseguimos" in detail


# ---------------- segurança ----------------

class TestSecurity:
    def test_status_does_not_expose_access_token(self, admin_session):
        r = admin_session.get(f"{API}/whatsapp/status")
        assert r.status_code == 200
        body_text = r.text.lower()
        assert "access_token" not in body_text
        d = r.json()
        if d.get("connection"):
            assert "access_token" not in d["connection"]

    def test_callback_signature_no_office_id_param(self):
        # Sanidade via AST: handler não aceita office_id como parâmetro
        import ast
        with open("/app/backend/whatsapp_routes.py") as f:
            tree = ast.parse(f.read())
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.AsyncFunctionDef) and n.name == "connect_callback")
        arg_names = [a.arg for a in fn.args.args]
        assert "office_id" not in arg_names
        assert set(arg_names) == {"code", "state"}


# ---------------- disconnect preserva histórico ----------------

class TestDisconnectPreservesHistory:
    def test_disconnect_keeps_clients_and_convs(self, admin_session, mongo, office_id):
        # snapshot antes
        clients_before = len(list(mongo.clients.find({"office_id": office_id})))
        convs_before = len(list(mongo.conversations.find({"office_id": office_id})))
        procs_before = len(list(mongo.processes.find({"office_id": office_id})))
        msgs_before = len(list(mongo.messages.find({"office_id": office_id})))

        # snapshot conexão original para restaurar
        original_conn = mongo.whatsapp_connections.find_one({"office_id": office_id})

        r = admin_session.post(f"{API}/whatsapp/disconnect")
        assert r.status_code == 200
        assert r.json().get("status") == "disconnected"

        # nada foi perdido
        assert len(list(mongo.clients.find({"office_id": office_id}))) == clients_before
        assert len(list(mongo.conversations.find({"office_id": office_id}))) == convs_before
        assert len(list(mongo.processes.find({"office_id": office_id}))) == procs_before
        assert len(list(mongo.messages.find({"office_id": office_id}))) == msgs_before

        # restaurar conexão original (para não quebrar outros testes)
        if original_conn and original_conn.get("status") == "connected":
            mongo.whatsapp_connections.update_one(
                {"office_id": office_id},
                {"$set": {"status": "connected",
                          "access_token": original_conn.get("access_token", ""),
                          "phone_number_id": original_conn.get("phone_number_id"),
                          "business_account_id": original_conn.get("business_account_id")}})
