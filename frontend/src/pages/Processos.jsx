import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, apiError } from "@/lib/api";
import { toast } from "sonner";
import { Plus, ChevronRight, Lock, FileUp, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const EMPTY = { number: "", client_id: "", status: "Em andamento", ultima_movimentacao: "", valor_causa: "", forma_pagamento: "" };

export default function Processos() {
  const [processes, setProcesses] = useState([]);
  const [clients, setClients] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [search, setSearch] = useState("");
  const [newClient, setNewClient] = useState({ name: "", phone: "" });
  const [cobrancas, setCobrancas] = useState([]);
  const [pdfFile, setPdfFile] = useState(null);
  const fileRef = useRef(null);
  const [importOpen, setImportOpen] = useState(false);
  const [importFile, setImportFile] = useState(null);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState(null);
  const importRef = useRef(null);

  const importPdf = async () => {
    if (!importFile) return;
    setImporting(true);
    setImportResult(null);
    try {
      const fd = new FormData();
      fd.append("file", importFile);
      const { data } = await api.post("/processes/import-pdf", fd, { headers: { "Content-Type": "multipart/form-data" } });
      setImportResult(data);
      load();
    } catch (err) {
      toast.error(apiError(err, "Não foi possível importar este PDF"));
    } finally {
      setImporting(false);
    }
  };

  const load = () => api.get("/processes").then((r) => setProcesses(r.data)).catch(() => {});
  useEffect(() => {
    load();
    api.get("/clients").then((r) => setClients(r.data)).catch(() => {});
  }, []);

  const save = async (e) => {
    e.preventDefault();
    try {
      const isNew = form.client_id === "__new__";
      const payload = {
        number: form.number, status: form.status, ultima_movimentacao: form.ultima_movimentacao,
        client_id: isNew ? null : form.client_id || null,
        new_client_name: isNew ? newClient.name : null,
        new_client_phone: isNew ? newClient.phone : null,
        valor_causa: form.valor_causa ? Number(form.valor_causa) : null,
        forma_pagamento: form.forma_pagamento || "",
        cobrancas: cobrancas.filter((c) => c.valor && c.data_vencimento),
      };
      const { data } = await api.post("/processes", payload);
      if (pdfFile) {
        try {
          const fd = new FormData();
          fd.append("file", pdfFile);
          await api.post(`/processes/${data.id}/document`, fd, { headers: { "Content-Type": "multipart/form-data" } });
          toast.success("PDF anexado — a IA já consegue ler o documento");
        } catch {
          toast.warning("Processo criado, mas o PDF não foi anexado. Tente na tela do processo.");
        }
      }
      setOpen(false);
      setForm(EMPTY);
      setNewClient({ name: "", phone: "" });
      setCobrancas([]);
      setPdfFile(null);
      if (data.tribunal) {
        toast.success(`Processo identificado: ${data.tribunal}`);
      } else {
        toast.success("Processo cadastrado");
      }
      load();
    } catch (err) {
      toast.error(apiError(err));
    }
  };

  const filtered = processes.filter((p) =>
    (p.numero_formatado || p.number || "").includes(search) ||
    (p.client_name || "").toLowerCase().includes(search.toLowerCase()));

  return (
    <div className="p-6 lg:p-8 space-y-6" data-testid="processos-page">
      <div className="flex items-center justify-between fade-up">
        <div>
          <h1 className="font-display text-2xl sm:text-3xl font-semibold tracking-tight text-zinc-100">Processos</h1>
          <p className="text-sm text-zinc-500 mt-1">Informe o número. O Ravi identifica tribunal e segmento automaticamente.</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={() => { setImportOpen(true); setImportFile(null); setImportResult(null); }}
            data-testid="import-pdf-btn" className="border-[#3F476C] text-zinc-300">
            <FileUp size={16} className="mr-1.5" /> Importar PDF
          </Button>
          <Button onClick={() => { setForm(EMPTY); setNewClient({ name: "", phone: "" }); setCobrancas([]); setPdfFile(null); setOpen(true); }}
            data-testid="add-process-btn" className="brand-gradient brand-gradient-hover text-white border-0">
            <Plus size={16} className="mr-1.5" /> Novo processo
          </Button>
        </div>
      </div>

      <Input placeholder="Buscar por número CNJ ou cliente…" value={search} onChange={(e) => setSearch(e.target.value)}
        data-testid="processes-search-input" className="max-w-sm bg-[#0F111A] border-[#23283E]" />

      <div className="rounded-xl border border-[#23283E] bg-[#0F111A] overflow-hidden fade-up" data-testid="processes-table">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[#23283E] text-left">
              <th className="px-5 py-3 font-mono-code text-[10px] uppercase tracking-widest text-zinc-500">Número</th>
              <th className="px-5 py-3 font-mono-code text-[10px] uppercase tracking-widest text-zinc-500 hidden md:table-cell">Tribunal</th>
              <th className="px-5 py-3 font-mono-code text-[10px] uppercase tracking-widest text-zinc-500 hidden sm:table-cell">Cliente</th>
              <th className="px-5 py-3 font-mono-code text-[10px] uppercase tracking-widest text-zinc-500">Situação</th>
              <th className="px-5 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 && (
              <tr><td colSpan={5} className="px-5 py-10 text-center text-zinc-500" data-testid="processes-empty">
                Nenhum processo cadastrado ainda.
              </td></tr>
            )}
            {filtered.map((p) => (
              <tr key={p.id} className="border-b border-[#23283E]/50 hover:bg-[#161925]/50 transition-colors duration-150" data-testid={`process-row-${p.id}`}>
                <td className="px-5 py-3.5">
                  <span className="font-mono-code text-xs text-indigo-300">{p.numero_formatado || p.number}</span>
                  {p.acesso_restrito && (
                    <span className="ml-2 inline-flex items-center gap-1 text-[10px] text-amber-400"><Lock size={10} /> acesso restrito</span>
                  )}
                </td>
                <td className="px-5 py-3.5 text-zinc-400 text-xs hidden md:table-cell">{p.tribunal || "—"}</td>
                <td className="px-5 py-3.5 text-zinc-300 hidden sm:table-cell">{p.client_name || "—"}</td>
                <td className="px-5 py-3.5 text-zinc-300">{p.status}</td>
                <td className="px-5 py-3.5 text-right">
                  <Link to={`/processos/${p.id}`} data-testid={`open-process-${p.id}`}
                    className="inline-flex items-center text-zinc-500 hover:text-zinc-200 transition-colors duration-150">
                    <ChevronRight size={16} />
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="bg-[#0F111A] border-[#23283E] max-h-[90vh] flex flex-col" data-testid="process-dialog">
          <DialogHeader>
            <DialogTitle className="font-display text-zinc-100">Novo processo</DialogTitle>
            <DialogDescription className="text-zinc-500 text-xs">Informe o número CNJ. O Ravi identifica tribunal e segmento automaticamente.</DialogDescription>
          </DialogHeader>
          <form id="process-form" onSubmit={save} className="space-y-4 overflow-y-auto pr-1 flex-1 min-h-0">
            <div className="space-y-1.5">
              <Label className="text-zinc-400 text-xs">Número do processo (CNJ)</Label>
              <Input required value={form.number} onChange={(e) => setForm({ ...form, number: e.target.value })}
                data-testid="process-number-input" placeholder="1001234-56.2025.8.26.0100"
                className="bg-[#090A0F] border-[#23283E] font-mono-code text-xs" />
            </div>
            <div className="space-y-1.5">
              <Label className="text-zinc-400 text-xs">Cliente</Label>
              <Select value={form.client_id} onValueChange={(v) => setForm({ ...form, client_id: v })}>
                <SelectTrigger data-testid="process-client-select" className="bg-[#090A0F] border-[#23283E]">
                  <SelectValue placeholder="Vincular cliente (opcional)" />
                </SelectTrigger>
                <SelectContent className="bg-[#0F111A] border-[#23283E]">
                  <SelectItem value="__new__" className="text-indigo-300">+ Cadastrar novo cliente</SelectItem>
                  {clients.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            {form.client_id === "__new__" && (
              <div className="grid grid-cols-2 gap-3 rounded-lg border border-indigo-800/40 bg-indigo-950/20 p-3" data-testid="new-client-fields">
                <div className="space-y-1.5">
                  <Label className="text-zinc-400 text-xs">Nome do cliente</Label>
                  <Input required value={newClient.name} onChange={(e) => setNewClient({ ...newClient, name: e.target.value })}
                    data-testid="process-new-client-name" placeholder="Carlos Eduardo" className="bg-[#090A0F] border-[#23283E]" />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-zinc-400 text-xs">WhatsApp</Label>
                  <Input required value={newClient.phone} onChange={(e) => setNewClient({ ...newClient, phone: e.target.value })}
                    data-testid="process-new-client-phone" placeholder="+55 11 98765-4321" className="bg-[#090A0F] border-[#23283E]" />
                </div>
              </div>
            )}
            <div className="space-y-1.5">
              <Label className="text-zinc-400 text-xs">Arquivo do processo (PDF, opcional)</Label>
              <button type="button" onClick={() => fileRef.current?.click()} data-testid="process-pdf-btn"
                className="w-full rounded-lg border border-dashed border-[#3F476C] bg-[#090A0F] px-3 py-2.5 text-left text-xs text-zinc-400 hover:border-indigo-500/50 hover:text-zinc-200 transition-colors duration-150 truncate">
                {pdfFile ? `📄 ${pdfFile.name}` : "Anexar PDF — a IA lê o documento e usa nas respostas ao cliente"}
              </button>
              <input ref={fileRef} type="file" accept="application/pdf" className="hidden"
                onChange={(e) => setPdfFile(e.target.files?.[0] || null)} data-testid="process-pdf-input" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label className="text-zinc-400 text-xs">Situação</Label>
                <Input value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}
                  data-testid="process-status-input" className="bg-[#090A0F] border-[#23283E]" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-zinc-400 text-xs">Última movimentação</Label>
                <Input value={form.ultima_movimentacao} onChange={(e) => setForm({ ...form, ultima_movimentacao: e.target.value })}
                  data-testid="process-lastmov-input" placeholder="18/08/2026" className="bg-[#090A0F] border-[#23283E]" />
              </div>
            </div>
            <div className="pt-2 border-t border-[#23283E] space-y-3">
              <p className="font-mono-code text-[10px] uppercase tracking-widest text-zinc-500">Financeiro (opcional)</p>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label className="text-zinc-400 text-xs">Valor da causa (R$)</Label>
                  <Input type="number" step="0.01" min="0" value={form.valor_causa}
                    onChange={(e) => setForm({ ...form, valor_causa: e.target.value })}
                    data-testid="process-valor-input" placeholder="15000.00" className="bg-[#090A0F] border-[#23283E]" />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-zinc-400 text-xs">Forma de pagamento</Label>
                  <Select value={form.forma_pagamento} onValueChange={(v) => setForm({ ...form, forma_pagamento: v })}>
                    <SelectTrigger data-testid="process-pagamento-select" className="bg-[#090A0F] border-[#23283E]">
                      <SelectValue placeholder="Selecionar" />
                    </SelectTrigger>
                    <SelectContent className="bg-[#0F111A] border-[#23283E]">
                      <SelectItem value="PIX">PIX</SelectItem>
                      <SelectItem value="Boleto">Boleto</SelectItem>
                      <SelectItem value="Cartão de crédito">Cartão de crédito</SelectItem>
                      <SelectItem value="Transferência">Transferência</SelectItem>
                      <SelectItem value="Dinheiro">Dinheiro</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label className="text-zinc-400 text-xs">Cobranças — lembrete automático no WhatsApp 5 dias antes e no dia</Label>
                  <button type="button" onClick={() => setCobrancas([...cobrancas, { valor: "", data_vencimento: "", descricao: "" }])}
                    data-testid="add-cobranca-btn" className="text-xs text-indigo-400 hover:text-indigo-300">+ adicionar</button>
                </div>
                {cobrancas.map((c, i) => (
                  <div key={i} className="grid grid-cols-[1fr_auto_auto] gap-2 items-center" data-testid={`cobranca-row-${i}`}>
                    <Input type="number" step="0.01" placeholder="Valor R$" value={c.valor}
                      onChange={(e) => setCobrancas(cobrancas.map((x, j) => j === i ? { ...x, valor: e.target.value } : x))}
                      data-testid={`cobranca-valor-${i}`} className="bg-[#090A0F] border-[#23283E]" />
                    <Input type="date" value={c.data_vencimento}
                      onChange={(e) => setCobrancas(cobrancas.map((x, j) => j === i ? { ...x, data_vencimento: e.target.value } : x))}
                      data-testid={`cobranca-data-${i}`} className="bg-[#090A0F] border-[#23283E] w-[150px]" />
                    <button type="button" onClick={() => setCobrancas(cobrancas.filter((_, j) => j !== i))}
                      data-testid={`cobranca-remove-${i}`} className="text-zinc-600 hover:text-rose-400 px-1">×</button>
                  </div>
                ))}
              </div>
            </div>
          </form>
          <div className="pt-3 border-t border-[#23283E] shrink-0">
            <Button type="submit" form="process-form" data-testid="process-save-btn"
              className="w-full brand-gradient brand-gradient-hover text-white border-0">
              Cadastrar processo
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={importOpen} onOpenChange={setImportOpen}>
        <DialogContent className="bg-[#0F111A] border-[#23283E]" data-testid="import-dialog">
          <DialogHeader>
            <DialogTitle className="font-display text-zinc-100">Importar processo de PDF</DialogTitle>
            <DialogDescription className="text-zinc-500 text-xs">A IA identifica número, partes, tribunal e movimentações do documento.</DialogDescription>
          </DialogHeader>
          {!importResult ? (
            <div className="space-y-4">
              <p className="text-xs text-zinc-500 leading-relaxed">
                O Ravi lê o documento e identifica automaticamente: número CNJ, tribunal, partes, assunto,
                movimentações e situação. O que não estiver no documento será informado como "não identificado" — nada é inventado.
              </p>
              <button type="button" onClick={() => importRef.current?.click()} data-testid="import-file-btn"
                className="w-full rounded-lg border border-dashed border-[#3F476C] bg-[#090A0F] px-3 py-6 text-center text-xs text-zinc-400 hover:border-indigo-500/50 hover:text-zinc-200 transition-colors duration-150">
                {importFile ? `📄 ${importFile.name}` : "Selecionar PDF do processo"}
              </button>
              <input ref={importRef} type="file" accept="application/pdf" className="hidden"
                onChange={(e) => setImportFile(e.target.files?.[0] || null)} data-testid="import-file-input" />
              <Button onClick={importPdf} disabled={!importFile || importing} data-testid="import-submit-btn"
                className="w-full brand-gradient brand-gradient-hover text-white border-0">
                {importing ? <><Loader2 size={15} className="mr-2 animate-spin" /> Lendo documento…</> : "Importar e identificar"}
              </Button>
            </div>
          ) : (
            <div className="space-y-4" data-testid="import-result">
              {importResult.restricted && (
                <p className="text-xs text-amber-300 bg-amber-950/40 border border-amber-700/40 rounded-lg px-3 py-2.5" data-testid="import-restricted-warning">
                  Este processo possui acesso restrito (segredo de justiça). O Ravi não tenta contornar restrições — apenas o conteúdo deste documento autorizado foi usado.
                </p>
              )}
              <div className="text-xs space-y-1.5">
                <p className="text-zinc-400">Número: <span className="font-mono-code text-indigo-300">{importResult.process.numero_formatado || importResult.process.number}</span></p>
                {importResult.process.tribunal && <p className="text-zinc-400">Tribunal: <span className="text-zinc-200">{importResult.process.tribunal}</span></p>}
                {importResult.process.subject && <p className="text-zinc-400">Assunto: <span className="text-zinc-200">{importResult.process.subject}</span></p>}
                <p className="text-zinc-400">Partes: <span className="text-zinc-200">{(importResult.process.partes || []).length} identificada(s)</span></p>
                <p className="text-zinc-400">Movimentações: <span className="text-zinc-200">{(importResult.process.movimentacoes || []).length} extraída(s)</span></p>
              </div>
              {importResult.nao_identificados.length > 0 && (
                <p className="text-[11px] text-zinc-500" data-testid="import-not-identified">
                  Não identificado no documento: {importResult.nao_identificados.join(", ")}.
                </p>
              )}
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => { setImportOpen(false); setImportResult(null); }}
                  data-testid="import-close-btn" className="border-[#3F476C] text-zinc-300 flex-1">Fechar</Button>
                <a href={`/processos/${importResult.process.id}`} className="flex-1" data-testid="import-open-process">
                  <Button className="w-full brand-gradient brand-gradient-hover text-white border-0">Ver processo</Button>
                </a>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
