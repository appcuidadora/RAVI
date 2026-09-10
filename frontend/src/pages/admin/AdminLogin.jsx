import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, apiError } from "@/lib/api";
import RaviLogo from "@/components/RaviLogo";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function AdminLogin() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await api.post("/admin/auth/login", { email, password });
      window.location.href = "/admin";
    } catch (err) {
      setError(apiError(err, "Não foi possível entrar"));
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#090A0F] grid-bg flex items-center justify-center p-6" data-testid="admin-login-page">
      <div className="w-full max-w-sm fade-up">
        <div className="flex flex-col items-center mb-8">
          <RaviLogo size={40} withName={false} />
          <h1 className="font-display font-bold text-xl text-zinc-100 mt-4">RAVI ADMIN</h1>
          <p className="text-xs font-mono-code uppercase tracking-widest text-zinc-600 mt-1">Área administrativa restrita</p>
        </div>
        <form onSubmit={submit} className="rounded-xl border border-[#23283E] bg-[#0F111A] p-6 space-y-4">
          <div className="space-y-1.5">
            <Label className="text-zinc-400 text-xs">E-mail administrativo</Label>
            <Input type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
              data-testid="admin-login-email" className="bg-[#090A0F] border-[#23283E]" />
          </div>
          <div className="space-y-1.5">
            <Label className="text-zinc-400 text-xs">Senha</Label>
            <Input type="password" required value={password} onChange={(e) => setPassword(e.target.value)}
              data-testid="admin-login-password" className="bg-[#090A0F] border-[#23283E]" />
          </div>
          {error && <p className="text-xs text-rose-400" data-testid="admin-login-error">{error}</p>}
          <Button type="submit" disabled={loading} data-testid="admin-login-submit"
            className="w-full brand-gradient brand-gradient-hover text-white border-0">
            {loading ? "Entrando…" : "Acessar RAVI ADMIN"}
          </Button>
        </form>
      </div>
    </div>
  );
}
