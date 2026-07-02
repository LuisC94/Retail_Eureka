import os
import torch
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from environment_constrained import StockEnvironment
from agent.ppo_agent import ParallelPPOAgent

# --- CONFIGURAÇÃO ---
PRODUCT_SKU = "3_252" # Pode ser: "3_080", "3_090", "3_252", "3_586"
EXCEL_PATH = rf"datasets\m5_foods_{PRODUCT_SKU}.xlsx"
MAX_CAPACITY = 500 # Usa a capacidade máxima otimizada
UPDATE_INTERVAL_DAYS = 15

# Melhores valores de Min-Max (s, S) estabelecidos em conversas anteriores para cada SKU
MIN_MAX_CONFIGS = {
    "3_080": {"s": 24, "S": 60},
    "3_090": {"s": 100, "S": 250},
    "3_252": {"s": 10, "S": 70}, # Alterado para s=10, S=70 para igualar ao comparativo (anteriormente s=35, S=130 no orquestrador)
    "3_586": {"s": 100, "S": 250},
    "911753": {"s": 35, "S": 130}
}

# Hyperparams de Fine-Tuning (Baixos para não destruir o treino de 35k episódios)
ONLINE_LR_ACTOR = 1e-5
ONLINE_LR_CRITIC = 5e-5
ONLINE_BATCH_SIZE = 32

# Modelo base inicial correspondente ao SKU
INITIAL_MODEL_PATH = rf"modelos_producao_constrained\{PRODUCT_SKU}\ppo_constrained_iter313"

def continual_training_step(agent, new_experiences, env_train, max_action_val):
    """
    Executa 1 ciclo de atualização do modelo (Fine-Tuning) 
    usando um Buffer Misto (80% Antigo / 20% Novo) para evitar Catastrophic Forgetting.
    """
    print(f"\n[FINE-TUNING] A iniciar atualização com {len(new_experiences)} dias novos...")
    
    # 1. Forçar as Learning Rates para modo "Fine-Tuning"
    for param_group in agent.optimizer_actor.param_groups:
        param_group['lr'] = ONLINE_LR_ACTOR
    for param_group in agent.optimizer_critic.param_groups:
        param_group['lr'] = ONLINE_LR_CRITIC
        
    num_new_days = len(new_experiences)
    num_old_needed = num_new_days * 4 # Proporção 80/20
    
    # 2. Gerar dados antigos usando a zona de Treino (primeiros 60% dos dados)
    state = env_train.reset()
    dias_gerados = 0
    
    agent.policy_old_actor.eval() # Modo avaliação para gerar trajetórias estáveis do passado
    
    while dias_gerados < num_old_needed:
        state_tensor = torch.FloatTensor(state).unsqueeze(0).to(agent.device)
        with torch.no_grad():
            action_mean, log_std = agent.policy_old_actor(state_tensor)
            dist = torch.distributions.Normal(action_mean, torch.exp(torch.clamp(log_std, -2.3, 1.5)))
            action_percent = dist.sample()
            action_logprob = dist.log_prob(action_percent)
            
            physical_action = torch.round(torch.clamp(action_percent * max_action_val, 0, max_action_val)).cpu().numpy().flatten()[0]
            
        next_state, reward, done, _ = env_train.step(physical_action)
        
        # Guardar a experiência antiga no buffer do Agente
        agent.buffer.states.append(state_tensor) 
        agent.buffer.actions.append(action_percent) 
        agent.buffer.logprobs.append(action_logprob) 
        agent.buffer.rewards.append([reward]) 
        agent.buffer.is_terminals.append([done]) 
        
        state = next_state
        dias_gerados += 1
        
        if done:
            state = env_train.reset()
            
    # 3. Injetar os dados novos reais (do mercado) no buffer do Agente
    for exp in new_experiences:
        agent.buffer.states.append(torch.FloatTensor(exp['state']).unsqueeze(0).to(agent.device)) 
        agent.buffer.actions.append(torch.FloatTensor(exp['action']).unsqueeze(0).to(agent.device)) 
        agent.buffer.logprobs.append(torch.FloatTensor(exp['logprob']).unsqueeze(0).to(agent.device)) 
        agent.buffer.rewards.append([exp['reward']]) 
        agent.buffer.is_terminals.append([exp['is_terminal']]) 
        
    # 4. O COMANDO MÁGICO - A rede atualiza os seus pesos com o misto de experiências
    agent.update()
    print(f"[FINE-TUNING CONCLUÍDO] O agente reajustou a sua política com sucesso ao novo mercado!\n")
    

