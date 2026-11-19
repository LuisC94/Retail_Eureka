"""
Validação do Buyer Agent já treinado nos últimos dias do histórico ("teste no passado").

  1. Ordena o histórico e usa os últimos `test_fraction` dias (por omissão 20 %) como período de teste.
  2. Com o modelo de produção (sem treinar nada), simula dia a dia, com as mesmas vendas reais, preços e clima:
       - Buyer Agent (decisão determinística, como em produção);
       - Reposição do défice (encomenda a previsão de amanhã menos o que sobra e o que está a caminho);
       - Cobertura de 3 dias de previsão;
       - Mín-Máx (mín. 2 dias, máx. 5 dias de procura prevista).
     As regras de referência são as mesmas da recomendação diária (engine/heuristics.py).
     Todas usam o mesmo simulador (ambiente original + Lifecycle LC), com o mesmo limite de encomenda e capacidade.
  3. Guarda um relatório (validation_report.json) com totais e séries diárias, junto do modelo.

Nota: o treino de produção ajusta os pesos com os primeiros 60 % dos dias que recebe e escolhe o melhor modelo
com os restantes 40 %. O relatório indica se o período de teste se sobrepõe a esses dias (quando as datas são conhecidas).
"""
import datetime
import json
import os
import sys

import numpy as np
import torch

_REF_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reference")
if _REF_DIR not in sys.path:
    sys.path.insert(0, _REF_DIR)

from dsac_agent import DSACAgent  # noqa: E402  (ficheiro original)

from .environment_lc import StockEnvironmentLC  # noqa: E402
from .heuristics import heuristic_orders  # noqa: E402
from .decider import load_meta  # noqa: E402
from .trainer import ACTION_DIM, NUM_QUANTILES, STATE_DIM, validate_training_frame  # noqa: E402

DEFAULT_TEST_FRACTION = 0.2
MIN_TEST_DAYS = 14
REPORT_FILE = "validation_report.json"
FORECAST_WINDOW = 20

POLICIES = [
    ("buyer_agent", "Buyer Agent"),
    ("forecast_tomorrow", "Reposição do défice"),
    ("cover_3d", "Cobertura de 3 dias"),
    ("min_max", "Mín-Máx"),
]


def split_index(n_days, test_fraction):
    return int(round(n_days * (1.0 - float(test_fraction))))


def check_split(n_days, test_fraction):
    if not 0.05 <= float(test_fraction) <= 0.5:
        raise ValueError("A percentagem de teste tem de estar entre 5 % e 50 %.")
    split = split_index(n_days, test_fraction)
    if n_days - split < MIN_TEST_DAYS:
        raise ValueError(f"O período de teste teria só {n_days - split} dias; são precisos pelo menos {MIN_TEST_DAYS}.")
    return split


def _load_actor(model_dir, risk_factor):
    agent = DSACAgent(state_dim=STATE_DIM, action_dim=ACTION_DIM, num_quantiles=NUM_QUANTILES,
                      risk_factor=risk_factor, device="cpu")
    agent.load(model_dir, filename_prefix="dsac_best")
    agent.actor.eval()
    return agent


def _test_env(df, split, meta):
    # train_split tal que int(len * train_split) == split (o ambiente original corta assim)
    env = StockEnvironmentLC(df, is_training=False, train_split=(split + 0.5) / len(df),
                             max_capacity=meta["max_capacity"], completely_unconstrained=False,
                             owner_type=meta.get("owner_type", "Retailer"), packaging=meta.get("packaging", "bulk"),
                             lc_model=meta.get("lc_model"))
    # Mesmo limite de encomenda do modelo avaliado (como em /decide)
    env.max_order_limit = float(meta["max_order_limit"])
    return env


def _heuristic_inputs(env):
    step = env.current_step
    preds = env.data["prediction"]
    return (float(sum(env.stock_profile)), float(sum(env.in_transit.values())), float(preds.iloc[step]),
            preds.iloc[step + 1: step + 1 + FORECAST_WINDOW].tolist())


def _decide_fn(key, agent):
    if key == "buyer_agent":
        def fn(env, state):
            with torch.no_grad():
                action_norm = agent.select_action(state, evaluate=True)
            return round(0.5 * (float(action_norm[0]) + 1.0) * env.max_order_limit)
        return fn
    field = {"forecast_tomorrow": "cnn_naive_kg", "cover_3d": "dos_3d_kg", "min_max": "min_max_kg"}[key]

    def fn(env, state):
        return round(heuristic_orders(*_heuristic_inputs(env))[field])
    return fn


def _simulate(df, split, meta, key, agent):
    env = _test_env(df, split, meta)
    decide = _decide_fn(key, agent)
    state = env.reset()
    done = False
    days = []
    while not done:
        day = env.data.iloc[env.current_step]["day"]
        order = decide(env, state)
        state, _, done, info = env.step(order, update_stats=False)
        days.append({
            "date": day.strftime("%Y-%m-%d"),
            "order": float(info["order_placed"]),
            "demand": float(info["real_demand"]),
            "sales": float(info["sales"]),
            "missed": float(info["missed_sales"]),
            "waste": float(info["overflow_waste"]),
            "stock": float(info["final_stock"]),
            "profit": float(info["commercial_profit"]),
            "transport_cost": float(info["transport_cost"]),
            "storage_cost": float(info["storage_cost"]),
        })
    return days


