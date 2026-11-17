import os
import io
import json
import queue
import datetime
import threading
from typing import List, Optional, Union

import pandas as pd
import torch
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from engine.forecaster import MODELS, ARTIFACT_FORMAT, MIN_TRAIN_DAYS, train, predict_horizon, predict_series

app = FastAPI(
    title="Retail Eureka - Demand Forecast Web Service",
    description=(
        "Previsão de procura com 4 modelos dos notebooks train/inference-RC-PT-1053 "
        "(apresentados como 'Modelo Previsão 1..4'), isolados por utilizador e cultura."
    ),
    version="3.0.0",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STORAGE_DIR = os.path.join(BASE_DIR, "models_storage")
os.makedirs(STORAGE_DIR, exist_ok=True)

# Nomes antigos aceites pela plataforma
ALIASES = {
    "modelo_1": "modelo_1", "model_1": "modelo_1", "mlp": "modelo_1", "sales_mlp": "modelo_1",
    "modelo_2": "modelo_2", "model_2": "modelo_2", "autoformer": "modelo_2", "sales_autoformer": "modelo_2",
    "modelo_3": "modelo_3", "model_3": "modelo_3",
    "modelo_4": "modelo_4", "model_4": "modelo_4",
}

_train_locks = {}
_train_locks_guard = threading.Lock()


def normalize_model_type(raw: Optional[str]) -> str:
    key = ALIASES.get(str(raw or "modelo_1").strip().lower())
    if not key:
        raise HTTPException(status_code=400, detail=f"Modelo desconhecido '{raw}'. Use modelo_1, modelo_2, modelo_3 ou modelo_4.")
    return key


def model_path(user_id, culture_id, model_type, create_dir=False) -> str:
    user_dir = os.path.join(STORAGE_DIR, f"user_{user_id}")
    if create_dir:
        os.makedirs(user_dir, exist_ok=True)
    return os.path.join(user_dir, f"culture_{culture_id}_{model_type}.pt")


def load_artifact(user_id, culture_id, model_type):
    path = model_path(user_id, culture_id, model_type)
    if not os.path.exists(path):
        return None
    try:
        art = torch.load(path, map_location="cpu", weights_only=False)
    except Exception:  # noqa: BLE001
        return None
    return art if isinstance(art, dict) and art.get("format") == ARTIFACT_FORMAT else None


def train_lock(user_id, culture_id, model_type):
    with _train_locks_guard:
        return _train_locks.setdefault(f"{user_id}:{culture_id}:{model_type}", threading.Lock())


# ============================================================
# CONTRATOS DE DADOS
# ============================================================

class HistoricalSaleItem(BaseModel):
    date: str = Field(..., examples=["2026-08-01"])
    sales_quantity_kg: float = Field(..., examples=[125.5])
    price_per_kg: Optional[float] = Field(None, description="Não usado pelos modelos (os notebooks não usam preço)")


class TrainRequest(BaseModel):
    user_id: Union[int, str]
    culture_id: Union[int, str]
    model_type: str = Field("modelo_1", examples=["modelo_1", "modelo_2", "modelo_3", "modelo_4"])
    sales_history: List[HistoricalSaleItem]


class PredictRequest(BaseModel):
    user_id: Union[int, str]
    culture_id: Union[int, str]
    model_type: Optional[str] = "modelo_1"
    horizon_days: int = Field(30, ge=1, le=120)
    start_date: Optional[str] = Field(None, description="Primeiro dia a prever (default: dia seguinte ao último do histórico)")
    sales_history: Optional[List[HistoricalSaleItem]] = Field(None, description="Histórico recente (recomendado >= 30 dias para os lags)")
    recent_sales_lags: Optional[List[float]] = Field(None, description="Compatibilidade: vendas dos últimos dias (mais antigo -> mais recente), terminando na véspera de start_date")
    avg_price: Optional[float] = Field(None, description="Não usado pelos modelos")


class PredictSeriesRequest(BaseModel):
    user_id: Union[int, str]
    culture_id: Union[int, str]
    model_type: Optional[str] = "modelo_1"
    sales_history: List[HistoricalSaleItem]


# ============================================================
# ENDPOINTS
# ============================================================

@app.get("/", tags=["Info"])
def root_info():
    return {
        "service": "Retail Eureka - Demand Forecast Web Service",
        "status": "online",
        "architecture": "Federated Microservice (Per-User Storage)",
        "supported_models": [{"model_type": k, "display_name": v["display_name"]} for k, v in MODELS.items()],
        "docs_url": "/docs",
    }


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "healthy", "timestamp": datetime.datetime.utcnow().isoformat()}


@app.get("/api/forecast/models", tags=["Forecast"])
def list_models():
    return [{"model_type": k, "display_name": v["display_name"]} for k, v in MODELS.items()]


@app.get("/api/forecast/status", tags=["Forecast"])
def get_status(user_id: Union[int, str] = Query(...), culture_id: Union[int, str] = Query(...)):
    available, details, legacy = [], {}, []
    for key, cfg in MODELS.items():
        art = load_artifact(user_id, culture_id, key)
        if art:
            available.append(key)
            details[key] = {"display_name": cfg["display_name"], "trained_at": art["trained_at"],
                            "val_metrics": art["val_metrics"], "last_date": art["last_date"],
                            "n_train": art["n_train"], "n_val": art["n_val"]}
        elif os.path.exists(model_path(user_id, culture_id, key)):
            legacy.append(key)
    last = max((d["trained_at"] for d in details.values()), default=None)
    return {"user_id": str(user_id), "culture_id": str(culture_id), "has_model": bool(available),
            "available_models": available, "models": details, "requires_retrain": legacy, "last_modified": last}


