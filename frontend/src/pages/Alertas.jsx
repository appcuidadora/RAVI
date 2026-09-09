import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, apiError } from "@/lib/api";
import { toast } from "sonner";
import { CheckCheck } from "lucide-react";
import { Button } from "@/components/ui/button";

const TYPE_META = {
  intervention: { label: "Intervenção", cls: "bg-rose-950/60 border-rose-700/50 text-rose-400", dot: "bg-rose-500" },
  monitoring: { label: "Acompanhamento", cls: "bg-amber-950/60 border-amber-700/50 text-amber-400", dot: "bg-amber-500" },
  resolved: { label: "Resolvido", cls: "bg-emerald-950/60 border-emerald-700/50 text-emerald-400", dot: "bg-emerald-500" },
};

export default function Alertas() {
  const [alerts, setAlerts] = useState([]);
  const [tab, setTab] = useState("open");

  const load = () => api.get(`/alerts?status=${tab}`).then((r) => setAlerts(r.data)).catch(() => {});
  useEffect(() => { load(); }, [tab]); // eslint-disable-line

  const resolve = async (a) => {
    try {
      await api.post(`/alerts/${a.id}/resolve`);
      toast.success("Alerta resolvido");
      load();
    } catch (e) { toast.error(apiError(e)); }
  };

  return (
    <div className="p-6 lg:p-8 space-y-6 max-w-4xl" data-testid="alertas-page">
      <div className="fade-up">
        <h1 className="font-display text-2xl sm:text-3xl font-semibold tracking-tight text-zinc-100">Alertas</h1>
        <p className="text-sm text-zinc-500 mt-1">O Ravi só interrompe quando realmente precisa de você.</p>
      </div>

      <div className="flex gap-1.5 fade-up">
        {[["open", "Abertos"], ["resolved", "Resolvidos"], ["all", "Todos"]].map(([v, l]) => (
          <button key={v} onClick={() => setTab(v)} data-testid={`alerts-tab-${v}`}
            className={`text-xs px-3 py-1.5 rounded-full border transition-colors duration-150 ${tab === v ? "border-indigo-500/60 text-indigo-300 bg-indigo-950/40" : "border-[#23283E] text-zinc-500 hover:text-zinc-300"}`}>
            {l}
          </button>
        ))}
      </div>

      <div className="space-y-3 fade-up" data-testid="alerts-list">
        {alerts.length === 0 && (
          <div className="rounded-xl border border-[#23283E] bg-[#0F111A] p-10 text-center text-sm text-zinc-500" data-testid="alerts-empty">
            Nenhum alerta por aqui. O Ravi está resolvendo tudo sozinho.
          </div>
        )}
        {alerts.map((a) => (
          <div key={a.id} data-testid={`alert-card-${a.id}`}
            className="rounded-xl border border-[#23283E] bg-[#0F111A] p-5 flex items-start justify-between gap-4 hover:border-indigo-500/30 transition-colors duration-200">
            <div className="flex items-start gap-3 min-w-0">
              <span className={`mt-1.5 w-2.5 h-2.5 rounded-full shrink-0 ${TYPE_META[a.type]?.dot || "bg-zinc-500"}`} />
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <p className="text-sm font-medium text-zinc-100">{a.title}</p>
                  <span className={`text-[10px] px-2 py-0.5 rounded-full border ${TYPE_META[a.type]?.cls || ""}`}>
                    {TYPE_META[a.type]?.label || a.type}
                  </span>
                  {a.status === "resolved" && <span className="text-[10px] text-emerald-400">resolvido</span>}
                </div>
                <p className="text-xs text-zinc-500 mt-1">{a.reason}</p>
                <p className="text-[11px] text-zinc-600 mt-1">
                  {a.client_name && <span className="text-zinc-400">{a.client_name} • </span>}
                  {new Date(a.created_at).toLocaleString("pt-BR")}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              {a.conversation_id && (
                <Link to={`/conversas?c=${a.conversation_id}`} data-testid={`alert-open-conv-${a.id}`}>
                  <Button size="sm" variant="outline" className="border-[#3F476C] text-zinc-300">Ver conversa</Button>
                </Link>
              )}
              {a.status === "open" && (
                <Button size="sm" onClick={() => resolve(a)} data-testid={`alert-resolve-${a.id}`}
                  className="brand-gradient brand-gradient-hover text-white border-0">
                  <CheckCheck size={14} className="mr-1" /> Resolver
                </Button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
