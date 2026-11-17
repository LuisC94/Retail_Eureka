"""
Inferência do Stock Agent.

1. simulate_season(): corre uma temporada completa com o agente treinado e com as políticas de referência
   (FEFO + Procura, Venda Imediata) e devolve KPIs, séries diárias, relatório por lote e todas as decisões
   do agente com probabilidades e explicação.

2. decide_snapshot(): decisão para HOJE a partir do estado atual da plataforma (payload JSON do Django).
   Reconstrói o estado biológico de cada lote com o kernel Lifecycle a partir das leituras dos sensores
   desde a entrada no armazém e pede a decisão ao agente. É o que o web service expõe.
"""
import math

import numpy as np
import pandas as pd

from .heuristics import BASELINES
from .lc_kernel import lc_advance_day
from .policy import act
from .schema import normalize
from .simulator import (SimParams, SeasonData, StockEnv, ST_STORED, ST_LISTED, ST_PENDING, LC_MODEL)

AGENT_NAME = "Agente RL"


def _kg(x):
    """Formato português: espaço como separador de milhares."""
    return f"{x:,.0f}".replace(",", " ")


# =====================================================================================================
# Explicações
# =====================================================================================================

def _market_context(env):
    k = env.off + min(env.t, env.s.T - 1)
    price = env.price_full[k]
    return {
        "preco": price,
        "preco_vs_ma30_pct": 100.0 * (price / max(1e-6, env.ma30[k]) - 1.0),
        "procura7": env.fc7[k],
        "stock_venda": float(env.kg[env.status == ST_LISTED].sum()),
    }


def explain_lot(env, i, prob, chosen):
    s = env.s
    rsl = env.current_rsl()[i]
    ca = bool(s.wh_ca[s.lot_wh[i]])
    m = _market_context(env)
    reasons = []
    if chosen:
        if rsl <= 30:
            reasons.append(f"tempo de vida restante curto ({rsl:.0f} dias)")
        if not ca and rsl <= 90:
            reasons.append("armazém sem atmosfera controlada (degrada mais depressa)")
        if m["preco_vs_ma30_pct"] >= 5:
            reasons.append(f"preço {m['preco_vs_ma30_pct']:+.0f}% acima da média de 30 dias")
        if m["stock_venda"] < m["procura7"]:
            reasons.append(f"procura prevista a 7 dias ({_kg(m['procura7'])} kg) acima do stock já à venda ({_kg(m['stock_venda'])} kg)")
        if not reasons:
            reasons.append("escoamento antecipado para equilibrar stock e procura até ao fim da campanha")
        return f"COLOCAR À VENDA ({prob * 100:.0f}%): " + "; ".join(reasons) + "."
    if rsl > 60:
        reasons.append(f"ainda tem {rsl:.0f} dias de vida" + (" em atmosfera controlada" if ca else ""))
    if m["stock_venda"] >= m["procura7"]:
        reasons.append(f"o stock à venda ({_kg(m['stock_venda'])} kg) já cobre a procura prevista a 7 dias")
    if m["preco_vs_ma30_pct"] <= -5:
        reasons.append(f"preço {m['preco_vs_ma30_pct']:+.0f}% abaixo da média de 30 dias")
    if not reasons:
        reasons.append("outros lotes têm prioridade")
    return f"AGUARDAR ({(1 - prob) * 100:.0f}%): " + "; ".join(reasons) + "."


def explain_warehouse(env, w, prob, chosen):
    s = env.s
    stored = (env.status == ST_STORED) & (s.lot_wh == w)
    rsl = env.current_rsl()[stored]
    kg = env.kg[stored].sum()
    m = _market_context(env)
    ca = bool(s.wh_ca[w])
    if chosen:
        reasons = []
        if rsl.min() <= 30:
            reasons.append(f"lote mais urgente com {rsl.min():.0f} dias de vida")
        if not ca:
            reasons.append("armazém sem atmosfera controlada")
        if m["preco_vs_ma30_pct"] >= 5:
            reasons.append(f"preço {m['preco_vs_ma30_pct']:+.0f}% acima da média de 30 dias")
        if m["stock_venda"] < m["procura7"]:
            reasons.append("procura prevista acima do stock à venda")
        if not reasons:
            reasons.append("melhor equilíbrio entre urgência biológica e procura")
        return f"ABRIR ({prob * 100:.0f}%): {_kg(kg)} kg em {stored.sum()} lote(s); " + "; ".join(reasons) + "."
    return f"MANTER FECHADO ({prob * 100:.0f}% de abrir): {_kg(kg)} kg, tempo de vida mínimo {rsl.min():.0f} dias" + \
        (" em atmosfera controlada." if ca else ".")


# =====================================================================================================
# Simulação de temporada
# =====================================================================================================