def _train_and_save(payload: TrainRequest, model_type: str, progress_cb=None):
    history = [h.model_dump() for h in payload.sales_history]
    art = train(model_type, history, progress_cb=progress_cb)
    path = model_path(payload.user_id, payload.culture_id, model_type, create_dir=True)
    buf = io.BytesIO()
    torch.save(art, buf)
    with open(path, "wb") as f:
        f.write(buf.getvalue())
    return {
        "status": "SUCCESS",
        "message": f"{art['display_name']} treinado com sucesso para o utilizador {payload.user_id}, cultura {payload.culture_id}.",
        "user_id": payload.user_id, "culture_id": payload.culture_id, "model_type": model_type,
        "model_display_name": art["display_name"],
        "saved_file": os.path.relpath(path, STORAGE_DIR).replace("\\", "/"),
        "samples_used": len(history), "val_metrics": art["val_metrics"],
        "training_time_seconds": art["training_time_seconds"], "trained_at": art["trained_at"],
    }


def _check_history(payload: TrainRequest):
    if len(payload.sales_history) < MIN_TRAIN_DAYS:
        raise HTTPException(status_code=400, detail=f"Histórico insuficiente: são necessários pelo menos {MIN_TRAIN_DAYS} dias (recebidos {len(payload.sales_history)}).")


@app.post("/api/forecast/train", tags=["Forecast"])
def train_forecast(payload: TrainRequest):
    model_type = normalize_model_type(payload.model_type)
    _check_history(payload)
    lock = train_lock(payload.user_id, payload.culture_id, model_type)
    if not lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Já existe um treino deste modelo a decorrer.")
    try:
        return _train_and_save(payload, model_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        lock.release()


@app.post("/api/forecast/train/stream", tags=["Forecast"])
def train_forecast_stream(payload: TrainRequest):
    """SSE: um evento por treino da pesquisa de kernels {step, total_steps, kernel, multiplier, score, best_score}; no fim {event: done}."""
    model_type = normalize_model_type(payload.model_type)
    _check_history(payload)
    lock = train_lock(payload.user_id, payload.culture_id, model_type)
    if not lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Já existe um treino deste modelo a decorrer.")
    q: "queue.Queue" = queue.Queue()

    def worker():
        try:
            q.put({"event": "done", **_train_and_save(payload, model_type, progress_cb=q.put)})
        except Exception as e:  # noqa: BLE001
            q.put({"event": "error", "detail": str(e)})
        finally:
            lock.release()
            q.put(None)

    threading.Thread(target=worker, daemon=True).start()

    def stream():
        while True:
            item = q.get()
            if item is None:
                break
            yield f"data: {json.dumps(item, ensure_ascii=False, default=str)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


def _require_artifact(user_id, culture_id, model_type):
    art = load_artifact(user_id, culture_id, model_type)
    if art is None:
        name = MODELS[model_type]["display_name"]
        if os.path.exists(model_path(user_id, culture_id, model_type)):
            raise HTTPException(status_code=409, detail=f"O {name} desta cultura foi treinado numa versão antiga. Volte a treiná-lo.")
        raise HTTPException(status_code=404, detail=f"O {name} ainda não foi treinado para esta cultura.")
    return art


@app.post("/api/forecast/predict", tags=["Forecast"])
def predict(payload: PredictRequest):
    model_type = normalize_model_type(payload.model_type)
    art = _require_artifact(payload.user_id, payload.culture_id, model_type)
    if payload.sales_history:
        history = [h.model_dump() for h in payload.sales_history]
    elif payload.recent_sales_lags:
        start = pd.to_datetime(payload.start_date or datetime.date.today()).normalize()
        n = len(payload.recent_sales_lags)
        days = pd.date_range(end=start - pd.Timedelta(days=1), periods=n, freq="D")
        history = [{"date": str(d.date()), "sales_quantity_kg": float(v)} for d, v in zip(days, payload.recent_sales_lags)]
    else:
        raise HTTPException(status_code=400, detail="Indique sales_history (recomendado) ou recent_sales_lags.")
    preds = predict_horizon(art, history, start_date=payload.start_date, horizon_days=payload.horizon_days)
    return {
        "status": "SUCCESS", "user_id": payload.user_id, "culture_id": payload.culture_id,
        "model_type": model_type, "model_display_name": art["display_name"], "horizon_days": payload.horizon_days,
        "history_days_used": len(history),
        "predictions": [{"date": str(d), "predicted_kg": v} for d, v in preds],
    }


@app.post("/api/forecast/predict_series", tags=["Forecast"])
def predict_history_series(payload: PredictSeriesRequest):
    """Previsão a 1 dia para cada data do histórico (série 'prediction' usada no treino do Buyer Agent)."""
    model_type = normalize_model_type(payload.model_type)
    art = _require_artifact(payload.user_id, payload.culture_id, model_type)
    preds = predict_series(art, [h.model_dump() for h in payload.sales_history])
    return {
        "status": "SUCCESS", "user_id": payload.user_id, "culture_id": payload.culture_id,
        "model_type": model_type, "model_display_name": art["display_name"],
        "total_dates": len(preds), "predictions": [{"date": str(d), "predicted_kg": v} for d, v in preds],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", "8001")), reload=False)
