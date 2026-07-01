import os
import sys
import torch
import numpy as np
import pandas as pd
from django.conf import settings

# Adicionar a pasta BuyerAgent ao sys.path dinamicamente para resolver imports relativos de agent.*
buyer_agent_path = os.path.join(settings.BASE_DIR, 'BuyerAgent')
if buyer_agent_path not in sys.path:
    sys.path.append(buyer_agent_path)

# Hiperparâmetros de Fine-Tuning leves para CPU
ONLINE_LR_ACTOR = 1e-5
ONLINE_LR_CRITIC = 5e-5
ONLINE_BATCH_SIZE = 32

def continual_training_step(agent, new_experiences, env_train, max_action_val):
    """
    Executa 1 ciclo de fine-tuning do cérebro PPO do agente,
    misturando memórias históricas do treino (80%) com experiências novas do mercado (20%)
    para evitar esquecimento catastrófico (Catastrophic Forgetting).
    """
    # Forçar as learning rates leves para fine-tuning
    for param_group in agent.optimizer_actor.param_groups:
        param_group['lr'] = ONLINE_LR_ACTOR
    for param_group in agent.optimizer_critic.param_groups:
        param_group['lr'] = ONLINE_LR_CRITIC

    num_new_days = len(new_experiences)
    num_old_needed = num_new_days * 4 # Proporção 80/20

    # 1. Gerar trajetórias históricas antigas do split de treino
    state = env_train.reset()
    dias_gerados = 0
    agent.policy_old_actor.eval()

    while dias_gerados < num_old_needed:
        state_tensor = torch.FloatTensor(state).unsqueeze(0).to(agent.device)
        with torch.no_grad():
            action_mean, log_std = agent.policy_old_actor(state_tensor)
            dist = torch.distributions.Normal(action_mean, torch.exp(torch.clamp(log_std, -2.3, 1.5)))
            action_percent = dist.sample()
            action_logprob = dist.log_prob(action_percent)
            physical_action = torch.round(torch.clamp(action_percent * max_action_val, 0, max_action_val)).cpu().numpy().flatten()[0]

        next_state, reward, done, _ = env_train.step(physical_action)

        # Adicionar trajetórias passadas ao buffer
        agent.buffer.states.append(state_tensor)
        agent.buffer.actions.append(action_percent)
        agent.buffer.logprobs.append(action_logprob)
        agent.buffer.rewards.append([reward])
        agent.buffer.is_terminals.append([done])

        state = next_state
        dias_gerados += 1
        if done:
            state = env_train.reset()

    # 2. Injetar experiências recentes do simulador no buffer
    for exp in new_experiences:
        agent.buffer.states.append(torch.FloatTensor(exp['state']).unsqueeze(0).to(agent.device))
        agent.buffer.actions.append(torch.FloatTensor(exp['action']).unsqueeze(0).to(agent.device))
        agent.buffer.logprobs.append(torch.FloatTensor(exp['logprob']).unsqueeze(0).to(agent.device))
        agent.buffer.rewards.append([exp['reward']])
        agent.buffer.is_terminals.append([exp['is_terminal']])

    # 3. Executar otimização matemática PPO (K-epochs = 30)
    agent.update()



