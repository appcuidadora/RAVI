import { useEffect, useState } from "react";
import { api, apiError } from "@/lib/api";
import { toast } from "sonner";
import { Plus, Pencil } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

const EMPTY = { name: "", process_limit: "", user_limit: "", message_limit: "", ai_quota: "",
                features: "", price_monthly: 0, price_yearly: 0, overage_pct: 10, status: "ativo" };

export default function AdminPlanos() {
  const [plans, setPlans] = useState([]);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY);

  const load = () => api.get("/admin/plans").then((r) => setPlans(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);

  const openNew = () => { setEditing(null); setForm(EMPTY); setOpen(true); };
  const openEdit = (p) => {
    setEditing(p);
    setForm({ ...EMPTY, ...p, process_limit: p.process_limit ?? "", user_limit: p.user_limit ?? "",
              message_limit: p.message_limit ?? "", ai_quota: p.ai_quota ?? "" });
    setOpen(true);
  };

  const save = async () => {
    const payload = { ...form,
      process_limit: form.process_limit === "" ? null : Number(form.process_limit),
      user_limit: form.user_limit === "" ? null : Number(form.user_limit),
      message_limit: form.message_limit === "" ? null : Number(form.message_limit),
      ai_quota: form.ai_quota === "" ? null : Number(form.ai_quota),
      price_monthly: Number(form.price_monthly) || 0, price_yearly: Number(form.price_yearly) || 0,
      overage_pct: Number(form.overage_pct) || 0 };
    try {
      if (editing) await api.patch(`/admin/plans/${editing.id}`, payload);
      else await api.post("/admin/plans", payload);
      toast.success(editing ? "Plano atualizado" : "Plano criado");
      setOpen(false);
      load();
    } catch (e) { toast.error(apiError(e)); }
  };

  const numField = (key, label, tid) => (
    <div className="space-y-1.5">
      <Label className="text-zinc-400 text-xs">{label}</Label>
      <Input type="number" value={form[key]} onChange={(e) => setForm({ ...form, [key]: e.target.value })}
        data-testid={tid} placeholder="vazio = ilimitado" className="bg-[#090A0F] border-[#23283E]" />
    </div>
  );

  return (
    <div className="p-6 lg:p-8 space-y-6" data-testid="admin-planos-page">
      <div className="flex items-center justify-between fade-up">
        <div>
          <h1 className="font-display text-2xl sm:text-3xl font-semibold tracking-tight text-zinc-100">Planos</h1>
          <p className="text-sm text-zinc-500 mt-1">Modelo baseado em quantidade de processos. Preços configuráveis.</p>
        </div>
        <Button onClick={openNew} data-testid="add-plan-btn" className="brand-gradient brand-gradient-hover text-white border-0">
          <Plus size={16} className="mr-1.5" /> Novo plano
        </Button>
      </div>

      <div className="grid md:grid-cols-2 xl:grid-cols-4 gap-4 fade-up" data-testid="plans-grid">
        {plans.map((p) => (
          <div key={p.id} data-testid={`plan-card-${p.id}`}
            className="rounded-xl border border-[#23283E] bg-[#0F111A] p-5 hover:border-indigo-500/40 transition-colors duration-200">
            <div className="flex items-center justify-between">
              <h3 className="font-display font-bold text-zinc-100">{p.name}</h3>
              <Badge className={p.status === "ativo"
                ? "bg-emerald-950/60 border border-emerald-700/50 text-emerald-400"
                : "bg-zinc-800 border border-zinc-700 text-zinc-400"}>{p.status}</Badge>
            </div>
            <p className="font-display text-2xl font-bold brand-gradient-text mt-3">
              {p.process_limit ? `até ${p.process_limit}` : "ilimitado"}
            </p>
            <p className="text-xs text-zinc-500">processos</p>
            <div className="text-xs text-zinc-500 mt-3 space-y-1">
              <p>Usuários: {p.user_limit ?? "ilimitado"} • Mensagens: {p.message_limit ?? "ilimitado"}</p>
              <p>Overage permitido: {p.overage_pct}%</p>
              <p>Mensal: R$ {p.price_monthly} • Anual: R$ {p.price_yearly}</p>
            </div>
            <Button variant="outline" size="sm" onClick={() => openEdit(p)} data-testid={`edit-plan-${p.id}`}
              className="mt-4 border-[#3F476C] text-zinc-300 w-full">
              <Pencil size={13} className="mr-1.5" /> Editar
            </Button>
          </div>
        ))}
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="bg-[#0F111A] border-[#23283E] max-w-lg" data-testid="plan-dialog">
          <DialogHeader><DialogTitle className="font-display text-zinc-100">{editing ? "Editar plano" : "Novo plano"}</DialogTitle></DialogHeader>
          <div className="space-y-4 max-h-[70vh] overflow-y-auto pr-1">
            <div className="space-y-1.5">
              <Label className="text-zinc-400 text-xs">Nome</Label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value.toUpperCase() })}
                data-testid="plan-name-input" placeholder="STARTER" className="bg-[#090A0F] border-[#23283E]" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              {numField("process_limit", "Limite de processos", "plan-process-limit")}
              {numField("user_limit", "Limite de usuários", "plan-user-limit")}
              {numField("message_limit", "Limite de mensagens", "plan-message-limit")}
              {numField("ai_quota", "Franquia de IA", "plan-ai-quota")}
              {numField("price_monthly", "Preço mensal R$", "plan-price-monthly")}
              {numField("price_yearly", "Preço anual R$", "plan-price-yearly")}
              {numField("overage_pct", "Overage máximo %", "plan-overage")}
            </div>
            <div className="space-y-1.5">
              <Label className="text-zinc-400 text-xs">Recursos incluídos</Label>
              <Input value={form.features} onChange={(e) => setForm({ ...form, features: e.target.value })}
                data-testid="plan-features-input" placeholder="WhatsApp, IA de atendimento, relatórios…"
                className="bg-[#090A0F] border-[#23283E]" />
            </div>
            <Button onClick={save} data-testid="plan-save-btn" className="w-full brand-gradient brand-gradient-hover text-white border-0">
              Salvar plano
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
