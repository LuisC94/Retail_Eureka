"""
CÓDIGO ORIGINAL DOS NOTEBOOKS train-RC-PT-1053.ipynb / inference-RC-PT-1053.ipynb (C:\\buyerAgent).

Ficheiro GERADO automaticamente: cada classe/função abaixo é o texto exato da célula de origem
(extraído por AST). Não editar à mão - para atualizar, voltar a gerar a partir dos notebooks.

  Origem:
    - Treino MLP + MMD Kernels (célula 17): kernels MMD, create_dataloaders, SimpleMLP, tilted_loss,
      set_lr, train_model, predict_dataframe, calculate_item_metrics, aggregate_global_score, set_seed
      (SimpleMLP, tilted_loss, set_lr e train_model são idênticos aos da célula 13 - MLP simples)
    - Treino Autoformer + MMD Kernels (célula 11): Time2Vec, SeriesDecomp, AutoCorrelation,
      AutoformerEncoderLayer, AutoformerEncoder, Autoformer_MLP
      (idênticos aos da célula 1 - Autoformer inicial)
    - Inferência (célula 15): predict_test_set_stepwise
"""
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset, WeightedRandomSampler
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error
from torch.cuda.amp import GradScaler, autocast
import math
import time
import os
import copy

# =========================
# Configurações (iguais nas células 1, 11, 13 e 17)
# =========================
LR = 1e-3
WEIGHT_DECAY = 1e-4
BATCH_SIZE = 256
DROPOUT = 0.2
NODE_EMB = 128
ATTN_HEADS = 8
KERNEL_SIZE = 13
CAT_EMB_DIM = 8
PATIENCE_EARLY = 15
CLIP_NORM = 1.0
AUTO_NUM_LAYERS = 2
QUANTILE = 0.5
WARMUP_FRACTION = 0.05

# =========================
# MMD / Kernels (células 11 e 17)
# =========================
MMD_WINDOW_L = 30
MMD_TAU = 1.4
KERNELS = ["laplace", "matern32", "cauchy", "rbf", "rq"]
MULTIPLIERS = [0.1, 0.5, 1.0, 2.0, 5.0]

lags = [1, 2, 3, 5, 7, 14, 30]

categorical_features = [
    "season_autumn",
    "season_spring",
    "season_summer",
    "season_winter"
]

numeric_features = [
    "holiday_proximity",
    "school_break_proximity",
    "festive_proximity",
    "day_of_week",
    "month",
    "day_of_year",
    "week",
    "day_of_week_sin",
    "day_of_week_cos",
    "month_sin",
    "month_cos",
    "day_of_year_sin",
    "day_of_year_cos",
    "weekend_proximity",
    "payday_proximity",
    "christmas_effect",
    "thanksgiving_effect",
] + [f"Lag-{lag}" for lag in lags]

features_to_normalize = [
    "holiday_proximity",
    "school_break_proximity",
    "festive_proximity",
    "weekend_proximity",
    "payday_proximity",
    "christmas_effect",
    "thanksgiving_effect",
] + [f"Lag-{lag}" for lag in lags]



# ======================================================================
# Célula 17 (MLP + MMD Kernels)
# ======================================================================

def get_kernel_function(name: str):
    def rbf(dist_sq, gamma):
        return np.exp(-gamma * dist_sq)

    def laplace(dist_sq, gamma):
        dist = np.sqrt(dist_sq + 1e-12)
        return np.exp(-gamma * dist)

    def matern32(dist_sq, gamma):
        dist = np.sqrt(dist_sq + 1e-12)
        sqrt3_d = np.sqrt(3) * dist * gamma
        return (1 + sqrt3_d) * np.exp(-sqrt3_d)

    def rational_quadratic(dist_sq, gamma, alpha=1.0):
        return (1 + (gamma * dist_sq) / (2 * alpha)) ** (-alpha)

    def cauchy(dist_sq, gamma):
        return 1.0 / (1.0 + gamma * dist_sq)

    registry = {
        "rbf": rbf,
        "laplace": laplace,
        "matern32": matern32,
        "rq": rational_quadratic,
        "cauchy": cauchy,
    }

    if name not in registry:
        raise ValueError(f"Kernel desconhecido: {name}")

    return registry[name]


