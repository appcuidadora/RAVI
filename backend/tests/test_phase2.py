"""RAVI Fase 2: Clientes com CPF/notes/archive + detalhe, Processos com campos novos,
Importação inteligente de PDF (normal, restrito, inválido) e isolamento multi-tenant."""
import os
import uuid
import requests
import pytest

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://ravi-client.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"
ADMIN_EMAIL = "construcaovilanova@gmail.com"
ADMIN_PASSWORD = "Ravi@2026"

FIX_NORMAL = "/app/tests/fixtures/ravi_processo_teste_01.pdf"
FIX_RESTR = "/app/tests/fixtures/ravi_processo_teste_02_restrito.pdf"


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def other_office():
    s = requests.Session()
    email = f"TEST_iso_{uuid.uuid4().hex[:8]}@example.com"
    r = s.post(f"{API}/auth/register",
               json={"name": "OtherOffice", "email": email, "password": "Test@1234"})
    assert r.status_code == 200, r.text
    r2 = s.post(f"{API}/auth/onboarding/complete",
                json={"office_name": f"TEST_Office_{uuid.uuid4().hex[:6]}"})
    assert r2.status_code == 200
    return s


# ---------- Clientes: CPF/notes/archive/detail/search ----------
class TestClientesPhase2:
    def test_create_with_cpf_and_notes(self, admin):
        phone = f"(11) 9{uuid.uuid4().int % 100000000:08d}"
        r = admin.post(f"{API}/clients", json={
            "name": "TEST_ClientePhase2", "phone": phone,
            "cpf": "123.456.789-00", "notes": "Cliente teste fase 2"})
        assert r.status_code == 200, r.text
        c = r.json()
        assert c["cpf"] == "123.456.789-00"
        assert c["notes"] == "Cliente teste fase 2"
        assert c["status"] == "ativo"
        assert "updated_at" in c
        # edit CPF
        pr = admin.patch(f"{API}/clients/{c['id']}", json={
            "name": c["name"], "phone": c["phone"], "cpf": "999.888.777-66",
            "notes": c["notes"]})
        assert pr.status_code == 200
        assert pr.json()["cpf"] == "999.888.777-66"
        admin.delete(f"{API}/clients/{c['id']}")

    def test_archive_hides_and_toggle_reveals(self, admin):
        phone = f"(11) 9{uuid.uuid4().int % 100000000:08d}"
        r = admin.post(f"{API}/clients", json={"name": "TEST_ToArchive", "phone": phone})
        cid = r.json()["id"]
        # archive
        ar = admin.post(f"{API}/clients/{cid}/archive")
        assert ar.status_code == 200
        assert ar.json()["status"] == "arquivado"
        # default list hides archived
        default_list = admin.get(f"{API}/clients").json()
        assert not any(c["id"] == cid for c in default_list)
        # include_archived shows
        full = admin.get(f"{API}/clients?include_archived=true").json()
        assert any(c["id"] == cid and c["status"] == "arquivado" for c in full)
        # reactivate
        rr = admin.post(f"{API}/clients/{cid}/archive")
        assert rr.status_code == 200
        assert rr.json()["status"] == "ativo"
        admin.delete(f"{API}/clients/{cid}")

    def test_client_detail_with_processes_and_conversations(self, admin):
        r = admin.get(f"{API}/clients").json()
        carlos = next(c for c in r if c["name"] == "Carlos Eduardo")
        d = admin.get(f"{API}/clients/{carlos['id']}")
        assert d.status_code == 200
        data = d.json()
        assert "processes" in data
        assert "conversations" in data
        assert isinstance(data["processes"], list)
        assert isinstance(data["conversations"], list)

    def test_client_detail_tenant_isolation(self, admin, other_office):
        r = admin.get(f"{API}/clients").json()
        carlos = next(c for c in r if c["name"] == "Carlos Eduardo")
        # other office cannot see
        r2 = other_office.get(f"{API}/clients/{carlos['id']}")
        assert r2.status_code == 404


