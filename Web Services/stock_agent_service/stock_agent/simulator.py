"""
Simulador de temporada do Stock Agent (partilhado pelos dois agentes).

Dinâmica diária:
  1. Os lotes chegam aos armazéns na data de entrada.
  2. O agente decide o que colocar à venda:
       - modo "lot":       todos os dias, qualquer subconjunto de lotes armazenados;
       - modo "warehouse": de 7 em 7 dias, abrir no máximo 1 armazém (todos os lotes dele vão para venda).
  3. O mercado absorve até `vendas_kg` (procura real do dia) do stock à venda, lote mais urgente primeiro,
     ao preço do dia x fator de qualidade.
  4. Todos os lotes envelhecem 1 dia com o motor Lifecycle LC v0.2.0 (kernel local, numba):
       - armazenado em atmosfera controlada (AC): leituras do armazém + fator de respiração reduzido;
       - armazenado em frio normal: leituras do armazém;
       - à venda: sai da AC (cais de expedição em frio normal).
  5. Desperdício: o lote estraga quando a qualidade cai abaixo do limiar depois de ter atingido o pico.
  6. Recompensa (EUR normalizados) = receita - peso_desperdicio x kg_desperdicados x preco_ref - custo_armazenagem.
     No fim do horizonte, todo o stock não vendido conta como desperdício.
"""
import math
from dataclasses import dataclass, asdict, field

import numba
import numpy as np
import pandas as pd

from .lc_kernel import build_param_array, initial_state, lc_advance_day, lc_quality, resolve_lc_fruit_key, \
    STATE_SIZE, S_FIRM, S_BRIX

ST_PENDING, ST_STORED, ST_LISTED, ST_DONE = 0, 1, 2, 3
MAX_RSL = 240.0
LC_MODEL = 1  # modelo LC com etileno (os armazéns têm sensores de etileno)


@dataclass
class SimParams:
    horizon_days: int = 240            # dias de campanha após a última entrada de lote
    quality_floor: float = 30.0        # qualidade (0-100) abaixo da qual o lote é desperdício
    waste_weight: float = 2.0          # penalização por kg desperdiçado, em múltiplos do preço médio
    holding_cost_ca: float = 0.0012    # EUR/kg/dia em atmosfera controlada
    holding_cost_cold: float = 0.0008  # EUR/kg/dia em frio normal / à venda
    ca_pkg_factor: float = 0.10        # fator de respiração em AC (equivalente a MAP no LC)
    min_price_factor: float = 0.5      # fator de preço com qualidade 0 (qualidade 100 -> 1.0)
    expedition_temp: float = 3.0       # condições do stock à venda vindo de AC
    expedition_rh: float = 90.0
    expedition_ethylene: float = 0.3
    warehouse_interval: int = 7        # dias entre decisões no agente de armazéns
    owner_type: str = "Producer"

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(**{k: v for k, v in (d or {}).items() if k in cls.__dataclass_fields__})


@numba.njit(cache=True)
def project_rsl(s, q, T_c, RH, E, pkg, model, P, floor, max_days):
    """Dias até a qualidade cair abaixo de `floor` depois de ter atingido o pico (fruta que amadurece em armazém)."""
    cur = s.copy()
    peaked = q >= floor
    days = 0
    while days < max_days:
        if peaked and q < floor:
            break
        cur, q = lc_advance_day(cur, T_c, RH, E, pkg, model, P)
        days += 1
        if q >= floor:
            peaked = True
    return days


# =====================================================================================================
# Dados de uma temporada (perfil x cultura x temporada)
# =====================================================================================================

