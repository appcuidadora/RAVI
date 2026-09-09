import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "@/lib/api";
import { ArrowLeft, Check, Lock, FileText } from "lucide-react";
import { Badge } from "@/components/ui/badge";

export default function ProcessoDetalhe() {
  const { id } = useParams();
  const [proc, setProc] = useState(null);

  useEffect(() => {
    api.get(`/processes/${id}`).then((r) => setProc(r.data)).catch(() => {});
  }, [id]);

  if (!proc) return <div className="p-8 text-zinc-500" data-testid="process-loading">Carregando…</div>;

  return (
    <div className="p-6 lg:p-8 space-y-6 max-w-5xl" data-testid="processo-detalhe-page">
      <Link to="/processos" data-testid="back-to-processes" className="inline-flex items-center gap-1.5 text-sm text-zinc-500 hover:text-zinc-200 transition-colors duration-150">
        <ArrowLeft size={15} /> Processos
      </Link>

      <div className="fade-up">
        <h1 className="font-display text-xl sm:text-2xl font-semibold tracking-tight text-zinc-100 font-mono-code" data-testid="process-number">
          {proc.numero_formatado || proc.number}
        </h1>
        <div className="flex flex-wrap gap-2 mt-3">
          {proc.tribunal && <Badge variant="outline" className="border-[#3F476C] text-indigo-300">{proc.tribunal}</Badge>}
          {proc.segmento && <Badge variant="outline" className="border-[#3F476C] text-zinc-400">{proc.segmento}</Badge>}
          <Badge className="bg-indigo-950/60 border border-indigo-700/50 text-indigo-300">{proc.status}</Badge>
          {proc.acesso_restrito && (
            <Badge className="bg-amber-950/60 border border-amber-700/50 text-amber-400">
              <Lock size={10} className="mr-1" /> Este processo possui acesso restrito
            </Badge>
          )}
        </div>
      </div>

      <div className="grid md:grid-cols-3 gap-4 fade-up">
        <div className="md:col-span-2 rounded-xl border border-[#23283E] bg-[#0F111A] p-6" data-testid="process-timeline">
          <h3 className="font-display font-semibold text-zinc-200 mb-5">Timeline de movimentações</h3>
          {(proc.movimentacoes || []).length === 0 && (
            <p className="text-sm text-zinc-500">Nenhuma movimentação disponível nas fontes atuais.</p>
          )}
          <div className="space-y-0">
            {(proc.movimentacoes || []).map((m, i) => (
              <div key={i} className="flex gap-4 pb-6 relative" data-testid={`movement-${i}`}>
                <div className="flex flex-col items-center">
                  <span className="w-2.5 h-2.5 rounded-full brand-gradient mt-1 shrink-0" />
                  {i < proc.movimentacoes.length - 1 && <span className="w-px flex-1 bg-[#23283E] mt-1" />}
                </div>
                <div>
                  <p className="font-mono-code text-[11px] text-indigo-300">{m.data}</p>
                  <p className="text-sm text-zinc-200 mt-0.5">{m.descricao}</p>
                  {m.fonte && <p className="text-[11px] text-zinc-600 mt-1">Fonte: {m.fonte}</p>}
                </div>
              </div>
            ))}
          </div>
          {proc.ultima_movimentacao && (
            <p className="text-xs text-zinc-500 pt-2 border-t border-[#23283E]">
              Última movimentação: <span className="text-zinc-300">{proc.ultima_movimentacao}</span>
            </p>
          )}
        </div>

        <div className="space-y-4">
          <div className="rounded-xl border border-indigo-500/30 bg-indigo-950/40 p-5 ravi-glow" data-testid="ravi-knowledge-card">
            <h3 className="font-display font-semibold text-indigo-200 text-sm mb-4">Como o Ravi conhece este processo</h3>
            <div className="space-y-2.5">
              {(proc.fontes || []).map((f, i) => (
                <div key={i} className="flex items-center gap-2.5" data-testid={`fonte-${i}`}>
                  <span className="w-4 h-4 rounded-full bg-emerald-500/20 flex items-center justify-center shrink-0">
                    <Check size={10} className="text-emerald-400" />
                  </span>
                  <span className="text-xs text-zinc-300">{f}</span>
                </div>
              ))}
            </div>
          </div>

          {proc.client && (
            <div className="rounded-xl border border-[#23283E] bg-[#0F111A] p-5" data-testid="process-client-card">
              <h4 className="font-mono-code text-[10px] uppercase tracking-widest text-zinc-500 mb-3">Cliente</h4>
              <p className="text-sm font-medium text-zinc-200">{proc.client.name}</p>
              <p className="text-xs text-zinc-500 mt-0.5">{proc.client.phone}</p>
            </div>
          )}

          {(proc.partes || []).length > 0 && (
            <div className="rounded-xl border border-[#23283E] bg-[#0F111A] p-5" data-testid="process-partes-card">
              <h4 className="font-mono-code text-[10px] uppercase tracking-widest text-zinc-500 mb-3">Partes</h4>
              {proc.partes.map((p, i) => (
                <p key={i} className="text-xs text-zinc-300 flex items-center gap-2 py-1">
                  <FileText size={11} className="text-zinc-600" /> {p}
                </p>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
