"""
Treino do Stock Agent (um modelo por perfil x cultura x modo).

Fase 1 (opcional) - Pré-treino por imitação (Behavior Cloning) da política FEFO + Procura:
    dá ao agente um ponto de partida sensato (não deixar fruta estragar).
Fase 2 - PPO sobre o simulador de temporada (com aumento de dados: preço, procura e lotes perturbados).
    Validação periódica nas temporadas de teste; guarda-se o melhor modelo.

`train_generator(...)` é um gerador de eventos (para a interface Streamlit / web service):
    {"type": "log", "msg": str}
    {"type": "progress", "episode": int, "total": int, ...métricas}
    {"type": "done", "zip_bytes": bytes, "config": dict, "history": DataFrame}
"""
import time
from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd
import torch

from .heuristics import BASELINES
from .model_io import bundle_to_zip_bytes
from .policy import SetActorCritic, act, pad_batch, pad_actions
from .simulator import (SimParams, StockEnv, build_seasons, normalization_stats, LOT_FEATURES, WH_FEATURES,
                        CTX_FEATURES)


@dataclass
class TrainConfig:
    episodes: int = 400
    episodes_per_update: int = 4
    ppo_epochs: int = 4
    minibatch: int = 256
    lr: float = 3e-4
    gamma: float = 0.99
    gae_lambda: float = 0.95
    clip: float = 0.2
    ent_coef: float = 0.01
    vf_coef: float = 0.5
    max_grad_norm: float = 0.5
    reward_scale: float = 0.1
    hidden: int = 128
    bc_episodes: int = 30
    bc_epochs: int = 15
    eval_every: int = 5          # em atualizações PPO
    seed: int = 42

    def to_dict(self):
        return asdict(self)


def run_episode(env, policy_fn):
    obs = env.reset()
    done = False
    total = 0.0
    while not done:
        obs, r, done = env.step(policy_fn(env, obs))
        total += r
    return total


def evaluate(model, seasons, mode, params, norm, baseline=None):
    """Avalia a política determinística (ou um baseline) nas temporadas, sem aumento de dados."""
    scores, profits, waste = [], [], []
    for s in seasons:
        env = StockEnv(s, mode, params, norm, rng=np.random.default_rng(0), augment=False)
        if baseline is not None:
            fn = baseline
        else:
            fn = lambda e, o: act(model, o, deterministic=True)[0]
        scores.append(run_episode(env, fn))
        k = env.kpis()
        profits.append(k["lucro_eur"])
        waste.append(k["pct_desperdicio"])
    return float(np.mean(scores)), float(np.mean(profits)), float(np.mean(waste))


def _gae(rewards, values, dones, gamma, lam):
    adv = np.zeros(len(rewards), dtype=np.float32)
    last = 0.0
    for t in reversed(range(len(rewards))):
        nv = 0.0 if dones[t] else values[t + 1]
        delta = rewards[t] + gamma * nv - values[t]
        last = delta + gamma * lam * (0.0 if dones[t] else last)
        adv[t] = last
    return adv, adv + np.array(values[:len(rewards)], dtype=np.float32)


def _forward_batch(model, ctxs, feats_list, f_item):
    feats, mask = pad_batch(feats_list, f_item)
    ctx = torch.from_numpy(np.stack(ctxs))
    logits, value = model(feats, mask, ctx)
    return logits, value, mask


