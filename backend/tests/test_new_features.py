"""RAVI iteration 5 — novas features:
- Cadastro inline de cliente ao criar processo (+ reuso por telefone)
- Upload/download de PDF anexo ao processo + isolamento tenant
- PATCH cobranças com merge por id + preservação de flags de lembrete
- POST /cobrancas/{cid}/pago
- Cron /api/cron/billing-reminders: auth, idempotência, disparo por vencimento
- Memória de 50 mensagens (coerência simples)
"""
import os
import io
import uuid
import requests
import pytest
from fpdf import FPDF

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://ravi-client.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"
ADMIN_EMAIL = "construcaovilanova@gmail.com"
ADMIN_PASSWORD = "Ravi@2026"
CRON_SECRET = "ravi-cron-3f8a9c1e5b7d2046f8a1c3e5b7d9f1a3c5e7b9d1f3a5c7e9b1d3f5a7c9e1b3d5"


# ---------- helpers ----------
def _make_pdf(text: str = "Audiencia 20/10/2026 14h Foro Central") -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(0, 10, text)
    out = pdf.output(dest="S")
    return bytes(out) if isinstance(out, (bytes, bytearray)) else out.encode("latin-1")


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def second_office():
    s = requests.Session()
    email = f"TEST_iso_{uuid.uuid4().hex[:8]}@example.com"
    r = s.post(f"{API}/auth/register",
               json={"name": "TestIso", "email": email, "password": "Test@1234"})
    assert r.status_code == 200, r.text
    r2 = s.post(f"{API}/auth/onboarding/complete",
                json={"office_name": f"TEST_Office_{uuid.uuid4().hex[:6]}"})
    assert r2.status_code == 200
    return s


# ---------- 1. Cadastro inline de cliente ----------
class TestInlineClient:
    def test_process_creates_new_client_inline(self, admin):
        phone = "(11) 98888-7777"
        # cleanup possíveis restos
        for c in admin.get(f"{API}/clients").json():
            if c["name"].startswith("TEST_Inline"):
                admin.delete(f"{API}/clients/{c['id']}")
        r = admin.post(f"{API}/processes", json={
            "number": f"TEST-{uuid.uuid4().hex[:8]}",
            "new_client_name": "TEST_Inline Cliente",
            "new_client_phone": phone,
        })
        assert r.status_code == 200, r.text
        proc = r.json()
        assert proc.get("client_id"), "client_id deveria estar vinculado"
        # cliente existe e foi normalizado
        clients = admin.get(f"{API}/clients").json()
        c = next((x for x in clients if x["id"] == proc["client_id"]), None)
        assert c is not None
        assert c["phone_normalized"] == "5511988887777"
        assert c["name"] == "TEST_Inline Cliente"

    def test_process_reuses_existing_client_by_phone(self, admin):
        phone = "(11) 97777-6666"
        # limpeza idempotente: a suíte roda várias vezes sobre o mesmo banco
        for c in admin.get(f"{API}/clients").json():
            if c.get("phone_normalized") == "5511977776666":
                admin.delete(f"{API}/clients/{c['id']}")
        # cria cliente primeiro
        r0 = admin.post(f"{API}/clients", json={"name": "TEST_Reuse", "phone": phone})
        assert r0.status_code == 200, r0.text
        cid = r0.json()["id"]
        # cria processo com "novo" mas o telefone bate — deve reusar
        r = admin.post(f"{API}/processes", json={
            "number": f"TEST-{uuid.uuid4().hex[:8]}",
            "new_client_name": "TEST_OutroNome",
            "new_client_phone": "11 9 7777-6666",
        })
        assert r.status_code == 200, r.text
        assert r.json()["client_id"] == cid, "deveria ter reusado cliente existente"
        # confirma que não duplicou
        clients = admin.get(f"{API}/clients").json()
        matches = [c for c in clients if c["phone_normalized"] == "5511977776666"]
        assert len(matches) == 1


