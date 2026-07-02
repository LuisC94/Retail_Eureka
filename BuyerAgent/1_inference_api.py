import os
import sys
import torch
import numpy as np
import pickle
import time
import matplotlib.pyplot as plt

from environment_constrained import StockEnvironment
from agent.ppo_agent import ParallelPPOAgent

# --- CONFIGURAÇÃO ---
EXCEL_PATH = r"Dados\m5_foods_3_080.xlsx" # Atualizado para o ficheiro correto do SKU 3_080
MODEL_DIR = "modelos_producao_constrained"
MEMORY_PATH = r"memoria\buffer_real.pkl"
MAX_CAPACITY = 500

# Se já houver um modelo treinado na pasta local, podemos começar a partir dele
DEFAULT_MODEL_FALLBACK = r"modelos_producao_constrained\3_080\ppo_constrained_iter313" 

def get_latest_model():
    """ Procura na pasta modelos_producao_constrained pelo ficheiro mais recente. """
    if not os.path.exists(MODEL_DIR):
        os.makedirs(MODEL_DIR)
        
    files = [os.path.join(MODEL_DIR, f) for f in os.listdir(MODEL_DIR) if f.endswith('.pth')]
    if len(files) == 0:
        return DEFAULT_MODEL_FALLBACK
    # Retorna o ficheiro mais recentemente modificado
    return max(files, key=os.path.getmtime)

