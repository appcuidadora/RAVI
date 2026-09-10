import { useEffect, useState } from "react";
import { api } from "@/lib/api";

const fmtMoney = (v) => `R$ ${Number(v || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}`;
const fmtTime = (min) => `${Math.floor(min / 60)}h${String(Math.round(min % 60)).padStart(2, "0")}`;

const GRAV = {
  alta: "bg-rose-950/60 border-rose-700/50 text-rose-400",
  media: "bg-amber-950/60 border-amber-700/50 text-amber-400",
  baixa: "bg-blue-950/60 border-blue-700/50 text-blue-400",
};

export default function AdminDashboard() {
  const [data, setData] = useState(null);

  useEffect(() => { api.get("/admin/dashboard").then((r) => setData(r.data)).catch(() => {}); }, []);

  const k = data?.kpis || {};
  const cards = [
    ["Escritórios ativos", k.escritorios_ativos], ["Suspensos", k.escritorios_suspensos], ["Em trial", k.escritorios_trial],
    ["Usuários ativos", k.usuarios_ativos], ["Processos monitorados", k.processos_monitorados], ["Clientes atendidos", k.clientes_atendidos],
    ["Msgs recebidas", k.mensagens_recebidas], ["Msgs respondidas", k.mensagens_respondidas],
    ["Conversas resolvidas", k.conversas_resolvidas], ["Conversas escaladas", k.conversas_escaladas],
    ["Tempo economizado", k.tempo_economizado_min != null ? fmtTime(k.tempo_economizado_min) : "—"],
    ["WhatsApps conectados", k.whatsapp_conectados], ["WhatsApps desconectados", k.whatsapp_desconectados],
    ["Recebido", fmtMoney(k.pagamentos_recebidos)], ["Pendente", fmtMoney(k.pagamentos_pendentes)],
    ["Inadimplência", k.inadimplencia], ["MRR", fmtMoney(k.mrr)], ["ARR", fmtMoney(k.arr)],
    ["Ticket médio", fmtMoney(k.ticket_medio)], ["Cancelamentos", k.cancelamentos],
  ];

  return (
    <div className="p-6 lg:p-8 space-y-6" data-testid="admin-dashboard-page">
      <div className="fade-up">
        <h1 className="font-display text-2xl sm:text-3xl font-semibold tracking-tight text-zinc-100">RAVI ADMIN</h1>
        <p className="text-sm text-zinc-500 mt-1">Visão geral da plataforma em tempo real.</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-5 gap-3 fade-up" data-testid="admin-kpi-grid">
        {cards.map(([label, val], i) => (
          <div key={label} data-testid={`admin-kpi-${i}`}
            className="rounded-xl border border-[#23283E] bg-[#0F111A] p-4 hover:border-indigo-500/40 transition-colors duration-200">
            <p className="font-mono-code text-[10px] uppercase tracking-widest text-zinc-500">{label}</p>
            <p className="font-display text-2xl font-bold text-zinc-100 mt-2">{val ?? "—"}</p>
          </div>
        ))}
      </div>

      <div className="rounded-xl border border-[#23283E] bg-[#0F111A] p-5 fade-up" data-testid="admin-attention-block">
        <h3 className="font-display font-semibold text-zinc-200 mb-4">⚠️ Atenção</h3>
        {(data?.atencao || []).length === 0 && (
          <p className="text-sm text-zinc-500 py-4 text-center">Nenhum ponto de atenção no momento.</p>
        )}
        <div className="space-y-2">
          {(data?.atencao || []).map((a, i) => (
            <div key={i} data-testid={`attention-${i}`}
              className={`rounded-lg border px-3.5 py-2.5 text-xs ${GRAV[a.gravidade] || GRAV.baixa}`}>
              {a.texto}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