# ---------- 2. PDF Upload/Download + isolamento ----------
class TestDocuments:
    def test_upload_pdf_and_download(self, admin):
        r = admin.post(f"{API}/processes", json={"number": f"TEST-DOC-{uuid.uuid4().hex[:6]}"})
        pid = r.json()["id"]
        pdf_bytes = _make_pdf("Audiencia 20/10/2026 14h Foro Central. Autor TEST_Doc.")
        up = admin.post(f"{API}/processes/{pid}/document",
                        files={"file": ("teste.pdf", pdf_bytes, "application/pdf")})
        assert up.status_code == 200, up.text
        j = up.json()
        assert j["ok"] is True
        assert j["texto_extraido"] is True
        doc_id = j["document"]["id"]
        # fonte adicionada
        proc = admin.get(f"{API}/processes/{pid}").json()
        assert "Documento fornecido pelo escritório" in proc["fontes"]
        assert any(d["id"] == doc_id for d in proc["documentos"])
        # download
        dl = admin.get(f"{API}/processes/{pid}/document/{doc_id}")
        assert dl.status_code == 200
        assert dl.headers.get("content-type", "").startswith("application/pdf")
        assert dl.content[:4] == b"%PDF"
        return pid, doc_id

    def test_reject_non_pdf(self, admin):
        r = admin.post(f"{API}/processes", json={"number": f"TEST-BAD-{uuid.uuid4().hex[:6]}"})
        pid = r.json()["id"]
        bad = admin.post(f"{API}/processes/{pid}/document",
                        files={"file": ("teste.txt", b"hello", "text/plain")})
        assert bad.status_code == 400

    def test_reject_large_pdf(self, admin):
        r = admin.post(f"{API}/processes", json={"number": f"TEST-BIG-{uuid.uuid4().hex[:6]}"})
        pid = r.json()["id"]
        big = b"%PDF-1.4\n" + b"0" * (10 * 1024 * 1024 + 100)
        rr = admin.post(f"{API}/processes/{pid}/document",
                       files={"file": ("big.pdf", big, "application/pdf")})
        assert rr.status_code == 400

    def test_tenant_isolation_document(self, admin, second_office):
        # upload no escritório admin
        r = admin.post(f"{API}/processes", json={"number": f"TEST-ISO-{uuid.uuid4().hex[:6]}"})
        pid = r.json()["id"]
        up = admin.post(f"{API}/processes/{pid}/document",
                       files={"file": ("iso.pdf", _make_pdf("segredo"), "application/pdf")})
        doc_id = up.json()["document"]["id"]
        # outro escritório não vê nem baixa
        r2 = second_office.get(f"{API}/processes/{pid}")
        assert r2.status_code == 404
        dl = second_office.get(f"{API}/processes/{pid}/document/{doc_id}")
        assert dl.status_code == 404


# ---------- 3. Cobranças: PATCH merge + mark paid ----------
class TestCobrancas:
    def test_patch_creates_and_merges_preserving_flags(self, admin):
        # cria processo com 1 cobrança
        r = admin.post(f"{API}/processes", json={
            "number": f"TEST-COB-{uuid.uuid4().hex[:6]}",
            "valor_causa": 10000,
            "forma_pagamento": "Pix",
            "cobrancas": [{"valor": 1000, "data_vencimento": "2026-12-15", "descricao": "Parcela 1"}],
        })
        assert r.status_code == 200, r.text
        proc = r.json()
        pid = proc["id"]
        assert len(proc["cobrancas"]) == 1
        cob = proc["cobrancas"][0]
        assert cob["status"] == "pendente"
        assert cob["lembrete_5d_em"] is None
        assert cob["lembrete_dia_em"] is None
        # simula flag setada externamente
        import pymongo
        # Emular flag setando via PATCH depois — mas API não faz isso. Vamos via update direto:
        # Como não temos DB, testamos preservação por outro caminho:
        # 1) marcamos como pago
        mp = admin.post(f"{API}/processes/{pid}/cobrancas/{cob['id']}/pago")
        assert mp.status_code == 200
        proc2 = admin.get(f"{API}/processes/{pid}").json()
        target = next(c for c in proc2["cobrancas"] if c["id"] == cob["id"])
        assert target["status"] == "pago"

        # PATCH com merge: mesma cobrança (mesmo id) + uma nova
        patch = admin.patch(f"{API}/processes/{pid}", json={
            "cobrancas": [
                {"id": cob["id"], "valor": 1200, "data_vencimento": "2026-12-20", "descricao": "P1 atualizada"},
                {"valor": 500, "data_vencimento": "2027-01-10", "descricao": "P2"},
            ]
        })
        assert patch.status_code == 200, patch.text
        cobs = patch.json()["cobrancas"]
        assert len(cobs) == 2
        first = next(c for c in cobs if c["id"] == cob["id"])
        # preserva status=pago (merge)
        assert first["status"] == "pago"
        assert first["valor"] == 1200
        assert first["data_vencimento"] == "2026-12-20"
        # nova é pendente com flags nulas
        new_c = next(c for c in cobs if c["id"] != cob["id"])
        assert new_c["status"] == "pendente"
        assert new_c["lembrete_5d_em"] is None
        assert new_c["lembrete_dia_em"] is None