def run_buyer_agent_simulation(product_sku, max_capacity=500, update_interval_days=15, num_days=150, min_threshold=35, max_threshold=130):
    """
    Executa a simulação completa de 150 dias do BuyerAgent em CPU.
    Compara o Lucro Acumulado do PPO Agent vs baseline Min-Max vs Oráculo Perfeito (God Mode)
    e aplica ciclos de Fine-Tuning (treino dinâmico online) a cada N dias de forma dinâmica.
    """
    # Ensure BuyerAgent path takes precedence in sys.path
    if buyer_agent_path in sys.path:
        sys.path.remove(buyer_agent_path)
    sys.path.insert(0, buyer_agent_path)
    
    # Force reload of agent packages to avoid collision with StockManagement
    import sys as sys_module
    for mod in ['agent.ppo_agent', 'agent.actor_critic', 'agent']:
        if mod in sys_module.modules:
            del sys_module.modules[mod]
            
    from environment_constrained import StockEnvironment
    from agent.ppo_agent import ParallelPPOAgent

    # 1. Definir caminho do dataset excel
    excel_name = f"m5_foods_{product_sku}.xlsx"
    if product_sku == "911753":
        excel_name = "911753_151dias_com_real.xlsx"
    excel_path = os.path.join(buyer_agent_path, 'datasets', excel_name)
    if not os.path.exists(excel_path):
        excel_path = os.path.join(buyer_agent_path, 'datasets', 'm5_foods_3_080.xlsx')

    # 2. Inicializar os ambientes
    env_test = StockEnvironment(excel_path=excel_path, is_training=False, train_split=0.6, max_capacity=max_capacity)
    env_minmax = StockEnvironment(excel_path=excel_path, is_training=False, train_split=0.6, max_capacity=max_capacity)
    env_minmax.max_order_limit = float('inf') # Sem limite de encomenda para Min-Max
    env_oracle = StockEnvironment(excel_path=excel_path, is_training=False, train_split=0.6, max_capacity=max_capacity)
    env_oracle.max_order_limit = float('inf') # Sem limite de encomenda para o Oráculo
    env_train = StockEnvironment(excel_path=excel_path, is_training=True, train_split=0.6, max_capacity=max_capacity)

    # 3. Instanciar o Agente
    state_dim = 17
    action_dim = 1
    # O limite máximo histórico de vendas define a escala de encomendas máxima
    max_order_limit = env_test.max_order_limit
    agent = ParallelPPOAgent(state_dim=state_dim, action_dim=action_dim, max_action=max_order_limit, batch_size=ONLINE_BATCH_SIZE)
    
    # Forçar dispositivo CPU para não pesar em servidores de produção
    agent.device = torch.device('cpu')
    agent.policy_actor.to('cpu')
    agent.policy_critic.to('cpu')
    agent.policy_old_actor.to('cpu')
    agent.policy_old_critic.to('cpu')

    # 4. Carregar os pesos pré-treinados
    sku_dir = "3_080" if product_sku not in ["3_080", "3_090", "3_252", "3_586"] else product_sku
    checkpoint_dir = os.path.join(buyer_agent_path, 'modelos_producao_constrained', sku_dir)
    checkpoint_path = os.path.join(checkpoint_dir, 'ppo_constrained_iter313')

    # Carregar actor e critic
    agent.load(checkpoint_path)
    
    # Carregar econ stats do Z-Score de Recompensa
    econ_stat_path = checkpoint_path + '_econ_stat.pth'
    if os.path.exists(econ_stat_path):
        econ_state = torch.load(econ_stat_path, map_location='cpu', weights_only=False)
        for env in [env_test, env_minmax, env_oracle, env_train]:
            env.stat_profit.n = econ_state['n']
            env.stat_profit.mean = econ_state['mean']
            env.stat_profit.S = econ_state['S']

    agent.policy_old_actor.eval()

    # 5. Iniciar variáveis de log
    state = env_test.reset()
    env_minmax.reset()
    env_oracle.reset()

    done = False
    dias_simulados = 0

    log_dias = []
    log_procura_real = []
    
    # Acumuladores de Lucros
    profits_agent = []
    profits_minmax = []
    profits_oracle = []
    
    # Ações diárias
    actions_agent = []
    actions_minmax = []
    actions_oracle = []

    # Telemetria do Agente
    log_stock_inicial = []
    log_stock_final = []
    log_vendas = []
    log_vendas_perdidas = []
    log_apodrecimento = []
    log_excesso = []

    # Flags de Penalidades
    flag_stockout = []
    flag_clientes_perdidos = []
    flag_excesso_armazem = []
    flag_apodrecimento_urgente = []

    update_days = []
    current_15d_buffer = []

    cum_profit_agent = 0
    cum_profit_minmax = 0
    cum_profit_oracle = 0

    # Limitar o número máximo de passos ao dataset ou num_days
    max_steps_to_run = min(env_test.max_steps, num_days)

    cum_waste_minmax = 0
    cum_lost_sales_minmax = 0

    # 6. Loop de Inferência Diária
    while not done and dias_simulados < max_steps_to_run:
        day = env_test.current_step

        # --- BASELINE: MIN-MAX ---
        stock_hoje_minmax = sum(env_minmax.stock_profile) + env_minmax.in_transit.get(env_minmax.current_step, 0)
        vendas_hoje_minmax = env_minmax.data.iloc[env_minmax.current_step]['real_value']
        stock_amanha_minmax = max(0, stock_hoje_minmax - vendas_hoje_minmax) + env_minmax.in_transit.get(env_minmax.current_step + 1, 0)
        
        action_minmax = 0
        if stock_amanha_minmax <= min_threshold:
            action_minmax = max(0, max_threshold - stock_amanha_minmax)
            action_minmax = min(action_minmax, max_capacity)
            
        _, _, _, info_minmax = env_minmax.step(action_minmax)
        cum_profit_minmax += info_minmax['profit']
        cum_waste_minmax += float(info_minmax['overflow_waste'])
        cum_lost_sales_minmax += float(max(0, vendas_hoje_minmax - info_minmax['sales']))

        # --- BASELINE: ORÁCULO PERFEITO ---
        stock_hoje_oracle = sum(env_oracle.stock_profile) + env_oracle.in_transit.get(env_oracle.current_step, 0)
        vendas_hoje_oracle = env_oracle.data.iloc[env_oracle.current_step]['real_value']
        stock_amanha_oracle = max(0, stock_hoje_oracle - vendas_hoje_oracle) + env_oracle.in_transit.get(env_oracle.current_step + 1, 0)
        
        action_oracle = 0
        demand_tomorrow = env_oracle.data.iloc[env_oracle.current_step + 1]['real_value'] if env_oracle.current_step + 1 <= env_oracle.max_steps else 0
        
        if stock_amanha_oracle < demand_tomorrow:
            future_demand = 0
            for i in range(1, 5):
                idx = env_oracle.current_step + i
                if idx <= env_oracle.max_steps:
                    future_demand += env_oracle.data.iloc[idx]['real_value']
            
            action_oracle = max(0, future_demand - stock_amanha_oracle)
            action_oracle = min(action_oracle, max_capacity)
            
        _, _, _, info_oracle = env_oracle.step(action_oracle)
        cum_profit_oracle += info_oracle['profit']

        state_tensor = torch.FloatTensor(state).unsqueeze(0).to(agent.device)
        with torch.no_grad():
            action_mean, log_std = agent.policy_old_actor(state_tensor)
            dist = torch.distributions.Normal(action_mean, torch.exp(torch.clamp(log_std, -2.3, 1.5)))
            action_percent = dist.sample()
            action_logprob = dist.log_prob(action_percent)
            physical_action = float(torch.round(torch.clamp(action_percent * max_order_limit, 0, max_order_limit)).cpu().numpy().flatten()[0])

        stock_inicial_hoje = float(sum(env_test.stock_profile))

        # Passo real do ambiente de teste
        next_state, reward, done_env, info = env_test.step(physical_action)
        done = done_env

        # Guardar experiências recentes para fine-tuning
        current_15d_buffer.append({
            'state': state_tensor.squeeze(0).cpu().numpy(),
            'action': action_percent.squeeze(0).cpu().numpy(),
            'logprob': action_logprob.squeeze(0).cpu().numpy(),
            'reward': reward,
            'is_terminal': done
        })

        # Acumular lucros do agente
        cum_profit_agent += info['profit']

        # Guardar dados nos logs diários
        log_dias.append(day)
        log_procura_real.append(float(info['real_demand']))
        
        profits_agent.append(float(cum_profit_agent))
        profits_minmax.append(float(cum_profit_minmax))
        profits_oracle.append(float(cum_profit_oracle))
        
        actions_agent.append(float(physical_action))
        actions_minmax.append(float(action_minmax))
        actions_oracle.append(float(action_oracle))

        # Telemetria do Armazém
        stock_final_hoje = float(sum(env_test.stock_profile))
        sales = float(info['sales'])
        lost_sales = float(max(0, info['real_demand'] - sales))
        overcapacity_waste = float(max(0, info['overflow_waste'] - info['spoilage']))
        spoilage = float(info['spoilage'])

        log_stock_inicial.append(stock_inicial_hoje)
        log_stock_final.append(stock_final_hoje)
        log_vendas.append(sales)
        log_vendas_perdidas.append(lost_sales)
        log_apodrecimento.append(spoilage)
        log_excesso.append(overcapacity_waste)

        # Flags de Penalidades
        flag_stockout.append(1 if stock_final_hoje <= 0 else 0)
        flag_clientes_perdidos.append(1 if lost_sales > 0 else 0)
        flag_excesso_armazem.append(1 if overcapacity_waste > 0 else 0)
        flag_apodrecimento_urgente.append(1 if spoilage > 0 else 0)

        state = next_state
        dias_simulados += 1

        # --- TRIGGER FINE-TUNING ONLINE ---
        # Apenas executa se não for o último dia e se passarem os dias do intervalo de update
        if dias_simulados % update_interval_days == 0 and not done:
            update_days.append(dias_simulados)
            continual_training_step(agent, current_15d_buffer, env_train, max_order_limit)
            current_15d_buffer = []
            agent.policy_old_actor.eval()

    # 7. Formatar payload de resposta JSON consolidada
    payload = {
        'dias': log_dias,
        'procura_real': log_procura_real,
        'lucros_agente': profits_agent,
        'lucros_minmax': profits_minmax,
        'lucros_oracle': profits_oracle,
        'acoes_agente': actions_agent,
        'acoes_minmax': actions_minmax,
        'acoes_oracle': actions_oracle,
        'stock_inicial': log_stock_inicial,
        'stock_final': log_stock_final,
        'vendas_efetivas': log_vendas,
        'vendas_perdidas': log_vendas_perdidas,
        'apodrecimento': log_apodrecimento,
        'excesso_descarte': log_excesso,
        'update_days': update_days,
        'flags': {
            'stockout': flag_stockout,
            'clientes_perdidos': flag_clientes_perdidos,
            'excesso_armazem': flag_excesso_armazem,
            'apodrecimento': flag_apodrecimento_urgente
        },
        'kpis': {
            'lucro_final_agente': float(cum_profit_agent),
            'lucro_final_minmax': float(cum_profit_minmax),
            'lucro_final_oracle': float(cum_profit_oracle),
            'ganho_versus_minmax': float(((cum_profit_agent - cum_profit_minmax) / (abs(cum_profit_minmax) + 1e-8)) * 100),
            'total_descarte_kg': float(sum(log_apodrecimento) + sum(log_excesso)),
            'total_descarte_minmax': float(cum_waste_minmax),
            'total_clientes_perdidos_un': float(sum(log_vendas_perdidas)),
            'total_clientes_perdidos_minmax': float(cum_lost_sales_minmax),
            'total_procura_un': float(sum(log_procura_real)),
            'ciclos_treino_run': len(update_days),
            'eficiencia_fill_rate': float((sum(log_vendas) / (sum(log_procura_real) + 1e-8)) * 100)
        }
    }

    return payload