def get_base_gamma(W: np.ndarray, kernel_name: str) -> float:
    W = np.asarray(W, float).ravel()

    if len(W) > 200:
        W = np.random.choice(W, 200, replace=False)

    W = W.reshape(-1, 1)
    dist_sq_matrix = (W - W.T) ** 2
    dists_sq = dist_sq_matrix[dist_sq_matrix > 0]

    if len(dists_sq) == 0:
        return 1.0

    median_sq = np.median(dists_sq)
    sigma = np.sqrt(median_sq) + 1e-6

    if kernel_name in ["rbf", "rq", "cauchy", "matern32"]:
        return 1.0 / (median_sq + 1e-6)

    if kernel_name == "laplace":
        return 1.0 / sigma

    return 1.0


def mmd2_scan_gamma(W: np.ndarray, kernel_name: str, gamma_multiplier: float) -> float:
    W = np.asarray(W, float).ravel()
    L = len(W)

    if L < 3:
        return 0.0

    W_col = W.reshape(-1, 1)
    dist_sq_global = (W_col - W_col.T) ** 2

    base_gamma = get_base_gamma(W, kernel_name)
    gamma = base_gamma * gamma_multiplier

    k_func = get_kernel_function(kernel_name)
    K_global = k_func(dist_sq_global, gamma)
    np.fill_diagonal(K_global, 0.0)

    best_score = 0.0

    for k in range(1, L):
        K_L = K_global[:k, :k]
        K_R = K_global[k:, k:]
        K_LR = K_global[:k, k:]

        m = k
        n = L - k

        term_L = K_L.sum() / (m * (m - 1)) if m > 1 else 0.0
        term_R = K_R.sum() / (n * (n - 1)) if n > 1 else 0.0
        term_LR = K_LR.mean()

        score = term_L + term_R - 2.0 * term_LR

        if score > best_score:
            best_score = score

    return best_score


def rolling_mmd_scores(series, L, kernel_name, gamma_multiplier):
    r = np.asarray(series, float).ravel()
    T = len(r)

    if T < L:
        return np.zeros(0, dtype=float)

    scores = np.zeros(T - L + 1, dtype=float)

    for i in range(T - L + 1):
        W = r[i:i + L]
        scores[i] = mmd2_scan_gamma(
            W,
            kernel_name=kernel_name,
            gamma_multiplier=gamma_multiplier
        )

    return scores


def scores_to_weights(
    scores,
    tau=1.4,
    w_min=0.02,
    w_max=50.0,
    eps=1e-8,
    delta=1e-6
):
    s = np.asarray(scores, float)

    if len(s) == 0:
        return np.array([], dtype=float)

    s = np.maximum(s, 0.0)

    s_min = float(s.min())
    s_max = float(s.max())

    denom = max(s_max - s_min, eps)
    z = (s - s_min) / denom

    # tau=0 -> uniforme; tau maior -> sampling mais concentrado
    w = np.clip((z + delta) ** tau, w_min, w_max)

    return w


def compute_mmd_kernel_weights(
    df_train,
    L,
    kernel_name,
    gamma_multiplier,
    tau,
    target_col="y",
    date_col="ds",
    group_col="node_idx"
):
    df = df_train.copy().reset_index(drop=True)
    df["_row_id"] = np.arange(len(df))

    raw_scores = np.zeros(len(df), dtype=float)

    for node, grp in df.groupby(group_col, sort=False):
        grp_sorted = grp.sort_values(date_col)
        vals = grp_sorted[target_col].values.astype(float)
        n = len(vals)

        if n >= L:
            scores = rolling_mmd_scores(
                vals,
                L=L,
                kernel_name=kernel_name,
                gamma_multiplier=gamma_multiplier
            )

            starts = np.arange(0, n - L + 1, dtype=int)
            tmp_scores = np.zeros(n, dtype=float)
            counts = np.zeros(n, dtype=float)

            for win_start, score in zip(starts, scores):
                win_end = win_start + L
                tmp_scores[win_start:win_end] += score
                counts[win_start:win_end] += 1.0

            mask = counts > 0

            if mask.any():
                tmp_scores[mask] = tmp_scores[mask] / counts[mask]
                tmp_scores[~mask] = tmp_scores[mask].min()
        else:
            tmp_scores = np.zeros(n, dtype=float)

        raw_scores[grp_sorted["_row_id"].values] = tmp_scores

    weights = scores_to_weights(raw_scores, tau=tau)

    return weights.astype(np.float32)


