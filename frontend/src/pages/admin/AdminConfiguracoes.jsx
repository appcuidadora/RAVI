import { useEffect, useState } from "react";
import { api, apiError } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export default function AdminConfiguracoes() {
  const [cfg, setCfg] = useState({ rules: [], tom_padrao: "acolhedor", autonomia: "padrao", limite_resposta: 400 });
  const [rulesText, setRulesText] = useState("");

  useEffect(() => {
    api.get("/admin/settings/ai").then((r) => {
      const merged = { rules: [], tom_padrao: "acolhedor", autonomia: "padrao", limite_resposta: 400, ...r.data };
      setCfg(merged);
      setRulesText((merged.rules || []).join("\n"));
    }).catch(() => {});
  }, []);

  const save = async (e) => {
    e.preventDefault();
    try {
      await api.put("/admin/settings/ai", {
        rules: rulesText.split("\n").map((s) => s.trim()).filter(Boolean),
        tom_padrao: cfg.tom_padrao, autonomia: cfg.autonomia,
        limite_resposta: Number(cfg.limite_resposta) || 400,
      });
      toast.success("Configurações globais de IA salvas — valem para todos os escritórios");
    } catch (err) { toast.error(apiError(err)); }
  };

  return (
    <div className="p-6 lg:p-8 space-y-6 max-w-3xl" data-testid="admin-configuracoes-page">
      <div className="fade-up">
        <h1 className="font-display text-2xl sm:text-3xl font-semibold tracking-tight text-zinc-100">Inteligência Artificial — Global</h1>
        <p className="text-sm text-zinc-500 mt-1">
          Hierarquia: GLOBAL RAVI → Escritório → Usuário → Conversa. Uma regra mais restritiva nunca é sobrescrita por uma menos restritiva.
        </p>
      </div>

      <form onSubmit={save} className="rounded-xl border border-[#23283E] bg-[#0F111A] p-6 space-y-5 fade-up" data-testid="ai-config-form">
        <div className="space-y-1.5">
          <Label className="text-zinc-400 text-xs">Regras globais de segurança (uma por linha)</Label>
          <Textarea value={rulesText} onChange={(e) => setRulesText(e.target.value)} rows={6}
            data-testid="ai-rules-input"
            placeholder={"RAVI nunca deve inventar informação processual.\nRAVI deve escalar questões jurídicas estratégicas.\nRAVI deve informar quando não possui informação suficiente."}
            className="bg-[#090A0F] border-[#23283E] font-mono-code text-xs" />
        </div>
        <div className="grid grid-cols-3 gap-3">
          <div className="space-y-1.5">
            <Label className="text-zinc-400 text-xs">Tom de voz padrão</Label>
            <Select value={cfg.tom_padrao} onValueChange={(v) => setCfg({ ...cfg, tom_padrao: v })}>
              <SelectTrigger data-testid="ai-tone-select" className="bg-[#090A0F] border-[#23283E]"><SelectValue /></SelectTrigger>
              <SelectContent className="bg-[#0F111A] border-[#23283E]">
                <SelectItem value="acolhedor">Acolhedor</SelectItem>
                <SelectItem value="formal">Formal</SelectItem>
                <SelectItem value="direto">Direto</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label className="text-zinc-400 text-xs">Nível de autonomia</Label>
            <Select value={cfg.autonomia} onValueChange={(v) => setCfg({ ...cfg, autonomia: v })}>
              <SelectTrigger data-testid="ai-autonomy-select" className="bg-[#090A0F] border-[#23283E]"><SelectValue /></SelectTrigger>
              <SelectContent className="bg-[#0F111A] border-[#23283E]">
                <SelectItem value="padrao">Padrão</SelectItem>
                <SelectItem value="restrito">Restrito</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label className="text-zinc-400 text-xs">Limite de resposta (caracteres)</Label>
            <Input type="number" value={cfg.limite_resposta} onChange={(e) => setCfg({ ...cfg, limite_resposta: e.target.value })}
              data-testid="ai-limit-input" className="bg-[#090A0F] border-[#23283E]" />
          </div>
        </div>
        <Button type="submit" data-testid="ai-config-save" className="brand-gradient brand-gradient-hover text-white border-0">
          Salvar configurações globais
        </Button>
      </form>
    </div>
  );
}
