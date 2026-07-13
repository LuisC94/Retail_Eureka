import io
import os
import math
import datetime
import joblib
import torch
import numpy as np
import pandas as pd
from django.utils import timezone
from django.db import transaction
from django.db.models import Sum, Avg, Max
from django.contrib.auth.models import User
from dashboard.models import ProductSubFamily, HistoricalSalesData, DemandForecast, MarketplaceOrder, ConsolidatedStock, Warehouse, TrainedModel
from sklearn.neural_network import MLPRegressor
import sys
import os

# Adicionar o diretório BuyerAgent ao path para resolver importações internas do agente de reforço
buyer_agent_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'BuyerAgent')
if buyer_agent_dir not in sys.path:
    sys.path.insert(0, buyer_agent_dir)

from BuyerAgent.agent.ppo_agent import ParallelPPOAgent

def get_user_stock_profile(user, subfamily):
    """
    Distribui o stock consolidado do comprador nas categorias G0-G3 de shelf-life
    com base nas datas de expiração das encomendas delivered.
    G0: RSL >= 4 dias
    G1: RSL == 3 dias
    G2: RSL == 2 dias
    G3: RSL == 1 dia
    """
    stock_profile = [0.0, 0.0, 0.0, 0.0]
    today = timezone.now().date()
    
    active_orders = MarketplaceOrder.objects.filter(
        requester=user,
        culture=subfamily,
        status='APPROVED',
        transport_status='DELIVERED'
    ).exclude(harvest_origin__isnull=True)
    
    for order in active_orders:
        exp_date = order.harvest_origin.expiration_date
        if exp_date:
            rsl = (exp_date - today).days
            qty = float(order.quantity_kg)
            if rsl >= 4:
                stock_profile[0] += qty
            elif rsl == 3:
                stock_profile[1] += qty
            elif rsl == 2:
                stock_profile[2] += qty
            elif rsl == 1:
                stock_profile[3] += qty

    # Forçar o total a bater certo com o stock consolidado real na base de dados
    total_cons = float(ConsolidatedStock.objects.filter(owner=user, culture=subfamily).aggregate(total=Sum('quantity'))['total'] or 0.0)
    total_profile = sum(stock_profile)
    
    if total_profile > 0 and total_cons != total_profile:
        ratio = total_cons / total_profile
        stock_profile = [x * ratio for x in stock_profile]
    elif total_cons > 0 and total_profile == 0:
        # Tentar calcular RSL dinâmico usando o LC Agent
        default_rsl = None
        stock_item = ConsolidatedStock.objects.filter(owner=user, culture=subfamily).first()
        if stock_item:
            try:
                from dashboard.models import Warehouse, WarehouseSensorReading
                from dashboard.services.lc_service import calculate_quality_decay_curve
                clean_location = stock_item.warehouse_location.split(' (WH:')[0].strip() if stock_item.warehouse_location and ' (WH:' in stock_item.warehouse_location else stock_item.warehouse_location
                warehouse = Warehouse.objects.filter(owner=user, location=clean_location).first()
                sensor_readings = []
                if warehouse:
                    today_date = datetime.date.today()
                    future_readings = WarehouseSensorReading.objects.filter(warehouse=warehouse, date__gte=today_date).order_by('date')
                    if future_readings.exists():
                        sensor_readings = list(future_readings[:120])
                    else:
                        past_readings = WarehouseSensorReading.objects.filter(warehouse=warehouse).order_by('-date')[:30]
                        sensor_readings = sorted(list(past_readings), key=lambda r: r.date)
                _, predicted_rsl = calculate_quality_decay_curve(
                    culture_name=f"{subfamily.name} ({subfamily.fruit_type})",
                    initial_score=stock_item.avg_quality_score or 10.0,
                    sensor_readings=sensor_readings
                )
                if predicted_rsl is not None:
                    default_rsl = predicted_rsl
            except Exception:
                pass
                
        # Se falhar ou for nulo, usa o tempo de vida padrão estático
        if default_rsl is None:
            default_rsl = 4
            name_lower = subfamily.name.lower()
            if "morango" in name_lower or "strawberry" in name_lower:
                default_rsl = 3
            elif any(x in name_lower for x in ["maca", "maçã", "gala", "fuji", "reineta", "smith", "delicious"]):
                default_rsl = 15
            elif any(x in name_lower for x in ["kiwi", "hayward", "green", "gold", "red"]):
                default_rsl = 10
            elif "uva" in name_lower or "grape" in name_lower:
                default_rsl = 6
            
        if default_rsl >= 4:
            stock_profile[0] = total_cons
        elif default_rsl == 3:
            stock_profile[1] = total_cons
        elif default_rsl == 2:
            stock_profile[2] = total_cons
        elif default_rsl == 1:
            stock_profile[3] = total_cons
        
    return stock_profile

