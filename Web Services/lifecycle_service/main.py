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
    PresetRequest,
    DailyReading
)
from engine.presets import (
    PRESETS_ACADEMIC,
    PRESETS_SOFIA,
    MOLD_BY_FRUIT,
    get_preset
)
from engine.imputation import fill_nulls_with_warehouse_sim
from engine.ode_solver import (
    run_simulation_prof_luis_paulo,
    run_simulation_sofia_machado
)

# Logging configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("lifecycle_service")

# Service Ports & Settings
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8003"))

app = FastAPI(
    title="Retail Eureka - Lifecycle Decay Prediction Web Service",
    description="Microserviço biológico de estimativa de vida útil (Shelf-Life), firmeza, brix e qualidade comercial para produtos perecíveis.",
    version="1.0.0"
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
    """Normalizes and resolves fruit keys against available biological presets."""
    ft = fruit_type.lower().strip().replace(" ", "_").replace("-", "_")
    cn = culture_name.lower().strip().replace(" ", "_").replace("-", "_")
    
    # Try combinations
    comb1 = f"{ft}_{cn}"
    comb2 = f"{cn}_{ft}"
    
    all_keys = set(list(PRESETS_SOFIA.keys()) + list(PRESETS_ACADEMIC.keys()))
    
    if comb1 in all_keys:
        return comb1
    if comb2 in all_keys:
        return comb2
    if ft in all_keys:
        return ft
    if cn in all_keys:
        return cn
        
    # Search for substring matches
    for k in all_keys:
        if k in comb1 or cn in k or ft in k:
            return k
            
    # Default fallback
    return "apple_gala"


@app.get("/health", tags=["Health"])
def health_check():
    """Health check endpoint for container orchestrators and platform monitoring."""
    return {
        "status": "healthy",
        "service": "lifecycle_service",
        "port": PORT,
        "available_presets": len(set(list(PRESETS_SOFIA.keys()) + list(PRESETS_ACADEMIC.keys())))
    }


@app.get("/status", response_model=StatusResponse, tags=["Monitoring"])
def get_service_status():
    """Returns the current concurrency and inference status of the service."""
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
    """Lists all registered fruit varieties and biological presets."""
    all_fruits = sorted(list(set(list(PRESETS_SOFIA.keys()) + list(PRESETS_ACADEMIC.keys()))))
    return {"total_presets": len(all_fruits), "fruits": all_fruits}


@app.get("/presets/{fruit_key}", tags=["Biological Presets"])
def get_preset_details(fruit_key: str):
    """Retrieves full kinetic and thermodynamic parameters for a given fruit variety."""
    try:
        preset_data = get_preset(fruit_key)
        return {"fruit_key": fruit_key, "parameters": preset_data}
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Preset '{fruit_key}' not found. Available: {list_presets()['fruits']}"
        )


@app.post("/preset", tags=["Biological Presets"])
def register_custom_preset(request: PresetRequest):
    """Dynamically registers or updates a custom biological preset."""
    pdump = request.preset.model_dump(exclude_none=True)
    if "E0_int" in pdump:
        PRESETS_ACADEMIC[request.fruit_key] = pdump
    else:
        PRESETS_SOFIA[request.fruit_key] = pdump
        
    MOLD_BY_FRUIT[request.fruit_key] = request.mold_preset.model_dump()
    return {
        "message": "Preset registered successfully",
        "fruit_key": request.fruit_key
    }


