import { useEffect, useState } from "react";
import { api, apiError } from "@/lib/api";
import { toast } from "sonner";
import { Plus, Pencil, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";

const EMPTY = { name: "", phone: "", email: "", notes: "" };

export default function Clientes() {
  const [clients, setClients] = useState([]);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [search, setSearch] = useState("");

  const load = () => api.get("/clients").then((r) => setClients(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);

  const openNew = () => { setEditing(null); setForm(EMPTY); setOpen(true); };
  const openEdit = (c) => { setEditing(c); setForm({ name: c.name, phone: c.phone, email: c.email || "", notes: c.notes || "" }); setOpen(true); };

  const save = async (e) => {
    e.preventDefault();
    try {
      if (editing) {
        await api.patch(`/clients/${editing.id}`, form);
        toast.success("Cliente atualizado");
      } else {
        await api.post("/clients", form);
        toast.success("Cliente cadastrado. O Ravi já consegue identificá-lo no WhatsApp.");
      }
      setOpen(false);
      load();
    } catch (err) {
      toast.error(apiError(err));
    }
  };

  const remove = async (c) => {
    try {
      await api.delete(`/clients/${c.id}`);
      toast.success("Cliente removido");
      load();
    } catch (err) {
      toast.error(apiError(err));
    }
  };

  const filtered = clients.filter((c) => c.name.toLowerCase().includes(search.toLowerCase()) || c.phone?.includes(search));

  return (
    <div className="p-6 lg:p-8 space-y-6" data-testid="clientes-page">
      <div className="flex items-center justify-between fade-up">
        <div>
          <h1 className="font-display text-2xl sm:text-3xl font-semibold tracking-tight text-zinc-100">Clientes</h1>
          <p className="text-sm text-zinc-500 mt-1">Cadastre o mínimo. O Ravi organiza o restante.</p>
        </div>
        <Button onClick={openNew} data-testid="add-client-btn" className="brand-gradient brand-gradient-hover text-white border-0">
          <Plus size={16} className="mr-1.5" /> Novo cliente
        </Button>
      </div>

      <Input placeholder="Buscar por nome ou WhatsApp…" value={search} onChange={(e) => setSearch(e.target.value)}
        data-testid="clients-search-input" className="max-w-sm bg-[#0F111A] border-[#23283E]" />

      <div className="rounded-xl border border-[#23283E] bg-[#0F111A] overflow-hidden fade-up" data-testid="clients-table">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[#23283E] text-left">
              <th className="px-5 py-3 font-mono-code text-[10px] uppercase tracking-widest text-zinc-500">Cliente</th>
              <th className="px-5 py-3 font-mono-code text-[10px] uppercase tracking-widest text-zinc-500 hidden md:table-cell">WhatsApp</th>
              <th className="px-5 py-3 font-mono-code text-[10px] uppercase tracking-widest text-zinc-500 hidden lg:table-cell">Processos</th>
              <th className="px-5 py-3 font-mono-code text-[10px] uppercase tracking-widest text-zinc-500 hidden sm:table-cell">Status</th>
              <th className="px-5 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 && (
              <tr><td colSpan={5} className="px-5 py-10 text-center text-zinc-500" data-testid="clients-empty">
                Nenhum cliente cadastrado ainda.
              </td></tr>
            )}
            {filtered.map((c) => (
              <tr key={c.id} className="border-b border-[#23283E]/50 hover:bg-[#161925]/50 transition-colors duration-150" data-testid={`client-row-${c.id}`}>
                <td className="px-5 py-3.5">
                  <p className="font-medium text-zinc-200">{c.name}</p>
                  {c.email && <p className="text-xs text-zinc-500">{c.email}</p>}
                </td>
                <td className="px-5 py-3.5 text-zinc-400 hidden md:table-cell">{c.phone}</td>
                <td className="px-5 py-3.5 hidden lg:table-cell">
                  {(c.processes || []).length === 0 ? <span className="text-zinc-600 text-xs">—</span> :
                    c.processes.map((p) => (
                      <Badge key={p.id} variant="outline" className="mr-1 border-[#3F476C] text-indigo-300 font-mono-code text-[10px]">
                        {p.numero_formatado || p.number}
                      </Badge>
                    ))}
                </td>
                <td className="px-5 py-3.5 hidden sm:table-cell">
                  <Badge className="bg-emerald-950/60 border border-emerald-700/50 text-emerald-400">{c.status}</Badge>
                </td>
                <td className="px-5 py-3.5 text-right">
                  <button onClick={() => openEdit(c)} data-testid={`edit-client-${c.id}`} className="text-zinc-500 hover:text-zinc-200 mr-3 transition-colors duration-150"><Pencil size={15} /></button>
                  <button onClick={() => remove(c)} data-testid={`delete-client-${c.id}`} className="text-zinc-500 hover:text-rose-400 transition-colors duration-150"><Trash2 size={15} /></button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="bg-[#0F111A] border-[#23283E]" data-testid="client-dialog">
          <DialogHeader>
            <DialogTitle className="font-display text-zinc-100">{editing ? "Editar cliente" : "Novo cliente"}</DialogTitle>
          </DialogHeader>
          <form onSubmit={save} className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-zinc-400 text-xs">Nome</Label>
              <Input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                data-testid="client-name-input" placeholder="Carlos Eduardo" className="bg-[#090A0F] border-[#23283E]" />
            </div>
            <div className="space-y-1.5">
              <Label className="text-zinc-400 text-xs">WhatsApp</Label>
              <Input required value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })}
                data-testid="client-phone-input" placeholder="+55 11 98765-4321" className="bg-[#090A0F] border-[#23283E]" />
              <p className="text-[11px] text-zinc-600">Aceita qualquer formato — o Ravi normaliza automaticamente.</p>
            </div>
            <div className="space-y-1.5">
              <Label className="text-zinc-400 text-xs">E-mail <span className="text-zinc-600">(opcional)</span></Label>
              <Input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })}
                data-testid="client-email-input" className="bg-[#090A0F] border-[#23283E]" />
            </div>
            <Button type="submit" data-testid="client-save-btn" className="w-full brand-gradient brand-gradient-hover text-white border-0">
              {editing ? "Salvar alterações" : "Cadastrar cliente"}
            </Button>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
