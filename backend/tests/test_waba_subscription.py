"""Test the fix for the user-reported bug (2nd occurrence): messages sent to Meta test
number weren't answered by RAVI because RAVI_API wasn't subscribed to the WABA.

Verifica:
- GET /v25.0/{WABA}/subscribed_apps inclui o app RAVI_API (id 4453203408280441)
- Backend hot-reloadou sem erros
- GET /api/whatsapp/status autenticado retorna connection.status='connected'
"""
import os
import time
import subprocess
import requests
import pytest
from pymongo import MongoClient

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://ravi-client.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"
ADMIN_EMAIL = "construcaovilanova@gmail.com"
ADMIN_PASSWORD = "Ravi@2026"
EXPECTED_APP_ID = "4453203408280441"  # RAVI_API
EXPECTED_WABA = "1074967048515451"
GRAPH_VER = os.environ.get("META_GRAPH_VERSION", "v25.0")


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def connection_doc():
    c = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    db_name = os.environ.get("DB_NAME", "test_database")
    doc = c[db_name].whatsapp_connections.find_one({"status": "connected"})
    assert doc is not None, "Nenhuma whatsapp_connection com status=connected"
    assert doc.get("access_token"), "connection sem access_token"
    return doc


class TestWabaSubscription:
    def test_connection_has_expected_waba_and_phone(self, connection_doc):
        assert connection_doc.get("business_account_id") == EXPECTED_WABA
        assert connection_doc.get("phone_number_id") == "1266842309849495"

    def test_subscribed_apps_lists_ravi_api(self, connection_doc):
        """Verificação central do fix: RAVI_API deve estar inscrito na WABA."""
        token = connection_doc["access_token"]
        waba = connection_doc["business_account_id"]
        r = requests.get(
            f"https://graph.facebook.com/{GRAPH_VER}/{waba}/subscribed_apps",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        assert r.status_code == 200, f"Graph API falhou: {r.status_code} {r.text[:200]}"
        data = r.json()
        apps = data.get("data") or []
        ids = [str((a.get("whatsapp_business_api_data") or {}).get("id") or a.get("id") or "") for a in apps]
        assert EXPECTED_APP_ID in ids, (
            f"App RAVI_API ({EXPECTED_APP_ID}) NÃO está inscrito. "
            f"Inscritos: {ids}"
        )


class TestBackendHealth:
    def test_backend_reloaded_without_errors(self):
        """Não deve haver tracebacks recentes no backend após a edição."""
        try:
            out = subprocess.check_output(
                ["bash", "-lc", "tail -n 200 /var/log/supervisor/backend.err.log 2>/dev/null"],
                timeout=5,
            ).decode("utf-8", "replace")
        except Exception as e:
            pytest.skip(f"Não foi possível ler logs: {e}")
        # Aceitável ter logs INFO/WARNING; procuramos traceback real
        bad_markers = ["Traceback (most recent call last)", "SyntaxError", "ImportError:", "ModuleNotFoundError"]
        found = [m for m in bad_markers if m in out]
        assert not found, f"Erros críticos nos logs do backend: {found}"

    def test_status_endpoint_returns_connected(self, admin_session):
        r = admin_session.get(f"{API}/whatsapp/status")
        assert r.status_code == 200, r.text
        body = r.json()
        conn = body.get("connection")
        assert conn is not None, f"connection ausente: {body}"
        assert conn.get("status") == "connected", f"status != connected: {conn}"
        assert conn.get("phone_number_id") == "1266842309849495"
