"""
Integração da plataforma com os Web Services de IA:
  - Forecast Web Service (:8001)  -> 4 modelos apresentados como "Modelo Previsão 1..4"
  - Buyer Agent Web Service (:8002) -> DSAC Limitado (30 variáveis) com Lifecycle LC v0.2.0 embutido

Regras:
  - O Buyer Agent é SEMPRE treinado com as previsões do Forecast (sem previsões, não há treino).
  - O clima (temperatura, humidade, etileno) vem das leituras do armazém (WarehouseSensorReading).
"""
import datetime
import json
import logging

import pandas as pd
import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from dashboard.models import ConsolidatedStock, DemandForecast, HistoricalSalesData, TrainedModel, Warehouse, WarehouseSensorReading

logger = logging.getLogger(__name__)

FORECAST_SERVICE_URL = getattr(settings, 'FORECAST_SERVICE_URL', 'http://127.0.0.1:8001')
BUYER_SERVICE_URL = getattr(settings, 'BUYER_SERVICE_URL', 'http://127.0.0.1:8002')

# Modelos de previsão (o nome real de cada modelo fica no Web Service; a plataforma só mostra o nome mascarado)
FORECAST_MODELS = [
    ('modelo_1', 'Modelo Previsão 1'),
    ('modelo_2', 'Modelo Previsão 2'),
    ('modelo_3', 'Modelo Previsão 3'),
    ('modelo_4', 'Modelo Previsão 4'),
]
FORECAST_MODEL_NAMES = dict(FORECAST_MODELS)
_FC_ALIASES = {'mlp': 'modelo_1', 'sales_mlp': 'modelo_1', 'model_1': 'modelo_1',
               'autoformer': 'modelo_2', 'sales_autoformer': 'modelo_2', 'model_2': 'modelo_2',
               'model_3': 'modelo_3', 'model_4': 'modelo_4'}
# Marcadores locais (TrainedModel.model_type). modelo_1/2 mantêm os nomes antigos para compatibilidade.
_FC_MARKER = {'modelo_1': 'sales_mlp', 'modelo_2': 'sales_autoformer', 'modelo_3': 'sales_modelo_3', 'modelo_4': 'sales_modelo_4'}
FORECAST_MARKER_TYPES = list(_FC_MARKER.values())

FORECAST_MIN_DAYS = 38          # mínimo exigido pelo Forecast (lags até 30 dias + validação)
BUYER_MIN_DAYS = 30
BUYER_EPISODES_DEFAULT = 350    # valor original do train_dsac.py
HISTORY_DAYS_FOR_PREDICT = 90


def normalize_forecast_model(model_type):
    key = str(model_type or '').strip().lower()
    key = _FC_ALIASES.get(key, key)
    return key if key in FORECAST_MODEL_NAMES else 'modelo_1'


def forecast_model_display(model_type):
    return FORECAST_MODEL_NAMES[normalize_forecast_model(model_type)]


def _service_error(resp):
    try:
        return resp.json().get('detail', resp.text)
    except ValueError:
        return resp.text


def _date_str(d):
    return d.strftime('%Y-%m-%d') if hasattr(d, 'strftime') else str(d)[:10]


# =====================================================================================
# FORECAST
# =====================================================================================

