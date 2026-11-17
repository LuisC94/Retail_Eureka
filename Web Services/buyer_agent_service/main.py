import os
import json
import queue
import datetime
import threading
from typing import List, Optional, Dict, Any, Union

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from engine.trainer import train_dsac, MAX_EPISODES, DEFAULT_CAPACITY, DEFAULT_RISK, STATE_DIM, MIN_DAYS
from engine.decider import decide, has_model, load_meta
from engine.lc_kernel import resolve_lc_fruit_key

app = FastAPI(
    title="Retail Eureka - Buyer Agent Web Service",
    description=(
        "Buyer Agent DSAC Limitado (Distributional Soft Actor-Critic, 30 variáveis) a partir do código original "
        "C:\\buyerAgent\\DSAC, com o Lifecycle LC v0.2.0 embutido no ambiente de simulação. "
        "Modelos isolados por utilizador e cultura."
    ),
    version="3.0.0",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STORAGE_DIR = os.path.join(BASE_DIR, "models_storage")
os.makedirs(STORAGE_DIR, exist_ok=True)
ALGORITHM = "DSAC_Limitado"

# Um treino de cada vez por utilizador/cultura
_training_locks: Dict[str, threading.Lock] = {}
_training_locks_guard = threading.Lock()


def model_dir(user_id, culture_id, create=False) -> str:
    path = os.path.join(STORAGE_DIR, f"user_{user_id}", f"culture_{culture_id}")
    if create:
        os.makedirs(path, exist_ok=True)
    return path


def training_lock(user_id, culture_id) -> threading.Lock:
    key = f"{user_id}:{culture_id}"
    with _training_locks_guard:
        return _training_locks.setdefault(key, threading.Lock())


# ============================================================
# CONTRATOS DE DADOS
# ============================================================

class MarketRecord(BaseModel):
    date: str = Field(..., examples=["2026-08-01"])
    real_value: float = Field(..., description="Vendas reais do dia (Kg)")
    prediction: float = Field(..., description="Previsão do Forecast Web Service para esse dia (Kg) - obrigatória")
    price: Optional[float] = Field(None, description="Preço de venda (€/Kg)")
    temperature: Optional[float] = Field(None, description="Temperatura do armazém (°C) - WarehouseSensorReading")
    humidity: Optional[float] = Field(None, description="Humidade relativa (%) - WarehouseSensorReading")
    ethylene: Optional[float] = Field(None, description="Etileno (ppm) - WarehouseSensorReading")
    volume: Optional[float] = Field(None, description="Volume por unidade (m3)")


class TrainRequest(BaseModel):
    user_id: Union[int, str]
    culture_id: Union[int, str]
    fruit_key: str = Field(..., examples=["apple_gala"], description="Fruta/variedade (resolvida para um preset LC v0.2.0)")
    owner_type: str = Field("Retailer", description="Perfil do comprador para os limiares de qualidade LC (Retailer/Processor)")
    max_capacity: float = Field(DEFAULT_CAPACITY, description="Capacidade física do armazém (Kg). Modo limitado: encomenda máx. = maior venda histórica do treino")
    episodes: int = Field(MAX_EPISODES, ge=1, le=5000)
    risk_factor: float = Field(DEFAULT_RISK, gt=0.0, le=1.0)
    packaging: str = Field("bulk", description="bulk | open_box | perforated_bag | map_sealed")
    train_data: List[MarketRecord]


class DayContext(BaseModel):
    date: str
    prediction: float
    price: Optional[float] = None
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    ethylene: Optional[float] = None
    volume: Optional[float] = None


class ForecastPoint(BaseModel):
    date: str
    prediction: float


class StockLot(BaseModel):
    quantity_kg: float
    age_days: int = Field(0, ge=0, description="Dias desde a entrada do lote em armazém")


class TransitItem(BaseModel):
    quantity_kg: float
    arrival_in_days: int = Field(1, ge=0, description="0 = chega hoje (ainda não recebido), 1 = amanhã, ...")


class DecideRequest(BaseModel):
    user_id: Union[int, str]
    culture_id: Union[int, str]
    history: List[MarketRecord] = Field(..., description="Dias anteriores (mín. 2, recomendado >= 15)")
    today: DayContext
    forecast: List[ForecastPoint] = Field(default_factory=list, description="Previsões dos próximos dias (até 20)")
    stock_lots: List[StockLot] = Field(default_factory=list)
    in_transit: List[TransitItem] = Field(default_factory=list)
    last_order_qty: float = 0.0
    consecutive_oos_days: int = 0


# ============================================================
# ENDPOINTS
# ============================================================

@app.get("/", tags=["Info"])
def root_info():
    return {
        "service": "Retail Eureka - Buyer Agent Web Service",
        "status": "online",
        "architecture": "DSAC Limitado (30 variáveis) + Lifecycle LC v0.2.0 embutido",
        "features": STATE_DIM,
        "docs_url": "/docs",
    }


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "healthy", "timestamp": datetime.datetime.utcnow().isoformat()}