def run_pricing_agent_simulation(product_sku, max_capacity=500, update_interval_days=15, num_days=150):
    """
    Executes a complete evaluation simulation of the Stock/Pricing Agent on CPU (testing split remaining 40%).
    Compares the cumulative profits of the PPO Agent, a Static Baseline [1.0, 1.0], and a Perfect Oracle.
    Triggers dynamic online fine-tuning loops every N days.
    """
    stock_management_path = os.path.join(settings.BASE_DIR, 'StockManagement')
    if stock_management_path in sys.path:
        sys.path.remove(stock_management_path)
    sys.path.insert(0, stock_management_path)
    
    # Force reload of agent packages to avoid collision with BuyerAgent
    import sys as sys_module
    for mod in ['agent.ppo_agent', 'agent.actor_critic', 'agent']:
        if mod in sys_module.modules:
            del sys_module.modules[mod]
            
    from environment_pricing import PricingStockEnvironment
    from agent.ppo_agent import ParallelPPOAgent
    import glob

    # 1. Define paths
    excel_name = f"m5_foods_{product_sku}.xlsx"
    if product_sku == "911753":
        excel_name = "911753_151dias_com_real.xlsx"
    excel_path = os.path.join(stock_management_path, 'datasets', excel_name)
    if not os.path.exists(excel_path):
        excel_path = os.path.join(stock_management_path, 'datasets', 'm5_foods_3_080.xlsx')

    # 2. Environments
    env_test = PricingStockEnvironment(excel_path=excel_path, is_training=False, train_split=0.6, max_capacity=max_capacity)
    env_baseline = PricingStockEnvironment(excel_path=excel_path, is_training=False, train_split=0.6, max_capacity=max_capacity)
    env_oracle = PricingStockEnvironment(excel_path=excel_path, is_training=False, train_split=0.6, max_capacity=max_capacity)
    env_train = PricingStockEnvironment(excel_path=excel_path, is_training=True, train_split=0.6, max_capacity=max_capacity)

    # 3. Agent
    state_dim = 17
    action_dim = 2
    agent = ParallelPPOAgent(state_dim=state_dim, action_dim=action_dim, batch_size=ONLINE_BATCH_SIZE)
    agent.device = torch.device('cpu')
    agent.policy_actor.to('cpu')
    agent.policy_critic.to('cpu')
    agent.policy_old_actor.to('cpu')
    agent.policy_old_critic.to('cpu')

    # Load offline trained weights (glob search inside subdirectories)
    checkpoint_dir = os.path.join(stock_management_path, 'models')
    loaded = False
    for base_name in [product_sku, "3_080"]:
        sku_folder = os.path.join(checkpoint_dir, base_name)
        search_paths = []
        if os.path.isdir(sku_folder):
            search_paths.append(sku_folder)
        search_paths.append(checkpoint_dir)
        for s_path in search_paths:
            actor_files = glob.glob(os.path.join(s_path, "*_actor.pth"))
            if not actor_files:
                actor_files = glob.glob(os.path.join(s_path, "**", "*_actor.pth"), recursive=True)
            if actor_files:
                matching_files = [f for f in actor_files if base_name in os.path.basename(f)]
                if not matching_files:
                    matching_files = actor_files
                matching_files.sort(key=lambda f: ('ep20032' in f, 'seed42' in f, os.path.getmtime(f)), reverse=True)
                for best_file in matching_files:
                    checkpoint_path = best_file.replace('_actor.pth', '')
                    try:
                        agent.load(checkpoint_path)
                        loaded = True
                        break
                    except Exception:
                        pass
                if loaded: break
        if loaded: break

    # 4. Simulation loops
    state = env_test.reset()
    env_baseline.reset()
    env_oracle.reset()

    done = False
    dias_simulados = 0
    max_steps_to_run = min(env_test.max_steps, num_days)

    log_dias = []
    log_procura_real = []
    profits_agent = []
    profits_baseline = []
    profits_oracle = []

    actions_agent_price = []
    actions_agent_qty = []
    log_stock_final = []
    log_spoilage = []

    cum_profit_agent = 0.0
    cum_profit_baseline = 0.0
    cum_profit_oracle = 0.0

    current_15d_buffer = []
    update_days = []

    # Oracle daily search function (lookahead helper)
    def run_oracle_lookahead_local(env_o):
        ckpt = env_o.get_checkpoint()
        p_grid = np.linspace(0.5, 1.5, 11)
        q_grid = np.linspace(0.1, 1.0, 5)
        best_prof = -float('inf')
        best_act = [1.0, 1.0]
        for p in p_grid:
            for q in q_grid:
                env_o.load_checkpoint(ckpt)
                _, _, _, info = env_o.step([p, q])
                if info['profit'] > best_prof:
                    best_prof = info['profit']
                    best_act = [p, q]
        env_o.load_checkpoint(ckpt)
        return best_act

    # Fine-tuning step adapted for 2-D continuous actions
    def continual_training_step_pricing(ppo_agent, new_experiences, train_env):
        # Force low learning rates
        for param_group in ppo_agent.optimizer_actor.param_groups:
            param_group['lr'] = ONLINE_LR_ACTOR
        for param_group in ppo_agent.optimizer_critic.param_groups:
            param_group['lr'] = ONLINE_LR_CRITIC
        
        num_new = len(new_experiences)
        num_old = num_new * 4
        
        state_t = train_env.reset()
        dias = 0
        ppo_agent.policy_old_actor.eval()
        
        while dias < num_old:
            state_tensor = torch.FloatTensor(state_t).unsqueeze(0).to(ppo_agent.device)
            with torch.no_grad():
                action_mean, log_std = ppo_agent.policy_old_actor(state_tensor)
                dist = torch.distributions.Normal(action_mean, torch.exp(torch.clamp(log_std, -2.3, 1.5)))
                action_percent = dist.sample()
                action_logprob = dist.log_prob(action_percent).sum(dim=-1, keepdim=True)
                price_mult = 0.5 + 1.0 * torch.clamp(action_percent[:, 0], 0.0, 1.0).item()
                qty_pct = torch.clamp(action_percent[:, 1], 0.0, 1.0).item()
                
            next_state, reward, done_t, _ = train_env.step([price_mult, qty_pct])
            ppo_agent.buffer.states.append(state_tensor)
            ppo_agent.buffer.actions.append(action_percent)
            ppo_agent.buffer.logprobs.append(action_logprob)
            ppo_agent.buffer.rewards.append([reward])
            ppo_agent.buffer.is_terminals.append([done_t])
            
            state_t = next_state
            dias += 1
            if done_t:
                state_t = train_env.reset()
                
        # Inject logged online experiences
        for exp in new_experiences:
            ppo_agent.buffer.states.append(torch.FloatTensor(exp['state']).unsqueeze(0).to(ppo_agent.device))
            ppo_agent.buffer.actions.append(torch.FloatTensor(exp['action']).unsqueeze(0).to(ppo_agent.device))
            ppo_agent.buffer.logprobs.append(torch.FloatTensor(exp['logprob']).unsqueeze(0).to(ppo_agent.device))
            ppo_agent.buffer.rewards.append([exp['reward']])
            ppo_agent.buffer.is_terminals.append([exp['is_terminal']])
            
        ppo_agent.update()

    # Get baseline values for static baseline and oracle
    env_baseline.reset()
    done_base = False
    cum_base_spoilage = 0.0
    while not done_base and len(profits_baseline) < max_steps_to_run:
        _, _, done_base, info_base = env_baseline.step([1.0, 1.0])
        cum_base_spoilage += float(info_base['spoilage'])

    while not done and dias_simulados < max_steps_to_run:
        day = env_test.current_step

        # 1. Baseline Estática (already simulated, extract from records or run parallel)
        # We can just reset/advance manually:
        env_baseline.current_step = day
        # Get baseline info at step
        _, _, _, info_base = env_baseline.step([1.0, 1.0])
        cum_profit_baseline += info_base['profit']

        # 2. Oráculo Perfeito
        action_oracle = run_oracle_lookahead_local(env_oracle)
        _, _, _, info_oracle = env_oracle.step(action_oracle)
        cum_profit_oracle += info_oracle['profit']

        # 3. Agente PPO
        state_tensor = torch.FloatTensor(state).unsqueeze(0).to(agent.device)
        with torch.no_grad():
            action_mean_percent, log_std = agent.policy_old_actor(state_tensor)
            std_tensor = torch.exp(torch.clamp(log_std, min=-2.3, max=1.5))
            dist = torch.distributions.Normal(action_mean_percent, std_tensor)
            action_percent = dist.sample()
            action_logprob = dist.log_prob(action_percent).sum(dim=-1, keepdim=True)
            
            price_mult = 0.5 + 1.0 * torch.clamp(action_percent[:, 0], 0.0, 1.0).item()
            qty_pct = torch.clamp(action_percent[:, 1], 0.0, 1.0).item()

        next_state, reward, done_env, info = env_test.step([price_mult, qty_pct])
        done = done_env
        cum_profit_agent += info['profit']

        # Log experiences for online retraining
        current_15d_buffer.append({
            'state': state_tensor.squeeze(0).cpu().numpy(),
            'action': action_percent.squeeze(0).cpu().numpy(),
            'logprob': action_logprob.squeeze(0).cpu().numpy(),
            'reward': reward,
            'is_terminal': done
        })

        # Telemetry logs
        log_dias.append(day)
        log_procura_real.append(float(info['demand_expected']))
        profits_agent.append(float(cum_profit_agent))
        profits_baseline.append(float(cum_profit_baseline))
        profits_oracle.append(float(cum_profit_oracle))
        
        actions_agent_price.append(float(price_mult))
        actions_agent_qty.append(float(qty_pct))
        log_stock_final.append(float(info['final_stock']))
        log_spoilage.append(float(info['spoilage']))

        state = next_state
        dias_simulados += 1

        # Retraining cycle
        if dias_simulados % update_interval_days == 0 and not done:
            update_days.append(dias_simulados)
            continual_training_step_pricing(agent, current_15d_buffer, env_train)
            current_15d_buffer = []
            agent.policy_old_actor.eval()

    payload = {
        'dias': log_dias,
        'procura_real': log_procura_real,
        'lucros_agente': profits_agent,
        'lucros_baseline': profits_baseline,
        'lucros_oracle': profits_oracle,
        'acoes_agente_preco': actions_agent_price,
        'acoes_agente_exposicao': actions_agent_qty,
        'stock_final': log_stock_final,
        'apodrecimento': log_spoilage,
        'update_days': update_days,
        'kpis': {
            'lucro_final_agente': float(cum_profit_agent),
            'lucro_final_baseline': float(cum_profit_baseline),
            'lucro_final_oracle': float(cum_profit_oracle),
            'ganho_versus_baseline': float(((cum_profit_agent - cum_profit_baseline) / (abs(cum_profit_baseline) + 1e-8)) * 100),
            'total_descarte_kg': float(sum(log_spoilage)),
            'total_descarte_baseline': float(cum_base_spoilage),
            'total_procura_un': float(sum(log_procura_real)),
            'ciclos_treino_run': len(update_days)
        }
    }
    return payload
