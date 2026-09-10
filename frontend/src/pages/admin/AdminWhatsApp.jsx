import { useEffect, useState } from "react";
import { api, apiError } from "@/lib/api";
import { toast } from "sonner";
import { Activity, KeyRound, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";

const SECRET_LABELS = {
  META_APP_ID: "Meta App ID", META_APP_SECRET: "Meta App Secret",
  META_CONFIG_ID: "Meta Config ID (Embedded Signup)",
  META_WEBHOOK_VERIFY_TOKEN: "Verify Token do webhook", META_TEST_TOKEN: "Token de teste",
};
const CONN_STATUS = {
  connected: ["Conectado", "text-emerald-400"], disconnected: ["Desconectado", "text-zinc-500"],
  token_expired: ["Token expirado", "text-amber-400"], pending: ["Pendente", "text-zinc-500"],
  error: ["Erro", "text-rose-400"],
};

export default function AdminWhatsApp() {
  const [status, setStatus] = useState(null);
  const [health, setHealth] = useState(null);
  const [healthLoading, setHealthLoading] = useState(false);
  const [form, setForm] = useState({ meta_app_id: "", meta_app_secret: "", meta_config_id: "", meta_test_token: "" });

  const load = () => api.get("/admin/meta/status").then((r) => setStatus(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);

  const saveSecrets = async (e) => {
    e.preventDefault();
    try {
      await api.post("/admin/meta/secrets", form);
      toast.success("Credenciais atualizadas");
      setForm({ meta_app_id: "", meta_app_secret: "", meta_config_id: "", meta_test_token: "" });
      load();
    } catch (err) { toast.error(apiError(err)); }
  };

  const runHealth = async () => {
    setHealthLoading(true);
    try {
      const { data } = await api.get("/admin/health");
      setHealth(data);
    } catch { toast.error("Falha ao executar health check"); }
    finally { setHealthLoading(false); }
  };

  return (
    <div className="p-6 lg:p-8 space-y-6 max-w-5xl" data-testid="admin-whatsapp-page">
      <div className="fade-up">
        <h1 className="font-display text-2xl sm:text-3xl font-semibold tracking-tight text-zinc-100">WhatsApp / Meta</h1>
        <p className="text-sm text-zinc-500 mt-1">Uma Meta App do RAVI para todos os escritórios. Secrets são write-only.</p>
      </div>

      <div className="grid md:grid-cols-2 gap-4 fade-up">
        <div className="rounded-xl border border-[#23283E] bg-[#0F111A] p-5 space-y-3" data-testid="meta-app-card">
          <div className="flex items-center justify-between">
            <h3 className="font-display font-semibold text-zinc-200 text-sm">Meta App do RAVI</h3>
            <Badge className={status?.ambiente === "produção"
              ? "bg-emerald-950/60 border border-emerald-700/50 text-emerald-400"
              : "bg-amber-950/60 border border-amber-700/50 text-amber-400"}>
              {status?.ambiente || "…"}
            </Badge>
          </div>
          {status?.app_id_masked && <p className="text-xs text-zinc-400">App ID: <span className="font-mono-code">{status.app_id_masked}</span></p>}
          <div className="space-y-2 pt-1">
            {Object.entries(SECRET_LABELS).map(([k, label]) => (
              <div key={k} className="flex items-center justify-between text-xs" data-testid={`secret-${k}`}>
                <span className="text-zinc-400">{label}</span>
                {status?.secrets?.[k]
                  ? <span className="text-emerald-400">✅ Configurado</span>
                  : <span className="text-amber-400">⚠️ Não configurado</span>}
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-[#23283E] bg-[#0F111A] p-5 space-y-3" data-testid="secrets-form-card">
          <h3 className="font-display font-semibold text-zinc-200 text-sm flex items-center gap-2">
            <KeyRound size={14} className="text-zinc-500" /> Atualizar credenciais
          </h3>
          <p className="text-[11px] text-zinc-600">Os valores nunca são exibidos novamente após salvar.</p>
          <form onSubmit={saveSecrets} className="space-y-2.5">
            {[["meta_app_id", "Meta App ID"], ["meta_app_secret", "Meta App Secret"],
              ["meta_config_id", "Config ID (Embedded Signup)"], ["meta_test_token", "Token de teste (24h)"]].map(([k, label]) => (
              <div key={k} className="space-y-1">
                <Label className="text-zinc-500 text-[11px]">{label}</Label>
                <Input type="password" value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })}
                  data-testid={`secret-input-${k}`} placeholder="••••••••" className="bg-[#090A0F] border-[#23283E] h-8 text-xs font-mono-code" />
              </div>
            ))}
            <Button type="submit" data-testid="secrets-save-btn" className="w-full brand-gradient brand-gradient-hover text-white border-0">
              Atualizar
            </Button>
          </form>
          {status?.test_token_meta?.updated_at && (
            <p className="text-[11px] text-zinc-600">
              Token de teste: atualizado em {new Date(status.test_token_meta.updated_at).toLocaleString("pt-BR")}
              {status.test_token_meta.status === "invalid" && <span className="text-rose-400 ml-1">— 🔴 Token inválido</span>}
            </p>
          )}
        </div>
      </div>

      <div className="rounded-xl border border-[#23283E] bg-[#0F111A] p-5 fade-up" data-testid="health-card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-display font-semibold text-zinc-200 text-sm">Health Check</h3>
          <Button onClick={runHealth} disabled={healthLoading} size="sm" data-testid="run-health-btn"
            variant="outline" className="border-[#3F476C] text-zinc-300">
            {healthLoading ? <Loader2 size={13} className="mr-1.5 animate-spin" /> : <Activity size={13} className="mr-1.5" />}
            Verificar agora
          </Button>
        </div>
        {!health && <p className="text-xs text-zinc-600">Execute uma verificação para ver o status de cada componente.</p>}
        {health && (
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2.5" data-testid="health-results">
            {Object.entries(health.checks).map(([k, c]) => (
              <div key={k} className="rounded-lg border border-[#23283E] bg-[#090A0F] px-3 py-2.5" data-testid={`health-${k}`}>
                <p className="text-xs text-zinc-300">{c.label}</p>
                <p className={`text-[11px] mt-0.5 ${c.ok ? "text-emerald-400" : "text-rose-400"}`}>{c.ok ? "🟢 Online" : "🔴 Falha"}</p>
                {(c.ultimo_evento || c.ultima_mensagem || c.ultima_resposta) && (
                  <p className="text-[10px] text-zinc-600 mt-0.5">
                    {new Date(c.ultimo_evento || c.ultima_mensagem || c.ultima_resposta).toLocaleString("pt-BR")}
                  </p>
                )}
              </div>
            ))}
            <p className="col-span-full text-[10px] text-zinc-600">Verificado em {new Date(health.verificado_em).toLocaleString("pt-BR")}</p>
          </div>
        )}
      </div>

      <div className="rounded-xl border border-[#23283E] bg-[#0F111A] p-5 fade-up" data-testid="connections-card">
        <h3 className="font-display font-semibold text-zinc-200 text-sm mb-4">Conexões por escritório</h3>
        {(status?.connections || []).length === 0 && <p className="text-xs text-zinc-600">Nenhuma conexão ainda.</p>}
        <div className="space-y-2">
          {(status?.connections || []).map((c) => (
            <div key={c.id} className="flex items-center justify-between rounded-lg border border-[#23283E] bg-[#090A0F] px-3.5 py-2.5" data-testid={`conn-${c.id}`}>
              <div>
                <p className="text-sm text-zinc-200">{c.office_name}</p>
                <p className="text-xs text-zinc-500">{c.display_phone_number || "—"}</p>
              </div>
              <span className={`text-xs ${(CONN_STATUS[c.status] || CONN_STATUS.pending)[1]}`}>
                {(CONN_STATUS[c.status] || CONN_STATUS.pending)[0]}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
