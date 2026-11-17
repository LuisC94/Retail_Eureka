"""
Treino DSAC Limitado: replica fielmente C:\\buyerAgent\\DSAC\\train_dsac.py (modo por omissão, sem --deslimitado:
limite de encomenda = maior venda histórica do período de treino),
recebendo os dados em memória em vez de um Excel e guardando os modelos por utilizador/cultura.

Diferenças em relação ao script original (apenas de I/O):
  - dados recebidos como DataFrame (mesmas colunas do Excel original);
  - o número de episódios e a capacidade podem ser passados no pedido (defaults = valores originais);
  - progresso reportado por callback (para o streaming SSE) e sem gráficos matplotlib;
  - use_lc=True usa o ambiente com o Lifecycle LC v0.2.0 embutido (engine/environment_lc.py);
    use_lc=False usa o ambiente original sem alterações (para validação).
"""
import datetime
import json
import os
import random
import sys
import time

import numpy as np
import pandas as pd
import torch

_REF_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reference")
if _REF_DIR not in sys.path:
    sys.path.insert(0, _REF_DIR)

from dsac_agent import DSACAgent  # noqa: E402  (ficheiro original)
from replay_buffer import ReplayBuffer  # noqa: E402  (ficheiro original)
from environment_constrained import StockEnvironment  # noqa: E402  (ficheiro original)

from .environment_lc import StockEnvironmentLC, dataframe_to_source  # noqa: E402

# Hiperparâmetros originais (train_dsac.py)
STATE_DIM = 30
ACTION_DIM = 1
BATCH_SIZE = 256
WARMUP_STEPS = 500
MAX_EPISODES = 350
EVAL_INTERVAL = 10
BUFFER_SIZE = 300_000
NUM_QUANTILES = 32
TRAIN_SPLIT = 0.6
SEED = 1337
DEFAULT_CAPACITY = 500
DEFAULT_RISK = 0.85

REQUIRED_COLUMNS = ["day", "prediction", "real_value", "price", "fruit_type"]
MIN_DAYS = 30


def set_seed(seed=SEED):
    torch.manual_seed(seed)
    np.random.seed(seed)
    random.seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def evaluate_policy(agent, eval_env):
    """ Igual a evaluate_policy() de train_dsac.py """
    state = eval_env.reset()
    done = False
    total_profit = total_sales = total_lost = total_waste = 0.0
    while not done:
        action_norm = agent.select_action(state, evaluate=True)
        action_pct = 0.5 * (float(action_norm[0]) + 1.0)
        action_physical = round(action_pct * eval_env.max_order_limit)
        next_state, reward, done, info = eval_env.step(action_physical, update_stats=False)
        total_profit += info['profit']
        total_sales += info['sales']
        total_lost += info['missed_sales']
        total_waste += info['overflow_waste']
        state = next_state
    return {"profit": total_profit, "sales": total_sales, "missed_sales": total_lost, "waste": total_waste}