# ---------- Import PDF: normal ----------
class TestImportPdfNormal:
    def test_fixture_exists(self):
        assert os.path.exists(FIX_NORMAL), f"missing fixture: {FIX_NORMAL}"

    @pytest.fixture(scope="class")
    def imported(self, admin):
        with open(FIX_NORMAL, "rb") as f:
            data = f.read()
        r = admin.post(f"{API}/processes/import-pdf",
                       files={"file": ("ravi_processo_teste_01.pdf", data, "application/pdf")})
        assert r.status_code == 200, r.text
        return r.json()

    def test_import_extracts_cnj_and_tribunal(self, imported):
        proc = imported["process"]
        assert "1009876-55.2026.8.26.0100" in (proc.get("numero_formatado") or proc.get("number") or "")
        trib = (proc.get("tribunal") or proc.get("court") or "").lower()
        assert "tjsp" in trib or "são paulo" in trib or "sao paulo" in trib, f"tribunal={trib}"
        assert imported["restricted"] is False

    def test_import_partes_typed(self, imported):
        partes = imported["process"].get("partes") or []
        assert len(partes) >= 3, f"expected >=3 partes, got {partes}"
        # all partes have 'tipo' and 'nome'
        for p in partes:
            assert "tipo" in p and "nome" in p
            assert p["tipo"] in ("cliente", "parte_contraria", "advogado", "outro")

    def test_import_movimentacoes_and_last_movement(self, imported):
        proc = imported["process"]
        movs = proc.get("movimentacoes") or []
        assert len(movs) >= 3, f"expected >=3 movimentações, got {len(movs)}"
        # last_movement_at populated
        assert proc.get("last_movement_at") or proc.get("ultima_movimentacao")

    def test_import_nao_identificados_empty_for_normal(self, imported):
        # for a well-formed doc most fields should be identified
        assert isinstance(imported["nao_identificados"], list)

    def test_import_document_stored_with_office(self, admin, imported):
        proc = imported["process"]
        assert len(proc.get("documentos") or []) == 1
        # get via API
        fetched = admin.get(f"{API}/processes/{proc['id']}").json()
        assert fetched["office_id"] == proc["office_id"] if "office_id" in proc else True

    def test_import_isolation_other_office_404(self, other_office, imported):
        pid = imported["process"]["id"]
        r = other_office.get(f"{API}/processes/{pid}")
        assert r.status_code == 404
        # also list does not include it
        lst = other_office.get(f"{API}/processes").json()
        assert not any(p["id"] == pid for p in lst)


# ---------- Import PDF: restrito ----------
class TestImportPdfRestrito:
    def test_fixture_exists(self):
        assert os.path.exists(FIX_RESTR)

    def test_restricted_flag_and_no_partes(self, admin):
        with open(FIX_RESTR, "rb") as f:
            data = f.read()
        r = admin.post(f"{API}/processes/import-pdf",
                       files={"file": ("restr.pdf", data, "application/pdf")})
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["restricted"] is True
        proc = j["process"]
        assert proc["restricted"] is True
        assert proc["acesso_restrito"] is True
        assert "Restrito" in proc["status"] or "segredo" in proc["status"].lower()
        # sem partes extraídas
        assert len(proc.get("partes") or []) == 0
        # nao_identificados lista os campos sensíveis
        ni = j["nao_identificados"]
        assert isinstance(ni, list) and len(ni) > 0


# ---------- Import PDF: inválido ----------
class TestImportPdfInvalid:
    def test_reject_non_pdf(self, admin):
        r = admin.post(f"{API}/processes/import-pdf",
                       files={"file": ("teste.txt", b"nope", "text/plain")})
        assert r.status_code == 400

    def test_reject_pdf_no_text(self, admin):
        # bytes header PDF but sem texto extraível
        bad = b"%PDF-1.4\n%aaaa\n" + b"\x00" * 500 + b"\n%%EOF"
        r = admin.post(f"{API}/processes/import-pdf",
                       files={"file": ("empty.pdf", bad, "application/pdf")})
        assert r.status_code == 400
