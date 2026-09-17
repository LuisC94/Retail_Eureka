import datetime
import math

# Parâmetros padrão de degradação biológica para cada família de produtos
CULTURE_DECAY_PARAMS = {
    "morango": {
        "base_decay": 0.18,      # Perda de qualidade base diária (~18% por dia em condições ideais)
        "ideal_temp": 0.0,       # Temperatura ótima (ºC)
        "ideal_humidity": 95.0,  # Humidade ótima (%)
        "default_rsl": 3         # Dias padrão de validade
    },
    "maca": {
        "base_decay": 0.04,      # Perda de qualidade base diária (~4% por dia)
        "ideal_temp": 1.0,
        "ideal_humidity": 90.0,
        "default_rsl": 15
    },
    "maçã": {
        "base_decay": 0.04,
        "ideal_temp": 1.0,
        "ideal_humidity": 90.0,
        "default_rsl": 15
    },
    "kiwi": {
        "base_decay": 0.06,      # Perda de qualidade base diária (~6% por dia)
        "ideal_temp": 0.0,
        "ideal_humidity": 92.0,
        "default_rsl": 10
    },
    "uva": {
        "base_decay": 0.08,      # Perda de qualidade base diária (~8% por dia)
        "ideal_temp": 0.5,
        "ideal_humidity": 92.0,
        "default_rsl": 6
    }
}

def get_culture_params(culture_name):
    """
    Retorna os parâmetros biológicos associados à cultura com base no nome.
    """
    name_lower = culture_name.lower()
    
    # Mapeamento robusto de termos em português e inglês
    if "kiwi" in name_lower:
        return CULTURE_DECAY_PARAMS["kiwi"]
    elif "maca" in name_lower or "maçã" in name_lower or "maça" in name_lower or "apple" in name_lower:
        return CULTURE_DECAY_PARAMS["maca"]
    elif "morango" in name_lower or "strawberry" in name_lower:
        return CULTURE_DECAY_PARAMS["morango"]
    elif "uva" in name_lower or "grape" in name_lower:
        return CULTURE_DECAY_PARAMS["uva"]
        
    # Fallback genérico de média duração
    return {
        "base_decay": 0.07,
        "ideal_temp": 1.0,
        "ideal_humidity": 90.0,
        "default_rsl": 7
    }


# ----------------------------------------------------------------------
# Presets de Qualidade Físico-Química por Subfamília (Colheita)
# ----------------------------------------------------------------------
CULTURE_QUALITY_PRESETS = {
    "gala": {"qual_firm_threshold": 28.0, "qual_brix_target": 14.5, "qual_acidez_target": 0.45},
    "fuji": {"qual_firm_threshold": 40.0, "qual_brix_target": 16.0, "qual_acidez_target": 0.40},
    "golden": {"qual_firm_threshold": 35.0, "qual_brix_target": 13.5, "qual_acidez_target": 0.50},
    "golden delicious": {"qual_firm_threshold": 35.0, "qual_brix_target": 13.5, "qual_acidez_target": 0.50},
    "reineta": {"qual_firm_threshold": 30.0, "qual_brix_target": 12.5, "qual_acidez_target": 0.65},
    "granny": {"qual_firm_threshold": 42.0, "qual_brix_target": 12.2, "qual_acidez_target": 0.85},
    "granny smith": {"qual_firm_threshold": 42.0, "qual_brix_target": 12.2, "qual_acidez_target": 0.85},
    "hayward": {"qual_firm_threshold": 8.0, "qual_brix_target": 15.0, "qual_acidez_target": 1.20},
    "green": {"qual_firm_threshold": 8.0, "qual_brix_target": 15.0, "qual_acidez_target": 1.20},
    "gold": {"qual_firm_threshold": 6.0, "qual_brix_target": 17.0, "qual_acidez_target": 1.00},
    "red": {"qual_firm_threshold": 6.0, "qual_brix_target": 16.5, "qual_acidez_target": 0.95},
}

def get_culture_quality_preset(culture_name):
    """
    Retorna o dicionário com os coeficientes de qualidade para uma determinada cultura/variedade.
    """
    if not culture_name:
        return {"qual_firm_threshold": 28.0, "qual_brix_target": 14.0, "qual_acidez_target": 0.50}
    name_lower = str(culture_name).lower()
    for key, val in CULTURE_QUALITY_PRESETS.items():
        if key in name_lower:
            return val
    if "kiwi" in name_lower:
        return {"qual_firm_threshold": 8.0, "qual_brix_target": 15.0, "qual_acidez_target": 1.20}
    return {"qual_firm_threshold": 30.0, "qual_brix_target": 14.0, "qual_acidez_target": 0.50}

