import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, apiError } from "@/lib/api";
import { toast } from "sonner";
import QRCode from "react-qr-code";
import { PhoneCall, Unplug, CheckCircle2, Loader2, QrCode, Settings, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";

const FRIENDLY_ERRORS = {
  invalid_state: "Precisamos concluir uma etapa de autorização da Meta. Tente novamente.",
  missing_params: "Não foi possível concluir a autorização da Meta. Tente novamente.",
  connect_failed: "Não foi possível conectar seu WhatsApp agora. Verifique o número e tente novamente.",
};

function maskPhone(v) {
  const d = v.replace(/\D/g, "").slice(0, 11);
  if (d.length <= 2) return d ? `(${d}` : "";
  if (d.length <= 6) return `(${d.slice(0, 2)}) ${d.slice(2)}`;
  if (d.length <= 10) return `(${d.slice(0, 2)}) ${d.slice(2, 6)}-${d.slice(6)}`;
  return `(${d.slice(0, 2)}) ${d.slice(2, 7)}-${d.slice(7)}`;
}

export default function WhatsAppPage() {
  const [params, setParams] = useSearchParams();
  const [status, setStatus] = useState(null);
  const [phone, setPhone] = useState("");
  const [connecting, setConnecting] = useState(false);
  const [qrUrl, setQrUrl] = useState("");
  const [testing, setTesting] = useState(false);
  const [testOk, setTestOk] = useState(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [testToken, setTestToken] = useState("");
  const [connectingTest, setConnectingTest] = useState(false);
  const [usage, setUsage] = useState(null);

  const load = () => {
    api.get("/whatsapp/status").then((r) => setStatus(r.data)).catch(() => {});
    api.get("/whatsapp/usage").then((r) => setUsage(r.data)).catch(() => {});
  };
  useEffect(() => { load(); }, []); // eslint-disable-line

  useEffect(() => {
    load();
    if (params.get("connected")) {
      toast.success("WhatsApp conectado com sucesso");
      setParams({}, { replace: true });
    } else if (params.get("error")) {
      toast.error(FRIENDLY_ERRORS[params.get("error")] || FRIENDLY_ERRORS.connect_failed);
      setParams({}, { replace: true });
    }
  }, []); // eslint-disable-line

  const startConnect = async (forQr = false) => {
    const digits = phone.replace(/\D/g, "");
    if (digits.length < 10 || digits.length > 11) {
      toast.error("Verifique o número informado e tente novamente.");
      return;
    }
    setConnecting(true);
    try {
      const { data } = await api.post("/whatsapp/connect/start", { phone });
      if (forQr) {
        setQrUrl(data.url);
      } else {
        window.location.href = data.url;
      }
    } catch (e) {
      toast.error(apiError(e, FRIENDLY_ERRORS.connect_failed));
    } finally {
      setConnecting(false);
    }
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
      toast.error(apiError(e2, "Não foi possível conectar agora. Tente novamente."));
    } finally {
      setConnectingTest(false);
    }
  };

  const testConnection = async () => {
    setTesting(true);
    setTestOk(null);
    try {
      const { data } = await api.post("/whatsapp/test-connection");
      setTestOk(data);
      toast.success("Conexão validada");
    } catch (e) {
      setTestOk(false);
      toast.error(apiError(e, "Não conseguimos validar a conexão agora. Tente novamente."));
    } finally {
      setTesting(false);
    }
  };

  const disconnect = async () => {
    try {
      await api.post("/whatsapp/disconnect");
      toast.success("WhatsApp desconectado. Seu histórico de clientes e conversas foi mantido.");
      setTestOk(null);
      load();
    } catch (e) {
      toast.error(apiError(e, "Não foi possível desconectar agora. Tente novamente."));
    }
  };

  const conn = status?.connection;
  const connected = conn?.status === "connected";

  return (
    <div className="p-6 lg:p-8 space-y-6 max-w-2xl" data-testid="whatsapp-page">
      <div className="fade-up">
        <h1 className="font-display text-2xl sm:text-3xl font-semibold tracking-tight text-zinc-100">
          Conecte o WhatsApp do seu escritório
        </h1>
        <p className="text-sm text-zinc-500 mt-1">
          Informe o número que sua equipe utiliza para atender seus clientes pelo WhatsApp.
        </p>
      </div>

      {connected ? (
        <div className="rounded-xl border border-emerald-700/40 bg-emerald-950/20 p-6 space-y-5 fade-up" data-testid="whatsapp-connected-card">
          <div className="flex items-center gap-3">
            <span className="w-10 h-10 rounded-full bg-emerald-500/15 flex items-center justify-center shrink-0">
              <CheckCircle2 size={20} className="text-emerald-400" />
            </span>
            <div>
              <p className="font-display font-semibold text-lg text-zinc-100" data-testid="whatsapp-status-text">WhatsApp conectado</p>
              <p className="text-sm text-zinc-400" data-testid="whatsapp-number">{conn.display_phone_number}</p>
            </div>
          </div>
          <div className="flex items-center gap-2 text-sm">
            <span className="w-2 h-2 rounded-full bg-emerald-500 pulse-dot" />
            <span className="text-emerald-400" data-testid="whatsapp-connection-status">Ativo</span>
          </div>
          {testOk && (
            <p className="text-sm text-emerald-300 bg-emerald-950/40 border border-emerald-800/40 rounded-lg px-3 py-2.5" data-testid="test-connection-ok">
              WhatsApp conectado e pronto para atendimento{testOk.verified_name ? ` — ${testOk.verified_name}` : ""}.
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            <Button onClick={testConnection} disabled={testing} data-testid="test-connection-btn"
              className="brand-gradient brand-gradient-hover text-white border-0">
              {testing ? <Loader2 size={15} className="mr-2 animate-spin" /> : <ShieldCheck size={15} className="mr-2" />}
              Testar conexão
            </Button>
            <Link to="/configuracoes" data-testid="whatsapp-settings-link">
              <Button variant="outline" className="border-[#3F476C] text-zinc-300">
                <Settings size={15} className="mr-2" /> Configurações
              </Button>
            </Link>
            <Button variant="outline" onClick={() => setConfirmOpen(true)} data-testid="disconnect-whatsapp-btn"
              className="border-rose-800/50 text-rose-400 hover:bg-rose-950/40">
              <Unplug size={15} className="mr-2" /> Desconectar
            </Button>
          </div>
        </div>
      ) : (
        <div className="rounded-xl border border-[#23283E] bg-[#0F111A] p-6 space-y-5 fade-up" data-testid="whatsapp-connect-card">
          {status?.meta_configured ? (
            <>
              <div className="space-y-4">
                <div className="space-y-1.5">
                  <Label className="text-zinc-400 text-xs">País</Label>
                  <Input value="Brasil (+55)" disabled data-testid="phone-country-input"
                    className="bg-[#090A0F] border-[#23283E] text-zinc-500" />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-zinc-400 text-xs">Número do WhatsApp de atendimento</Label>
                  <Input value={phone} onChange={(e) => setPhone(maskPhone(e.target.value))}
                    data-testid="office-phone-input" placeholder="(11) 99999-9999"
                    className="bg-[#090A0F] border-[#23283E]" />
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button onClick={() => startConnect(false)} disabled={connecting} data-testid="connect-whatsapp-btn"
                  className="brand-gradient brand-gradient-hover text-white border-0">
                  {connecting ? <Loader2 size={15} className="mr-2 animate-spin" /> : <PhoneCall size={15} className="mr-2" />}
                  Conectar WhatsApp
                </Button>
                <Button variant="outline" onClick={() => startConnect(true)} disabled={connecting}
                  data-testid="connect-qr-btn" className="border-[#3F476C] text-zinc-300">
                  <QrCode size={15} className="mr-2" /> Conectar pelo celular
                </Button>
              </div>
              {qrUrl && (
                <div className="rounded-lg border border-[#23283E] bg-[#090A0F] p-5 inline-block" data-testid="qr-panel">
                  <div className="bg-white p-3 rounded-lg inline-block">
                    <QRCode value={qrUrl} size={160} />
                  </div>
                  <p className="text-xs text-zinc-500 mt-3 max-w-[220px]">
                    Aponte a câmera do celular para abrir a autorização oficial da Meta. A conexão é vinculada ao seu escritório automaticamente.
                  </p>
                </div>
              )}
              <p className="text-xs text-zinc-500">
                Você será redirecionado para a autorização oficial da Meta/WhatsApp e volta automaticamente ao RAVI.
                Não pedimos senhas, códigos técnicos ou configurações.
              </p>
            </>
          ) : (
            <div className="rounded-lg border border-amber-700/40 bg-amber-950/30 p-4" data-testid="meta-pending-panel">
              <p className="text-sm text-amber-300 font-medium">Conexão oficial em ativação</p>
              <p className="text-xs text-zinc-400 mt-1.5 leading-relaxed">
                Estamos concluindo a ativação da infraestrutura oficial da Meta para o RAVI.
                Nenhuma configuração técnica será necessária para você — em breve bastará informar o número e clicar em "Conectar WhatsApp".
              </p>
            </div>
          )}

          {status?.meta_test_available && !status?.meta_configured && (
            <div className="rounded-lg border border-indigo-800/40 bg-indigo-950/30 p-4 space-y-3" data-testid="test-number-panel">
              <p className="text-sm text-indigo-300 font-medium">Ambiente de testes — número da Meta (+1 555 665-3479)</p>
              <p className="text-xs text-zinc-400 leading-relaxed">Disponível apenas durante a fase de testes do RAVI.</p>
              <form onSubmit={connectTest} className="flex gap-2">
                <Input type="password" value={testToken} onChange={(e) => setTestToken(e.target.value)}
                  data-testid="test-token-input" placeholder="Token temporário do painel da Meta"
                  className="bg-[#090A0F] border-[#23283E] font-mono-code text-xs" />
                <Button type="submit" disabled={connectingTest || !testToken.trim()} data-testid="connect-test-btn"
                  className="brand-gradient brand-gradient-hover text-white border-0 shrink-0">
                  {connectingTest ? <Loader2 size={15} className="animate-spin" /> : "Ativar"}
                </Button>
              </form>
            </div>
          )}
        </div>
      )}

      {usage && usage.mensagens_total > 0 && (
        <div className="rounded-xl border border-[#23283E] bg-[#0F111A] p-6 space-y-4 fade-up" data-testid="consumo-card">
          <div className="flex items-center justify-between">
            <h3 className="font-display font-semibold text-zinc-200">Consumo WhatsApp</h3>
            <span className="font-mono-code text-[10px] uppercase tracking-widest text-zinc-500">Período {usage.periodo}</span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div><p className="font-mono-code text-[10px] uppercase tracking-widest text-zinc-500">Mensagens faturáveis</p>
              <p className="font-display text-xl font-bold text-zinc-100 mt-1" data-testid="consumo-faturaveis">{usage.mensagens_faturaveis}</p></div>
            <div><p className="font-mono-code text-[10px] uppercase tracking-widest text-zinc-500">Valor acumulado</p>
              <p className="font-display text-xl font-bold text-zinc-100 mt-1" data-testid="consumo-acumulado">R$ {usage.valor_acumulado.toFixed(2)}</p></div>
            <div><p className="font-mono-code text-[10px] uppercase tracking-widest text-zinc-500">Já faturado</p>
              <p className="font-display text-xl font-bold text-zinc-400 mt-1" data-testid="consumo-faturado">R$ {usage.valor_faturado.toFixed(2)}</p></div>
            <div><p className="font-mono-code text-[10px] uppercase tracking-widest text-zinc-500">A pagar</p>
              <p className="font-display text-xl font-bold brand-gradient-text mt-1" data-testid="consumo-a-pagar">R$ {usage.valor_a_pagar.toFixed(2)}</p></div>
          </div>
          {usage.historico.length > 0 && (
            <div className="pt-3 border-t border-[#23283E]" data-testid="consumo-historico">
              <p className="font-mono-code text-[10px] uppercase tracking-widest text-zinc-500 mb-2">Histórico por dia</p>
              <div className="space-y-1 max-h-48 overflow-y-auto">
                {usage.historico.map((h, i) => (
                  <div key={i} className="flex items-center justify-between text-xs py-1" data-testid={`consumo-dia-${i}`}>
                    <span className="text-zinc-500">{new Date(h.data + "T12:00:00").toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" })}</span>
                    <span className="text-zinc-400">{h.categoria}</span>
                    <span className="text-zinc-400">{h.faturavel} faturáveis × R$ {h.unitario}</span>
                    <span className="text-zinc-200">R$ {h.valor.toFixed(2)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent className="bg-[#0F111A] border-[#23283E]" data-testid="disconnect-confirm-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle className="font-display text-zinc-100">Desconectar WhatsApp</AlertDialogTitle>
            <AlertDialogDescription className="text-zinc-400">
              Tem certeza que deseja desconectar o WhatsApp do escritório? O Ravi deixará de responder automaticamente,
              mas todo o histórico de clientes, conversas e processos será mantido. Você pode reconectar quando quiser.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="disconnect-cancel-btn" className="border-[#3F476C] text-zinc-300 bg-transparent">Cancelar</AlertDialogCancel>
            <AlertDialogAction onClick={disconnect} data-testid="disconnect-confirm-btn"
              className="bg-rose-600 hover:bg-rose-500 text-white border-0">Desconectar</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
