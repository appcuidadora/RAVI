import re
from typing import Optional


def normalize_phone(phone: str) -> str:
    """Regra única de normalização de telefone (usada em cadastro, webhook, busca e conversas):
    1. Remove tudo que não é dígito (+, espaços, parênteses, hífens).
    2. Se tiver 10-11 dígitos (DDD + número), assume Brasil e prefixa 55.
    3. Resultado: apenas dígitos com código do país, ex: 5511987654321.
    """
    digits = re.sub(r"\D", "", phone or "")
    if not digits:
        return ""
    if digits.startswith("55") and len(digits) in (12, 13):
        return digits
    if len(digits) in (10, 11):
        return "55" + digits
    return digits


def format_phone_br(normalized: str) -> str:
    d = re.sub(r"\D", "", normalized or "")
    if d.startswith("55") and len(d) in (12, 13):
        ddd = d[2:4]
        rest = d[4:]
        if len(rest) == 9:
            return f"+55 ({ddd}) {rest[:5]}-{rest[5:]}"
        return f"+55 ({ddd}) {rest[:4]}-{rest[4:]}"
    return f"+{d}" if d else ""


SEGMENTOS_JUSTICA = {
    "1": "Supremo Tribunal Federal",
    "2": "Conselho Nacional de Justiça",
    "3": "Superior Tribunal de Justiça",
    "4": "Justiça Federal",
    "5": "Justiça do Trabalho",
    "6": "Justiça Eleitoral",
    "7": "Justiça Militar da União",
    "8": "Justiça Estadual",
    "9": "Justiça Militar Estadual",
}

TRIBUNAIS = {
    "26": "TJSP — Tribunal de Justiça de São Paulo",
    "19": "TJRJ — Tribunal de Justiça do Rio de Janeiro",
    "13": "TJMG — Tribunal de Justiça de Minas Gerais",
    "21": "TJRS — Tribunal de Justiça do Rio Grande do Sul",
    "16": "TJPR — Tribunal de Justiça do Paraná",
    "24": "TJSC — Tribunal de Justiça de Santa Catarina",
    "15": "TJPE — Tribunal de Justiça de Pernambuco",
    "05": "TJBA — Tribunal de Justiça da Bahia",
    "06": "TJCE — Tribunal de Justiça do Ceará",
    "10": "TJGO — Tribunal de Justiça de Goiás",
    "08": "TJDFT — Tribunal de Justiça do Distrito Federal e Territórios",
}

CNJ_RE = re.compile(r"^(\d{7})-?(\d{2})\.?(\d{4})\.?(\d)\.?(\d{2})\.?(\d{4})$")


def parse_cnj(number: str) -> Optional[dict]:
    """Extrai metadados de um número CNJ (NNNNNNN-DD.AAAA.J.TR.OOOO).
    Não garante acesso às informações do processo — apenas identifica a estrutura do número."""
    if not number:
        return None
    m = CNJ_RE.match(number.strip())
    if not m:
        return None
    seq, dv, ano, seg, tr, origem = m.groups()
    return {
        "numero_sequencial": seq,
        "digito_verificador": dv,
        "ano": ano,
        "segmento_codigo": seg,
        "segmento": SEGMENTOS_JUSTICA.get(seg, f"Segmento {seg}"),
        "tribunal_codigo": tr,
        "tribunal": TRIBUNAIS.get(tr, f"Tribunal (código {tr})"),
        "unidade_origem": origem,
        "numero_formatado": f"{seq}-{dv}.{ano}.{seg}.{tr}.{origem}",
    }
