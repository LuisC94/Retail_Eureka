"""
Rede Actor-Critic para conjuntos de tamanho variável (Deep Sets), partilhada pelos dois agentes.

Cada candidato (lote ou armazém) é codificado pela mesma rede, juntamente com o contexto de mercado.
Um resumo do conjunto (média + máximo) permite que a decisão sobre um candidato tenha em conta os outros.

- modo "lot":       uma probabilidade Bernoulli por lote ("colocar à venda hoje?") -> 0, 1 ou vários lotes.
- modo "warehouse": distribuição categórica sobre [ESPERAR, armazém_1, ..., armazém_k] -> no máximo 1 por semana.

Funciona com qualquer número de lotes/armazéns e é invariante à ordem.
"""
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F


def mlp(i, h, o, layers=2):
    mods = [nn.Linear(i, h), nn.ReLU()]
    for _ in range(layers - 1):
        mods += [nn.Linear(h, h), nn.ReLU()]
    mods.append(nn.Linear(h, o))
    return nn.Sequential(*mods)


class SetActorCritic(nn.Module):
    def __init__(self, f_item, f_ctx, mode, hidden=128):
        super().__init__()
        self.mode = mode
        self.hidden = hidden
        self.item_enc = mlp(f_item + f_ctx, hidden, hidden)
        self.ctx_enc = mlp(f_ctx, hidden, hidden, layers=1)
        self.item_head = mlp(4 * hidden, hidden, 1)
        self.wait_head = mlp(3 * hidden, hidden, 1) if mode == "warehouse" else None
        self.critic = mlp(3 * hidden + 1, hidden, 1)
        nn.init.constant_(self.item_head[-1].bias, -1.0 if mode == "lot" else 0.0)

    def _encode(self, feats, mask, ctx):
        B, N, _ = feats.shape
        c = ctx.unsqueeze(1).expand(B, N, ctx.shape[-1])
        h = F.relu(self.item_enc(torch.cat([feats, c], dim=-1)))           # B,N,H
        m = mask.unsqueeze(-1).float()
        cnt = m.sum(1).clamp(min=1.0)
        mean = (h * m).sum(1) / cnt                                         # B,H
        mx = torch.where(mask.unsqueeze(-1), h, torch.full_like(h, -1e4)).max(1).values
        mx = torch.where(mask.any(1, keepdim=True), mx, torch.zeros_like(mx))
        cz = F.relu(self.ctx_enc(ctx))                                      # B,H
        return h, mean, mx, cz, mask.float().sum(1, keepdim=True)

    def forward(self, feats, mask, ctx):
        """Devolve (logits, valor). logits: B,N (lot) ou B,N+1 (warehouse, índice 0 = esperar)."""
        B, N, _ = feats.shape
        h, mean, mx, cz, n = self._encode(feats, mask, ctx)
        g = torch.cat([mean, mx, cz], dim=-1)
        item_in = torch.cat([h, g.unsqueeze(1).expand(B, N, g.shape[-1])], dim=-1)
        item_logits = self.item_head(item_in).squeeze(-1)                   # B,N
        value = self.critic(torch.cat([g, n / 10.0], dim=-1)).squeeze(-1)
        if self.mode == "lot":
            return item_logits, value
        wait = self.wait_head(g)                                            # B,1
        logits = torch.cat([wait, item_logits], dim=1)
        logits = logits.masked_fill(~torch.cat([torch.ones_like(mask[:, :1]), mask], dim=1), -1e9)
        return logits, value

    # ------------------------------------------------------------------ distribuições
    def log_prob_entropy(self, logits, mask, actions):
        if self.mode == "lot":
            a = actions.float()
            lp = a * F.logsigmoid(logits) + (1 - a) * F.logsigmoid(-logits)
            p = torch.sigmoid(logits)
            ent = -(p * F.logsigmoid(logits) + (1 - p) * F.logsigmoid(-logits))
            m = mask.float()
            return (lp * m).sum(1), (ent * m).sum(1) / m.sum(1).clamp(min=1.0)
        dist = torch.distributions.Categorical(logits=logits)
        return dist.log_prob(actions.long()), dist.entropy()

    def probabilities(self, logits):
        return torch.sigmoid(logits) if self.mode == "lot" else torch.softmax(logits, dim=-1)


def pad_batch(items, f_item):
    """items: lista de arrays (n_i, f_item) -> tensor B,N,F e máscara B,N (N >= 1)."""
    B = len(items)
    N = max(1, max((len(x) for x in items), default=1))
    feats = np.zeros((B, N, f_item), dtype=np.float32)
    mask = np.zeros((B, N), dtype=bool)
    for b, x in enumerate(items):
        if len(x):
            feats[b, :len(x)] = x
            mask[b, :len(x)] = True
    return torch.from_numpy(feats), torch.from_numpy(mask)


def pad_actions(actions, N, mode):
    if mode == "warehouse":
        return torch.tensor([int(a) for a in actions], dtype=torch.long)
    out = np.zeros((len(actions), N), dtype=np.float32)
    for b, a in enumerate(actions):
        if len(a):
            out[b, :len(a)] = a
    return torch.from_numpy(out)


@torch.no_grad()
def act(model, obs, deterministic=False, rng=None):
    """Decide para uma observação; devolve (ação, log_prob, valor, probabilidades)."""
    feats, mask = pad_batch([obs["feats"]], model.item_enc[0].in_features - len(obs["ctx"]))
    ctx = torch.from_numpy(obs["ctx"]).unsqueeze(0)
    logits, value = model(feats, mask, ctx)
    probs = model.probabilities(logits)[0].numpy()
    n = len(obs["feats"])
    if model.mode == "lot":
        p = probs[:n]
        if deterministic:
            a = (p >= 0.5).astype(np.int64)
        else:
            a = ((rng.random(n) if rng is not None else np.random.random(n)) < p).astype(np.int64)
        lp, _ = model.log_prob_entropy(logits, mask, pad_actions([a], mask.shape[1], "lot"))
        return a, float(lp[0]), float(value[0]), p
    p = probs[:n + 1]
    if deterministic:
        a = int(np.argmax(p))
    else:
        p_ = p / p.sum()
        a = int((rng or np.random).choice(len(p_), p=p_))
    lp, _ = model.log_prob_entropy(logits, mask, torch.tensor([a]))
    return a, float(lp[0]), float(value[0]), p
