import { useState } from "react";
import { api, apiError } from "@/lib/api";
import RaviLogo from "@/components/RaviLogo";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function Onboarding() {
  const [form, setForm] = useState({ name: "", last_name: "", office_name: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await api.post("/auth/onboarding/complete", form);
      window.location.href = "/dashboard";
    } catch (err) {
      setError(apiError(err, "Não foi possível concluir"));
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#090A0F] grid-bg flex items-center justify-center p-6" data-testid="onboarding-page">
      <div className="w-full max-w-md fade-up">
        <div className="flex flex-col items-center mb-8">
          <RaviLogo size={44} />
          <h1 className="font-display font-bold text-2xl text-zinc-100 mt-6 tracking-tight">Vamos configurar seu escritório</h1>
          <p className="text-sm text-zinc-500 mt-2 text-center">
            Só precisamos do básico. O Ravi organiza o restante automaticamente.
          </p>
        </div>
        <form onSubmit={submit} className="rounded-xl border border-[#23283E] bg-[#0F111A] p-6 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-zinc-400 text-xs">Seu nome</Label>
              <Input required value={form.name} onChange={set("name")} data-testid="onboarding-name-input"
                placeholder="Carlos" className="bg-[#090A0F] border-[#23283E]" />
            </div>
            <div className="space-y-1.5">
              <Label className="text-zinc-400 text-xs">Sobrenome <span className="text-zinc-600">(opcional)</span></Label>
              <Input value={form.last_name} onChange={set("last_name")} data-testid="onboarding-lastname-input"
                className="bg-[#090A0F] border-[#23283E]" />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label className="text-zinc-400 text-xs">Nome do escritório</Label>
            <Input required value={form.office_name} onChange={set("office_name")} data-testid="onboarding-office-input"
              placeholder="Silva Advocacia" className="bg-[#090A0F] border-[#23283E]" />
          </div>
          {error && <p className="text-xs text-rose-400" data-testid="onboarding-error">{error}</p>}
          <Button type="submit" disabled={loading} data-testid="onboarding-submit-btn"
            className="w-full brand-gradient brand-gradient-hover text-white border-0">
            {loading ? "Configurando…" : "Concluir e entrar"}
          </Button>
          <p className="text-[11px] text-zinc-600 text-center">
            Você será o sócio administrador. A equipe pode ser convidada depois, em Equipe.
          </p>
        </form>
      </div>
    </div>
  );
}
