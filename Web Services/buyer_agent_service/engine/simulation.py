"""
Simulação interativa, dia a dia, do Buyer Agent já treinado (não treina nem altera o modelo).

Ciclo de cada dia D (o mesmo do ambiente de treino, StockEnvironment.step):
  1. Com as condições do dia D (previsão de hoje e de amanhã, preço, temperatura, humidade) e o estado do armazém
     (lotes com idade/qualidade, encomendas a caminho), o modelo recomenda a encomenda de D (chega em D+1).
     As regras clássicas (engine/heuristics.py) são mostradas ao lado.
  2. O utilizador indica a encomenda feita e a procura real do dia D.
  3. O simulador processa o dia (chegadas, vendas FEFO, envelhecimento LC, custos) e passa ao dia D+1,
     cujas condições o utilizador pode alterar antes de pedir a nova recomendação.

Guarda-se apenas o histórico de dias (com as alterações do utilizador) e as encomendas; o estado do armazém é
reconstruído em cada pedido repetindo os dias desde o início com o mesmo simulador (determinístico).
O estado fica em model_dir/simulation.json (uma simulação por utilizador e cultura).
"""
import datetime
import json
import math
import os

import numpy as np
import pandas as pd
import torch

from .decider import load_agent, load_meta
from .environment_lc import StockEnvironmentLC
from .heuristics import heuristic_orders

SIM_FILE = "simulation.json"
FORECAST_WINDOW = 20
DEFAULT_INITIAL_STOCK = 100.0   # o mesmo lote inicial do ambiente de treino (stock_inicial)
MIN_CONTEXT_DAYS = 2            # o estado usa a procura real de ontem e anteontem
CONDITION_FIELDS = ("prediction", "price", "temperature", "humidity")


class SimulationError(ValueError):
    pass


# ------------------------------------------------------------------ ficheiro
def _path(model_dir):
    return os.path.join(model_dir, SIM_FILE)


def load_sim(model_dir):
    p = _path(model_dir)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save_sim(model_dir, sim):
    tmp = _path(model_dir) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(sim, f, ensure_ascii=False)
    os.replace(tmp, _path(model_dir))


def delete_sim(model_dir):
    if os.path.exists(_path(model_dir)):
        os.remove(_path(model_dir))


def _num(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) else v


def _require_model(model_dir):
    meta = load_meta(model_dir)
    if not meta or not os.path.exists(os.path.join(model_dir, "dsac_best_actor.pth")):
        raise SimulationError("Não existe modelo do Buyer Agent treinado para esta cultura. Treine o agente primeiro.")
    return meta


# ------------------------------------------------------------------ início
def start_simulation(model_dir, df, start_date=None, initial_stock_kg=None, test_fraction=0.2):
    """
    df: histórico já normalizado (colunas day, real_value, prediction, price, temperature, humidity, ethylene).
    start_date: primeiro dia a simular; por omissão, o primeiro dia dos últimos `test_fraction` do histórico.
    """
    meta = _require_model(model_dir)
    df = df.sort_values("day").reset_index(drop=True)
    days = pd.to_datetime(df["day"]).dt.strftime("%Y-%m-%d").tolist()
    if start_date:
        start = next((i for i, d in enumerate(days) if d >= str(start_date)[:10]), None)
        if start is None:
            raise SimulationError(f"A data de início ({start_date}) é posterior ao último dia do histórico ({days[-1]}).")
    else:
        start = int(round(len(days) * (1.0 - float(test_fraction))))
    if start < MIN_CONTEXT_DAYS:
        raise SimulationError(f"A simulação tem de começar pelo menos {MIN_CONTEXT_DAYS} dias depois do início do histórico ({days[MIN_CONTEXT_DAYS]}).")
    stock0 = DEFAULT_INITIAL_STOCK if initial_stock_kg in (None, "") else float(initial_stock_kg)
    if stock0 < 0 or stock0 > float(meta["max_capacity"]):
        raise SimulationError(f"O stock inicial tem de estar entre 0 e a capacidade do armazém ({meta['max_capacity']:.0f} kg).")

    rows = []
    for i, r in enumerate(df.itertuples(index=False)):
        row = {"date": days[i], "real_value": _num(r.real_value), "prediction": float(r.prediction),
               "price": float(r.price), "temperature": float(r.temperature), "humidity": float(r.humidity),
               "ethylene": float(r.ethylene)}
        row["hist"] = {k: row[k] for k in ("real_value", "prediction", "price", "temperature", "humidity")}
        rows.append(row)
    sim = {
        "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "model_trained_at": meta.get("trained_at"),
        "fruit_key": meta["fruit_key"],
        "start_index": start,
        "history_days": len(rows),
        "initial_stock_kg": stock0,
        "rows": rows,
        "orders": [],
    }
    save_sim(model_dir, sim)
    return sim