def create_dataloaders(df_train, df_val, weights=None):
    train_dataset = TensorDataset(
        torch.tensor(df_train["item_id_idx"].values, dtype=torch.long),
        torch.tensor(df_train["store_id_idx"].values, dtype=torch.long),
        torch.tensor(df_train[numeric_features].values, dtype=torch.float32),
        torch.tensor(df_train[categorical_features].values, dtype=torch.long),
        torch.tensor(df_train["node_idx"].values, dtype=torch.long),
        torch.tensor(df_train["y"].values, dtype=torch.float32).view(-1, 1),
    )

    if weights is not None:
        sampler = WeightedRandomSampler(
            weights=torch.tensor(weights, dtype=torch.float32),
            num_samples=len(weights),
            replacement=True,
        )

        train_loader = DataLoader(
            train_dataset,
            batch_size=BATCH_SIZE,
            sampler=sampler,
        )
    else:
        train_loader = DataLoader(
            train_dataset,
            batch_size=BATCH_SIZE,
            shuffle=True,
        )

    val_dataset = TensorDataset(
        torch.tensor(df_val["item_id_idx"].values, dtype=torch.long),
        torch.tensor(df_val["store_id_idx"].values, dtype=torch.long),
        torch.tensor(df_val[numeric_features].values, dtype=torch.float32),
        torch.tensor(df_val[categorical_features].values, dtype=torch.long),
        torch.tensor(df_val["node_idx"].values, dtype=torch.long),
        torch.tensor(df_val["y"].values, dtype=torch.float32).view(-1, 1),
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=BATCH_SIZE,
        shuffle=False,
    )

    return train_loader, val_loader


class SimpleMLP(nn.Module):
    def __init__(
        self,
        num_nodes,
        node_embedding_dim,
        n_numeric_features,
        n_categorical_features,
        cat_embedding_dim,
        output_size=1,
        dropout_rate=DROPOUT,
    ):
        super().__init__()

        self.node_embeddings = nn.Embedding(num_nodes, node_embedding_dim)

        self.categorical_embeddings = nn.ModuleList([
            nn.Embedding(2, cat_embedding_dim)
            for _ in range(n_categorical_features)
        ])

        mlp_input_dim = (
            node_embedding_dim
            + n_numeric_features
            + n_categorical_features * cat_embedding_dim
        )

        self.mlp = nn.Sequential(
            nn.Linear(mlp_input_dim, 1024),
            nn.BatchNorm1d(1024),
            nn.GELU(),
            nn.Dropout(dropout_rate),

            nn.Linear(1024, 512),
            nn.BatchNorm1d(512),
            nn.GELU(),
            nn.Dropout(dropout_rate),

            nn.Linear(512, 256),
            nn.BatchNorm1d(256),
            nn.GELU(),
            nn.Dropout(dropout_rate),

            nn.Linear(256, 128),
            nn.BatchNorm1d(128),
            nn.GELU(),
            nn.Dropout(dropout_rate),

            nn.Linear(128, 64),
            nn.GELU(),

            nn.Linear(64, 32),
            nn.GELU(),

            nn.Linear(32, output_size),
        )

    def forward(self, numeric_features, categorical_features, node_indices):
        node_emb = self.node_embeddings(node_indices)

        if categorical_features.size(1) > 0:
            cat_embs = [
                self.categorical_embeddings[i](categorical_features[:, i])
                for i in range(categorical_features.size(1))
            ]
            cat_emb = torch.cat(cat_embs, dim=1)
        else:
            cat_emb = torch.empty((node_emb.size(0), 0), device=node_emb.device)

        x = torch.cat([node_emb, numeric_features, cat_emb], dim=1)

        return self.mlp(x)


def tilted_loss(y_true, y_pred, quantile=QUANTILE, weights=None):
    errors = y_true - y_pred
    loss = torch.where(
        errors >= 0,
        quantile * errors,
        (quantile - 1) * errors
    )

    if weights is not None:
        loss = loss * weights

    return loss.mean()


def set_lr(optimizer, lr_value):
    for g in optimizer.param_groups:
        g["lr"] = lr_value


