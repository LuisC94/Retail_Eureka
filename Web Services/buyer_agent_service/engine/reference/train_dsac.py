import os
import sys
import torch
import numpy as np
import random
import pandas as pd
import matplotlib.pyplot as plt
from loguru import logger

# Configurar caminhos do projeto
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
for path in [ROOT_DIR, os.path.join(ROOT_DIR, "Train_Interface"), SCRIPT_DIR]:
    if os.path.exists(path) and path not in sys.path:
        sys.path.insert(0, path)

from environment_constrained import StockEnvironment
from replay_buffer import ReplayBuffer
from dsac_agent import DSACAgent

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

def set_seed(seed=1337):
    torch.manual_seed(seed)
    np.random.seed(seed)
    random.seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

def evaluate_policy(agent, eval_env):
    """ Avaliação determinística no conjunto de teste """
    state = eval_env.reset()
    done = False
    total_profit = 0.0
    total_sales = 0.0
    total_lost = 0.0
    total_waste = 0.0

    while not done:
        action_norm = agent.select_action(state, evaluate=True)
        action_pct = 0.5 * (float(action_norm[0]) + 1.0)
        action_physical = round(action_pct * eval_env.max_order_limit)

        next_state, reward, done, info = eval_env.step(action_physical, update_stats=False)
        total_profit += info['profit']
        total_sales += info['sales']
        total_lost += info['missed_sales']
        total_waste += info['overflow_waste']
        state = next_state

    return {
        "profit": total_profit,
        "sales": total_sales,
        "missed_sales": total_lost,
        "waste": total_waste
    }

