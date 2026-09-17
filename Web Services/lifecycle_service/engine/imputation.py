import math
import random
from datetime import datetime, timedelta
from typing import List, Tuple, Optional

# =============================================================================
# METEOROLOGICAL ESTIMATION & WAREHOUSE PHYSICS (IPMA & PSYCHROMETRY)
# =============================================================================

REGIONAL_PROFILES = {
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


def get_region_weather(region_code: str, target_date: datetime) -> Tuple[float, float]:
    """
    Simula dados climáticos baseados no perfil regional do IPMA e na sazonalidade do dia do ano.
    Retorna (temperatura_celsius, humidade_percentual).
    """
    base_temp, temp_amp, base_hum, hum_amp = REGIONAL_PROFILES.get(region_code, (16.0, 7.0, 75.0, 8.0))
    
    day_of_year = target_date.timetuple().tm_yday
    # Curva senoidal com pico solar em Julho (~dia 200)
    seasonal_factor = math.sin(2 * math.pi * (day_of_year - 110) / 365)
    
    temp = round(base_temp + temp_amp * seasonal_factor + random.uniform(-1.2, 1.2), 1)
    hum = round(base_hum - hum_amp * seasonal_factor + random.uniform(-2.5, 2.5), 1)
    hum = min(100.0, max(15.0, hum))
    
    return temp, hum


def calc_absolute_humidity(T_cels: float, RH_pct: float) -> float:
    """Calcula a Humidade Absoluta (g/m3 ou kg/m3) a partir de T e RH."""
    numerator = 2.16679 * RH_pct * 6.112 * math.exp((17.67 * T_cels) / (T_cels + 243.5))
    denominator = T_cels + 273.15
    return numerator / denominator


def calc_relative_humidity(T_cels: float, HA: float) -> float:
    """Calcula a Humidade Relativa (%) a partir de T e Humidade Absoluta."""
    numerator = HA * (T_cels + 273.15)
    denominator = 2.16679 * 6.112 * math.exp((17.67 * T_cels) / (T_cels + 243.5))
    HR = numerator / denominator
    return min(max(HR, 0.0), 100.0)


def simulate_warehouse_climate(
    T_ext_series: List[float], 
    HR_ext_series: List[float], 
    alphas: Optional[List[float]] = None, 
    T_int_initial: Optional[float] = None
) -> Tuple[List[float], List[float]]:
    """
    Simula o microclima interior de um armazém com inércia térmica (fator alpha).
    """
    if not T_ext_series or len(T_ext_series) != len(HR_ext_series):
        return [], []
    
    if alphas is None:
        alphas = [0.9] * len(T_ext_series)
    elif not isinstance(alphas, list):
        alphas = [alphas] * len(T_ext_series)
        
    T_int_series = []
    HR_int_series = []
    
    T_int_prev = T_ext_series[0] if T_int_initial is None else T_int_initial
        
    for i in range(len(T_ext_series)):
        T_ext = T_ext_series[i]
        HR_ext = HR_ext_series[i]
        alpha = alphas[i]
        
        T_int = alpha * T_int_prev + (1 - alpha) * T_ext
        T_int_series.append(round(T_int, 2))
        
        HA_ext = calc_absolute_humidity(T_ext, HR_ext)
        HR_int = calc_relative_humidity(T_int, HA_ext)
        HR_int_series.append(round(HR_int, 2))
        
        T_int_prev = T_int
        
    return T_int_series, HR_int_series


def fill_nulls_with_warehouse_sim(
    temp_array: List[Optional[float]], 
    rh_array: List[Optional[float]], 
    region_codes: List[str], 
    alphas: List[float], 
    start_date: datetime
) -> Tuple[List[float], List[float]]:
    """
    Preenche leituras nulas com a simulação climática regional IPMA + inércia de armazém.
    """
    T_ext_series = []
    HR_ext_series = []
    
    for i in range(len(temp_array)):
        current_date = start_date + timedelta(days=i)
        reg = region_codes[i] if i < len(region_codes) and region_codes[i] else 'PT-LVT'
        temp, hum = get_region_weather(reg, current_date)
        T_ext_series.append(temp)
        HR_ext_series.append(hum)
        
    T_int_series, HR_int_series = simulate_warehouse_climate(T_ext_series, HR_ext_series, alphas=alphas)
    
    res_temp = []
    res_rh = []
    
    for i in range(len(temp_array)):
        t_val = temp_array[i]
        rh_val = rh_array[i]
        
        res_temp.append(T_int_series[i] if t_val is None else float(t_val))
        res_rh.append(HR_int_series[i] if rh_val is None else float(rh_val))
            
    return res_temp, res_rh
