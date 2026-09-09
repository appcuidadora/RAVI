import { useEffect, useRef, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api, apiError } from "@/lib/api";
import { toast } from "sonner";
import { ArrowLeft, Check, Lock, FileText, Upload, Download, Banknote } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function ProcessoDetalhe() {
  const { id } = useParams();
  const [proc, setProc] = useState(null);
  const fileRef = useRef(null);
  const [uploading, setUploading] = useState(false);
  const [newCob, setNewCob] = useState({ valor: "", data_vencimento: "", descricao: "" });

  const reload = () => api.get(`/processes/${id}`).then((r) => setProc(r.data)).catch(() => {});
  useEffect(() => { reload(); }, [id]); // eslint-disable-line

  const uploadPdf = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      await api.post(`/processes/${id}/document`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success("PDF anexado — a IA já consegue ler este documento");
      reload();
    } catch (err) {
      toast.error(apiError(err, "Falha ao anexar PDF"));
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  };

  const downloadPdf = async (d) => {
    try {
      const r = await api.get(`/processes/${id}/document/${d.id}`, { responseType: "blob" });
      window.open(URL.createObjectURL(r.data), "_blank");
    } catch {
      toast.error("Falha ao baixar documento");
    }
  };

  const addCobranca = async () => {
    if (!newCob.valor || !newCob.data_vencimento) return;
    try {
      await api.patch(`/processes/${id}`, {
        cobrancas: [...(proc.cobrancas || []),
          { valor: Number(newCob.valor), data_vencimento: newCob.data_vencimento, descricao: newCob.descricao }],
      });
      setNewCob({ valor: "", data_vencimento: "", descricao: "" });
      toast.success("Cobrança adicionada — lembretes automáticos ativados");
      reload();
    } catch (err) { toast.error(apiError(err)); }
  };

  const markPaid = async (c) => {
    try {
      await api.post(`/processes/${id}/cobrancas/${c.id}/pago`);
      toast.success("Cobrança marcada como paga");
      reload();
    } catch (err) { toast.error(apiError(err)); }
  };

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

          <div className="rounded-xl border border-[#23283E] bg-[#0F111A] p-5" data-testid="process-documents-card">
            <div className="flex items-center justify-between mb-3">
              <h4 className="font-mono-code text-[10px] uppercase tracking-widest text-zinc-500">Documentos do processo</h4>
              <button onClick={() => fileRef.current?.click()} data-testid="upload-pdf-btn"
                className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1 transition-colors duration-150">
                <Upload size={12} /> Anexar PDF
              </button>
              <input ref={fileRef} type="file" accept="application/pdf" className="hidden" onChange={uploadPdf} data-testid="upload-pdf-input" />
            </div>
            {(proc.documentos || []).length === 0 && (
              <p className="text-xs text-zinc-600">Anexe o PDF do processo — a IA lê o conteúdo e usa nas respostas ao cliente.</p>
            )}
            {(proc.documentos || []).map((d) => (
              <div key={d.id} className="flex items-center justify-between py-1.5" data-testid={`document-${d.id}`}>
                <span className="text-xs text-zinc-300 truncate flex items-center gap-2">
                  <FileText size={11} className="text-zinc-600 shrink-0" /> {d.filename}
                </span>
                <button onClick={() => downloadPdf(d)} data-testid={`download-${d.id}`}
                  className="text-zinc-500 hover:text-zinc-200 transition-colors duration-150 shrink-0 ml-2"><Download size={13} /></button>
              </div>
            ))}
            {uploading && <p className="text-[11px] text-indigo-300 mt-2 pulse-dot">Enviando e lendo documento…</p>}
          </div>

          <div className="rounded-xl border border-[#23283E] bg-[#0F111A] p-5" data-testid="process-billing-card">
            <h4 className="font-mono-code text-[10px] uppercase tracking-widest text-zinc-500 mb-3 flex items-center gap-2">
              <Banknote size={12} /> Financeiro
            </h4>
            {proc.valor_causa != null && (
              <p className="text-sm text-zinc-200">Valor da causa: <span className="font-semibold">R$ {Number(proc.valor_causa).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</span></p>
            )}
            {proc.forma_pagamento && <p className="text-xs text-zinc-500 mt-0.5">Pagamento: {proc.forma_pagamento}</p>}
            <div className="mt-3 space-y-2">
              {(proc.cobrancas || []).length === 0 && (
                <p className="text-xs text-zinc-600">Sem cobranças. Adicione parcelas e o Ravi lembra o cliente no WhatsApp 5 dias antes e no dia do vencimento.</p>
              )}
              {(proc.cobrancas || []).map((c) => (
                <div key={c.id} className="flex items-center justify-between rounded-lg border border-[#23283E] bg-[#090A0F] px-3 py-2" data-testid={`cobranca-${c.id}`}>
                  <div className="min-w-0">
                    <p className="text-xs text-zinc-200">
                      R$ {Number(c.valor).toLocaleString("pt-BR", { minimumFractionDigits: 2 })} • {new Date(c.data_vencimento + "T12:00:00").toLocaleDateString("pt-BR")}
                    </p>
                    {c.descricao && <p className="text-[10px] text-zinc-600 truncate">{c.descricao}</p>}
                  </div>
                  {c.status === "pago"
                    ? <span className="text-[10px] text-emerald-400 shrink-0">pago</span>
                    : <button onClick={() => markPaid(c)} data-testid={`cobranca-pago-${c.id}`}
                        className="text-[10px] text-indigo-400 hover:text-indigo-300 shrink-0 transition-colors duration-150">marcar pago</button>}
                </div>
              ))}
            </div>
            <div className="grid grid-cols-[1fr_auto_auto] gap-2 items-center mt-3">
              <Input type="number" step="0.01" placeholder="Nova parcela R$" value={newCob.valor}
                onChange={(e) => setNewCob({ ...newCob, valor: e.target.value })}
                data-testid="new-cobranca-valor" className="bg-[#090A0F] border-[#23283E] h-8 text-xs" />
              <Input type="date" value={newCob.data_vencimento}
                onChange={(e) => setNewCob({ ...newCob, data_vencimento: e.target.value })}
                data-testid="new-cobranca-data" className="bg-[#090A0F] border-[#23283E] h-8 text-xs w-[135px]" />
              <Button size="sm" onClick={addCobranca} data-testid="new-cobranca-add"
                className="h-8 brand-gradient brand-gradient-hover text-white border-0 text-xs">Adicionar</Button>
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