def _run(env, decide):
    obs = env.reset()
    done = False
    decisions = []
    while not done:
        a, info = decide(env, obs)
        if info is not None:
            decisions.extend(info)
        obs, _, done = env.step(a)
    daily = pd.DataFrame(env.daily)
    if len(daily):
        daily["lucro_acumulado"] = (daily["receita"] - daily["custo_armazenagem"]).cumsum()
        daily["desperdicio_acumulado_kg"] = daily["kg_desperdicio"].cumsum()
    return {"kpis": env.kpis(), "daily": daily, "lots": env.lot_report(), "decisions": pd.DataFrame(decisions)}


def _agent_decider(model, mode):
    def decide(env, obs):
        a, _, value, probs = act(model, obs, deterministic=True)
        s = env.s
        date = s.days[min(env.t, s.T - 1)].date()
        rows = []
        rsl = env.current_rsl()
        if mode == "lot":
            for j, i in enumerate(obs["ids"]):
                rows.append({
                    "data": date, "lote_id": s.lot_ids[i], "armazem": s.wh_ids[s.lot_wh[i]],
                    "atmosfera_controlada": bool(s.wh_ca[s.lot_wh[i]]), "kg": round(env.kg[i], 1),
                    "qualidade": round(env.q[i], 1), "rsl_dias": round(rsl[i], 0),
                    "prob_venda_pct": round(100 * probs[j], 1), "decisao": "COLOCAR À VENDA" if a[j] else "AGUARDAR",
                    "explicacao": explain_lot(env, i, probs[j], bool(a[j])),
                })
        else:
            rows.append({"data": date, "armazem": "ESPERAR", "prob_pct": round(100 * probs[0], 1),
                         "decisao": "ESPERAR" if a == 0 else "", "explicacao": "Não abrir nenhum armazém esta semana." if a == 0 else ""})
            for j, w in enumerate(obs["ids"]):
                chosen = a == j + 1
                stored = (env.status == ST_STORED) & (s.lot_wh == w)
                rows.append({
                    "data": date, "armazem": s.wh_ids[w], "atmosfera_controlada": bool(s.wh_ca[w]),
                    "kg": round(env.kg[stored].sum(), 1), "n_lotes": int(stored.sum()),
                    "rsl_min_dias": round(rsl[stored].min(), 0), "prob_pct": round(100 * probs[j + 1], 1),
                    "decisao": "ABRIR" if chosen else "FECHADO",
                    "explicacao": explain_warehouse(env, w, probs[j + 1], chosen),
                })
        return a, rows
    return decide


def simulate_season(model, config, data, temporada, include_baselines=True, sim_params: SimParams = None):
    mode = config["mode"]
    params = sim_params or SimParams.from_dict(config["sim_params"])
    season = SeasonData(data, config["perfil"], config["cultura"], temporada, params)
    norm = config["norm"]
    results = {}
    env = StockEnv(season, mode, params, norm, rng=np.random.default_rng(0), augment=False)
    results[AGENT_NAME] = _run(env, _agent_decider(model, mode))
    if include_baselines:
        for name, fn in BASELINES[mode].items():
            env = StockEnv(season, mode, params, norm, rng=np.random.default_rng(0), augment=False)
            results[name] = _run(env, lambda e, o, fn=fn: (fn(e, o), None))
    results["_season"] = season
    return results


def comparison_table(results):
    rows = []
    for name, r in results.items():
        if name.startswith("_"):
            continue
        k = r["kpis"]
        rows.append({"Política": name, "Lucro (EUR)": k["lucro_eur"], "Receita (EUR)": k["receita_eur"],
                     "Custo armazenagem (EUR)": k["custo_armazenagem_eur"], "Kg vendidos": k["kg_vendidos"],
                     "Kg desperdiçados": k["kg_desperdicio"], "% Desperdício": k["pct_desperdicio"],
                     "Preço médio venda (EUR/kg)": k["preco_medio_venda"]})
    return pd.DataFrame(rows)


def report_excel_bytes(results, config):
    import io
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        comparison_table(results).to_excel(xw, sheet_name="Comparacao", index=False)
        for name, r in results.items():
            if name.startswith("_"):
                continue
            tag = {"Agente RL": "RL", "FEFO + Procura": "FEFO", "Venda Imediata": "Imediata"}.get(name, name)[:10]
            r["lots"].to_excel(xw, sheet_name=f"Lotes_{tag}", index=False)
            r["daily"].to_excel(xw, sheet_name=f"Diario_{tag}", index=False)
        dec = results[AGENT_NAME]["decisions"]
        if len(dec):
            dec.to_excel(xw, sheet_name="Decisoes_RL", index=False)
        pd.DataFrame([{"chave": k, "valor": str(v)} for k, v in config.items() if k not in ("item_features", "ctx_features")]) \
            .to_excel(xw, sheet_name="Modelo", index=False)
    return buf.getvalue()


