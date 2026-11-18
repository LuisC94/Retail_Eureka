"""
Cliente do Stock Agent Web Service (FastAPI, porta 8005 - Web Services/stock_agent_service).

Monta, a partir do ORM, o estado atual de um perfil (Produtor, Retalhista ou Processador) para uma cultura
e pede ao agente a recomendação do dia:
  - modo "lot":       que lote(s) colocar à venda hoje;
  - modo "warehouse": que armazém abrir esta semana (todo o stock vai para venda).

Lotes por perfil:
  - Produtor: cada Harvest com stock e armazém (batch LOTE-<id>).
  - Retalhista / Processador: o stock (ConsolidatedStock) é agregado; os lotes são reconstruídos a partir das
    receções confirmadas (DealReception), assumindo que o stock mais antigo saiu primeiro (FIFO). Cada lote entra na
    data de receção com as medições dessa receção; se faltarem, as da colheita de origem (batch_id LOTE-<id>).
    O stock sem receção associada (compra rápida, ajuste manual) é tratado como um lote com entrada estimada.
"""
import datetime
import logging
import re

import requests
from django.conf import settings

from dashboard.models import (ConsolidatedStock, DemandForecast, Harvest, HistoricalSalesData, ProductSubFamily,
                              Warehouse, WarehouseSensorReading)
from dashboard.services.marketplace_service import marketplace_service

logger = logging.getLogger(__name__)

STOCK_AGENT_SERVICE_URL = getattr(settings, 'STOCK_AGENT_SERVICE_URL', 'http://127.0.0.1:8005').rstrip('/')
ROLES = ('Producer', 'Retailer', 'Processor')
PAST_DAYS = 40      # histórico de mercado enviado (o agente usa médias de 7 e 30 dias)
FUTURE_DAYS = 14    # previsão de procura enviada


def user_role(user):
    for r in ROLES:
        if user.groups.filter(name=r).exists():
            return r
    return 'Producer' if user.is_superuser else None


def check_health():
    try:
        return requests.get(f"{STOCK_AGENT_SERVICE_URL}/health", timeout=3).status_code == 200
    except requests.RequestException:
        return False


def fruit_label(subfamily):
    return f"{subfamily.fruit_type or ''} {subfamily.name}".strip()


def _f(v):
    return None if v is None else float(v)


# ---------------------------------------------------------------------------------------------
# Culturas com stock
# ---------------------------------------------------------------------------------------------

def cultures_with_stock(user):
    role = user_role(user)
    out = {}
    if role == 'Producer':
        for h in Harvest.objects.filter(producer=user, warehouse__isnull=False, subfamily__isnull=False).select_related('subfamily'):
            kg = float(h.current_stock_kg)
            if kg <= 0:
                continue
            c = out.setdefault(h.subfamily_id, {"id": h.subfamily_id, "nome": h.subfamily.name, "fruta": h.subfamily.fruit_type,
                                                "kg": 0.0, "n_lotes": 0, "armazens": set()})
            c["kg"] += kg
            c["n_lotes"] += 1
            c["armazens"].add(h.warehouse_id)
    else:
        for s in ConsolidatedStock.objects.filter(owner=user, quantity__gt=0).select_related('culture'):
            c = out.setdefault(s.culture_id, {"id": s.culture_id, "nome": s.culture.name, "fruta": s.culture.fruit_type,
                                              "kg": 0.0, "n_lotes": 0, "armazens": set()})
            c["kg"] += float(s.quantity)
            c["n_lotes"] += 1
            c["armazens"].add(s.warehouse_location)
    res = []
    for c in out.values():
        c["n_armazens"] = len(c.pop("armazens"))
        c["kg"] = round(c["kg"], 1)
        res.append(c)
    return sorted(res, key=lambda c: -c["kg"])


# ---------------------------------------------------------------------------------------------
# Lotes
# ---------------------------------------------------------------------------------------------