class SeasonData:
    PRE_DAYS = 30  # histórico de preço antes do início (para médias móveis)

    def __init__(self, data, perfil, cultura, temporada, params: SimParams, end_date=None):
        lotes = data["Lotes"]
        sel = lotes[(lotes["perfil"] == perfil) & (lotes["cultura"] == cultura) & (lotes["temporada"] == temporada)]
        if sel.empty:
            raise ValueError(f"Sem lotes para {perfil} / {cultura} / temporada {temporada}")
        sel = sel.sort_values(["data_entrada", "lote_id"]).reset_index(drop=True)
        self.perfil, self.cultura, self.temporada = perfil, cultura, temporada
        self.fruit_key = resolve_lc_fruit_key(sel["tipo_fruta"].iloc[0])

        merc = data["Mercado"]
        merc = merc[(merc["perfil"] == perfil) & (merc["cultura"] == cultura)].set_index("data").sort_index()
        if merc.empty:
            raise ValueError(f"Sem dados de Mercado para {perfil} / {cultura}")

        self.start = sel["data_entrada"].min()
        end = sel["data_entrada"].max() + pd.Timedelta(days=params.horizon_days)
        if end_date is not None:
            end = min(end, pd.Timestamp(end_date))
        end = min(end, merc.index.max())
        if end <= self.start:
            raise ValueError(f"Mercado não cobre a temporada {temporada} ({self.start.date()} -> {end.date()})")
        self.days = pd.date_range(self.start, end, freq="D")
        self.T = len(self.days)

        full = pd.date_range(self.start - pd.Timedelta(days=self.PRE_DAYS), end + pd.Timedelta(days=14), freq="D")
        m = merc.reindex(full)
        m["preco_kg"] = m["preco_kg"].ffill().bfill()
        m["vendas_kg"] = m["vendas_kg"].fillna(0.0)
        m["procura_prevista_kg"] = m["procura_prevista_kg"].fillna(m["vendas_kg"])
        self.full_price = m["preco_kg"].values.astype(np.float64)
        self.full_demand = m["vendas_kg"].values.astype(np.float64)
        self.full_forecast = m["procura_prevista_kg"].values.astype(np.float64)

        # Armazéns usados
        arm = data["Armazens"].set_index("armazem_id")
        self.wh_ids = sorted(sel["armazem_id"].unique().tolist())
        self.wh_names = [str(arm.loc[w, "localizacao"]) if "localizacao" in arm.columns else w for w in self.wh_ids]
        self.wh_ca = np.array([bool(arm.loc[w, "controlado"]) for w in self.wh_ids])
        leit = data["Leituras"]
        W = len(self.wh_ids)
        self.wh_T = np.zeros((W, self.T))
        self.wh_RH = np.zeros((W, self.T))
        self.wh_E = np.zeros((W, self.T))
        for i, w in enumerate(self.wh_ids):
            r = leit[leit["armazem_id"] == w].set_index("data").sort_index()
            r = r[~r.index.duplicated()].reindex(self.days)
            dT, dRH, dE = (0.8, 94.0, 0.02) if self.wh_ca[i] else (2.5, 89.0, 0.3)
            self.wh_T[i] = r["temperatura"].ffill().bfill().fillna(dT).values
            self.wh_RH[i] = r["humidade"].ffill().bfill().fillna(dRH).values
            self.wh_E[i] = r["etileno"].ffill().bfill().fillna(dE).values
        # Médias móveis de 7 dias (para projetar o RSL com clima estável)
        k = np.ones(7) / 7.0
        self.wh_T7 = np.array([_trailing_mean(x, 7) for x in self.wh_T])
        self.wh_RH7 = np.array([_trailing_mean(x, 7) for x in self.wh_RH])
        self.wh_E7 = np.array([_trailing_mean(x, 7) for x in self.wh_E])

        # Lotes
        wh_index = {w: i for i, w in enumerate(self.wh_ids)}
        self.lot_ids = sel["lote_id"].astype(str).tolist()
        self.lot_wh = np.array([wh_index[w] for w in sel["armazem_id"]], dtype=np.int64)
        self.lot_entry = np.array([(d - self.start).days for d in sel["data_entrada"]], dtype=np.int64)
        self.lot_kg = sel["quantidade_kg"].astype(float).values
        self.lot_harvest = sel["data_colheita"].tolist()
        self.lot_init = []
        for _, r in sel.iterrows():
            f0, b0, a0 = plausible_metrics(self.fruit_key, _num(r.get("firmeza")), _num(r.get("brix")), _num(r.get("acidez")))
            self.lot_init.append(initial_state(self.fruit_key, firmness_0=f0, brix_0=b0, acidity_0=a0))
        self.n_lots = len(self.lot_ids)


def plausible_metrics(fruit_key, firmness, brix, acidity):
    """Limita as medições à colheita a intervalos fisiologicamente plausíveis da fruta (protege de erros de registo).
    Valores em falta ficam None (o Lifecycle usa os valores por defeito do preset)."""
    from .lc_kernel import LC_PRESETS
    p = LC_PRESETS[fruit_key]
    clip = lambda v, lo, hi: None if v is None else float(min(hi, max(lo, v)))
    a0 = float(p.get("acidity_0_default", 1.0))
    return (clip(firmness, float(p["firmness_min"]) * 1.5, float(p["firmness_0_default"]) * 1.6),
            clip(brix, float(p["brix_min"]) * 0.6, float(p["brix_max"])),
            clip(acidity, float(p.get("acidity_min", 0.2)), a0 * 2.5))