def get_buyer_agent_state(user, subfamily, max_capacity=500):
    """
    Reconstrói o vetor de estado de 17 variáveis requisitado pelo Buyer Agent (PPO).
    """
    today = timezone.now().date()
    stock_profile = get_user_stock_profile(user, subfamily)
    
    # Encomendas em trânsito
    total_in_transit = float(MarketplaceOrder.objects.filter(
        requester=user,
        culture=subfamily,
        status='APPROVED'
    ).exclude(transport_status='DELIVERED').aggregate(total=Sum('quantity_kg'))['total'] or 0.0)
    
    # Previsões
    pred_today_obj = DemandForecast.objects.filter(owner=user, culture=subfamily, date=today).first()
    prediction_today = float(pred_today_obj.predicted_quantity_kg) if pred_today_obj else 10.0
    
    tomorrow = today + datetime.timedelta(days=1)
    pred_tomorrow_obj = DemandForecast.objects.filter(owner=user, culture=subfamily, date=tomorrow).first()
    prediction_tomorrow = float(pred_tomorrow_obj.predicted_quantity_kg) if pred_tomorrow_obj else prediction_today
    
    # Histórico de vendas reais
    yesterday = today - datetime.timedelta(days=1)
    t_minus_2 = today - datetime.timedelta(days=2)
    
    sale_yesterday = HistoricalSalesData.objects.filter(owner=user, culture=subfamily, date=yesterday).first()
    real_t_minus_1 = float(sale_yesterday.sales_quantity_kg) if sale_yesterday else prediction_today
    
    sale_t_minus_2 = HistoricalSalesData.objects.filter(owner=user, culture=subfamily, date=t_minus_2).first()
    real_t_minus_2 = float(sale_t_minus_2.sales_quantity_kg) if sale_t_minus_2 else real_t_minus_1
    
    # Preço do Marketplace
    active_sell_orders = MarketplaceOrder.objects.filter(culture=subfamily, order_type='SELL', status='OPEN')
    avg_price = active_sell_orders.aggregate(avg=Avg('price_per_kg'))['avg']
    if avg_price is not None:
        price_today = float(avg_price)
    else:
        # Fallback para o preço pré-definido da cultura
        default_price = 2.0
        name_lower = subfamily.name.lower()
        if "morango" in name_lower or "strawberry" in name_lower:
            default_price = 4.5
        elif any(x in name_lower for x in ["maca", "maçã", "gala", "fuji", "reineta", "smith", "delicious"]):
            default_price = 1.8
        elif any(x in name_lower for x in ["kiwi", "hayward", "green", "gold", "red"]):
            default_price = 3.2
        elif "uva" in name_lower or "grape" in name_lower:
            default_price = 2.5
        price_today = default_price
        
    preco_relativo_safe = 0.0 # Sem variância no live
    
    # Componentes de Calendário
    day_of_week = today.weekday() + 1
    month = today.month
    
    sin_day = math.sin(2 * math.pi * day_of_week / 7.0)
    cos_day = math.cos(2 * math.pi * day_of_week / 7.0)
    sin_month = math.sin(2 * math.pi * month / 12.0)
    cos_month = math.cos(2 * math.pi * month / 12.0)
    
    # Cobertura e Urgência
    stock_total = sum(stock_profile)
    cobertura_dias = stock_total / (prediction_today + 1e-8)
    cobertura_norm = np.clip(cobertura_dias, 0, 7) / 7.0
    urgencia_norm = stock_profile[3] / (stock_total + 1e-8)
    
    # Erro de previsão
    pred_yesterday_obj = DemandForecast.objects.filter(owner=user, culture=subfamily, date=yesterday).first()
    prediction_yesterday = float(pred_yesterday_obj.predicted_quantity_kg) if pred_yesterday_obj else prediction_today
    erro_previsao = (real_t_minus_1 - prediction_yesterday) / (prediction_yesterday + 1e-8)
    erro_norm = np.clip(erro_previsao, -1.0, 1.0)
    
    # 1. Escalar as primeiras 9 variáveis absolutass
    via1_absolutas = [
        stock_profile[0],
        stock_profile[1],
        stock_profile[2],
        stock_profile[3],
        total_in_transit,
        prediction_today,
        prediction_tomorrow,
        real_t_minus_1,
        real_t_minus_2
    ]
    
    # MinMax manual baseado no setup original:
    # Primeiras 5 divididas por max_capacity, restantes 4 divididas por 100.0
    scaled_via1 = []
    for idx, val in enumerate(via1_absolutas):
        max_val = float(max_capacity) if idx < 5 else 100.0
        scaled_via1.append(val / max_val)
        
    via2_bypass = [
        preco_relativo_safe,
        sin_day,
        cos_day,
        sin_month,
        cos_month,
        cobertura_norm,
        urgencia_norm,
        erro_norm
    ]
    
    final_state = np.concatenate([scaled_via1, via2_bypass])
    return final_state

