import os
import sys
import torch
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from loguru import logger

# Configurar caminhos
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
for path in [ROOT_DIR, os.path.join(ROOT_DIR, "Train_Interface"), SCRIPT_DIR]:
    if os.path.exists(path) and path not in sys.path:
        sys.path.insert(0, path)

from environment_constrained import StockEnvironment
from dsac_agent import DSACAgent

MIN_MAX_CONFIGS = {
    "3_080": {"s": 28, "S": 34},
    "3_090": {"s": 93, "S": 97},
    "3_252": {"s": 15, "S": 80},
    "3_586": {"s": 58, "S": 68},
    "911753": {"s": 92, "S": 144}
}

def normalize_sku(sku_str):
    s = str(sku_str).strip()
    if s.endswith(".xlsx"):
        s = os.path.basename(s).replace(".xlsx", "").replace("m5_foods_", "")
    sku_map = {
        "3080": "3_080", "3090": "3_090", "3252": "3_252", "3586": "3_586",
        "080": "3_080", "090": "3_090", "252": "3_252", "586": "3_586",
    }
    return sku_map.get(s, s)

def find_dataset(sku):
    override = os.getenv("EXCEL_PATH_OVERRIDE")
    if override and os.path.exists(override):
        return override

    fname = "911753_151dias_com_real.xlsx" if "911753" in str(sku) else f"m5_foods_{sku}.xlsx"
    candidates = [
        os.path.join(ROOT_DIR, "Dados", fname),
        os.path.join(ROOT_DIR, "Dados", f"m5_foods_{sku}.xlsx"),
        os.path.join(ROOT_DIR, "Dados", f"{sku}.xlsx"),
        os.path.join(ROOT_DIR, f"{sku}.xlsx"),
        os.path.join(ROOT_DIR, fname)
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return os.path.join(ROOT_DIR, "Dados", "m5_foods_3_080.xlsx")

def evaluate_dsac_vs_baselines(sku_input="3_080", with_noise=False, is_unconstrained=False):
    sku = normalize_sku(sku_input)
    excel_path = find_dataset(sku)
    
    constraint_str = "DESLIMITADO (Sem Teto de Compra)" if is_unconstrained else "LIMITADO (Max Compra = Maior Venda)"
    mode_str = "ESTOCASTICO (COM RUIDO: u = mu + sigma * eps)" if with_noise else "DETERMINISTICO (SEM RUIDO: a = tanh(mu))"
    print("=" * 80)
    print(f"      AVALIAÇÃO COMPARATIVA: AGENTE DSAC vs. MIN-MAX")
    print(f"      SKU: {sku} | Regime: {constraint_str} | Modo: {mode_str}")
    print("=" * 80)

    dir_prefix = f"modelos_dsac_deslimitado_{sku}" if is_unconstrained else f"modelos_dsac_{sku}"
    model_dir = os.path.join(SCRIPT_DIR, dir_prefix)
    actor_best = os.path.join(model_dir, "dsac_best_actor.pth")
    actor_latest = os.path.join(model_dir, "dsac_latest_actor.pth")

    actor_path = actor_best if os.path.exists(actor_best) else actor_latest
    if not os.path.exists(actor_path):
        logger.error(f"Pesos do modelo DSAC não encontrados em: {model_dir}")
        logger.error(f"Execute primeiro: python DSAC/train_dsac.py {sku}{' --unconstrained' if is_unconstrained else ''}")
        return

    # Ambientes de Teste
    env_dsac = StockEnvironment(excel_path, is_training=False, train_split=0.6, max_capacity=500, completely_unconstrained=is_unconstrained)
    env_mm = StockEnvironment(excel_path, is_training=False, train_split=0.6, max_capacity=500, completely_unconstrained=False)

    # Carregar Agente DSAC
    agent_dsac = DSACAgent(state_dim=30, action_dim=1, device="cpu")
    agent_dsac.actor.load_state_dict(torch.load(actor_path, map_location="cpu"))
    agent_dsac.actor.eval()
    logger.info(f"Modelo DSAC carregado com sucesso: {actor_path}")
    logger.info(f"Regime de Compra: {constraint_str} (Max Order Limit: {env_dsac.max_order_limit})")
    logger.info(f"Modo de Decisão: {mode_str}")

    # Configuração Min-Max oficial do benchmark
    mm_cfg = MIN_MAX_CONFIGS.get(sku, {"s": 28, "S": 34})
    s_min, S_max = mm_cfg["s"], mm_cfg["S"]
    logger.info(f"Heurística Min-Max Oficial: s={s_min} | S={S_max}")

    # Reset
    state_dsac = env_dsac.reset()
    state_mm = env_mm.reset()

    total_days = len(env_dsac.data)
    history_dsac = []
    history_mm = []

    cum_profit_dsac = 0.0
    cum_profit_mm = 0.0

    logger.info(f"Executando simulação nos {total_days} dias do conjunto de teste...")

    for day in range(total_days):
        # 1. AÇÃO DSAC (evaluate=False usa ruído estocástico; evaluate=True usa determinístico)
        act_norm_dsac = agent_dsac.select_action(state_dsac, evaluate=(not with_noise))
        act_pct_dsac = 0.5 * (float(act_norm_dsac[0]) + 1.0)
        action_dsac = round(act_pct_dsac * env_dsac.max_order_limit)

        next_state_dsac, _, done_dsac, info_dsac = env_dsac.step(action_dsac, update_stats=False)
        cum_profit_dsac += info_dsac['profit']
        state_dsac = next_state_dsac

        # 2. AÇÃO MIN-MAX (s, S) Oficial do Benchmark
        stock_hoje_mm = sum(env_mm.stock_profile) + env_mm.in_transit.get(env_mm.current_step, 0)
        vendas_hoje_mm = env_mm.data.iloc[env_mm.current_step]['real_value']
        stock_amanha_mm = max(0, stock_hoje_mm - vendas_hoje_mm) + env_mm.in_transit.get(env_mm.current_step + 1, 0)

        action_mm = 0
        if stock_amanha_mm <= s_min:
            action_mm = min(max(0, S_max - stock_amanha_mm), env_mm.max_order_limit)

        next_state_mm, _, done_mm, info_mm = env_mm.step(action_mm, update_stats=False)
        cum_profit_mm += info_mm['profit']
        state_mm = next_state_mm

        history_dsac.append({
            "dia": day + 1,
            "stock_final": info_dsac['final_stock'],
            "encomenda": action_dsac,
            "vendas": info_dsac['sales'],
            "vendas_perdidas": info_dsac['missed_sales'],
            "desperdicio": info_dsac['overflow_waste'],
            "lucro_diario": info_dsac['profit'],
            "lucro_acumulado": cum_profit_dsac,
            "custo_transporte": info_dsac['transport_cost'],
            "custo_armazem": info_dsac['storage_cost']
        })

        history_mm.append({
            "dia": day + 1,
            "stock_final": info_mm['final_stock'],
            "encomenda": action_mm,
            "vendas": info_mm['sales'],
            "vendas_perdidas": info_mm['missed_sales'],
            "desperdicio": info_mm['overflow_waste'],
            "lucro_diario": info_mm['profit'],
            "lucro_acumulado": cum_profit_mm,
            "custo_transporte": info_mm['transport_cost'],
            "custo_armazem": info_mm['storage_cost']
        })

    df_dsac = pd.DataFrame(history_dsac)
    df_mm = pd.DataFrame(history_mm)

    total_demand = df_dsac['vendas'].sum() + df_dsac['vendas_perdidas'].sum()
    service_dsac = (df_dsac['vendas'].sum() / total_demand * 100.0) if total_demand > 0 else 100.0
    service_mm = (df_mm['vendas'].sum() / total_demand * 100.0) if total_demand > 0 else 100.0

    print("\n" + "=" * 80)
    print(f"                      RESULTADOS COMPARATIVOS")
    print("=" * 80)
    print(f"{'Métrica':<35} | {'Min-Max Oficial':<18} | {'Agente DSAC':<18}")
    print("-" * 80)
    print(f"{'Lucro Total Líquido (€)':<35} | {cum_profit_mm:18.2f} | {cum_profit_dsac:18.2f}")
    diff_profit = cum_profit_dsac - cum_profit_mm
    print(f"{'Diferença Absoluta (€)':<35} | {'---':<18} | {diff_profit:+18.2f}")
    pct_gain = ((cum_profit_dsac - cum_profit_mm) / abs(cum_profit_mm) * 100.0) if cum_profit_mm != 0 else 0.0
    print(f"{'Variação Percentual (%)':<35} | {'---':<18} | {pct_gain:+17.1f}%")
    print(f"{'Nível de Serviço (Fill Rate)':<35} | {service_mm:17.1f}% | {service_dsac:17.1f}%")
    print(f"{'Vendas Perdidas (Caixas)':<35} | {df_mm['vendas_perdidas'].sum():18.0f} | {df_dsac['vendas_perdidas'].sum():18.0f}")
    print(f"{'Desperdício / Spoilage (Caixas)':<35} | {df_mm['desperdicio'].sum():18.0f} | {df_dsac['desperdicio'].sum():18.0f}")
    print(f"{'Custo de Transporte (€)':<35} | {df_mm['custo_transporte'].sum():18.2f} | {df_dsac['custo_transporte'].sum():18.2f}")
    print(f"{'Custo de Armazenagem (€)':<35} | {df_mm['custo_armazem'].sum():18.2f} | {df_dsac['custo_armazem'].sum():18.2f}")
    print("=" * 80)

    out_dir_name = f"Resultados_DSAC_Deslimitado_{sku}" if is_unconstrained else f"Resultados_DSAC_{sku}"
    out_dir = os.path.join(SCRIPT_DIR, out_dir_name)
    os.makedirs(out_dir, exist_ok=True)

    suffix = "_ComRuido" if with_noise else ""
    excel_out = os.path.join(out_dir, f"Comparativo_DSAC_vs_MinMax{suffix}.xlsx")
    with pd.ExcelWriter(excel_out, engine="openpyxl") as writer:
        df_dsac.to_excel(writer, sheet_name="DSAC", index=False)
        df_mm.to_excel(writer, sheet_name="MinMax", index=False)

    fig, axs = plt.subplots(3, 1, figsize=(14, 12), sharex=True)

    axs[0].plot(df_dsac['dia'], df_dsac['lucro_acumulado'], label=f"Agente DSAC ({'Ruído ON' if with_noise else 'Determinístico'})", color="#9467bd", linewidth=2.0)
    axs[0].plot(df_mm['dia'], df_mm['lucro_acumulado'], label=f"Min-Max ({s_min}, {S_max})", color="#ff7f0e", linestyle="--", linewidth=2.0)
    axs[0].set_title(f"Comparativo de Lucro Acumulado ({sku}) - DSAC vs Min-Max [{mode_str}] - [{constraint_str}]", fontsize=13, fontweight="bold")
    axs[0].set_ylabel("Lucro Acumulado (€)")
    axs[0].legend(loc="upper left")
    axs[0].grid(True, alpha=0.3)

    axs[1].plot(df_dsac['dia'], df_dsac['stock_final'], label="Stock DSAC", color="#9467bd", alpha=0.8)
    axs[1].plot(df_mm['dia'], df_mm['stock_final'], label="Stock Min-Max", color="#ff7f0e", linestyle=":", alpha=0.8)
    axs[1].set_title("Níveis de Stock no Armazém")
    axs[1].set_ylabel("Caixas em Stock")
    axs[1].legend(loc="upper left")
    axs[1].grid(True, alpha=0.3)

    axs[2].bar(df_dsac['dia'] - 0.2, df_dsac['encomenda'], width=0.4, label="Encomenda DSAC", color="#9467bd", alpha=0.7)
    axs[2].bar(df_mm['dia'] + 0.2, df_mm['encomenda'], width=0.4, label="Encomenda Min-Max", color="#d62728", alpha=0.5)
    axs[2].set_title("Decisões Diárias de Encomenda")
    axs[2].set_xlabel("Dia do Período de Teste")
    axs[2].set_ylabel("Quantidade Encomendada")
    axs[2].legend(loc="upper left")
    axs[2].grid(True, alpha=0.3)

    plt.tight_layout()
    plot_out = os.path.join(out_dir, f"Grafico_Comparativo_DSAC_vs_MinMax{suffix}.png")
    plt.savefig(plot_out, dpi=150)
    plt.close()

    logger.success(f"Resultados detalhados guardados em: {excel_out}")
    logger.success(f"Gráfico comparativo guardado em: {plot_out}")

if __name__ == "__main__":
    sku_param = "3_080"
    with_noise = False
    is_unconstrained = False
    for arg in sys.argv[1:]:
        if arg.lower() in ["--ruido", "--noise", "--stochastic", "-n"]:
            with_noise = True
        elif arg.lower() in ["--unconstrained", "--deslimitado", "--sem-limite", "-u"]:
            is_unconstrained = True
        elif not arg.startswith("-"):
            sku_param = arg
    evaluate_dsac_vs_baselines(sku_param, with_noise=with_noise, is_unconstrained=is_unconstrained)

