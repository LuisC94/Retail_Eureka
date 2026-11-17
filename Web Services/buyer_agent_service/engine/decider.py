"""
Decisão de encomenda com um modelo DSAC treinado.

O vetor de estado (30 variáveis) é construído pelo próprio ambiente (StockEnvironment._get_state),
exatamente como no treino e no evaluate_dsac.py: monta-se um ambiente com o histórico recente,
o dia de hoje e as previsões futuras, posiciona-se no dia de hoje e injeta-se o stock real
(lotes com idade), o stock em trânsito, a última encomenda e os dias seguidos em rutura.
"""
import json
import os
import sys

import numpy as np
import pandas as pd
import torch

_REF_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reference")
if _REF_DIR not in sys.path:
    sys.path.insert(0, _REF_DIR)

from dsac_agent import DSACAgent  # noqa: E402  (ficheiro original)

from .environment_lc import StockEnvironmentLC  # noqa: E402
from .trainer import STATE_DIM, ACTION_DIM, NUM_QUANTILES  # noqa: E402

_AGENT_CACHE = {}


def load_meta(model_dir):
    path = os.path.join(model_dir, "meta.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def has_model(model_dir):
    meta = load_meta(model_dir)
    return bool(meta and meta.get("state_dim") == STATE_DIM and os.path.exists(os.path.join(model_dir, "dsac_best_actor.pth")))


def load_agent(model_dir):
    actor_path = os.path.join(model_dir, "dsac_best_actor.pth")
    mtime = os.path.getmtime(actor_path)
    cached = _AGENT_CACHE.get(model_dir)
    if cached and cached[0] == mtime:
        return cached[1]
    meta = load_meta(model_dir) or {}
    agent = DSACAgent(state_dim=STATE_DIM, action_dim=ACTION_DIM, num_quantiles=NUM_QUANTILES,
                      risk_factor=meta.get("risk_factor", 0.85), device="cpu")
    agent.load(model_dir, filename_prefix="dsac_best")
    agent.actor.eval()
    _AGENT_CACHE[model_dir] = (mtime, agent)
    return agent


def build_decision_env(meta, history, today, forecast, stock_lots, in_transit, last_order_qty, consecutive_oos_days):
    """
    history:   lista de dias passados [{date, real_value, prediction, price, temperature, humidity, ethylene}]
    today:     {date, prediction, price, temperature, humidity, ethylene}
    forecast:  previsões para os dias seguintes [{date, prediction}] (o ambiente usa até 20 dias)
    stock_lots:[{quantity_kg, age_days}]
    in_transit:[{quantity_kg, arrival_in_days}] com arrival_in_days >= 0 (0 = chega hoje, ainda não recebido)
    """
    fruit = meta["fruit_key"]
    rows = []
    for h in history:
        rows.append({"day": h["date"], "prediction": h["prediction"], "real_value": h["real_value"],
                     "price": h.get("price"), "temperature": h.get("temperature"), "humidity": h.get("humidity"),
                     "ethylene": h.get("ethylene"), "volume": h.get("volume")})
    rows.append({"day": today["date"], "prediction": today["prediction"], "real_value": np.nan,
                 "price": today.get("price"), "temperature": today.get("temperature"),
                 "humidity": today.get("humidity"), "ethylene": today.get("ethylene"), "volume": today.get("volume")})
    for f in forecast:
        rows.append({"day": f["date"], "prediction": f["prediction"], "real_value": np.nan, "price": today.get("price"),
                     "temperature": today.get("temperature"), "humidity": today.get("humidity"),
                     "ethylene": today.get("ethylene"), "volume": today.get("volume")})
    df = pd.DataFrame(rows)
    df["day"] = pd.to_datetime(df["day"])
    # Valores em falta: mesmos defaults que o ambiente usa quando a coluna não existe
    df["price"] = pd.to_numeric(df["price"], errors="coerce").ffill().bfill().fillna(10.0)
    df["temperature"] = pd.to_numeric(df["temperature"], errors="coerce").ffill().bfill().fillna(22.0)
    df["humidity"] = pd.to_numeric(df["humidity"], errors="coerce").ffill().bfill().fillna(70.0)
    df["ethylene"] = pd.to_numeric(df["ethylene"], errors="coerce").ffill().bfill().fillna(0.8)
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").ffill().bfill().fillna(0.002)
    df["fruit_type"] = fruit
    today_idx = len(history)

    env = StockEnvironmentLC(df, is_training=False, train_split=0.0, max_capacity=meta["max_capacity"],
                             completely_unconstrained=False, owner_type=meta.get("owner_type", "Retailer"),
                             packaging=meta.get("packaging", "bulk"), lc_model=meta.get("lc_model"))
    # Modo Limitado: o limite de encomenda é a maior venda do período de treino (guardado em meta.json),
    # não o máximo recalculado sobre o histórico enviado no pedido.
    env.max_order_limit = float(meta["max_order_limit"])
    env.reset(start_step=today_idx)

    # Clima dos dias anteriores a hoje (mais antigo primeiro) para envelhecer os lotes existentes:
    # um lote com N dias foi envelhecido nos N dias antes de hoje (igual ao ciclo step() do ambiente)
    clim = [(float(r.temperature), float(r.humidity), float(r.ethylene)) for r in df.iloc[:today_idx].itertuples()]
    env.active_batches = []
    for lot in stock_lots:
        qty = float(lot.get("quantity_kg", 0) or 0)
        if qty <= 0:
            continue
        age = int(max(0, lot.get("age_days", 0) or 0))
        env.active_batches.append(env.make_batch(qty, age_days=age, climate_history=clim[-age:] if age else None))

    env.in_transit = {}
    for t in in_transit:
        qty = float(t.get("quantity_kg", 0) or 0)
        # 0 = chega hoje mas ainda não deu entrada (no treino é a encomenda de ontem), 1 = amanhã, ...
        d = int(max(0, t.get("arrival_in_days", 0) or 0))
        if qty > 0:
            env.in_transit[today_idx + d] = env.in_transit.get(today_idx + d, 0.0) + qty
    env.last_order_qty = float(last_order_qty or 0.0)
    env.consecutive_oos_days = int(consecutive_oos_days or 0)
    # No ambiente original o perfil G0-G3 é recalculado no fim do step() do dia anterior (com o clima de ontem),
    # antes de current_step avançar. Reproduz-se o mesmo para o estado ser idêntico ao do treino.
    env.current_step = max(0, today_idx - 1)
    env._update_stock_profile_from_batches()
    env.current_step = today_idx
    return env


def decide(model_dir, **kwargs):
    meta = load_meta(model_dir)
    agent = load_agent(model_dir)
    env = build_decision_env(meta, **kwargs)
    state = env._get_state()
    with torch.no_grad():
        action_norm = agent.select_action(state, evaluate=True)
    action_pct = 0.5 * (float(action_norm[0]) + 1.0)
    order_qty = int(round(action_pct * env.max_order_limit))

    stock_total = float(sum(env.stock_profile))
    pred_today = float(kwargs["today"]["prediction"])
    lots_rsl = [int(env.project_batch_rsl(b)) for b in env.active_batches if b["quantity"] > 0]
    return {
        "recommended_order_kg": float(order_qty),
        "order_percentage": round(action_pct, 4),
        "state_summary": {
            "total_stock_kg": round(stock_total, 2),
            "stock_profile_kg": [round(float(x), 2) for x in env.stock_profile],
            "coverage_days": round(stock_total / (pred_today + 1e-8), 2) if pred_today > 0 else None,
            "urgency_index": round(float(env.stock_profile[3]) / (stock_total + 1e-8), 4) if stock_total > 0 else 0.0,
            "in_transit_kg": round(float(sum(env.in_transit.values())), 2),
            "forecast_today_kg": round(pred_today, 2),
            "forecast_tomorrow_kg": round(float(env.data.iloc[min(env.current_step + 1, env.max_steps)]["prediction"]), 2),
            "min_rsl_days": int(min(lots_rsl)) if lots_rsl else 0,
            "lots_rsl_days": lots_rsl,
        },
        "state_vector": [round(float(x), 6) for x in state],
        "model_metadata": {
            "algorithm": meta.get("algorithm"), "state_dim": STATE_DIM, "fruit_key": meta.get("fruit_key"),
            "lifecycle_engine": meta.get("lifecycle_engine"), "max_capacity": meta.get("max_capacity"),
            "max_order_limit": float(env.max_order_limit), "trained_at": meta.get("trained_at"),
            "best_eval_profit": meta.get("best_eval_profit"),
        },
    }