@app.get("/api/buyer/status", tags=["Status"])
def get_model_status(user_id: Union[int, str] = Query(...), culture_id: Union[int, str] = Query(...)):
    d = model_dir(user_id, culture_id)
    meta = load_meta(d) if has_model(d) else None
    if not meta:
        return {"user_id": user_id, "culture_id": culture_id, "has_model": False, "algorithm": ALGORITHM,
                "state_dim": STATE_DIM, "is_training": training_lock(user_id, culture_id).locked()}
    return {
        "user_id": user_id, "culture_id": culture_id, "has_model": True, "algorithm": meta["algorithm"],
        "state_dim": meta["state_dim"], "fruit_key": meta["fruit_key"], "lifecycle_engine": meta["lifecycle_engine"],
        "max_order_limit": meta["max_order_limit"], "max_capacity": meta["max_capacity"],
        "last_trained": meta["trained_at"], "avg_profit": meta["best_eval_profit"],
        "best_eval_metrics": meta.get("best_eval_metrics"), "episodes": meta.get("episodes"),
        "days_train": meta.get("days_train"), "days_eval": meta.get("days_eval"),
        "is_training": training_lock(user_id, culture_id).locked(),
    }


def _training_frame(payload: TrainRequest) -> pd.DataFrame:
    if len(payload.train_data) < MIN_DAYS:
        raise HTTPException(status_code=400, detail=f"São necessários pelo menos {MIN_DAYS} dias de histórico com previsões (recebidos {len(payload.train_data)}).")
    df = pd.DataFrame([r.model_dump() for r in payload.train_data]).rename(columns={"date": "day"})
    for col, default in (("price", 10.0), ("temperature", 22.0), ("humidity", 70.0), ("ethylene", 0.8), ("volume", 0.002)):
        df[col] = pd.to_numeric(df[col], errors="coerce")
        if df[col].isna().all():
            df[col] = default  # mesmo valor por omissão que o ambiente original usa quando a coluna não existe
        else:
            df[col] = df[col].ffill().bfill()
    df["fruit_type"] = resolve_lc_fruit_key(payload.fruit_key)
    return df


def _run_training(payload: TrainRequest, progress_cb=None):
    df = _training_frame(payload)
    d = model_dir(payload.user_id, payload.culture_id, create=True)
    return train_dsac(
        df, d, max_capacity=payload.max_capacity, risk_factor=payload.risk_factor, episodes=payload.episodes,
        use_lc=True, owner_type=payload.owner_type, packaging=payload.packaging, progress_cb=progress_cb,
        extra_meta={"user_id": str(payload.user_id), "culture_id": str(payload.culture_id),
                    "fruit_input": payload.fruit_key},
    )


