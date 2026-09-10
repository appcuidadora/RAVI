import { useEffect, useState } from "react";
import { api, apiError } from "@/lib/api";
import { toast } from "sonner";
import { Plus, CheckCircle2, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const fmt = (v) => `R$ ${Number(v || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}`;
const STATUS_META = {
  pending: ["Pendente", "bg-amber-950/60 border-amber-700/50 text-amber-400"],
  paid: ["Pago", "bg-emerald-950/60 border-emerald-700/50 text-emerald-400"],
  overdue: ["Vencido", "bg-rose-950/60 border-rose-700/50 text-rose-400"],
  canceled: ["Cancelado", "bg-zinc-800 border-zinc-700 text-zinc-400"],
  refunded: ["Estornado", "bg-blue-950/60 border-blue-700/50 text-blue-400"],
};

export default function AdminFinanceiro() {
  const [ov, setOv] = useState(null);
  const [data, setData] = useState({ charges: [], offices: [] });
  const [filter, setFilter] = useState("all");
  const [addOpen, setAddOpen] = useState(false);
  const [payTarget, setPayTarget] = useState(null);
  const [form, setForm] = useState({ office_id: "", competencia: "", vencimento: "", valor: "", desconto: 0 });
  const [payForm, setPayForm] = useState({ valor: "", metodo: "PIX", referencia: "" });

  const load = () => {
    api.get("/admin/billing/overview").then((r) => setOv(r.data)).catch(() => {});
    api.get(`/admin/billing/charges?status=${filter}`).then((r) => setData(r.data)).catch(() => {});
  };
  useEffect(() => { load(); }, [filter]); // eslint-disable-line

  const createCharge = async (e) => {
    e.preventDefault();
    try {
      await api.post("/admin/billing/charges", { ...form, valor: Number(form.valor), desconto: Number(form.desconto) || 0 });
      toast.success("Cobrança criada");
      setAddOpen(false);
      load();
    } catch (err) { toast.error(apiError(err)); }
  };

  const pay = async () => {
    try {
      await api.post(`/admin/billing/charges/${payTarget.id}/pay`, { ...payForm, valor: Number(payForm.valor) });
      toast.success("Recebimento registrado");
      setPayTarget(null);
      load();
    } catch (err) { toast.error(apiError(err)); }
  };

  const cancel = async (c) => {
    try {
      await api.post(`/admin/billing/charges/${c.id}/cancel`);
      toast.success("Cobrança cancelada");
      load();
    } catch (err) { toast.error(apiError(err)); }
  };

  const cards = [
    ["MRR", fmt(ov?.mrr)], ["ARR", fmt(ov?.arr)], ["Ticket médio", fmt(ov?.ticket_medio)],
    ["Faturado no mês", fmt(ov?.faturado_mes)], ["Recebido (total)", fmt(ov?.recebido_total)],
    ["A receber", fmt(ov?.a_receber)], ["Vencido", fmt(ov?.vencido)],
    ["Contas vencidas", ov?.contas_vencidas], ["Descontos concedidos", fmt(ov?.descontos_concedidos)],
  ];

  return (
    <div className="p-6 lg:p-8 space-y-6" data-testid="admin-financeiro-page">
      <div className="flex items-center justify-between fade-up">
        <div>
          <h1 className="font-display text-2xl sm:text-3xl font-semibold tracking-tight text-zinc-100">Financeiro</h1>
          <p className="text-sm text-zinc-500 mt-1">Receita recorrente do SaaS. Gateway de pagamento: camada de abstração pronta (Stripe/Mercado Pago/Asaas).</p>
        </div>
        <Button onClick={() => setAddOpen(true)} data-testid="add-charge-btn" className="brand-gradient brand-gradient-hover text-white border-0">
          <Plus size={16} className="mr-1.5" /> Nova cobrança
        </Button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-3 fade-up" data-testid="billing-cards">
        {cards.map(([l, v]) => (
          <div key={l} className="rounded-xl border border-[#23283E] bg-[#0F111A] p-4">
            <p className="font-mono-code text-[10px] uppercase tracking-widest text-zinc-500">{l}</p>
            <p className="font-display text-xl font-bold text-zinc-100 mt-2">{v ?? "—"}</p>
          </div>
        ))}
        {ov && (
          <div className="rounded-xl border border-[#23283E] bg-[#0F111A] p-4 col-span-2 md:col-span-3 xl:col-span-1" data-testid="aging-card">
            <p className="font-mono-code text-[10px] uppercase tracking-widest text-zinc-500">Aging</p>
            <div className="text-[11px] text-zinc-400 mt-2 space-y-0.5">
              {Object.entries(ov.aging).map(([k, v]) => <p key={k}>{k} dias: <span className="text-zinc-200">{fmt(v)}</span></p>)}
            </div>
          </div>
        )}
      </div>

      <div className="flex gap-1.5 fade-up">
        {[["all", "Todas"], ["pending", "Pendentes"], ["paid", "Pagas"], ["canceled", "Canceladas"]].map(([v, l]) => (
          <button key={v} onClick={() => setFilter(v)} data-testid={`charges-tab-${v}`}
            className={`text-xs px-3 py-1.5 rounded-full border transition-colors duration-150 ${filter === v ? "border-indigo-500/60 text-indigo-300 bg-indigo-950/40" : "border-[#23283E] text-zinc-500 hover:text-zinc-300"}`}>
            {l}
          </button>
        ))}
      </div>

      <div className="rounded-xl border border-[#23283E] bg-[#0F111A] overflow-hidden fade-up" data-testid="charges-table">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[#23283E] text-left">
              <th className="px-5 py-3 font-mono-code text-[10px] uppercase tracking-widest text-zinc-500">Escritório</th>
              <th className="px-5 py-3 font-mono-code text-[10px] uppercase tracking-widest text-zinc-500 hidden sm:table-cell">Competência</th>
              <th className="px-5 py-3 font-mono-code text-[10px] uppercase tracking-widest text-zinc-500">Vencimento</th>
              <th className="px-5 py-3 font-mono-code text-[10px] uppercase tracking-widest text-zinc-500">Valor final</th>
              <th className="px-5 py-3 font-mono-code text-[10px] uppercase tracking-widest text-zinc-500">Status</th>
              <th className="px-5 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {data.charges.length === 0 && (
              <tr><td colSpan={6} className="px-5 py-10 text-center text-zinc-500" data-testid="charges-empty">Nenhuma cobrança.</td></tr>
            )}
            {data.charges.map((c) => {
              const effective = c.status === "pending" && c.dias_atraso > 0 ? "overdue" : c.status;
              const [label, cls] = STATUS_META[effective] || STATUS_META.pending;
              return (
                <tr key={c.id} className="border-b border-[#23283E]/50 hover:bg-[#161925]/50 transition-colors duration-150" data-testid={`charge-row-${c.id}`}>
                  <td className="px-5 py-3.5 text-zinc-200">{c.office_name}</td>
                  <td className="px-5 py-3.5 text-zinc-400 hidden sm:table-cell">{c.competencia}</td>
                  <td className="px-5 py-3.5 text-zinc-300">
                    {new Date(c.vencimento + "T12:00:00").toLocaleDateString("pt-BR")}
                    {c.dias_atraso > 0 && <span className="text-rose-400 text-xs ml-1">({c.dias_atraso}d)</span>}
                  </td>
                  <td className="px-5 py-3.5 text-zinc-200">{fmt(c.valor_final)}</td>
                  <td className="px-5 py-3.5"><Badge className={`border ${cls}`}>{label}</Badge></td>
                  <td className="px-5 py-3.5 text-right whitespace-nowrap">
                    {c.status === "pending" && (
                      <>
                        <button onClick={() => { setPayTarget(c); setPayForm({ valor: c.valor_final, metodo: "PIX", referencia: "" }); }}
                          data-testid={`pay-charge-${c.id}`} title="Registrar recebimento"
                          className="text-zinc-500 hover:text-emerald-400 mr-3 transition-colors duration-150"><CheckCircle2 size={15} /></button>
                        <button onClick={() => cancel(c)} data-testid={`cancel-charge-${c.id}`} title="Cancelar"
                          className="text-zinc-500 hover:text-rose-400 transition-colors duration-150"><XCircle size={15} /></button>
                      </>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent className="bg-[#0F111A] border-[#23283E]" data-testid="charge-dialog">
          <DialogHeader><DialogTitle className="font-display text-zinc-100">Nova cobrança</DialogTitle></DialogHeader>
          <form onSubmit={createCharge} className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-zinc-400 text-xs">Escritório</Label>
              <Select value={form.office_id} onValueChange={(v) => setForm({ ...form, office_id: v })}>
                <SelectTrigger data-testid="charge-office-select" className="bg-[#090A0F] border-[#23283E]"><SelectValue placeholder="Selecionar…" /></SelectTrigger>
                <SelectContent className="bg-[#0F111A] border-[#23283E]">
                  {data.offices.map((o) => <SelectItem key={o.id} value={o.id}>{o.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label className="text-zinc-400 text-xs">Competência</Label>
                <Input type="month" required value={form.competencia} onChange={(e) => setForm({ ...form, competencia: e.target.value })}
                  data-testid="charge-competencia" className="bg-[#090A0F] border-[#23283E]" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-zinc-400 text-xs">Vencimento</Label>
                <Input type="date" required value={form.vencimento} onChange={(e) => setForm({ ...form, vencimento: e.target.value })}
                  data-testid="charge-vencimento" className="bg-[#090A0F] border-[#23283E]" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-zinc-400 text-xs">Valor R$</Label>
                <Input type="number" step="0.01" required value={form.valor} onChange={(e) => setForm({ ...form, valor: e.target.value })}
                  data-testid="charge-valor" className="bg-[#090A0F] border-[#23283E]" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-zinc-400 text-xs">Desconto R$</Label>
                <Input type="number" step="0.01" value={form.desconto} onChange={(e) => setForm({ ...form, desconto: e.target.value })}
                  data-testid="charge-desconto" className="bg-[#090A0F] border-[#23283E]" />
              </div>
            </div>
            <Button type="submit" data-testid="charge-save-btn" className="w-full brand-gradient brand-gradient-hover text-white border-0">Criar cobrança</Button>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={!!payTarget} onOpenChange={() => setPayTarget(null)}>
        <DialogContent className="bg-[#0F111A] border-[#23283E]" data-testid="pay-dialog">
          <DialogHeader><DialogTitle className="font-display text-zinc-100">Registrar recebimento</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label className="text-zinc-400 text-xs">Valor recebido R$</Label>
                <Input type="number" step="0.01" value={payForm.valor} onChange={(e) => setPayForm({ ...payForm, valor: e.target.value })}
                  data-testid="pay-valor" className="bg-[#090A0F] border-[#23283E]" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-zinc-400 text-xs">Método</Label>
                <Select value={payForm.metodo} onValueChange={(v) => setPayForm({ ...payForm, metodo: v })}>
                  <SelectTrigger data-testid="pay-metodo" className="bg-[#090A0F] border-[#23283E]"><SelectValue /></SelectTrigger>
                  <SelectContent className="bg-[#0F111A] border-[#23283E]">
                    <SelectItem value="PIX">PIX</SelectItem><SelectItem value="Boleto">Boleto</SelectItem>
                    <SelectItem value="Cartão">Cartão</SelectItem><SelectItem value="Transferência">Transferência</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="space-y-1.5">
              <Label className="text-zinc-400 text-xs">Referência (opcional)</Label>
              <Input value={payForm.referencia} onChange={(e) => setPayForm({ ...payForm, referencia: e.target.value })}
                data-testid="pay-referencia" className="bg-[#090A0F] border-[#23283E]" />
            </div>
            <Button onClick={pay} data-testid="pay-confirm-btn" className="w-full brand-gradient brand-gradient-hover text-white border-0">Confirmar recebimento</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
