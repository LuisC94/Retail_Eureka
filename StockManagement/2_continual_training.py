import os
import sys
import torch
import pickle
import numpy as np

# Add parent directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)
sys.path.append(current_dir)

from agent.ppo_agent import ParallelPPOAgent
from environment_pricing import PricingStockEnvironment

# Config
MODEL_DIR = os.path.join(current_dir, "models")
MEMORY_DIR = os.path.join(current_dir, "memoria")
MAX_CAPACITY = 500

# Low learning rates for fine-tuning to prevent policy disruption
ONLINE_LR_ACTOR = 1e-5
ONLINE_LR_CRITIC = 5e-5
ONLINE_BATCH_SIZE = 32
MIN_EXPERIENCES_TO_TRAIN = 15

def get_latest_model(sku_name):
    # Returns the path of the SKU specific model or fallbacks (supporting subdirectories, seeds and best dynamically)
    os.makedirs(MODEL_DIR, exist_ok=True)
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
                return matching_files[0].replace('_actor.pth', '')
                
    return os.path.join(MODEL_DIR, "3_080")

def get_next_version_name(sku_name):
    os.makedirs(MODEL_DIR, exist_ok=True)
    # Check current version models to find the next version increment
    files = [f for f in os.listdir(MODEL_DIR) if f.startswith(f"{sku_name}_v") and f.endswith('_actor.pth')]
    if not files:
        return os.path.join(MODEL_DIR, f"{sku_name}_v1")
    versions = []
    for f in files:
        try:
            v = int(f.split(f"{sku_name}_v")[1].split('_actor.pth')[0])
            versions.append(v)
        except:
            pass
    next_v = max(versions) + 1 if versions else 1
    return os.path.join(MODEL_DIR, f"{sku_name}_v{next_v}")

def run_continual_training(sku_name="3_080"):
    print("======================================================")
    print(f" INICIANDO RETREINO CONTINUO (STOCK AGENT: {sku_name}) ")
    print("======================================================")
    
    memory_path = os.path.join(MEMORY_DIR, f"buffer_real_{sku_name}.pkl")
    
    # 1. Check if logged real data is available
    if not os.path.exists(memory_path):
        print(f"[AVISO] O buffer de memória '{memory_path}' não existe. Sem novos dados.")
        return
        
    with open(memory_path, 'rb') as f:
        experiences = pickle.load(f)
        
    if len(experiences) < MIN_EXPERIENCES_TO_TRAIN:
        print(f"[AVISO] Apenas {len(experiences)} dias na memória. Requer pelo menos {MIN_EXPERIENCES_TO_TRAIN} dias.")
        return
        
    print(f"[OK] Encontrados {len(experiences)} dias de novos dados reais. Preparando Mixed Buffer...")
    
    # Dataset path for SKU
    excel_name = f"m5_foods_{sku_name}.xlsx"
    if sku_name == "911753":
        excel_name = "911753_151dias_com_real.xlsx"
        
    excel_path = os.path.join(current_dir, "datasets", excel_name)
    if not os.path.exists(excel_path):
        excel_path = os.path.join(current_dir, "datasets", "m5_foods_3_080.xlsx")
        
    env_train = PricingStockEnvironment(excel_path=excel_path, is_training=True, train_split=0.6, max_capacity=MAX_CAPACITY)
    
    state_dim = 17
    action_dim = 2
    
    agent = ParallelPPOAgent(state_dim=state_dim, action_dim=action_dim, batch_size=ONLINE_BATCH_SIZE)
    
    # Load model
    model_path = get_latest_model(sku_name)
    try:
        agent.load(model_path)
        print(f"[OK] Modelo base carregado de: {model_path}")
    except Exception as e:
        print(f"[ERRO] Falha ao carregar o modelo base: {e}")
        return
        
    # Lower learning rates for online fine-tuning
    for param_group in agent.optimizer_actor.param_groups:
        param_group['lr'] = ONLINE_LR_ACTOR
    for param_group in agent.optimizer_critic.param_groups:
        param_group['lr'] = ONLINE_LR_CRITIC
        
    # Mixed Buffer strategy: 80% historical simulation data, 20% live logged data
    num_new_days = len(experiences)
    num_old_needed = num_new_days * 4
    print(f"[MIXED BUFFER] Injetando {num_new_days} novos dias e gerando {num_old_needed} dias do simulador...")
    
    state = env_train.reset()
    dias_gerados = 0
    
    agent.policy_old_actor.eval()
    while dias_gerados < num_old_needed:
        state_tensor = torch.FloatTensor(state).unsqueeze(0).to(agent.device)
        with torch.no_grad():
            action_mean_percent, log_std = agent.policy_old_actor(state_tensor)
            std_tensor = torch.exp(torch.clamp(log_std, min=-2.3, max=1.5))
            dist = torch.distributions.Normal(action_mean_percent, std_tensor)
            action_percent = dist.sample()
            action_logprob = dist.log_prob(action_percent).sum(dim=-1, keepdim=True)
            
            # Map action to environment domains
            price_mult = 0.5 + 1.0 * torch.clamp(action_percent[:, 0], 0.0, 1.0).item()
            qty_pct = torch.clamp(action_percent[:, 1], 0.0, 1.0).item()
            
        next_state, reward, done, _ = env_train.step([price_mult, qty_pct])
        
        # Save to buffer (Parallel PPO expectations)
        agent.buffer.states.append(state_tensor)
        agent.buffer.actions.append(action_percent)
        agent.buffer.logprobs.append(action_logprob)
        agent.buffer.rewards.append([reward])
        agent.buffer.is_terminals.append([done])
        
        state = next_state
        dias_gerados += 1
        if done:
            state = env_train.reset()
            
    print(f"[OK] {dias_gerados} dias gerados do simulador offline.")
    
    # Inject logged live data
    for exp in experiences:
        agent.buffer.states.append(torch.FloatTensor(exp['state']).unsqueeze(0).to(agent.device))
        agent.buffer.actions.append(torch.FloatTensor(exp['action']).unsqueeze(0).to(agent.device))
        agent.buffer.logprobs.append(torch.FloatTensor(exp['logprob']).unsqueeze(0).to(agent.device))
        agent.buffer.rewards.append([exp['reward']])
        agent.buffer.is_terminals.append([exp['is_terminal']])
        
    print(f"[OK] {num_new_days} dias reais adicionados ao buffer.")
    
    # Optimize weights
    agent.update()
    print("[OK] Otimização incremental concluída.")
    
    # Save incremental version
    next_version = get_next_version_name(sku_name)
    agent.save(next_version)
    # Also overwrite the active production weights
    active_path = os.path.join(MODEL_DIR, sku_name)
    agent.save(active_path)
    print(f"[OK] Modelo atualizado e salvo em: {next_version} e {active_path}")
    
    # Clear logs
    with open(memory_path, 'wb') as f:
        pickle.dump([], f)
    print(f"[LIMPEZA] Limpeza do buffer de log '{memory_path}' concluída.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--sku", type=str, default="3_080", choices=["3_080", "911753", "3_252", "3_090", "3_586"])
    args = parser.parse_args()
    
    run_continual_training(args.sku)