def train():
    raw_sku = "3_080"
    is_unconstrained = False
    device_override = None

    for arg in sys.argv[1:]:
        if arg.lower() in ["--unconstrained", "--deslimitado", "--sem-limite", "-u"]:
            is_unconstrained = True
        elif arg.lower() in ["--gpu", "--cuda"]:
            device_override = "cuda"
        elif arg.lower() in ["--cpu"]:
            device_override = "cpu"
        elif not arg.startswith("-"):
            raw_sku = arg
    target_sku = normalize_sku(raw_sku)
    excel_path = find_dataset(target_sku)
    
    # Parâmetro de Aversão ao Risco (0.85 = Foco nos 85% piores cenários para evitar desperdício de perecíveis)
    risk_factor = float(os.getenv("DSAC_RISK_FACTOR", "0.85"))

    mode_desc = "DESLIMITADO (Sem teto de compra máxima, até 500 un)" if is_unconstrained else "LIMITADO (Max compra = Maior venda histórica)"
    logger.info(f"=== INICIANDO TREINO DSAC (DISTRIBUTIONAL) PARA O SKU: {target_sku} ===")
    logger.info(f"Ficheiro de dados: {excel_path}")
    logger.info(f"Modo de Treino: {mode_desc}")
    logger.info(f"Fator de Risco Quântico (CVaR): {risk_factor:.2f}")

    set_seed(1337)

    # Seleção de Dispositivo (CPU ou GPU)
    if device_override in ["gpu", "cuda"]:
        if torch.cuda.is_available():
            device = "cuda"
            logger.info(f"Dispositivo forçado via --gpu: GPU ({torch.cuda.get_device_name(0)})")
        else:
            logger.warning("Opção --gpu foi passada, mas CUDA não está ativo neste ambiente PyTorch. A reverter para CPU.")
            device = "cpu"
    elif device_override == "cpu":
        device = "cpu"
        logger.info("Dispositivo forçado via --cpu: CPU")
    else:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        dev_name = torch.cuda.get_device_name(0) if device == "cuda" else "CPU"
        logger.info(f"Dispositivo detetado automaticamente: {device.upper()} ({dev_name})")

    # Ambientes (Com parâmetros de waste shaping universais nativos do environment para todos os modelos)
    env_train = StockEnvironment(excel_path, is_training=True, train_split=0.6, max_capacity=500, completely_unconstrained=is_unconstrained)
    env_eval = StockEnvironment(excel_path, is_training=False, train_split=0.6, max_capacity=500, shared_stats={'econ': env_train.stat_profit}, completely_unconstrained=is_unconstrained)

    state_dim = 30
    action_dim = 1
    max_order_limit = env_train.max_order_limit

    # Hiperparâmetros
    BATCH_SIZE = 256
    WARMUP_STEPS = 500
    MAX_EPISODES = 350
    EVAL_INTERVAL = 10
    BUFFER_SIZE = 300_000
    NUM_QUANTILES = 32

    agent = DSACAgent(
        state_dim=state_dim,
        action_dim=action_dim,
        gamma=0.99,
        tau=0.005,
        lr_actor=3e-4,
        lr_critic=3e-4,
        lr_alpha=3e-4,
        num_quantiles=NUM_QUANTILES,
        risk_factor=risk_factor,
        device=device
    )

    replay_buffer = ReplayBuffer(state_dim=state_dim, action_dim=action_dim, max_size=BUFFER_SIZE, device=device)

    dir_name = f"modelos_dsac_deslimitado_{target_sku}" if is_unconstrained else f"modelos_dsac_{target_sku}"
    save_dir = os.path.join(SCRIPT_DIR, dir_name)
    os.makedirs(save_dir, exist_ok=True)

    train_profits = []
    eval_profits = []
    critic_losses = []
    actor_losses = []
    alpha_history = []

    best_eval_profit = -float("inf")
    total_steps = 0

    for episode in range(1, MAX_EPISODES + 1):
        state = env_train.reset()
        done = False
        episode_profit = 0.0
        ep_critic_loss = []
        ep_actor_loss = []

        while not done:
            total_steps += 1

            if total_steps < WARMUP_STEPS:
                action_norm = np.random.uniform(-1.0, 1.0, size=(action_dim,)).astype(np.float32)
            else:
                action_norm = agent.select_action(state, evaluate=False)

            action_pct = 0.5 * (float(action_norm[0]) + 1.0)
            physical_action = round(action_pct * max_order_limit)

            next_state, _, done, info = env_train.step(physical_action)
            episode_profit += info.get('commercial_profit', info['profit'])

            # Recompensa calculada nativamente pelo Environment (já inclui penalizações de waste shaping)
            reward_stationary = float(np.clip(info['profit'] / 100.0, -10.0, 10.0))

            replay_buffer.push(state, action_norm, reward_stationary, next_state, done)
            state = next_state

            if total_steps >= WARMUP_STEPS:
                metrics = agent.update(replay_buffer, batch_size=BATCH_SIZE)
                if metrics:
                    ep_critic_loss.append(metrics["loss_critic"])
                    ep_actor_loss.append(metrics["loss_actor"])
                    alpha_history.append(metrics["alpha"])

        train_profits.append(episode_profit)
        avg_c_loss = np.mean(ep_critic_loss) if ep_critic_loss else 0.0
        avg_a_loss = np.mean(ep_actor_loss) if ep_actor_loss else 0.0
        critic_losses.append(avg_c_loss)
        actor_losses.append(avg_a_loss)

        if episode % 5 == 0 or episode == 1:
            current_alpha = float(agent.alpha.item())
            logger.info(
                f"Episódio {episode:3d}/{MAX_EPISODES} | "
                f"Passos Totais: {total_steps:5d} | "
                f"Lucro Treino: {episode_profit:9.2f} € | "
                f"Quantile Critic Loss: {avg_c_loss:7.4f} | "
                f"Actor Loss: {avg_a_loss:7.4f} | "
                f"Alpha (Temp): {current_alpha:6.4f}"
            )

        if episode % EVAL_INTERVAL == 0:
            eval_metrics = evaluate_policy(agent, env_eval)
            eval_profit = eval_metrics["profit"]
            eval_profits.append((episode, eval_profit))

            logger.info(
                f">>> [EVALUAÇÃO DSAC EP {episode}] Lucro Teste: {eval_profit:.2f} € | "
                f"Vendas: {eval_metrics['sales']:.0f} | "
                f"Rutura: {eval_metrics['missed_sales']:.0f} | "
                f"Desperdício: {eval_metrics['waste']:.0f}"
            )

            if eval_profit > best_eval_profit:
                best_eval_profit = eval_profit
                agent.save(save_dir, filename_prefix="dsac_best")
                logger.success(f"★ Novo recorde DSAC guardado: {eval_profit:.2f} €")

            agent.save(save_dir, filename_prefix="dsac_latest")

    # Gráfico Final
    fig, axs = plt.subplots(2, 2, figsize=(14, 10))

    axs[0, 0].plot(train_profits, label="Lucro Treino (Episódio)", color="#1f77b4")
    axs[0, 0].set_title("Evolução do Lucro no Treino (DSAC)")
    axs[0, 0].set_xlabel("Episódio")
    axs[0, 0].set_ylabel("Lucro (€)")
    axs[0, 0].grid(True, alpha=0.3)

    if eval_profits:
        eval_x, eval_y = zip(*eval_profits)
        axs[0, 1].plot(eval_x, eval_y, marker="o", color="#2ca02c", label="Lucro Teste")
        axs[0, 1].set_title(f"Evolução no Teste DSAC (Recorde: {best_eval_profit:.2f} €)")
        axs[0, 1].set_xlabel("Episódio")
        axs[0, 1].set_ylabel("Lucro Teste (€)")
        axs[0, 1].grid(True, alpha=0.3)

    axs[1, 0].plot(critic_losses, label="Quantile Huber Loss", color="#d62728")
    axs[1, 0].set_title("Evolução da Perda do Crítico Quântico (Z1 + Z2)")
    axs[1, 0].set_xlabel("Episódio")
    axs[1, 0].set_ylabel("Quantile Loss")
    axs[1, 0].grid(True, alpha=0.3)

    axs[1, 1].plot(alpha_history, label="Temperatura Alpha (Entropia)", color="#9467bd")
    axs[1, 1].set_title("Ajuste Dinâmico da Entropia (Alpha)")
    axs[1, 1].set_xlabel("Passos de Gradiente")
    axs[1, 1].set_ylabel("Alpha")
    axs[1, 1].grid(True, alpha=0.3)

    plt.tight_layout()
    plot_path = os.path.join(save_dir, "dsac_training_curves.png")
    plt.savefig(plot_path, dpi=150)
    plt.close()

    logger.success(f"Treino DSAC concluído com sucesso!")
    logger.success(f"Modelos e gráficos guardados em: {save_dir}")

if __name__ == "__main__":
    train()