def _producer_lots(user, subfamily, today, avisos):
    harvests = list(Harvest.objects.filter(producer=user, subfamily=subfamily, warehouse__isnull=False,
                                           harvest_date__lte=today).select_related('warehouse'))
    listed = set()
    try:
        for l in marketplace_service.fetch_open_listings(seller_id=user.username):
            if l.get('batch_id'):
                listed.add(str(l['batch_id']))
    except Exception:  # noqa: BLE001
        avisos.append("Marketplace indisponível: não foi possível verificar que lotes já estão à venda.")
    lots, whs = [], {}
    for h in harvests:
        kg = float(h.current_stock_kg)
        if kg <= 0:
            continue
        batch = f"LOTE-{h.pk}"
        lots.append({
            "lote_id": batch, "armazem_id": str(h.warehouse_id),
            "data_colheita": h.harvest_date.isoformat(), "data_entrada": h.harvest_date.isoformat(),
            "quantidade_kg": round(kg, 2), "firmeza": _f(h.firmness), "brix": _f(h.soluble_solids), "acidez": _f(h.acidity),
            "estado": "a_venda" if batch in listed else "armazenado",
        })
        whs[h.warehouse_id] = h.warehouse
    return lots, whs


def _stock_warehouse(stock):
    loc = stock.warehouse_location or ''
    m = re.search(r'\(WH:\s*(\d+)\)', loc)
    if m:
        wh = Warehouse.objects.filter(pk=int(m.group(1))).first()
        if wh:
            return wh
    clean = loc.split(' (WH:')[0].strip()
    return (Warehouse.objects.filter(owner=stock.owner, location=clean).first()
            or Warehouse.objects.filter(owner=stock.owner).first())


def _origin_harvest(batch_id):
    m = re.match(r'LOTE-(\d+)$', str(batch_id or ''))
    return Harvest.objects.filter(pk=int(m.group(1))).first() if m else None


def _buyer_lots(user, subfamily, today, avisos):
    """
    Retalhista / Processador: reconstrói os lotes a partir das receções confirmadas (FIFO).
    O Stock Agent começa cada lote na data de entrada com as medições indicadas, por isso as medições da receção
    (estado real à chegada) têm prioridade sobre as da colheita.
    """
    from dashboard.models import DealReception

    stocks = list(ConsolidatedStock.objects.filter(owner=user, culture=subfamily, quantity__gt=0))
    lots, whs = [], {}
    kg_sem_rececao = 0.0
    for s in stocks:
        wh = _stock_warehouse(s)
        if wh is None:
            avisos.append(f"Stock '{s.warehouse_location}' sem armazém associado: ignorado.")
            continue
        whs[wh.pk] = wh
        remaining = float(s.quantity)
        receptions = (DealReception.objects.filter(buyer=user, culture=subfamily, stock=s,
                                                   status=DealReception.STATUS_RECEIVED, received_at__lte=today)
                      .order_by('-received_at', '-confirmed_at'))
        for r in receptions:  # o stock restante corresponde às receções mais recentes
            if remaining <= 0:
                break
            qty = min(remaining, float(r.received_quantity_kg or r.quantity_kg or 0.0))
            if qty <= 0:
                continue
            origin = _origin_harvest(r.batch_id)

            def pick(measured, from_origin):
                if measured is not None:
                    return _f(measured)
                return _f(from_origin) if origin is not None else None

            lots.append({
                "lote_id": f"{r.batch_id or 'REC'}@{r.deal_id}", "armazem_id": str(wh.pk),
                "data_colheita": (origin.harvest_date if origin else r.received_at).isoformat(),
                "data_entrada": r.received_at.isoformat(), "quantidade_kg": round(qty, 2),
                "firmeza": pick(r.firmness, origin.firmness if origin else None),
                "brix": pick(r.soluble_solids, origin.soluble_solids if origin else None) or (_f(s.avg_soluble_solids) or None),
                "acidez": pick(r.acidity, origin.acidity if origin else None),
                "estado": "armazenado",
            })
            remaining -= qty
        if remaining > 1e-6:
            kg_sem_rececao += remaining
            entry = today - datetime.timedelta(days=10)
            lots.append({
                "lote_id": f"STOCK-{s.pk}", "armazem_id": str(wh.pk),
                "data_colheita": (entry - datetime.timedelta(days=3)).isoformat(), "data_entrada": entry.isoformat(),
                "quantidade_kg": round(remaining, 2), "firmeza": None, "brix": _f(s.avg_soluble_solids) or None,
                "acidez": None, "estado": "armazenado",
            })
    if kg_sem_rececao > 0:
        avisos.append(f"{kg_sem_rececao:.0f} kg sem receção associada (ex.: compra rápida ou ajuste manual): "
                      "entrada estimada há 10 dias (precisão reduzida do tempo de vida).")
    return lots, whs


