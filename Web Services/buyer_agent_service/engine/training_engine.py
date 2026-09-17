import os
import json
import time
import datetime
import torch
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional

from .environment_constrained import StockEnvironment, EnvRunningStat
from .ppo_agent import ParallelPPOAgent


def train_buyer_agent(
    data: pd.DataFrame,
    save_dir: str,
    user_id: Any,
    culture_id: Any,
    fruit_key: str = "maca_gala",
    max_capacity: float = 500.0,
    total_episodes: int = 500,
    num_envs: int = 16,
    horizon: int = 60,
    lr_actor: float = 0.0003,
    lr_critic: float = 0.001,
    gamma: float = 0.8,
    K_epochs: int = 15,
    eps_clip: float = 0.2,
    batch_size: int = 512,
    seed: int = 42
) -> Dict[str, Any]:
    """
    Treina o Agente de Compras (PPO Constrangido) de forma modular para um utilizador e cultura.
    Gera e guarda os pesos do Actor, Critic, Scaler e Metadados.
    """
    torch.manual_seed(seed)
    np.random.seed(seed)
    
    os.makedirs(save_dir, exist_ok=True)
    start_time = time.time()
    
    shared_stats = {
        'econ': EnvRunningStat()
    }
    
    # 1. Instanciar N ambientes sincronizados
    envs = [
        StockEnvironment(
            data=data,
            is_training=True,
            train_split=0.8,
            max_capacity=max_capacity,
            fruit_key=fruit_key,
            shared_stats=shared_stats
        ) for _ in range(num_envs)
    ]
    
    max_order_limit = envs[0].max_order_limit
    scaler_min = envs[0].scaler.data_min_.tolist()
    scaler_max = envs[0].scaler.data_max_.tolist()
    
    # 2. Instanciar o Agente PPO
    agent = ParallelPPOAgent(
        state_dim=17,
        action_dim=1,
        max_action=max_order_limit,
        lr_actor=lr_actor,
        lr_critic=lr_critic,
        gamma=gamma,
        K_epochs=K_epochs,
        eps_clip=eps_clip,
        batch_size=batch_size
    )
    agent.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    agent.policy_old_actor.to(agent.device)
    agent.policy_old_critic.to(agent.device)
    
    states = [env.reset() for env in envs]
    states_matrix = np.array(states)
    
    episodes_played = 0
    iteration = 0
    recent_profits = []
    
    # 3. Ciclo de Treino PPO
    while episodes_played < total_episodes:
        iteration += 1
        agent.buffer.clear()
        
        for step in range(horizon):
            with torch.no_grad():
                st_tensor = torch.FloatTensor(states_matrix).to(agent.device)
                action_mean_percent, log_std = agent.policy_old_actor(st_tensor)
                
                clamped_log_std = torch.clamp(log_std, min=-2.3, max=1.5)
                std_tensor = torch.exp(clamped_log_std)
                dist = torch.distributions.Normal(action_mean_percent, std_tensor)
                
                action_percent = dist.sample()
                action_logprob = dist.log_prob(action_percent)
                physical_actions = torch.round(
                    torch.clamp(action_percent * max_order_limit, 0, max_order_limit)
                ).cpu().numpy().flatten()
            
            agent.buffer.states.append(st_tensor)
            agent.buffer.actions.append(action_percent)
            agent.buffer.logprobs.append(action_logprob)
            
            next_states_list = []
            rewards_list = []
            dones_list = []
            
            for i in range(num_envs):
                ns, r, d, info = envs[i].step(physical_actions[i])
                if d:
                    ns = envs[i].reset()
                next_states_list.append(ns)
                rewards_list.append(r)
                dones_list.append(d)
                recent_profits.append(info['profit'])
                
            agent.buffer.rewards.append(rewards_list)
            agent.buffer.is_terminals.append(dones_list)
            states_matrix = np.array(next_states_list)
            
        with torch.no_grad():
            st_final = torch.FloatTensor(states_matrix).to(agent.device)
            agent.buffer.states.append(st_final)
            
        # Atualização dos gradientes PPO
        loss_total, loss_actor, loss_critic = agent.update()
        episodes_played += num_envs
        
    # 4. Guardar Pesos e Scaler
    agent.save(save_dir)
    
    # 5. Guardar Metadados do Modelo
    elapsed_time = round(time.time() - start_time, 2)
    avg_profit = float(np.mean(recent_profits[-100:])) if recent_profits else 0.0
    
    meta = {
        "user_id": user_id,
        "culture_id": culture_id,
        "fruit_key": fruit_key,
        "max_capacity": max_capacity,
        "max_order_limit": max_order_limit,
        "scaler_min": scaler_min,
        "scaler_max": scaler_max,
        "episodes_trained": episodes_played,
        "training_time_seconds": elapsed_time,
        "avg_profit": round(avg_profit, 2),
        "trained_at": datetime.datetime.utcnow().isoformat(),
        "state_dim": 17,
        "action_dim": 1
    }
    
    with open(os.path.join(save_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=4)
        
    return {
        "status": "success",
        "message": f"Buyer Agent treinado com sucesso ({episodes_played} episódios em {elapsed_time}s).",
        "user_id": user_id,
        "culture_id": culture_id,
        "fruit_key": fruit_key,
        "max_order_limit": max_order_limit,
        "avg_profit": round(avg_profit, 2),
        "training_time_seconds": elapsed_time,
        "saved_path": save_dir,
        "trained_at": meta["trained_at"]
    }
