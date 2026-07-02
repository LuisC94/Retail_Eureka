import os
import sys
import torch
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import argparse

# Add parent directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)
sys.path.append(current_dir)

from environment_pricing import PricingStockEnvironment
from agent.ppo_agent import ParallelPPOAgent

# Config
DATASETS = {
    "3_080": os.path.join(current_dir, "datasets", "m5_foods_3_080.xlsx"),
    "911753": os.path.join(current_dir, "datasets", "911753_151dias_com_real.xlsx"),
    "3_252": os.path.join(current_dir, "datasets", "m5_foods_3_252.xlsx"),
    "3_090": os.path.join(current_dir, "datasets", "m5_foods_3_090.xlsx"),
    "3_586": os.path.join(current_dir, "datasets", "m5_foods_3_586.xlsx")
}
MODEL_DIR = os.path.join(current_dir, "models")
MAX_CAPACITY = 500
UPDATE_INTERVAL_DAYS = 15

# Fine-Tuning parameters
ONLINE_LR_ACTOR = 1e-5
ONLINE_LR_CRITIC = 5e-5
ONLINE_BATCH_SIZE = 32

def run_fine_tuning(agent, new_experiences, env_train):
    """ Executes PPO training step using 80% generated training data / 20% online logs """
    # Set fine-tuning learning rates
    for param_group in agent.optimizer_actor.param_groups:
        param_group['lr'] = ONLINE_LR_ACTOR
    for param_group in agent.optimizer_critic.param_groups:
        param_group['lr'] = ONLINE_LR_CRITIC
        
    num_new = len(new_experiences)
    num_old = num_new * 4
    
    # 1. Generate offline simulation experiences
    state = env_train.reset()
    dias_gerados = 0
    agent.policy_old_actor.eval()
    
    while dias_gerados < num_old:
        state_tensor = torch.FloatTensor(state).unsqueeze(0).to(agent.device)
        with torch.no_grad():
            action_mean_percent, log_std = agent.policy_old_actor(state_tensor)
            std_tensor = torch.exp(torch.clamp(log_std, min=-2.3, max=1.5))
            dist = torch.distributions.Normal(action_mean_percent, std_tensor)
            action_percent = dist.sample()
            action_logprob = dist.log_prob(action_percent).sum(dim=-1, keepdim=True)
            
            price_mult = 0.5 + 1.0 * torch.clamp(action_percent[:, 0], 0.0, 1.0).item()
            qty_pct = torch.clamp(action_percent[:, 1], 0.0, 1.0).item()
            
        next_state, reward, done, _ = env_train.step([price_mult, qty_pct])
        
        agent.buffer.states.append(state_tensor)
        agent.buffer.actions.append(action_percent)
        agent.buffer.logprobs.append(action_logprob)
        agent.buffer.rewards.append([reward])
        agent.buffer.is_terminals.append([done])
        
        state = next_state
        dias_gerados += 1
        if done:
            state = env_train.reset()
            
    # 2. Inject logged online experiences
    for exp in new_experiences:
        agent.buffer.states.append(torch.FloatTensor(exp['state']).unsqueeze(0).to(agent.device))
        agent.buffer.actions.append(torch.FloatTensor(exp['action']).unsqueeze(0).to(agent.device))
        agent.buffer.logprobs.append(torch.FloatTensor(exp['logprob']).unsqueeze(0).to(agent.device))
        agent.buffer.rewards.append([exp['reward']])
        agent.buffer.is_terminals.append([exp['is_terminal']])
        
    # 3. Update agent weights
    agent.update()

def run_oracle_lookahead(env_oracle):
    """
    Looks ahead 1 step and selects optimal price multiplier and shelf exposure
    using a brute-force checkpoint search grid.
    """
    ckpt = env_oracle.get_checkpoint()
    
    # 2D search grid
    p_grid = np.linspace(0.5, 1.5, 11)
    q_grid = np.linspace(0.1, 1.0, 5)
    
    best_profit = -float('inf')
    best_action = [1.0, 1.0]
    
    for p in p_grid:
        for q in q_grid:
            env_oracle.load_checkpoint(ckpt)
            _, _, _, info = env_oracle.step([p, q])
            if info['profit'] > best_profit:
                best_profit = info['profit']
                best_action = [p, q]
                
    # Restore final
    env_oracle.load_checkpoint(ckpt)
    return best_action