def validate_training_frame(df: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Colunas em falta nos dados de treino: {missing}")
    if len(df) < MIN_DAYS:
        raise ValueError(f"São necessários pelo menos {MIN_DAYS} dias de histórico (recebidos {len(df)}).")
    if df["prediction"].isna().any():
        raise ValueError("Existem dias sem previsão do Forecast ('prediction'). O Buyer Agent precisa sempre das previsões.")
    if df["real_value"].isna().any():
        raise ValueError("Existem dias sem vendas reais ('real_value').")
    df = df.copy()
    df["day"] = pd.to_datetime(df["day"])
    df = df.sort_values("day").reset_index(drop=True)
    return df


def build_envs(df, max_capacity, use_lc=True, owner_type="Retailer", packaging="bulk"):
    common = dict(train_split=TRAIN_SPLIT, max_capacity=max_capacity, completely_unconstrained=False)
    if use_lc:
        env_train = StockEnvironmentLC(df, is_training=True, owner_type=owner_type, packaging=packaging, **common)
        env_eval = StockEnvironmentLC(df, is_training=False, owner_type=owner_type, packaging=packaging,
                                      shared_stats={'econ': env_train.stat_profit}, lc_model=env_train.lc_model, **common)
    else:
        env_train = StockEnvironment(dataframe_to_source(df), is_training=True, **common)
        env_eval = StockEnvironment(dataframe_to_source(df), is_training=False,
                                    shared_stats={'econ': env_train.stat_profit}, **common)
    return env_train, env_eval


def train_dsac(df: pd.DataFrame, save_dir: str, max_capacity=DEFAULT_CAPACITY, risk_factor=DEFAULT_RISK,
               episodes=MAX_EPISODES, use_lc=True, owner_type="Retailer", packaging="bulk",
               progress_cb=None, device=None, extra_meta=None):
    """Treina o DSAC Limitado com o mesmo ciclo de train_dsac.py e guarda dsac_best_* / dsac_latest_* + meta.json."""
    t0 = time.time()
    df = validate_training_frame(df)
    set_seed(SEED)
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")

    env_train, env_eval = build_envs(df, max_capacity, use_lc=use_lc, owner_type=owner_type, packaging=packaging)
    max_order_limit = env_train.max_order_limit

    agent = DSACAgent(state_dim=STATE_DIM, action_dim=ACTION_DIM, gamma=0.99, tau=0.005, lr_actor=3e-4,
                      lr_critic=3e-4, lr_alpha=3e-4, num_quantiles=NUM_QUANTILES, risk_factor=risk_factor,
                      device=device)
    replay_buffer = ReplayBuffer(state_dim=STATE_DIM, action_dim=ACTION_DIM, max_size=BUFFER_SIZE, device=device)
    os.makedirs(save_dir, exist_ok=True)

    train_profits, eval_history = [], []
    best_eval_profit = -float("inf")
    best_metrics = None
    total_steps = 0

    for episode in range(1, int(episodes) + 1):
        state = env_train.reset()
        done = False
        episode_profit = 0.0
        while not done:
            total_steps += 1
            if total_steps < WARMUP_STEPS:
                action_norm = np.random.uniform(-1.0, 1.0, size=(ACTION_DIM,)).astype(np.float32)
            else:
                action_norm = agent.select_action(state, evaluate=False)
            action_pct = 0.5 * (float(action_norm[0]) + 1.0)
            physical_action = round(action_pct * max_order_limit)
            next_state, _, done, info = env_train.step(physical_action)
            episode_profit += info.get('commercial_profit', info['profit'])
            reward_stationary = float(np.clip(info['profit'] / 100.0, -10.0, 10.0))
            replay_buffer.push(state, action_norm, reward_stationary, next_state, done)
            state = next_state
            if total_steps >= WARMUP_STEPS:
                agent.update(replay_buffer, batch_size=BATCH_SIZE)

        train_profits.append(float(episode_profit))
        event = {"episode": episode, "total_episodes": int(episodes), "episode_profit": round(float(episode_profit), 2)}

        if episode % EVAL_INTERVAL == 0:
            m = evaluate_policy(agent, env_eval)
            eval_history.append({"episode": episode, **{k: round(float(v), 2) for k, v in m.items()}})
            event["eval_profit"] = round(float(m["profit"]), 2)
            if m["profit"] > best_eval_profit:
                best_eval_profit = float(m["profit"])
                best_metrics = m
                agent.save(save_dir, filename_prefix="dsac_best")
                event["new_best"] = True
            agent.save(save_dir, filename_prefix="dsac_latest")

        if progress_cb:
            progress_cb(event)

    # Garantir que existe sempre um modelo "best" (se episodes < EVAL_INTERVAL)
    if best_metrics is None:
        best_metrics = evaluate_policy(agent, env_eval)
        best_eval_profit = float(best_metrics["profit"])
        agent.save(save_dir, filename_prefix="dsac_best")
        agent.save(save_dir, filename_prefix="dsac_latest")

    meta = {
        "algorithm": "DSAC_Limitado",
        "state_dim": STATE_DIM,
        "fruit_key": getattr(env_train, "lc_fruit_key", env_train.fruit_key),
        "lifecycle_engine": f"LC v0.2.0 (modelo {env_train.lc_model})" if use_lc else "FruitModel2 (original)",
        "lc_model": getattr(env_train, "lc_model", None),
        "owner_type": owner_type,
        "packaging": packaging,
        "max_capacity": float(max_capacity),
        "max_order_limit": float(max_order_limit),
        "risk_factor": float(risk_factor),
        "episodes": int(episodes),
        "train_split": TRAIN_SPLIT,
        "days_total": int(len(df)),
        "days_train": int(len(env_train.data)),
        "days_eval": int(len(env_eval.data)),
        "best_eval_profit": round(best_eval_profit, 2),
        "best_eval_metrics": {k: round(float(v), 2) for k, v in best_metrics.items()},
        "avg_train_profit_last10": round(float(np.mean(train_profits[-10:])), 2),
        "eval_history": eval_history,
        "training_time_seconds": round(time.time() - t0, 1),
        "trained_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    if extra_meta:
        meta.update(extra_meta)
    with open(os.path.join(save_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    return meta
