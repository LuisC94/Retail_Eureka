"""
Treino e previsão dos 4 modelos escolhidos dos notebooks RC-PT-1053 (WRMSSE no notebook de inferência):

  modelo_1  "Modelo Previsão 1"  MLP + MMD Kernels         (célula 17)  WRMSSE 0.7851
  modelo_2  "Modelo Previsão 2"  Autoformer + MMD Kernels  (célula 11)  WRMSSE 0.7535
  modelo_3  "Modelo Previsão 3"  MLP simples               (célula 13)  WRMSSE 0.7909
  modelo_4  "Modelo Previsão 4"  Autoformer inicial        (célula 1)   WRMSSE 0.8049

Toda a modelação (arquiteturas, perda, ciclo de treino, pesos MMD, pesquisa de kernel, inferência
passo-a-passo) vem de engine/notebook_code.py (código extraído dos notebooks). Este módulo apenas
monta os dados de uma série (utilizador/cultura), faz a divisão treino/validação e guarda o artefacto.
"""
import contextlib
import datetime
import io
import time

import numpy as np
import pandas as pd
import torch
from sklearn.preprocessing import StandardScaler

from . import notebook_code as nb
from .features import (ITEM_STORE_TO_IDX, daily_series, training_frame, history_frame, future_frame)

ARTIFACT_FORMAT = "rc-pt-1053-v1"
VAL_RATIO = 0.2
MIN_TRAIN_DAYS = max(nb.lags) + 8  # 38: precisa de pelo menos 30 dias de lags + validação

MODELS = {
    "modelo_1": {"display_name": "Modelo Previsão 1", "arch": "mlp", "mmd": True, "seed": 1200,
                 "source": "MLP + MMD Kernels (train-RC-PT-1053 célula 17)", "notebook_wrmsse": 0.7851},
    "modelo_2": {"display_name": "Modelo Previsão 2", "arch": "autoformer", "mmd": True, "seed": 1200,
                 "source": "Autoformer + MMD Kernels (train-RC-PT-1053 célula 11)", "notebook_wrmsse": 0.7535},
    "modelo_3": {"display_name": "Modelo Previsão 3", "arch": "mlp", "mmd": False, "seed": 340,
                 "source": "MLP simples (train-RC-PT-1053 célula 13)", "notebook_wrmsse": 0.7909},
    "modelo_4": {"display_name": "Modelo Previsão 4", "arch": "autoformer", "mmd": False, "seed": 1200,
                 "source": "Autoformer inicial (train-RC-PT-1053 célula 1)", "notebook_wrmsse": 0.8049},
}


def build_model(arch, device):
    kwargs = dict(num_nodes=len(ITEM_STORE_TO_IDX), node_embedding_dim=nb.NODE_EMB,
                  n_numeric_features=len(nb.numeric_features), n_categorical_features=len(nb.categorical_features),
                  cat_embedding_dim=nb.CAT_EMB_DIM)
    model = nb.SimpleMLP(**kwargs) if arch == "mlp" else nb.Autoformer_MLP(**kwargs)
    return model.to(device)


def split_train_val(df):
    n = len(df)
    n_val = max(7, int(round(n * VAL_RATIO)))
    df_train = df.iloc[:n - n_val].copy().reset_index(drop=True)
    df_val = df.iloc[n - n_val:].copy().reset_index(drop=True)
    # BatchNorm1d em modo treino não aceita um lote de 1 amostra (último lote com n % 256 == 1)
    if len(df_train) % nb.BATCH_SIZE == 1:
        df_train = df_train.iloc[1:].reset_index(drop=True)
    return df_train, df_val


def _predict_df(df, model, device):
    """predict_dataframe() do notebook falha se o último lote tiver 1 linha (squeeze -> escalar); duplica-se a última linha."""
    if len(df) % nb.BATCH_SIZE == 1:
        padded = pd.concat([df, df.iloc[[-1]]], ignore_index=True)
        return nb.predict_dataframe(padded, model, device).iloc[:len(df)]
    return nb.predict_dataframe(df, model, device)


