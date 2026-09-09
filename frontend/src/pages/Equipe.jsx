import { useEffect, useState } from "react";
import { api, apiError } from "@/lib/api";
import { toast } from "sonner";
import { Plus, UserCog, Power } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const MODULE_LABELS = {
  dashboard: "Dashboard", clientes: "Clientes", processos: "Processos", conversas: "Conversas/WhatsApp",
  alertas: "Alertas", equipe: "Equipe", configuracoes: "Configurações", whatsapp: "WhatsApp",
  documentos: "Documentos", ia: "IA", financeiro: "Financeiro (futuro)",
};

export default function Equipe() {
  const [data, setData] = useState({ members: [], roles: {}, modules: [] });
  const [addOpen, setAddOpen] = useState(false);
  const [editMember, setEditMember] = useState(null);
  const [form, setForm] = useState({ name: "", email: "", role: "SECRETARIA_ATENDIMENTO" });
  const [editPerms, setEditPerms] = useState({});
  const [editRole, setEditRole] = useState("");
  const [tempPassword, setTempPassword] = useState("");

  const load = () => api.get("/team").then((r) => setData(r.data)).catch((e) => toast.error(apiError(e)));
  useEffect(() => { load(); }, []);

  const add = async (e) => {
    e.preventDefault();
    try {
      const { data: m } = await api.post("/team", form);
      setTempPassword(m.temp_password);
      toast.success("Membro adicionado");
      load();
    } catch (err) { toast.error(apiError(err)); }
  };

  const openEdit = (m) => {
    setEditMember(m);
    setEditPerms({ ...(m.permissions || {}) });
    setEditRole(m.role);
  };

  const saveEdit = async () => {
    try {
      await api.patch(`/team/${editMember.id}`, { role: editRole, permissions: editPerms });
      toast.success("Permissões atualizadas");
      setEditMember(null);
      load();
    } catch (err) { toast.error(apiError(err)); }
  };

  const toggle = async (m) => {
    try {
      const { data: r } = await api.post(`/team/${m.id}/toggle-active`);
      toast.success(r.active ? "Membro reativado" : "Membro desativado");
      load();
    } catch (err) { toast.error(apiError(err)); }
  };

  return (
    <div className="p-6 lg:p-8 space-y-6" data-testid="equipe-page">
      <div className="flex items-center justify-between fade-up">
        <div>
          <h1 className="font-display text-2xl sm:text-3xl font-semibold tracking-tight text-zinc-100">Equipe</h1>
          <p className="text-sm text-zinc-500 mt-1">Controle quem acessa o quê no seu escritório.</p>
        </div>
        <Button onClick={() => { setAddOpen(true); setTempPassword(""); setForm({ name: "", email: "", role: "SECRETARIA_ATENDIMENTO" }); }}
          data-testid="add-member-btn" className="brand-gradient brand-gradient-hover text-white border-0">
          <Plus size={16} className="mr-1.5" /> Adicionar membro
        </Button>
      </div>

      <div className="rounded-xl border border-[#23283E] bg-[#0F111A] overflow-hidden fade-up" data-testid="team-table">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[#23283E] text-left">
              <th className="px-5 py-3 font-mono-code text-[10px] uppercase tracking-widest text-zinc-500">Membro</th>
              <th className="px-5 py-3 font-mono-code text-[10px] uppercase tracking-widest text-zinc-500 hidden sm:table-cell">Função</th>
              <th className="px-5 py-3 font-mono-code text-[10px] uppercase tracking-widest text-zinc-500">Status</th>
              <th className="px-5 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {data.members.map((m) => (
              <tr key={m.id} className="border-b border-[#23283E]/50 hover:bg-[#161925]/50 transition-colors duration-150" data-testid={`member-row-${m.id}`}>
                <td className="px-5 py-3.5">
                  <p className="font-medium text-zinc-200">{m.name} {m.last_name}</p>
                  <p className="text-xs text-zinc-500">{m.email}</p>
                </td>
                <td className="px-5 py-3.5 hidden sm:table-cell">
                  <Badge variant="outline" className="border-[#3F476C] text-indigo-300">{m.role_label}</Badge>
                </td>
                <td className="px-5 py-3.5">
                  {m.active
                    ? <Badge className="bg-emerald-950/60 border border-emerald-700/50 text-emerald-400">ativo</Badge>
                    : <Badge className="bg-zinc-800 border border-zinc-700 text-zinc-400">desativado</Badge>}
                </td>
                <td className="px-5 py-3.5 text-right">
                  <button onClick={() => openEdit(m)} data-testid={`edit-member-${m.id}`}
                    className="text-zinc-500 hover:text-zinc-200 mr-3 transition-colors duration-150" title="Permissões">
                    <UserCog size={16} />
                  </button>
                  <button onClick={() => toggle(m)} data-testid={`toggle-member-${m.id}`}
                    className={`transition-colors duration-150 ${m.active ? "text-zinc-500 hover:text-rose-400" : "text-zinc-500 hover:text-emerald-400"}`}
                    title={m.active ? "Desativar" : "Reativar"}>
                    <Power size={16} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent className="bg-[#0F111A] border-[#23283E]" data-testid="add-member-dialog">
          <DialogHeader>
            <DialogTitle className="font-display text-zinc-100">Adicionar membro</DialogTitle>
          </DialogHeader>
          {tempPassword ? (
            <div className="space-y-3" data-testid="member-created-panel">
              <p className="text-sm text-zinc-300">Membro criado. Compartilhe a senha temporária:</p>
              <p className="font-mono-code text-sm text-indigo-300 bg-indigo-950/40 border border-indigo-800/40 rounded-lg px-3 py-2.5 select-all">
                {tempPassword}
              </p>
              <p className="text-[11px] text-zinc-500">Ela não será exibida novamente. O membro pode trocá-la em "Esqueci a senha".</p>
              <Button onClick={() => setAddOpen(false)} data-testid="member-created-close" className="w-full brand-gradient text-white border-0">Fechar</Button>
            </div>
          ) : (
            <form onSubmit={add} className="space-y-4">
              <div className="space-y-1.5">
                <Label className="text-zinc-400 text-xs">Nome</Label>
                <Input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                  data-testid="member-name-input" className="bg-[#090A0F] border-[#23283E]" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-zinc-400 text-xs">E-mail</Label>
                <Input type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })}
                  data-testid="member-email-input" className="bg-[#090A0F] border-[#23283E]" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-zinc-400 text-xs">Função</Label>
                <Select value={form.role} onValueChange={(v) => setForm({ ...form, role: v })}>
                  <SelectTrigger data-testid="member-role-select" className="bg-[#090A0F] border-[#23283E]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-[#0F111A] border-[#23283E]">
                    {Object.entries(data.roles).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <Button type="submit" data-testid="member-save-btn" className="w-full brand-gradient brand-gradient-hover text-white border-0">
                Adicionar
              </Button>
            </form>
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={!!editMember} onOpenChange={() => setEditMember(null)}>
        <DialogContent className="bg-[#0F111A] border-[#23283E] max-w-md" data-testid="edit-member-dialog">
          <DialogHeader>
            <DialogTitle className="font-display text-zinc-100">Permissões — {editMember?.name}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-zinc-400 text-xs">Função</Label>
              <Select value={editRole} onValueChange={setEditRole}>
                <SelectTrigger data-testid="edit-role-select" className="bg-[#090A0F] border-[#23283E]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-[#0F111A] border-[#23283E]">
                  {Object.entries(data.roles).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-1 gap-2.5 pt-2">
              {(data.modules || []).map((mod) => (
                <div key={mod} className="flex items-center justify-between rounded-lg border border-[#23283E] bg-[#090A0F] px-3.5 py-2.5">
                  <span className="text-sm text-zinc-300">{MODULE_LABELS[mod] || mod}</span>
                  <Switch checked={!!editPerms[mod]} disabled={editMember?.role === "SOCIO_ADMIN" && editRole === "SOCIO_ADMIN"}
                    onCheckedChange={(v) => setEditPerms({ ...editPerms, [mod]: v })}
                    data-testid={`perm-switch-${mod}`} />
                </div>
              ))}
            </div>
            <Button onClick={saveEdit} data-testid="save-permissions-btn" className="w-full brand-gradient brand-gradient-hover text-white border-0">
              Salvar permissões
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
