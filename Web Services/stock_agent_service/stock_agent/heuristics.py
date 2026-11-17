"""
Políticas de referência (baselines) usadas para comparação na inferência e para o pré-treino por imitação.

- FEFO + Procura: coloca à venda os lotes com menor tempo de vida restante (First Expired First Out)
  até o stock à venda cobrir a procura prevista dos próximos N dias; força a venda de lotes críticos.
- Venda Imediata: coloca tudo à venda assim que chega (o que acontece sem planeamento).
"""
import numpy as np

from .simulator import ST_LISTED, ST_STORED


def fefo_lot_policy(env, obs, cover_days=10, critical_rsl=21.0):
    ids = obs["ids"]
    action = np.zeros(len(ids), dtype=np.int64)
    if len(ids) == 0:
        return action
    rsl = env.current_rsl()
    k = env.off + min(env.t, env.s.T - 1)
    target = env.fc7[k] * cover_days / 7.0
    listed_kg = float(env.kg[env.status == ST_LISTED].sum())
    order = np.argsort(rsl[ids], kind="stable")
    for j in order:
        i = ids[j]
        if rsl[i] <= critical_rsl or listed_kg < target:
            action[j] = 1
            listed_kg += env.kg[i]
    return action


def fefo_warehouse_policy(env, obs, cover_days=10, critical_rsl=21.0):
    ids = obs["ids"]
    if len(ids) == 0:
        return 0
    rsl = env.current_rsl()
    stored = env.status == ST_STORED
    mins = np.array([rsl[stored & (env.s.lot_wh == w)].min() for w in ids])
    k = env.off + min(env.t, env.s.T - 1)
    target = env.fc7[k] * cover_days / 7.0
    listed_kg = float(env.kg[env.status == ST_LISTED].sum())
    j = int(np.argmin(mins))
    if mins[j] <= critical_rsl or listed_kg < target:
        return j + 1
    return 0


def immediate_lot_policy(env, obs):
    return np.ones(len(obs["ids"]), dtype=np.int64)


def immediate_warehouse_policy(env, obs):
    return 1 if len(obs["ids"]) else 0


BASELINES = {
    "lot": {"FEFO + Procura": fefo_lot_policy, "Venda Imediata": immediate_lot_policy},
    "warehouse": {"FEFO + Procura": fefo_warehouse_policy, "Venda Imediata": immediate_warehouse_policy},
}
