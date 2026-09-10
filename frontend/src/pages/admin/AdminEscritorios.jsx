import { useEffect, useState } from "react";
import { api, apiError } from "@/lib/api";
import { toast } from "sonner";
import { Eye, Pencil } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const STATUS_META = {
  trial: "bg-blue-950/60 border-blue-700/50 text-blue-400",
  active: "bg-emerald-950/60 border-emerald-700/50 text-emerald-400",
  past_due: "bg-amber-950/60 border-amber-700/50 text-amber-400",
  suspended: "bg-rose-950/60 border-rose-700/50 text-rose-400",
  canceled: "bg-zinc-800 border-zinc-700 text-zinc-400",
};
const STATUS_LABELS = { trial: "Trial", active: "Ativo", past_due: "Em atraso", suspended: "Suspenso", canceled: "Cancelado" };

export default function AdminEscritorios() {
  const [data, setData] = useState({ offices: [], plans: [] });
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({});
  const [impOffice, setImpOffice] = useState(null);
  const [motivo, setMotivo] = useState("");

  const load = () => api.get("/admin/offices").then((r) => setData(r.data)).catch((e) => toast.error(apiError(e)));
  useEffect(() => { load(); }, []);

  const openEdit = (o) => {
    setEditing(o);
    setForm({ name: o.name, status: o.status, plan_id: o.plan_id || "", valor_mensal: o.valor_mensal,
              valor_anual: o.valor_anual, ciclo: o.ciclo, vencimento: o.vencimento, observacoes: o.observacoes });
  };

  const save = async () => {
    try {
      await api.patch(`/admin/offices/${editing.id}`, { ...form, plan_id: form.plan_id || null });
      toast.success("Escritório atualizado");
      setEditing(null);
      load();
    } catch (e) { toast.error(apiError(e)); }
  };

  const impersonate = async () => {
    try {
      const { data } = await api.post(`/admin/offices/${impOffice.id}/impersonate`, { motivo });
      sessionStorage.setItem("ravi_impersonate", JSON.stringify({
        token: data.token, log_id: data.log_id, office_name: data.office_name }));
      window.location.href = "/dashboard";
    } catch (e) { toast.error(apiError(e)); }
  };

  return (
    <div className="p-6 lg:p-8 space-y-6" data-testid="admin-escritorios-page">
      <div className="fade-up">
        <h1 className="font-display text-2xl sm:text-3xl font-semibold tracking-tight text-zinc-100">Escritórios</h1>
        <p className="text-sm text-zinc-500 mt-1">{data.offices.length} escritórios na plataforma.</p>
      </div>

      <div className="rounded-xl border border-[#23283E] bg-[#0F111A] overflow-hidden fade-up" data-testid="offices-table">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[#23283E] text-left">
              <th className="px-5 py-3 font-mono-code text-[10px] uppercase tracking-widest text-zinc-500">Escritório</th>
              <th className="px-5 py-3 font-mono-code text-[10px] uppercase tracking-widest text-zinc-500 hidden md:table-cell">Plano</th>
              <th className="px-5 py-3 font-mono-code text-[10px] uppercase tracking-widest text-zinc-500 hidden lg:table-cell">Uso</th>
              <th className="px-5 py-3 font-mono-code text-[10px] uppercase tracking-widest text-zinc-500 hidden sm:table-cell">WhatsApp</th>
              <th className="px-5 py-3 font-mono-code text-[10px] uppercase tracking-widest text-zinc-500">Status</th>
              <th className="px-5 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {data.offices.map((o) => (
              <tr key={o.id} className="border-b border-[#23283E]/50 hover:bg-[#161925]/50 transition-colors duration-150" data-testid={`office-row-${o.id}`}>
                <td className="px-5 py-3.5">
                  <p className="font-medium text-zinc-200">{o.name}</p>
                  <p className="text-xs text-zinc-500">{o.responsavel} • {o.responsavel_email}</p>
                </td>
                <td className="px-5 py-3.5 hidden md:table-cell">
                  <span className="text-xs text-indigo-300">{o.plan_name}</span>
                  {o.valor_mensal > 0 && <p className="text-[11px] text-zinc-500">R$ {o.valor_mensal}/mês</p>}
                </td>
                <td className="px-5 py-3.5 hidden lg:table-cell">
                  {o.uso_pct != null ? (
                    <div>
                      <p className="text-xs text-zinc-300">{o.processos}/{o.process_limit} processos</p>
                      <div className="w-24 h-1.5 rounded-full bg-[#1E2235] mt-1.5">
                        <div className={`h-full rounded-full ${o.uso_pct >= 100 ? "bg-rose-500" : o.uso_pct >= 90 ? "bg-amber-500" : "brand-gradient"}`}
                          style={{ width: `${Math.min(o.uso_pct, 100)}%` }} />
                      </div>
                      <p className={`text-[10px] mt-1 ${o.uso_pct >= 100 ? "text-rose-400" : "text-zinc-600"}`}>{o.uso_pct}% do limite</p>
                    </div>
                  ) : <span className="text-xs text-zinc-600">{o.processos} processos</span>}
                </td>
                <td className="px-5 py-3.5 hidden sm:table-cell">
                  <span className={`text-xs ${o.whatsapp_status === "connected" ? "text-emerald-400" : o.whatsapp_status === "token_expired" ? "text-amber-400" : "text-zinc-600"}`}>
                    {o.whatsapp_status === "connected" ? "🟢 " : o.whatsapp_status === "token_expired" ? "🟠 " : "⚪ "}{o.whatsapp_status}
                  </span>
                </td>
                <td className="px-5 py-3.5">
                  <Badge className={`border ${STATUS_META[o.status]}`}>{STATUS_LABELS[o.status]}</Badge>
                </td>
                <td className="px-5 py-3.5 text-right whitespace-nowrap">
                  <button onClick={() => openEdit(o)} data-testid={`edit-office-${o.id}`} title="Editar"
                    className="text-zinc-500 hover:text-zinc-200 mr-3 transition-colors duration-150"><Pencil size={15} /></button>
                  <button onClick={() => { setImpOffice(o); setMotivo(""); }} data-testid={`impersonate-office-${o.id}`} title="Visualizar como escritório"
                    className="text-zinc-500 hover:text-indigo-300 transition-colors duration-150"><Eye size={15} /></button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Dialog open={!!editing} onOpenChange={() => setEditing(null)}>
        <DialogContent className="bg-[#0F111A] border-[#23283E]" data-testid="office-edit-dialog">
          <DialogHeader><DialogTitle className="font-display text-zinc-100">Editar — {editing?.name}</DialogTitle></DialogHeader>
          <div className="space-y-4 max-h-[70vh] overflow-y-auto pr-1">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label className="text-zinc-400 text-xs">Status</Label>
                <Select value={form.status} onValueChange={(v) => setForm({ ...form, status: v })}>
                  <SelectTrigger data-testid="office-status-select" className="bg-[#090A0F] border-[#23283E]"><SelectValue /></SelectTrigger>
                  <SelectContent className="bg-[#0F111A] border-[#23283E]">
                    {Object.entries(STATUS_LABELS).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-zinc-400 text-xs">Plano</Label>
                <Select value={form.plan_id} onValueChange={(v) => setForm({ ...form, plan_id: v })}>
                  <SelectTrigger data-testid="office-plan-select" className="bg-[#090A0F] border-[#23283E]"><SelectValue placeholder="Sem plano" /></SelectTrigger>
                  <SelectContent className="bg-[#0F111A] border-[#23283E]">
                    {data.plans.map((p) => <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div className="space-y-1.5">
                <Label className="text-zinc-400 text-xs">Valor mensal R$</Label>
                <Input type="number" step="0.01" value={form.valor_mensal} onChange={(e) => setForm({ ...form, valor_mensal: Number(e.target.value) })}
                  data-testid="office-valor-input" className="bg-[#090A0F] border-[#23283E]" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-zinc-400 text-xs">Ciclo</Label>
                <Select value={form.ciclo} onValueChange={(v) => setForm({ ...form, ciclo: v })}>
                  <SelectTrigger data-testid="office-ciclo-select" className="bg-[#090A0F] border-[#23283E]"><SelectValue /></SelectTrigger>
                  <SelectContent className="bg-[#0F111A] border-[#23283E]">
                    <SelectItem value="mensal">Mensal</SelectItem>
                    <SelectItem value="anual">Anual</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-zinc-400 text-xs">Vencimento</Label>
                <Input type="date" value={form.vencimento} onChange={(e) => setForm({ ...form, vencimento: e.target.value })}
                  data-testid="office-vencimento-input" className="bg-[#090A0F] border-[#23283E]" />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label className="text-zinc-400 text-xs">Observações internas</Label>
              <Textarea value={form.observacoes} onChange={(e) => setForm({ ...form, observacoes: e.target.value })}
                data-testid="office-obs-input" rows={3} className="bg-[#090A0F] border-[#23283E]" />
            </div>
            <p className="text-[11px] text-zinc-600">Suspender remove o acesso operacional do escritório sem apagar dados. Cancelar registra churn.</p>
            <Button onClick={save} data-testid="office-save-btn" className="w-full brand-gradient brand-gradient-hover text-white border-0">Salvar</Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={!!impOffice} onOpenChange={() => setImpOffice(null)}>
        <DialogContent className="bg-[#0F111A] border-[#23283E]" data-testid="impersonate-dialog">
          <DialogHeader><DialogTitle className="font-display text-zinc-100">Visualizar como escritório</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <p className="text-sm text-zinc-400">
              Você verá o RAVI APP como <strong className="text-zinc-200">{impOffice?.name}</strong>. Nenhuma senha é compartilhada.
              O acesso é auditado (administrador, escritório, data/hora, motivo).
            </p>
            <div className="space-y-1.5">
              <Label className="text-zinc-400 text-xs">Motivo do acesso (obrigatório)</Label>
              <Input value={motivo} onChange={(e) => setMotivo(e.target.value)} data-testid="impersonate-motivo-input"
                placeholder="Ex: suporte ao chamado #123" className="bg-[#090A0F] border-[#23283E]" />
            </div>
            <Button onClick={impersonate} disabled={!motivo.trim()} data-testid="impersonate-confirm-btn"
              className="w-full brand-gradient brand-gradient-hover text-white border-0">
              Iniciar sessão de suporte
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
