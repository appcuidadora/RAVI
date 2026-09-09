import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, apiError } from "@/lib/api";
import RaviLogo from "@/components/RaviLogo";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function ResetPassword() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await api.post("/auth/reset-password", { token: params.get("token") || "", password });
      navigate("/login");
    } catch (err) {
      setError(apiError(err, "Link inválido ou expirado"));
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#090A0F] grid-bg flex items-center justify-center p-6" data-testid="reset-password-page">
      <div className="w-full max-w-sm fade-up">
        <div className="flex justify-center mb-8"><RaviLogo size={40} /></div>
        <form onSubmit={submit} className="rounded-xl border border-[#23283E] bg-[#0F111A] p-6 space-y-4">
          <h1 className="font-display font-semibold text-lg text-zinc-100">Nova senha</h1>
          <div className="space-y-1.5">
            <Label className="text-zinc-400 text-xs">Senha</Label>
            <Input type="password" required minLength={6} value={password} onChange={(e) => setPassword(e.target.value)}
              data-testid="reset-password-input" className="bg-[#090A0F] border-[#23283E]" />
          </div>
          {error && <p className="text-xs text-rose-400" data-testid="reset-error">{error}</p>}
          <Button type="submit" disabled={loading} data-testid="reset-submit-btn"
            className="w-full brand-gradient brand-gradient-hover text-white border-0">
            {loading ? "Salvando…" : "Redefinir senha"}
          </Button>
          <Link to="/login" data-testid="back-to-login-link" className="block text-xs text-indigo-400 hover:text-indigo-300 text-center">
            Voltar para o login
          </Link>
        </form>
      </div>
    </div>
  );
}
