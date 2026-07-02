import os
import sys
import torch
import numpy as np
import random
import pandas as pd
import multiprocessing as mp

# Add parent directory to path to ensure relative imports work correctly
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)
sys.path.append(current_dir)

from environment_pricing import PricingStockEnvironment
from agent.ppo_agent import ParallelPPOAgent

# =====================================================================
# --- CONFIGURAÇÃO MANUAL DO DATASET (Altere o caminho para cada treino) ---
# =====================================================================
EXCEL_PATH = os.path.join(current_dir, "datasets", "911753_151dias_com_real.xlsx")

# --- PARÂMETROS DE TREINO (Igualados a 0_training_constrained.py) ---
NUM_ENVS = 64               
NUM_WORKERS = 4              # Usar 4 cores reais
ENVS_PER_WORKER = NUM_ENVS // NUM_WORKERS

MAX_EPISODES_TOTAL = 20000    
HORIZON = 90                 # Passos por ronda
MAX_CAPACITY = 500            

LR_ACTOR = 0.0003
LR_CRITIC = 0.001
GAMMA = 0.8
K_EPOCHS = 30                
EPS_CLIP = 0.2               
BATCH_SIZE = 2048

SAVE_MODEL_FREQ = 1

def pricing_ppo_worker(worker_id, excel_path, num_envs, capacity, weights_queue, results_queue):
    """ Worker managing a batch of pricing environments in parallel """
    # Create sub-environments
    envs = [PricingStockEnvironment(excel_path=excel_path, is_training=True, train_split=0.6, 
                                   max_capacity=capacity) for _ in range(num_envs)]
    
    agent = ParallelPPOAgent(state_dim=17, action_dim=2)
    agent.device = torch.device('cpu') 
    agent.policy_old_actor.to('cpu')
    agent.policy_old_critic.to('cpu')
    
    states = [env.reset() for env in envs]
    states_matrix = np.array(states)
    
    while True:
        weights = weights_queue.get()
        if weights is None: 
            break
        
        agent.policy_old_actor.load_state_dict(weights['actor'])
        worker_memory = {
            'states': [], 'actions': [], 'logprobs': [], 'rewards': [], 'dones': [], 'profits': []
        }
        
        for step in range(HORIZON):
            with torch.no_grad():
                st_t = torch.FloatTensor(states_matrix).to('cpu')
                action_mean, log_std = agent.policy_old_actor(st_t)
                dist = torch.distributions.Normal(action_mean, torch.exp(torch.clamp(log_std, -2.3, 1.5)))
                action_percent = dist.sample()
                action_logprob = dist.log_prob(action_percent).sum(dim=-1, keepdim=True)
                
                # Physical actions mapping
                # Action 0 (Price): sigmoid maps to [0,1] -> scaled [0.5, 1.5]
                price_mult = 0.5 + 1.0 * torch.clamp(action_percent[:, 0:1], 0.0, 1.0)
                # Action 1 (Expose Qty %): clamp [0,1]
                qty_pct = torch.clamp(action_percent[:, 1:2], 0.0, 1.0)
                
                physical_actions = torch.cat([price_mult, qty_pct], dim=-1).numpy()

            worker_memory['states'].append(st_t)
            worker_memory['actions'].append(action_percent)
            worker_memory['logprobs'].append(action_logprob)
            
            next_states_list = []
            rewards_list = []
            dones_list = []
            profits_list = []
            
            for i in range(num_envs):
                ns, r, d, info = envs[i].step(physical_actions[i])
                if d:
                    ns = envs[i].reset()
                next_states_list.append(ns)
                rewards_list.append(r)
                dones_list.append(d)
                profits_list.append(info['profit'])
            
            worker_memory['rewards'].append(rewards_list)
            worker_memory['dones'].append(dones_list)
            worker_memory['profits'].append(profits_list)
            
            states_matrix = np.array(next_states_list)
            
        with torch.no_grad():
            st_final = torch.FloatTensor(states_matrix).to('cpu')
            worker_memory['states'].append(st_final)
        
        results_queue.put({
            'worker_id': worker_id,
            'memory': worker_memory,
            'total_profit': np.sum(worker_memory['profits'])
        })