def train_sales_forecaster(user, subfamily, df_data):
    """
    Treina a rede neuronal MLP de 3 camadas com base no DataFrame e guarda o modelo.
    """
    # 1. Ordenar por data
    df_data = df_data.sort_values(by='date').reset_index(drop=True)
    
    if len(df_data) < 10:
        raise ValueError("São necessários pelo menos 10 dias de histórico para treinar o modelo de vendas.")
        
    # 2. Criar Lags e Variáveis Cíclicas
    df_data['day_of_week'] = df_data['date'].apply(lambda x: x.weekday() + 1)
    df_data['month'] = df_data['date'].apply(lambda x: x.month)
    
    df_data['real_value_lag1'] = df_data['sales_quantity_kg'].shift(1)
    df_data['real_value_lag7'] = df_data['sales_quantity_kg'].shift(7)
    
    # Limpar NaNs
    df_data = df_data.dropna().reset_index(drop=True)
    
    if len(df_data) < 3:
        raise ValueError("Histórico insuficiente após aplicação de lags temporais (mínimo 8 dias no total).")
        
    X = df_data[['real_value_lag1', 'real_value_lag7', 'price_per_kg', 'day_of_week', 'month']].values
    y = df_data['sales_quantity_kg'].values
    
    # 3. Treinar MLP com 3 camadas ocultas
    mlp = MLPRegressor(hidden_layer_sizes=(64, 32, 16), max_iter=10000, random_state=42)
    mlp.fit(X, y)
    
    # 4. Guardar na Base de Dados (BLOB)
    buffer = io.BytesIO()
    joblib.dump(mlp, buffer)
    binary_data = buffer.getvalue()
    
    TrainedModel.objects.update_or_create(
        owner=user,
        culture=subfamily,
        model_type='sales_mlp',
        file_name='sales_mlp.joblib',
        defaults={'file_data': binary_data}
    )
    
    # Persistir também os dados no histórico de vendas da BD
    with transaction.atomic():
        # Limpar histórico anterior desta cultura para este user
        HistoricalSalesData.objects.filter(owner=user, culture=subfamily).delete()
        
        objs = []
        for idx, row in df_data.iterrows():
            objs.append(HistoricalSalesData(
                owner=user,
                culture=subfamily,
                date=row['date'],
                sales_quantity_kg=row['sales_quantity_kg'],
                price_per_kg=row['price_per_kg']
            ))
        HistoricalSalesData.objects.bulk_create(objs)
        
    return len(objs)