def train(model_type, sales_history, progress_cb=None, device=None):
    cfg = MODELS[model_type]
    device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
    t0 = time.time()

    series = daily_series(sales_history)
    if len(series) < MIN_TRAIN_DAYS:
        raise ValueError(f"Histórico insuficiente: são necessários pelo menos {MIN_TRAIN_DAYS} dias consecutivos (recebidos {len(series)}).")
    df = training_frame(series)
    df_train, df_val = split_train_val(df)

    # Normalização (igual aos notebooks: scaler ajustado no treino)
    scaler = StandardScaler()
    df_train[nb.features_to_normalize] = scaler.fit_transform(df_train[nb.features_to_normalize])
    df_val[nb.features_to_normalize] = scaler.transform(df_val[nb.features_to_normalize])

    combos = [(k, m) for k in nb.KERNELS for m in nb.MULTIPLIERS] if cfg["mmd"] else [(None, None)]
    best = None
    sweep = []
    for i, (kernel_name, mult) in enumerate(combos, start=1):
        if kernel_name is not None:
            weights = nb.compute_mmd_kernel_weights(df_train=df_train, L=nb.MMD_WINDOW_L, kernel_name=kernel_name,
                                                    gamma_multiplier=mult, tau=nb.MMD_TAU, target_col="y",
                                                    date_col="ds", group_col="node_idx")
        else:
            weights = None
        train_loader, val_loader = nb.create_dataloaders(df_train, df_val, weights=weights)
        nb.set_seed(cfg["seed"])
        model = build_model(cfg["arch"], device)
        log = io.StringIO()
        with contextlib.redirect_stdout(log):
            train_losses, val_losses, train_time = nb.train_model(model, train_loader, val_loader, device, num_epochs=1000)
        df_val_pred = _predict_df(df_val, model, device)
        item_metrics = nb.calculate_item_metrics(df_val_pred)
        m = next(iter(item_metrics.values()))
        row = {"kernel": kernel_name, "multiplier": mult, "epochs": len(train_losses), "train_time": round(train_time, 2),
               **{k: round(float(v), 4) for k, v in m.items()}}
        sweep.append(row)
        if best is None or m["score"] < best["metrics"]["score"]:
            best = {"kernel": kernel_name, "multiplier": mult, "metrics": m,
                    "state_dict": {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}}
        if progress_cb:
            progress_cb({"step": i, "total_steps": len(combos), **row, "best_score": round(float(best["metrics"]["score"]), 4)})

    return {
        "format": ARTIFACT_FORMAT,
        "model_type": model_type,
        "display_name": cfg["display_name"],
        "arch": cfg["arch"],
        "source": cfg["source"],
        "seed": cfg["seed"],
        "state_dict": best["state_dict"],
        "scaler": scaler,
        "numeric_features": list(nb.numeric_features),
        "categorical_features": list(nb.categorical_features),
        "features_to_normalize": list(nb.features_to_normalize),
        "lags": list(nb.lags),
        "kernel": best["kernel"],
        "multiplier": best["multiplier"],
        "val_metrics": {k: round(float(v), 4) for k, v in best["metrics"].items()},
        "sweep": sweep,
        "n_train": len(df_train),
        "n_val": len(df_val),
        "first_date": str(series.index.min().date()),
        "last_date": str(series.index.max().date()),
        "training_time_seconds": round(time.time() - t0, 1),
        "trained_at": datetime.datetime.now().isoformat(timespec="seconds"),
    }


def load_model(artifact, device="cpu"):
    if artifact.get("format") != ARTIFACT_FORMAT:
        raise ValueError("Modelo guardado num formato antigo/incompatível. Volte a treinar este modelo.")
    model = build_model(artifact["arch"], torch.device(device))
    model.load_state_dict(artifact["state_dict"])
    model.eval()
    return model


def predict_horizon(artifact, sales_history, start_date=None, horizon_days=30, device="cpu"):
    """Previsão recursiva dia-a-dia (predict_test_set_stepwise do notebook)."""
    dev = torch.device(device)
    model = load_model(artifact, device)
    series = daily_series(sales_history)
    if start_date is None:
        start_date = series.index.max() + pd.Timedelta(days=1)
    start_date = pd.to_datetime(start_date).normalize()
    series = series[series.index < start_date]
    df_hist = history_frame(series)
    df_test = future_frame(start_date, horizon_days)
    df_pred, _ = nb.predict_test_set_stepwise(df_test=df_test, model=model, numeric_features=nb.numeric_features,
                                              categorical_features=nb.categorical_features, lags=nb.lags,
                                              df_historico=df_hist, scaler=artifact["scaler"],
                                              item_store_to_idx=ITEM_STORE_TO_IDX, device=dev,
                                              features_to_normalize=nb.features_to_normalize)
    return [(d.date(), round(float(p), 2)) for d, p in zip(df_pred["ds"], df_pred["predict"])]


def predict_series(artifact, sales_history, device="cpu"):
    """
    Previsão a 1 dia para cada dia do histórico, com os lags reais (predict_dataframe do notebook, usado na
    validação). É a série 'prediction' que o Buyer Agent usa no treino, ao lado das vendas reais.
    """
    dev = torch.device(device)
    model = load_model(artifact, device)
    series = daily_series(sales_history)
    df = training_frame(series)
    df[nb.features_to_normalize] = artifact["scaler"].transform(df[nb.features_to_normalize])
    df_pred = _predict_df(df, model, dev)
    return [(d.date(), round(float(p), 2)) for d, p in zip(df_pred["ds"], df_pred["predict"])]