# ------------------------------------------------------------------ reconstrução do estado
def _frame(sim):
    df = pd.DataFrame([{k: r.get(k) for k in ("date", "real_value", "prediction", "price", "temperature", "humidity", "ethylene")}
                       for r in sim["rows"]]).rename(columns={"date": "day"})
    df["day"] = pd.to_datetime(df["day"])
    df["real_value"] = pd.to_numeric(df["real_value"], errors="coerce")
    df["volume"] = 0.002
    df["fruit_type"] = sim["fruit_key"]
    return df


def _env(sim, meta):
    # train_split=0: o ambiente usa o histórico completo, com o mesmo índice de dias do treino (calendário do estado)
    env = StockEnvironmentLC(_frame(sim), is_training=False, train_split=0.0, max_capacity=meta["max_capacity"],
                             completely_unconstrained=False, owner_type=meta.get("owner_type", "Retailer"),
                             packaging=meta.get("packaging", "bulk"), lc_model=meta.get("lc_model"))
    env.max_order_limit = float(meta["max_order_limit"])
    env.reset(start_step=sim["start_index"])
    stock0 = float(sim.get("initial_stock_kg", DEFAULT_INITIAL_STOCK))
    if stock0 != env.stock_inicial:
        env.active_batches = [env.make_batch(stock0)] if stock0 > 0 else []
        env._next_lot_id = 2
        env._update_stock_profile_from_batches()
    return env


def _agent_order(agent, env, state):
    with torch.no_grad():
        action_norm = agent.select_action(state, evaluate=True)
    pct = 0.5 * (float(action_norm[0]) + 1.0)
    return float(round(pct * env.max_order_limit)), pct


def _heuristics(env):
    step = env.current_step
    preds = env.data["prediction"]
    return heuristic_orders(float(sum(env.stock_profile)), float(sum(env.in_transit.values())), float(preds.iloc[step]),
                            preds.iloc[step + 1: step + 1 + FORECAST_WINDOW].tolist())


def replay(model_dir, sim):
    """Repete os dias já simulados e devolve (env no dia atual, agente, meta, resultados diários)."""
    meta = _require_model(model_dir)
    agent = load_agent(model_dir)
    env = _env(sim, meta)
    days, cum = [], 0.0
    for order in sim["orders"]:
        state = env._get_state()
        rec, _ = _agent_order(agent, env, state)
        date = sim["rows"][env.current_step]["date"]
        _, _, _, info = env.step(float(order), update_stats=False)
        cum += float(info["commercial_profit"])
        days.append({
            "date": date, "recommended": rec, "entered": float(order), "ordered": float(info["order_placed"]),
            "arrived": float(info["arrived_today"]), "demand": float(info["real_demand"]), "sales": float(info["sales"]),
            "missed": float(info["missed_sales"]), "waste": float(info["overflow_waste"]), "stock": float(info["final_stock"]),
            "profit": float(info["commercial_profit"]), "cum_profit": cum,
        })
    return env, agent, meta, days


# ------------------------------------------------------------------ vista para a interface
def _r(v, d=1):
    return None if v is None else round(float(v), d)


