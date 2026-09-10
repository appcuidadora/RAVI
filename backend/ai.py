import os
import logging
from datetime import datetime, timezone
from database import db

logger = logging.getLogger(__name__)

_ai_cfg_cache = {"at": 0.0, "data": None}


async def _ai_global_config() -> dict:
    """Configuração global de IA (RAVI ADMIN). Cache de 60s. Regras globais são inegociáveis."""
    import time
    t = time.time()
    if _ai_cfg_cache["data"] is not None and t - _ai_cfg_cache["at"] < 60:
        return _ai_cfg_cache["data"]
    doc = await db.platform_settings.find_one({"id": "global"}, {"_id": 0, "ai_config": 1})
    cfg = (doc or {}).get("ai_config") or {}
    _ai_cfg_cache["at"] = t
    _ai_cfg_cache["data"] = cfg
    return cfg

RED_SIGNALS = [
    "estrateg", "recurs", "recorrer", "acordo", "negoci", "acelerar", "vale a pena",
    "compensa", "devo ", "o que eu faço", "o que eu faco", "orienta", "decidir",
    "honorár", "honorar", "pagamento", "pagar", "desistir", "prazo", "multa",
    "reclama", "demora", "demorando", "absurdo", "raiva", "frustrad",
]

GREEN_SIGNALS = [
    "novidade", "andamento", "movimenta", "como está", "como esta", "como anda",
    "status", "já saiu", "ja saiu", "saiu alguma", "última", "ultima",
    "alguma coisa", "atualização", "atualizacao", "notícia", "noticia",
    "oi ", "olá", "ola", "bom dia", "boa tarde", "boa noite",
]

ESCALATION_REPLY = (
    "Essa é uma questão que precisa ser analisada pelo advogado responsável pelo processo. "
    "Vou encaminhar sua mensagem para ele e você receberá um retorno em breve."
)

UNKNOWN_REPLY = (
    "Não consegui confirmar essa informação nas fontes disponíveis. "
    "Vou encaminhar para o responsável pelo processo."
)


async def transcribe_audio(data: bytes) -> str:
    """Transcreve áudio do WhatsApp (ogg/opus) para texto pt-BR via Whisper.
    A lib só aceita mp3/mp4/mpeg/mpga/m4a/wav/webm — converte o ogg com ffmpeg antes."""
    import io
    import subprocess
    import tempfile
    from emergentintegrations.llm.openai import OpenAISpeechToText
    src = mp3 = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as fin:
            fin.write(data)
            src = fin.name
        mp3 = src[:-4] + ".mp3"
        subprocess.run(["ffmpeg", "-y", "-i", src, "-vn", "-acodec", "libmp3lame", "-q:a", "4", mp3],
                       check=True, capture_output=True, timeout=60)
        with open(mp3, "rb") as f:
            payload = f.read()
    finally:
        for p in (src, mp3):
            if p:
                try:
                    os.unlink(p)
                except OSError:
                    pass
    stt = OpenAISpeechToText(api_key=os.environ["EMERGENT_LLM_KEY"])
    buf = io.BytesIO(payload)
    buf.name = "audio.mp3"
    resp = await stt.transcribe(
        file=buf, model="whisper-1", response_format="json", language="pt",
        prompt="Mensagem de voz de um cliente de escritório de advocacia em português do Brasil.")
    return (getattr(resp, "text", "") or "").strip()


def classify_message(text: str) -> tuple:
    """Motor de decisão do RAVI: VERDE (responde), AMARELO (responde + acompanha), VERMELHO (humano)."""
    t = (text or "").lower()
    for sig in RED_SIGNALS:
        if sig in t:
            return "red", "Orientação jurídica/estratégica ou tema sensível detectado"
    for sig in GREEN_SIGNALS:
        if sig in t:
            return "green", "Pergunta objetiva sobre andamento/status"
    return "yellow", "Pergunta fora do padrão — resposta objetiva com acompanhamento"


