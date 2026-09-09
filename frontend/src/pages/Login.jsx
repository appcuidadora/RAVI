import { useState } from "react";
import { useNavigate, useLocation, Link } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { apiError } from "@/lib/api";
import RaviLogo from "@/components/RaviLogo";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password);
      const dest = location.state?.from && location.state.from !== "/login" ? location.state.from : "/dashboard";
      navigate(dest, { replace: true });
    } catch (err) {
      setError(apiError(err, "Não foi possível entrar"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#090A0F] grid-bg flex items-center justify-center p-6" data-testid="login-page">
      <div className="w-full max-w-sm fade-up">
        <div className="flex flex-col items-center mb-8">
          <RaviLogo size={44} />
          <p className="text-sm text-zinc-500 mt-4 text-center">
            Seu cliente pergunta. O Ravi responde.<br />Você só entra quando realmente precisa.
          </p>
        </div>
        <form onSubmit={submit} className="rounded-xl border border-[#23283E] bg-[#0F111A] p-6 space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="email" className="text-zinc-400 text-xs">E-mail</Label>
            <Input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
              data-testid="login-email-input" placeholder="voce@escritorio.com"
              className="bg-[#090A0F] border-[#23283E]" />
          </div>
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <Label htmlFor="password" className="text-zinc-400 text-xs">Senha</Label>
              <Link to="/esqueci-senha" data-testid="forgot-password-link" className="text-xs text-indigo-400 hover:text-indigo-300">
                Esqueci a senha
              </Link>
            </div>
            <Input id="password" type="password" required value={password} onChange={(e) => setPassword(e.target.value)}
              data-testid="login-password-input" placeholder="••••••••"
              className="bg-[#090A0F] border-[#23283E]" />
          </div>
          {error && <p className="text-xs text-rose-400" data-testid="login-error">{error}</p>}
          <Button type="submit" disabled={loading} data-testid="login-submit-btn"
            className="w-full brand-gradient brand-gradient-hover text-white border-0 transition-colors duration-200">
            {loading ? "Entrando…" : "Entrar"}
          </Button>
          <p className="text-xs text-zinc-500 text-center">
            Primeiro acesso?{" "}
            <Link to="/cadastro" data-testid="register-link" className="text-indigo-400 hover:text-indigo-300">
              Criar conta do escritório
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
}
