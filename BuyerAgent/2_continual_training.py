import os
import sys
import torch
import pickle
import glob

from agent.ppo_agent import ParallelPPOAgent
from environment_constrained import StockEnvironment

# --- CONFIGURAÇÃO ---
MODEL_DIR = "modelos_producao_constrained"
MEMORY_PATH = r"memoria\buffer_real.pkl"
MAX_CAPACITY = 500

# Learning Rates MUITO BAIXOS para fine-tuning (10x a 100x mais baixos que o treino offline)
ONLINE_LR_ACTOR = 1e-5
ONLINE_LR_CRITIC = 5e-5
ONLINE_BATCH_SIZE = 32

# Quantos dias novos precisamos no mínimo para valer a pena treinar?
MIN_EXPERIENCES_TO_TRAIN = 15

DEFAULT_MODEL_FALLBACK = r"modelos_producao_constrained\3_080\ppo_constrained_iter313"

def get_latest_model():
    if not os.path.exists(MODEL_DIR):
        os.makedirs(MODEL_DIR)
        
    files = [os.path.join(MODEL_DIR, f) for f in os.listdir(MODEL_DIR) if f.endswith('.pth')]
    if len(files) == 0:
        return DEFAULT_MODEL_FALLBACK
    return max(files, key=os.path.getmtime)

def get_next_version_name():
    files = [f for f in os.listdir(MODEL_DIR) if f.startswith('modelo_v') and f.endswith('.pth')]
    if not files:
        return os.path.join(MODEL_DIR, "modelo_v1.pth")
    # Encontra o maior número
    versions = []
    for f in files:
        try:
            v = int(f.split('modelo_v')[1].split('.pth')[0])
            versions.append(v)
        except:
            pass
    next_v = max(versions) + 1 if versions else 1
    return os.path.join(MODEL_DIR, f"modelo_v{next_v}.pth")