def run_sales_inference(user, subfamily, horizon_days=30):
    """
    Executa a inferência autoregressiva multi-step e grava previsões na BD.
    """
    model_record = TrainedModel.objects.filter(
        owner=user,
        culture=subfamily,
        model_type='sales_mlp',
        file_name='sales_mlp.joblib'
    ).first()
    
    if not model_record:
        raise FileNotFoundError("O modelo preditivo de vendas ainda não foi treinado para esta cultura.")
        
    mlp = joblib.load(io.BytesIO(model_record.file_data))
    
    # Obter os últimos 7 dias reais para alimentar a autoregressão inicial
    last_sales = list(HistoricalSalesData.objects.filter(owner=user, culture=subfamily).order_by('-date')[:7])
    if len(last_sales) < 7:
        raise ValueError("É necessário ter pelo menos 7 dias de histórico real guardado para iniciar as previsões.")
        
    # Inverter para ordem cronológica (mais antigo para mais recente)
    running_history = [float(x.sales_quantity_kg) for x in reversed(last_sales)]
    avg_price = float(HistoricalSalesData.objects.filter(owner=user, culture=subfamily).aggregate(avg=Avg('price_per_kg'))['avg'] or 2.0)
    
    predictions = []
    start_date = timezone.now().date()
    
    for step in range(horizon_days):
        current_date = start_date + datetime.timedelta(days=step)
        day_of_week = current_date.weekday() + 1
        month = current_date.month
        
        lag1 = running_history[-1]
        lag7 = running_history[-7]
        
        X_pred = np.array([[lag1, lag7, avg_price, day_of_week, month]])
        y_pred = float(mlp.predict(X_pred)[0])
        y_pred = max(0.0, y_pred) # Evitar previsões negativas
        
        predictions.append((current_date, y_pred))
        running_history.append(y_pred)
        
    # Gravar as previsões na base de dados
    with transaction.atomic():
        # Limpar previsões anteriores
        DemandForecast.objects.filter(owner=user, culture=subfamily).delete()
        
        objs = []
        for dt, val in predictions:
            objs.append(DemandForecast(
                owner=user,
                culture=subfamily,
                date=dt,
                predicted_quantity_kg=val
            ))
        DemandForecast.objects.bulk_create(objs)
        
    return predictions