def train_sku_seed(sku_name, dataset_path, seed, save_dir="models"):
    # Enforce exact reproducibility seeds
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    
    print(f"\n=======================================================")
    print(f" TREINO SKU: {sku_name} | SEED: {seed} | EPISODIOS ALVO: {MAX_EPISODES_TOTAL}")
    print(f" Dataset: {dataset_path}")
    print(f"=======================================================")
    
    # Init agent
    agent = ParallelPPOAgent(
        state_dim=17,
        action_dim=2,
        lr_actor=LR_ACTOR,
        lr_critic=LR_CRITIC,
        gamma=GAMMA,
        K_epochs=K_EPOCHS,
        eps_clip=EPS_CLIP,
        batch_size=BATCH_SIZE
    )
    
    checkpoint_dir = os.path.join(current_dir, save_dir)
    os.makedirs(checkpoint_dir, exist_ok=True)
    checkpoint_path = os.path.join(checkpoint_dir, f"{sku_name}_seed{seed}")
    
    # Establish multiprocessing queues
    weights_queues = [mp.Queue() for _ in range(NUM_WORKERS)]
    results_queue = mp.Queue()
    
    processes = []
    for i in range(NUM_WORKERS):
        p = mp.Process(
            target=pricing_ppo_worker, 
            args=(i, dataset_path, ENVS_PER_WORKER, MAX_CAPACITY, weights_queues[i], results_queue)
        )
        p.start()
        processes.append(p)
        
    episodes_played = 0
    iteration = 0
    
    try:
        while episodes_played < MAX_EPISODES_TOTAL:
            iteration += 1
            current_weights = {
                'actor': {k: v.cpu() for k, v in agent.policy_old_actor.state_dict().items()}
            }
            for q in weights_queues:
                q.put(current_weights)
            
            all_worker_data = []
            for _ in range(NUM_WORKERS):
                all_worker_data.append(results_queue.get())
            
            T = len(all_worker_data[0]['memory']['rewards'])
            
            for t in range(T):
                step_states = torch.cat([res['memory']['states'][t] for res in all_worker_data], dim=0).to(agent.device)
                step_actions = torch.cat([res['memory']['actions'][t] for res in all_worker_data], dim=0).to(agent.device)
                step_logprobs = torch.cat([res['memory']['logprobs'][t] for res in all_worker_data], dim=0).to(agent.device)
                step_rewards = []
                step_dones = []
                for res in all_worker_data:
                    step_rewards.extend(res['memory']['rewards'][t])
                    step_dones.extend(res['memory']['dones'][t])
                
                agent.buffer.states.append(step_states)
                agent.buffer.actions.append(step_actions)
                agent.buffer.logprobs.append(step_logprobs)
                agent.buffer.rewards.append(step_rewards)
                agent.buffer.is_terminals.append(step_dones)
                
            if len(all_worker_data[0]['memory']['states']) > T:
                final_states = torch.cat([res['memory']['states'][T] for res in all_worker_data], dim=0).to(agent.device)
                agent.buffer.states.append(final_states)
            
            loss_t, loss_a, loss_c = agent.update()
            episodes_played += NUM_ENVS
            
            # Imprime e salva os pesos a cada iteração (corresponde a cada 64 episódios)
            avg_profit = np.mean([res['total_profit'] / ENVS_PER_WORKER for res in all_worker_data])
            print(f"Episódios: {episodes_played}/{MAX_EPISODES_TOTAL} | Média Lucro Batch: {avg_profit:.2f}€ | Loss Total: {loss_t:.4f}")
            
            # Guardar checkpoint histórico individual (ex: 3_080_seed42_ep64)
            checkpoint_path_ep = f"{checkpoint_path}_ep{episodes_played}"
            agent.save(checkpoint_path_ep)
            
            # Atualizar também o modelo mais recente sob o nome padrão para o Django
            agent.save(checkpoint_path)
                
    except KeyboardInterrupt:
        print("[AVISO] Treino interrompido pelo utilizador.")
    finally:
        # Shutdown worker processes
        for q in weights_queues: 
            q.put(None)
        for p in processes: 
            p.join()
            
        agent.save(checkpoint_path)
        print(f"[OK] Modelo do SKU {sku_name} com seed {seed} salvo em: {checkpoint_path}")

def main():
    # Enforce spawn start method for safe PyTorch CUDA/CPU multiprocessing on Windows
    try:
        mp.set_start_method('spawn', force=True)
    except RuntimeError:
        pass

    if not os.path.exists(EXCEL_PATH):
        print(f"[ERRO] Dataset não encontrado no caminho configurado: {EXCEL_PATH}")
        sys.exit(1)
        
    # Extrair dinamicamente a chave SKU do nome do ficheiro
    excel_name = os.path.basename(EXCEL_PATH).lower()
    if "3_080" in excel_name:
        sku_name = "3_080"
    elif "911753" in excel_name:
        sku_name = "911753"
    elif "3_252" in excel_name:
        sku_name = "3_252"
    elif "3_090" in excel_name:
        sku_name = "3_090"
    elif "3_586" in excel_name or "2_586" in excel_name:
        sku_name = "3_586"
    else:
        sku_name = "custom_sku"
        
    seeds = [42, 1337]
    for seed in seeds:
        train_sku_seed(sku_name, EXCEL_PATH, seed)

if __name__ == "__main__":
    main()