# ---------------------------------------------------------------------------------------------
# Leituras e mercado
# ---------------------------------------------------------------------------------------------

def _readings(whs, start, today, avisos):
    out = []
    for wh in whs.values():
        by_date = {r.date: r for r in WarehouseSensorReading.objects.filter(warehouse=wh, date__gte=start, date__lte=today)}
        filled = 0
        d = start
        ft = float(wh.fixed_temperature) if wh.fixed_temperature is not None else (0.8 if wh.control_type == 'Controlled' else 4.0)
        fh = float(wh.fixed_humidity) if wh.fixed_humidity is not None else 90.0
        while d <= today:
            r = by_date.get(d)
            if r is not None:
                out.append({"armazem_id": str(wh.pk), "data": d.isoformat(), "temperatura": float(r.temperature),
                            "humidade": float(r.humidity), "etileno": _f(r.ethylene)})
            else:
                filled += 1
                out.append({"armazem_id": str(wh.pk), "data": d.isoformat(), "temperatura": ft, "humidade": fh, "etileno": None})
            d += datetime.timedelta(days=1)
        if filled:
            avisos.append(f"Armazém {wh.location}: {filled} dias sem leituras de sensores (usados valores fixos {ft:.1f}°C / {fh:.0f}%).")
    return out


def _market(user, subfamily, today, avisos):
    start = today - datetime.timedelta(days=PAST_DAYS)
    end = today + datetime.timedelta(days=FUTURE_DAYS)
    hist = {h.date: h for h in HistoricalSalesData.objects.filter(owner=user, culture=subfamily, date__gte=start, date__lte=today)}
    fc = {f.date: float(f.predicted_quantity_kg) for f in DemandForecast.objects.filter(owner=user, culture=subfamily, date__gte=start, date__lte=end)}

    recent = list(HistoricalSalesData.objects.filter(owner=user, culture=subfamily).order_by('-date')[:90])
    ref_price = sum(float(h.price_per_kg) for h in recent) / len(recent) if recent else None
    ref_sales = sum(float(h.sales_quantity_kg) for h in recent) / len(recent) if recent else None
    ticker_price = None
    try:
        prices = marketplace_service.fetch_market_prices() or {}
        for t in prices.get('market_tickers', []) or []:
            if str(t.get('culture_name', '')).strip().lower() == subfamily.name.strip().lower():
                ticker_price = float(t.get('current_avg_price_eur') or 0) or None
    except Exception:  # noqa: BLE001
        pass

    # Último recurso: histórico da mesma cultura noutros perfis da plataforma (referência de mercado)
    others = None
    if ref_price is None or ref_sales is None:
        others = list(HistoricalSalesData.objects.filter(culture=subfamily).exclude(owner=user).order_by('-date')[:180])

    if len(hist) < 10:
        if ticker_price:
            ref_price = ticker_price
            avisos.append(f"Sem vendas recentes registadas: preço de referência = cotação do Marketplace ({ticker_price:.2f} €/kg).")
        elif ref_price:
            avisos.append(f"Sem vendas nos últimos {PAST_DAYS} dias: preço de referência = média das últimas vendas registadas ({ref_price:.2f} €/kg).")
        elif others:
            ref_price = sum(float(h.price_per_kg) for h in others) / len(others)
            avisos.append(f"Este perfil não tem histórico de vendas de {subfamily.name}: preço de referência = média de mercado "
                          f"da plataforma para esta cultura ({ref_price:.2f} €/kg).")
    if ref_price is None:
        return None, (f"Sem histórico de preços para {subfamily.name} (nem deste perfil, nem do Marketplace, nem de outros perfis). "
                      "Carregue o histórico de vendas na aba Previsão de Vendas.")
    future_fc = [v for k, v in fc.items() if k > today]
    if not future_fc:
        base = ref_sales
        if base is None and others:
            base = ref_sales = sum(float(h.sales_quantity_kg) for h in others) / len(others)
            avisos.append(f"Este perfil não tem histórico nem previsão de procura de {subfamily.name}: usada a procura média de outros "
                          f"perfis da plataforma ({base:.0f} kg/dia). A recomendação é apenas indicativa.")
        elif base is not None:
            avisos.append(f"Sem previsão de procura para os próximos {FUTURE_DAYS} dias: usada a média de vendas históricas ({base:.0f} kg/dia). "
                          "Gere previsões na aba Previsão de Vendas para recomendações mais precisas.")
        if base is None:
            return None, ("Sem previsão de procura nem histórico de vendas para esta cultura. "
                          "Carregue o histórico de vendas e gere a previsão no separador Previsão de Vendas.")
    fc_default = (sum(future_fc) / len(future_fc)) if future_fc else ref_sales

    rows = []
    d = start
    while d <= end:
        h = hist.get(d)
        price = float(h.price_per_kg) if h else ref_price
        sales = float(h.sales_quantity_kg) if h else None
        pred = fc.get(d, sales if sales is not None else fc_default)
        rows.append({"data": d.isoformat(), "preco_kg": round(price, 4), "procura_prevista_kg": round(float(pred or 0.0), 2),
                     "vendas_kg": round(sales if sales is not None else float(pred or 0.0), 2)})
        d += datetime.timedelta(days=1)
    return rows, None


