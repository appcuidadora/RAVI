import os
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

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
    system = (
        f"Você é o RAVI, assistente de atendimento do escritório de advocacia '{(office or {}).get('name', '')}'. "
        f"Tom de voz: {tone}. Responda sempre em português do Brasil, de forma curta (máx. 4 frases), clara e humana, sem juridiquês. "
        "REGRAS INEGOCIÁVEIS: use apenas as informações do contexto abaixo; nunca invente dados, datas ou decisões; "
        "nunca dê orientação jurídica, opinião estratégica ou prometa resultados; "
        "se a informação não estiver no contexto, diga que vai confirmar com o responsável pelo processo.\n\n"
        f"CONTEXTO DO CLIENTE: {client.get('name', 'Cliente')}\n"
        f"CONTEXTO DO PROCESSO:\n{_process_context(process)}"
    )
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