def train_generator(data, perfil, cultura, mode, train_seasons, val_seasons, sim_params: SimParams = None,
                    cfg: TrainConfig = None):
    sim_params = sim_params or SimParams()
    cfg = cfg or TrainConfig()
    torch.set_num_threads(1)
    torch.manual_seed(cfg.seed)
    rng = np.random.default_rng(cfg.seed)
    t0 = time.time()

    seasons_tr = build_seasons(data, perfil, cultura, train_seasons, sim_params)
    seasons_val = build_seasons(data, perfil, cultura, val_seasons, sim_params) if val_seasons else []
    if not seasons_tr:
        raise ValueError("Nenhuma temporada de treino válida (verifique lotes e cobertura da folha Mercado).")
    eval_seasons = seasons_val or seasons_tr
    norm = normalization_stats(seasons_tr)
    f_item = len(LOT_FEATURES) if mode == "lot" else len(WH_FEATURES)
    f_ctx = len(CTX_FEATURES)
    gamma = cfg.gamma if mode == "lot" else cfg.gamma ** sim_params.warehouse_interval
    # No modo armazém cada passo agrega vários dias de recompensa
    reward_scale = cfg.reward_scale if mode == "lot" else cfg.reward_scale / sim_params.warehouse_interval
    model = SetActorCritic(f_item, f_ctx, mode, hidden=cfg.hidden)
    opt = torch.optim.Adam(model.parameters(), lr=cfg.lr)
    nome_modo = "Agente de Lotes (diário)" if mode == "lot" else "Agente de Armazéns (semanal)"

    yield {"type": "log", "msg": f"[SETUP] {nome_modo} | Perfil: {perfil} | Cultura: {cultura} ({seasons_tr[0].fruit_key})"}
    yield {"type": "log", "msg": f"[SETUP] Temporadas treino: {[s.temporada for s in seasons_tr]} | validação: "
                                 f"{[s.temporada for s in seasons_val] or 'nenhuma (usa treino)'}"}
    yield {"type": "log", "msg": f"[SETUP] Lotes/temporada: ~{norm['n_lots_scale']:.0f} | Procura média: "
                                 f"{norm['kg_scale']:.0f} kg/dia | Preço médio: {norm['price_scale']:.2f} EUR/kg"}

    fefo = BASELINES[mode]["FEFO + Procura"]
    b_score, b_profit, b_waste = evaluate(None, eval_seasons, mode, sim_params, norm, baseline=fefo)
    yield {"type": "log", "msg": f"[BASELINE] FEFO + Procura (validação): lucro médio {b_profit:,.0f} EUR | "
                                 f"desperdício {b_waste:.1f}% | score {b_score:.1f}"}

    # ------------------------------------------------------------------ Fase 1: Behavior Cloning
    if cfg.bc_episodes > 0 and cfg.bc_epochs > 0:
        yield {"type": "log", "msg": f"[FASE 1] Pré-treino por imitação da FEFO ({cfg.bc_episodes} episódios)..."}
        ctxs, feats, acts = [], [], []
        for _ in range(cfg.bc_episodes):
            s = seasons_tr[rng.integers(len(seasons_tr))]
            env = StockEnv(s, mode, sim_params, norm, rng=rng, augment=True)
            obs = env.reset()
            done = False
            while not done:
                a = fefo(env, obs)
                ctxs.append(obs["ctx"]); feats.append(obs["feats"]); acts.append(a)
                obs, _, done = env.step(a)
        n = len(acts)
        for ep in range(cfg.bc_epochs):
            perm = rng.permutation(n)
            tot, cnt = 0.0, 0
            for st in range(0, n, cfg.minibatch):
                idx = perm[st:st + cfg.minibatch]
                logits, _, mask = _forward_batch(model, [ctxs[i] for i in idx], [feats[i] for i in idx], f_item)
                a = pad_actions([acts[i] for i in idx], mask.shape[1], mode)
                lp, _ = model.log_prob_entropy(logits, mask, a)
                loss = -lp.mean()
                opt.zero_grad(); loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), cfg.max_grad_norm)
                opt.step()
                tot += loss.item() * len(idx); cnt += len(idx)
            yield {"type": "log", "msg": f"[FASE 1] Época {ep + 1}/{cfg.bc_epochs} | perda imitação: {tot / cnt:.4f}"}
        sc, pr, wa = evaluate(model, eval_seasons, mode, sim_params, norm)
        yield {"type": "log", "msg": f"[FASE 1] Após imitação (validação): lucro {pr:,.0f} EUR | desperdício {wa:.1f}% | score {sc:.1f}"}

    # ------------------------------------------------------------------ Fase 2: PPO
    yield {"type": "log", "msg": f"[FASE 2] PPO: {cfg.episodes} episódios, {cfg.episodes_per_update} por atualização"}
    best_score, best_state = -1e18, None
    if cfg.bc_episodes > 0 and cfg.bc_epochs > 0:
        best_score, best_state = sc, {k: v.clone() for k, v in model.state_dict().items()}
    history = []
    ep_done = 0
    update = 0
    while ep_done < cfg.episodes:
        buf = {"ctx": [], "feats": [], "act": [], "logp": [], "adv": [], "ret": []}
        ep_returns, ep_profit, ep_waste = [], [], []
        for _ in range(min(cfg.episodes_per_update, cfg.episodes - ep_done)):
            s = seasons_tr[rng.integers(len(seasons_tr))]
            env = StockEnv(s, mode, sim_params, norm, rng=rng, augment=True)
            obs = env.reset()
            done = False
            rewards, values, dones = [], [], []
            while not done:
                a, lp, v, _ = act(model, obs, deterministic=False, rng=rng)
                buf["ctx"].append(obs["ctx"]); buf["feats"].append(obs["feats"]); buf["act"].append(a)
                buf["logp"].append(lp)
                obs, r, done = env.step(a)
                rewards.append(r * reward_scale); values.append(v); dones.append(done)
            values.append(0.0)
            adv, ret = _gae(rewards, values, dones, gamma, cfg.gae_lambda)
            buf["adv"].extend(adv.tolist()); buf["ret"].extend(ret.tolist())
            k = env.kpis()
            ep_returns.append(sum(rewards) / reward_scale); ep_profit.append(k["lucro_eur"])
            ep_waste.append(k["pct_desperdicio"])
            ep_done += 1

        n = len(buf["act"])
        adv_all = np.array(buf["adv"], dtype=np.float32)
        adv_all = (adv_all - adv_all.mean()) / (adv_all.std() + 1e-8)
        ret_all = np.array(buf["ret"], dtype=np.float32)
        old_lp = np.array(buf["logp"], dtype=np.float32)
        pl_sum, vl_sum, ent_sum, nb = 0.0, 0.0, 0.0, 0
        for _ in range(cfg.ppo_epochs):
            perm = rng.permutation(n)
            for st in range(0, n, cfg.minibatch):
                idx = perm[st:st + cfg.minibatch]
                logits, value, mask = _forward_batch(model, [buf["ctx"][i] for i in idx], [buf["feats"][i] for i in idx], f_item)
                a = pad_actions([buf["act"][i] for i in idx], mask.shape[1], mode)
                lp, ent = model.log_prob_entropy(logits, mask, a)
                ratio = torch.exp(torch.clamp(lp - torch.from_numpy(old_lp[idx]), -20, 20))
                A = torch.from_numpy(adv_all[idx])
                pl = -torch.min(ratio * A, torch.clamp(ratio, 1 - cfg.clip, 1 + cfg.clip) * A).mean()
                vl = ((value - torch.from_numpy(ret_all[idx])) ** 2).mean()
                loss = pl + cfg.vf_coef * vl - cfg.ent_coef * ent.mean()
                opt.zero_grad(); loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), cfg.max_grad_norm)
                opt.step()
                pl_sum += pl.item(); vl_sum += vl.item(); ent_sum += ent.mean().item(); nb += 1
        update += 1
        row = {"episodio": ep_done, "score_treino": float(np.mean(ep_returns)), "lucro_treino": float(np.mean(ep_profit)),
               "desperdicio_treino_pct": float(np.mean(ep_waste)), "perda_actor": pl_sum / nb, "perda_critic": vl_sum / nb,
               "entropia": ent_sum / nb}
        msg = (f"Episódios: {ep_done}/{cfg.episodes} | Score: {row['score_treino']:+.1f} | Lucro: {row['lucro_treino']:,.0f} EUR"
               f" | Desperdício: {row['desperdicio_treino_pct']:.1f}% | Actor: {row['perda_actor']:+.4f} | Critic: {row['perda_critic']:.3f}")
        if update % cfg.eval_every == 0 or ep_done >= cfg.episodes:
            sc, pr, wa = evaluate(model, eval_seasons, mode, sim_params, norm)
            row.update({"score_validacao": sc, "lucro_validacao": pr, "desperdicio_validacao_pct": wa})
            msg += f"\n   [VALIDAÇÃO] Lucro {pr:,.0f} EUR | Desperdício {wa:.1f}% | Score {sc:.1f}"
            if sc > best_score:
                best_score = sc
                best_state = {k: v.clone() for k, v in model.state_dict().items()}
                msg += "  <- melhor modelo"
        history.append(row)
        yield {"type": "log", "msg": msg}
        yield {"type": "progress", "episode": ep_done, "total": cfg.episodes, **row}

    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()
    sc, pr, wa = evaluate(model, eval_seasons, mode, sim_params, norm)
    hist_df = pd.DataFrame(history)
    config = {
        "mode": mode, "perfil": perfil, "cultura": cultura, "fruit_key": seasons_tr[0].fruit_key,
        "f_item": f_item, "f_ctx": f_ctx, "hidden": cfg.hidden,
        "item_features": LOT_FEATURES if mode == "lot" else WH_FEATURES, "ctx_features": CTX_FEATURES,
        "norm": norm, "sim_params": sim_params.to_dict(), "train_config": cfg.to_dict(),
        "train_seasons": [int(s.temporada) for s in seasons_tr], "val_seasons": [int(s.temporada) for s in seasons_val],
        "metrics": {"validacao_lucro_eur": pr, "validacao_desperdicio_pct": wa, "validacao_score": sc,
                    "fefo_lucro_eur": b_profit, "fefo_desperdicio_pct": b_waste, "fefo_score": b_score,
                    "melhor_que_fefo": bool(sc >= b_score)},
        "trained_at": pd.Timestamp.now().isoformat(timespec="seconds"),
        "training_seconds": round(time.time() - t0, 1),
    }
    yield {"type": "log", "msg": f"[FIM] Melhor modelo (validação): lucro {pr:,.0f} EUR | desperdício {wa:.1f}% | score {sc:.1f}"
                                 f"  vs FEFO: lucro {b_profit:,.0f} EUR | desperdício {b_waste:.1f}%  ({time.time() - t0:.0f}s)"}
    if sc < b_score:
        yield {"type": "log", "msg": "[AVISO] O modelo ainda não supera a heurística FEFO na validação. "
                                     "Aumente o número de episódios ou reveja os parâmetros antes de o usar em produção."}
    yield {"type": "done", "zip_bytes": bundle_to_zip_bytes(model, config, hist_df), "config": config, "history": hist_df}