@app.post("/forecast", response_model=ForecastResponse, tags=["Decay Inference"])
def calculate_lot_lifecycle_decay(
    request: LifecycleDataRequest, 
    client_id: str = "django-platform", 
    store_id: str = "main-warehouse"
):
    """
    Computes dynamic lot decay, remaining shelf-life, firmness, brix, and quality score
    using kinetic ODE simulations and meteorological imputation.
    """
    fruit_type = request.lot_identification.fruit_type
    culture_name = request.lot_identification.culture_name
    fruit_key = resolve_fruit_key(fruit_type, culture_name)
    
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
        T_c: List[Optional[float]] = []
        RH_pct: List[Optional[float]] = []
        E_ppm: List[Optional[float]] = []
        region_codes: List[str] = []
        alphas: List[float] = []
        packaging_methods: List[Optional[str]] = []
        
        default_alpha = 0.9
        start_date_str = None

        # Build chronological sequences across all warehouse & transport segments
        for wh in request.sensor_history_by_warehouse:
            if not wh.daily_readings and wh.keptancy_start_date and wh.total_days_recorded > 0:
                s_dt = datetime.strptime(wh.keptancy_start_date, "%Y-%m-%d")
                for j in range(wh.total_days_recorded):
                    c_dt = s_dt + timedelta(days=j)
                    wh.daily_readings.append(DailyReading(date=c_dt.strftime("%Y-%m-%d"), source="GENERATED"))
                    
            for reading in wh.daily_readings:
                if start_date_str is None:
                    start_date_str = reading.date
                T_c.append(reading.temperature_celsius)
                RH_pct.append(reading.humidity_percent)
                E_ppm.append(reading.ethylene_ppm)
                region_codes.append(wh.region)
                alphas.append(default_alpha)
                packaging_methods.append(wh.packaging_method)

        # Fallback if no readings supplied: build at least 1 day baseline
        if not T_c:
            harvest_dt = datetime.strptime(request.lot_identification.harvest_date, "%Y-%m-%d")
            start_date_str = request.lot_identification.harvest_date
            days_elapsed = max(1, (datetime.now().date() - harvest_dt.date()).days)
            for d in range(days_elapsed):
                T_c.append(None)
                RH_pct.append(None)
                E_ppm.append(None)
                region_codes.append("PT-LVT")
                alphas.append(default_alpha)
                packaging_methods.append("Granel (Sem embalagem)")
        
        start_date = datetime.strptime(start_date_str or request.lot_identification.harvest_date, "%Y-%m-%d")
        days = len(T_c)
        
        # Meteorological Imputation (Fixed Fallback vs IPMA Regional Normals)
        fallback_mode = request.meteorology_and_imputation_strategy.get("json_fallback_mode", "IPMA")
        if fallback_mode == "FIXED":
            fixed_t = float(request.meteorology_and_imputation_strategy.get("fixed_temperature_celsius", 4.0))
            fixed_rh = float(request.meteorology_and_imputation_strategy.get("fixed_humidity_percent", 90.0))
            T_c_filled = [t if t is not None else fixed_t for t in T_c]
            RH_pct_filled = [rh if rh is not None else fixed_rh for rh in RH_pct]
        else:
            T_c_filled, RH_pct_filled = fill_nulls_with_warehouse_sim(T_c, RH_pct, region_codes, alphas, start_date)
        
        # Decide solver: Academic ODE (with Ethylene synthesis) vs Multi-attribute supply chain ODE
        has_ethylene = any(e is not None for e in E_ppm)
        has_academic_preset = fruit_key in PRESETS_ACADEMIC
        use_academic = has_ethylene and has_academic_preset

        if use_academic:
            preset = PRESETS_ACADEMIC[fruit_key]
        else:
            preset = PRESETS_SOFIA.get(fruit_key, PRESETS_SOFIA["apple_gala"])

        b0 = request.lot_identification.initial_metrics.soluble_solids_brix
        if b0 is None:
            b0 = float(preset["brix_0_default"])
        
        f0 = request.lot_identification.initial_metrics.firmness
        if f0 is None:
            f0 = float(preset["firmness_0_default"])
            
        a0 = request.lot_identification.initial_metrics.acidity
        if a0 is None:
            a0 = float(preset.get("acidity_0_default", 0.5))

        if use_academic:
            algorithm = "ode_academic"
            E_ppm_filled = [float(e) if e is not None else 0.0 for e in E_ppm]
            quality, lifetime, final_f, final_b, arrays_dict = run_simulation_prof_luis_paulo(
                fruit_key=fruit_key,
                T_c=T_c_filled,
                RH_pct=RH_pct_filled,
                E_ext_ppm=E_ppm_filled,
                days=days,
                firmness_0_user=f0,
                brix_0_user=b0
            )
        else:
            algorithm = "ode_new"
            quality, lifetime, final_f, final_b, arrays_dict = run_simulation_sofia_machado(
                fruit_key=fruit_key,
                T_c=T_c_filled,
                RH_pct=RH_pct_filled,
                days=days,
                firmness_0_user=f0,
                brix_0_user=b0,
                acidity_0_user=a0,
                packaging_methods=packaging_methods,
                current_owner_type=request.lot_identification.current_owner_type
            )

        logger.info(f"[Lifecycle Service] Forecast for {fruit_key} (Lot {request.lot_identification.batch_id}): Quality={quality:.1f}, RSL={lifetime:.1f}d, Firmness={final_f:.1f}N, Brix={final_b:.1f}°Bx")

        return ForecastResponse(
            service="lifecycle_inference",
            client_id=client_id,
            store_id=store_id,
            algorithm=algorithm,
            product_id=fruit_key,
            quality_index=round(quality, 2),
            remaining_lifetime=round(lifetime, 1),
            firmness=round(final_f, 2),
            brix=round(final_b, 2),
            continuous_data=arrays_dict if request.plot_info else None
        )
        
    except Exception as e:
        logger.error(f"[Lifecycle Service] Inference failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inference error: {str(e)}"
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
    logger.info(f"Starting Lifecycle Decay Prediction Web Service on {HOST}:{PORT}...")
    uvicorn.run("main:app", host=HOST, port=PORT, reload=False)