def _process_context(process: dict) -> str:
    if not process:
        return "Nenhum processo vinculado a este cliente no momento."
    movs = process.get("movimentacoes") or []
    mov_txt = "\n".join(f"- {m.get('data')}: {m.get('descricao')}" for m in movs[-5:]) or "Sem movimentações registradas."
    return (
        f"Processo: {process.get('numero_formatado') or process.get('number')}\n"
        f"Tribunal: {process.get('tribunal', 'não identificado')}\n"
        f"Situação: {process.get('status', 'em andamento')}\n"
        f"Última movimentação: {process.get('ultima_movimentacao', 'não registrada')}\n"
        f"Movimentações recentes:\n{mov_txt}"
    )


def fallback_reply(client_name: str, process: dict) -> str:
    first = (client_name or "").split()[0] or "tudo bem"
    if process:
        status = process.get("status", "em andamento")
        last = process.get("ultima_movimentacao", "")
        msg = f"Olá, {first}! Consultei as informações disponíveis do seu processo. No momento, ele continua {status.lower()}."
        if last:
            msg += f" A última movimentação registrada foi em {last}."
        msg += " Até agora não identifiquei nenhuma nova providência que você precise tomar."
        return msg
    return f"Olá, {first}! Recebi sua mensagem e já estou verificando as informações. Qualquer novidade, aviso por aqui."


async def generate_ravi_reply(office: dict, client: dict, process: dict, history: list, text: str) -> str:
    tone = (office or {}).get("tone", "acolhedor")
    hist_lines = []
    for m in (history or [])[-50:]:
        who = {"client": "Cliente", "ravi": "Ravi", "user": "Advogado"}.get(m.get("sender"), "Cliente")
        hist_lines.append(f"{who}: {m.get('text', '')}")
    hist_txt = "\n".join(hist_lines) or "(sem mensagens anteriores)"
    docs_txt = ""
    if process:
        docs = [d for d in (process.get("documentos") or []) if d.get("texto")]
        if docs:
            joined = "\n---\n".join(f"Documento '{d['filename']}':\n{d['texto'][:3500]}" for d in docs[:2])
            docs_txt = (f"\nCONTEÚDO DE DOCUMENTOS DO PROCESSO (PDFs fornecidos pelo escritório):\n{joined}\n")
    system = (
        f"Você é o RAVI, assistente de atendimento do escritório de advocacia '{(office or {}).get('name', '')}'. "
        f"Tom de voz: {tone}. Responda sempre em português do Brasil, de forma curta (máx. 4 frases), clara e humana, sem juridiquês. "
        "REGRAS INEGOCIÁVEIS: use apenas as informações do contexto abaixo; nunca invente dados, datas ou decisões; "
        "nunca dê orientação jurídica, opinião estratégica ou prometa resultados; "
        "se a informação não estiver no contexto, diga que vai confirmar com o responsável pelo processo; "
        "leve em conta o histórico da conversa para não repetir informações nem saudações.\n\n"
        f"CONTEXTO DO CLIENTE: {client.get('name', 'Cliente')}\n"
        f"CONTEXTO DO PROCESSO:\n{_process_context(process)}\n{docs_txt}\n"
        f"HISTÓRICO DA CONVERSA (do mais antigo ao mais recente):\n{hist_txt}"
    )
    cfg = await _ai_global_config()
    rules = cfg.get("rules") or []
    if rules:
        system += "\n\nREGRAS GLOBAIS DO RAVI (inegociáveis, nunca podem ser violadas):\n" + \
            "\n".join(f"- {r}" for r in rules)
    if cfg.get("autonomia") == "restrito":
        system += ("\nMODO RESTRITO: responda apenas perguntas objetivas sobre andamento/status; "
                   "todo o restante deve ser encaminhado ao advogado responsável.")
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(
            api_key=os.environ["EMERGENT_LLM_KEY"],
            session_id=f"ravi-{(client or {}).get('id', 'anon')}-{datetime.now(timezone.utc).timestamp()}",
            system_message=system,
        ).with_model("anthropic", "claude-sonnet-4-6")
        reply = await chat.send_message(UserMessage(text=text))
        if reply and reply.strip():
            return reply.strip()
    except Exception as e:
        logger.error(f"RAVI LLM fallback: {e}")
    return fallback_reply(client.get("name", ""), process)
