import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { api, apiError } from "@/lib/api";
import RaviLogo from "@/components/RaviLogo";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function Register() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", last_name: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await api.post("/auth/register", form);
      window.location.href = "/onboarding";
    } catch (err) {
      setError(apiError(err, "Não foi possível criar a conta"));
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#090A0F] grid-bg flex items-center justify-center p-6" data-testid="register-page">
      <div className="w-full max-w-sm fade-up">
        <div className="flex flex-col items-center mb-8">
          <RaviLogo size={44} />
          <p className="text-sm text-zinc-500 mt-4 text-center">Crie a conta do seu escritório em menos de 1 minuto.</p>
        </div>
        <form onSubmit={submit} className="rounded-xl border border-[#23283E] bg-[#0F111A] p-6 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-zinc-400 text-xs">Nome</Label>
              <Input required value={form.name} onChange={set("name")} data-testid="register-name-input"
                placeholder="Carlos" className="bg-[#090A0F] border-[#23283E]" />
            </div>
            <div className="space-y-1.5">
              <Label className="text-zinc-400 text-xs">Sobrenome <span className="text-zinc-600">(opcional)</span></Label>
              <Input value={form.last_name} onChange={set("last_name")} data-testid="register-lastname-input"
                className="bg-[#090A0F] border-[#23283E]" />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label className="text-zinc-400 text-xs">E-mail</Label>
            <Input type="email" required value={form.email} onChange={set("email")} data-testid="register-email-input"
              placeholder="voce@escritorio.com" className="bg-[#090A0F] border-[#23283E]" />
          </div>
          <div className="space-y-1.5">
            <Label className="text-zinc-400 text-xs">Senha</Label>
            <Input type="password" required minLength={6} value={form.password} onChange={set("password")}
              data-testid="register-password-input" placeholder="mínimo 6 caracteres"
              className="bg-[#090A0F] border-[#23283E]" />
          </div>
          {error && <p className="text-xs text-rose-400" data-testid="register-error">{error}</p>}
          <Button type="submit" disabled={loading} data-testid="register-submit-btn"
            className="w-full brand-gradient brand-gradient-hover text-white border-0">
            {loading ? "Criando…" : "Criar conta"}
          </Button>
          <p className="text-xs text-zinc-500 text-center">
            Já tem conta?{" "}
            <Link to="/login" data-testid="login-link" className="text-indigo-400 hover:text-indigo-300">Entrar</Link>
          </p>
        </form>
      </div>
    </div>
  );
}