def train_buyer_agent_optimizer_generator(user, subfamily, df_market_data, max_episodes="640"):
    """
    Treina o PPO chamando o script '0_training_constrained.py' como um subprocesso
    e fazendo yield de cada linha de log em tempo real.
    """
    import subprocess
    
    # 1. Salvar os dados de treino num ficheiro Excel temporário dentro de BuyerAgent/Dados
    buyer_agent_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'BuyerAgent')
    dados_dir = os.path.join(buyer_agent_dir, 'Dados')
    os.makedirs(dados_dir, exist_ok=True)
    
    temp_filename = f"temp_market_user_{user.id}_cult_{subfamily.pk}.xlsx"
    temp_excel_path = os.path.join(dados_dir, temp_filename)
    
    # Renomear as colunas para o formato esperado pelo ambiente
    df_save = df_market_data.copy()
    rename_dict = {
        'sales_quantity_kg': 'real_value',
        'price_per_kg': 'price',
        'date': 'day'
    }
    df_save = df_save.rename(columns=rename_dict)
    
    # Adicionar colunas default se estiverem em falta
    if 'real_value' not in df_save.columns:
        df_save['real_value'] = 100.0
    if 'price' not in df_save.columns:
        df_save['price'] = 2.0
    if 'volume' not in df_save.columns:
        df_save['volume'] = 0.002
        
    df_save.to_excel(temp_excel_path, index=False)
    
    # 2. Configurar variáveis de ambiente para rodar o subprocesso
    env = os.environ.copy()
    env["EXCEL_PATH"] = os.path.join('Dados', temp_filename)
    env["MAX_EPISODES_TOTAL"] = str(max_episodes) 
    env["SINGLE_SEED"] = "1337"
    env["NUM_WORKERS"] = "4" # Configurado para usar 4 cores físicos do CPU do servidor
    
    # 3. Invocar o script 0_training_constrained.py
    cmd = [sys.executable, '0_training_constrained.py']
    
    yield "[Django] A iniciar subprocesso de treino (0_training_constrained.py)...\n"
    
    logs = []
    try:
        process = subprocess.Popen(
            cmd,
            cwd=buyer_agent_dir,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        # Capturar o stdout em tempo real
        for line in process.stdout:
            clean_line = line.strip()
            if clean_line:
                logs.append(clean_line)
                yield clean_line + "\n"
                    
        process.wait()
    except Exception as run_err:
        yield f"[ERRO] Falha ao executar 0_training_constrained.py: {run_err}\n"
        return
        
    # 4. Carregar os pesos gerados para a base de dados como BLOB
    final_actor_path = os.path.join(buyer_agent_dir, 'modelos_producao_constrained', 'ppo_constrained_final_actor.pth')
    final_critic_path = os.path.join(buyer_agent_dir, 'modelos_producao_constrained', 'ppo_constrained_final_critic.pth')
    final_scaler_path = os.path.join(buyer_agent_dir, 'modelos_producao_constrained', 'ppo_constrained_final_scaler.pth')
    
    if os.path.exists(final_actor_path) and os.path.exists(final_critic_path):
        with open(final_actor_path, 'rb') as f:
            actor_data = f.read()
        TrainedModel.objects.update_or_create(
            owner=user,
            culture=subfamily,
            model_type='buyer_agent',
            file_name='buyer_agent_actor.pth',
            defaults={'file_data': actor_data}
        )
        
        with open(final_critic_path, 'rb') as f:
            critic_data = f.read()
        TrainedModel.objects.update_or_create(
            owner=user,
            culture=subfamily,
            model_type='buyer_agent',
            file_name='buyer_agent_critic.pth',
            defaults={'file_data': critic_data}
        )
        
        if os.path.exists(final_scaler_path):
            with open(final_scaler_path, 'rb') as f:
                scaler_data = f.read()
            TrainedModel.objects.update_or_create(
                owner=user,
                culture=subfamily,
                model_type='buyer_agent',
                file_name='buyer_agent_scaler.pth',
                defaults={'file_data': scaler_data}
            )
            
        yield "[Django] [Sucesso] Modelos e pesos PPO carregados para a base de dados com segurança.\n"
    else:
        error_msg = "[Django] [ERRO] O script de treino PPO falhou a criar os ficheiros finais de pesos."
        if logs:
            error_msg += "\n\nLogs do subprocesso:\n" + "\n".join(logs)
        yield error_msg + "\n"
        raise FileNotFoundError(error_msg)
        
    # 5. Limpar os ficheiros do disco para manter o servidor limpo
    try:
        if os.path.exists(temp_excel_path):
            os.remove(temp_excel_path)
        if os.path.exists(final_actor_path):
            os.remove(final_actor_path)
        if os.path.exists(final_critic_path):
            os.remove(final_critic_path)
        if os.path.exists(final_scaler_path):
            os.remove(final_scaler_path)
        final_econ_stat = os.path.join(buyer_agent_dir, 'modelos_producao_constrained', 'ppo_constrained_final_econ_stat.pth')
        if os.path.exists(final_econ_stat):
            os.remove(final_econ_stat)
    except Exception as cleanup_err:
        yield f"[Django] [Aviso] Falha na limpeza de ficheiros locais: {cleanup_err}\n"

def train_buyer_agent_optimizer(user, subfamily, df_market_data, max_episodes="640"):
    """
    Wrapper compatível com testes para consumir o generator de treino PPO e retornar a lista de logs.
    """
    return list(train_buyer_agent_optimizer_generator(user, subfamily, df_market_data, max_episodes=max_episodes))

def compute_daily_agent_decision(user, subfamily, max_capacity=500):
    """
    Lê o estado atual de 17 variáveis e decide a quantidade ótima a comprar hoje.
    """
    # 1. Carregar weights: tentar do banco de dados primeiro
    actor_record = TrainedModel.objects.filter(owner=user, culture=subfamily, model_type='buyer_agent', file_name='buyer_agent_actor.pth').first()
    critic_record = TrainedModel.objects.filter(owner=user, culture=subfamily, model_type='buyer_agent', file_name='buyer_agent_critic.pth').first()
    scaler_record = TrainedModel.objects.filter(owner=user, culture=subfamily, model_type='buyer_agent', file_name='buyer_agent_scaler.pth').first()
    
    # Determinar max_action (máximo histórico de vendas do utilizador)
    sales = HistoricalSalesData.objects.filter(owner=user, culture=subfamily)
    max_demand = float(sales.aggregate(max_val=Max('sales_quantity_kg'))['max_val'] or 150.0)
    if max_demand <= 0:
        max_demand = 150.0
        
    # Inicializar e carregar agente
    agent = ParallelPPOAgent(state_dim=17, action_dim=1, max_action=max_demand)
    
    if actor_record and critic_record:
        agent.policy_actor.load_state_dict(torch.load(io.BytesIO(actor_record.file_data), map_location=agent.device, weights_only=False))
        agent.policy_critic.load_state_dict(torch.load(io.BytesIO(critic_record.file_data), map_location=agent.device, weights_only=False))
        agent.policy_old_actor.load_state_dict(agent.policy_actor.state_dict())
        agent.policy_old_critic.load_state_dict(agent.policy_critic.state_dict())
        if scaler_record:
            scaler_state = torch.load(io.BytesIO(scaler_record.file_data), map_location='cpu', weights_only=False)
            agent.reward_scaler.n = scaler_state['n']
            agent.reward_scaler.mean = scaler_state['mean']
            agent.reward_scaler.S = scaler_state['S']
    else:
        # Fallback: tentar usar o modelo base do repositório
        sku_map = {
            "morango": "3_080",
            "maca": "3_090",
            "kiwi": "3_252",
            "uva": "3_586"
        }
        base_sku = "3_252"
        for k, v in sku_map.items():
            if k in subfamily.name.lower():
                base_sku = v
                break
        checkpoint_prefix = os.path.join('BuyerAgent', 'modelos_producao_constrained', base_sku, 'ppo_constrained_iter313')
        
        if not os.path.exists(checkpoint_prefix + '_actor.pth'):
            raise FileNotFoundError("Não foi encontrado nenhum modelo treinado ou base do Buyer Agent para esta cultura.")
        agent.load(checkpoint_prefix)
        
    # Construir vetor de estado
    state = get_buyer_agent_state(user, subfamily, max_capacity=max_capacity)
    
    # Correr o Actor para obter a percentagem recomendada
    state_tensor = torch.FloatTensor(state).unsqueeze(0).to(agent.device)
    agent.policy_old_actor.eval()
    with torch.no_grad():
        action_mean, _ = agent.policy_old_actor(state_tensor)
        action_percent = float(action_mean.cpu().numpy().flatten()[0])
        
    # Calcular quantidade em Kg
    recommended_qty_kg = round(action_percent * max_demand, 2)
    return recommended_qty_kg
