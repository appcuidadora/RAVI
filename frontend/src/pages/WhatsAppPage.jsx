import { useEffect, useState } from "react";
import { api, apiError } from "@/lib/api";
import { toast } from "sonner";
import { PhoneCall, Unplug, CheckCircle2, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const META_APP_ID = process.env.REACT_APP_META_APP_ID;
const META_CONFIG_ID = process.env.REACT_APP_META_CONFIG_ID;
const META_VERSION = process.env.REACT_APP_META_GRAPH_VERSION || "v25.0";

export default function WhatsAppPage() {
  const [status, setStatus] = useState(null);
  const [sdkReady, setSdkReady] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [testToken, setTestToken] = useState("");
  const [connectingTest, setConnectingTest] = useState(false);

  const load = () => api.get("/whatsapp/status").then((r) => setStatus(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);

  useEffect(() => {
    if (!META_APP_ID) return;
    const s = document.createElement("script");
    s.src = "https://connect.facebook.net/pt_BR/sdk.js";
    s.async = true;
    s.defer = true;
    window.fbAsyncInit = () => {
      window.FB.init({ appId: META_APP_ID, cookie: true, xfbml: true, version: META_VERSION });
      setSdkReady(true);
    };
    document.body.appendChild(s);

    const onMessage = (e) => {
      if (e.origin !== "https://www.facebook.com" && e.origin !== "https://business.facebook.com") return;
      try {
        const x = JSON.parse(e.data);
        if (x.type === "WA_EMBEDDED_SIGNUP" && x.data) {
          window.__waSignup = { waba_id: x.data.waba_id, phone_number_id: x.data.phone_number_id };
        }
      } catch {}
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, []);

  const connect = () => {
    if (!window.FB) return;
    setConnecting(true);
    window.FB.login(async (r) => {
      try {
        if (!r.authResponse?.code) { setConnecting(false); return; }
        const ids = window.__waSignup || {};
        if (!ids.waba_id || !ids.phone_number_id) {
          toast.error("Não foi possível obter os dados da conta do WhatsApp. Tente novamente.");
          setConnecting(false);
          return;
        }
        await api.post("/whatsapp/connect", {
          code: r.authResponse.code, waba_id: ids.waba_id, phone_number_id: ids.phone_number_id,
        });
        toast.success("WhatsApp conectado com sucesso");
        load();
      } catch (e) {
        toast.error(apiError(e, "Falha ao conectar WhatsApp"));
      } finally {
        setConnecting(false);
      }
    }, { config_id: META_CONFIG_ID, response_type: "code", override_default_response_type: true, extras: { setup: {} } });
  };

  const connectTest = async (e) => {
    e.preventDefault();
    setConnectingTest(true);
    try {
      const { data } = await api.post("/whatsapp/connect-test", { access_token: testToken });
      toast.success(`Número de teste conectado: ${data.display_phone_number}`);
      setTestToken("");
      load();
    } catch (e2) {
      toast.error(apiError(e2, "Falha ao conectar número de teste"));
    } finally {
      setConnectingTest(false);
    }
  };

  const disconnect = async () => {
    try {
      await api.post("/whatsapp/disconnect");
      toast.success("WhatsApp desconectado");
      load();
    } catch (e) { toast.error(apiError(e)); }
  };

  const conn = status?.connection;
  const connected = conn?.status === "connected";
  const webhookUrl = `${process.env.REACT_APP_BACKEND_URL}/api/webhooks/whatsapp`;

  return (
    <div className="p-6 lg:p-8 space-y-6 max-w-3xl" data-testid="whatsapp-page">
      <div className="fade-up">
        <h1 className="font-display text-2xl sm:text-3xl font-semibold tracking-tight text-zinc-100">Conexão WhatsApp</h1>
        <p className="text-sm text-zinc-500 mt-1">
          Conexão oficial via WhatsApp Business Platform (Cloud API) da Meta. Nada de QR Code ou gambiarras.
        </p>
      </div>

      <div className="rounded-xl border border-[#23283E] bg-[#0F111A] p-6 space-y-5 fade-up" data-testid="whatsapp-status-card">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className={`w-3 h-3 rounded-full pulse-dot ${connected ? "bg-emerald-500" : "bg-zinc-600"}`} />
            <div>
              <p className="text-sm font-medium text-zinc-100" data-testid="whatsapp-status-text">
                {connected ? "WhatsApp conectado" : "WhatsApp não conectado"}
              </p>
              {connected && conn?.display_phone_number && (
                <p className="text-xs text-zinc-500" data-testid="whatsapp-number">{conn.display_phone_number}</p>
              )}
            </div>
          </div>
          {connected && <CheckCircle2 size={20} className="text-emerald-400" />}
        </div>

        {!connected && (
          <>
            {META_APP_ID ? (
              <Button onClick={connect} disabled={!sdkReady || connecting} data-testid="connect-whatsapp-btn"
                className="brand-gradient brand-gradient-hover text-white border-0">
                {connecting ? <Loader2 size={15} className="mr-2 animate-spin" /> : <PhoneCall size={15} className="mr-2" />}
                {connecting ? "Conectando…" : "Conectar WhatsApp"}
              </Button>
            ) : (
              <div className="rounded-lg border border-amber-700/40 bg-amber-950/30 p-4" data-testid="meta-pending-panel">
                <p className="text-sm text-amber-300 font-medium">Configuração da Meta App pendente</p>
                <p className="text-xs text-zinc-400 mt-1.5 leading-relaxed">
                  O adaptador está pronto: Embedded Signup, troca de código por token, inscrição da WABA e webhook.
                  Assim que as credenciais da Meta App do RAVI (App ID, App Secret e Config ID do Embedded Signup)
                  forem adicionadas ao servidor, este botão é ativado — sem nenhuma configuração técnica para o advogado.
                </p>
              </div>
            )}
            <div className="text-xs text-zinc-500 space-y-1.5">
              <p className="font-mono-code text-[10px] uppercase tracking-widest text-zinc-600">Como funciona para o advogado</p>
              <p>Conectar WhatsApp → autorização oficial da Meta → pronto. O Ravi nunca pede tokens, IDs ou senhas de tribunal.</p>
            </div>

            {status?.meta_test_available && (
              <div className="rounded-lg border border-indigo-800/40 bg-indigo-950/30 p-4 space-y-3" data-testid="test-number-panel">
                <p className="text-sm text-indigo-300 font-medium">Número de teste da Meta (+1 555 665-3479)</p>
                <p className="text-xs text-zinc-400 leading-relaxed">
                  Cole o token de acesso temporário do painel da Meta (WhatsApp → Configuração da API).
                  Ele fica salvo somente no servidor do RAVI e nunca aparece aqui novamente.
                </p>
                <form onSubmit={connectTest} className="flex gap-2">
                  <Input type="password" value={testToken} onChange={(e) => setTestToken(e.target.value)}
                    data-testid="test-token-input" placeholder="Token de acesso temporário (24h)"
                    className="bg-[#090A0F] border-[#23283E] font-mono-code text-xs" />
                  <Button type="submit" disabled={connectingTest || !testToken.trim()} data-testid="connect-test-btn"
                    className="brand-gradient brand-gradient-hover text-white border-0 shrink-0">
                    {connectingTest ? <Loader2 size={15} className="animate-spin" /> : "Ativar"}
                  </Button>
                </form>
              </div>
            )}
          </>
        )}

        {connected && (
          <Button onClick={disconnect} variant="outline" data-testid="disconnect-whatsapp-btn"
            className="border-rose-800/50 text-rose-400 hover:bg-rose-950/40">
            <Unplug size={14} className="mr-1.5" /> Desconectar
          </Button>
        )}
      </div>

      <div className="rounded-xl border border-[#23283E] bg-[#0F111A] p-6 space-y-3 fade-up" data-testid="webhook-card">
        <h3 className="font-display font-semibold text-zinc-200 text-sm">Webhook (para a Meta)</h3>
        <p className="text-xs text-zinc-500">Endpoint público que recebe as mensagens e identifica o escritório pelo phone_number_id:</p>
        <p className="font-mono-code text-xs text-indigo-300 bg-indigo-950/40 border border-indigo-800/40 rounded-lg px-3 py-2.5 break-all select-all" data-testid="webhook-url">
          {webhookUrl}
        </p>
        {conn?.phone_number_id && (
          <p className="text-[11px] text-zinc-600">Phone Number ID: <span className="font-mono-code">{conn.phone_number_id}</span></p>
        )}
      </div>
    </div>
  );
}