def continual_training():
    print("======================================================")
    print(" INICIANDO MÓDULO DE TREINO (O ANALISTA FINANCEIRO)   ")
    print("======================================================")
    
    # 1. Verificar se há dados para treinar
    if not os.path.exists(MEMORY_PATH):
        print("[AVISO] O 'buffer_real.pkl' não existe. O Gerente ainda não trabalhou.")
        return
        
    with open(MEMORY_PATH, 'rb') as f:
        experiences = pickle.load(f)
        
    if len(experiences) < MIN_EXPERIENCES_TO_TRAIN:
        print(f"[AVISO] Apenas {len(experiences)} dias na memória. Esperando por pelo menos {MIN_EXPERIENCES_TO_TRAIN}.")
        return
        
    print(f"[OK] Encontrados {len(experiences)} dias de nova experiência. A preparar o estudo...")
    
    # Inicia o ambiente de treino (usa os primeiros 60% do Excel) para obter o limite
    EXCEL_PATH = r"Dados\m5_foods_3_080.xlsx"
    env_train = StockEnvironment(excel_path=EXCEL_PATH, is_training=True, train_split=0.6, max_capacity=MAX_CAPACITY)
    max_order_limit = env_train.max_order_limit
    print(f"[OK] Limite Máximo de Encomenda Diária (Constrained): {max_order_limit} un")
    
    state_dim = 17
    action_dim = 1
    
    agent = ParallelPPOAgent(state_dim=state_dim, action_dim=action_dim, max_action=max_order_limit, batch_size=ONLINE_BATCH_SIZE)
    
    # 2. Carregar o modelo atual
    model_path = get_latest_model()
    try:
        agent.load(model_path)
        print(f"[OK] Manual Atual carregado de: {model_path}")
    except Exception as e:
        print(f"[ERRO CRÍTICO] Não consegui carregar o modelo base. {e}")
        return

    # 3. Forçar as Learning Rates para modo "Fine-Tuning"
    for param_group in agent.optimizer_actor.param_groups:
        param_group['lr'] = ONLINE_LR_ACTOR
    for param_group in agent.optimizer_critic.param_groups:
        param_group['lr'] = ONLINE_LR_CRITIC
        
    # 4. Replay Buffer Misto (80% Passado / 20% Presente)
    num_new_days = len(experiences)
    # Queremos que os dados novos representem 20% do total. Logo, os dados antigos devem ser 4x os dados novos.
    num_old_needed = num_new_days * 4
    
    print(f"\n[MIXED BUFFER] Temos {num_new_days} dias novos. Vamos gerar {num_old_needed} dias antigos para manter a proporção 80/20.")
    
    # Gerar dados antigos (80%)
    state = env_train.reset()
    dias_gerados = 0
    
    # Colocamos o ator em modo de avaliação para gerar trajetórias estáveis
    agent.policy_old_actor.eval()
    
    while dias_gerados < num_old_needed:
        state_tensor = torch.FloatTensor(state).unsqueeze(0).to(agent.device)
        with torch.no_grad():
            action_mean, log_std = agent.policy_old_actor(state_tensor)
            dist = torch.distributions.Normal(action_mean, torch.exp(torch.clamp(log_std, -2.3, 1.5)))
            action_percent = dist.sample()
            action_logprob = dist.log_prob(action_percent)
            
            physical_action = torch.round(torch.clamp(action_percent * max_order_limit, 0, max_order_limit)).cpu().numpy().flatten()[0]
            
        next_state, reward, done, _ = env_train.step(physical_action)
        
        # Guarda no buffer do agente (Simulando 1 ambiente para o ParallelPPOAgent)
        agent.buffer.states.append(state_tensor) # Shape [1, 28]
        agent.buffer.actions.append(action_percent) # Shape [1, 1]
        agent.buffer.logprobs.append(action_logprob) # Shape [1, 1]
        agent.buffer.rewards.append([reward]) # Lista de tamanho 1
        agent.buffer.is_terminals.append([done]) # Lista de tamanho 1
        
        state = next_state
        dias_gerados += 1
        
        if done:
            state = env_train.reset()
            
    print(f"[OK] {dias_gerados} dias de memória antiga gerados com sucesso.")
    
    # Injetar os dados novos (20%) (Simulando 1 ambiente para o ParallelPPOAgent)
    for exp in experiences:
        agent.buffer.states.append(torch.FloatTensor(exp['state']).unsqueeze(0).to(agent.device)) # Shape [1, 28]
        agent.buffer.actions.append(torch.FloatTensor(exp['action']).unsqueeze(0).to(agent.device)) # Shape [1, 1]
        agent.buffer.logprobs.append(torch.FloatTensor(exp['logprob']).unsqueeze(0).to(agent.device)) # Shape [1, 1]
        agent.buffer.rewards.append([exp['reward']]) # Lista de tamanho 1
        agent.buffer.is_terminals.append([exp['is_terminal']]) # Lista de tamanho 1
        
    print(f"[OK] {num_new_days} dias reais adicionados ao buffer.")
        
    print(f"\n[A TREINAR] A executar PPO Update com Actor LR={ONLINE_LR_ACTOR} e Critic LR={ONLINE_LR_CRITIC}...")
    
    # O comando mágico onde a rede atualiza os pesos
    agent.update()
    
    print("[OK] Treino concluído com sucesso.")
    
    # 5. Guardar a Nova Versão
    new_model_path = get_next_version_name()
    agent.save(new_model_path)
    print(f"[OK] Novo manual de regras impresso e guardado em: {new_model_path}")
    
    # 6. Limpar o Diário de Experiências (Opcionalmente, poderíamos arquivá-lo num CSV histórico)
    with open(MEMORY_PATH, 'wb') as f:
        pickle.dump([], f)
    print("[LIMPEZA] 'buffer_real.pkl' foi esvaziado para os próximos dias.")
    print("======================================================")

if __name__ == "__main__":
    continual_training()