def calculate_harvest_quality(culture_name, firmness, brix, acidity):
    """
    Calcula a qualidade base de um lote de colheita com base na fórmula biológica:
    - firm_score = 1 / (1 + exp(-0.35 * (firmeza - qual_firm_threshold)))
    - brix_score = exp(-((brix - qual_brix_target)**2) / 2)
    - acidez_score = exp(-((acidez - qual_acidez_target)**2) / 0.5)
    - target_ratio = qual_brix_target / qual_acidez_target
    - ratio_score = exp(-(((brix / acidez) - target_ratio)**2) / 25.0)
    - quality_base = 100 * (0.35 * firm_score + 0.35 * ratio_score + 0.15 * brix_score + 0.15 * acidez_score)

    Retorna a pontuação de qualidade na escala de 0 a 100 (float).
    """
    p = get_culture_quality_preset(culture_name)
    
    try:
        firmeza = float(firmness) if firmness is not None and str(firmness).strip() != "" else float(p["qual_firm_threshold"])
        brix_val = float(brix) if brix is not None and str(brix).strip() != "" else float(p["qual_brix_target"])
        acidez_val = float(acidity) if acidity is not None and str(acidity).strip() != "" else float(p["qual_acidez_target"])
        
        if acidez_val <= 0:
            acidez_val = 0.01
            
        firm_threshold = float(p["qual_firm_threshold"])
        brix_target = float(p["qual_brix_target"])
        acidez_target = float(p["qual_acidez_target"])
        
        # 1. Firm Score
        firm_score = 1.0 / (1.0 + math.exp(-0.35 * (firmeza - firm_threshold)))
        
        # 2. Brix Score
        brix_score = math.exp(-((brix_val - brix_target) ** 2) / 2.0)
        
        # 3. Acidez Score
        acidez_score = math.exp(-((acidez_val - acidez_target) ** 2) / 0.5)
        
        # 4. Ratio Score
        target_ratio = brix_target / acidez_target
        ratio = brix_val / acidez_val
        ratio_score = math.exp(-((ratio - target_ratio) ** 2) / 25.0)
        
        # Qualidade Base (0 - 100)
        quality_base = 100.0 * (0.35 * firm_score + 0.35 * ratio_score + 0.15 * brix_score + 0.15 * acidez_score)
        return max(0.0, min(100.0, round(quality_base, 2)))
    except Exception as e:
        return 100.0
    """
    Calcula a projeção da curva de degradação da qualidade (% de 0 a 100)
    ao longo dos próximos 15 dias com base nos sensores.
    Retorna a lista de pontos do gráfico e o RSL (Remaining Shelf Life) previsto em dias.
    """
    params = get_culture_params(culture_name)
    base_decay = params["base_decay"]
    ideal_temp = params["ideal_temp"]
    ideal_humidity = params["ideal_humidity"]
    
    # Iniciar com qualidade máxima (ou proporcional ao score inicial, escala 0-10)
    current_quality = float(initial_score) * 10.0 if initial_score else 100.0
    current_quality = min(100.0, max(0.0, current_quality))
    
    decay_curve = []
    today = datetime.date.today()
    rsl_days = None
    
    # Criar lista indexada dos sensores para facilitar a correspondência diária
    sensor_map = {}
    if sensor_readings:
        for r in sensor_readings:
            # r pode ser um objeto model ou dict
            r_date = r.date if hasattr(r, 'date') else r.get('date')
            if isinstance(r_date, str):
                try:
                    r_date = datetime.datetime.strptime(r_date, "%Y-%m-%d").date()
                except ValueError:
                    pass
            if r_date:
                sensor_map[r_date] = r
                
    # Fallbacks padrão de condições do armazém se não houver sensores
    fallback_temp = 4.0
    fallback_humidity = 90.0
    fallback_ethylene = None
    
    # Se houver leituras reais de sensores, usar a mais recente (última da lista) como a projeção para o futuro
    if sensor_readings:
        latest = sensor_readings[-1]
        fallback_temp = float(latest.temperature if hasattr(latest, 'temperature') else latest.get('temperature', fallback_temp))
        fallback_humidity = float(latest.humidity if hasattr(latest, 'humidity') else latest.get('humidity', fallback_humidity))
        raw_eth = latest.ethylene if hasattr(latest, 'ethylene') else latest.get('ethylene', None)
        fallback_ethylene = float(raw_eth) if raw_eth is not None else None
    
    # Projeção de até 120 dias para encontrar a validade real do lote
    full_curve = []
    for day_offset in range(120):
        target_date = today + datetime.timedelta(days=day_offset)
        
        # Obter dados climáticos para o dia projetado
        reading = sensor_map.get(target_date)
        if reading:
            temp = float(reading.temperature if hasattr(reading, 'temperature') else reading.get('temperature', fallback_temp))
            humidity = float(reading.humidity if hasattr(reading, 'humidity') else reading.get('humidity', fallback_humidity))
            raw_eth = reading.ethylene if hasattr(reading, 'ethylene') else reading.get('ethylene', None)
            ethylene = float(raw_eth) if raw_eth is not None else fallback_ethylene
        else:
            temp = fallback_temp
            humidity = fallback_humidity
            ethylene = fallback_ethylene
            
        # 1. Multiplicador de Temperatura
        temp_diff = max(0.0, temp - ideal_temp)
        temp_multiplier = math.pow(2.0, temp_diff / 10.0)
        
        # 2. Multiplicador de Etileno (Neutro 1.0 quando não há medição de etileno)
        if ethylene is not None:
            ethylene_multiplier = 1.0 + max(0.0, float(ethylene) * 8.0)
        else:
            ethylene_multiplier = 1.0
        
        # 3. Multiplicador de Humidade
        humidity_diff = max(0.0, ideal_humidity - humidity)
        humidity_multiplier = 1.0 + (humidity_diff * 0.04)
        
        # Degradação calculada para hoje
        daily_decay = base_decay * temp_multiplier * ethylene_multiplier * humidity_multiplier
        
        # Guardar ponto temporário
        full_curve.append({
            "day": day_offset,
            "date": target_date.strftime("%Y-%m-%d"),
            "quality": round(current_quality, 1),
            "temperature": temp,
            "humidity": humidity,
            "ethylene": round(ethylene, 3) if ethylene is not None else None
        })
        
        # Reduzir a qualidade para o dia seguinte
        current_quality -= daily_decay * 10.0
        current_quality = max(0.0, current_quality)
        
        # Determinar o RSL
        if current_quality < 10.0 and rsl_days is None:
            rsl_days = day_offset
            break
            
    # Se ainda tiver qualidade decente após 120 dias
    if rsl_days is None:
        rsl_days = 120

    # Simplificar a curva se tiver muitos pontos para manter a renderização do gráfico rápida e limpa
    decay_curve = []
    if full_curve:
        step = 1 if len(full_curve) <= 15 else max(1, len(full_curve) // 15)
        for i in range(0, len(full_curve), step):
            decay_curve.append(full_curve[i])
        if full_curve[-1] not in decay_curve:
            decay_curve.append(full_curve[-1])
            
        # Garantir pelo menos 7 a 15 pontos
        if len(decay_curve) < 7:
            decay_curve = []
            for point in full_curve[:15]:
                decay_curve.append(point)
        
    return decay_curve, rsl_days


def generate_fallback_sensor_readings(warehouse):
    """
    Gera leituras climáticas (180 dias passados e 184 dias futuros)
    para o armazém com base na sua estratégia meteorológica configurada (FIXED, IPMA, JSON).
    Etileno só é gerado se o armazém tiver sensores de etileno reais registados.
    """
    import random
    import datetime
    from django.db import transaction
    from dashboard.models import WarehouseSensorReading
    
    meteo_source = getattr(warehouse, 'meteo_source', 'FIXED') or 'FIXED'
    json_fallback = getattr(warehouse, 'json_fallback_mode', 'FIXED') or 'FIXED'
    fixed_t = float(warehouse.fixed_temperature if warehouse.fixed_temperature is not None else 4.0)
    fixed_h = float(warehouse.fixed_humidity if warehouse.fixed_humidity is not None else 90.0)
    
    reg = str(warehouse.region).upper()
    
    # Verificar se o armazém possui histórico com etileno real
    has_real_ethylene = WarehouseSensorReading.objects.filter(
        warehouse=warehouse,
        ethylene__isnull=False
    ).exists()
    
    # Perfis Regionais IPMA: (Temp_Média, Temp_Amplitude, Humidade_Média, Humidade_Amplitude)
    profiles = {
        'PT-NL': (14.5, 5.0, 83.0, 5.0),   # Norte Litoral: húmido, moderado
        'PT-NI': (13.5, 10.0, 72.0, 12.0), # Norte Interior: grande amplitude, frio/quente
        'PT-CL': (15.5, 6.0, 78.0, 6.0),   # Centro Litoral: temperado marítimo
        'PT-CI': (14.0, 9.0, 70.0, 10.0),  # Centro Interior: continental
        'PT-LVT': (17.0, 7.0, 72.0, 8.0),  # Lisboa e Vale do Tejo: mediterrânico moderado
        'PT-AL': (17.5, 11.0, 64.0, 15.0), # Alentejo: seco, verão quente, invernos frios
        'PT-ALG': (18.5, 6.5, 67.0, 8.0),  # Algarve: mediterrânico ameno, seco
        'PT-SM': (8.5, 9.5, 78.0, 12.0),   # Serra da Estrela: montanha, frio rigoroso
        'PT-MAD': (19.5, 3.5, 74.0, 4.0),  # Madeira: subtropical estável
        'PT-ACO': (17.5, 3.0, 85.0, 4.0),  # Açores: oceânico muito húmido, estável
    }
    
    base_temp, temp_amp, base_hum, hum_amp = profiles.get(reg, (16.0, 7.0, 75.0, 8.0))
    is_controlled = (warehouse.control_type == 'Controlled')
    today = datetime.date.today()
    start_date = today - datetime.timedelta(days=180)
    
    readings = []
    for day_offset in range(365):
        current_date = start_date + datetime.timedelta(days=day_offset)
        day_of_year = current_date.timetuple().tm_yday
        seasonal_factor = math.sin(2 * math.pi * (day_of_year - 110) / 365)
        
        # Determinar valores com base na estratégia meteorológica
        ethylene = None
        if meteo_source == 'FIXED':
            temp = round(fixed_t + random.uniform(-0.3, 0.3), 1)
            hum = round(min(100.0, max(10.0, fixed_h + random.uniform(-1.0, 1.0))), 1)
            ethylene = None
        elif meteo_source == 'IPMA':
            if is_controlled:
                temp = round(3.5 + random.uniform(-0.5, 0.5), 1)
                hum = round(91.0 + random.uniform(-1.5, 1.5), 1)
            else:
                temp = round(base_temp + temp_amp * seasonal_factor + random.uniform(-1.2, 1.2), 1)
                hum = round(max(20.0, min(100.0, base_hum - hum_amp * seasonal_factor + random.uniform(-2.5, 2.5))), 1)
            ethylene = None
        elif meteo_source == 'JSON':
            # Modo JSON: usa fallback configurado para os dias sem sensor manual
            if json_fallback == 'FIXED':
                temp = round(fixed_t + random.uniform(-0.3, 0.3), 1)
                hum = round(min(100.0, max(10.0, fixed_h + random.uniform(-1.0, 1.0))), 1)
            elif json_fallback == 'IPMA':
                if is_controlled:
                    temp = round(3.5 + random.uniform(-0.5, 0.5), 1)
                    hum = round(91.0 + random.uniform(-1.5, 1.5), 1)
                else:
                    temp = round(base_temp + temp_amp * seasonal_factor + random.uniform(-1.2, 1.2), 1)
                    hum = round(max(20.0, min(100.0, base_hum - hum_amp * seasonal_factor + random.uniform(-2.5, 2.5))), 1)
            else: # NONE
                temp = 4.0
                hum = 90.0
                
            # Apenas gera etileno interpolado se o armazém possuir sensores de etileno reais
            if has_real_ethylene:
                ethylene = round(0.015 + random.uniform(-0.003, 0.003), 3)
            else:
                ethylene = None
        else:
            temp = round(fixed_t, 1)
            hum = round(fixed_h, 1)
            ethylene = None
            
        readings.append(WarehouseSensorReading(
            warehouse=warehouse,
            date=current_date,
            temperature=temp,
            humidity=hum,
            ethylene=ethylene
        ))
        
    with transaction.atomic():
        WarehouseSensorReading.objects.filter(warehouse=warehouse).delete()
        WarehouseSensorReading.objects.bulk_create(readings)
        
    return len(readings)