def production_loop():
    print("======================================================")
    print(" INICIANDO ORQUESTRADOR DE PRODUÇÃO (CICLOS 15 DIAS)  ")
    print("======================================================")
    
    # 1. Inicializar Ambientes
    print("[INIT] A preparar Ambiente de Teste (Inferência para o futuro)...")
    env_test = StockEnvironment(excel_path=EXCEL_PATH, is_training=False, train_split=0.6, max_capacity=MAX_CAPACITY)
    
    # Obter dinamicamente o limite de ação do agente constrangido
    # Obter os parâmetros Min-Max (s, S) otimizados para o produto atual
    config_minmax = MIN_MAX_CONFIGS.get(PRODUCT_SKU, {"s": 100, "S": 250})
    s_min = config_minmax["s"]
    S_max = config_minmax["S"]
    print(f"[OK] Configuração Min-Max baseline para {PRODUCT_SKU}: s={s_min}, S={S_max}")
    
    env_minmax = StockEnvironment(excel_path=EXCEL_PATH, is_training=False, train_split=0.6, max_capacity=MAX_CAPACITY)
    env_minmax.max_order_limit = float('inf') # Sem limite de encomenda para Min-Max
    env_oracle = StockEnvironment(excel_path=EXCEL_PATH, is_training=False, train_split=0.6, max_capacity=MAX_CAPACITY)
    env_oracle.max_order_limit = float('inf') # Sem limite de encomenda para o Oráculo
    
    print("[INIT] A preparar Ambiente de Treino (Para resgatar memórias antigas)...")
    env_train = StockEnvironment(excel_path=EXCEL_PATH, is_training=True, train_split=0.6, max_capacity=MAX_CAPACITY)
    
    state_dim = 17
    action_dim = 1
    
    # Obter dinamicamente o limite de ação do agente constrangido
    max_order_limit = env_test.max_order_limit
    print(f"[OK] Limite Máximo de Encomenda Diária (Action Cap): {max_order_limit} un")
    
    # Instanciar o Agente com o limite correto de ação
    agent = ParallelPPOAgent(state_dim=state_dim, action_dim=action_dim, max_action=max_order_limit, batch_size=ONLINE_BATCH_SIZE)
    
    # 2. Carregar o Modelo Inicial (o de 35.000 episódios)
    try:
        agent.load(INITIAL_MODEL_PATH)
        print(f"[OK] Modelo Inicial carregado: {INITIAL_MODEL_PATH}")
    except Exception as e:
        print(f"[ERRO CRÍTICO] Falha ao carregar {INITIAL_MODEL_PATH}. Verifica se o nome está correto. Erro: {e}")
        return

    # 2.1 Carregar o estado do Z-Score do Ambiente (shared_stats['econ'])
    econ_stat_path = INITIAL_MODEL_PATH + '_econ_stat.pth'
    if os.path.exists(econ_stat_path):
        econ_state = torch.load(econ_stat_path, weights_only=False)
        print(f"[OK] Estatísticas de Recompensa do Ambiente carregadas: {econ_stat_path}")
        for env in [env_test, env_minmax, env_oracle, env_train]:
            env.stat_profit.n = econ_state['n']
            env.stat_profit.mean = econ_state['mean']
            env.stat_profit.S = econ_state['S']
    else:
        print(f"[AVISO] Ficheiro {econ_stat_path} não encontrado. Z-Score começará a zeros.")

    # Garantir que o ator está em modo de avaliação e no dispositivo correto
    agent.policy_old_actor.to(agent.device)
    agent.policy_old_actor.eval()
    
    state = env_test.reset()
    state_minmax = env_minmax.reset()
    state_oracle = env_oracle.reset()
    
    done = False
    
    # Variáveis de Log
    rewards_agent = []
    profits_agent = []
    actions_agent = []
    vendas_reais = []
    
    profits_minmax = []
    profits_oracle = []
    
    update_days = [] # Guarda os dias exatos em que o modelo foi atualizado para marcar no gráfico
    
    cum_profit_agent = 0
    cum_profit_minmax = 0
    cum_profit_oracle = 0
    
    dias_simulados = 0
    
    # Listas detalhadas para gravação em Excel e marcadores Plotly
    log_dias = []
    log_procura_real = []
    log_preco_venda = []
    
    log_acoes_agente = []
    log_acoes_minmax = []
    log_acoes_oracle = []
    
    log_stock_inicial_agente = []
    log_stock_final_agente = []
    log_vendas_agente = []
    log_vendas_perdidas_agente = []
    log_apodrecimento_agente = []
    log_excesso_agente = []
    
    log_lucro_diario_agente = []
    log_lucro_acumulado_agente = []
    log_lucro_acumulado_minmax = []
    log_lucro_acumulado_oracle = []
    
    flag_stockout = []
    flag_clientes_perdidos = []
    flag_excesso_armazem = []
    flag_apodrecimento = []
    
    # Buffer temporário para armazenar a experiência a cada 15 dias
    current_15d_buffer = []

    print("\n[PRODUÇÃO] A iniciar simulação contínua do mercado livre...\n")
    
    while not done:
        day = env_test.current_step
        
        # --- FASE 1.1: MIN-MAX BASELINE ---
        stock_hoje_minmax = sum(env_minmax.stock_profile) + env_minmax.in_transit.get(env_minmax.current_step, 0)
        vendas_hoje_minmax = env_minmax.data.iloc[env_minmax.current_step]['real_value']
        # O stock que vamos ter garantido amanhã de manhã (Stock Hoje - Vendas Hoje + Camiões a chegar amanhã)
        stock_amanha_minmax = max(0, stock_hoje_minmax - vendas_hoje_minmax) + env_minmax.in_transit.get(env_minmax.current_step + 1, 0)
        
        action_minmax = 0
        if stock_amanha_minmax <= s_min:
            action_minmax = max(0, S_max - stock_amanha_minmax)
            action_minmax = min(action_minmax, MAX_CAPACITY)
        _, _, _, info_minmax = env_minmax.step(action_minmax)
        cum_profit_minmax += info_minmax['profit']
        profits_minmax.append(cum_profit_minmax)

        # --- FASE 1.2: ORÁCULO PERFEITO (GOD MODE) ---
        stock_hoje_oracle = sum(env_oracle.stock_profile) + env_oracle.in_transit.get(env_oracle.current_step, 0)
        vendas_hoje_oracle = env_oracle.data.iloc[env_oracle.current_step]['real_value']
        stock_amanha_oracle = max(0, stock_hoje_oracle - vendas_hoje_oracle) + env_oracle.in_transit.get(env_oracle.current_step + 1, 0)
        
        action_oracle = 0
        demand_tomorrow = env_oracle.data.iloc[env_oracle.current_step + 1]['real_value'] if env_oracle.current_step + 1 <= env_oracle.max_steps else 0
        
        if stock_amanha_oracle < demand_tomorrow:
            future_demand = 0
            for i in range(1, 5): # T+1 a T+4
                idx = env_oracle.current_step + i
                if idx <= env_oracle.max_steps:
                    future_demand += env_oracle.data.iloc[idx]['real_value']
            
            action_oracle = max(0, future_demand - stock_amanha_oracle)
            action_oracle = min(action_oracle, MAX_CAPACITY)
            
        _, _, _, info_oracle = env_oracle.step(action_oracle)
        cum_profit_oracle += info_oracle['profit']
        profits_oracle.append(cum_profit_oracle)

        # --- FASE 1.3: INFERÊNCIA DIÁRIA (O GERENTE DECIDE) ---
        state_tensor = torch.FloatTensor(state).unsqueeze(0).to(agent.device)
        with torch.no_grad():
            action_mean, log_std = agent.policy_old_actor(state_tensor)
            dist = torch.distributions.Normal(action_mean, torch.exp(torch.clamp(log_std, -2.3, 1.5)))
            action_percent = dist.sample()
            action_logprob = dist.log_prob(action_percent)
            physical_action = torch.round(torch.clamp(action_percent * max_order_limit, 0, max_order_limit)).cpu().numpy().flatten()[0]

        stock_inicial_hoje = sum(env_test.stock_profile)

        next_state, reward, done_env, info = env_test.step(physical_action)
        done = done_env
        
        print(f"[Dia {day:03d}] Ações -> Agente: {physical_action:03.0f} | MinMax: {action_minmax:03.0f} | Oráculo: {action_oracle:03.0f} || Lucros Diários -> Agente: {info['profit']:.2f}€ | Oráculo: {info_oracle['profit']:.2f}€")
        
        # O gerente anota o que aconteceu neste dia para entregar ao analista mais tarde
        current_15d_buffer.append({
            'state': state_tensor.squeeze(0).cpu().numpy(),
            'action': action_percent.squeeze(0).cpu().numpy(),
            'logprob': action_logprob.squeeze(0).cpu().numpy(),
            'reward': reward,
            'is_terminal': done
        })
        
        # Logs Globais para Gráficos
        rewards_agent.append(reward)
        cum_profit_agent += info['profit']
        profits_agent.append(cum_profit_agent)
        actions_agent.append(physical_action)
        vendas_reais.append(env_test.data.iloc[day]['real_value'])
        
        # Logs detalhados para Excel e Plotly
        stock_final_hoje = sum(env_test.stock_profile)
        sales = info['sales']
        real_demand = info['real_demand']
        spoilage = info['spoilage']
        lost_sales = max(0, real_demand - sales)
        overcapacity_waste = max(0, info['overflow_waste'] - spoilage)
        
        log_dias.append(day)
        log_procura_real.append(real_demand)
        log_preco_venda.append(info['price_today'])
        
        log_acoes_agente.append(physical_action)
        log_acoes_minmax.append(action_minmax)
        log_acoes_oracle.append(action_oracle)
        
        log_stock_inicial_agente.append(stock_inicial_hoje)
        log_stock_final_agente.append(stock_final_hoje)
        log_vendas_agente.append(sales)
        log_vendas_perdidas_agente.append(lost_sales)
        log_apodrecimento_agente.append(spoilage)
        log_excesso_agente.append(overcapacity_waste)
        
        log_lucro_diario_agente.append(info['profit'])
        log_lucro_acumulado_agente.append(cum_profit_agent)
        log_lucro_acumulado_minmax.append(cum_profit_minmax)
        log_lucro_acumulado_oracle.append(cum_profit_oracle)
        
        # Flags de Penalidades
        flag_stockout.append(1 if stock_final_hoje <= 0 else 0)
        flag_clientes_perdidos.append(1 if lost_sales > 0 else 0)
        flag_excesso_armazem.append(1 if overcapacity_waste > 0 else 0)
        flag_apodrecimento.append(1 if spoilage > 0 else 0)
        
        state = next_state
        dias_simulados += 1
        
        # --- FASE 2: TRIGGER DE ATUALIZAÇÃO (O ANALISTA TRABALHA) ---
        if dias_simulados % UPDATE_INTERVAL_DAYS == 0 and not done:
            update_days.append(dias_simulados)
            
            # Passa a prancheta de 15 dias para o Analista (Treino Contínuo)
            continual_training_step(agent, current_15d_buffer, env_train, max_order_limit)
            
            # Deita fora as anotações antigas para começar o novo ciclo de 15 dias do zero
            current_15d_buffer = []
            
            # Garante que o ator volta a modo de inferência rigorosa
            agent.policy_old_actor.eval()

    print("\n======================================================")
    print(f"[FIM DA SIMULAÇÃO] {dias_simulados} dias concluídos com {len(update_days)} atualizações de modelo.")
    print(f"Lucro Acumulado Final AGENTE:  {cum_profit_agent:.2f}€")
    print(f"Lucro Acumulado Final MINMAX:  {cum_profit_minmax:.2f}€")
    print(f"Lucro Acumulado Final ORÁCULO: {cum_profit_oracle:.2f}€")
    print("======================================================")
    
    # 5. Salvar o modelo online final e o novo estado dos scalers
    try:
        final_model_path = INITIAL_MODEL_PATH + "_online_final"
        agent.save(final_model_path)
        
        final_econ_state = {
            'n': env_test.stat_profit.n,
            'mean': env_test.stat_profit.mean,
            'S': env_test.stat_profit.S
        }
        torch.save(final_econ_state, final_model_path + '_econ_stat.pth')
        print(f"[OK] Modelo Online Final e Estatísticas guardados em: {final_model_path}")
    except Exception as e:
        print(f"[AVISO] Não foi possível salvar o modelo online final: {e}")
    
    # --- GERAÇÃO DO GRÁFICO PROFISSIONAL ---
    print("\nA desenhar o gráfico da evolução do treino contínuo...")
    os.makedirs("Dados", exist_ok=True)
    
    fig, ax1 = plt.subplots(figsize=(16, 7))

    # Eixo Esquerdo: Rewards
    color = 'tab:blue'
    ax1.set_xlabel('Dias de Operação', fontsize=12)
    ax1.set_ylabel('Reward Diária (Z-Score)', color=color, fontsize=12)
    ax1.plot(rewards_agent, color=color, alpha=0.6, label='Reward Diária')
    ax1.tick_params(axis='y', labelcolor=color)

    # Eixo Direito: Lucros Acumulados
    ax2 = ax1.twinx()
    
    ax2.set_ylabel('Lucro Acumulado (€)', color='black', fontsize=12)
    ax2.plot(profits_agent, color='tab:green', linewidth=2.5, label=f'Lucro PPO Agente ({cum_profit_agent:.0f}€)')
    ax2.plot(profits_minmax, color='black', linewidth=1.5, linestyle=':', label=f'Lucro Min-Max ({cum_profit_minmax:.0f}€)')
    ax2.plot(profits_oracle, color='goldenrod', linewidth=2.0, linestyle='--', label=f'Lucro Oráculo Perfeito ({cum_profit_oracle:.0f}€)')
    
    ax2.tick_params(axis='y', labelcolor='black')

    # Adicionar as Linhas Verticais de Atualização do Modelo (De 15 em 15 dias)
    for idx, update_day in enumerate(update_days):
        label = 'Fine-Tuning (Update)' if idx == 0 else "" # Apenas mete legenda no primeiro para não poluir
        ax1.axvline(x=update_day, color='red', linestyle='--', alpha=0.5, label=label)
        
        # A cada X atualizações (para não colar muito texto), escreve a versão do modelo
        if idx % 2 == 0:
            ax1.text(update_day, max(rewards_agent)*0.8, f"v{idx+1}", rotation=90, color='red', alpha=0.7, fontsize=8)

    plt.title("Continual Learning na Produção: Ajuste Automático do Agente a Cada 15 Dias", fontsize=14, fontweight='bold')
    fig.tight_layout()
    
    # Juntar legendas dos dois eixos
    lines_1, labels_1 = ax1.get_legend_handles_labels()
    lines_2, labels_2 = ax2.get_legend_handles_labels()
    ax1.legend(lines_1 + lines_2, labels_1 + labels_2, loc='upper left')
    
    plt.grid(True, alpha=0.3)
    
    save_path = r"Dados\producao_ciclos_15dias.png"
    plt.savefig(save_path, dpi=300)
    plt.close()
    
    print(f"[OK] Gráfico espetacular guardado em: {save_path}")
    
    # --- EXTRAÇÃO DINÂMICA E CAMINHOS ---
    nome_excel = os.path.basename(EXCEL_PATH)
    os.makedirs("Resultados", exist_ok=True)
    excel_output_path = os.path.join("Resultados", nome_excel)
    html_output_path = os.path.join("Resultados", "Relatorio_Vendas_vs_Acoes.html")
    
    # --- GRAVAÇÃO DOS DADOS EM EXCEL ---
    print(f"\nA gravar os dados completos da simulação no Excel...")
    try:
        df_excel = pd.DataFrame({
            'Dia': log_dias,
            'Procura_Real': log_procura_real,
            'Preco_Venda_Dia': log_preco_venda,
            'Acao_Agente_PPO': log_acoes_agente,
            'Acao_MinMax': log_acoes_minmax,
            'Acao_Oraculo': log_acoes_oracle,
            'Stock_Inicial_Agente': log_stock_inicial_agente,
            'Stock_Final_Agente': log_stock_final_agente,
            'Vendas_Agente': log_vendas_agente,
            'Vendas_Perdidas_Agente': log_vendas_perdidas_agente,
            'Apodrecimento_Agente': log_apodrecimento_agente,
            'Excesso_Armazem_Agente': log_excesso_agente,
            'Lucro_Diario_Agente': log_lucro_diario_agente,
            'Lucro_Acumulado_Agente': log_lucro_acumulado_agente,
            'Lucro_Acumulado_MinMax': log_lucro_acumulado_minmax,
            'Lucro_Acumulado_Oraculo': log_lucro_acumulado_oracle,
            'Flag_Stockout': flag_stockout,
            'Flag_Clientes_Perdidos': flag_clientes_perdidos,
            'Flag_Excesso_Armazem': flag_excesso_armazem,
            'Flag_Apodrecimento': flag_apodrecimento
        })
        df_excel.to_excel(excel_output_path, index=False)
        print(f"[OK] Ficheiro Excel guardado com sucesso em: {excel_output_path}")
    except Exception as e:
        print(f"[AVISO] Não foi possível criar o ficheiro Excel: {e}")
        
    # --- GERAÇÃO DO DASHBOARD PLOTLY DINÂMICO (INTERATIVO EM HTML) ---
    print("\nA gerar o dashboard interativo Plotly (HTML)...")
    try:
        import plotly.graph_objects as go
        import webbrowser
        
        fig_plotly = go.Figure()
        
        # 1. Adicionar a curva de Vendas Reais (Procura)
        fig_plotly.add_trace(go.Scatter(
            x=log_dias,
            y=log_procura_real,
            mode='lines',
            name='Vendas Reais (Procura)',
            line=dict(color='#00d2ff', width=2),
            hovertemplate='Dia %{x}<br>Vendas: %{y:.1f} un<extra></extra>'
        ))
        
        # 2. Adicionar as Ações de Encomenda do Actor (Agente PPO)
        fig_plotly.add_trace(go.Scatter(
            x=log_dias,
            y=log_acoes_agente,
            mode='lines+markers',
            name='Encomendas do Actor PPO (Ação)',
            line=dict(color='#ff9f43', width=1.5),
            marker=dict(size=4),
            hovertemplate='Dia %{x}<br>Encomenda PPO: %{y:.1f} un<extra></extra>'
        ))
        
        # 3. Adicionar as Ações de Encomenda do Min-Max
        fig_plotly.add_trace(go.Scatter(
            x=log_dias,
            y=log_acoes_minmax,
            mode='lines+markers',
            name='Encomendas do Min-Max (Ação)',
            line=dict(color='#888888', width=1.2, dash='dot'),
            marker=dict(size=4, color='#888888'),
            hovertemplate='Dia %{x}<br>Encomenda Min-Max: %{y:.1f} un<extra></extra>'
        ))
        
        # 4. Marcadores de Penalidade (Flags overlay)
        dias_stockout = [d for d in log_dias if flag_stockout[d] == 1]
        acoes_stockout = [log_acoes_agente[d] for d in dias_stockout]
        
        dias_clientes_perdidos = [d for d in log_dias if flag_clientes_perdidos[d] == 1]
        acoes_clientes_perdidos = [log_acoes_agente[d] for d in dias_clientes_perdidos]
        qtd_perdida = [log_vendas_perdidas_agente[d] for d in dias_clientes_perdidos]
        
        dias_excesso = [d for d in log_dias if flag_excesso_armazem[d] == 1]
        acoes_excesso = [log_acoes_agente[d] for d in dias_excesso]
        qtd_excesso = [log_excesso_agente[d] for d in dias_excesso]
        
        dias_apodrecimento = [d for d in log_dias if flag_apodrecimento[d] == 1]
        acoes_apodrecimento = [log_acoes_agente[d] for d in dias_apodrecimento]
        qtd_apodrecimento = [log_apodrecimento_agente[d] for d in dias_apodrecimento]
        
        # Stockout / Stock Zero (Marcador Branco)
        if dias_stockout:
            fig_plotly.add_trace(go.Scatter(
                x=dias_stockout,
                y=acoes_stockout,
                mode='markers',
                name='Penalidade: Stock Zero (Vazio)',
                marker=dict(color='#ffffff', size=8, symbol='circle', line=dict(color='#000000', width=1.5)),
                hovertemplate='Dia %{x}<br>Armazém Vazio! Encomenda PPO: %{y} un<extra></extra>'
            ))
            
        # Clientes Perdidos (Marcador Roxo 'X')
        if dias_clientes_perdidos:
            fig_plotly.add_trace(go.Scatter(
                x=dias_clientes_perdidos,
                y=acoes_clientes_perdidos,
                mode='markers',
                name='Penalidade: Clientes Perdidos',
                marker=dict(color='#a55eea', size=8, symbol='x'),
                customdata=qtd_perdida,
                hovertemplate='Dia %{x}<br>Clientes Perdidos: %{customdata:.1f} un<br>Encomenda PPO: %{y} un<extra></extra>'
            ))
            
        # Excesso de Armazém (Marcador Vermelho 'Triangle-Up')
        if dias_excesso:
            fig_plotly.add_trace(go.Scatter(
                x=dias_excesso,
                y=acoes_excesso,
                mode='markers',
                name='Penalidade: Excesso de Armazém (>500 un)',
                marker=dict(color='#ff4d4d', size=8, symbol='triangle-up'),
                customdata=qtd_excesso,
                hovertemplate='Dia %{x}<br>Descarte por Excesso: %{customdata:.1f} un<br>Encomenda PPO: %{y} un<extra></extra>'
            ))
            
        # Apodrecimento por Validade (Marcador Amarelo 'Diamond')
        if dias_apodrecimento:
            fig_plotly.add_trace(go.Scatter(
                x=dias_apodrecimento,
                y=acoes_apodrecimento,
                mode='markers',
                name='Penalidade: Apodrecimento (Validade)',
                marker=dict(color='#fed330', size=8, symbol='diamond'),
                customdata=qtd_apodrecimento,
                hovertemplate='Dia %{x}<br>Apodrecimento: %{customdata:.1f} un<br>Encomenda PPO: %{y} un<extra></extra>'
            ))
        
        # Estética do Layout Premium
        fig_plotly.update_layout(
            title={
                'text': f"Simulação em Produção: Vendas Reais vs. Ações de Encomenda<br>"
                        f"<span style='font-size: 14px; color: #a5a5b5;'>"
                        f"Lucro Final: Agente = <b>{cum_profit_agent:,.2f}€</b> | "
                        f"MinMax = <b>{cum_profit_minmax:,.2f}€</b> | "
                        f"Oráculo = <b>{cum_profit_oracle:,.2f}€</b>"
                        f"</span>",
                'y': 0.95,
                'x': 0.5,
                'xanchor': 'center',
                'yanchor': 'top',
                'font': {'size': 20, 'family': 'Segoe UI', 'color': '#ffffff'}
            },
            xaxis_title="Dias de Operação",
            yaxis_title="Quantidade (Unidades)",
            paper_bgcolor="#111116",
            plot_bgcolor="#111116",
            font=dict(color="#ffffff", family="Segoe UI"),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="center",
                x=0.5,
                font=dict(size=12)
            ),
            hovermode="x unified",
            margin=dict(t=120, b=50, l=50, r=50)
        )
        
        # Configurar as grelhas para o tema escuro
        fig_plotly.update_xaxes(showgrid=True, gridwidth=1, gridcolor='#22222b', linecolor='#33333f')
        fig_plotly.update_yaxes(showgrid=True, gridwidth=1, gridcolor='#22222b', linecolor='#33333f')
        
        # Adicionar linhas de trigger de fine-tuning (linhas vermelhas verticais interativas)
        for idx, update_day in enumerate(update_days):
            fig_plotly.add_vline(
                x=update_day, 
                line_width=1, 
                line_dash="dash", 
                line_color="#ff4757",
                annotation_text=f"Update v{idx+1}",
                annotation_position="top left",
                annotation_font=dict(size=9, color="#ff4757")
            )
            
        # Gravar na pasta Resultados ao lado do Excel
        fig_plotly.write_html(html_output_path)
        print(f"[OK] Dashboard Plotly Dinâmico guardado com sucesso em: {html_output_path}")
        
        # Abrir automaticamente no browser padrão
        webbrowser.open(html_output_path)
    except Exception as e:
        print(f"[AVISO] Não foi possível criar o dashboard Plotly interativo: {e}")

if __name__ == "__main__":
    production_loop()
