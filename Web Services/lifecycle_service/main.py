import os
import uuid
import logging
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from schemas import (
    LifecycleDataRequest,
    ForecastResponse,
    StatusResponse,
    DailyReading
)
from engine.lc_v0_2_0 import (
    PRESETS,
    PACKAGING_FACTORS,
    STAKEHOLDER_CONFIG_BY_GROUP,
    get_fruit_group,
    get_stakeholder_config,
    fill_nulls_with_warehouse_sim,
    run_simulation_prof_luis_paulo,
    run_simulation_sofia_machado
)

# Logging configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("lifecycle_service")

# Service Settings
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8003"))

app = FastAPI(
    title="Retail Eureka - Lifecycle Decay Prediction Web Service",
    description="Microserviço biológico de estimativa de vida útil (Shelf-Life), firmeza, brix, acidez e qualidade comercial (LC v0.2.0 - Ponto A Comercial & Ponto B Biológico).",
    version="2.0.0"
)

# Enable CORS for communication from Django or external services
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Concurrency locks
_inference_lock = threading.Lock()
_status_lock = threading.Lock()
_current_operation: Dict[str, Any] = {
    "operation": None,
    "client_id": None,
    "store_id": None,
    "product_id": None,
    "algorithm": None,
}


def resolve_fruit_key(fruit_type: str, culture_name: str) -> str:
    """Normaliza e resolve nomes de variedades e famílias botânicas nos presets do modelo v0.2.0."""
    ft = str(fruit_type or '').lower().strip()
    cn = str(culture_name or '').lower().strip()
    combined = f"{ft} {cn}".lower()
    
    if "hayward" in combined:
        return "kiwi_hayward"
    elif "baby" in combined:
        return "kiwi_baby"
    elif "gold" in combined and "kiwi" in combined:
        return "kiwi_gold"
    elif "kiwi" in combined:
        return "kiwi_hayward"
    elif "gala" in combined:
        return "apple_gala"
    elif "fuji" in combined:
        return "apple_fuji"
    elif "golden" in combined:
        return "apple_golden"
    elif "reineta" in combined:
        return "apple_reineta"
    elif "granny" in combined or "smith" in combined:
        return "apple_golden"
    elif "red delicious" in combined:
        return "apple_red_delicious"
    elif "esmolfe" in combined or "bravo" in combined:
        return "apple_reineta"
    elif "pink lady" in combined:
        return "apple_fuji"
    elif "alcobaca" in combined or "alcobaça" in combined:
        return "apple_gala"
    elif "jonagold" in combined:
        return "apple_golden"
    elif "royal" in combined:
        return "apple_gala"
    elif "maca" in combined or "maçã" in combined or "apple" in combined:
        return "apple_gala"
    elif "pera" in combined or "pêra" in combined or "pear" in combined or "rocha" in combined:
        return "pear"
    elif "morango" in combined or "strawberry" in combined:
        return "strawberry"
    elif "framboesa" in combined or "raspberry" in combined:
        return "raspberry"
    elif "figo" in combined or "fig" in combined:
        return "fig"
    elif "mirtilo" in combined or "blueberry" in combined:
        return "blueberry"
    elif "cereja" in combined or "cherry" in combined:
        return "cherry"
    elif "banana" in combined:
        return "banana"
    elif "pessego" in combined or "pêssego" in combined or "peach" in combined:
        return "peach"
    elif "ameixa" in combined or "plum" in combined:
        return "plum"
    elif "melao" in combined or "melão" in combined or "melon" in combined:
        return "melon"
    elif "uva" in combined or "grape" in combined:
        return "grape"
    elif "laranja" in combined or "orange" in combined:
        return "orange"
        
    for k in PRESETS:
        if k in ft or k in cn:
            return k
            
    return "apple_gala"


@app.get("/health", tags=["Health"])
def health_check():
    """Health check endpoint for container orchestrators and platform monitoring."""
    return {
        "status": "healthy",
        "service": "lifecycle_service",
        "version": "2.0.0",
        "port": PORT,
        "available_presets": len(PRESETS)
    }


@app.get("/status", response_model=StatusResponse, tags=["Monitoring"])
def get_service_status():
    """Returns current concurrency and inference status of the service."""
    busy = _inference_lock.locked()
    if not busy:
        return StatusResponse(busy=False, message="Available")
    
    with _status_lock:
        op = dict(_current_operation)
        
    return StatusResponse(
        busy=True,
        operation=op.get("operation"),
        message="Busy",
        client_id=op.get("client_id"),
        store_id=op.get("store_id"),
        product_id=op.get("product_id"),
        algorithm=op.get("algorithm"),
    )


@app.get("/presets", tags=["Biological Presets"])
def list_presets():
    """Lists all registered fruit varieties and biological presets in LC v0.2.0."""
    all_fruits = sorted(list(PRESETS.keys()))
    return {"total_presets": len(all_fruits), "fruits": all_fruits}