def _num(v):
    try:
        f = float(v)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _trailing_mean(x, w):
    c = np.cumsum(np.insert(x, 0, 0.0))
    out = np.empty_like(x)
    for i in range(len(x)):
        j = max(0, i - w + 1)
        out[i] = (c[i + 1] - c[j]) / (i + 1 - j)
    return out


def build_seasons(data, perfil, cultura, temporadas, params: SimParams):
    seasons = []
    for t in temporadas:
        try:
            seasons.append(SeasonData(data, perfil, cultura, t, params))
        except ValueError:
            continue
    return seasons


def normalization_stats(seasons):
    """Escalas usadas para normalizar estado e recompensa (guardadas com o modelo)."""
    P = SeasonData.PRE_DAYS
    prices = np.concatenate([s.full_price[P:P + s.T] for s in seasons])
    demand = np.concatenate([s.full_demand[P:P + s.T] for s in seasons])
    kg_lot = np.concatenate([s.lot_kg for s in seasons])
    return {
        "price_scale": float(max(0.05, prices.mean())),
        "kg_scale": float(max(1.0, demand.mean())),          # procura média diária
        "lot_kg_scale": float(max(1.0, kg_lot.mean())),
        "n_lots_scale": float(max(1.0, np.mean([s.n_lots for s in seasons]))),
        "n_wh_scale": float(max(1.0, np.mean([len(s.wh_ids) for s in seasons]))),
    }


# =====================================================================================================
# Ambiente
# =====================================================================================================

LOT_FEATURES = [
    "kg", "qualidade", "rsl", "rsl_le_14", "rsl_le_30", "tendencia_qualidade", "firmeza_rel", "brix_rel",
    "dias_armazenado", "atmosfera_controlada", "temperatura", "humidade", "etileno", "kg_vs_procura14", "rank_urgencia",
]
WH_FEATURES = [
    "atmosfera_controlada", "n_lotes", "kg", "rsl_min", "rsl_medio", "frac_kg_rsl_le_30", "qualidade_media",
    "qualidade_min", "temperatura", "humidade", "etileno", "kg_vs_procura14", "dias_desde_entrada", "rank_urgencia",
]
CTX_FEATURES = [
    "preco_rel", "preco_vs_ma30", "preco_vs_ma7", "procura7", "procura14", "stock_venda_vs_procura7",
    "rsl_min_venda", "stock_armazenado", "n_lotes_armazenados", "sin_doy", "cos_doy", "progresso",
    "cobertura_stock", "n_lotes_venda", "lotes_por_chegar",
]


