import { useEffect, useState } from "react";
import { api } from "@/lib/api";

const fmt = (v) => `R$ ${Number(v || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}`;

function Block({ title, children, tid }) {
  return (
    <div className="rounded-xl border border-[#23283E] bg-[#0F111A] p-5" data-testid={tid}>
      <h3 className="font-display font-semibold text-zinc-200 text-sm mb-4">{title}</h3>
      {children}
    </div>
  );
}

function Row({ label, value }) {
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-[#23283E]/40 last:border-0">
      <span className="text-xs text-zinc-500 capitalize">{label}</span>
      <span className="text-xs text-zinc-200 font-medium">{value}</span>
    </div>
  );
}

export default function AdminRelatorios() {
  const [r, setR] = useState(null);
  useEffect(() => { api.get("/admin/reports").then((x) => setR(x.data)).catch(() => {}); }, []);

  if (!r) return <div className="p-8 text-zinc-500" data-testid="relatorios-loading">Carregando…</div>;

  return (
    <div className="p-6 lg:p-8 space-y-6" data-testid="admin-relatorios-page">
      <div className="fade-up">
        <h1 className="font-display text-2xl sm:text-3xl font-semibold tracking-tight text-zinc-100">Relatórios</h1>
        <p className="text-sm text-zinc-500 mt-1">Visões consolidadas da plataforma. Exportação disponível em versão futura.</p>
      </div>
      <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4 fade-up">
        <Block title="Escritórios" tid="rep-escritorios">
          <Row label="Total" value={r.escritorios.total} />
          {Object.entries(r.escritorios.por_status).map(([k, v]) => <Row key={k} label={k} value={v} />)}
          {Object.entries(r.escritorios.por_plano).map(([k, v]) => <Row key={k} label={`plano ${k}`} value={v} />)}
        </Block>
        <Block title="Utilização" tid="rep-utilizacao">
          {Object.entries(r.utilizacao).map(([k, v]) => <Row key={k} label={k} value={v} />)}
        </Block>
        <Block title="Atendimento" tid="rep-atendimento">
          {Object.entries(r.atendimento).map(([k, v]) => <Row key={k} label={k} value={v} />)}
        </Block>
        <Block title="WhatsApp" tid="rep-whatsapp">
          {Object.keys(r.whatsapp).length === 0 && <p className="text-xs text-zinc-600">Sem conexões.</p>}
          {Object.entries(r.whatsapp).map(([k, v]) => <Row key={k} label={k} value={v} />)}
        </Block>
        <Block title="Financeiro" tid="rep-financeiro">
          <Row label="receita recebida" value={fmt(r.financeiro.receita_recebida)} />
          <Row label="cobranças" value={r.financeiro.cobrancas} />
          <Row label="upgrades" value={r.financeiro.upgrades} />
          <Row label="downgrades" value={r.financeiro.downgrades} />
          <Row label="cancelamentos" value={r.financeiro.cancelamentos} />
        </Block>
        <Block title="Inteligência Artificial" tid="rep-ia">
          <Row label="perguntas" value={r.ia.perguntas} />
          <Row label="respostas" value={r.ia.respostas} />
          <Row label="escalonamentos" value={r.ia.escalonamentos} />
          <Row label="taxa de resolução" value={`${r.ia.taxa_resolucao}%`} />
        </Block>
      </div>
    </div>
  );
}
