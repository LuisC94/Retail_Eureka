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


def generate_fallback_sensor_readings(warehouse):
    """
    Gera procedimentalmente um conjunto completo de 365 dias de leituras climáticas (180 dias passados e 184 dias futuros)
    para o armazém com base no seu perfil regional (PT-NL, PT-NI, PT-CL, PT-CI, PT-LVT, PT-AL, PT-ALG, PT-SM, PT-MAD, PT-ACO).
    """
    import random
    import datetime
    from django.db import transaction
    from dashboard.models import WarehouseSensorReading
    
    reg = str(warehouse.region).upper()
    
    # Perfis: (Temp_Média, Temp_Amplitude, Humidade_Média, Humidade_Amplitude)
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
    
    # Fallback se não encontrar perfil
    base_temp, temp_amp, base_hum, hum_amp = profiles.get(reg, (16.0, 7.0, 75.0, 8.0))
    
    is_controlled = (warehouse.control_type == 'Controlled')
    today = datetime.date.today()
    start_date = today - datetime.timedelta(days=180)
    
    readings = []
    for day_offset in range(365):
        current_date = start_date + datetime.timedelta(days=day_offset)
        
        # Sazonalidade via curva senoidal
        day_of_year = current_date.timetuple().tm_yday
        # Pico no dia 200 (Julho)
        seasonal_factor = math.sin(2 * math.pi * (day_of_year - 110) / 365)
        
        if is_controlled:
            # Armazém controlado (câmara de frio): ignora condições exteriores
            temp = round(3.5 + random.uniform(-0.5, 0.5), 1)
            hum = round(91.0 + random.uniform(-1.5, 1.5), 1)
            ethylene = round(0.02 + random.uniform(-0.005, 0.005), 3)
        else:
            # Armazém ambiente
            temp = round(base_temp + temp_amp * seasonal_factor + random.uniform(-1.2, 1.2), 1)
            # Humidade inverte a temperatura (mais quente = mais seco)
            hum = round(base_hum - hum_amp * seasonal_factor + random.uniform(-2.5, 2.5), 1)
            # Etileno flutua ligeiramente com o calor/maturação
            ethylene = round(0.05 + 0.02 * seasonal_factor + random.uniform(-0.01, 0.01), 3)
            
        readings.append(WarehouseSensorReading(
            warehouse=warehouse,
            date=current_date,
            temperature=temp,
            humidity=hum,
            ethylene=ethylene
        ))
        
    with transaction.atomic():
        # Limpar leituras antigas deste armazém para evitar violação de unique_together
        WarehouseSensorReading.objects.filter(warehouse=warehouse).delete()
        WarehouseSensorReading.objects.bulk_create(readings)
        
    return len(readings)

