"""
Treina os modelos POR DEFEITO do Stock Agent (um por fruta do Lifecycle x modo), com dados sintéticos.

São usados pelo Web Service quando um perfil ainda não tem modelo próprio. Na decisão, o estado é normalizado
com as escalas do próprio perfil (preço, procura e tamanho dos lotes), por isso servem para qualquer volume.

    python -m stock_agent.train_defaults --out "<models_storage>" [--frutas kiwi_hayward,apple_gala] [--workers 6]
"""
import argparse
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

DEFAULT_FRUITS = ["kiwi_hayward", "kiwi_gold", "apple_gala", "apple_fuji", "apple_golden", "apple_reineta"]
EPISODES = {"lot": 400, "warehouse": 600}


def _train_one(fruit, mode, out_root, seed):
    import torch
    torch.set_num_threads(1)
    from .synthetic import generate, CULTURES
    from .schema import normalize
    from .training import train_generator, TrainConfig
    from .model_io import save_to_storage, DEFAULT_PROFILE

    t0 = time.time()
    data = normalize(generate(perfil="Sintetico", fruit_keys=[fruit], n_warehouses=6, frac_controlled=0.5,
                              n_seasons=6, lots_per_season=24, seed=seed))
    cultura = CULTURES[fruit]["cultura"]
    seasons = sorted(data["Lotes"]["temporada"].unique().tolist())
    result = None
    for ev in train_generator(data, "Sintetico", cultura, mode, seasons[:-1], seasons[-1:],
                              cfg=TrainConfig(episodes=EPISODES[mode], seed=seed)):
        if ev["type"] == "done":
            result = ev
    path = save_to_storage(out_root, result["zip_bytes"], DEFAULT_PROFILE, fruit, mode)
    m = result["config"]["metrics"]
    return (f"{fruit:14s} {mode:9s} | RL lucro {m['validacao_lucro_eur']:>10,.0f} desp {m['validacao_desperdicio_pct']:5.1f}% | "
            f"FEFO lucro {m['fefo_lucro_eur']:>10,.0f} desp {m['fefo_desperdicio_pct']:5.1f}% | "
            f"{'OK ' if m['melhor_que_fefo'] else 'ABAIXO FEFO'} | {time.time() - t0:.0f}s -> {path}")


def main():
    ap = argparse.ArgumentParser(description="Treinar modelos por defeito do Stock Agent")
    ap.add_argument("--out", default=os.environ.get("STOCK_AGENT_MODELS",
                                                    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models_storage")))
    ap.add_argument("--frutas", default=",".join(DEFAULT_FRUITS))
    ap.add_argument("--modos", default="lot,warehouse")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    jobs = [(f, m) for f in a.frutas.split(",") for m in a.modos.split(",")]
    print(f"A treinar {len(jobs)} modelos por defeito em {a.out} ({a.workers} processos)...", flush=True)
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(_train_one, f, m, a.out, a.seed + i): (f, m) for i, (f, m) in enumerate(jobs)}
        for fut in as_completed(futs):
            try:
                print(fut.result(), flush=True)
            except Exception as e:  # noqa: BLE001
                print(f"ERRO {futs[fut]}: {e}", flush=True)


if __name__ == "__main__":
    main()
