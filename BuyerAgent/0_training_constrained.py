import os
import torch
import numpy as np
import random
import pandas as pd
import multiprocessing as mp
from environment_constrained import StockEnvironment, EnvRunningStat
from agent.ppo_agent import ParallelPPOAgent
from torch.utils.tensorboard import SummaryWriter
from loguru import logger

# --- HYPERPARAMETERS ---
EXCEL_PATH = r"Dados\m5_foods_3_080.xlsx"
NUM_ENVS = 64               
NUM_WORKERS = 4              # Usar 4 cores reais
ENVS_PER_WORKER = NUM_ENVS // NUM_WORKERS

MAX_EPISODES_TOTAL = 20000    
HORIZON = 90                 # Cenário B: Passos por ronda
MAX_CAPACITY = 500            

LR_ACTOR = 0.0003
LR_CRITIC = 0.001
GAMMA = 0.8
K_EPOCHS = 30                
EPS_CLIP = 0.2               
BATCH_SIZE = 2048

PRINT_FREQ_EPISODES = 1
SAVE_MODEL_FREQ = 1

def ppo_worker(worker_id, excel_path, num_envs, capacity, weights_queue, results_queue, shared_stats):
    """ Worker que gere um bloco de ambientes PPO de forma sincronizada com ações limitadas """
    # Criar sub-ambientes
    envs = [StockEnvironment(excel_path=excel_path, is_training=True, train_split=0.6, 
                             max_capacity=capacity, shared_stats=shared_stats) for _ in range(num_envs)]
    
    # O limite de ação é definido dinamicamente pelo ambiente
    max_order_limit = envs[0].max_order_limit
    
    agent = ParallelPPOAgent(state_dim=17, action_dim=1, max_action=max_order_limit)
    agent.device = torch.device('cpu') 
    agent.policy_old_actor.to('cpu')
    agent.policy_old_critic.to('cpu')
    
    states = [env.reset() for env in envs]
    states_matrix = np.array(states)
    
    while True:
        weights = weights_queue.get()
        if weights is None: break
        
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
                action_logprob = dist.log_prob(action_percent)
                # Escalar com base no limite máximo e não na capacidade total do armazém!
                physical_actions = torch.round(torch.clamp(action_percent * max_order_limit, 0, max_order_limit)).numpy().flatten()

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

def train_multi_core(seed: int):
    mp.set_start_method('spawn', force=True)
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    
    # Determinar dinamicamente o limite máximo de procura no treino
    df_temp = pd.read_excel(EXCEL_PATH)
    split_idx = int(len(df_temp) * 0.6)
    MAX_ORDER_LIMIT = float(df_temp.iloc[:split_idx]['real_value'].max())
    
    logger.info(f"Iniciando PPO CONSTRANGIDO | {NUM_ENVS} ambientes em {NUM_WORKERS} cores | Seed: {seed}")
    logger.info(f"Limite Máximo de Encomenda Diária (MAX_ORDER_LIMIT) = {MAX_ORDER_LIMIT} un (Capacidade Armazém = {MAX_CAPACITY} un)")
    
    shared_stats = {
        'econ': EnvRunningStat(), 'eco': EnvRunningStat(), 'risk': EnvRunningStat()
    }
    
    agent = ParallelPPOAgent(state_dim=17, action_dim=1, max_action=MAX_ORDER_LIMIT, 
                             lr_actor=LR_ACTOR, lr_critic=LR_CRITIC, gamma=GAMMA, K_epochs=K_EPOCHS, eps_clip=EPS_CLIP, batch_size=BATCH_SIZE)
    
    writer = SummaryWriter(log_dir=f"runs/ppo_constrained_seed_{seed}")
    save_dir = "modelos_producao_constrained"
    os.makedirs(save_dir, exist_ok=True)
    
    weights_queues = [mp.Queue() for _ in range(NUM_WORKERS)]
    results_queue = mp.Queue()
    
    processes = []
    for i in range(NUM_WORKERS):
        p = mp.Process(target=ppo_worker, args=(i, EXCEL_PATH, ENVS_PER_WORKER, MAX_CAPACITY, weights_queues[i], results_queue, shared_stats))
        p.start()
        processes.append(p)
        
    episodes_played = 0
    iteration = 0
    
    losses_total = []
    losses_actor = []
    losses_critic = []
    
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
            losses_total.append(loss_t)
            losses_actor.append(loss_a)
            losses_critic.append(loss_c)
            
            episodes_played += NUM_ENVS
            avg_profit = np.mean([res['total_profit'] / ENVS_PER_WORKER for res in all_worker_data])
            logger.info(f"Episodes: {episodes_played}/{MAX_EPISODES_TOTAL} | Batch Profit Avg: {avg_profit:.2f}€")
            writer.add_scalar("Profit/Avg_Batch", avg_profit, episodes_played)
            
            if iteration % SAVE_MODEL_FREQ == 0:
                checkpoint_path = os.path.join(save_dir, f"ppo_constrained_iter{iteration}")
                agent.save(checkpoint_path)
                
                econ_state = {
                    'n': shared_stats['econ'].n,
                    'mean': shared_stats['econ'].mean,
                    'S': shared_stats['econ'].S
                }
                torch.save(econ_state, checkpoint_path + '_econ_stat.pth')
                
    except KeyboardInterrupt:
        logger.warning("Treino interrompido.")
    finally:
        for q in weights_queues: q.put(None)
        for p in processes: p.join()
        
        final_path = os.path.join(save_dir, "ppo_constrained_final")
        agent.save(final_path)
        
        econ_state = {
            'n': shared_stats['econ'].n,
            'mean': shared_stats['econ'].mean,
            'S': shared_stats['econ'].S
        }
        torch.save(econ_state, final_path + '_econ_stat.pth')
        writer.close()
        
        if len(losses_total) > 0:
            try:
                import matplotlib.pyplot as plt
                plt.figure(figsize=(12, 6))
                plt.plot(losses_total, label="Total Loss", color="#1f77b4", linewidth=2)
                plt.plot(losses_actor, label="Actor Loss (Policy)", color="#2ca02c", linewidth=1.5, alpha=0.8)
                plt.plot(losses_critic, label="Critic Loss (Value)", color="#d62728", linewidth=1.5, alpha=0.8)
                plt.title(f"Evolução das Losses de Treino (PPO Constrangido) - Seed {seed}", fontsize=14, fontweight='bold')
                plt.xlabel("Iterações de Treino", fontsize=12)
                plt.ylabel("Loss", fontsize=12)
                plt.legend(loc='upper right')
                plt.grid(True, linestyle='--', alpha=0.5)
                plt.tight_layout()
                
                plot_loss_path = os.path.join(save_dir, f"ppo_constrained_losses_seed_{seed}.png")
                plt.savefig(plot_loss_path, dpi=300)
                plt.close()
                logger.info(f"[OK] Gráfico de losses guardado com sucesso em: {plot_loss_path}")
            except Exception as e:
                logger.error(f"[ERRO] Falha ao gerar gráfico de losses: {e}")

if __name__ == "__main__":
    SEEDS = [1337, 42]
    for current_seed in SEEDS:
        train_multi_core(seed=current_seed)