def build_view(model_dir, sim):
    env, agent, meta, days = replay(model_dir, sim)
    cur = env.current_step
    rows = sim["rows"]
    row = rows[cur]
    nxt = rows[cur + 1] if cur + 1 < len(rows) else None

    state = env._get_state()
    rec, pct = _agent_order(agent, env, state)
    stock_total = float(sum(env.stock_profile))
    free_cap = max(0.0, float(env.max_capacity) - sum(b["quantity"] for b in env.active_batches if b["quantity"] > 0))

    lots = []
    for b in sorted(env.active_batches, key=lambda b: -float(b.get("age", 0))):
        if b["quantity"] <= 0:
            continue
        lots.append({"lot_id": b.get("lot_id"), "quantity_kg": _r(b["quantity"]), "age_days": int(b.get("age", 0)),
                     "quality": _r(b.get("quality", 100.0)), "rsl_days": int(env.project_batch_rsl(b))})
    in_transit = [{"date": rows[k]["date"] if k < len(rows) else None, "days": int(k - cur), "kg": _r(v)}
                  for k, v in sorted(env.in_transit.items()) if v > 0]

    hist = row.get("hist") or {}
    edited = [k for k in CONDITION_FIELDS if hist and row.get(k) != hist.get(k)]
    if nxt and nxt.get("hist") and nxt.get("prediction") != nxt["hist"].get("prediction"):
        edited.append("prediction_tomorrow")
    demand_default = row.get("real_value") if row.get("real_value") is not None else hist.get("real_value")

    total = lambda k: sum(d[k] for d in days)  # noqa: E731
    demand = total("demand")
    totals = {
        "days": len(days), "profit": _r(total("profit"), 2), "demand_kg": _r(demand), "sales_kg": _r(total("sales")),
        "missed_kg": _r(total("missed")), "waste_kg": _r(total("waste")), "ordered_kg": _r(total("ordered")),
        "service_level_pct": _r(100.0 * total("sales") / demand) if demand > 0 else None,
        "followed_agent_days": int(sum(1 for d in days if abs(d["entered"] - d["recommended"]) < 0.5)),
    }
    for d in days:
        for k in list(d):
            if k != "date":
                d[k] = _r(d[k], 2 if k in ("profit", "cum_profit") else 1)

    return {
        "created_at": sim["created_at"],
        "start_date": rows[sim["start_index"]]["date"],
        "history_last_date": rows[sim["history_days"] - 1]["date"],
        "model_trained_at": meta.get("trained_at"),
        "model_changed": bool(sim.get("model_trained_at") and sim["model_trained_at"] != meta.get("trained_at")),
        "initial_stock_kg": sim.get("initial_stock_kg"),
        "max_order_limit": float(env.max_order_limit),
        "max_capacity": float(env.max_capacity),
        "current": {
            "date": row["date"],
            "day_number": len(days) + 1,
            "in_history": cur < sim["history_days"],
            "conditions": {
                "prediction": _r(row["prediction"]), "prediction_tomorrow": _r(nxt["prediction"]) if nxt else _r(sim.get("tomorrow_prediction")),
                "price": _r(row["price"], 2), "temperature": _r(row["temperature"]), "humidity": _r(row["humidity"]),
            },
            "history": {k: _r(v, 2 if k == "price" else 1) for k, v in hist.items()} if hist else None,
            "edited": edited,
            "demand_default": _r(demand_default),
        },
        "state": {
            "stock_kg": _r(stock_total), "stock_profile_kg": [_r(x) for x in env.stock_profile],
            "in_transit": in_transit, "lots": lots, "free_capacity_kg": _r(free_cap),
            "consecutive_oos_days": int(env.consecutive_oos_days), "last_order_kg": _r(env.last_order_qty),
            "coverage_days": _r(stock_total / row["prediction"], 2) if row["prediction"] > 0 else None,
        },
        "recommendation": {
            "buyer_agent_kg": rec, "order_percentage": round(pct, 4),
            "max_effective_kg": _r(min(float(env.max_order_limit), free_cap)),
            "heuristics": _heuristics(env),
        },
        "days": days,
        "totals": totals,
    }


# ------------------------------------------------------------------ ações
def _current_index(sim):
    return sim["start_index"] + len(sim["orders"])


def update_today(model_dir, sim, values):
    """Altera as condições do dia atual (e a previsão de amanhã) antes de pedir a recomendação."""
    cur = _current_index(sim)
    row = sim["rows"][cur]
    for k in CONDITION_FIELDS:
        v = _num(values.get(k))
        if v is None:
            continue
        if k in ("prediction", "price") and v < 0:
            raise SimulationError("A previsão e o preço não podem ser negativos.")
        if k == "humidity" and not 0 <= v <= 100:
            raise SimulationError("A humidade tem de estar entre 0 e 100 %.")
        row[k] = v
    t = _num(values.get("prediction_tomorrow"))
    if t is not None:
        if t < 0:
            raise SimulationError("A previsão de amanhã não pode ser negativa.")
        if cur + 1 < len(sim["rows"]):
            sim["rows"][cur + 1]["prediction"] = t
        else:
            sim["tomorrow_prediction"] = t
    save_sim(model_dir, sim)
    return sim


def advance_day(model_dir, sim, order_kg, demand_kg):
    """Fecha o dia atual com a encomenda feita e a procura real, e passa ao dia seguinte."""
    order, demand = _num(order_kg), _num(demand_kg)
    if order is None or order < 0:
        raise SimulationError("Indique a encomenda feita (kg, 0 ou mais).")
    if demand is None or demand < 0:
        raise SimulationError("Indique a procura real do dia (kg, 0 ou mais).")
    rows = sim["rows"]
    cur = _current_index(sim)
    rows[cur]["real_value"] = demand
    if cur + 1 >= len(rows):
        # Depois do fim do histórico: o dia seguinte começa com as condições de hoje (o utilizador ajusta-as)
        last = rows[cur]
        nd = (pd.Timestamp(last["date"]) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        pred = sim.pop("tomorrow_prediction", None)
        rows.append({"date": nd, "real_value": None, "prediction": float(pred if pred is not None else last["prediction"]),
                     "price": last["price"], "temperature": last["temperature"], "humidity": last["humidity"],
                     "ethylene": last["ethylene"], "hist": None})
    sim["orders"].append(order)
    save_sim(model_dir, sim)
    return sim


def undo_day(model_dir, sim):
    if not sim["orders"]:
        raise SimulationError("Não há dias para desfazer.")
    sim["orders"].pop()
    cur = _current_index(sim)
    # Remove os dias acrescentados depois do fim do histórico que ainda não foram simulados
    while len(sim["rows"]) > max(sim["history_days"], cur + 1) and sim["rows"][-1].get("hist") is None:
        sim["rows"].pop()
    save_sim(model_dir, sim)
    return sim