def _totals(days):
    demand = sum(d["demand"] for d in days)
    sales = sum(d["sales"] for d in days)
    return {
        "profit": round(sum(d["profit"] for d in days), 2),
        "demand_kg": round(demand, 1),
        "sales_kg": round(sales, 1),
        "missed_kg": round(sum(d["missed"] for d in days), 1),
        "waste_kg": round(sum(d["waste"] for d in days), 1),
        "ordered_kg": round(sum(d["order"] for d in days), 1),
        "service_level_pct": round(100.0 * sales / demand, 1) if demand > 0 else 100.0,
        "stockout_days": int(sum(1 for d in days if d["missed"] > 1e-6)),
        "avg_stock_kg": round(float(np.mean([d["stock"] for d in days])), 1) if days else 0.0,
        "transport_cost": round(sum(d["transport_cost"] for d in days), 2),
        "storage_cost": round(sum(d["storage_cost"] for d in days), 2),
    }


def backtest(df, split, model_dir, meta, progress_cb=None):
    """Simula as políticas no período de teste df[split:] com o modelo guardado em model_dir."""
    agent = _load_actor(model_dir, meta.get("risk_factor", 0.85))
    results = {}
    for i, (key, label) in enumerate(POLICIES, start=1):
        if progress_cb:
            progress_cb({"event": "backtest", "step": i, "total_steps": len(POLICIES), "policy": label})
        results[key] = _simulate(df, split, meta, key, agent)

    dates = [d["date"] for d in results["buyer_agent"]]
    policies, daily = [], {"dates": dates}
    for key, label in POLICIES:
        days = results[key]
        policies.append({"key": key, "label": label, "totals": _totals(days)})
        daily[key] = {
            "cum_profit": [round(float(x), 2) for x in np.cumsum([d["profit"] for d in days])],
            "stock": [round(d["stock"], 1) for d in days],
            "order": [round(d["order"], 1) for d in days],
            "missed": [round(d["missed"], 1) for d in days],
            "waste": [round(d["waste"], 1) for d in days],
        }
    daily["demand"] = [round(d["demand"], 1) for d in results["buyer_agent"]]
    return policies, daily


def run_validation(df, model_dir, test_fraction=DEFAULT_TEST_FRACTION, progress_cb=None):
    """
    Simula o modelo JÁ TREINADO (produção, em model_dir) e as regras clássicas nos últimos `test_fraction` dias.
    Não treina nada: o modelo e o meta.json ficam iguais. O relatório fica em model_dir/validation_report.json.
    """
    meta = load_meta(model_dir)
    if not meta or not os.path.exists(os.path.join(model_dir, "dsac_best_actor.pth")):
        raise ValueError("Não existe modelo do Buyer Agent treinado para esta cultura. Treine o agente primeiro.")
    df = validate_training_frame(df)
    split = check_split(len(df), test_fraction)
    test_from, test_to = df["day"].iloc[split].strftime("%Y-%m-%d"), df["day"].iloc[-1].strftime("%Y-%m-%d")
    if progress_cb:
        progress_cb({"event": "split", "days_total": len(df), "days_before": split, "days_test": len(df) - split,
                     "test_from": test_from, "test_to": test_to})

    policies, daily = backtest(df, split, model_dir, meta, progress_cb=progress_cb)
    agent_totals = policies[0]["totals"]

    # Sobreposição do período de teste com os dias usados no treino do modelo (só conhecido em treinos recentes)
    fit_to = meta.get("weights_train_to")
    overlap = None
    if fit_to:
        overlap = "weights" if test_from <= fit_to else (
            "selection" if meta.get("selection_to") and test_from <= meta["selection_to"] else "none")
    report = {
        "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "test_fraction": float(test_fraction),
        "days_total": int(len(df)),
        "days_test": int(len(df) - split),
        "simulated_days": len(daily["dates"]),
        "test_from": test_from,
        "test_to": test_to,
        "model": {
            "trained_at": meta.get("trained_at"), "episodes": meta.get("episodes"),
            "days_train": meta.get("days_train"), "days_eval": meta.get("days_eval"),
            "weights_train_from": meta.get("weights_train_from"), "weights_train_to": fit_to,
            "selection_from": meta.get("selection_from"), "selection_to": meta.get("selection_to"),
        },
        "overlap": overlap,
        "fruit_key": meta["fruit_key"],
        "lifecycle_engine": meta.get("lifecycle_engine"),
        "max_order_limit": meta["max_order_limit"],
        "max_capacity": meta["max_capacity"],
        "policies": policies,
        "vs_agent": {
            p["key"]: {
                "profit_diff": round(agent_totals["profit"] - p["totals"]["profit"], 2),
                "waste_diff_kg": round(agent_totals["waste_kg"] - p["totals"]["waste_kg"], 1),
                "missed_diff_kg": round(agent_totals["missed_kg"] - p["totals"]["missed_kg"], 1),
            } for p in policies[1:]
        },
        "daily": daily,
    }
    with open(os.path.join(model_dir, REPORT_FILE), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False)
    return report


def load_report(model_dir):
    path = os.path.join(model_dir, REPORT_FILE)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)
