"""RAVI Fase 7: segurança — isolamento multi-tenant (Office A × Office B), RBAC do RAVI ADMIN,
assinatura obrigatória do webhook, invalidação de sessão no logout e cobertura de auditoria.

Office A = Silva Advocacia (demo). Office B = escritório criado pelo próprio teste.
Ordem das classes importa: TestSessionSecurity invalida a sessão de B (token_version);
TestAuditCoverage faz login fresco de B antes de checar os eventos.
"""
import os
import uuid
import json
import hmac
import hashlib
import requests
import pytest
from _webhook_sign import signed_webhook_post, WEBHOOK_TEST_SECRET

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://ravi-client.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"
ADMIN_EMAIL = "construcaovilanova@gmail.com"
ADMIN_PASSWORD = "Ravi@2026"


def _admin_session():
    s = requests.Session()
    r = s.post(f"{API}/admin/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def office_a():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    clients = s.get(f"{API}/clients").json()
    procs = s.get(f"{API}/processes").json()
    convs = s.get(f"{API}/conversations").json()
    assert clients and procs and convs, "Dados demo do Office A ausentes"
    return {"session": s, "client_id": clients[0]["id"],
            "process_id": procs[0]["id"], "conversation_id": convs[0]["id"]}


@pytest.fixture(scope="module")
def office_b():
    email = f"fase7_b_{uuid.uuid4().hex[:8]}@teste.com"
    pwd = "Fase7@Segura123"
    s = requests.Session()
    r = s.post(f"{API}/auth/register",
               json={"name": "Advogado", "last_name": "B", "email": email, "password": pwd})
    assert r.status_code == 200, r.text
    r = s.post(f"{API}/auth/onboarding/complete",
               json={"office_name": f"Escritorio B {uuid.uuid4().hex[:6]}"})
    assert r.status_code == 200, r.text
    office_id = r.json()["office"]["id"]
    r = s.post(f"{API}/clients", json={"name": "Cliente do B", "phone": "+55 21 90000-0001"})
    assert r.status_code == 200, r.text
    return {"session": s, "email": email, "password": pwd,
            "office_id": office_id, "client_id": r.json()["id"]}


class TestMultiTenantIsolation:
    def test_b_nao_le_cliente_de_a(self, office_a, office_b):
        r = office_b["session"].get(f"{API}/clients/{office_a['client_id']}")
        assert r.status_code == 404, r.text

    def test_b_nao_edita_cliente_de_a(self, office_a, office_b):
        r = office_b["session"].patch(f"{API}/clients/{office_a['client_id']}",
                                      json={"name": "Invadido", "phone": "+55 21 90000-0002"})
        assert r.status_code == 404, r.text

    def test_b_nao_deleta_cliente_de_a(self, office_a, office_b):
        r = office_b["session"].delete(f"{API}/clients/{office_a['client_id']}")
        assert r.status_code == 404, r.text

    def test_b_nao_le_processo_de_a(self, office_a, office_b):
        r = office_b["session"].get(f"{API}/processes/{office_a['process_id']}")
        assert r.status_code == 404, r.text

    def test_b_nao_le_conversa_de_a(self, office_a, office_b):
        r = office_b["session"].get(f"{API}/conversations/{office_a['conversation_id']}")
        assert r.status_code == 404, r.text

    def test_listagem_de_b_nao_vaza_dados_de_a(self, office_a, office_b):
        clients = office_b["session"].get(f"{API}/clients").json()
        assert all(c["id"] != office_a["client_id"] for c in clients)
        procs = office_b["session"].get(f"{API}/processes").json()
        assert all(p["id"] != office_a["process_id"] for p in procs)

    def test_a_nao_vincula_cliente_de_b_em_conversa_de_a(self, office_a, office_b):
        r = office_a["session"].post(
            f"{API}/conversations/{office_a['conversation_id']}/link-client",
            json={"client_id": office_b["client_id"]})
        assert r.status_code == 404, r.text

    def test_uso_whatsapp_de_b_mostra_apenas_b(self, office_b):
        r = office_b["session"].get(f"{API}/whatsapp/usage")
        assert r.status_code == 200, r.text
        assert r.json()["mensagens_total"] == 0

    def test_usuario_tenant_nao_entra_no_admin(self, office_b):
        r = requests.post(f"{API}/admin/auth/login",
                          json={"email": office_b["email"], "password": office_b["password"]})
        assert r.status_code == 401, r.text
        r = office_b["session"].get(f"{API}/admin/dashboard")
        assert r.status_code == 401, r.text


class TestAdminRBAC:
    @pytest.fixture(scope="class")
    def analista(self):
        sa = _admin_session()
        email = f"analista_f7_{uuid.uuid4().hex[:6]}@ravi.app"
        r = sa.post(f"{API}/admin/users", json={"name": "Analista F7", "email": email, "role": "ANALISTA"})
        assert r.status_code == 200, r.text
        temp = r.json()["temp_password"]
        s = requests.Session()
        r = s.post(f"{API}/admin/auth/login", json={"email": email, "password": temp})
        assert r.status_code == 200, r.text
        return s

    def test_analista_nao_impersona(self, analista, office_b):
        r = analista.post(f"{API}/admin/offices/{office_b['office_id']}/impersonate",
                          json={"motivo": "teste de segurança fase 7"})
        assert r.status_code == 403, r.text

    def test_analista_nao_cria_plano(self, analista):
        r = analista.post(f"{API}/admin/plans", json={"name": f"PLANO_{uuid.uuid4().hex[:6]}"})
        assert r.status_code == 403, r.text

    def test_analista_nao_toca_secrets(self, analista):
        r = analista.post(f"{API}/admin/meta/secrets", json={"meta_app_id": "123"})
        assert r.status_code == 403, r.text

    def test_analista_nao_cria_cobranca(self, analista, office_b):
        r = analista.post(f"{API}/admin/billing/charges",
                          json={"office_id": office_b["office_id"], "descricao": "x",
                                "valor": 10, "data_vencimento": "2026-12-01"})
        assert r.status_code == 403, r.text

    def test_analista_le_dashboard(self, analista):
        r = analista.get(f"{API}/admin/dashboard")
        assert r.status_code == 200, r.text

    def test_super_admin_impersona_com_motivo(self, office_b):
        sa = _admin_session()
        r = sa.post(f"{API}/admin/offices/{office_b['office_id']}/impersonate",
                    json={"motivo": "regressão fase 7"})
        assert r.status_code == 200, r.text
        assert r.json()["token"]


class TestWebhookSignature:
    def test_post_sem_assinatura_403(self):
        r = requests.post(f"{API}/webhooks/whatsapp", json={"entry": []})
        assert r.status_code == 403, r.text

    def test_post_assinatura_errada_403(self):
        body = json.dumps({"entry": []}).encode()
        sig = "sha256=" + hmac.new(b"segredo-errado", body, hashlib.sha256).hexdigest()
        r = requests.post(f"{API}/webhooks/whatsapp", data=body,
                          headers={"Content-Type": "application/json", "X-Hub-Signature-256": sig})
        assert r.status_code == 403, r.text

    def test_post_assinado_200(self):
        r = signed_webhook_post({"entry": []})
        assert r.status_code == 200, r.text
        assert r.json() == {"ok": True}


class TestSessionSecurity:
    def test_logout_invalida_access_e_refresh(self, office_b):
        s = requests.Session()
        r = s.post(f"{API}/auth/login",
                   json={"email": office_b["email"], "password": office_b["password"]})
        assert r.status_code == 200, r.text
        assert s.get(f"{API}/auth/me").status_code == 200
        r = s.post(f"{API}/auth/logout")
        assert r.status_code == 200
        assert s.get(f"{API}/auth/me").status_code == 401
        assert s.post(f"{API}/auth/refresh").status_code == 401


class TestAuditCoverage:
    def test_eventos_de_seguranca_registrados(self, office_b):
        s = requests.Session()
        r = s.post(f"{API}/auth/login",
                   json={"email": office_b["email"], "password": office_b["password"]})
        assert r.status_code == 200, r.text
        r = s.delete(f"{API}/clients/{office_b['client_id']}")
        assert r.status_code == 200, r.text
        sa = _admin_session()
        r = sa.get(f"{API}/admin/logs", params={"tipo": "tenant", "office_id": office_b["office_id"]})
        assert r.status_code == 200, r.text
        events = {l.get("event") for l in r.json()["logs"]}
        assert "user_login" in events
        assert "user_logout" in events
        assert "client_created" in events
        assert "client_deleted" in events
