import { useEffect, useState } from "react";
import { api, apiError } from "@/lib/api";
import { toast } from "sonner";
import { Plus, Power } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const ROLE_LABELS = {
  SUPER_ADMIN: "Super Admin", ADMIN_FINANCEIRO: "Financeiro", ADMIN_SUPORTE: "Suporte",
  ADMIN_OPERACOES: "Operações", ADMIN_COMERCIAL: "Comercial", ADMIN_TECNOLOGIA: "Tecnologia",
  ANALISTA: "Analista",
};

export default function AdminUsuarios() {
  const [data, setData] = useState({ users: [], roles: [] });
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", email: "", role: "ANALISTA" });
  const [tempPassword, setTempPassword] = useState("");
  const [forbidden, setForbidden] = useState(false);

  const load = () => api.get("/admin/users").then((r) => { setData(r.data); setForbidden(false); })
    .catch((e) => { if (e.response?.status === 403) setForbidden(true); });
  useEffect(() => { load(); }, []);

  const add = async (e) => {
    e.preventDefault();
    try {
      const { data: u } = await api.post("/admin/users", form);
      setTempPassword(u.temp_password);
      toast.success("Administrador criado");
      load();
    } catch (err) { toast.error(apiError(err)); }
  };

  const toggle = async (u) => {
    try {
      const { data: r } = await api.post(`/admin/users/${u.id}/toggle-active`);
      toast.success(r.active ? "Administrador reativado" : "Administrador desativado");
      load();
    } catch (err) { toast.error(apiError(err)); }
  };

  const setRole = async (u, role) => {
    try {
      await api.patch(`/admin/users/${u.id}`, { role });
      toast.success("Perfil atualizado");
      load();
    } catch (err) { toast.error(apiError(err)); }
  };

  if (forbidden) {
    return (
      <div className="p-8" data-testid="admin-users-forbidden">
        <p className="text-sm text-amber-400">Apenas SUPER_ADMIN pode gerenciar administradores.</p>
      </div>
    );
  }

  return (
    <div className="p-6 lg:p-8 space-y-6" data-testid="admin-usuarios-page">
      <div className="flex items-center justify-between fade-up">
        <div>
          <h1 className="font-display text-2xl sm:text-3xl font-semibold tracking-tight text-zinc-100">Usuários administrativos</h1>
          <p className="text-sm text-zinc-500 mt-1">Equipe interna RAVI. Perfis por departamento, prontos para especialização futura.</p>
        </div>
        <Button onClick={() => { setOpen(true); setTempPassword(""); setForm({ name: "", email: "", role: "ANALISTA" }); }}
          data-testid="add-admin-user-btn" className="brand-gradient brand-gradient-hover text-white border-0">
          <Plus size={16} className="mr-1.5" /> Novo administrador
        </Button>
      </div>

      <div className="rounded-xl border border-[#23283E] bg-[#0F111A] overflow-hidden fade-up" data-testid="admin-users-table">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[#23283E] text-left">
              <th className="px-5 py-3 font-mono-code text-[10px] uppercase tracking-widest text-zinc-500">Nome</th>
              <th className="px-5 py-3 font-mono-code text-[10px] uppercase tracking-widest text-zinc-500 hidden sm:table-cell">Perfil</th>
              <th className="px-5 py-3 font-mono-code text-[10px] uppercase tracking-widest text-zinc-500">Status</th>
              <th className="px-5 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {data.users.map((u) => (
              <tr key={u.id} className="border-b border-[#23283E]/50 hover:bg-[#161925]/50 transition-colors duration-150" data-testid={`admin-user-row-${u.id}`}>
                <td className="px-5 py-3.5">
                  <p className="font-medium text-zinc-200">{u.name}</p>
                  <p className="text-xs text-zinc-500">{u.email}</p>
                </td>
                <td className="px-5 py-3.5 hidden sm:table-cell">
                  <Select value={u.role} onValueChange={(v) => setRole(u, v)}>
                    <SelectTrigger data-testid={`admin-user-role-${u.id}`} className="w-44 bg-[#090A0F] border-[#23283E] h-8 text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-[#0F111A] border-[#23283E]">
                      {data.roles.map((r) => <SelectItem key={r} value={r}>{ROLE_LABELS[r] || r}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </td>
                <td className="px-5 py-3.5">
                  {u.active
                    ? <Badge className="bg-emerald-950/60 border border-emerald-700/50 text-emerald-400">ativo</Badge>
                    : <Badge className="bg-zinc-800 border border-zinc-700 text-zinc-400">desativado</Badge>}
                </td>
                <td className="px-5 py-3.5 text-right">
                  <button onClick={() => toggle(u)} data-testid={`toggle-admin-user-${u.id}`}
                    title={u.active ? "Desativar" : "Reativar"}
                    className={`transition-colors duration-150 ${u.active ? "text-zinc-500 hover:text-rose-400" : "text-zinc-500 hover:text-emerald-400"}`}>
                    <Power size={15} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="bg-[#0F111A] border-[#23283E]" data-testid="admin-user-dialog">
          <DialogHeader>
            <DialogTitle className="font-display text-zinc-100">Novo administrador</DialogTitle>
            <DialogDescription className="text-zinc-500 text-xs">Acesso ao RAVI ADMIN. Senha temporária exibida uma única vez.</DialogDescription>
          </DialogHeader>
          {tempPassword ? (
            <div className="space-y-3" data-testid="admin-user-created-panel">
              <p className="text-sm text-zinc-300">Administrador criado. Senha temporária:</p>
              <p className="font-mono-code text-sm text-indigo-300 bg-indigo-950/40 border border-indigo-800/40 rounded-lg px-3 py-2.5 select-all">{tempPassword}</p>
              <p className="text-[11px] text-zinc-500">Ela não será exibida novamente.</p>
              <Button onClick={() => setOpen(false)} data-testid="admin-user-created-close" className="w-full brand-gradient text-white border-0">Fechar</Button>
            </div>
          ) : (
            <form onSubmit={add} className="space-y-4">
              <div className="space-y-1.5">
                <Label className="text-zinc-400 text-xs">Nome</Label>
                <Input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                  data-testid="admin-user-name" className="bg-[#090A0F] border-[#23283E]" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-zinc-400 text-xs">E-mail</Label>
                <Input type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })}
                  data-testid="admin-user-email" className="bg-[#090A0F] border-[#23283E]" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-zinc-400 text-xs">Perfil</Label>
                <Select value={form.role} onValueChange={(v) => setForm({ ...form, role: v })}>
                  <SelectTrigger data-testid="admin-user-role-select" className="bg-[#090A0F] border-[#23283E]"><SelectValue /></SelectTrigger>
                  <SelectContent className="bg-[#0F111A] border-[#23283E]">
                    {data.roles.map((r) => <SelectItem key={r} value={r}>{ROLE_LABELS[r] || r}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <Button type="submit" data-testid="admin-user-save" className="w-full brand-gradient brand-gradient-hover text-white border-0">Criar administrador</Button>
            </form>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
