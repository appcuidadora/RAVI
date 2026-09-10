import { useEffect, useState } from "react";
import { api, apiError } from "@/lib/api";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const PRIO = {
  baixa: "bg-zinc-800 border-zinc-700 text-zinc-400", media: "bg-blue-950/60 border-blue-700/50 text-blue-400",
  alta: "bg-amber-950/60 border-amber-700/50 text-amber-400", critica: "bg-rose-950/60 border-rose-700/50 text-rose-400",
};
const STATUS = ["aberto", "em atendimento", "aguardando cliente", "resolvido", "encerrado"];

export default function AdminSuporte() {
  const [tickets, setTickets] = useState([]);
  const [filter, setFilter] = useState("all");

  const load = () => api.get(`/admin/tickets?status=${filter}`).then((r) => setTickets(r.data)).catch(() => {});
  useEffect(() => { load(); }, [filter]); // eslint-disable-line

  const setStatus = async (t, status) => {
    try {
      await api.patch(`/admin/tickets/${t.id}`, { status });
      toast.success("Chamado atualizado");
      load();
    } catch (e) { toast.error(apiError(e)); }
  };

  return (
    <div className="p-6 lg:p-8 space-y-6" data-testid="admin-suporte-page">
      <div className="fade-up">
        <h1 className="font-display text-2xl sm:text-3xl font-semibold tracking-tight text-zinc-100">Suporte</h1>
        <p className="text-sm text-zinc-500 mt-1">Chamados abertos pelos escritórios.</p>
      </div>

      <div className="flex gap-1.5 fade-up flex-wrap">
        {[["all", "Todos"], ...STATUS.map((s) => [s, s])].map(([v, l]) => (
          <button key={v} onClick={() => setFilter(v)} data-testid={`tickets-tab-${v.replace(/\s/g, "-")}`}
            className={`text-xs px-3 py-1.5 rounded-full border capitalize transition-colors duration-150 ${filter === v ? "border-indigo-500/60 text-indigo-300 bg-indigo-950/40" : "border-[#23283E] text-zinc-500 hover:text-zinc-300"}`}>
            {l}
          </button>
        ))}
      </div>

      <div className="space-y-3 fade-up" data-testid="tickets-list">
        {tickets.length === 0 && (
          <div className="rounded-xl border border-[#23283E] bg-[#0F111A] p-10 text-center text-sm text-zinc-500" data-testid="tickets-empty">
            Nenhum chamado.
          </div>
        )}
        {tickets.map((t) => (
          <div key={t.id} data-testid={`ticket-${t.id}`}
            className="rounded-xl border border-[#23283E] bg-[#0F111A] p-5 flex items-start justify-between gap-4">
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <p className="text-sm font-medium text-zinc-100">{t.assunto}</p>
                <Badge className={`border text-[10px] ${PRIO[t.prioridade] || PRIO.media}`}>{t.prioridade}</Badge>
                <span className="text-[10px] text-zinc-500">{t.categoria}</span>
              </div>
              <p className="text-xs text-zinc-400 mt-1.5 whitespace-pre-wrap">{t.descricao}</p>
              <p className="text-[11px] text-zinc-600 mt-2">
                {t.office_name} • {t.user_name} ({t.user_email}) • {new Date(t.created_at).toLocaleString("pt-BR")}
              </p>
            </div>
            <Select value={t.status} onValueChange={(v) => setStatus(t, v)}>
              <SelectTrigger data-testid={`ticket-status-${t.id}`} className="w-44 bg-[#090A0F] border-[#23283E] text-xs shrink-0">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-[#0F111A] border-[#23283E]">
                {STATUS.map((s) => <SelectItem key={s} value={s} className="capitalize">{s}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
        ))}
      </div>
    </div>
  );
}
