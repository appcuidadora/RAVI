import { useEffect, useRef, useState, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { api, apiError } from "@/lib/api";
import { toast } from "sonner";
import { Pause, Play, UserCheck, Send, Bot, Link2, UserPlus, Mic } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

const RISK_META = {
  green: { label: "Ravi cuidando", cls: "bg-emerald-950/60 border-emerald-700/50 text-emerald-400", dot: "bg-emerald-500" },
  yellow: { label: "Acompanhamento", cls: "bg-amber-950/60 border-amber-700/50 text-amber-400", dot: "bg-amber-500" },
  red: { label: "Precisa de você", cls: "bg-rose-950/60 border-rose-700/50 text-rose-400", dot: "bg-rose-500" },
};

function Bubble({ m }) {
  const isClient = m.sender === "client";
  const isRavi = m.sender === "ravi";
  return (
    <div className={`flex ${isClient ? "justify-start" : "justify-end"}`} data-testid={`message-${m.id}`}>
      <div className={
        isClient
          ? "bg-[#161925] text-zinc-200 border border-[#23283E] rounded-2xl rounded-tl-sm p-3.5 max-w-[80%]"
          : isRavi
            ? "bg-gradient-to-br from-indigo-950/80 to-blue-950/80 border border-indigo-700/40 text-zinc-100 rounded-2xl rounded-tr-sm p-4 max-w-[85%] shadow-lg shadow-indigo-950/30"
            : "bg-blue-600/90 text-white rounded-2xl rounded-tr-sm p-3.5 max-w-[80%]"
      }>
        {m.kind === "audio" && (
          <p className="flex items-center gap-1.5 text-[10px] font-mono-code uppercase tracking-widest text-zinc-500 mb-1.5">
            <Mic size={11} /> áudio transcrito
          </p>
        )}
        {isRavi && (
          <p className="flex items-center gap-1.5 text-[10px] font-mono-code uppercase tracking-widest text-indigo-300 mb-1.5">
            <Bot size={11} /> Ravi {m.risk_level === "red" ? "• escalonado" : ""}
          </p>
        )}
        <p className="text-sm leading-relaxed whitespace-pre-wrap">{m.text}</p>
        <p className="text-[10px] mt-1.5 opacity-50">
          {new Date(m.created_at).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}
          {!isClient && !m.delivered && " • aguardando conexão WhatsApp"}
        </p>
      </div>
    </div>
  );
}

export default function Conversas() {
  const [params, setParams] = useSearchParams();
  const [convs, setConvs] = useState([]);
  const [active, setActive] = useState(null);
  const [text, setText] = useState("");
  const [simText, setSimText] = useState("");
  const [filter, setFilter] = useState("all");
  const [linkOpen, setLinkOpen] = useState(false);
  const [clients, setClients] = useState([]);
  const [linkClientId, setLinkClientId] = useState("");
  const [newClientName, setNewClientName] = useState("");
  const bottomRef = useRef(null);

  const loadConvs = useCallback(() => api.get("/conversations").then((r) => setConvs(r.data)).catch(() => {}), []);

  const openConv = useCallback(async (id) => {
    const { data } = await api.get(`/conversations/${id}`);
    setActive(data);
    setParams({ c: id });
  }, [setParams]);

  useEffect(() => { loadConvs(); }, [loadConvs]);
  useEffect(() => {
    const c = params.get("c");
    if (c) openConv(c);
  }, []); // eslint-disable-line

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [active?.messages?.length]);

  const doAction = async (action, successMsg) => {
    try {
      await api.post(`/conversations/${active.id}/${action}`);
      toast.success(successMsg);
      openConv(active.id);
      loadConvs();
    } catch (e) { toast.error(apiError(e)); }
  };

  const sendHuman = async (e) => {
    e.preventDefault();
    if (!text.trim()) return;
    try {
      await api.post(`/conversations/${active.id}/send`, { text });
      setText("");
      openConv(active.id);
    } catch (e2) { toast.error(apiError(e2)); }
  };

  const simulate = async (e) => {
    e.preventDefault();
    if (!simText.trim()) return;
    try {
      const { data } = await api.post(`/conversations/${active.id}/client-message`, { text: simText });
      setSimText("");
      if (data.risk_level === "red") toast.warning("Ravi escalonou para intervenção humana");
      openConv(active.id);
      loadConvs();
    } catch (e2) { toast.error(apiError(e2)); }
  };

  const linkClient = async (createNew) => {
    try {
      await api.post(`/conversations/${active.id}/link-client`,
        createNew ? { new_client_name: newClientName } : { client_id: linkClientId });
      toast.success("Cliente vinculado à conversa");
      setLinkOpen(false);
      openConv(active.id);
      loadConvs();
    } catch (e) { toast.error(apiError(e)); }
  };

  const openLinkDialog = () => {
    setLinkOpen(true);
    api.get("/clients").then((r) => setClients(r.data)).catch(() => {});
  };

  const filtered = convs.filter((c) => filter === "all" || c.risk_level === filter ||
    (filter === "unidentified" && c.status === "unidentified"));

  return (
    <div className="flex h-full" data-testid="conversas-page">
      <div className="w-72 shrink-0 border-r border-[#23283E] bg-[#0B0D14] flex-col hidden md:flex">
        <div className="p-4 border-b border-[#23283E]">
          <h1 className="font-display font-semibold text-zinc-100">Central de Conversas</h1>
          <div className="flex gap-1.5 mt-3 flex-wrap">
            {[["all", "Todas"], ["red", "Vermelho"], ["yellow", "Amarelo"], ["green", "Verde"], ["unidentified", "Novo contato"]].map(([v, l]) => (
              <button key={v} onClick={() => setFilter(v)} data-testid={`filter-${v}`}
                className={`text-[11px] px-2.5 py-1 rounded-full border transition-colors duration-150 ${filter === v ? "border-indigo-500/60 text-indigo-300 bg-indigo-950/40" : "border-[#23283E] text-zinc-500 hover:text-zinc-300"}`}>
                {l}
              </button>
            ))}
          </div>
        </div>
        <div className="flex-1 overflow-y-auto" data-testid="conversation-list">
          {filtered.map((c) => (
            <button key={c.id} onClick={() => openConv(c.id)} data-testid={`conversation-item-${c.id}`}
              className={`w-full text-left p-4 border-b border-[#23283E]/50 hover:bg-[#161925] transition-colors duration-150 ${active?.id === c.id ? "bg-[#161925]" : ""}`}>
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium text-zinc-200 truncate">{c.client?.name || `+${c.phone_normalized}`}</p>
                <span className={`w-2 h-2 rounded-full shrink-0 ${RISK_META[c.risk_level]?.dot || "bg-zinc-600"}`} />
              </div>
              <p className="text-xs text-zinc-500 truncate mt-1">{c.last_message_text || "Sem mensagens"}</p>
              {c.status === "unidentified" && (
                <Badge className="mt-1.5 bg-amber-950/60 border border-amber-700/50 text-amber-400 text-[10px]">Novo contato</Badge>
              )}
            </button>
          ))}
          {filtered.length === 0 && <p className="text-xs text-zinc-600 p-6 text-center">Nenhuma conversa.</p>}
        </div>
      </div>

      <div className="flex-1 flex flex-col min-w-0">
        {!active ? (
          <div className="flex-1 flex items-center justify-center text-zinc-600 text-sm" data-testid="no-conversation-selected">
            Selecione uma conversa para visualizar.
          </div>
        ) : (
          <>
            <div className="h-14 border-b border-[#23283E] px-5 flex items-center justify-between bg-[#0B0D14]">
              <div className="flex items-center gap-3 min-w-0">
                <p className="text-sm font-medium text-zinc-100 truncate" data-testid="active-conversation-name">
                  {active.client?.name || `+${active.phone_normalized}`}
                </p>
                <Badge className={`border text-[10px] ${RISK_META[active.risk_level]?.cls || ""}`} data-testid="conversation-risk-badge">
                  {RISK_META[active.risk_level]?.label}
                </Badge>
                {active.human_control && <Badge className="bg-blue-950/60 border border-blue-700/50 text-blue-400 text-[10px]">Você está atendendo</Badge>}
                {!active.ai_enabled && !active.human_control && <Badge className="bg-zinc-800 border border-zinc-700 text-zinc-400 text-[10px]">Ravi pausado</Badge>}
              </div>
              <div className="flex items-center gap-2">
                {active.status === "unidentified" ? (
                  <Button size="sm" onClick={openLinkDialog} data-testid="link-client-btn"
                    className="bg-amber-950/60 border border-amber-700/50 text-amber-400 hover:bg-amber-900/60">
                    <Link2 size={14} className="mr-1.5" /> Identificar cliente
                  </Button>
                ) : active.human_control || !active.ai_enabled ? (
                  <Button size="sm" onClick={() => doAction("resume-ravi", "Ravi retomou o atendimento")} data-testid="resume-ravi-btn"
                    className="brand-gradient brand-gradient-hover text-white border-0">
                    <Play size={14} className="mr-1.5" /> Retomar Ravi
                  </Button>
                ) : (
                  <>
                    <Button size="sm" variant="outline" onClick={() => doAction("pause-ravi", "Ravi pausado nesta conversa")}
                      data-testid="pause-ravi-btn" className="border-[#3F476C] text-zinc-300">
                      <Pause size={14} className="mr-1.5" /> Pausar Ravi
                    </Button>
                    <Button size="sm" onClick={() => doAction("takeover", "Você assumiu a conversa")} data-testid="takeover-btn"
                      className="bg-blue-600 hover:bg-blue-500 text-white border-0">
                      <UserCheck size={14} className="mr-1.5" /> Assumir conversa
                    </Button>
                  </>
                )}
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-5 space-y-4" data-testid="messages-area">
              {active.messages.map((m) => <Bubble key={m.id} m={m} />)}
              <div ref={bottomRef} />
            </div>

            <div className="border-t border-[#23283E] p-4 space-y-2.5 bg-[#0B0D14]">
              <form onSubmit={sendHuman} className="flex gap-2">
                <Input value={text} onChange={(e) => setText(e.target.value)} data-testid="human-message-input"
                  placeholder="Responder como advogado…" className="bg-[#090A0F] border-[#23283E]" />
                <Button type="submit" data-testid="human-send-btn" className="bg-blue-600 hover:bg-blue-500 text-white border-0 shrink-0">
                  <Send size={15} />
                </Button>
              </form>
              <form onSubmit={simulate} className="flex gap-2">
                <Input value={simText} onChange={(e) => setSimText(e.target.value)} data-testid="simulate-message-input"
                  placeholder="Simular mensagem do cliente (testa o motor RAVI)…"
                  className="bg-[#090A0F] border-[#23283E] border-dashed text-xs" />
                <Button type="submit" variant="outline" data-testid="simulate-send-btn"
                  className="border-dashed border-[#3F476C] text-zinc-400 text-xs shrink-0">
                  Simular cliente
                </Button>
              </form>
            </div>
          </>
        )}
      </div>

      {active && (
        <div className="w-72 shrink-0 border-l border-[#23283E] bg-[#0B0D14] p-5 space-y-5 overflow-y-auto hidden xl:block" data-testid="context-panel">
          <div>
            <h4 className="font-mono-code text-[10px] uppercase tracking-widest text-zinc-500 mb-2">Cliente</h4>
            <p className="text-sm text-zinc-200">{active.client?.name || "Não identificado"}</p>
            <p className="text-xs text-zinc-500">+{active.phone_normalized}</p>
          </div>
          {active.process && (
            <div>
              <h4 className="font-mono-code text-[10px] uppercase tracking-widest text-zinc-500 mb-2">Processo</h4>
              <p className="font-mono-code text-xs text-indigo-300">{active.process.numero_formatado || active.process.number}</p>
              <p className="text-xs text-zinc-400 mt-1">{active.process.status}</p>
              {active.process.ultima_movimentacao && (
                <p className="text-xs text-zinc-500 mt-1">Última mov.: {active.process.ultima_movimentacao}</p>
              )}
            </div>
          )}
          <div>
            <h4 className="font-mono-code text-[10px] uppercase tracking-widest text-zinc-500 mb-2">Estado do Ravi</h4>
            <p className="text-xs text-zinc-400">
              {active.human_control ? "Atendimento humano ativo — Ravi não responde." :
                active.ai_enabled ? "Ravi ativo, respondendo automaticamente." : "Ravi pausado nesta conversa."}
            </p>
          </div>
        </div>
      )}

      <Dialog open={linkOpen} onOpenChange={setLinkOpen}>
        <DialogContent className="bg-[#0F111A] border-[#23283E]" data-testid="link-client-dialog">
          <DialogHeader>
            <DialogTitle className="font-display text-zinc-100">Identificar contato</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <p className="text-xs text-zinc-500">Vincular a cliente existente:</p>
              <div className="flex gap-2">
                <select value={linkClientId} onChange={(e) => setLinkClientId(e.target.value)} data-testid="link-existing-select"
                  className="flex-1 rounded-md border border-[#23283E] bg-[#090A0F] text-sm text-zinc-200 px-3 py-2">
                  <option value="">Selecionar…</option>
                  {clients.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
                <Button onClick={() => linkClient(false)} disabled={!linkClientId} data-testid="link-existing-btn"
                  variant="outline" className="border-[#3F476C] text-zinc-200">Vincular</Button>
              </div>
            </div>
            <div className="space-y-2 pt-2 border-t border-[#23283E]">
              <p className="text-xs text-zinc-500">Ou criar novo cliente:</p>
              <div className="flex gap-2">
                <Input value={newClientName} onChange={(e) => setNewClientName(e.target.value)} data-testid="link-new-name-input"
                  placeholder="Nome do cliente" className="bg-[#090A0F] border-[#23283E]" />
                <Button onClick={() => linkClient(true)} disabled={!newClientName.trim()} data-testid="link-create-btn"
                  className="brand-gradient brand-gradient-hover text-white border-0">
                  <UserPlus size={14} className="mr-1.5" /> Criar
                </Button>
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
