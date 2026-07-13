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

def calculate_quality_decay_curve(culture_name, initial_score=10.0, sensor_readings=None):
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
    fallback_ethylene = 0.01
    
    # Se houver leituras reais de sensores, usar a mais recente (última da lista) como a projeção para o futuro
    if sensor_readings:
        latest = sensor_readings[-1]
        fallback_temp = float(latest.temperature if hasattr(latest, 'temperature') else latest.get('temperature', fallback_temp))
        fallback_humidity = float(latest.humidity if hasattr(latest, 'humidity') else latest.get('humidity', fallback_humidity))
        fallback_ethylene = float(latest.ethylene if hasattr(latest, 'ethylene') else latest.get('ethylene', fallback_ethylene))
    
    # Projeção de até 120 dias para encontrar a validade real do lote
    full_curve = []
    for day_offset in range(120):
        target_date = today + datetime.timedelta(days=day_offset)
        
        # Obter dados climáticos para o dia projetado
        reading = sensor_map.get(target_date)
        if reading:
            temp = float(reading.temperature if hasattr(reading, 'temperature') else reading.get('temperature', fallback_temp))
            humidity = float(reading.humidity if hasattr(reading, 'humidity') else reading.get('humidity', fallback_humidity))
            ethylene = float(reading.ethylene if hasattr(reading, 'ethylene') else reading.get('ethylene', fallback_ethylene))
        else:
            temp = fallback_temp
            humidity = fallback_humidity
            ethylene = fallback_ethylene
            
        # 1. Multiplicador de Temperatura
        temp_diff = max(0.0, temp - ideal_temp)
        temp_multiplier = math.pow(2.0, temp_diff / 10.0)
        
        # 2. Multiplicador de Etileno
        ethylene_multiplier = 1.0 + max(0.0, ethylene * 8.0)
        
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
            "ethylene": ethylene
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
    total_points = len(full_curve)
    if total_points <= 50:
        decay_curve = full_curve
    else:
        # Downsampling para ~25 pontos intermédios
        step = math.ceil(total_points / 25.0)
        decay_curve = []
        for idx, point in enumerate(full_curve):
            if idx == 0 or idx == total_points - 1 or idx % step == 0:
                decay_curve.append(point)
        
    return decay_curve, rsl_days