@app.get("/presets/{fruit_key}", tags=["Biological Presets"])
def get_preset_details(fruit_key: str):
    """Retrieves full kinetic and thermodynamic parameters for a given fruit variety."""
    if fruit_key in PRESETS:
        return {"fruit_key": fruit_key, "parameters": PRESETS[fruit_key]}
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Preset '{fruit_key}' not found. Available: {list(PRESETS.keys())}"
    )


@app.post("/forecast", response_model=ForecastResponse, tags=["Decay Inference"])
def calculate_lot_lifecycle_decay(
    request: LifecycleDataRequest, 
    client_id: str = "django-platform", 
    store_id: str = "main-warehouse"
):
    """
    Calcula a simulação biológica contínua de degradação, Ponto A (Fim de Vida Comercial)
    e Ponto B (Fim de Vida Biológica / Apodrecimento) com sincronismo fisiológico rigoroso (LC v0.2.0).
    """
    fruit_type = request.lot_identification.fruit_type
    culture_name = request.lot_identification.culture_name
    fruit_key = resolve_fruit_key(fruit_type, culture_name)
    if fruit_key not in PRESETS:
        fruit_key = "apple_gala"
    
    acquired = _inference_lock.acquire(blocking=False)
    operation_id = str(uuid.uuid4())
    
    with _status_lock:
        _current_operation.update({
            "operation": operation_id,
            "client_id": client_id,
            "store_id": store_id,
            "product_id": fruit_key,
            "algorithm": "ode",
        })
        
    if not acquired:
        return JSONResponse(
            status_code=429,
            content={
                "detail": "Too Many Requests",
                "message": "Inference simulation is currently busy processing another batch."
            }
        )

    try:
        preset = PRESETS.get(fruit_key, PRESETS["apple_gala"])
        owner_type = request.lot_identification.current_owner_type or "Retailer (Grocery Store)"

        T_c: List[Optional[float]] = []
        RH_pct: List[Optional[float]] = []
        E_ppm: List[Optional[float]] = []
        region_codes: List[str] = []
        packaging_methods: List[str] = []
        start_date_str = None

        # Build chronological sequences across warehouse/transport segments
        for wh in request.sensor_history_by_warehouse:
            s_date = wh.starting_date or wh.keptancy_start_date
            if not wh.daily_readings and s_date and wh.total_days_recorded > 0:
                s_dt = datetime.strptime(s_date, "%Y-%m-%d")
                for j in range(wh.total_days_recorded):
                    c_dt = s_dt + timedelta(days=j)
                    wh.daily_readings.append(DailyReading(date=c_dt.strftime("%Y-%m-%d"), source="GENERATED"))

            pkg_method = wh.packaging_method or "bulk"
            for reading in wh.daily_readings:
                if start_date_str is None:
                    start_date_str = reading.date
                T_c.append(reading.temperature_celsius)
                RH_pct.append(reading.humidity_percent)
                E_ppm.append(reading.ethylene_ppm)
                region_codes.append(wh.region or "PT-LVT")
                packaging_methods.append(pkg_method)

        # Se houver override global de embalagem no pedido (Abordagem B: Simulação interativa no modal)
        if request.packaging_method:
            raw_pkg = request.packaging_method.lower().strip()
            if "map" in raw_pkg or "selad" in raw_pkg:
                selected_pkg = "map_sealed"
            elif "perfur" in raw_pkg or "saco" in raw_pkg:
                selected_pkg = "perforated_bag"
            elif "caixa" in raw_pkg or "open" in raw_pkg or "grade" in raw_pkg:
                selected_pkg = "open_box"
            else:
                selected_pkg = "bulk"

            # Aplica no segmento final / atual
            if packaging_methods:
                packaging_methods[-1] = selected_pkg
            else:
                packaging_methods = [selected_pkg]

        # Calculate actual days elapsed since harvest
        real_days_elapsed = 0
        if request.lot_identification.harvest_date:
            try:
                harvest_dt = datetime.strptime(request.lot_identification.harvest_date, "%Y-%m-%d")
                real_days_elapsed = max(0, (datetime.now().date() - harvest_dt.date()).days)
            except Exception:
                real_days_elapsed = 0

        if not T_c and real_days_elapsed > 0:
            start_date_str = request.lot_identification.harvest_date
            for _ in range(real_days_elapsed):
                T_c.append(None)
                RH_pct.append(None)
                E_ppm.append(None)
                region_codes.append("PT-LVT")
                packaging_methods.append(request.packaging_method or "bulk")

        if not T_c:
            # Lote colhido hoje sem leituras prévias: dia 0
            T_c = [4.0]
            RH_pct = [90.0]
            E_ppm = [None]
            region_codes = ["PT-LVT"]
            packaging_methods = [request.packaging_method or "bulk"]
            start_date_str = request.lot_identification.harvest_date

        days = len(T_c)
        start_date = datetime.strptime(start_date_str or request.lot_identification.harvest_date, "%Y-%m-%d")

        # Imputation Strategy (Fixed vs IPMA Regional Normals)
        fallback_mode = request.meteorology_and_imputation_strategy.get("json_fallback_mode", "IPMA")
        if fallback_mode == "FIXED":
            fixed_t = float(request.meteorology_and_imputation_strategy.get("fixed_temperature_celsius", 4.0))
            fixed_rh = float(request.meteorology_and_imputation_strategy.get("fixed_humidity_percent", 90.0))
            fixed_eth = float(request.meteorology_and_imputation_strategy.get("fixed_ethylene_ppm", 0.05))
            T_c_filled = [fixed_t if t is None else float(t) for t in T_c]
            RH_pct_filled = [fixed_rh if rh is None else float(rh) for rh in RH_pct]
            E_ppm_filled = [fixed_eth if e is None else float(e) for e in E_ppm]
        else:
            T_c_filled, RH_pct_filled = fill_nulls_with_warehouse_sim(
                T_c, RH_pct, region_codes, alphas=[0.9]*days, start_date=start_date
            )
            E_ppm_filled = [0.0 if e is None else float(e) for e in E_ppm]

        # Model Decision Trigger: if any ethylene reading > 0, activate Prof. Luís Paulo; otherwise Sofia Machado
        has_any_ethylene = any(e is not None and float(e) > 0 for e in E_ppm)

        b0 = request.lot_identification.initial_metrics.soluble_solids_brix
        if b0 is None:
            b0 = float(preset["brix_0_default"])
        
        f0 = request.lot_identification.initial_metrics.firmness
        if f0 is None:
            f0 = request.lot_identification.initial_metrics.firmness_n
        if f0 is None:
            f0 = float(preset["firmness_0_default"])
            
        a0 = request.lot_identification.initial_metrics.acidity
        if a0 is None:
            a0 = request.lot_identification.initial_metrics.acidity_percent
        if a0 is None:
            a0 = float(preset.get("acidity_0_default", 0.5))

        if has_any_ethylene:
            algo = "ode_academic"
            q, comm_life, bio_life, final_f, final_b, pt_a, pt_b, arrays_dict = run_simulation_prof_luis_paulo(
                fruit_key=fruit_key,
                T_c=T_c_filled,
                E_ext_ppm=E_ppm_filled,
                RH_pct=RH_pct_filled,
                days=days,
                firmness_0_user=f0,
                brix_0_user=b0,
                packaging_methods=packaging_methods,
                current_owner_type=owner_type
            )
        else:
            algo = "ode_new"
            q, comm_life, bio_life, final_f, final_b, pt_a, pt_b, arrays_dict = run_simulation_sofia_machado(
                fruit_key=fruit_key,
                T_c=T_c_filled,
                RH_pct=RH_pct_filled,
                days=days,
                firmness_0_user=f0,
                brix_0_user=b0,
                acidity_0_user=a0,
                packaging_methods=packaging_methods,
                current_owner_type=owner_type
            )

        final_a = None
        if arrays_dict and "acidity" in arrays_dict and len(arrays_dict["acidity"]) > 0:
            final_a = float(arrays_dict["acidity"][-1])
        elif a0 is not None:
            final_a = float(a0)

        final_mold = 0.0
        if arrays_dict and "mold" in arrays_dict and len(arrays_dict["mold"]) > 0:
            final_mold = float(arrays_dict["mold"][-1])

        logger.info(
            f"[Lifecycle Service v0.2.0] Forecast {fruit_key} (Lot {request.lot_identification.batch_id}): "
            f"Qualidade={q:.1f}%, Ponto A={pt_a:.1f}d (RSL={comm_life:.1f}d), Ponto B={pt_b:.1f}d (RSL={bio_life:.1f}d), "
            f"Firmeza={final_f:.1f}N, Brix={final_b:.1f}°Bx, Embalagem={packaging_methods[-1] if packaging_methods else 'bulk'}"
        )

        return ForecastResponse(
            service="lifecycle_inference",
            client_id=client_id,
            store_id=store_id,
            algorithm=algo,
            product_id=fruit_key,
            quality_index=round(float(q), 2),
            commercial_lifetime_remaining=round(float(comm_life), 1),
            biological_lifetime_remaining=round(float(bio_life), 1),
            remaining_lifetime=round(float(comm_life), 1),
            point_a_day=round(float(pt_a), 1),
            point_b_day=round(float(pt_b), 1),
            firmness=round(float(final_f), 2),
            brix=round(float(final_b), 2),
            acidity=round(float(final_a), 3) if final_a is not None else None,
            mold=round(float(final_mold), 4),
            continuous_data=arrays_dict if request.plot_info else None
        )

    except Exception as e:
        logger.error(f"[Lifecycle Service] Falha na inferência: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro na simulação do ciclo de vida: {str(e)}"
        )
    finally:
        with _status_lock:
            _current_operation.update({
                "operation": None,
                "client_id": None,
                "store_id": None,
                "product_id": None,
                "algorithm": None,
            })
        _inference_lock.release()


if __name__ == "__main__":
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
