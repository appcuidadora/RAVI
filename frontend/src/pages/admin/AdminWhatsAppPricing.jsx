import { useEffect, useState } from "react";
import { api, apiError } from "@/lib/api";
import { toast } from "sonner";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const CATEGORIES = ["SERVICE", "UTILITY", "MARKETING", "AUTHENTICATION", "AUTHENTICATION_INTERNATIONAL", "OTHER"];

export default function AdminWhatsAppPricing() {
  const [metaRates, setMetaRates] = useState([]);
  const [customer, setCustomer] = useState({ rates: [], plans: [] });
  const [alertPcts, setAlertPcts] = useState("70, 80, 90");
  const [open, setOpen] = useState(null); // 'meta' | 'customer'
  const [metaForm, setMetaForm] = useState({ category: "UTILITY", meta_rate: "", effective_from: "", country: "BR", currency: "BRL" });
  const [custForm, setCustForm] = useState({ plan_id: "", category: "UTILITY", customer_rate: "", effective_from: "" });

  const load = () => {
    api.get("/admin/pricing/meta").then((r) => setMetaRates(r.data)).catch(() => {});
    api.get("/admin/pricing/customer").then((r) => setCustomer(r.data)).catch(() => {});
    api.get("/admin/settings/consumption").then((r) => setAlertPcts(r.data.alert_pcts.join(", "))).catch(() => {});
  };
  useEffect(() => { load(); }, []);

  const saveMeta = async (e) => {
    e.preventDefault();
    try {
      await api.post("/admin/pricing/meta", { ...metaForm, meta_rate: Number(metaForm.meta_rate) });
      toast.success("Tarifa Meta registrada (versionada)");
      setOpen(null); load();
    } catch (err) { toast.error(apiError(err)); }
  };

  const saveCustomer = async (e) => {
    e.preventDefault();
    try {
      await api.post("/admin/pricing/customer", { ...custForm, customer_rate: Number(custForm.customer_rate) });
      toast.success("Preço RAVI registrado para o plano");
      setOpen(null); load();
    } catch (err) { toast.error(apiError(err)); }
  };

  const saveAlerts = async () => {
    try {
      const pcts = alertPcts.split(",").map((s) => Number(s.trim())).filter((n) => n >= 1 && n <= 100);
      await api.put("/admin/settings/consumption", { alert_pcts: pcts });
      toast.success("Alertas de consumo configurados");
    } catch (err) { toast.error(apiError(err)); }
  };

  return (
    <div className="p-6 lg:p-8 space-y-6" data-testid="admin-pricing-page">
      <div className="fade-up">
        <h1 className="font-display text-2xl sm:text-3xl font-semibold tracking-tight text-zinc-100">Tarifas WhatsApp</h1>
        <p className="text-sm text-zinc-500 mt-1">Custo Meta de referência e preço RAVI por plano — tudo versionado, nada fixo em código.</p>
      </div>

      <div className="grid lg:grid-cols-2 gap-4 fade-up">
        <div className="rounded-xl border border-[#23283E] bg-[#0F111A] p-5" data-testid="meta-pricing-card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-display font-semibold text-zinc-200 text-sm">Custo Meta (referência)</h3>
            <Button size="sm" variant="outline" onClick={() => setOpen("meta")} data-testid="add-meta-rate-btn" className="border-[#3F476C] text-zinc-300">
              <Plus size={13} className="mr-1" /> Nova tarifa
            </Button>
          </div>
          {metaRates.length === 0 && <p className="text-xs text-zinc-600">Nenhuma tarifa configurada.</p>}
          <div className="space-y-2">
            {metaRates.map((r) => (
              <div key={r.id} className="flex items-center justify-between rounded-lg border border-[#23283E] bg-[#090A0F] px-3.5 py-2.5" data-testid={`meta-rate-${r.id}`}>
                <div>
                  <p className="text-xs text-zinc-200">{r.category} <span className="text-zinc-600">({r.country} • {r.currency})</span></p>
                  <p className="text-[10px] text-zinc-600">vigente desde {r.effective_from} • {r.pricing_unit}</p>
                </div>
                <span className="text-sm font-mono-code text-amber-300">$ {r.meta_rate}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-[#23283E] bg-[#0F111A] p-5" data-testid="customer-pricing-card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-display font-semibold text-zinc-200 text-sm">Preço RAVI por plano</h3>
            <Button size="sm" variant="outline" onClick={() => setOpen("customer")} data-testid="add-customer-rate-btn" className="border-[#3F476C] text-zinc-300">
              <Plus size={13} className="mr-1" /> Novo preço
            </Button>
          </div>
          {customer.rates.length === 0 && <p className="text-xs text-zinc-600">Nenhum preço configurado.</p>}
          <div className="space-y-2">
            {customer.rates.map((r) => (
              <div key={r.id} className="flex items-center justify-between rounded-lg border border-[#23283E] bg-[#090A0F] px-3.5 py-2.5" data-testid={`customer-rate-${r.id}`}>
                <div>
                  <p className="text-xs text-zinc-200">{r.plan_name} <span className="text-zinc-600">• {r.category}</span></p>
                  <p className="text-[10px] text-zinc-600">vigente desde {r.effective_from}</p>
                </div>
                <span className="text-sm font-mono-code text-emerald-300">R$ {r.customer_rate}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-[#23283E] bg-[#0F111A] p-5 fade-up max-w-md" data-testid="consumption-alerts-card">
        <h3 className="font-display font-semibold text-zinc-200 text-sm mb-1.5">Alertas de consumo</h3>
        <p className="text-[11px] text-zinc-600 mb-3">Percentuais do limite de mensagens do plano que geram alerta ao escritório (nunca bloqueia).</p>
        <div className="flex gap-2">
          <Input value={alertPcts} onChange={(e) => setAlertPcts(e.target.value)} data-testid="alert-pcts-input"
            placeholder="70, 80, 90" className="bg-[#090A0F] border-[#23283E]" />
          <Button onClick={saveAlerts} data-testid="alert-pcts-save" className="brand-gradient brand-gradient-hover text-white border-0 shrink-0">Salvar</Button>
        </div>
      </div>

      <Dialog open={open === "meta"} onOpenChange={() => setOpen(null)}>
        <DialogContent className="bg-[#0F111A] border-[#23283E]" data-testid="meta-rate-dialog">
          <DialogHeader>
            <DialogTitle className="font-display text-zinc-100">Nova tarifa Meta</DialogTitle>
            <DialogDescription className="text-zinc-500 text-xs">Referência versionada — tarifas antigas nunca são sobrescritas.</DialogDescription>
          </DialogHeader>
          <form onSubmit={saveMeta} className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label className="text-zinc-400 text-xs">Categoria</Label>
                <Select value={metaForm.category} onValueChange={(v) => setMetaForm({ ...metaForm, category: v })}>
                  <SelectTrigger data-testid="meta-rate-category" className="bg-[#090A0F] border-[#23283E]"><SelectValue /></SelectTrigger>
                  <SelectContent className="bg-[#0F111A] border-[#23283E]">
                    {CATEGORIES.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-zinc-400 text-xs">Custo Meta (por mensagem)</Label>
                <Input type="number" step="0.0001" required value={metaForm.meta_rate}
                  onChange={(e) => setMetaForm({ ...metaForm, meta_rate: e.target.value })}
                  data-testid="meta-rate-value" placeholder="0.0068" className="bg-[#090A0F] border-[#23283E]" />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label className="text-zinc-400 text-xs">Vigente a partir de</Label>
              <Input type="date" required value={metaForm.effective_from}
                onChange={(e) => setMetaForm({ ...metaForm, effective_from: e.target.value })}
                data-testid="meta-rate-from" className="bg-[#090A0F] border-[#23283E]" />
            </div>
            <Button type="submit" data-testid="meta-rate-save" className="w-full brand-gradient brand-gradient-hover text-white border-0">Registrar tarifa</Button>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={open === "customer"} onOpenChange={() => setOpen(null)}>
        <DialogContent className="bg-[#0F111A] border-[#23283E]" data-testid="customer-rate-dialog">
          <DialogHeader>
            <DialogTitle className="font-display text-zinc-100">Preço RAVI por plano</DialogTitle>
            <DialogDescription className="text-zinc-500 text-xs">Valor comercial definido pelo RAVI — independente do custo Meta.</DialogDescription>
          </DialogHeader>
          <form onSubmit={saveCustomer} className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label className="text-zinc-400 text-xs">Plano</Label>
                <Select value={custForm.plan_id} onValueChange={(v) => setCustForm({ ...custForm, plan_id: v })}>
                  <SelectTrigger data-testid="customer-rate-plan" className="bg-[#090A0F] border-[#23283E]"><SelectValue placeholder="Selecionar…" /></SelectTrigger>
                  <SelectContent className="bg-[#0F111A] border-[#23283E]">
                    {customer.plans.map((p) => <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-zinc-400 text-xs">Categoria</Label>
                <Select value={custForm.category} onValueChange={(v) => setCustForm({ ...custForm, category: v })}>
                  <SelectTrigger data-testid="customer-rate-category" className="bg-[#090A0F] border-[#23283E]"><SelectValue /></SelectTrigger>
                  <SelectContent className="bg-[#0F111A] border-[#23283E]">
                    {CATEGORIES.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label className="text-zinc-400 text-xs">Preço RAVI (R$/mensagem)</Label>
                <Input type="number" step="0.0001" required value={custForm.customer_rate}
                  onChange={(e) => setCustForm({ ...custForm, customer_rate: e.target.value })}
                  data-testid="customer-rate-value" placeholder="0.05" className="bg-[#090A0F] border-[#23283E]" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-zinc-400 text-xs">Vigente a partir de</Label>
                <Input type="date" required value={custForm.effective_from}
                  onChange={(e) => setCustForm({ ...custForm, effective_from: e.target.value })}
                  data-testid="customer-rate-from" className="bg-[#090A0F] border-[#23283E]" />
              </div>
            </div>
            <Button type="submit" data-testid="customer-rate-save" className="w-full brand-gradient brand-gradient-hover text-white border-0">Registrar preço</Button>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
