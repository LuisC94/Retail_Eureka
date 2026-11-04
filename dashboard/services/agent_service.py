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
from dashboard.models import ProductSubFamily, HistoricalSalesData, DemandForecast, ConsolidatedStock, Warehouse, TrainedModel
from dashboard.services.marketplace_service import marketplace_service
from sklearn.neural_network import MLPRegressor


def get_user_stock_profile(user, subfamily):
    """
    Distribui o stock consolidado do comprador nas categorias G0-G3 de shelf-life
    com base nas leituras dinâmicas do armazém e estimativa de RSL do LC Agent.
    G0: RSL >= 4 dias
    G1: RSL == 3 dias
    G2: RSL == 2 dias
    G3: RSL == 1 dia
    """
    stock_profile = [0.0, 0.0, 0.0, 0.0]
    total_cons = float(ConsolidatedStock.objects.filter(owner=user, culture=subfamily).aggregate(total=Sum('quantity'))['total'] or 0.0)
    
    if total_cons > 0:
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
                    if WarehouseSensorReading.objects.filter(warehouse=warehouse).count() < 30:
                        try:
                            from dashboard.services.lc_service import generate_fallback_sensor_readings
                            generate_fallback_sensor_readings(warehouse)
                        except Exception:
                            pass
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
    
    # Re-inferência automática de previsões se faltarem dados para os próximos 25 dias
    try:
        from dashboard.models import DemandForecast, TrainedModel
        future_forecast_count = DemandForecast.objects.filter(owner=user, culture=subfamily, date__gte=today).count()
        if future_forecast_count < 25:
            has_model = TrainedModel.objects.filter(owner=user, culture=subfamily, model_type__in=['sales_mlp', 'sales_autoformer']).exists()
            if has_model:
                run_sales_inference(user, subfamily, horizon_days=30)
    except Exception as e:
        print(f"[Auto-Refresh Forecast] Erro ao re-inferir: {str(e)}")

    stock_profile = get_user_stock_profile(user, subfamily)
    
    # Encomendas em trânsito (obtidas do Marketplace Web Service)
    total_in_transit = 0.0
    try:
        deals = marketplace_service.fetch_deals(buyer_id=user.username, culture_name=subfamily.name)
        for d in deals:
            if d.get('transport_status') in ['PENDING', 'ACCEPTED', 'PLANNED', 'IN_TRANSIT']:
                total_in_transit += float(d.get('quantity_kg', 0.0))
    except Exception:
        total_in_transit = 0.0
    
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
    
    # Preço do Marketplace (obtido do Marketplace Web Service)
    price_today = 2.0
    try:
        listings = marketplace_service.fetch_open_listings(culture_name=subfamily.name)
        if listings:
            prices = [float(l.get('price_per_kg', 0.0)) for l in listings if l.get('price_per_kg')]
            if prices:
                price_today = sum(prices) / len(prices)
            else:
                price_today = float(listings[0].get('price_per_kg', 2.0))
        else:
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
    except Exception:
        price_today = 2.0
        
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

import requests
from django.conf import settings

FORECAST_SERVICE_URL = getattr(settings, 'FORECAST_SERVICE_URL', 'http://127.0.0.1:8001')
BUYER_SERVICE_URL = getattr(settings, 'BUYER_SERVICE_URL', 'http://127.0.0.1:8002')


