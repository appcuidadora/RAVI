import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import RaviLogo from "@/components/RaviLogo";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try { await api.post("/auth/forgot-password", { email }); } catch {}
    setSent(true);
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-[#090A0F] grid-bg flex items-center justify-center p-6" data-testid="forgot-password-page">
      <div className="w-full max-w-sm fade-up">
        <div className="flex justify-center mb-8"><RaviLogo size={40} /></div>
        <div className="rounded-xl border border-[#23283E] bg-[#0F111A] p-6 space-y-4">
          {sent ? (
            <p className="text-sm text-zinc-300" data-testid="forgot-password-confirmation">
              Se este e-mail estiver cadastrado, enviamos um link para redefinir sua senha. Verifique sua caixa de entrada.
            </p>
          ) : (
            <form onSubmit={submit} className="space-y-4">
              <h1 className="font-display font-semibold text-lg text-zinc-100">Redefinir senha</h1>
              <div className="space-y-1.5">
                <Label className="text-zinc-400 text-xs">E-mail cadastrado</Label>
                <Input type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
                  data-testid="forgot-email-input" className="bg-[#090A0F] border-[#23283E]" />
              </div>
              <Button type="submit" disabled={loading} data-testid="forgot-submit-btn"
                className="w-full brand-gradient brand-gradient-hover text-white border-0">
                {loading ? "Enviando…" : "Enviar link"}
              </Button>
            </form>
          )}
          <Link to="/login" data-testid="back-to-login-link" className="block text-xs text-indigo-400 hover:text-indigo-300 text-center">
            Voltar para o login
          </Link>
        </div>
      </div>
    </div>
  );
}
