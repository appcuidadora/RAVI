from fastapi import APIRouter, Depends
from database import db
from security import require_permission, office_filter
from usage import current_period

router = APIRouter(prefix="/api/whatsapp", tags=["usage"])


@router.get("/usage")
async def whatsapp_usage(user: dict = Depends(require_permission("whatsapp"))):
    """Painel de consumo do escritório: somente dados do próprio office_id."""
    f = office_filter(user)
    period = current_period()
    events = await db.whatsapp_usage_events.find({**f, "billing_period": period}, {"_id": 0}).to_list(20000)

    billable = [e for e in events if e["billable"]]
    total = round(sum(e["ravi_price"] for e in billable), 2)
    invoiced = round(sum(e["ravi_price"] for e in billable if e.get("invoice_id")), 2)

    by_cat = {}
    for e in billable:
        c = e["billing_category"]
        by_cat.setdefault(c, {"quantidade": 0, "valor": 0.0})
        by_cat[c]["quantidade"] += 1
        by_cat[c]["valor"] = round(by_cat[c]["valor"] + e["ravi_price"], 4)

    daily = {}
    for e in events:
        dia = e["created_at"][:10]
        d = daily.setdefault(dia, {})
        c = e["billing_category"]
        dc = d.setdefault(c, {"quantidade": 0, "valor": 0.0, "unitario": e["ravi_price"], "faturavel": 0})
        dc["quantidade"] += 1
        if e["billable"]:
            dc["faturavel"] += 1
            dc["valor"] = round(dc["valor"] + e["ravi_price"], 4)
    history = [{"data": dia, "categoria": cat, **vals}
               for dia, cats in sorted(daily.items(), reverse=True) for cat, vals in cats.items()]

    invoices = await db.whatsapp_invoices.find(f, {"_id": 0}).sort("issue_date", -1).to_list(24)
    return {
        "periodo": period,
        "mensagens_total": len(events),
        "mensagens_faturaveis": len(billable),
        "mensagens_gratuitas": len(events) - len(billable),
        "valor_acumulado": total,
        "valor_faturado": invoiced,
        "valor_a_pagar": round(total - invoiced, 2),
        "por_categoria": by_cat,
        "historico": history[:90],
        "faturas": invoices,
    }
