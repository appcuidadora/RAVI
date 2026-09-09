import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { FileStack, MessagesSquare, CheckCircle2, AlertTriangle, Clock, ArrowRight } from "lucide-react";
import { AreaChart, Area, XAxis, Tooltip, ResponsiveContainer } from "recharts";

function fmtTime(min) {
  const h = Math.floor(min / 60);
  const m = Math.round(min % 60);
  return `${h}h${String(m).padStart(2, "0")}`;
}

const RISK = {
  intervention: { label: "Intervenção", cls: "bg-rose-950/60 border-rose-700/50 text-rose-400", dot: "bg-rose-500" },
  monitoring: { label: "Acompanhamento", cls: "bg-amber-950/60 border-amber-700/50 text-amber-400", dot: "bg-amber-500" },
  resolved: { label: "Resolvido", cls: "bg-emerald-950/60 border-emerald-700/50 text-emerald-400", dot: "bg-emerald-500" },
};

export default function Dashboard() {
  const { user } = useAuth();
  const [data, setData] = useState(null);

  useEffect(() => {
    api.get("/dashboard/stats").then((r) => setData(r.data)).catch(() => {});
  }, []);

  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Bom dia" : hour < 18 ? "Boa tarde" : "Boa noite";
  const s = data?.stats;

  const kpis = [
    { label: "Processos monitorados", val: s?.processos ?? "—", icon: FileStack, tid: "kpi-card-processos" },
    { label: "Clientes atendidos", val: s?.clientes ?? "—", icon: MessagesSquare, tid: "kpi-card-clientes" },
    { label: "Resolvidos", val: s?.resolvidos ?? "—", icon: CheckCircle2, accent: "text-emerald-400", tid: "kpi-card-resolvidos" },
    { label: "Precisam de você", val: s?.precisam_de_voce ?? "—", icon: AlertTriangle, accent: "text-rose-400", tid: "kpi-card-precisam" },
    { label: "Tempo estimado economizado", val: s ? fmtTime(s.tempo_economizado_min) : "—", icon: Clock, accent: "brand-gradient-text", tid: "kpi-card-tempo" },
  ];

  return (
    <div className="p-6 lg:p-8 space-y-8" data-testid="dashboard-page">
      <div className="fade-up">
        <h1 className="font-display text-3xl sm:text-4xl font-bold tracking-tight text-zinc-100" data-testid="dashboard-greeting">
          {greeting}, Dr(a). {user?.name}.
        </h1>
        <p className="text-base md:text-lg text-zinc-400 mt-2">
          O Ravi cuidou do atendimento. Você cuida do que precisa de você.
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-4 fade-up" data-testid="kpi-grid">
        {kpis.map((k) => (
          <div key={k.label} data-testid={k.tid}
            className="rounded-xl border border-[#23283E] bg-[#0F111A] p-5 hover:border-indigo-500/40 transition-colors duration-200">
            <div className="flex items-center justify-between">
              <span className="font-mono-code text-[10px] uppercase tracking-widest text-zinc-500">{k.label}</span>
              <k.icon size={15} className="text-zinc-600" />
            </div>
            <p className={`font-display text-3xl font-bold mt-3 ${k.accent || "text-zinc-100"}`}>{k.val}</p>
          </div>
        ))}
      </div>

      <div className="grid lg:grid-cols-5 gap-4 fade-up">
        <div className="lg:col-span-2 rounded-xl border border-[#23283E] bg-[#0F111A] p-5" data-testid="attention-queue">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-display font-semibold text-zinc-200">Fila de atenção</h3>
            <Link to="/alertas" data-testid="ver-alertas-link" className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1">
              Ver todos <ArrowRight size={12} />
            </Link>
          </div>
          <div className="space-y-2.5">
            {(data?.attention || []).length === 0 && (
              <p className="text-sm text-zinc-500 py-6 text-center">Nada pendente. O Ravi está cuidando de tudo.</p>
            )}
            {(data?.attention || []).map((a) => (
              <Link key={a.id} to={a.conversation_id ? `/conversas?c=${a.conversation_id}` : "/alertas"}
                data-testid={`attention-item-${a.id}`}
                className="flex items-start gap-3 rounded-lg border border-[#23283E] bg-[#090A0F] p-3.5 hover:border-indigo-500/40 transition-colors duration-200">
                <span className={`mt-1.5 w-2 h-2 rounded-full shrink-0 ${RISK[a.type]?.dot || "bg-zinc-500"}`} />
                <div className="min-w-0">
                  <p className="text-sm text-zinc-200 font-medium truncate">{a.title}</p>
                  <p className="text-xs text-zinc-500 truncate">{a.client_name || a.reason}</p>
                </div>
              </Link>
            ))}
          </div>
        </div>

        <div className="lg:col-span-3 rounded-xl border border-[#23283E] bg-[#0F111A] p-5" data-testid="volume-chart-card">
          <h3 className="font-display font-semibold text-zinc-200 mb-4">Atendimentos do Ravi por horário</h3>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data?.chart || []}>
                <defs>
                  <linearGradient id="ravigrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#6366F1" stopOpacity={0.4} />
                    <stop offset="100%" stopColor="#6366F1" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="hora" tick={{ fill: "#6B7280", fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ background: "#0F111A", border: "1px solid #23283E", borderRadius: 8, fontSize: 12 }}
                  labelStyle={{ color: "#9CA3AF" }} itemStyle={{ color: "#A5B4FC" }} />
                <Area type="monotone" dataKey="atendimentos" stroke="#6366F1" strokeWidth={2} fill="url(#ravigrad)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <p className="text-center text-sm text-zinc-500 pt-2 fade-up" data-testid="dashboard-motto">
        Você não precisa olhar todos os processos. <span className="brand-gradient-text font-semibold">O Ravi olha por você.</span>
      </p>
    </div>
  );
}