def _done_message(meta):
    return {
        "event": "done", "status": "success",
        "message": f"Buyer Agent DSAC Limitado treinado em {meta['training_time_seconds']}s ({meta['episodes']} episódios, {meta['lifecycle_engine']}).",
        "fruit_key": meta["fruit_key"], "max_order_limit": meta["max_order_limit"],
        "avg_profit": meta["best_eval_profit"], "best_eval_metrics": meta["best_eval_metrics"],
        "training_time_seconds": meta["training_time_seconds"], "trained_at": meta["trained_at"],
    }


@app.post("/api/buyer/train", tags=["Training"])
def train_buyer_policy(payload: TrainRequest):
    lock = training_lock(payload.user_id, payload.culture_id)
    if not lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Já existe um treino a decorrer para este utilizador/cultura.")
    try:
        return _done_message(_run_training(payload))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        lock.release()


@app.post("/api/buyer/train/stream", tags=["Training"])
def train_buyer_policy_stream(payload: TrainRequest):
    """Server-Sent Events: um evento por episódio {episode, total_episodes, episode_profit, avg_profit, eval_profit?} e no fim {event: done}."""
    lock = training_lock(payload.user_id, payload.culture_id)
    if not lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Já existe um treino a decorrer para este utilizador/cultura.")
    try:
        _training_frame(payload)  # valida antes de abrir o stream
    except HTTPException:
        lock.release()
        raise
    except ValueError as e:
        lock.release()
        raise HTTPException(status_code=400, detail=str(e))

    q: "queue.Queue" = queue.Queue()
    profits: List[float] = []

    def cb(event):
        profits.append(event["episode_profit"])
        window = profits[-20:]
        event["avg_profit"] = round(sum(window) / len(window), 2)
        q.put(event)

    def worker():
        try:
            q.put(_done_message(_run_training(payload, progress_cb=cb)))
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
            yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


def _heuristics(stock_total, in_transit, pred_today, forecast):
    """Políticas de referência mostradas na interface ao lado da decisão DSAC."""
    nxt = [f.prediction for f in forecast]
    pos = stock_total + in_transit
    next3 = sum(nxt[:3]) if nxt else pred_today * 3
    tomorrow = nxt[0] if nxt else pred_today
    dos_3d = max(0.0, next3 - pos)
    naive = max(0.0, tomorrow - max(0.0, stock_total - pred_today) - in_transit)
    s_min, s_max = 2.0 * pred_today, 5.0 * pred_today
    min_max = max(0.0, s_max - pos) if pos < s_min else 0.0
    return {"dos_3d_kg": round(dos_3d, 1), "cnn_naive_kg": round(naive, 1), "min_max_kg": round(min_max, 1)}


@app.post("/api/buyer/decide", tags=["Inference"])
def decide_order(payload: DecideRequest):
    d = model_dir(payload.user_id, payload.culture_id)
    if not has_model(d):
        raise HTTPException(status_code=404, detail="Não existe modelo DSAC treinado para este utilizador/cultura. Treine o Buyer Agent primeiro.")
    if len(payload.history) < 2:
        raise HTTPException(status_code=400, detail="São necessários pelo menos 2 dias de histórico (vendas reais e previsões).")
    try:
        result = decide(
            d,
            history=[h.model_dump() for h in payload.history],
            today=payload.today.model_dump(),
            forecast=[f.model_dump() for f in payload.forecast],
            stock_lots=[s.model_dump() for s in payload.stock_lots],
            in_transit=[t.model_dump() for t in payload.in_transit],
            last_order_qty=payload.last_order_qty,
            consecutive_oos_days=payload.consecutive_oos_days,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    s = result["state_summary"]
    return {
        "status": "success",
        "user_id": payload.user_id,
        "culture_id": payload.culture_id,
        "decision_date": payload.today.date,
        "price_today": payload.today.price,
        **result,
        "heuristics_comparison": _heuristics(s["total_stock_kg"], s["in_transit_kg"], payload.today.prediction, payload.forecast),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", "8002")), reload=False)