# ---------------------------------------------------------------------------------------------
# Pedido ao agente
# ---------------------------------------------------------------------------------------------

def build_payload(user, subfamily, mode, today=None):
    today = today or datetime.date.today()
    avisos = []
    role = user_role(user)
    if role == 'Producer':
        lots, whs = _producer_lots(user, subfamily, today, avisos)
    else:
        lots, whs = _buyer_lots(user, subfamily, today, avisos)
    if not lots:
        return None, avisos, "Sem lotes em stock para esta cultura."
    start = min(datetime.date.fromisoformat(l["data_entrada"]) for l in lots)
    mercado, err = _market(user, subfamily, today, avisos)
    if err:
        return None, avisos, err
    payload = {
        "perfil": user.username, "cultura": subfamily.name, "tipo_fruta": fruit_label(subfamily), "modo": mode,
        "data": today.isoformat(),
        "armazens": [{"armazem_id": str(w.pk), "tipo_controlo": w.control_type, "localizacao": w.location, "aberto": False}
                     for w in whs.values()],
        "lotes": lots,
        "leituras": _readings(whs, start, today, avisos),
        "mercado": mercado,
    }
    return payload, avisos, None


def recommend(user, subfamily_id, mode='lot', today=None):
    subfamily = ProductSubFamily.objects.filter(pk=subfamily_id).first()
    if subfamily is None:
        return {"status": "error", "message": "Cultura inexistente."}
    if mode not in ('lot', 'warehouse'):
        return {"status": "error", "message": "Modo inválido."}
    payload, avisos, err = build_payload(user, subfamily, mode, today)
    if err:
        return {"status": "error", "message": err, "avisos": avisos}
    try:
        resp = requests.post(f"{STOCK_AGENT_SERVICE_URL}/decide", json=payload, timeout=(5, 120))
    except requests.RequestException as e:
        return {"status": "error", "message": f"Stock Agent Web Service (porta 8005) inacessível: {e}", "avisos": avisos}
    if resp.status_code != 200:
        try:
            detail = resp.json().get('detail', resp.text)
        except ValueError:
            detail = resp.text
        return {"status": "error", "message": f"Stock Agent: {detail}", "avisos": avisos}
    result = resp.json()
    wh_names = {a["armazem_id"]: a["localizacao"] for a in payload["armazens"]}
    wh_types = {a["armazem_id"]: a["tipo_controlo"] for a in payload["armazens"]}
    for r in result.get("avaliacao_lotes", []) + result.get("avaliacao_armazens", []):
        r["armazem_nome"] = wh_names.get(str(r.get("armazem_id")), str(r.get("armazem_id")))
        r["atmosfera_controlada"] = wh_types.get(str(r.get("armazem_id"))) == 'Controlled'
    if result.get("armazem_a_abrir"):
        result["armazem_a_abrir_nome"] = wh_names.get(str(result["armazem_a_abrir"]), result["armazem_a_abrir"])
    return {"status": "success", "perfil_tipo": user_role(user), "cultura": subfamily.name, "fruta": subfamily.fruit_type,
            "avisos": avisos, "resultado": result,
            "dados": {"lotes": len(payload["lotes"]), "armazens": len(payload["armazens"]),
                      "kg_total": round(sum(l["quantidade_kg"] for l in payload["lotes"]), 1)}}