def train_model(model, train_loader, val_loader, device, num_epochs=1000):
    optimizer = optim.AdamW(
        model.parameters(),
        lr=LR,
        weight_decay=WEIGHT_DECAY
    )

    scaler_amp = GradScaler(enabled=(device.type == "cuda"))

    train_losses = []
    val_losses = []

    best_val_loss = float("inf")
    best_state = None
    patience_counter = 0

    warmup_epochs = max(1, int(WARMUP_FRACTION * num_epochs))

    cosine = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer,
        T_max=max(1, num_epochs - warmup_epochs),
        eta_min=1e-6,
    )

    start_time = time.time()

    for epoch in range(num_epochs):
        if epoch < warmup_epochs:
            set_lr(optimizer, LR * (epoch + 1) / warmup_epochs)
        else:
            if epoch == warmup_epochs:
                set_lr(optimizer, LR)
            cosine.step()

        model.train()
        epoch_train_loss = 0.0

        for item_ids, store_ids, numeric_feats, cat_feats, node_indices, targets in train_loader:
            numeric_feats = numeric_feats.to(device)
            cat_feats = cat_feats.to(device)
            node_indices = node_indices.to(device)
            targets = targets.to(device)

            optimizer.zero_grad(set_to_none=True)

            with autocast(enabled=(device.type == "cuda")):
                outputs = model(numeric_feats, cat_feats, node_indices)

                weights_q = torch.where(
                    targets > 0,
                    torch.tensor(1.0, device=device),
                    torch.tensor(0.5, device=device),
                )

                loss = tilted_loss(
                    targets,
                    outputs,
                    quantile=QUANTILE,
                    weights=weights_q
                )

            scaler_amp.scale(loss).backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=CLIP_NORM)
            scaler_amp.step(optimizer)
            scaler_amp.update()

            epoch_train_loss += loss.item() * targets.size(0)

        epoch_train_loss /= len(train_loader.dataset)
        train_losses.append(epoch_train_loss)

        model.eval()
        epoch_val_loss = 0.0

        with torch.no_grad():
            for item_ids, store_ids, numeric_feats, cat_feats, node_indices, targets in val_loader:
                numeric_feats = numeric_feats.to(device)
                cat_feats = cat_feats.to(device)
                node_indices = node_indices.to(device)
                targets = targets.to(device)

                with autocast(enabled=(device.type == "cuda")):
                    outputs = model(numeric_feats, cat_feats, node_indices)

                    weights_q = torch.where(
                        targets > 0,
                        torch.tensor(1.0, device=device),
                        torch.tensor(0.5, device=device),
                    )

                    loss = tilted_loss(
                        targets,
                        outputs,
                        quantile=QUANTILE,
                        weights=weights_q
                    )

                epoch_val_loss += loss.item() * targets.size(0)

        epoch_val_loss /= len(val_loader.dataset)
        val_losses.append(epoch_val_loss)

        if (epoch + 1) % 25 == 0:
            print(
                f"[{epoch + 1}/{num_epochs}] "
                f"Train: {epoch_train_loss:.4f} | Val: {epoch_val_loss:.4f}"
            )

        if epoch_val_loss < best_val_loss - 1e-6:
            best_val_loss = epoch_val_loss
            best_state = {
                k: v.detach().cpu().clone()
                for k, v in model.state_dict().items()
            }
            patience_counter = 0
        else:
            patience_counter += 1

            if patience_counter >= PATIENCE_EARLY:
                print(f"Early stopping na época {epoch + 1}")
                print(f"Melhor Val Loss: {best_val_loss:.6f}")
                break

    if best_state is not None:
        model.load_state_dict(best_state)

    train_time = time.time() - start_time

    return train_losses, val_losses, train_time


def predict_dataframe(df_input, model, device):
    model.eval()

    dataset = TensorDataset(
        torch.tensor(df_input[numeric_features].values, dtype=torch.float32),
        torch.tensor(df_input[categorical_features].values, dtype=torch.long),
        torch.tensor(df_input["node_idx"].values, dtype=torch.long),
    )

    loader = DataLoader(
        dataset,
        batch_size=BATCH_SIZE,
        shuffle=False
    )

    preds = []

    with torch.no_grad():
        for numeric_feats, cat_feats, node_indices in loader:
            numeric_feats = numeric_feats.to(device)
            cat_feats = cat_feats.to(device)
            node_indices = node_indices.to(device)

            with autocast(enabled=(device.type == "cuda")):
                outputs = model(numeric_feats, cat_feats, node_indices)

            preds.append(outputs.squeeze().cpu().numpy())

    preds = np.concatenate(preds)
    preds = np.clip(preds, 0, None)

    df_pred = df_input.copy()
    df_pred["predict"] = preds

    return df_pred


