"""
Gerador de dados sintéticos do Stock Agent no formato do Excel (ver schema.py).

Cria, para um perfil (produtor):
  - armazéns com e sem atmosfera controlada;
  - várias temporadas de lotes por cultura (podendo misturar culturas no mesmo armazém);
  - leituras diárias de sensores (temperatura, humidade, etileno) por armazém;
  - mercado diário por cultura: preço (sazonal + ruído + picos), procura real e procura prevista.

A procura de cada temporada é calibrada contra o stock total dessa temporada, para que exista
pressão real de escoamento (vender tudo de uma vez gera desperdício; esperar demais também).
"""
import argparse
import os

import numpy as np
import pandas as pd

from .schema import to_excel_bytes, readme_frame

# Perfil de cada cultura: janela de colheita (mês, dia) -> (mês, dia), preço base, duração da campanha
CULTURES = {
    "kiwi_hayward": {"cultura": "Kiwi Hayward", "harvest": ((10, 10), (11, 25)), "price": 1.55, "campaign_days": 220,
                     "firm": 45.0, "brix": 7.5, "acid": 1.5, "caliber": 70.0},
    "pear": {"cultura": "Pera Rocha", "harvest": ((8, 15), (9, 25)), "price": 0.95, "campaign_days": 150,
             "firm": 55.0, "brix": 12.0, "acid": 0.3, "caliber": 62.0},
    "apple_gala": {"cultura": "Maçã Gala", "harvest": ((8, 10), (9, 20)), "price": 0.85, "campaign_days": 150,
                   "firm": 60.0, "brix": 13.0, "acid": 0.4, "caliber": 72.0},
    "apple_fuji": {"cultura": "Maçã Fuji", "harvest": ((10, 1), (11, 10)), "price": 0.95, "campaign_days": 240,
                   "firm": 75.0, "brix": 14.0, "acid": 0.35, "caliber": 75.0},
    "apple_golden": {"cultura": "Maçã Golden", "harvest": ((9, 1), (10, 10)), "price": 0.80, "campaign_days": 200,
                     "firm": 70.0, "brix": 13.5, "acid": 0.5, "caliber": 72.0},
    "apple_reineta": {"cultura": "Maçã Reineta", "harvest": ((9, 15), (10, 31)), "price": 1.10, "campaign_days": 140,
                      "firm": 65.0, "brix": 11.5, "acid": 0.8, "caliber": 75.0},
    "kiwi_gold": {"cultura": "Kiwi Gold", "harvest": ((9, 20), (10, 31)), "price": 2.40, "campaign_days": 170,
                  "firm": 40.0, "brix": 9.5, "acid": 0.95, "caliber": 65.0},
    "orange": {"cultura": "Laranja", "harvest": ((12, 1), (2, 28)), "price": 0.70, "campaign_days": 90,
               "firm": 50.0, "brix": 11.0, "acid": 0.9, "caliber": 70.0},
}

REGIONS = ["PT-NL", "PT-CL", "PT-LVT", "PT-CI", "PT-AL"]


def _season_dates(year, window):
    (m0, d0), (m1, d1) = window
    start = pd.Timestamp(year=year, month=m0, day=d0)
    end_year = year if (m1, d1) >= (m0, d0) else year + 1
    end = pd.Timestamp(year=end_year, month=m1, day=d1)
    return start, end