# =====================================================================================================
# Decisão a partir do estado atual (web service)
# =====================================================================================================

def snapshot_to_data(payload, config):
    """Converte o payload JSON da plataforma no formato de dados interno (as mesmas folhas do Excel)."""
    perfil, cultura = config["perfil"], config["cultura"]
    arm = pd.DataFrame(payload["armazens"])
    arm["perfil"] = perfil
    lot = pd.DataFrame(payload["lotes"])
    lot["perfil"] = perfil
    lot["cultura"] = cultura
    lot["tipo_fruta"] = lot.get("tipo_fruta", config["fruit_key"])
    lot["temporada"] = 0
    leit = pd.DataFrame(payload.get("leituras") or [], columns=["armazem_id", "data", "temperatura", "humidade", "etileno"])
    merc = pd.DataFrame(payload["mercado"])
    merc["perfil"] = perfil
    merc["cultura"] = cultura
    if "vendas_kg" not in merc.columns:
        merc["vendas_kg"] = merc.get("procura_prevista_kg", 0.0)
    if "procura_prevista_kg" not in merc.columns:
        merc["procura_prevista_kg"] = merc["vendas_kg"]
    return normalize({"Armazens": arm, "Lotes": lot, "Leituras": leit, "Mercado": merc})


def payload_norm(payload):
    """Escalas de normalização calculadas a partir do próprio pedido.
    Usadas quando o modelo não foi treinado com os dados deste perfil (modelo por defeito), para que o
    estado fique na mesma escala relativa que o agente viu no treino (preço médio, procura diária, lote médio)."""
    merc = pd.DataFrame(payload["mercado"])
    lot = pd.DataFrame(payload["lotes"])
    dem = merc["procura_prevista_kg"].astype(float) if "procura_prevista_kg" in merc else merc["vendas_kg"].astype(float)
    whs = lot["armazem_id"].nunique() if len(lot) else 1
    return {
        "price_scale": float(max(0.05, merc["preco_kg"].astype(float).mean())),
        "kg_scale": float(max(1.0, dem.mean())),
        "lot_kg_scale": float(max(1.0, lot["quantidade_kg"].astype(float).mean())) if len(lot) else 1.0,
        "n_lots_scale": float(max(1.0, len(lot))),
        "n_wh_scale": float(max(1.0, whs)),
    }


