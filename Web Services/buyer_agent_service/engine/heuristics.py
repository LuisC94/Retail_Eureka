"""
Políticas de referência (regras clássicas de reposição) comparadas com o Buyer Agent.
Usadas na recomendação diária (/api/buyer/decide) e na validação no período de teste (engine/validation.py),
para que as duas comparações sejam exatamente iguais.
"""


def heuristic_orders(stock_total, in_transit, pred_today, next_predictions):
    """
    stock_total:      stock atual (kg)
    in_transit:       encomendas a caminho (kg)
    pred_today:       previsão de procura de hoje (kg)
    next_predictions: previsões dos dias seguintes, a começar em amanhã (kg)
    """
    nxt = [float(x) for x in (next_predictions or [])]
    pos = stock_total + in_transit
    next3 = sum(nxt[:3]) if nxt else pred_today * 3
    tomorrow = nxt[0] if nxt else pred_today
    dos_3d = max(0.0, next3 - pos)
    # Reposição do défice: o que sobra depois de hoje = stock + o que chega - procura de hoje.
    # (A versão anterior descontava o que chega hoje depois de o tirar das sobras: contava-o a menos e encomendava a menos.)
    naive = max(0.0, tomorrow - max(0.0, stock_total + in_transit - pred_today))
    s_min, s_max = 2.0 * pred_today, 5.0 * pred_today
    min_max = max(0.0, s_max - pos) if pos < s_min else 0.0
    return {"dos_3d_kg": round(dos_3d, 1), "cnn_naive_kg": round(naive, 1), "min_max_kg": round(min_max, 1)}