def calculate_item_metrics(df_pred):
    item_metrics = {}

    for item in df_pred["item_id"].unique():
        df_item = df_pred[df_pred["item_id"] == item].dropna(subset=["predict"])

        if not df_item.empty:
            mae = mean_absolute_error(df_item["y"], df_item["predict"])
            rmse = np.sqrt(mean_squared_error(df_item["y"], df_item["predict"]))
            bias = np.mean(df_item["predict"] - df_item["y"])
            avg_bias = abs(bias)
            score = 0.5 * rmse + 0.25 * mae + 0.25 * avg_bias

            item_metrics[item] = {
                "mae": mae,
                "rmse": rmse,
                "bias": bias,
                "avg_bias": avg_bias,
                "score": score,
            }

    return item_metrics


def aggregate_global_score(item_metrics):
    if not item_metrics:
        return float("inf")

    return float(np.mean([m["score"] for m in item_metrics.values()]))


def set_seed(seed):
    torch.manual_seed(seed)
    np.random.seed(seed)

    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


# ======================================================================
# Célula 11 (Autoformer + MMD Kernels)
# ======================================================================

class Time2Vec(nn.Module):
    def __init__(self, d_model, num_frequencies=20):
        super().__init__()

        self.linear_weight = nn.Parameter(torch.randn(1, 1, d_model // 2))
        self.linear_bias = nn.Parameter(torch.randn(1, 1, d_model // 2))
        self.periodic_weight = nn.Parameter(torch.randn(1, 1, num_frequencies))
        self.periodic_bias = nn.Parameter(torch.randn(1, 1, num_frequencies))
        self.out_projection = nn.Linear(d_model // 2 + num_frequencies, d_model)

    def forward(self, x):
        b, L, _ = x.size()

        t = torch.arange(
            L,
            dtype=torch.float,
            device=x.device
        ).unsqueeze(0).expand(b, L, 1)

        linear = t * self.linear_weight + self.linear_bias
        periodic = torch.sin(t * self.periodic_weight + self.periodic_bias)

        te = torch.cat([linear, periodic], dim=-1)
        te = self.out_projection(te)

        return x + te


class SeriesDecomp(nn.Module):
    def __init__(self, kernel_size):
        super().__init__()

        self.kernel_size = kernel_size

        self.avg = nn.AvgPool1d(
            kernel_size=kernel_size,
            stride=1,
            padding=kernel_size // 2
        )

    def forward(self, x):
        if x.size(1) < self.kernel_size:
            pad = self.kernel_size - x.size(1)

            x_padded = F.pad(
                x,
                (0, 0, pad, pad),
                mode="replicate"
            )
        else:
            x_padded = x

        trend = self.avg(
            x_padded.permute(0, 2, 1)
        ).permute(0, 2, 1)

        if x.size(1) < self.kernel_size:
            trend = trend[:, :x.size(1), :]

        seasonal = x - trend

        return seasonal, trend


class AutoCorrelation(nn.Module):
    def __init__(self, d_model, n_heads, top_k=5, dropout=0.2):
        super().__init__()

        if d_model % n_heads != 0:
            raise ValueError("d_model must be divisible by n_heads")

        self.n_heads = n_heads
        self.top_k = top_k
        self.head_dim = d_model // n_heads
        self.scale = 1.0 / math.sqrt(self.head_dim)

        self.q = nn.Linear(d_model, d_model)
        self.k = nn.Linear(d_model, d_model)
        self.v = nn.Linear(d_model, d_model)
        self.out = nn.Linear(d_model, d_model)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x):
        B, L, D = x.size()

        q = self.q(x).view(B, L, self.n_heads, self.head_dim)
        k = self.k(x).view(B, L, self.n_heads, self.head_dim)
        v = self.v(x).view(B, L, self.n_heads, self.head_dim)

        scores = torch.einsum(
            "blhd,bmhd->blhm",
            q,
            k
        ) * self.scale

        tk = min(self.top_k, L)

        _, topk_idx = torch.topk(
            scores,
            tk,
            dim=-1
        )

        v_heads = v.permute(0, 2, 1, 3)

        idx = topk_idx.permute(0, 2, 1, 3).unsqueeze(-1)
        idx = idx.expand(-1, -1, -1, -1, self.head_dim)

        v_expand = v_heads.unsqueeze(2).expand(
            -1,
            -1,
            L,
            -1,
            -1
        )

        selected = torch.gather(
            v_expand,
            dim=3,
            index=idx
        )

        out = selected.sum(dim=3)
        out = out.permute(0, 2, 1, 3).contiguous().view(B, L, D)

        return self.dropout(self.out(out))


class AutoformerEncoderLayer(nn.Module):
    def __init__(
        self,
        d_model,
        n_heads,
        kernel_size=KERNEL_SIZE,
        dropout=DROPOUT
    ):
        super().__init__()

        self.decomp = SeriesDecomp(kernel_size)
        self.time2vec = Time2Vec(d_model)
        self.auto_corr = AutoCorrelation(
            d_model,
            n_heads,
            top_k=5,
            dropout=dropout
        )

        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)
        self.dropout = nn.Dropout(dropout)

        self.ffn = nn.Sequential(
            nn.Linear(d_model, d_model * 4),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(d_model * 4, d_model),
        )

    def forward(self, x):
        residual = x

        seasonal, trend = self.decomp(x)
        seasonal = self.time2vec(seasonal)

        seasonal_out = self.auto_corr(seasonal)
        seasonal_out = self.norm1(
            seasonal + self.dropout(seasonal_out)
        )

        ffn_out = self.ffn(seasonal_out)
        seasonal_out = self.norm2(
            seasonal_out + self.dropout(ffn_out)
        )

        return seasonal_out + trend + residual


class AutoformerEncoder(nn.Module):
    def __init__(
        self,
        d_model,
        n_heads,
        num_layers=AUTO_NUM_LAYERS
    ):
        super().__init__()

        self.layers = nn.ModuleList([
            AutoformerEncoderLayer(d_model, n_heads)
            for _ in range(num_layers)
        ])

        self.pos_encoder = nn.Parameter(
            torch.randn(1, 1, d_model)
        )

    def forward(self, x):
        x = x + self.pos_encoder.expand(
            x.size(0),
            x.size(1),
            -1
        )

        for layer in self.layers:
            x = layer(x)

        return x


class Autoformer_MLP(nn.Module):
    def __init__(
        self,
        num_nodes,
        node_embedding_dim,
        n_numeric_features,
        n_categorical_features,
        cat_embedding_dim,
        output_size=1,
        dropout_rate=DROPOUT,
    ):
        super().__init__()

        self.node_embeddings = nn.Parameter(
            torch.randn(num_nodes, node_embedding_dim)
        )

        self.autoformer = AutoformerEncoder(
            d_model=node_embedding_dim,
            n_heads=ATTN_HEADS,
            num_layers=AUTO_NUM_LAYERS,
        )

        self.categorical_embeddings = nn.ModuleList([
            nn.Embedding(2, cat_embedding_dim)
            for _ in range(n_categorical_features)
        ])

        mlp_input_dim = (
            node_embedding_dim
            + n_numeric_features
            + n_categorical_features * cat_embedding_dim
        )

        self.mlp = nn.Sequential(
            nn.Linear(mlp_input_dim, 512),
            nn.BatchNorm1d(512),
            nn.GELU(),
            nn.Dropout(dropout_rate),

            nn.Linear(512, 256),
            nn.BatchNorm1d(256),
            nn.GELU(),
            nn.Dropout(dropout_rate),

            nn.Linear(256, 128),
            nn.BatchNorm1d(128),
            nn.GELU(),
            nn.Dropout(dropout_rate),

            nn.Linear(128, 64),
            nn.GELU(),

            nn.Linear(64, 32),
            nn.GELU(),

            nn.Linear(32, output_size),
        )

    def forward(self, numeric_features, categorical_features, node_indices):
        x = self.node_embeddings[node_indices]

        x = x.unsqueeze(1)
        x = self.autoformer(x).squeeze(1)

        if categorical_features.size(1) > 0:
            cat_embs = [
                self.categorical_embeddings[i](
                    categorical_features[:, i]
                )
                for i in range(categorical_features.size(1))
            ]

            cat_emb = torch.cat(cat_embs, dim=1)
        else:
            cat_emb = torch.empty(
                (x.size(0), 0),
                device=x.device
            )

        x = torch.cat(
            [x, numeric_features, cat_emb],
            dim=1
        )

        return self.mlp(x)


# ======================================================================
# Inferência - célula 15
# ======================================================================

def predict_test_set_stepwise(
    df_test,
    model,
    numeric_features,
    categorical_features,
    lags,
    df_historico,
    scaler,
    item_store_to_idx,
    device,
    features_to_normalize
):
    df_test = df_test.copy()
    df_test["predict"] = np.nan

    df_history_updated = df_historico.copy()

    df_history_updated["item_id"] = df_history_updated["item_id"].astype(str)
    df_history_updated["store_id"] = df_history_updated["store_id"].astype(str)
    df_history_updated["ds"] = pd.to_datetime(df_history_updated["ds"]).dt.normalize()

    df_test["item_id"] = df_test["item_id"].astype(str)
    df_test["store_id"] = df_test["store_id"].astype(str)
    df_test["ds"] = pd.to_datetime(df_test["ds"]).dt.normalize()

    first_test_day = df_test["ds"].min()

    df_history_updated.loc[
        df_history_updated["ds"] >= first_test_day,
        "y"
    ] = np.nan

    test_days = sorted(df_test["ds"].unique())
    lag_cols = [f"Lag-{lag}" for lag in lags]

    model.eval()
    start_time = time.time()

    with torch.no_grad():
        for day in test_days:
            past_data = df_history_updated[df_history_updated["ds"] < day].copy()
            current_day = df_test[df_test["ds"] == day].copy()

            current_day["item_store_id"] = (
                current_day["item_id"].astype(str)
                + "_"
                + current_day["store_id"].astype(str)
            )

            current_day["node_idx"] = (
                current_day["item_store_id"]
                .map(item_store_to_idx)
                .fillna(-1)
                .astype(int)
            )

            valid_mask = current_day["node_idx"] != -1
            valid_index = current_day[valid_mask].index
            current_day = current_day[valid_mask].copy()

            if current_day.empty:
                continue

            current_day.drop(columns=lag_cols, inplace=True, errors="ignore")

            for lag in lags:
                lag_day = day - pd.Timedelta(days=lag)

                lag_data = (
                    past_data[past_data["ds"] == lag_day]
                    [["item_id", "store_id", "y"]]
                    .rename(columns={"y": f"Lag-{lag}"})
                )

                if not lag_data.empty:
                    lag_data.drop_duplicates(
                        subset=["item_id", "store_id"],
                        keep="last",
                        inplace=True
                    )

                current_day = current_day.merge(
                    lag_data,
                    on=["item_id", "store_id"],
                    how="left"
                )

            current_day[lag_cols] = current_day[lag_cols].fillna(0).clip(lower=0)

            for feature in numeric_features + categorical_features:
                if feature not in current_day.columns:
                    current_day[feature] = 0

            for col in categorical_features:
                current_day[col] = current_day[col].fillna(0).astype(int)

            for col in numeric_features:
                current_day[col] = current_day[col].fillna(0).astype(float)

            current_day[features_to_normalize] = scaler.transform(
                current_day[features_to_normalize]
            )

            X_num = torch.tensor(
                current_day[numeric_features].values,
                dtype=torch.float32
            ).to(device)

            X_cat = torch.tensor(
                current_day[categorical_features].values,
                dtype=torch.long
            ).to(device)

            X_node = torch.tensor(
                current_day["node_idx"].values,
                dtype=torch.long
            ).to(device)

            with autocast(enabled=(device.type == "cuda")):
                preds = model(X_num, X_cat, X_node).squeeze().cpu().numpy()

            preds = np.atleast_1d(preds)
            preds = np.clip(preds, 0, None)

            df_test.loc[valid_index, "predict"] = preds

            predicted_day_df = current_day[["item_id", "store_id", "ds"]].copy()
            predicted_day_df["y"] = preds

            df_history_updated = pd.concat(
                [df_history_updated, predicted_day_df],
                ignore_index=True
            )

            df_history_updated["item_id"] = df_history_updated["item_id"].astype(str)
            df_history_updated["store_id"] = df_history_updated["store_id"].astype(str)
            df_history_updated["ds"] = pd.to_datetime(
                df_history_updated["ds"]
            ).dt.normalize()

    predict_time = time.time() - start_time

    return df_test, predict_time
