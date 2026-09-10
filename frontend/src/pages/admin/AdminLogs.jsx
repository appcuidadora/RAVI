import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function AdminLogs() {
  const [data, setData] = useState({ logs: [], offices: [] });
  const [tipo, setTipo] = useState("all");
  const [officeId, setOfficeId] = useState("");

  useEffect(() => {
    api.get(`/admin/logs?tipo=${tipo}&office_id=${officeId}`).then((r) => setData(r.data)).catch(() => {});
  }, [tipo, officeId]);

  const officeName = (id) => data.offices.find((o) => o.id === id)?.name || id || "—";

  return (
    <div className="p-6 lg:p-8 space-y-6" data-testid="admin-logs-page">
      <div className="fade-up">
        <h1 className="font-display text-2xl sm:text-3xl font-semibold tracking-tight text-zinc-100">Logs / Auditoria</h1>
        <p className="text-sm text-zinc-500 mt-1">Eventos administrativos e de todos os escritórios.</p>
      </div>

      <div className="flex gap-2 flex-wrap fade-up">
        {[["all", "Todos"], ["admin", "Administrativos"], ["tenant", "Escritórios"]].map(([v, l]) => (
          <button key={v} onClick={() => setTipo(v)} data-testid={`logs-tab-${v}`}
            className={`text-xs px-3 py-1.5 rounded-full border transition-colors duration-150 ${tipo === v ? "border-indigo-500/60 text-indigo-300 bg-indigo-950/40" : "border-[#23283E] text-zinc-500 hover:text-zinc-300"}`}>
            {l}
          </button>
        ))}
        <select value={officeId} onChange={(e) => setOfficeId(e.target.value)} data-testid="logs-office-filter"
          className="rounded-full border border-[#23283E] bg-[#090A0F] text-xs text-zinc-300 px-3 py-1.5">
          <option value="">Todos os escritórios</option>
          {data.offices.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
        </select>
      </div>

      <div className="rounded-xl border border-[#23283E] bg-[#0F111A] p-2 fade-up max-h-[65vh] overflow-y-auto" data-testid="logs-list">
        {data.logs.length === 0 && <p className="text-sm text-zinc-500 p-6 text-center">Nenhum evento.</p>}
        {data.logs.map((l) => (
          <div key={l.id} className="flex items-start justify-between gap-4 px-3 py-2.5 border-b border-[#23283E]/40 last:border-0" data-testid={`log-${l.id}`}>
            <div className="min-w-0">
              <p className="text-xs text-zinc-200 font-mono-code">
                <span className={l.origem === "admin" ? "text-amber-400" : "text-indigo-300"}>[{l.origem}]</span>{" "}
                {l.action || l.event}
              </p>
              <p className="text-[11px] text-zinc-600 truncate">
                {l.admin_email || l.actor} {l.office_id ? `• ${officeName(l.office_id)}` : ""} {l.motivo ? `• motivo: ${l.motivo}` : ""}
              </p>
            </div>
            <span className="text-[11px] text-zinc-600 shrink-0">{new Date(l.created_at).toLocaleString("pt-BR")}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
