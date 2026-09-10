import { useEffect, useState } from "react";
import { api, apiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export default function Configuracoes() {
  const { user } = useAuth();
  const isSocio = user?.role === "SOCIO_ADMIN";
  const [form, setForm] = useState({ name: "", tone: "acolhedor", minutes_per_attendance: 5.4, welcome_message: "" });
  const [auditLogs, setAuditLogs] = useState([]);
  const [ticket, setTicket] = useState({ categoria: "WhatsApp", prioridade: "media", assunto: "", descricao: "" });
  const [myTickets, setMyTickets] = useState([]);

  const createTicket = async (e) => {
    e.preventDefault();
    try {
      await api.post("/support/tickets", ticket);
      toast.success("Chamado aberto — nossa equipe vai responder em breve");
      setTicket({ categoria: "WhatsApp", prioridade: "media", assunto: "", descricao: "" });
      api.get("/support/tickets").then((r) => setMyTickets(r.data)).catch(() => {});
    } catch (err) { toast.error(apiError(err)); }
  };

  useEffect(() => {
    api.get("/office/settings").then((r) => setForm({
      name: r.data.name || "", tone: r.data.tone || "acolhedor",
      minutes_per_attendance: r.data.minutes_per_attendance ?? 5.4,
      welcome_message: r.data.welcome_message || "",
    })).catch(() => {});
    api.get("/audit").then((r) => setAuditLogs(r.data)).catch(() => {});
    api.get("/support/tickets").then((r) => setMyTickets(r.data)).catch(() => {});
  }, []);

  const save = async (e) => {
    e.preventDefault();
    try {
      await api.patch("/office/settings", { ...form, minutes_per_attendance: Number(form.minutes_per_attendance) });
      toast.success("Configurações salvas");
    } catch (err) { toast.error(apiError(err)); }
  };

  return (
    <div className="p-6 lg:p-8 space-y-6 max-w-3xl" data-testid="configuracoes-page">
      <div className="fade-up">
        <h1 className="font-display text-2xl sm:text-3xl font-semibold tracking-tight text-zinc-100">Configurações do Ravi</h1>
        <p className="text-sm text-zinc-500 mt-1">Ajuste como o Ravi atende em nome do seu escritório.</p>
      </div>

      <form onSubmit={save} className="rounded-xl border border-[#23283E] bg-[#0F111A] p-6 space-y-5 fade-up" data-testid="settings-form">
        <div className="space-y-1.5">
          <Label className="text-zinc-400 text-xs">Nome do escritório</Label>
          <Input value={form.name} disabled={!isSocio} onChange={(e) => setForm({ ...form, name: e.target.value })}
            data-testid="settings-office-name" className="bg-[#090A0F] border-[#23283E]" />
        </div>
        <div className="space-y-1.5">
          <Label className="text-zinc-400 text-xs">Tom de voz do Ravi</Label>
          <Select value={form.tone} onValueChange={(v) => setForm({ ...form, tone: v })} disabled={!isSocio}>
            <SelectTrigger data-testid="settings-tone-select" className="bg-[#090A0F] border-[#23283E]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="bg-[#0F111A] border-[#23283E]">
              <SelectItem value="acolhedor">Acolhedor</SelectItem>
              <SelectItem value="formal">Formal</SelectItem>
              <SelectItem value="direto">Direto</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label className="text-zinc-400 text-xs">Tempo médio por atendimento manual (minutos)</Label>
          <Input type="number" step="0.1" min="1" value={form.minutes_per_attendance} disabled={!isSocio}
            onChange={(e) => setForm({ ...form, minutes_per_attendance: e.target.value })}
            data-testid="settings-minutes-input" className="bg-[#090A0F] border-[#23283E] max-w-[160px]" />
          <p className="text-[11px] text-zinc-600">Base da métrica "tempo estimado economizado" (estimativa, não medição exata).</p>
        </div>
        <div className="space-y-1.5">
          <Label className="text-zinc-400 text-xs">Mensagem de boas-vindas (opcional)</Label>
          <Textarea value={form.welcome_message} disabled={!isSocio}
            onChange={(e) => setForm({ ...form, welcome_message: e.target.value })}
            data-testid="settings-welcome-input" rows={3}
            placeholder="Olá! Sou o assistente virtual do escritório…" className="bg-[#090A0F] border-[#23283E]" />
        </div>
        {isSocio && (
          <Button type="submit" data-testid="settings-save-btn" className="brand-gradient brand-gradient-hover text-white border-0">
            Salvar configurações
          </Button>
        )}
      </form>

      <div className="rounded-xl border border-[#23283E] bg-[#0F111A] p-6 fade-up" data-testid="support-card">
        <h3 className="font-display font-semibold text-zinc-200 mb-1.5">Suporte RAVI</h3>
        <p className="text-xs text-zinc-500 mb-4">Precisa de ajuda? Abra um chamado e acompanhe o status por aqui.</p>
        <form onSubmit={createTicket} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <Select value={ticket.categoria} onValueChange={(v) => setTicket({ ...ticket, categoria: v })}>
              <SelectTrigger data-testid="ticket-categoria" className="bg-[#090A0F] border-[#23283E]"><SelectValue /></SelectTrigger>
              <SelectContent className="bg-[#0F111A] border-[#23283E]">
                {["Conta", "WhatsApp", "Processos", "IA", "Financeiro", "Sistema", "Outros"].map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
              </SelectContent>
            </Select>
            <Select value={ticket.prioridade} onValueChange={(v) => setTicket({ ...ticket, prioridade: v })}>
              <SelectTrigger data-testid="ticket-prioridade" className="bg-[#090A0F] border-[#23283E]"><SelectValue /></SelectTrigger>
              <SelectContent className="bg-[#0F111A] border-[#23283E]">
                <SelectItem value="baixa">Baixa</SelectItem><SelectItem value="media">Média</SelectItem>
                <SelectItem value="alta">Alta</SelectItem><SelectItem value="critica">Crítica</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <Input placeholder="Assunto" value={ticket.assunto} onChange={(e) => setTicket({ ...ticket, assunto: e.target.value })}
            data-testid="ticket-assunto" className="bg-[#090A0F] border-[#23283E]" />
          <Textarea placeholder="Descreva o que está acontecendo…" value={ticket.descricao} rows={3}
            onChange={(e) => setTicket({ ...ticket, descricao: e.target.value })}
            data-testid="ticket-descricao" className="bg-[#090A0F] border-[#23283E]" />
          <Button type="submit" data-testid="ticket-submit" className="brand-gradient brand-gradient-hover text-white border-0">
            Abrir chamado
          </Button>
        </form>
        {myTickets.length > 0 && (
          <div className="mt-4 space-y-2" data-testid="my-tickets">
            {myTickets.slice(0, 5).map((t) => (
              <div key={t.id} className="flex items-center justify-between rounded-lg border border-[#23283E] bg-[#090A0F] px-3 py-2" data-testid={`my-ticket-${t.id}`}>
                <p className="text-xs text-zinc-300 truncate">{t.assunto}</p>
                <span className="text-[10px] text-indigo-300 capitalize shrink-0 ml-2">{t.status}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="rounded-xl border border-[#23283E] bg-[#0F111A] p-6 fade-up" data-testid="audit-trail">
        <h3 className="font-display font-semibold text-zinc-200 mb-4">Trilha de auditoria</h3>
        <div className="space-y-0 max-h-96 overflow-y-auto">
          {auditLogs.length === 0 && <p className="text-sm text-zinc-500">Nenhum evento registrado ainda.</p>}
          {auditLogs.map((l) => (
            <div key={l.id} className="flex items-start justify-between gap-4 py-2.5 border-b border-[#23283E]/50 last:border-0" data-testid={`audit-${l.id}`}>
              <div className="min-w-0">
                <p className="text-xs text-zinc-300 font-mono-code">{l.event}</p>
                <p className="text-[11px] text-zinc-600 truncate">ator: {l.actor}{l.details?.risk_level ? ` • risco: ${l.details.risk_level}` : ""}</p>
              </div>
              <span className="text-[11px] text-zinc-600 shrink-0">{new Date(l.created_at).toLocaleString("pt-BR")}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
