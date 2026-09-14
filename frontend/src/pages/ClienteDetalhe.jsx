import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "@/lib/api";
import { ArrowLeft, FileText, MessageSquare, ChevronRight } from "lucide-react";
import { Badge } from "@/components/ui/badge";

export default function ClienteDetalhe() {
  const { id } = useParams();
  const [client, setClient] = useState(null);

  useEffect(() => {
    api.get(`/clients/${id}`).then((r) => setClient(r.data)).catch(() => {});
  }, [id]);

  if (!client) return <div className="p-8 text-zinc-500" data-testid="client-loading">Carregando…</div>;

  return (
    <div className="p-6 lg:p-8 space-y-6 max-w-4xl" data-testid="cliente-detalhe-page">
      <Link to="/clientes" data-testid="back-to-clients"
        className="inline-flex items-center gap-1.5 text-sm text-zinc-500 hover:text-zinc-200 transition-colors duration-150">
        <ArrowLeft size={15} /> Clientes
      </Link>

      <div className="rounded-xl border border-[#23283E] bg-[#0F111A] p-6 fade-up" data-testid="client-info-card">
        <div className="flex items-center justify-between">
          <h1 className="font-display text-2xl font-semibold tracking-tight text-zinc-100">{client.name}</h1>
          <Badge className={client.status === "arquivado"
            ? "bg-zinc-800 border border-zinc-700 text-zinc-400"
            : "bg-emerald-950/60 border border-emerald-700/50 text-emerald-400"}>{client.status}</Badge>
        </div>
        <div className="grid sm:grid-cols-3 gap-4 mt-4 text-sm">
          <div><p className="font-mono-code text-[10px] uppercase tracking-widest text-zinc-500">WhatsApp</p>
            <p className="text-zinc-200 mt-1" data-testid="client-phone">{client.phone}</p></div>
          <div><p className="font-mono-code text-[10px] uppercase tracking-widest text-zinc-500">E-mail</p>
            <p className="text-zinc-200 mt-1">{client.email || "—"}</p></div>
          <div><p className="font-mono-code text-[10px] uppercase tracking-widest text-zinc-500">CPF</p>
            <p className="text-zinc-200 mt-1">{client.cpf || "—"}</p></div>
          <div><p className="font-mono-code text-[10px] uppercase tracking-widest text-zinc-500">Responsável</p>
            <p className="text-zinc-200 mt-1">{client.responsible_name || "—"}</p></div>
          <div><p className="font-mono-code text-[10px] uppercase tracking-widest text-zinc-500">Cliente desde</p>
            <p className="text-zinc-200 mt-1">{new Date(client.created_at).toLocaleDateString("pt-BR")}</p></div>
        </div>
        {client.notes && <p className="text-xs text-zinc-500 mt-4 pt-4 border-t border-[#23283E]">{client.notes}</p>}
      </div>

      <div className="rounded-xl border border-[#23283E] bg-[#0F111A] p-6 fade-up" data-testid="client-processes-card">
        <h3 className="font-display font-semibold text-zinc-200 mb-4 flex items-center gap-2">
          <FileText size={15} className="text-zinc-500" /> Processos vinculados ({(client.processes || []).length})
        </h3>
        {(client.processes || []).length === 0 && <p className="text-sm text-zinc-500">Nenhum processo vinculado.</p>}
        <div className="space-y-2">
          {(client.processes || []).map((p) => (
            <Link key={p.id} to={`/processos/${p.id}`} data-testid={`client-process-${p.id}`}
              className="flex items-center justify-between rounded-lg border border-[#23283E] bg-[#090A0F] px-4 py-3 hover:border-indigo-500/40 transition-colors duration-150">
              <div>
                <p className="font-mono-code text-xs text-indigo-300">{p.numero_formatado || p.number}</p>
                <p className="text-xs text-zinc-500 mt-0.5">{p.title || p.subject || p.status}</p>
              </div>
              <ChevronRight size={15} className="text-zinc-600" />
            </Link>
          ))}
        </div>
      </div>

      <div className="rounded-xl border border-[#23283E] bg-[#0F111A] p-6 fade-up" data-testid="client-history-card">
        <h3 className="font-display font-semibold text-zinc-200 mb-4 flex items-center gap-2">
          <MessageSquare size={15} className="text-zinc-500" /> Histórico de atendimento
        </h3>
        {(client.conversations || []).length === 0 && <p className="text-sm text-zinc-500">Nenhuma conversa ainda.</p>}
        <div className="space-y-2">
          {(client.conversations || []).map((c) => (
            <Link key={c.id} to={`/conversas?c=${c.id}`} data-testid={`client-conv-${c.id}`}
              className="block rounded-lg border border-[#23283E] bg-[#090A0F] px-4 py-3 hover:border-indigo-500/40 transition-colors duration-150">
              <p className="text-xs text-zinc-300 truncate">{c.last_message_text || "Conversa sem mensagens"}</p>
              <p className="text-[10px] text-zinc-600 mt-1">{new Date(c.last_message_at || c.created_at).toLocaleString("pt-BR")}</p>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