def inference_loop():
    print("======================================================")
    print(" INICIANDO MÓDULO DE INFERÊNCIA (O GERENTE DE LOJA)   ")
    print("======================================================")
    
    # Inicia o ambiente simulando o mundo real usando os dados de teste (os últimos 40% do Excel)
    env = StockEnvironment(excel_path=EXCEL_PATH, is_training=False, train_split=0.6, max_capacity=MAX_CAPACITY)
    
    # Inicializar Ambientes para as Baselines
    env_dos = StockEnvironment(excel_path=EXCEL_PATH, is_training=False, train_split=0.6, max_capacity=MAX_CAPACITY)
    env_dos.max_order_limit = float('inf') # Sem limite de encomenda para DOS
    env_cnn = StockEnvironment(excel_path=EXCEL_PATH, is_training=False, train_split=0.6, max_capacity=MAX_CAPACITY)
    env_cnn.max_order_limit = float('inf') # Sem limite de encomenda para CNN
    env_minmax = StockEnvironment(excel_path=EXCEL_PATH, is_training=False, train_split=0.6, max_capacity=MAX_CAPACITY)
    env_minmax.max_order_limit = float('inf') # Sem limite de encomenda para Min-Max
    
    env_dos.reset()
    env_cnn.reset()
    env_minmax.reset()
    
    state_dim = 17
    action_dim = 1
    
    # Obter o limite cap dinâmico
    max_order_limit = env.max_order_limit
    print(f"[OK] Limite Máximo de Encomenda Diária (Constrained): {max_order_limit} un")
    
    agent = ParallelPPOAgent(state_dim=state_dim, action_dim=action_dim, max_action=max_order_limit)
    
    model_path = get_latest_model()
    try:
        agent.load(model_path)
        print(f"[OK] Manual de Regras Carregado de: {model_path}")
    except Exception as e:
        print(f"[AVISO] Não foi possível carregar {model_path}. O agente vai usar regras aleatórias. Erro: {e}")

    # Movemos para CPU porque a inferência é leve
    agent.policy_old_actor.to('cpu')
    agent.policy_old_actor.eval()
    
    state = env.reset()
    done = False
    
    # Inicializa ou carrega a memória existente
    if os.path.exists(MEMORY_PATH):
        with open(MEMORY_PATH, 'rb') as f:
            experience_buffer = pickle.load(f)
    else:
        experience_buffer = []

    # Listas para guardar dados para os gráficos
    rewards_agent = []
    profits_agent = []
    profits_dos = []
    profits_cnn = []
    profits_minmax = []
    
    actions_agent = []
    actions_dos = []
    actions_cnn = []
    actions_minmax = []
    
    cum_profit_agent = 0
    cum_profit_dos = 0
    cum_profit_cnn = 0
    cum_profit_minmax = 0

    print("\nSimulando a chegada de novos dias (Loop Rápido)...")
    
    dias_simulados = 0
    
    # Definição das funções das baselines (adaptadas de evaluate_ppo_mcts_foresight.py)
    def simular_dos_3d(env_copy):
        step = env_copy.current_step
        lookahead = min(env_copy.max_steps, step + 3)
        future_demands = env_copy.data.iloc[step:lookahead]['prediction'].sum()
        current_stock = sum(env_copy.stock_profile) + sum(env_copy.in_transit.values())
        return max(0, future_demands - current_stock)

    def simular_cnn_naive(env_copy):
        step = env_copy.current_step
        pred_today = env_copy.data.iloc[step]['prediction']
        pred_tomorrow = env_copy.data.iloc[min(env_copy.max_steps, step + 1)]['prediction']
        current_stock = sum(env_copy.stock_profile) + sum(env_copy.in_transit.values())
        stock_fim_do_dia = max(0, current_stock - pred_today)
        return max(0, pred_tomorrow - stock_fim_do_dia)

    def simular_min_max(env_copy, min_stock=100, max_stock=250):
        current_stock = sum(env_copy.stock_profile) + sum(env_copy.in_transit.values())
        if current_stock <= min_stock:
            return max_stock - current_stock
        return 0
    
    while not done:
        day = env.current_step
        
        # 1. Ação do Agente
        state_tensor = torch.FloatTensor(state).unsqueeze(0).to('cpu')
        with torch.no_grad():
            action_mean, log_std = agent.policy_old_actor(state_tensor)
            dist = torch.distributions.Normal(action_mean, torch.exp(torch.clamp(log_std, -2.3, 1.5)))
            action_percent = dist.sample()
            action_logprob = dist.log_prob(action_percent)
            physical_action = torch.round(torch.clamp(action_percent * max_order_limit, 0, max_order_limit)).numpy().flatten()[0]

        # 2. Ações das Baselines
        action_dos = simular_dos_3d(env_dos)
        action_cnn = simular_cnn_naive(env_cnn)
        action_minmax = simular_min_max(env_minmax)

        # 3. Avançar os Ambientes
        next_state, reward, done, info = env.step(physical_action)
        _, _, _, info_dos = env_dos.step(action_dos)
        _, _, _, info_cnn = env_cnn.step(action_cnn)
        _, _, _, info_minmax = env_minmax.step(action_minmax)
        
        print(f"[Dia {day:02d}] Ação Ditada: {physical_action:04.0f} caixas | Lucro Realizado: {info['profit']:.2f}€")
        
        # O Gerente de Loja escreve a experiência no seu diário para o Analista ler mais tarde
        experience_buffer.append({
            'state': state_tensor.squeeze(0).numpy(),
            'action': action_percent.squeeze(0).numpy(),
            'logprob': action_logprob.squeeze(0).numpy(),
            'reward': reward,
            'is_terminal': done
        })
        
        # Guardar dados para gráficos
        rewards_agent.append(reward)
        
        cum_profit_agent += info['profit']
        cum_profit_dos += info_dos['profit']
        cum_profit_cnn += info_cnn['profit']
        cum_profit_minmax += info_minmax['profit']
        
        profits_agent.append(cum_profit_agent)
        profits_dos.append(cum_profit_dos)
        profits_cnn.append(cum_profit_cnn)
        profits_minmax.append(cum_profit_minmax)
        
        actions_agent.append(physical_action)
        actions_dos.append(action_dos)
        actions_cnn.append(action_cnn)
        actions_minmax.append(action_minmax)
        
        state = next_state
        dias_simulados += 1
        
        # Simula uma pequena pausa para podermos ver no ecrã (opcional)
        time.sleep(0.01)
        
    # Guarda o buffer atualizado no disco
    os.makedirs(os.path.dirname(MEMORY_PATH), exist_ok=True)
    with open(MEMORY_PATH, 'wb') as f:
        pickle.dump(experience_buffer, f)
        
    print("======================================================")
    print(f"[FIM] {dias_simulados} dias simulados.")
    print(f"[MEMÓRIA] O ficheiro 'buffer_real.pkl' tem agora {len(experience_buffer)} registos guardados.")
    print("======================================================")
    
    # --- GERAÇÃO DE GRÁFICOS ---
    print("\nA gerar gráficos de desempenho...")
    
    # Gráfico 1: Evolução das Rewards diárias do Agente
    plt.figure(figsize=(12, 5))
    plt.plot(rewards_agent, label='Reward Diária (Agente)', color='#1f77b4')
    plt.title("Evolução das Rewards Diárias do Agente")
    plt.xlabel("Dias")
    plt.ylabel("Reward")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.savefig(r"Dados\rewards_diarias.png", dpi=300)
    plt.close()
    
    # Gráfico 2: Lucros Acumulados vs Baselines
    plt.figure(figsize=(12, 7))
    plt.plot(profits_agent, label=f'PPO Agente (Lucro: {cum_profit_agent:.0f}€)', color='#1f77b4', linewidth=3)
    plt.plot(profits_cnn, label=f'CNN Naive (Lucro: {cum_profit_cnn:.0f}€)', color='#ff7f0e', linestyle='--')
    plt.plot(profits_dos, label=f'DOS 3 Dias (Lucro: {cum_profit_dos:.0f}€)', color='#2ca02c', linestyle='-.')
    plt.plot(profits_minmax, label=f'Min-Max Clássico (Lucro: {cum_profit_minmax:.0f}€)', color='#d62728', linestyle=':')
    
    plt.title("Lucro Acumulado: Agente vs Baselines")
    plt.xlabel("Dias")
    plt.ylabel("Lucro Acumulado (€)")
    plt.legend(loc="upper left")
    plt.grid(True, alpha=0.3)
    plt.savefig(r"Dados\lucro_acumulado_vs_baselines.png", dpi=300)
    plt.close()
    
    # Gráfico 3: Ações Tomadas vs Baselines
    plt.figure(figsize=(12, 5))
    plt.plot(actions_agent, label='Ações Agente', color='#1f77b4', alpha=0.7)
    plt.plot(actions_cnn, label='Ações CNN Naive', color='#ff7f0e', alpha=0.5, linestyle='--')
    plt.plot(actions_dos, label='Ações DOS 3 Dias', color='#2ca02c', alpha=0.5, linestyle='-.')
    
    plt.title("Ações Tomadas (Encomendas) ao Longo dos Dias")
    plt.xlabel("Dias")
    plt.ylabel("Quantidade Encomendada")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.savefig(r"Dados\acoes_tomadas.png", dpi=300)
    plt.close()
    
    print("[OK] Gráficos guardados na pasta 'Dados'!")
    print("======================================================")

if __name__ == "__main__":
    inference_loop()