def generate(perfil="Produtor_Demo", fruit_keys=("kiwi_hayward", "pear"), n_warehouses=6, frac_controlled=0.5,
             n_seasons=5, first_year=2020, lots_per_season=24, seed=42) -> dict:
    rng = np.random.default_rng(seed)
    fruit_keys = list(fruit_keys)

    # ------------------------------------------------------------------ Armazéns
    n_ca = max(1, int(round(n_warehouses * frac_controlled))) if frac_controlled > 0 else 0
    armazens = []
    for i in range(n_warehouses):
        ca = i < n_ca
        armazens.append({
            "armazem_id": f"A{i + 1:02d}",
            "perfil": perfil,
            "localizacao": f"Armazém {i + 1} ({'AC' if ca else 'Frio'})",
            "regiao": REGIONS[i % len(REGIONS)],
            "tipo_controlo": "Controlled" if ca else "Non-Controlled",
            "capacidade_kg": float(rng.choice([120000, 160000, 200000, 250000])),
        })
    df_arm = pd.DataFrame(armazens)
    wh_weights = np.where(df_arm["tipo_controlo"] == "Controlled", 2.5, 1.0)
    wh_weights = wh_weights / wh_weights.sum()

    # ------------------------------------------------------------------ Lotes
    lotes = []
    lot_counter = 1
    for year in range(first_year, first_year + n_seasons):
        for fk in fruit_keys:
            cfg = CULTURES[fk]
            h0, h1 = _season_dates(year, cfg["harvest"])
            n_lots = int(rng.integers(int(lots_per_season * 0.75), int(lots_per_season * 1.25) + 1))
            span = max(1, (h1 - h0).days)
            for _ in range(n_lots):
                hd = h0 + pd.Timedelta(days=int(rng.integers(0, span + 1)))
                # Fruta de guarda longa vai preferencialmente para atmosfera controlada (peso 2.5 : 1)
                wh = df_arm.iloc[int(rng.choice(n_warehouses, p=wh_weights))]
                qty = float(np.round(rng.uniform(4000, 22000) / 20.0) * 20.0)
                q_factor = rng.normal(1.0, 0.07)
                lotes.append({
                    "lote_id": f"L{lot_counter:05d}",
                    "perfil": perfil,
                    "armazem_id": wh["armazem_id"],
                    "cultura": cfg["cultura"],
                    "tipo_fruta": fk,
                    "temporada": year,
                    "data_colheita": hd,
                    "data_entrada": hd + pd.Timedelta(days=int(rng.integers(0, 3))),
                    "quantidade_kg": qty,
                    "firmeza": round(cfg["firm"] * float(np.clip(q_factor, 0.8, 1.2)), 2),
                    "brix": round(cfg["brix"] * float(np.clip(rng.normal(1.0, 0.06), 0.85, 1.15)), 2),
                    "acidez": round(cfg["acid"] * float(np.clip(rng.normal(1.0, 0.08), 0.8, 1.2)), 3),
                    "calibre_mm": round(cfg["caliber"] * float(np.clip(rng.normal(1.0, 0.05), 0.85, 1.15)), 1),
                    "score_qualidade": round(float(np.clip(8.0 * q_factor + rng.normal(0, 0.4), 5, 10)), 1),
                })
                lot_counter += 1
    df_lot = pd.DataFrame(lotes).sort_values(["data_entrada", "lote_id"]).reset_index(drop=True)

    # ------------------------------------------------------------------ Período total e leituras de sensores
    t_start = df_lot["data_colheita"].min() - pd.Timedelta(days=5)
    t_end = max(_season_dates(first_year + n_seasons - 1, CULTURES[fk]["harvest"])[1] +
                pd.Timedelta(days=CULTURES[fk]["campaign_days"] + 40) for fk in fruit_keys)
    days = pd.date_range(t_start, t_end, freq="D")
    nd = len(days)

    leituras = []
    for _, wh in df_arm.iterrows():
        ca = wh["tipo_controlo"] == "Controlled"
        if ca:
            temp = 0.8 + 0.25 * rng.standard_normal(nd)
            hum = np.clip(94.0 + 1.2 * rng.standard_normal(nd), 88, 98)
            eth = np.clip(0.02 + 0.01 * rng.standard_normal(nd), 0.0, None)
        else:
            base_t = rng.uniform(2.0, 3.5)
            temp = base_t + 0.7 * rng.standard_normal(nd)
            hum = np.clip(rng.uniform(86, 91) + 2.5 * rng.standard_normal(nd), 70, 98)
            eth_level = rng.uniform(0.15, 0.45)
            eth = np.clip(eth_level + 0.12 * rng.standard_normal(nd), 0.0, None)
        # Excursões (falhas de frio / portas abertas): ~1.5% dos dias, duram 1-3 dias
        n_exc = rng.binomial(nd, 0.015)
        for _ in range(n_exc):
            d0 = int(rng.integers(0, nd))
            dur = int(rng.integers(1, 4))
            temp[d0:d0 + dur] += rng.uniform(2.5, 6.0)
            eth[d0:d0 + dur] += rng.uniform(0.1, 0.5)
        for i, d in enumerate(days):
            leituras.append({"armazem_id": wh["armazem_id"], "data": d, "temperatura": round(float(temp[i]), 2),
                             "humidade": round(float(hum[i]), 1), "etileno": round(float(eth[i]), 3)})
    df_leit = pd.DataFrame(leituras)

    # ------------------------------------------------------------------ Mercado (por cultura)
    mercado = []
    for fk in fruit_keys:
        cfg = CULTURES[fk]
        # Preço: tendência sazonal por temporada (barato na colheita, sobe com a escassez) + AR(1) + picos
        price = np.zeros(nd)
        demand = np.zeros(nd)
        for year in range(first_year - 1, first_year + n_seasons + 1):
            h0, h1 = _season_dates(year, cfg["harvest"])
            camp_end = h1 + pd.Timedelta(days=cfg["campaign_days"])
            season_lots = df_lot[(df_lot["tipo_fruta"] == fk) & (df_lot["temporada"] == year)]
            stock = float(season_lots["quantidade_kg"].sum())
            idx = np.where((days >= h0) & (days < camp_end))[0]
            if len(idx) == 0:
                continue
            x = (days[idx] - h0).days.values / max(1.0, (camp_end - h0).days)
            year_mult = rng.uniform(0.85, 1.15)
            price[idx] = cfg["price"] * year_mult * (0.82 + 0.55 * x ** 1.4)
            if stock > 0:
                # Procura: forma de sino ao longo da campanha, total ~ 0.95-1.15 x stock da temporada
                shape = 0.85 + 0.75 * np.sin(np.pi * np.clip(x * 1.05, 0, 1)) ** 0.8
                shape = shape / shape.sum()
                total = stock * rng.uniform(0.95, 1.15)
                demand[idx] = total * shape
        # Fora da campanha: preço alto, procura residual
        off = price == 0
        price[off] = cfg["price"] * 1.4
        demand[off] = demand[~off].mean() * 0.05 if (~off).any() else 0.0
        # AR(1) multiplicativo + picos de preço
        ar = np.zeros(nd)
        for i in range(1, nd):
            ar[i] = 0.93 * ar[i - 1] + 0.025 * rng.standard_normal()
        spikes = np.zeros(nd)
        for _ in range(rng.binomial(nd, 0.01)):
            d0 = int(rng.integers(0, nd))
            spikes[d0:d0 + int(rng.integers(5, 15))] += rng.uniform(0.12, 0.30)
        price = np.maximum(0.15, price * (1.0 + ar + spikes))
        # Procura: dia da semana + ruído; picos de preço reduzem ligeiramente a procura
        dow = np.array([1.05, 1.0, 1.0, 1.05, 1.15, 0.9, 0.6])[days.dayofweek.values]
        demand = demand * dow * np.clip(1.0 + 0.15 * rng.standard_normal(nd), 0.5, 1.6) * (1.0 - 0.3 * spikes)
        demand = np.maximum(0.0, demand)
        forecast = demand * np.clip(1.0 + 0.12 * rng.standard_normal(nd), 0.6, 1.5)
        for i, d in enumerate(days):
            mercado.append({"perfil": perfil, "cultura": cfg["cultura"], "data": d,
                            "preco_kg": round(float(price[i]), 3), "vendas_kg": round(float(demand[i]), 1),
                            "procura_prevista_kg": round(float(forecast[i]), 1)})
    df_merc = pd.DataFrame(mercado)

    return {"Armazens": df_arm, "Lotes": df_lot, "Leituras": df_leit, "Mercado": df_merc}


def generate_excel_bytes(**kwargs) -> bytes:
    return to_excel_bytes(generate(**kwargs), readme=readme_frame())


def main():
    ap = argparse.ArgumentParser(description="Gerar Excel sintético para o Stock Agent")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "dados_sinteticos_stock_agent.xlsx"))
    ap.add_argument("--perfil", default="Produtor_Demo")
    ap.add_argument("--frutas", default="kiwi_hayward,pear")
    ap.add_argument("--armazens", type=int, default=6)
    ap.add_argument("--frac_ac", type=float, default=0.5)
    ap.add_argument("--temporadas", type=int, default=5)
    ap.add_argument("--ano_inicial", type=int, default=2020)
    ap.add_argument("--lotes", type=int, default=24)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    b = generate_excel_bytes(perfil=a.perfil, fruit_keys=a.frutas.split(","), n_warehouses=a.armazens,
                             frac_controlled=a.frac_ac, n_seasons=a.temporadas, first_year=a.ano_inicial,
                             lots_per_season=a.lotes, seed=a.seed)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "wb") as f:
        f.write(b)
    print(f"Excel gerado: {a.out}")


if __name__ == "__main__":
    main()