def decide_snapshot(model, config, payload, adapt_norm=False):
    """
    payload = {
      "data": "YYYY-MM-DD",
      "armazens": [{"armazem_id", "tipo_controlo", "localizacao"?, "aberto"?: bool}],
      "lotes": [{"lote_id", "armazem_id", "data_colheita", "data_entrada"?, "quantidade_kg" (atual),
                 "firmeza"?, "brix"?, "acidez"?, "estado"?: "armazenado" | "a_venda"}],
      "leituras": [{"armazem_id", "data", "temperatura", "humidade", "etileno"?}],   # desde a entrada dos lotes
      "mercado": [{"data", "preco_kg", "procura_prevista_kg", "vendas_kg"?}]        # >= 30 dias antes e 14 dias depois
    }
    """
    mode = config["mode"]
    params = SimParams.from_dict(config["sim_params"])
    data = snapshot_to_data(payload, config)
    today = pd.Timestamp(payload["data"]).normalize()
    params.horizon_days = max(1, (today + pd.Timedelta(days=1) - data["Lotes"]["data_entrada"].max()).days + 14)
    season = SeasonData(data, config["perfil"], config["cultura"], 0, params)
    if today < season.start or today > season.days[-1]:
        raise ValueError("A data de decisão tem de estar entre a primeira entrada de lote e o último dia da folha mercado.")
    norm = payload_norm(payload) if adapt_norm else config["norm"]
    env = StockEnv(season, mode, params, norm, rng=np.random.default_rng(0), augment=False)
    env.reset()

    # Reconstrução do estado biológico: envelhecer cada lote desde a entrada até hoje (sem vendas, kg = atuais)
    t_today = (today - season.start).days
    lot_df = data["Lotes"].set_index("lote_id").loc[season.lot_ids]
    estados = lot_df["estado"].astype(str).str.lower().tolist() if "estado" in lot_df.columns else ["armazenado"] * season.n_lots
    env.status[:] = ST_PENDING
    for t in range(t_today):
        env.t = t
        for i in range(season.n_lots):
            if season.lot_entry[i] <= t:
                env.status[i] = ST_STORED
                T, RH, E, pkg = env._conditions(i, t)
                env.lc[i], env.q[i] = lc_advance_day(env.lc[i], T, RH, E, pkg, LC_MODEL, env.P)
                if t == t_today - 7:
                    env.q_week[i] = env.q[i]
    env.t = t_today
    env.kg = season.lot_kg.copy()
    env.kg0 = env.kg.copy()
    for i in range(season.n_lots):
        if season.lot_entry[i] <= t_today:
            env.status[i] = ST_LISTED if estados[i].startswith("a_venda") or estados[i].startswith("venda") else ST_STORED
    if mode == "warehouse" and "aberto" in data["Armazens"].columns:
        abertos = set(data["Armazens"].loc[data["Armazens"]["aberto"].astype(bool), "armazem_id"].astype(str))
        for w, wid in enumerate(season.wh_ids):
            env.wh_open[w] = wid in abertos
    env.rsl_dirty[:] = True
    env._refresh_rsl(force=True)
    obs = env.observe()

    a, _, value, probs = act(model, obs, deterministic=True)
    rsl = env.current_rsl()
    out = {"data": str(today.date()), "modo": mode, "perfil": config["perfil"], "cultura": config["cultura"],
           "contexto_mercado": {k: round(float(v), 3) for k, v in _market_context(env).items()}}
    if mode == "lot":
        recs = []
        for j, i in enumerate(obs["ids"]):
            recs.append({"lote_id": season.lot_ids[i], "armazem_id": season.wh_ids[season.lot_wh[i]],
                         "colocar_a_venda": bool(a[j]), "probabilidade": round(float(probs[j]), 4),
                         "kg": round(float(env.kg[i]), 1), "qualidade": round(float(env.q[i]), 1),
                         "rsl_dias": round(float(rsl[i]), 0), "explicacao": explain_lot(env, i, probs[j], bool(a[j]))})
        recs.sort(key=lambda r: -r["probabilidade"])
        out["lotes_a_colocar_a_venda"] = [r["lote_id"] for r in recs if r["colocar_a_venda"]]
        out["avaliacao_lotes"] = recs
    else:
        cands = []
        for j, w in enumerate(obs["ids"]):
            stored = (env.status == ST_STORED) & (season.lot_wh == w)
            cands.append({"armazem_id": season.wh_ids[w], "abrir": bool(a == j + 1),
                          "probabilidade": round(float(probs[j + 1]), 4), "kg": round(float(env.kg[stored].sum()), 1),
                          "n_lotes": int(stored.sum()), "rsl_min_dias": round(float(rsl[stored].min()), 0),
                          "explicacao": explain_warehouse(env, w, probs[j + 1], bool(a == j + 1))})
        out["armazem_a_abrir"] = season.wh_ids[obs["ids"][a - 1]] if a > 0 else None
        out["probabilidade_esperar"] = round(float(probs[0]), 4)
        out["avaliacao_armazens"] = sorted(cands, key=lambda r: -r["probabilidade"])
    return out


def snapshot_from_excel(data, config, date, temporada):
    """Constrói um payload de exemplo a partir do Excel (útil para testar o web service)."""
    date = pd.Timestamp(date)
    perfil, cultura = config["perfil"], config["cultura"]
    lot = data["Lotes"]
    lot = lot[(lot["perfil"] == perfil) & (lot["cultura"] == cultura) & (lot["temporada"] == temporada) &
              (lot["data_entrada"] <= date)]
    whs = sorted(lot["armazem_id"].unique())
    arm = data["Armazens"][data["Armazens"]["armazem_id"].isin(whs)]
    leit = data["Leituras"][(data["Leituras"]["armazem_id"].isin(whs)) & (data["Leituras"]["data"] <= date) &
                            (data["Leituras"]["data"] >= lot["data_entrada"].min())]
    merc = data["Mercado"]
    merc = merc[(merc["perfil"] == perfil) & (merc["cultura"] == cultura) &
                (merc["data"] >= date - pd.Timedelta(days=40)) & (merc["data"] <= date + pd.Timedelta(days=14))]
    fmt = lambda df, cols: [{c: (str(v.date()) if isinstance(v, pd.Timestamp) else (None if (isinstance(v, float) and math.isnan(v)) else v))
                             for c, v in zip(cols, row)} for row in df[cols].itertuples(index=False)]
    return {
        "perfil": perfil, "cultura": cultura, "modo": config["mode"],
        "data": str(date.date()),
        "armazens": fmt(arm, ["armazem_id", "tipo_controlo", "localizacao"]),
        "lotes": fmt(lot, ["lote_id", "armazem_id", "data_colheita", "data_entrada", "quantidade_kg", "firmeza", "brix", "acidez"]),
        "leituras": fmt(leit, ["armazem_id", "data", "temperatura", "humidade", "etileno"]),
        "mercado": fmt(merc, ["data", "preco_kg", "vendas_kg", "procura_prevista_kg"]),
    }
