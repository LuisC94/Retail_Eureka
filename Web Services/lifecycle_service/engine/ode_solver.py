import numpy as np
from typing import List, Tuple, Dict, Optional, Union
from .presets import PRESETS_ACADEMIC, PRESETS_SOFIA, MOLD_DEFAULTS, PACKAGING_FACTORS, STAKEHOLDER_PROFILES

# =============================================================================
# BIOLOGICAL ODE SIMULATORS & KINETIC DECAY ENGINES
# =============================================================================

def k_temp_scaling(Ea: float, T: np.ndarray, Tref: float, R: float = 8.314) -> np.ndarray:
    """Arrhenius-type temperature kinetic scaling factor."""
    return np.exp((-Ea / R) * (1.0 / T - 1.0 / Tref))


def sigmoid(x: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
    """Standard logistic sigmoid function."""
    return 1.0 / (1.0 + np.exp(-x))


def calc_vpd(T_cels: np.ndarray, RH_p: np.ndarray) -> np.ndarray:
    """Computes Vapor Pressure Deficit (VPD in kPa) from temperature and RH."""
    es = 0.6108 * np.exp(17.27 * T_cels / (T_cels + 237.3))
    ea = es * (RH_p / 100.0)
    return es - ea


def run_simulation_prof_luis_paulo(
    fruit_key: str, 
    T_c: List[float], 
    E_ext_ppm: Union[List[float], float], 
    RH_pct: List[float], 
    days: int, 
    firmness_0_user: float, 
    brix_0_user: float, 
    custom_preset: Optional[dict] = None
) -> Tuple[float, float, float, float, dict]:
    """
    Executa a simulação biológica com síntese e impacto de etileno endógeno/exógeno (Prof. Luís Paulo).
    Retorna (qualidade_final, vida_remanescente_dias, firmeza_final, brix_final, series_temporais_dict).
    """
    dt = 0.05  # Passo temporal de 1.2h
    R = 8.314

    if custom_preset is not None:
        p = dict(custom_preset)
        for kk, vv in MOLD_DEFAULTS.items():
            p.setdefault(kk, vv)
    else:
        p = PRESETS_ACADEMIC[fruit_key]

    max_sim_days = max(days + 200, 365)
    t = np.arange(0, max_sim_days + dt * 0.5, dt)
    
    extra_days = max_sim_days - days
    if extra_days > 0:
        T_c = list(T_c) + [p["Tref_C"]] * extra_days
        RH_pct = list(RH_pct) + [p["RH_ref"]] * extra_days
        
    T_c_arr = np.repeat(np.array(T_c), int(1.0 / dt))
    RH_pct_arr = np.repeat(np.array(RH_pct), int(1.0 / dt))

    if np.isscalar(E_ext_ppm):
        E_ext_arr = np.full(len(t), float(E_ext_ppm))
    else:
        e_list = list(E_ext_ppm)
        if extra_days > 0:
            e_list = e_list + [0.0] * extra_days
        E_ext_arr = np.repeat(np.array(e_list), int(1.0 / dt))

    # 1. Termodinâmica e Cinética
    T_K = T_c_arr + 273.15
    Tref_K = p["Tref_C"] + 273.15
    kT_firm = p["k_firm_ref"] * k_temp_scaling(p["Ea_J"], T_K, Tref_K, R)
    RH_ref = p["RH_ref"]

    # 2. Etileno Endógeno (E_int)
    E_int = np.zeros_like(t)
    E_int[0] = float(p.get("E0_int", 0.01))

    Ea_E_J = float(p.get("Ea_E_J", 52000.0))
    Eref_prod = float(p.get("Eref_prod", 0.15))
    E_decay = float(p.get("E_decay", 0.65))
    E_t0 = float(p.get("E_t0", 10.0))
    E_g = float(p.get("E_g", 0.9))
    E_auto = float(p.get("E_auto", 0.5))
    E_ext_shift = float(p.get("E_ext_shift", 2.0))

    t0_eff = E_t0 - E_ext_shift * np.log1p(np.maximum(0.0, E_ext_arr))
    prod_T = k_temp_scaling(Ea_E_J, T_K, Tref_K, R)

    for i in range(1, len(t)):
        ramp = sigmoid(E_g * (t[i-1] - (t0_eff[i-1] if not np.isscalar(t0_eff) else t0_eff)))
        prod = Eref_prod * prod_T[i-1] * ramp
        dE = (prod * (1.0 + E_auto * E_int[i-1]) - E_decay * E_int[i-1]) * dt
        E_int[i] = max(0.0, E_int[i-1] + dE)

    E_total = E_ext_arr + E_int

    # 3. Firmeza (ODE)
    firmness = np.zeros_like(t)
    firmness_min = float(p["firmness_min"])
    firmness[0] = max(firmness_min + 1e-6, float(firmness_0_user))
    alpha_E = float(p.get("alpha_E", 0.1))

    for i in range(1, len(t)):
        kE = (1.0 + alpha_E * E_total[i-1])
        RH_deficit = max(0.0, (RH_ref - RH_pct_arr[i-1]) / 100.0)
        kRH = (1.0 + p.get("beta_RH", 1.0) * RH_deficit)
        k = kT_firm[i-1] * kRH * kE
        dD = (-k * (firmness[i-1] - firmness_min)) * dt
        firmness[i] = max(firmness_min, firmness[i-1] + dD)

    # 4. Brix (ODE Logística)
    brix = np.zeros_like(t)
    brix_min = float(p["brix_min"])
    brix_max = float(p["brix_max"])
    brix[0] = float(brix_0_user)
    r0 = float(p.get("brix_g", 0.2))
    alpha_bE = 0.25
    rT = k_temp_scaling(Ea_E_J, T_K, Tref_K, R)

    for i in range(1, len(t)):
        bRH = max(0.0, (RH_ref - RH_pct_arr[i-1]) / 100.0)
        rRH = (1.0 - 0.6 * bRH)
        r = r0 * rT[i-1] * rRH * (1.0 + alpha_bE * E_total[i-1])
        x = max(0.01, brix[i-1] - brix_min)
        K = max(1e-6, (brix_max - brix_min))
        db = (r * x * (1.0 - x / K)) * dt
        brix[i] = min(brix_max, max(brix_min, brix[i-1] + db))

    # 5. Índice de Qualidade Base
    firm_score = 1.0 / (1.0 + np.exp(-0.35 * (firmness - float(p["qual_firmness_threshold"]))))
    brix_score = np.exp(-((brix - float(p["qual_brix_target"])) ** 2) / 2.0)
    quality_base = 100.0 * (0.65 * firm_score + 0.35 * brix_score)

    # 6. Crescimento de Bolores/Fungos
    RH_mold_thr = float(p.get("RH_mold_thr", 95.0))
    mold_rate_ref = float(p.get("mold_rate_ref", 0.06))
    mold_sens_RH = float(p.get("mold_sens_RH", 10.0))
    mold_max_penalty = float(p.get("mold_max_penalty", 0.80))
    Ea_mold_J = float(p.get("Ea_mold_J", 45000.0))
    mold_T = k_temp_scaling(Ea_mold_J, T_K, Tref_K, R)

    mold = np.zeros_like(t)
    mold[0] = 0.0
    for i in range(1, len(t)):
        RH_excess = max(0.0, (RH_pct_arr[i-1] - RH_mold_thr) / 100.0)
        RH_factor = 1.0 - np.exp(-mold_sens_RH * RH_excess)
        rate = mold_rate_ref * mold_T[i-1] * RH_factor
        dm = (rate * (1.0 - mold[i-1])) * dt
        mold[i] = min(1.0, max(0.0, mold[i-1] + dm))

    mold_penalty = mold_max_penalty * mold
    quality = quality_base * (1.0 - mold_penalty)

    # 7. Cálculo no dia pedido
    idx_days = int(days / dt) - 1
    if idx_days < 0:
        idx_days = 0
    if idx_days >= len(quality):
        idx_days = len(quality) - 1
    
    final_quality = float(quality[idx_days])
    
    below_30 = np.where(quality <= 30.0)[0]
    if len(below_30) > 0:
        idx_30 = below_30[0]
        remaining_SL = 0.0 if idx_30 <= idx_days else float(t[idx_30] - days)
    else:
        remaining_SL = float(max_sim_days - days)
        
    idx_end = idx_days + 1
    arrays_dict = {
        "quality": quality[:idx_end].tolist(),
        "firmness": firmness[:idx_end].tolist(),
        "brix": brix[:idx_end].tolist(),
        "t": t[:idx_end].tolist()
    }
    return final_quality, remaining_SL, float(firmness[idx_days]), float(brix[idx_days]), arrays_dict


def run_simulation_sofia_machado(
    fruit_key: str, 
    T_c: List[float], 
    RH_pct: List[float], 
    days: int,
    firmness_0_user: float, 
    brix_0_user: float, 
    acidity_0_user: float, 
    packaging_methods: Optional[List[str]] = None,
    dt: float = 0.05, 
    custom_preset: Optional[dict] = None, 
    current_owner_type: Optional[str] = None
) -> Tuple[float, float, float, float, dict]:
    """
    Executa a simulação biológica multi-parâmetro de cadeia de abastecimento (Sofia Machado).
    Retorna (qualidade_final, vida_remanescente_dias, firmeza_final, brix_final, series_temporais_dict).
    """
    R = 8.314

    if custom_preset is not None:
        p = dict(custom_preset)
        for kk, vv in MOLD_DEFAULTS.items():
            p.setdefault(kk, vv)
    else:
        p = PRESETS_SOFIA[fruit_key]
        
    if packaging_methods is None:
        packaging_methods = ["Granel (Sem embalagem)"] * days
    else:
        packaging_methods = [pm if pm is not None else "Granel (Sem embalagem)" for pm in packaging_methods]
        
    t = np.arange(0, days + dt * 0.5, dt)
    T_c_arr = np.repeat(np.array(T_c), int(1.0 / dt))
    RH_pct_arr = np.repeat(np.array(RH_pct), int(1.0 / dt))
    packaging_methods_rep = np.repeat(np.array(packaging_methods), int(1.0 / dt))

    T_K = T_c_arr + 273.15
    Tref_K = p["Tref_C"] + 273.15

    # VPD e Cinética
    VPD = calc_vpd(T_c_arr, RH_pct_arr)
    VPD_ref = calc_vpd(np.array([p["Tref_C"]]), np.array([p["RH_ref"]]))[0]

    kT_firm = p["k_firm_ref"] * k_temp_scaling(p["Ea_J"], T_K, Tref_K, R)
    firmness = np.zeros_like(t)
    firmness_min = float(p["firmness_min"])
    firmness[0] = max(firmness_min + 1e-6, float(firmness_0_user))

    brix = np.zeros_like(t)
    brix_min = float(p["brix_min"])
    brix_max = float(p["brix_max"])
    brix[0] = float(brix_0_user)
    r0 = float(p["brix_g"])
    rT = k_temp_scaling(52000.0, T_K, Tref_K, R)

    acidity = np.zeros_like(t)
    acidity_min = float(p["acidity_min"])
    acidity[0] = max(acidity_min + 1e-6, float(acidity_0_user))
    kT_acidity = p["k_acidity_ref"] * k_temp_scaling(p["Ea_acidity_J"], T_K, Tref_K, R)
    
    SL_ref = float(p.get("SL_ref", 30))
    consumed_SL = np.zeros_like(t)

    for i in range(1, len(t)):
        VPD_excess = max(0.0, VPD[i-1] - VPD_ref)
        fator_embalagem = PACKAGING_FACTORS.get(packaging_methods_rep[i-1], 1.0)
        VPD_efetivo = VPD_excess * fator_embalagem
        
        # Firmeza
        k_VPD_firm = 1.0 + p.get("beta_RH", 1.0) * VPD_efetivo
        dD = (-kT_firm[i-1] * k_VPD_firm * (firmness[i-1] - firmness_min)) * dt
        firmness[i] = max(firmness_min, firmness[i-1] + dD)

        # Brix
        r_VPD_brix = max(0.0, 1.0 - 0.2 * VPD_efetivo)
        r_brix = r0 * rT[i-1] * r_VPD_brix
        x = max(0.01, brix[i-1] - brix_min)
        K = max(1e-6, (brix_max - brix_min))
        db = (r_brix * x * (1.0 - x / K)) * dt
        brix[i] = min(brix_max, max(brix_min, brix[i-1] + db))

        # Acidez
        dA = (-kT_acidity[i-1] * (acidity[i-1] - acidity_min)) * dt
        acidity[i] = max(acidity_min, acidity[i-1] + dA)

        # Shelf Life
        r_T_SL = k_temp_scaling(55000.0, T_K[i-1], Tref_K, R)
        r_VPD_SL = 1.0 + 0.5 * VPD_efetivo
        consumed_SL[i] = consumed_SL[i-1] + (r_T_SL * r_VPD_SL) * dt

    remaining_SL = np.maximum(0.0, SL_ref - consumed_SL)

    # Scores
    firm_score = 1.0 / (1.0 + np.exp(-0.35 * (firmness - float(p["qual_firmness_threshold"]))))
    brix_score = np.exp(-((brix - float(p["qual_brix_target"])) ** 2) / 2.0)
    acidity_score = np.exp(-((acidity - float(p.get("qual_acidity_target", 1.0))) ** 2) / 0.5)
    
    maturation_index = brix / np.maximum(1e-5, acidity)
    target_ratio = float(p["qual_brix_target"]) / max(1e-5, float(p.get("qual_acidity_target", 1.0)))
    ratio_score = np.exp(-((maturation_index - target_ratio) ** 2) / 10.0)
    
    quality_base = 100.0 * (0.35 * firm_score + 0.35 * ratio_score + 0.15 * brix_score + 0.15 * acidity_score)

    # Bolores
    RH_mold_thr = float(p["RH_mold_thr"])
    mold_rate_ref = float(p["mold_rate_ref"])
    mold_sens_RH = float(p["mold_sens_RH"])
    mold_max_penalty = float(p["mold_max_penalty"])
    Ea_mold_J = float(p["Ea_mold_J"])
    mold_T = k_temp_scaling(Ea_mold_J, T_K, Tref_K, R)

    mold = np.zeros_like(t)
    mold[0] = 0.0
    for i in range(1, len(t)):
        VPD_thr = calc_vpd(np.array([T_c_arr[i-1]]), np.array([RH_mold_thr]))[0]
        VPD_deficit = max(VPD_thr - VPD[i-1], 0.0)
        VPD_factor = 1.0 - np.exp(-mold_sens_RH * VPD_deficit * 5.0)
        rate = mold_rate_ref * mold_T[i-1] * VPD_factor
        dm = (rate * (1.0 - mold[i-1])) * dt
        mold[i] = min(1.0, max(0.0, mold[i-1] + dm))

    profile = STAKEHOLDER_PROFILES.get(current_owner_type, STAKEHOLDER_PROFILES["Retailer (Grocery Store)"])
    
    target_brix = float(p["qual_brix_target"])
    target_acidity = float(p.get("qual_acidity_target", 1.0))
    target_ratio = target_brix / max(1e-5, target_acidity)
    
    firmness_limit = float(p["qual_firmness_threshold"]) * profile["firm_multiplier"]
    mold_limit = profile["mold_limit"]
    min_quality = profile["min_quality"]
    brix_limit = target_brix * profile["brix_multiplier"]
    ratio_limit = target_ratio * profile["ratio_multiplier"]
    
    marketable = np.zeros_like(t, dtype=bool)
    for i in range(len(t)):
        if (brix[i] >= brix_limit and 
            maturation_index[i] >= ratio_limit and
            quality_base[i] >= min_quality and 
            firmness[i] >= firmness_limit and 
            mold[i] <= mold_limit):
            marketable[i] = True
            
    mold_penalty = mold_max_penalty * mold
    quality = quality_base * (1.0 - mold_penalty)
    quality[~marketable] = 0.0
    remaining_SL = np.where(mold_penalty > 0.0, 0.0, remaining_SL)

    arrays_dict = {
        "quality": quality.tolist(), 
        "quality_base": quality_base.tolist(), 
        "firmness": firmness.tolist(), 
        "brix": brix.tolist(), 
        "acidity": acidity.tolist(), 
        "ratio": maturation_index.tolist(), 
        "t": t.tolist()
    }
    
    return float(quality[-1]), float(remaining_SL[-1]), float(firmness[-1]), float(brix[-1]), arrays_dict