def get_forecast_model_status(user, subfamily):
    """
    Consulta o estado dos modelos (MLP e Autoformer) para este utilizador e cultura no Forecast Web Service.
    """
    try:
        resp = requests.get(
            f"{FORECAST_SERVICE_URL}/api/forecast/status",
            params={"user_id": user.id, "culture_id": subfamily.pk},
            timeout=5
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.warning(f"Erro ao verificar status no Forecast Web Service: {e}")
    
    # Fallback para BD local se o microserviço não responder
    models = list(TrainedModel.objects.filter(owner=user, culture=subfamily).values_list('model_type', flat=True))
    available = []
    if 'sales_mlp' in models:
        available.append('mlp')
    if 'sales_autoformer' in models:
        available.append('autoformer')
    return {
        "user_id": user.id,
        "culture_id": subfamily.pk,
        "has_model": len(available) > 0,
        "available_models": available,
        "last_modified": None
    }


def train_sales_forecaster(user, subfamily, df_data, model_type='mlp'):
    """
    Envia os dados históricos para o Forecast Web Service treinar e guardar o modelo.
    """
    df_data = df_data.sort_values(by='date').reset_index(drop=True)
    
    if len(df_data) < 10:
        raise ValueError("São necessários pelo menos 10 dias de histórico para treinar o modelo de vendas.")
        
    sales_history = []
    for _, row in df_data.iterrows():
        dt_val = row['date']
        dt_str = dt_val.strftime('%Y-%m-%d') if hasattr(dt_val, 'strftime') else str(dt_val)
        sales_history.append({
            "date": dt_str,
            "sales_quantity_kg": float(row['sales_quantity_kg']),
            "price_per_kg": float(row.get('price_per_kg', 2.0) or 2.0)
        })
        
    model_type_clean = model_type.lower() if model_type else 'mlp'
    if model_type_clean not in ['mlp', 'autoformer']:
        model_type_clean = 'mlp'

    payload = {
        "user_id": user.id,
        "culture_id": subfamily.pk,
        "model_type": model_type_clean,
        "sales_history": sales_history
    }
    
    try:
        resp = requests.post(f"{FORECAST_SERVICE_URL}/api/forecast/train", json=payload, timeout=90)
        if resp.status_code != 200:
            error_detail = resp.json().get('detail', resp.text) if resp.headers.get('content-type') == 'application/json' else resp.text
            raise RuntimeError(f"Erro no Forecast Web Service: {error_detail}")
        resp_data = resp.json()
    except requests.exceptions.ConnectionError:
        raise ConnectionError(f"Não foi possível contactar o Forecast Web Service em {FORECAST_SERVICE_URL}. Verifique se o serviço está ativo.")

    # Guardar marcador na base de dados local indicando que o modelo existe no Web Service
    TrainedModel.objects.update_or_create(
        owner=user,
        culture=subfamily,
        model_type=f'sales_{model_type_clean}',
        file_name=f'culture_{subfamily.pk}_{model_type_clean}',
        defaults={'file_data': b'web_service_remote_model'}
    )
    
    # Persistir também os dados no histórico de vendas da BD local
    with transaction.atomic():
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
        
    return {
        "samples_count": len(objs),
        "model_type": model_type_clean,
        "saved_file": resp_data.get('saved_file', ''),
        "trained_at": resp_data.get('trained_at', timezone.now().isoformat())
    }


def run_sales_inference(user, subfamily, horizon_days=30, model_type=None):
    """
    Pede ao Forecast Web Service a previsão para os próximos N dias e persiste na BD local.
    Retorna dicionário completo com previsões, histórico recente e KPIs agregados.
    """
    last_sales = list(HistoricalSalesData.objects.filter(owner=user, culture=subfamily).order_by('-date')[:30])
    if len(last_sales) < 7:
        raise ValueError("É necessário ter pelo menos 7 dias de histórico real guardado para iniciar as previsões. Por favor treine o modelo ou carregue o histórico primeiro.")
        
    running_history = [float(x.sales_quantity_kg) for x in reversed(last_sales)]
    recent_history_items = [{
        'date': x.date.strftime('%Y-%m-%d'),
        'value': round(float(x.sales_quantity_kg), 2)
    } for x in reversed(last_sales)]
    
    avg_price = float(HistoricalSalesData.objects.filter(owner=user, culture=subfamily).aggregate(avg=Avg('price_per_kg'))['avg'] or 2.0)
    
    # Se model_type não for especificado, detetar preferência treinada
    if not model_type:
        has_autoformer = TrainedModel.objects.filter(owner=user, culture=subfamily, model_type='sales_autoformer').exists()
        model_type = 'autoformer' if has_autoformer else 'mlp'
    else:
        model_type = model_type.lower()
    
    start_date_str = timezone.now().date().strftime('%Y-%m-%d')
    
    payload = {
        "user_id": user.id,
        "culture_id": subfamily.pk,
        "model_type": model_type,
        "horizon_days": int(horizon_days),
        "start_date": start_date_str,
        "recent_sales_lags": running_history,
        "avg_price": avg_price
    }
    
    try:
        resp = requests.post(f"{FORECAST_SERVICE_URL}/api/forecast/predict", json=payload, timeout=30)
        if resp.status_code != 200:
            error_detail = resp.json().get('detail', resp.text) if resp.headers.get('content-type') == 'application/json' else resp.text
            raise RuntimeError(f"Erro no Forecast Web Service: {error_detail}")
        data = resp.json()
    except requests.exceptions.ConnectionError:
        raise ConnectionError(f"Não foi possível contactar o Forecast Web Service em {FORECAST_SERVICE_URL}. Verifique se o serviço está ativo.")

    predictions = []
    total_val = 0.0
    peak_val = 0.0
    peak_date = ""
    
    for item in data.get('predictions', []):
        dt_str = item['date']
        val = max(0.0, float(item['predicted_kg']))
        val_rounded = round(val, 2)
        predictions.append({
            'date': dt_str,
            'value': val_rounded
        })
        total_val += val_rounded
        if val_rounded > peak_val:
            peak_val = val_rounded
            peak_date = dt_str
        
    # Gravar as previsões recebidas na base de dados local para manter sincronismo
    with transaction.atomic():
        DemandForecast.objects.filter(owner=user, culture=subfamily).delete()
        objs = []
        for p in predictions:
            dt_obj = datetime.datetime.strptime(p['date'], '%Y-%m-%d').date()
            objs.append(DemandForecast(
                owner=user,
                culture=subfamily,
                date=dt_obj,
                predicted_quantity_kg=p['value']
            ))
        DemandForecast.objects.bulk_create(objs)
        
    count_pred = len(predictions)
    daily_avg = round(total_val / count_pred, 2) if count_pred > 0 else 0.0
    
    kpis = {
        'total_predicted_kg': round(total_val, 2),
        'daily_avg_kg': daily_avg,
        'peak_date': peak_date,
        'peak_val_kg': round(peak_val, 2),
        'model_type': model_type.upper(),
        'horizon_days': int(horizon_days),
        'samples_trained': len(last_sales)
    }
    
    return {
        'predictions': predictions,
        'recent_history': recent_history_items,
        'kpis': kpis,
        'model_type': model_type
    }


def check_buyer_service_health():
    """
    Verifica se o Buyer Agent Web Service (Porta 8002) está online.
    """
    try:
        resp = requests.get(f"{BUYER_SERVICE_URL}/health", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False


def get_buyer_model_status(user, subfamily):
    """
    Consulta o estado do modelo PPO no Buyer Agent Web Service (Porta 8002).
    Sem fallbacks locais: se o serviço estiver offline, lança ConnectionError.
    """
    try:
        resp = requests.get(
            f"{BUYER_SERVICE_URL}/api/buyer/status",
            params={"user_id": user.id, "culture_id": subfamily.pk},
            timeout=5
        )
        if resp.status_code == 200:
            data = resp.json()
            data["service_online"] = True
            return data
        else:
            err = resp.json().get('detail', resp.text) if resp.headers.get('content-type') == 'application/json' else resp.text
            raise RuntimeError(f"Erro no Buyer Web Service ({resp.status_code}): {err}")
    except requests.exceptions.ConnectionError:
        raise ConnectionError(f"O Buyer Agent Web Service está inacessível em {BUYER_SERVICE_URL}. Certifique-se de que o microserviço está ativo na porta 8002.")


def train_buyer_agent_optimizer_generator(user, subfamily, df_market_data, max_episodes="300", fruit_key=None):
    """
    Treina a política PPO do Buyer Agent comunicando exclusivamente com o Buyer Agent Web Service via REST.
    Envia a série histórica com vendas reais e previsões.
    """
    yield f"[Django] A preparar dados de treino para a cultura {subfamily.name}...\n"
    
    df_save = df_market_data.copy()
    rename_dict = {
        'sales_quantity_kg': 'real_value',
        'price_per_kg': 'price'
    }
    df_save = df_save.rename(columns=rename_dict)
    
    if 'real_value' not in df_save.columns:
        df_save['real_value'] = 100.0
    if 'price' not in df_save.columns:
        df_save['price'] = 2.0
    if 'volume' not in df_save.columns:
        df_save['volume'] = 0.002
        
    # Enriquecimento com previsões da BD ou aproximação local
    if 'prediction' not in df_save.columns or df_save['prediction'].isna().all():
        db_forecasts = {f.date: float(f.predicted_quantity_kg) for f in DemandForecast.objects.filter(owner=user, culture=subfamily)}
        predictions = []
        for _, row in df_save.iterrows():
            d = row['date'] if hasattr(row['date'], 'strftime') else row['date']
            if d in db_forecasts:
                predictions.append(db_forecasts[d])
            else:
                predictions.append(float(row['real_value']))
        df_save['prediction'] = predictions

    # Mapeamento do preset biológico da cultura caso não seja fornecido explicitamente
    if not fruit_key:
        name_lower = subfamily.name.lower()
        if "gala" in name_lower or "maca" in name_lower or "maçã" in name_lower:
            fruit_key = "maca_gala"
        elif "fuji" in name_lower:
            fruit_key = "maca_fuji"
        elif "kiwi" in name_lower or "hayward" in name_lower:
            fruit_key = "kiwi_hayward"
        elif "golden" in name_lower:
            fruit_key = "maca_golden"
        elif "reineta" in name_lower:
            fruit_key = "maca_reineta"
        else:
            fruit_key = "maca_gala"
        
    train_records = []
    for _, row in df_save.iterrows():
        dt_val = row['date']
        dt_str = dt_val.strftime('%Y-%m-%d') if hasattr(dt_val, 'strftime') else str(dt_val)
        train_records.append({
            "date": dt_str,
            "real_value": float(row['real_value']),
            "prediction": float(row['prediction']),
            "price": float(row.get('price', 2.0) or 2.0),
            "temperature": float(row.get('temperature', 1.5) or 1.5),
            "humidity": float(row.get('humidity', 92.0) or 92.0),
            "ethylene": float(row.get('ethylene', 0.05) or 0.05),
            "volume": float(row.get('volume', 0.002) or 0.002)
        })
        
    num_episodes = int(max_episodes) if str(max_episodes).isdigit() else 300
    
    payload = {
        "user_id": user.id,
        "culture_id": subfamily.pk,
        "fruit_key": fruit_key,
        "max_capacity": 500.0,
        "episodes": num_episodes,
        "train_data": train_records
    }
    
    yield f"[Django] A contactar o Buyer Agent Web Service ({BUYER_SERVICE_URL}/api/buyer/train)...\n"
    yield f"[Django] A treinar política PPO ({num_episodes} episódios, {len(train_records)} amostras, preset: {fruit_key})...\n"
    
    try:
        resp = requests.post(f"{BUYER_SERVICE_URL}/api/buyer/train", json=payload, timeout=180)
        if resp.status_code != 200:
            err = resp.json().get('detail', resp.text) if resp.headers.get('content-type') == 'application/json' else resp.text
            yield f"[Django] [ERRO] Falha no Buyer Agent Web Service: {err}\n"
            raise RuntimeError(f"Erro no Buyer Agent Web Service: {err}")
            
        data = resp.json()
        yield f"[Django] [Sucesso] {data.get('message', 'Modelo PPO treinado com sucesso.')}\n"
        yield f"[Django] Lucro Médio de Simulação: {data.get('avg_profit')} € | Limite Máximo Diário: {data.get('max_order_limit')} Kg | Tempo: {data.get('training_time_seconds')}s\n"
        
        # Criar/atualizar marcador de modelo treinado na BD local
        TrainedModel.objects.update_or_create(
            owner=user,
            culture=subfamily,
            model_type='buyer_agent',
            defaults={
                'file_name': 'actor.pth',
                'file_data': b'web_service_remote_model'
            }
        )
        yield "[Django] Marcador de modelo sincronizado na base de dados com sucesso.\n"
    except requests.exceptions.ConnectionError:
        err_msg = f"[Django] [ERRO] Não foi possível ligar ao Buyer Agent Web Service em {BUYER_SERVICE_URL}. O serviço deve estar online para realizar o treino."
        yield err_msg + "\n"
        raise ConnectionError(err_msg)


def train_buyer_agent_optimizer(user, subfamily, df_market_data, max_episodes="300", fruit_key=None):
    """
    Wrapper compatível para treinar o Buyer Agent e retornar a lista de logs.
    """
    return list(train_buyer_agent_optimizer_generator(user, subfamily, df_market_data, max_episodes=max_episodes, fruit_key=fruit_key))


def get_buyer_agent_decision_details(user, subfamily, max_capacity=500):
    """
    Gera a recomendação ótima e o relatório analítico completo contactando o Buyer Agent Web Service (/api/buyer/decide).
    Sem fallbacks locais: se o serviço estiver offline, lança ConnectionError.
    """
    today = timezone.now().date()
    
    # 1. Garantir que existem previsões de procura recentes
    try:
        future_forecast_count = DemandForecast.objects.filter(owner=user, culture=subfamily, date__gte=today).count()
        if future_forecast_count < 2:
            has_model = TrainedModel.objects.filter(owner=user, culture=subfamily, model_type__in=['sales_mlp', 'sales_autoformer']).exists()
            if has_model:
                run_sales_inference(user, subfamily, horizon_days=30)
    except Exception as e:
        print(f"[Auto-Refresh Forecast] Aviso: {e}")

    # 2. Perfil de stock [G0, G1, G2, G3]
    stock_profile = get_user_stock_profile(user, subfamily)
    
    # Encomendas em trânsito (obtidas do Marketplace Web Service)
    total_in_transit = 0.0
    try:
        deals = marketplace_service.fetch_deals(buyer_id=user.username, culture_name=subfamily.name)
        for d in deals:
            if d.get('transport_status') in ['PENDING', 'ACCEPTED', 'PLANNED', 'IN_TRANSIT']:
                total_in_transit += float(d.get('quantity_kg', 0.0))
    except Exception:
        total_in_transit = 0.0
    
    # Previsão para hoje e amanhã
    pred_today_obj = DemandForecast.objects.filter(owner=user, culture=subfamily, date=today).first()
    prediction_today = float(pred_today_obj.predicted_quantity_kg) if pred_today_obj else 10.0
    
    tomorrow = today + datetime.timedelta(days=1)
    pred_tomorrow_obj = DemandForecast.objects.filter(owner=user, culture=subfamily, date=tomorrow).first()
    prediction_tomorrow = float(pred_tomorrow_obj.predicted_quantity_kg) if pred_tomorrow_obj else prediction_today
    
    # Vendas reais passadas (t-1 e t-2)
    yesterday = today - datetime.timedelta(days=1)
    t_minus_2 = today - datetime.timedelta(days=2)
    
    sale_yesterday = HistoricalSalesData.objects.filter(owner=user, culture=subfamily, date=yesterday).first()
    real_t_minus_1 = float(sale_yesterday.sales_quantity_kg) if sale_yesterday else prediction_today
    
    sale_t_minus_2 = HistoricalSalesData.objects.filter(owner=user, culture=subfamily, date=t_minus_2).first()
    real_t_minus_2 = float(sale_t_minus_2.sales_quantity_kg) if sale_t_minus_2 else real_t_minus_1
    
    # Preço do Marketplace
    price_today = 2.0
    try:
        listings = marketplace_service.fetch_open_listings(culture_name=subfamily.name)
        if listings:
            prices = [float(l.get('price_per_kg', 0.0)) for l in listings if l.get('price_per_kg')]
            if prices:
                price_today = sum(prices) / len(prices)
            else:
                price_today = float(listings[0].get('price_per_kg', 2.0))
        else:
            default_price = 2.0
            name_lower = subfamily.name.lower()
            if "morango" in name_lower:
                default_price = 4.5
            elif any(x in name_lower for x in ["maca", "maçã", "gala", "fuji", "reineta"]):
                default_price = 1.8
            elif any(x in name_lower for x in ["kiwi", "hayward"]):
                default_price = 3.2
            elif "uva" in name_lower:
                default_price = 2.5
            price_today = default_price
    except Exception:
        price_today = 2.0

    past_sales = HistoricalSalesData.objects.filter(owner=user, culture=subfamily).order_by('-date')[:15]
    recent_prices = [float(s.price_per_kg or price_today) for s in past_sales] if past_sales.exists() else [price_today] * 15

    # 3. Contactar Buyer Agent Web Service
    payload = {
        "user_id": user.id,
        "culture_id": subfamily.pk,
        "date": today.isoformat(),
        "current_stock_profile": stock_profile,
        "in_transit_kg": total_in_transit,
        "prediction_today_kg": prediction_today,
        "prediction_tomorrow_kg": prediction_tomorrow,
        "recent_sales_lags": [real_t_minus_1, real_t_minus_2],
        "price_today": price_today,
        "recent_prices": recent_prices,
        "max_capacity": float(max_capacity)
    }

    try:
        resp = requests.post(f"{BUYER_SERVICE_URL}/api/buyer/decide", json=payload, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            data["culture_name"] = subfamily.name
            data["price_today"] = price_today
            return data
        else:
            err = resp.json().get('detail', resp.text) if resp.headers.get('content-type') == 'application/json' else resp.text
            raise RuntimeError(f"Erro no Buyer Agent Web Service: {err}")
    except requests.exceptions.ConnectionError:
        raise ConnectionError(f"O Buyer Agent Web Service está inacessível em {BUYER_SERVICE_URL}. A inferência só pode ser executada quando o microserviço estiver online.")


def compute_daily_agent_decision(user, subfamily, max_capacity=500):
    """
    Wrapper para obter a quantidade recomendada diretamente do Buyer Agent Web Service.
    """
    decision = get_buyer_agent_decision_details(user, subfamily, max_capacity=max_capacity)
    return float(decision.get('recommended_order_kg', 0.0))