def get_forecast_model_status(user, subfamily):
    """Estado dos 4 modelos de previsão desta cultura no Forecast Web Service."""
    try:
        resp = requests.get(f"{FORECAST_SERVICE_URL}/api/forecast/status",
                            params={"user_id": user.id, "culture_id": subfamily.pk}, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            data['service_online'] = True
            data['model_names'] = FORECAST_MODEL_NAMES
            return data
    except requests.exceptions.RequestException as e:
        logger.warning("Forecast Web Service inacessível: %s", e)
    return {"user_id": user.id, "culture_id": subfamily.pk, "has_model": False, "available_models": [],
            "models": {}, "requires_retrain": [], "last_modified": None, "service_online": False,
            "model_names": FORECAST_MODEL_NAMES}


def _sales_history_payload(rows):
    return [{"date": _date_str(r['date']), "sales_quantity_kg": float(r['sales_quantity_kg']),
             "price_per_kg": float(r['price_per_kg']) if r.get('price_per_kg') is not None else None} for r in rows]


def train_sales_forecaster(user, subfamily, df_data, model_type='modelo_1'):
    """Envia o histórico para o Forecast Web Service treinar o modelo escolhido e guarda o histórico na BD."""
    df_data = df_data.sort_values(by='date').reset_index(drop=True)
    if len(df_data) < FORECAST_MIN_DAYS:
        raise ValueError(f"São necessários pelo menos {FORECAST_MIN_DAYS} dias de histórico para treinar o modelo de previsão (recebidos {len(df_data)}).")
    model_key = normalize_forecast_model(model_type)
    rows = df_data.to_dict('records')
    payload = {"user_id": user.id, "culture_id": subfamily.pk, "model_type": model_key,
               "sales_history": _sales_history_payload(rows)}
    try:
        # Os modelos com pesquisa de kernels MMD treinam 25 configurações: pode demorar vários minutos
        resp = requests.post(f"{FORECAST_SERVICE_URL}/api/forecast/train", json=payload, timeout=(10, 3600))
    except requests.exceptions.ConnectionError:
        raise ConnectionError(f"Não foi possível contactar o Forecast Web Service em {FORECAST_SERVICE_URL}. Verifique se o serviço está ativo.")
    if resp.status_code != 200:
        raise RuntimeError(f"Erro no Forecast Web Service: {_service_error(resp)}")
    resp_data = resp.json()

    TrainedModel.objects.update_or_create(
        owner=user, culture=subfamily, model_type=_FC_MARKER[model_key],
        file_name=f'culture_{subfamily.pk}_{model_key}', defaults={'file_data': b'web_service_remote_model'})

    # O ficheiro substitui só os dias que cobre: vendas registadas fora desse intervalo mantêm-se
    with transaction.atomic():
        HistoricalSalesData.objects.filter(owner=user, culture=subfamily,
                                           date__gte=rows[0]['date'], date__lte=rows[-1]['date']).delete()
        HistoricalSalesData.objects.bulk_create([
            HistoricalSalesData(owner=user, culture=subfamily, date=r['date'], sales_quantity_kg=r['sales_quantity_kg'],
                                price_per_kg=r['price_per_kg'])
            for r in rows])

    return {"samples_count": len(rows), "model_type": model_key, "model_display_name": FORECAST_MODEL_NAMES[model_key],
            "saved_file": resp_data.get('saved_file', ''), "val_metrics": resp_data.get('val_metrics'),
            "trained_at": resp_data.get('trained_at', timezone.now().isoformat())}


def _default_forecast_model(user, subfamily):
    status = get_forecast_model_status(user, subfamily)
    available = status.get('available_models') or []
    if not available:
        raise ValueError(f"Não existe nenhum modelo de previsão treinado para '{subfamily.name}'. Treine um modelo na aba 'Previsão de Vendas'.")
    return available[0]


def forecast_horizon(user, subfamily, start_date, horizon_days, model_type=None, history_rows=None):
    """Previsão recursiva a partir de start_date com o histórico recente (lista de {date, predicted_kg})."""
    model_key = normalize_forecast_model(model_type) if model_type else _default_forecast_model(user, subfamily)
    if history_rows is None:
        history_rows = list(HistoricalSalesData.objects.filter(owner=user, culture=subfamily, date__lt=start_date)
                            .order_by('-date').values('date', 'sales_quantity_kg', 'price_per_kg')[:HISTORY_DAYS_FOR_PREDICT])[::-1]
    if not history_rows:
        raise ValueError("Não existe histórico de vendas guardado para esta cultura. Treine primeiro o modelo de previsão.")
    payload = {"user_id": user.id, "culture_id": subfamily.pk, "model_type": model_key, "horizon_days": int(horizon_days),
               "start_date": _date_str(start_date), "sales_history": _sales_history_payload(history_rows)}
    try:
        resp = requests.post(f"{FORECAST_SERVICE_URL}/api/forecast/predict", json=payload, timeout=60)
    except requests.exceptions.ConnectionError:
        raise ConnectionError(f"Não foi possível contactar o Forecast Web Service em {FORECAST_SERVICE_URL}. Verifique se o serviço está ativo.")
    if resp.status_code != 200:
        raise RuntimeError(f"Erro no Forecast Web Service: {_service_error(resp)}")
    return model_key, resp.json().get('predictions', []), history_rows


def forecast_series(user, subfamily, history_rows, model_type):
    """Previsão a 1 dia para cada dia do histórico (série usada pelo Buyer Agent). Devolve {date_str: kg}."""
    payload = {"user_id": user.id, "culture_id": subfamily.pk, "model_type": normalize_forecast_model(model_type),
               "sales_history": _sales_history_payload(history_rows)}
    try:
        resp = requests.post(f"{FORECAST_SERVICE_URL}/api/forecast/predict_series", json=payload, timeout=120)
    except requests.exceptions.ConnectionError:
        raise ConnectionError(f"Não foi possível contactar o Forecast Web Service em {FORECAST_SERVICE_URL}. Certifique-se de que o microserviço está ativo na porta 8001.")
    if resp.status_code != 200:
        raise RuntimeError(f"Erro no Forecast Web Service: {_service_error(resp)}")
    return {item['date']: float(item['predicted_kg']) for item in resp.json().get('predictions', [])}


def run_sales_inference(user, subfamily, horizon_days=30, model_type=None, save_to_db=False):
    """Previsão para os próximos N dias a partir do dia seguinte ao último dia de vendas registado."""
    last = HistoricalSalesData.objects.filter(owner=user, culture=subfamily).order_by('-date').first()
    if not last:
        raise ValueError("É necessário ter histórico de vendas guardado para gerar previsões. Treine primeiro o modelo de previsão.")
    start_date = last.date + datetime.timedelta(days=1)
    model_key, preds, history_rows = forecast_horizon(user, subfamily, start_date, horizon_days, model_type=model_type)

    predictions = [{'date': p['date'], 'value': round(max(0.0, float(p['predicted_kg'])), 2)} for p in preds]
    if save_to_db:
        with transaction.atomic():
            DemandForecast.objects.filter(owner=user, culture=subfamily).delete()
            DemandForecast.objects.bulk_create([
                DemandForecast(owner=user, culture=subfamily, date=datetime.date.fromisoformat(p['date']),
                               predicted_quantity_kg=p['value']) for p in predictions])

    total = sum(p['value'] for p in predictions)
    peak = max(predictions, key=lambda p: p['value']) if predictions else {'date': '', 'value': 0.0}
    recent = [{'date': _date_str(r['date']), 'value': round(float(r['sales_quantity_kg']), 2)} for r in history_rows[-30:]]
    return {
        'predictions': predictions,
        'recent_history': recent,
        'kpis': {'total_predicted_kg': round(total, 2),
                 'daily_avg_kg': round(total / len(predictions), 2) if predictions else 0.0,
                 'peak_date': peak['date'], 'peak_val_kg': round(peak['value'], 2),
                 'model_type': FORECAST_MODEL_NAMES[model_key], 'horizon_days': int(horizon_days),
                 'samples_trained': len(history_rows)},
        'model_type': model_key,
        'model_display_name': FORECAST_MODEL_NAMES[model_key],
    }


# =====================================================================================
# BUYER AGENT
# =====================================================================================

def check_buyer_service_health():
    try:
        return requests.get(f"{BUYER_SERVICE_URL}/health", timeout=3).status_code == 200
    except requests.exceptions.RequestException:
        return False


def _buyer_warehouse(user, subfamily):
    """Armazém do comprador para esta cultura (onde está o stock), senão o primeiro com capacidade."""
    stock_item = ConsolidatedStock.objects.filter(owner=user, culture=subfamily).first()
    loc = stock_item.warehouse_location if stock_item else None
    if loc and ' (WH:' in loc:
        loc = loc.split(' (WH:')[0].strip()
    wh = Warehouse.objects.filter(owner=user, location=loc).first() if loc else None
    return wh or Warehouse.objects.filter(owner=user, capacity__gt=0).first() or Warehouse.objects.filter(owner=user).first()


def _owner_type(user):
    return 'Processor' if user.groups.filter(name='Processor').exists() else 'Retailer'


def _fruit_key(subfamily):
    # O Buyer Web Service resolve este texto para um preset do Lifecycle LC v0.2.0
    return f"{subfamily.fruit_type or ''} {subfamily.name}".strip()


def _climate_by_date(warehouse, date_from, date_to):
    if not warehouse:
        return {}
    qs = WarehouseSensorReading.objects.filter(warehouse=warehouse, date__gte=date_from, date__lte=date_to)
    return {r.date: (float(r.temperature), float(r.humidity), float(r.ethylene) if r.ethylene is not None else None) for r in qs}


def _latest_climate(warehouse, on_date):
    if not warehouse:
        return None
    r = WarehouseSensorReading.objects.filter(warehouse=warehouse, date__lte=on_date).order_by('-date').first() \
        or WarehouseSensorReading.objects.filter(warehouse=warehouse).order_by('date').first()
    return (float(r.temperature), float(r.humidity), float(r.ethylene) if r.ethylene is not None else None) if r else None


def get_buyer_model_status(user, subfamily):
    wh = _buyer_warehouse(user, subfamily)
    wh_capacity = float(wh.capacity) if (wh and wh.capacity and float(wh.capacity) > 0) else None
    fc_status = get_forecast_model_status(user, subfamily)
    try:
        resp = requests.get(f"{BUYER_SERVICE_URL}/api/buyer/status",
                            params={"user_id": user.id, "culture_id": subfamily.pk}, timeout=5)
    except requests.exceptions.ConnectionError:
        raise ConnectionError(f"O Buyer Agent Web Service está inacessível em {BUYER_SERVICE_URL}. Certifique-se de que o microserviço está ativo na porta 8002.")
    if resp.status_code != 200:
        raise RuntimeError(f"Erro no Buyer Web Service ({resp.status_code}): {_service_error(resp)}")
    data = resp.json()
    data.update({
        "service_online": True,
        "max_capacity": wh_capacity,
        "has_sales_forecast": fc_status.get('has_model', False),
        "has_forecast_model": fc_status.get('has_model', False),
        "available_forecast_models": fc_status.get('available_models', []),
        "forecast_model_names": FORECAST_MODEL_NAMES,
    })
    return data


# Nomes de colunas aceites nos ficheiros de histórico (sem distinguir maiúsculas/minúsculas)
MARKET_COLUMN_ALIASES = {
    'date': ['date', 'data', 'day', 'dia'],
    'sales_quantity_kg': ['sales_quantity_kg', 'vendas_kg', 'real_value', 'quantidade_kg', 'vendas', 'sales_kg'],
    'price_per_kg': ['price_per_kg', 'preco_venda_euro', 'preco_kg', 'price', 'preco', 'preco_eur_kg'],
    'temperature': ['temperature', 'temperatura', 'temperatura_c', 'temp', 'temp_c'],
    'humidity': ['humidity', 'humidade', 'humidade_pct', 'humidade_%', 'rh', 'hr'],
    'ethylene': ['ethylene', 'etileno', 'etileno_ppm', 'ethylene_ppm'],
}


def normalize_market_columns(df):
    """Uniformiza os nomes das colunas de um ficheiro de histórico (vendas, preço e clima)."""
    by_lower = {str(c).strip().lower(): c for c in df.columns}
    rename = {}
    for target, aliases in MARKET_COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in by_lower and target not in rename.values():
                rename[by_lower[alias]] = target
                break
    return df.rename(columns=rename)


def _num_or_none(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(f) else f


def _normalize_market_df(df):
    df = normalize_market_columns(df)
    df = df.rename(columns={'sales_quantity_kg': 'real_value', 'price_per_kg': 'price'})
    if 'date' not in df.columns or 'real_value' not in df.columns:
        raise ValueError("Os dados de treino têm de ter a data e as vendas reais (date / sales_quantity_kg).")
    df = df.dropna(subset=['date', 'real_value']).sort_values('date').reset_index(drop=True)
    return df


def train_buyer_agent_optimizer_generator(user, subfamily, df_market_data, max_episodes=None, fruit_key=None, forecast_model_type=None):
    """
    Treina o Buyer Agent DSAC no Buyer Web Service:
      1) obtém as previsões do Forecast Web Service para todos os dias do histórico (obrigatório);
      2) junta o clima de cada dia (do ficheiro; nos dias em falta, das leituras do armazém);
      3) envia para /api/buyer/train/stream e reencaminha o progresso.
    """
    yield f"[Django] A preparar dados de treino para a cultura {subfamily.name}...\n"
    df = _normalize_market_df(df_market_data.copy())
    if len(df) < BUYER_MIN_DAYS:
        raise ValueError(f"São necessários pelo menos {BUYER_MIN_DAYS} dias de histórico de vendas para treinar o Buyer Agent (existem {len(df)}).")

    wh = _buyer_warehouse(user, subfamily)
    if not wh or not wh.capacity or float(wh.capacity) <= 0:
        raise ValueError("Não foi encontrado nenhum armazém com capacidade registada. Configure a capacidade do armazém em 'Gestão de Armazéns' antes de treinar o Buyer Agent.")
    capacity = float(wh.capacity)

    # 1) Previsões do Forecast (sempre)
    fc_status = get_forecast_model_status(user, subfamily)
    available = fc_status.get('available_models') or []
    if not available:
        raise ValueError(f"Não existe nenhum modelo de previsão treinado para '{subfamily.name}'. Treine um modelo na aba 'Previsão de Vendas' antes do Buyer Agent.")
    fc_key = normalize_forecast_model(forecast_model_type) if forecast_model_type else available[0]
    if fc_key not in available:
        raise ValueError(f"O {FORECAST_MODEL_NAMES[fc_key]} não está treinado para '{subfamily.name}'. Modelos disponíveis: {', '.join(FORECAST_MODEL_NAMES[k] for k in available)}.")
    yield f"[Django] [1/3] A obter {len(df)} previsões de procura com o {FORECAST_MODEL_NAMES[fc_key]} (Forecast Web Service :8001)...\n"
    history_rows = [{'date': r['date'], 'sales_quantity_kg': r['real_value'], 'price_per_kg': r.get('price')} for r in df.to_dict('records')]
    pred_map = forecast_series(user, subfamily, history_rows, fc_key)
    missing = [_date_str(d) for d in df['date'] if _date_str(d) not in pred_map]
    if missing:
        raise RuntimeError(f"O Forecast Web Service não devolveu previsões para {len(missing)} dias (ex.: {missing[:3]}). O treino foi cancelado.")
    df['prediction'] = [pred_map[_date_str(d)] for d in df['date']]

    # 2) Clima de cada dia: primeiro o do ficheiro de treino; nos dias em falta, as leituras do armazém;
    #    sem nenhum dos dois, o Buyer Web Service usa os valores por omissão (22 °C / 70 %).
    climate = _climate_by_date(wh, df['date'].min(), df['date'].max())
    n_file = n_wh = n_none = 0
    train_records = []
    for r in df.to_dict('records'):
        t, h, e = _num_or_none(r.get('temperature')), _num_or_none(r.get('humidity')), _num_or_none(r.get('ethylene'))
        if t is not None and h is not None:
            n_file += 1
        else:
            c = climate.get(r['date'])
            if c:
                t, h = c[0], c[1]
                e = e if e is not None else c[2]
                n_wh += 1
            else:
                n_none += 1
        train_records.append({
            "date": _date_str(r['date']),
            "real_value": float(r['real_value']),
            "prediction": float(r['prediction']),
            "price": _num_or_none(r.get('price')),
            "temperature": t,
            "humidity": h,
            "ethylene": e,
        })
    yield (f"[Django] [2/3] Previsões obtidas. Clima por dia: {n_file} do ficheiro, {n_wh} das leituras do armazém "
           f"'{wh.location}', {n_none} sem dados (usados 22 °C / 70 % por omissão).\n")

    episodes = int(max_episodes) if str(max_episodes or '').strip().isdigit() else BUYER_EPISODES_DEFAULT
    payload = {
        "user_id": user.id, "culture_id": subfamily.pk, "fruit_key": fruit_key or _fruit_key(subfamily),
        "owner_type": _owner_type(user), "max_capacity": capacity, "episodes": episodes, "risk_factor": 0.85,
        "train_data": train_records,
    }
    yield f"[Django] [3/3] A treinar o Buyer Agent DSAC Limitado (30 variáveis, {episodes} episódios, capacidade {capacity:.0f} Kg) no Buyer Web Service :8002...\n"

    try:
        resp = requests.post(f"{BUYER_SERVICE_URL}/api/buyer/train/stream", json=payload, timeout=(10, 3600), stream=True)
    except requests.exceptions.ConnectionError:
        raise ConnectionError(f"Não foi possível ligar ao Buyer Agent Web Service em {BUYER_SERVICE_URL}. O serviço deve estar online para realizar o treino.")
    if resp.status_code != 200:
        raise RuntimeError(f"Erro no Buyer Agent Web Service: {_service_error(resp)}")

    final_result = None
    for line in resp.iter_lines(decode_unicode=True):
        if not line or not line.startswith('data: '):
            continue
        try:
            data = json.loads(line[6:])
        except ValueError:
            continue
        if 'episode' in data and 'total_episodes' in data:
            ep, total_ep = data['episode'], data['total_episodes']
            msg = f"[WS:8002] Episódio {ep}/{total_ep} ({round(100.0 * ep / total_ep)}%) | Lucro Episódio: {data.get('episode_profit')} € | Média (20ep): {data.get('avg_profit')} €"
            if 'eval_profit' in data:
                msg += f" | Avaliação: {data['eval_profit']} €" + (" ★ novo melhor" if data.get('new_best') else "")
            yield msg + "\n"
        elif data.get('event') == 'error':
            raise RuntimeError(f"Erro no Buyer Agent Web Service: {data.get('detail')}")
        elif data.get('event') == 'done':
            final_result = data
            yield f"[Django] [Sucesso] {data.get('message')}\n"
            m = data.get('best_eval_metrics') or {}
            yield f"[Django] Melhor avaliação: lucro {data.get('avg_profit')} € | vendas {m.get('sales')} | rutura {m.get('missed_sales')} | desperdício {m.get('waste')} | {data.get('training_time_seconds')}s\n"
    if final_result is None:
        raise RuntimeError("O stream de treino terminou sem resultado final.")

    TrainedModel.objects.update_or_create(owner=user, culture=subfamily, model_type='buyer_agent',
                                          defaults={'file_name': 'dsac_best_actor.pth', 'file_data': b'web_service_remote_model'})
    yield "[Django] Marcador de modelo sincronizado na base de dados com sucesso.\n"


def train_buyer_agent_optimizer(user, subfamily, df_market_data, max_episodes=None, fruit_key=None, forecast_model_type=None):
    return list(train_buyer_agent_optimizer_generator(user, subfamily, df_market_data, max_episodes=max_episodes,
                                                      fruit_key=fruit_key, forecast_model_type=forecast_model_type))


def _lot_initial_state(reception, today):
    """Estado inicial do lote para o Buyer Agent (regra comum: reception_service.reception_initial_state)."""
    from dashboard.services.reception_service import reception_initial_state
    st = reception_initial_state(reception)
    lot = {"age_days": max(0, (today - st["start_date"]).days), "initial_source": st["source"]}
    for k in ("firmness", "brix", "acidity"):
        if st[k] is not None:
            lot[k] = st[k]
    return lot


def _stock_and_transit(user, subfamily, today, stock_total):
    """
    Estado de stock para a decisão do Buyer Agent, a partir das receções de mercadoria (DealReception):
      - em trânsito: receções PENDENTES desta cultura (chegada pela data prevista; sem data, amanhã);
      - lotes: receções CONFIRMADAS mais recentes até perfazer o stock atual (consumo FEFO: o mais antigo sai primeiro),
        com o estado inicial medido (receção > colheita > valores por omissão; ver _lot_initial_state). O stock que não corresponde a nenhuma receção (ex.: compra rápida
        ou ajuste manual) entra como um lote com idade 0.
      - última encomenda: quantidade do negócio mais recente desta cultura.
    """
    from dashboard.models import DealReception

    receptions = DealReception.objects.filter(buyer=user, culture=subfamily)

    in_transit = []
    for r in receptions.filter(status=DealReception.STATUS_PENDING):
        qty = float(r.quantity_kg or 0.0)
        if qty <= 0:
            continue
        arrival = max(0, (r.expected_date - today).days) if r.expected_date else 1
        in_transit.append({"quantity_kg": qty, "arrival_in_days": arrival})

    lots, remaining = [], float(stock_total)
    received = receptions.filter(status=DealReception.STATUS_RECEIVED, received_at__lte=today).order_by('-received_at', '-confirmed_at')
    for r in received:
        if remaining <= 0:
            break
        take = min(float(r.received_quantity_kg or r.quantity_kg or 0.0), remaining)
        if take <= 0:
            continue
        lots.append({"quantity_kg": round(take, 2), **_lot_initial_state(r, today)})
        remaining -= take
    if remaining > 0.01:
        lots.append({"quantity_kg": round(remaining, 2), "age_days": 0})

    last = receptions.order_by('-created_at').first()
    last_order = float(last.quantity_kg) if last else 0.0
    return lots, in_transit, last_order


def get_buyer_agent_decision_details(user, subfamily, max_capacity=None):
    """
    Decisão de encomenda para hoje no Buyer Web Service (/api/buyer/decide).
    O estado é construído no serviço pelo ambiente DSAC original a partir de:
    histórico recente com previsões, previsão de hoje e dos próximos 20 dias, lotes em stock, trânsito e clima.
    """
    today = timezone.now().date()
    wh = _buyer_warehouse(user, subfamily)

    # Se o histórico carregado termina antes de ontem, a decisão é feita para o dia seguinte à última venda
    # (assim os lags e as previsões usam dias consecutivos, como no treino).
    last_sale = HistoricalSalesData.objects.filter(owner=user, culture=subfamily, date__lt=today).order_by('-date').first()
    if last_sale and last_sale.date < today - datetime.timedelta(days=1):
        today = last_sale.date + datetime.timedelta(days=1)

    sales = list(HistoricalSalesData.objects.filter(owner=user, culture=subfamily, date__lt=today)
                 .order_by('-date').values('date', 'sales_quantity_kg', 'price_per_kg')[:HISTORY_DAYS_FOR_PREDICT])[::-1]
    if len(sales) < 2:
        raise ValueError(f"São necessários pelo menos 2 dias de vendas registadas para '{subfamily.name}' antes de pedir uma decisão.")

    status = get_buyer_model_status(user, subfamily)
    if not status.get('has_model'):
        raise ValueError(f"O Buyer Agent ainda não foi treinado para '{subfamily.name}'.")
    fc_key = _default_forecast_model(user, subfamily)

    # Previsões: histórico (a 1 dia, como no treino) + hoje e próximos 20 dias (recursivo)
    pred_map = forecast_series(user, subfamily, sales, fc_key)
    _, future, _ = forecast_horizon(user, subfamily, today, 21, model_type=fc_key, history_rows=sales)
    if not future:
        raise RuntimeError("O Forecast Web Service não devolveu previsões para hoje.")

    climate = _climate_by_date(wh, sales[0]['date'], today)
    today_clim = climate.get(today) or _latest_climate(wh, today)
    last_price = next((float(s['price_per_kg']) for s in reversed(sales) if s['price_per_kg']), None)

    history = []
    for s in sales[-30:]:
        c = climate.get(s['date'])
        history.append({"date": _date_str(s['date']), "real_value": float(s['sales_quantity_kg']),
                        "prediction": pred_map.get(_date_str(s['date']), float(s['sales_quantity_kg'])),
                        "price": float(s['price_per_kg']) if s['price_per_kg'] else None,
                        "temperature": c[0] if c else None, "humidity": c[1] if c else None, "ethylene": c[2] if c else None})
    today_ctx = {"date": _date_str(today), "prediction": float(future[0]['predicted_kg']), "price": last_price,
                 "temperature": today_clim[0] if today_clim else None, "humidity": today_clim[1] if today_clim else None,
                 "ethylene": today_clim[2] if today_clim else None}
    forecast = [{"date": p['date'], "prediction": float(p['predicted_kg'])} for p in future[1:]]

    stock_total = float(sum(float(s.quantity) for s in ConsolidatedStock.objects.filter(owner=user, culture=subfamily)))
    lots, in_transit, last_order = _stock_and_transit(user, subfamily, today, stock_total)

    consecutive_oos = 0
    for s in reversed(sales[-10:]):
        if float(s['sales_quantity_kg'] or 0) <= 0.01:
            consecutive_oos += 1
        else:
            break

    payload = {"user_id": user.id, "culture_id": subfamily.pk, "history": history, "today": today_ctx, "forecast": forecast,
               "stock_lots": lots, "in_transit": in_transit, "last_order_qty": last_order,
               "consecutive_oos_days": consecutive_oos}
    try:
        resp = requests.post(f"{BUYER_SERVICE_URL}/api/buyer/decide", json=payload, timeout=60)
    except requests.exceptions.ConnectionError:
        raise ConnectionError(f"O Buyer Agent Web Service está inacessível em {BUYER_SERVICE_URL}. A inferência só pode ser executada quando o microserviço estiver online.")
    if resp.status_code != 200:
        raise RuntimeError(f"Erro no Buyer Agent Web Service: {_service_error(resp)}")
    data = resp.json()
    data["culture_name"] = subfamily.name
    data["price_today"] = last_price or 0.0
    data["forecast_model"] = FORECAST_MODEL_NAMES[fc_key]
    data.setdefault("state_summary", {})["rsl_days"] = data["state_summary"].get("min_rsl_days")
    return data


def compute_daily_agent_decision(user, subfamily, max_capacity=None):
    return float(get_buyer_agent_decision_details(user, subfamily, max_capacity=max_capacity).get('recommended_order_kg', 0.0))