class StockEnv:
    def __init__(self, season: SeasonData, mode: str, params: SimParams, norm: dict, rng=None, augment=False):
        assert mode in ("lot", "warehouse")
        self.s = season
        self.mode = mode
        self.p = params
        self.norm = norm
        self.rng = rng if rng is not None else np.random.default_rng()
        self.augment = augment
        self.P = build_param_array(season.fruit_key, params.owner_type)
        p = self.P
        self.firm_ref = float(p[10]) if p[10] > 0 else 1.0
        self.brix_ref = float(p[8]) if p[8] > 0 else 1.0

    # ------------------------------------------------------------------ setup
    def reset(self):
        s, rng = self.s, self.rng
        Pd = SeasonData.PRE_DAYS
        price = s.full_price.copy()
        demand = s.full_demand.copy()
        forecast = s.full_forecast.copy()
        keep = np.ones(s.n_lots, dtype=bool)
        kg = s.lot_kg.copy()
        if self.augment:
            price *= rng.uniform(0.85, 1.15) * np.exp(np.cumsum(rng.normal(0, 0.01, len(price))) * 0.5)
            dm = rng.uniform(0.85, 1.15)
            noise = np.clip(rng.normal(1.0, 0.08, len(demand)), 0.6, 1.4)
            demand *= dm * noise
            forecast *= dm * noise * np.clip(rng.normal(1.0, 0.05, len(demand)), 0.8, 1.2)
            keep = rng.random(s.n_lots) > rng.uniform(0.0, 0.2)
            if not keep.any():
                keep[rng.integers(0, s.n_lots)] = True
            kg *= rng.uniform(0.9, 1.1, s.n_lots)
        self.price_full = price
        self.demand_full = demand
        self.forecast_full = forecast
        self.ma7 = _trailing_mean(price, 7)
        self.ma30 = _trailing_mean(price, 30)
        c = np.cumsum(np.insert(forecast, 0, 0.0))
        idx = np.arange(len(forecast))
        self.fc7 = c[np.minimum(idx + 8, len(c) - 1)] - c[np.minimum(idx + 1, len(c) - 1)]
        self.fc14 = c[np.minimum(idx + 15, len(c) - 1)] - c[np.minimum(idx + 1, len(c) - 1)]
        self.off = Pd
        self.price_ref = float(np.mean(price[Pd:Pd + s.T]))

        n = s.n_lots
        self.status = np.where(keep, ST_PENDING, ST_DONE).astype(np.int64)
        self.kg = np.where(keep, kg, 0.0)
        self.kg0 = self.kg.copy()
        self.lc = np.array([x.copy() for x in s.lot_init])
        self.q = np.array([lc_quality(self.lc[i], LC_MODEL, self.P) for i in range(n)])
        self.q_week = self.q.copy()
        self.peaked = self.q >= self.p.quality_floor
        self.rsl = np.full(n, MAX_RSL)
        self.rsl_day = np.full(n, 0, dtype=np.int64)
        self.rsl_dirty = np.ones(n, dtype=bool)
        self.listed_day = np.full(n, -1, dtype=np.int64)
        self.done_day = np.full(n, -1, dtype=np.int64)
        self.done_reason = [""] * n
        self.sold_kg = np.zeros(n)
        self.revenue_lot = np.zeros(n)
        self.wasted_kg = np.zeros(n)
        self.q_at_listing = np.full(n, np.nan)
        self.rsl_at_listing = np.full(n, np.nan)
        self.wh_open = np.zeros(len(s.wh_ids), dtype=bool)
        self.wh_open_day = np.full(len(s.wh_ids), -1, dtype=np.int64)
        self.t = 0
        self.totals = {"receita": 0.0, "kg_vendidos": 0.0, "kg_desperdicio": 0.0, "custo_armazenagem": 0.0,
                       "penalizacao_desperdicio": 0.0, "procura_total": 0.0, "procura_nao_satisfeita": 0.0}
        self.daily = []
        self._arrivals()
        self._refresh_rsl(force=True)
        reward = 0.0
        if self.mode == "lot":
            reward = self._skip_idle()
        self._pre_reward = reward
        return self.observe()

    # ------------------------------------------------------------------ dinâmica
    def _arrivals(self):
        s = self.s
        arr = (self.status == ST_PENDING) & (s.lot_entry <= self.t)
        if arr.any():
            for i in np.where(arr)[0]:
                if self.wh_open[s.lot_wh[i]]:
                    self._list_lot(i)
                else:
                    self.status[i] = ST_STORED

    def _conditions(self, i, t, smooth=False):
        s, w = self.s, self.s.lot_wh[i]
        tt = min(t, s.T - 1)
        if smooth:
            T, RH, E = s.wh_T7[w, tt], s.wh_RH7[w, tt], s.wh_E7[w, tt]
        else:
            T, RH, E = s.wh_T[w, tt], s.wh_RH[w, tt], s.wh_E[w, tt]
        if self.status[i] == ST_LISTED and s.wh_ca[w]:
            return self.p.expedition_temp, self.p.expedition_rh, self.p.expedition_ethylene, 1.0
        pkg = self.p.ca_pkg_factor if (s.wh_ca[w] and self.status[i] == ST_STORED) else 1.0
        return T, RH, E, pkg

    def _refresh_rsl(self, force=False, idx=None):
        live = np.where((self.status == ST_STORED) | (self.status == ST_LISTED))[0] if idx is None else idx
        for i in live:
            age = self.t - self.rsl_day[i]
            if force or age >= 7 or self.rsl_dirty[i]:
                T, RH, E, pkg = self._conditions(i, self.t, smooth=True)
                self.rsl[i] = float(project_rsl(self.lc[i], self.q[i], T, RH, E, pkg, LC_MODEL, self.P,
                                                self.p.quality_floor, int(MAX_RSL)))
                self.rsl_day[i] = self.t
                self.rsl_dirty[i] = False
        # decremento diário entre recálculos
        cur = np.maximum(0.0, self.rsl - np.maximum(0, self.t - self.rsl_day))
        return cur

    def current_rsl(self):
        return np.maximum(0.0, self.rsl - np.maximum(0, self.t - self.rsl_day))

    def _list_lot(self, i):
        self.status[i] = ST_LISTED
        self.listed_day[i] = self.t
        self.q_at_listing[i] = self.q[i]
        self.rsl_at_listing[i] = self.current_rsl()[i]
        self.rsl_dirty[i] = True  # condições mudam (sai da AC) -> recalcular no fim do dia

    def _simulate_day(self):
        """Mercado + envelhecimento + desperdício para o dia self.t; devolve recompensa normalizada."""
        s, p = self.s, self.p
        t = self.t
        k = self.off + t
        price = self.price_full[k]
        D = self.demand_full[k]
        self.totals["procura_total"] += D
        rsl_now = self.current_rsl()

        # 1. Vendas: stock à venda, mais urgente primeiro
        revenue = 0.0
        sold_today = 0.0
        pool = np.where(self.status == ST_LISTED)[0]
        if len(pool):
            pool = pool[np.argsort(rsl_now[pool], kind="stable")]
            remaining = D
            for i in pool:
                if remaining <= 0:
                    break
                q_sell = min(self.kg[i], remaining)
                pf = p.min_price_factor + (1.0 - p.min_price_factor) * min(1.0, self.q[i] / 100.0)
                r = q_sell * price * pf
                revenue += r
                self.revenue_lot[i] += r
                self.sold_kg[i] += q_sell
                self.kg[i] -= q_sell
                remaining -= q_sell
                sold_today += q_sell
                if self.kg[i] <= 1e-6:
                    self.kg[i] = 0.0
                    self.status[i] = ST_DONE
                    self.done_day[i] = t
                    self.done_reason[i] = "vendido"
        self.totals["procura_nao_satisfeita"] += max(0.0, D - sold_today)

        # 2. Custo de armazenagem
        stored = self.status == ST_STORED
        listed = self.status == ST_LISTED
        ca_stored = stored & s.wh_ca[s.lot_wh]
        holding = (self.kg[ca_stored].sum() * p.holding_cost_ca +
                   (self.kg[stored & ~ca_stored].sum() + self.kg[listed].sum()) * p.holding_cost_cold)

        # 3. Envelhecimento (LC) e desperdício
        waste = 0.0
        live = np.where(stored | listed)[0]
        for i in live:
            T, RH, E, pkg = self._conditions(i, t)
            self.lc[i], self.q[i] = lc_advance_day(self.lc[i], T, RH, E, pkg, LC_MODEL, self.P)
            if self.q[i] >= p.quality_floor:
                self.peaked[i] = True
            elif self.peaked[i]:
                waste += self.kg[i]
                self.wasted_kg[i] += self.kg[i]
                self.kg[i] = 0.0
                self.status[i] = ST_DONE
                self.done_day[i] = t
                self.done_reason[i] = "desperdicio"
        if (t + 1) % 7 == 0:
            self.q_week = self.q.copy()

        waste_pen = waste * p.waste_weight * self.price_ref
        self.totals["receita"] += revenue
        self.totals["kg_vendidos"] += sold_today
        self.totals["kg_desperdicio"] += waste
        self.totals["custo_armazenagem"] += holding
        self.totals["penalizacao_desperdicio"] += waste_pen
        self.daily.append({
            "dia": t, "data": s.days[t], "preco_kg": price, "procura_kg": D, "procura_prevista_kg": self.forecast_full[k],
            "kg_vendidos": sold_today, "receita": revenue, "kg_desperdicio": waste, "custo_armazenagem": holding,
            "stock_armazenado_kg": float(self.kg[self.status == ST_STORED].sum()),
            "stock_a_venda_kg": float(self.kg[self.status == ST_LISTED].sum()),
            "lucro_dia": revenue - holding,
        })
        self.t += 1
        self._arrivals()
        self._refresh_rsl()
        return (revenue - waste_pen - holding) / (self.norm["kg_scale"] * self.norm["price_scale"])

    def _terminal_waste(self):
        live = (self.status == ST_STORED) | (self.status == ST_LISTED)
        left = float(self.kg[live].sum())
        for i in np.where(live)[0]:
            self.wasted_kg[i] += self.kg[i]
            self.kg[i] = 0.0
            self.status[i] = ST_DONE
            self.done_day[i] = self.t
            self.done_reason[i] = "fim_horizonte"
        pen = left * self.p.waste_weight * self.price_ref
        self.totals["kg_desperdicio"] += left
        self.totals["penalizacao_desperdicio"] += pen
        return -pen / (self.norm["kg_scale"] * self.norm["price_scale"])

    def _finished(self):
        if self.t >= self.s.T:
            return True
        return not np.any((self.status == ST_PENDING) | (self.status == ST_STORED) | (self.status == ST_LISTED))

    def _skip_idle(self):
        """Modo lote: avança dias sem lotes armazenados (nada para decidir)."""
        r = 0.0
        while not self._finished() and not np.any(self.status == ST_STORED):
            r += self._simulate_day()
        return r

    # ------------------------------------------------------------------ interface RL
    def step(self, action):
        """modo lot: action = array 0/1 por candidato (ordem de obs['ids']); modo warehouse: int (0 = esperar)."""
        reward = self._pre_reward
        self._pre_reward = 0.0
        obs = self._last_obs
        if self.mode == "lot":
            for j, i in enumerate(obs["ids"]):
                if action[j] > 0.5 and self.status[i] == ST_STORED:
                    self._list_lot(i)
            reward += self._simulate_day()
            reward += self._skip_idle()
        else:
            a = int(action)
            if a > 0:
                w = obs["ids"][a - 1]
                self.wh_open[w] = True
                self.wh_open_day[w] = self.t
                for i in np.where((self.status == ST_STORED) & (self.s.lot_wh == w))[0]:
                    self._list_lot(i)
            for _ in range(self.p.warehouse_interval):
                if self._finished():
                    break
                reward += self._simulate_day()
            # salta semanas sem armazéns para abrir
            while not self._finished() and len(self._wh_candidates()) == 0:
                reward += self._simulate_day()
        done = self._finished()
        if done:
            reward += self._terminal_waste()
        return self.observe(), float(reward), done

    def _wh_candidates(self):
        s = self.s
        out = []
        for w in range(len(s.wh_ids)):
            if not self.wh_open[w] and np.any((self.status == ST_STORED) & (s.lot_wh == w)):
                out.append(w)
        return out

    def observe(self):
        s, n = self.s, self.norm
        t = min(self.t, s.T - 1)
        k = self.off + t
        rsl = self.current_rsl()
        stored = self.status == ST_STORED
        listed = self.status == ST_LISTED
        fc7, fc14 = self.fc7[k], self.fc14[k]
        price = self.price_full[k]
        listed_kg = float(self.kg[listed].sum())
        stored_kg = float(self.kg[stored].sum())
        remaining_days = max(1.0, s.T - t)
        doy = s.days[t].dayofyear / 365.25 * 2 * np.pi
        ctx = np.array([
            price / n["price_scale"],
            price / max(1e-6, self.ma30[k]) - 1.0,
            price / max(1e-6, self.ma7[k]) - 1.0,
            fc7 / (7 * n["kg_scale"]),
            fc14 / (14 * n["kg_scale"]),
            min(5.0, listed_kg / max(1.0, fc7)),
            (rsl[listed].min() if listed.any() else MAX_RSL) / MAX_RSL,
            stored_kg / (n["kg_scale"] * 60.0),
            stored.sum() / n["n_lots_scale"],
            math.sin(doy), math.cos(doy),
            t / max(1.0, s.T),
            min(5.0, (stored_kg + listed_kg) / max(1.0, n["kg_scale"] * remaining_days)),
            listed.sum() / 10.0,
            (self.status == ST_PENDING).sum() / n["n_lots_scale"],
        ], dtype=np.float32)

        if self.mode == "lot":
            ids = np.where(stored)[0]
            feats = np.zeros((len(ids), len(LOT_FEATURES)), dtype=np.float32)
            if len(ids):
                r = rsl[ids]
                order = np.argsort(np.argsort(r, kind="stable"), kind="stable")
                for j, i in enumerate(ids):
                    w = s.lot_wh[i]
                    feats[j] = [
                        math.log1p(self.kg[i] / n["lot_kg_scale"]),
                        self.q[i] / 100.0,
                        r[j] / MAX_RSL,
                        float(r[j] <= 14), float(r[j] <= 30),
                        (self.q[i] - self.q_week[i]) / 20.0,
                        self.lc[i][S_FIRM] / self.firm_ref / 5.0,
                        self.lc[i][S_BRIX] / self.brix_ref,
                        (t - s.lot_entry[i]) / MAX_RSL,
                        float(s.wh_ca[w]),
                        s.wh_T[w, t] / 10.0, s.wh_RH[w, t] / 100.0, min(2.0, s.wh_E[w, t]) / 2.0,
                        min(5.0, self.kg[i] / max(1.0, fc14)),
                        order[j] / max(1, len(ids) - 1) if len(ids) > 1 else 0.0,
                    ]
            obs = {"ctx": ctx, "feats": feats, "ids": ids}
        else:
            ids = self._wh_candidates()
            feats = np.zeros((len(ids), len(WH_FEATURES)), dtype=np.float32)
            if ids:
                mins = []
                for w in ids:
                    m = stored & (s.lot_wh == w)
                    mins.append(rsl[m].min())
                order = np.argsort(np.argsort(mins, kind="stable"), kind="stable")
                for j, w in enumerate(ids):
                    m = stored & (s.lot_wh == w)
                    kgw = self.kg[m]
                    rw = rsl[m]
                    tot = max(1e-6, kgw.sum())
                    feats[j] = [
                        float(s.wh_ca[w]),
                        m.sum() / 10.0,
                        kgw.sum() / (n["kg_scale"] * 30.0),
                        rw.min() / MAX_RSL,
                        float((rw * kgw).sum() / tot) / MAX_RSL,
                        float(kgw[rw <= 30].sum() / tot),
                        float((self.q[m] * kgw).sum() / tot) / 100.0,
                        self.q[m].min() / 100.0,
                        s.wh_T[w, t] / 10.0, s.wh_RH[w, t] / 100.0, min(2.0, s.wh_E[w, t]) / 2.0,
                        min(5.0, kgw.sum() / max(1.0, fc14)),
                        (t - s.lot_entry[m].min()) / MAX_RSL,
                        order[j] / max(1, len(ids) - 1) if len(ids) > 1 else 0.0,
                    ]
            obs = {"ctx": ctx, "feats": feats, "ids": np.array(ids, dtype=np.int64)}
        self._last_obs = obs
        return obs

    # ------------------------------------------------------------------ relatórios
    def lot_report(self):
        s = self.s
        rows = []
        for i in range(s.n_lots):
            if self.kg0[i] <= 0:
                continue
            rows.append({
                "lote_id": s.lot_ids[i], "armazem": s.wh_ids[s.lot_wh[i]],
                "atmosfera_controlada": bool(s.wh_ca[s.lot_wh[i]]),
                "data_entrada": s.days[min(s.lot_entry[i], s.T - 1)].date(),
                "kg_inicial": round(self.kg0[i], 1),
                "data_colocado_venda": s.days[self.listed_day[i]].date() if self.listed_day[i] >= 0 else None,
                "dias_ate_venda": int(self.listed_day[i] - s.lot_entry[i]) if self.listed_day[i] >= 0 else None,
                "qualidade_na_venda": round(self.q_at_listing[i], 1) if not np.isnan(self.q_at_listing[i]) else None,
                "rsl_na_venda": round(self.rsl_at_listing[i], 0) if not np.isnan(self.rsl_at_listing[i]) else None,
                "kg_vendidos": round(self.sold_kg[i], 1), "receita_eur": round(self.revenue_lot[i], 2),
                "kg_desperdicio": round(self.wasted_kg[i], 1),
                "estado_final": self.done_reason[i] or ("a_venda" if self.status[i] == ST_LISTED else "armazenado"),
            })
        return pd.DataFrame(rows)

    def kpis(self):
        tot = self.totals
        kg_total = float(self.kg0.sum())
        lucro = tot["receita"] - tot["custo_armazenagem"]
        return {
            "receita_eur": tot["receita"],
            "custo_armazenagem_eur": tot["custo_armazenagem"],
            "lucro_eur": lucro,
            "kg_total": kg_total,
            "kg_vendidos": tot["kg_vendidos"],
            "kg_desperdicio": tot["kg_desperdicio"],
            "pct_desperdicio": 100.0 * tot["kg_desperdicio"] / max(1.0, kg_total),
            "preco_medio_venda": tot["receita"] / max(1.0, tot["kg_vendidos"]),
            "procura_nao_satisfeita_kg": tot["procura_nao_satisfeita"],
        }