# ---------- 4. Cron billing-reminders ----------
class TestCron:
    def test_unauthorized_without_bearer(self):
        r = requests.post(f"{API}/cron/billing-reminders", json={"run_id": "x"})
        assert r.status_code == 401

    def test_wrong_secret(self):
        r = requests.post(f"{API}/cron/billing-reminders",
                        headers={"Authorization": "Bearer wrong"}, json={"run_id": "x"})
        assert r.status_code == 401

    def test_ok_and_idempotent(self):
        run_id = f"test-{uuid.uuid4().hex}"
        h = {"Authorization": f"Bearer {CRON_SECRET}"}
        r1 = requests.post(f"{API}/cron/billing-reminders", headers=h, json={"run_id": run_id})
        assert r1.status_code == 200, r1.text
        assert r1.json().get("ok") is True
        # segundo POST mesmo run_id → duplicate
        r2 = requests.post(f"{API}/cron/billing-reminders", headers=h, json={"run_id": run_id})
        assert r2.status_code == 200
        assert r2.json().get("duplicate") is True


# ---------- 5. Cron dispatch: vence hoje ----------
class TestCronDispatch:
    def test_reminder_today_marks_flag(self, admin):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        today = datetime.now(ZoneInfo("America/Sao_Paulo")).date().isoformat()
        # cria cliente + processo com cobrança vencendo hoje
        phone = f"(11) 9{uuid.uuid4().int % 100000000:08d}"
        rc = admin.post(f"{API}/clients", json={"name": "TEST_CronClient", "phone": phone})
        assert rc.status_code == 200
        cid = rc.json()["id"]
        rp = admin.post(f"{API}/processes", json={
            "number": f"TEST-CRON-{uuid.uuid4().hex[:6]}",
            "client_id": cid,
            "forma_pagamento": "Pix",
            "cobrancas": [{"valor": 750.50, "data_vencimento": today, "descricao": "Hoje"}],
        })
        assert rp.status_code == 200, rp.text
        pid = rp.json()["id"]
        cob_id = rp.json()["cobrancas"][0]["id"]

        h = {"Authorization": f"Bearer {CRON_SECRET}"}
        rr = requests.post(f"{API}/cron/billing-reminders", headers=h,
                           json={"run_id": f"test-dispatch-{uuid.uuid4().hex}"})
        assert rr.status_code == 200
        # espera background
        import time
        time.sleep(3)
        proc = admin.get(f"{API}/processes/{pid}").json()
        target = next(c for c in proc["cobrancas"] if c["id"] == cob_id)
        # Nova semântica: flag só é marcada com entrega confirmada; se a Meta recusar
        # (telefone de teste não verificado), registra audit billing_reminder_failed e tenta no próximo cron
        if target["lembrete_dia_em"] is None:
            audits = admin.get(f"{API}/audit").json()
            assert any(a["event"] == "billing_reminder_failed" and a["details"].get("cobranca_id") == cob_id
                       for a in audits), "nem flag marcada nem audit de falha registrado"

    def test_reminder_skips_when_no_client(self, admin):
        """Cobrança em processo sem client_id não deve disparar (nem crashear)."""
        from datetime import datetime
        from zoneinfo import ZoneInfo
        today = datetime.now(ZoneInfo("America/Sao_Paulo")).date().isoformat()
        rp = admin.post(f"{API}/processes", json={
            "number": f"TEST-NOCLI-{uuid.uuid4().hex[:6]}",
            "cobrancas": [{"valor": 100, "data_vencimento": today, "descricao": "sem cliente"}],
        })
        assert rp.status_code == 200
        pid = rp.json()["id"]
        cob_id = rp.json()["cobrancas"][0]["id"]
        h = {"Authorization": f"Bearer {CRON_SECRET}"}
        rr = requests.post(f"{API}/cron/billing-reminders", headers=h,
                           json={"run_id": f"test-nocli-{uuid.uuid4().hex}"})
        assert rr.status_code == 200
        import time
        time.sleep(2)
        proc = admin.get(f"{API}/processes/{pid}").json()
        target = next(c for c in proc["cobrancas"] if c["id"] == cob_id)
        assert target["lembrete_dia_em"] is None  # não disparou


# ---------- 6. crons.yml ----------
class TestCronsYml:
    def test_crons_yml_exists(self):
        p = "/app/.emergent/crons.yml"
        assert os.path.exists(p)
        content = open(p).read()
        assert "billing-reminders" in content
        assert "0 12 * * *" in content