def run_orchestrated_evaluation(sku_name="3_080", generate_plots=True):
    print("======================================================")
    print(f" ORQUESTRADOR DE VALIDAÇÃO: SKU {sku_name} ")
    print("======================================================")
    
    dataset_path = DATASETS.get(sku_name)
    if not dataset_path or not os.path.exists(dataset_path):
        print(f"[ERRO] Dataset não encontrado para {sku_name}: {dataset_path}")
        return
        
    # Initialize Environments (test split)
    env_agent = PricingStockEnvironment(excel_path=dataset_path, is_training=False, train_split=0.6, max_capacity=MAX_CAPACITY)
    env_baseline = PricingStockEnvironment(excel_path=dataset_path, is_training=False, train_split=0.6, max_capacity=MAX_CAPACITY)
    env_oracle = PricingStockEnvironment(excel_path=dataset_path, is_training=False, train_split=0.6, max_capacity=MAX_CAPACITY)
    
    # Training Environment for fine-tuning memory replay
    env_train = PricingStockEnvironment(excel_path=dataset_path, is_training=True, train_split=0.6, max_capacity=MAX_CAPACITY)
    
    state_dim = 17
    action_dim = 2
    
    agent = ParallelPPOAgent(state_dim=state_dim, action_dim=action_dim, batch_size=ONLINE_BATCH_SIZE)
    agent.device = torch.device('cpu')
    
    # Load Offline Trained weights (supporting subdirectories, seeds and best dynamically)
    loaded = False
    import glob
    for base_name in [sku_name, "3_080"]:
        sku_folder = os.path.join(MODEL_DIR, base_name)
        search_paths = []
        if os.path.isdir(sku_folder):
            search_paths.append(sku_folder)
        search_paths.append(MODEL_DIR)
        
        for s_path in search_paths:
            actor_files = glob.glob(os.path.join(s_path, "*_actor.pth"))
            if not actor_files:
                actor_files = glob.glob(os.path.join(s_path, "**", "*_actor.pth"), recursive=True)
                
            if actor_files:
                matching_files = [f for f in actor_files if base_name in os.path.basename(f)]
                if not matching_files:
                    matching_files = actor_files
                
                # Sort to prefer models with highest episodes and seed42
                matching_files.sort(key=lambda f: ('ep20032' in f, 'seed42' in f, os.path.getmtime(f)), reverse=True)
                
                for best_file in matching_files:
                    checkpoint_path = best_file.replace('_actor.pth', '')
                    try:
                        agent.load(checkpoint_path)
                        agent.policy_old_actor.to('cpu')
                        agent.policy_old_actor.eval()
                        print(f"[OK] Modelo carregado com sucesso de: {checkpoint_path}")
                        loaded = True
                        break
                    except Exception:
                        pass
                if loaded:
                    break
        if loaded:
            break
                
    if not loaded:
        print("[AVISO] Não foi possível carregar nenhuns pesos. O agente operará com pesos iniciais aleatórios.")

    # Simulation lists
    days = []
    profits_agent = []
    profits_baseline = []
    profits_oracle = []
    
    cum_agent = 0
    cum_base = 0
    cum_oracle = 0
    
    prices_agent = []
    expositions_agent = []
    stocks_agent = []
    
    logged_experiences = []
    
    state = env_agent.reset()
    env_baseline.reset()
    env_oracle.reset()
    
    done = False
    dias_passados = 0
    
    while not done:
        day_idx = env_agent.current_step
        days.append(day_idx)
        
        # 1. PPO Agent Action
        state_tensor = torch.FloatTensor(state).unsqueeze(0)
        with torch.no_grad():
            action_mean_percent, log_std = agent.policy_old_actor(state_tensor)
            std_tensor = torch.exp(torch.clamp(log_std, min=-2.3, max=1.5))
            dist = torch.distributions.Normal(action_mean_percent, std_tensor)
            action_percent = dist.sample()
            action_logprob = dist.log_prob(action_percent).sum(dim=-1, keepdim=True)
            
            price_mult = 0.5 + 1.0 * torch.clamp(action_percent[:, 0], 0.0, 1.0).item()
            qty_pct = torch.clamp(action_percent[:, 1], 0.0, 1.0).item()
            
        action_agent = [price_mult, qty_pct]
        next_state, reward, done, info = env_agent.step(action_agent)
        
        # Log experiences for online retraining
        logged_experiences.append({
            'state': state,
            'action': action_percent.numpy()[0],
            'logprob': action_logprob.numpy()[0],
            'reward': reward,
            'is_terminal': done
        })
        
        # 2. Static Baseline Action [1.0, 1.0]
        _, _, _, info_base = env_baseline.step([1.0, 1.0])
        
        # 3. Oracle Lookahead Action
        action_oracle = run_oracle_lookahead(env_oracle)
        _, _, _, info_oracle = env_oracle.step(action_oracle)
        
        cum_agent += info['profit']
        cum_base += info_base['profit']
        cum_oracle += info_oracle['profit']
        
        profits_agent.append(cum_agent)
        profits_baseline.append(cum_base)
        profits_oracle.append(cum_oracle)
        
        prices_agent.append(price_mult)
        expositions_agent.append(qty_pct)
        stocks_agent.append(info['final_stock'])
        
        state = next_state
        dias_passados += 1
        
        # Periodic Online Retraining (mixed buffer) every 15 days
        if dias_passados % UPDATE_INTERVAL_DAYS == 0 and len(logged_experiences) >= 15:
            run_fine_tuning(agent, logged_experiences, env_train)
            logged_experiences = []
            print(f"-> Dia {day_idx:03d}: Retreino online PPO concluído.")

    print("\n=== RESULTADOS FINAIS DE VALIDAÇÃO ===")
    print(f"Total Lucro Agente RL (com retreino): {cum_agent:.2f}€")
    print(f"Total Lucro Baseline Estática: {cum_base:.2f}€")
    print(f"Total Lucro Oráculo Perfeito: {cum_oracle:.2f}€")
    print(f"Melhoria do Agente vs Baseline: {cum_agent - cum_base:.2f}€ ({((cum_agent - cum_base)/max(1.0, abs(cum_base)))*100:.2f}%)")
    
    if generate_plots:
        plt.figure(figsize=(15, 10))
        
        # Plot 1: Cumulative Profits
        plt.subplot(2, 1, 1)
        plt.plot(days, profits_agent, label=f'PPO Agent ({cum_agent:.0f}€)', color='#1f77b4', linewidth=2.5)
        plt.plot(days, profits_baseline, label=f'Static Baseline ({cum_base:.0f}€)', color='#7f7f7f', linestyle='--')
        plt.plot(days, profits_oracle, label=f'Perfect Oracle ({cum_oracle:.0f}€)', color='#2ca02c', linestyle='-.')
        plt.title(f"Lucro Acumulado SKU {sku_name}: Agente vs Baselines", fontsize=12, fontweight='bold')
        plt.ylabel("Lucro Acumulado (€)")
        plt.grid(True, alpha=0.3)
        plt.legend()
        
        # Plot 2: Price and Stock actions
        plt.subplot(2, 1, 2)
        ax1 = plt.gca()
        ax2 = ax1.twinx()
        
        ax1.plot(days, prices_agent, label='Multiplicador Preço (Agente)', color='#ff7f0e', alpha=0.7)
        ax1.axhline(y=1.0, color='red', linestyle=':', label='Preço Mercado (1.0)', alpha=0.5)
        ax1.set_ylabel('Multiplicador de Preço', color='#ff7f0e')
        ax1.tick_params(axis='y', labelcolor='#ff7f0e')
        ax1.set_ylim(0.4, 1.6)
        
        ax2.plot(days, stocks_agent, label='Nível Stock Armazém', color='#2ca02c', alpha=0.4, linestyle='--')
        ax2.set_ylabel('Stock em Armazém (kg)', color='#2ca02c')
        ax2.tick_params(axis='y', labelcolor='#2ca02c')
        
        plt.title("Preços e Níveis de Stock do Agente PPO ao longo da simulação", fontsize=12, fontweight='bold')
        ax1.set_xlabel("Dia de Simulação")
        plt.grid(True, alpha=0.3)
        
        # Combine legends
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
        
        plt.tight_layout()
        chart_path = os.path.join(current_dir, "pricing_simulation_results.png")
        plt.savefig(chart_path, dpi=300)
        plt.close()
        print(f"[OK] Gráfico comparativo gerado em: {chart_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sku", type=str, default="3_080", choices=["3_080", "911753", "3_252", "3_090", "3_586"])
    args = parser.parse_args()
    
    run_orchestrated_evaluation(args.sku)
