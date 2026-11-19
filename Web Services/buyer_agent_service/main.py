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

from engine.trainer import train_dsac, MAX_EPISODES, DEFAULT_CAPACITY, DEFAULT_RISK, STATE_DIM, MIN_DAYS, TRAIN_SPLIT
from engine.decider import decide, has_model, load_meta
from engine.lc_kernel import resolve_lc_fruit_key
from engine.heuristics import heuristic_orders
from engine.validation import DEFAULT_TEST_FRACTION, MIN_TEST_DAYS, check_split, load_report, run_validation
from engine import simulation as sim_engine

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
    age_days: int = Field(0, ge=0, description="Dias de envelhecimento desde o estado inicial (receção ou colheita)")
    # Estado inicial medido (opcional). Sem valores, usa os valores por omissão da variedade (comportamento anterior).
    firmness: Optional[float] = Field(None, description="Firmeza inicial medida (N)")
    brix: Optional[float] = Field(None, description="Brix inicial medido (°Bx)")
    acidity: Optional[float] = Field(None, description="Acidez inicial medida")


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


def _market_frame(records, fruit_key, min_days=MIN_DAYS) -> pd.DataFrame:
    if len(records) < min_days:
        raise HTTPException(status_code=400, detail=f"São necessários pelo menos {min_days} dias de histórico com previsões (recebidos {len(records)}).")
    df = pd.DataFrame([r.model_dump() for r in records]).rename(columns={"date": "day"})
    for col, default in (("price", 10.0), ("temperature", 22.0), ("humidity", 70.0), ("ethylene", 0.8), ("volume", 0.002)):
        df[col] = pd.to_numeric(df[col], errors="coerce")
        if df[col].isna().all():
            df[col] = default  # mesmo valor por omissão que o ambiente original usa quando a coluna não existe
        else:
            df[col] = df[col].ffill().bfill()
    df["fruit_type"] = resolve_lc_fruit_key(fruit_key)
    return df


def _training_frame(payload: TrainRequest) -> pd.DataFrame:
    return _market_frame(payload.train_data, payload.fruit_key)


def _training_periods(df):
    """Datas dos dias usados para ajustar os pesos (primeiros TRAIN_SPLIT) e para escolher o melhor modelo (restantes)."""
    days = sorted(pd.to_datetime(df["day"]).dt.strftime("%Y-%m-%d"))
    split = int(len(days) * TRAIN_SPLIT)
    if split <= 0 or split >= len(days):
        return {}
    return {"weights_train_from": days[0], "weights_train_to": days[split - 1],
            "selection_from": days[split], "selection_to": days[-1]}


def _run_training(payload: TrainRequest, progress_cb=None):
    df = _training_frame(payload)
    d = model_dir(payload.user_id, payload.culture_id, create=True)
    return train_dsac(
        df, d, max_capacity=payload.max_capacity, risk_factor=payload.risk_factor, episodes=payload.episodes,
        use_lc=True, owner_type=payload.owner_type, packaging=payload.packaging, progress_cb=progress_cb,
        extra_meta={"user_id": str(payload.user_id), "culture_id": str(payload.culture_id),
                    "fruit_input": payload.fruit_key, **_training_periods(df)},
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


class ValidateRequest(BaseModel):
    user_id: Union[int, str]
    culture_id: Union[int, str]
    test_fraction: float = Field(DEFAULT_TEST_FRACTION, ge=0.05, le=0.5,
                                 description="Fração final do histórico usada como período de teste (0.2 = últimos 20 %)")
    train_data: List[MarketRecord] = Field(..., description="Histórico com vendas reais e previsões (o mesmo formato do treino)")


@app.get("/api/buyer/validation", tags=["Validation"])
def get_validation_report(user_id: Union[int, str] = Query(...), culture_id: Union[int, str] = Query(...)):
    d = model_dir(user_id, culture_id)
    report = load_report(d) if has_model(d) else None
    return {"user_id": user_id, "culture_id": culture_id, "has_model": has_model(d), "has_report": report is not None,
            "is_running": training_lock(user_id, f"{culture_id}:validation").locked(), "report": report}


@app.post("/api/buyer/validate/stream", tags=["Validation"])
def validate_buyer_policy_stream(payload: ValidateRequest):
    """
    Valida o Buyer Agent JÁ TREINADO nos últimos `test_fraction` dias: simula, dia a dia, o agente e as regras
    clássicas com as vendas, preços e clima reais. Não treina nada nem altera o modelo.
    Server-Sent Events: {event: split}, {event: backtest} por política e no fim {event: done, report}.
    """
    d = model_dir(payload.user_id, payload.culture_id)
    if not has_model(d):
        raise HTTPException(status_code=404, detail="Não existe modelo do Buyer Agent treinado para esta cultura. Treine o agente primeiro.")
    lock = training_lock(payload.user_id, f"{payload.culture_id}:validation")
    if not lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Já existe uma validação a decorrer para este utilizador/cultura.")
    try:
        df = _market_frame(payload.train_data, load_meta(d)["fruit_key"], min_days=MIN_TEST_DAYS)
        check_split(len(df), payload.test_fraction)
    except HTTPException:
        lock.release()
        raise
    except ValueError as e:
        lock.release()
        raise HTTPException(status_code=400, detail=str(e))

    q: "queue.Queue" = queue.Queue()

    def worker():
        try:
            report = run_validation(df, d, test_fraction=payload.test_fraction, progress_cb=q.put)
            q.put({"event": "done", "status": "success", "report": report})
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


# ============================================================
# SIMULAÇÃO DIA A DIA (modelo já treinado, sem treino)
# ============================================================

class SimulationStartRequest(BaseModel):
    user_id: Union[int, str]
    culture_id: Union[int, str]
    start_date: Optional[str] = Field(None, description="Primeiro dia a simular (por omissão, início dos últimos 20 % do histórico)")
    initial_stock_kg: Optional[float] = Field(None, ge=0, description="Stock no início (por omissão 100 kg, como no treino)")
    train_data: List[MarketRecord] = Field(..., description="Histórico com vendas reais e previsões (o mesmo formato do treino)")


class SimulationTodayRequest(BaseModel):
    user_id: Union[int, str]
    culture_id: Union[int, str]
    prediction: Optional[float] = None
    prediction_tomorrow: Optional[float] = None
    price: Optional[float] = None
    temperature: Optional[float] = None
    humidity: Optional[float] = None


class SimulationStepRequest(BaseModel):
    user_id: Union[int, str]
    culture_id: Union[int, str]
    order_kg: float = Field(..., ge=0, description="Encomenda feita no dia atual (chega amanhã)")
    demand_kg: float = Field(..., ge=0, description="Procura real do dia atual")


class SimulationRef(BaseModel):
    user_id: Union[int, str]
    culture_id: Union[int, str]


def _sim_call(user_id, culture_id, action):
    """Executa uma ação sobre a simulação (uma de cada vez por utilizador/cultura) e devolve a vista atualizada."""
    d = model_dir(user_id, culture_id)
    if not has_model(d):
        raise HTTPException(status_code=404, detail="Não existe modelo do Buyer Agent treinado para esta cultura. Treine o agente primeiro.")
    lock = training_lock(user_id, f"{culture_id}:simulation")
    with lock:
        try:
            sim = action(d)
            return {"status": "success", "has_model": True, "has_simulation": True, "view": sim_engine.build_view(d, sim)}
        except sim_engine.SimulationError as e:
            raise HTTPException(status_code=400, detail=str(e))


def _existing_sim(d):
    sim = sim_engine.load_sim(d)
    if sim is None:
        raise sim_engine.SimulationError("Não há nenhuma simulação iniciada para esta cultura.")
    return sim


@app.get("/api/buyer/simulation", tags=["Simulation"])
def get_simulation(user_id: Union[int, str] = Query(...), culture_id: Union[int, str] = Query(...)):
    d = model_dir(user_id, culture_id)
    if not has_model(d):
        return {"status": "success", "has_model": False, "has_simulation": False}
    if sim_engine.load_sim(d) is None:
        return {"status": "success", "has_model": True, "has_simulation": False}
    return _sim_call(user_id, culture_id, _existing_sim)


@app.post("/api/buyer/simulation/start", tags=["Simulation"])
def start_simulation(payload: SimulationStartRequest):
    """Começa (ou recomeça) a simulação dia a dia a partir de um dia do histórico. Não treina o modelo."""
    d = model_dir(payload.user_id, payload.culture_id)
    if not has_model(d):
        raise HTTPException(status_code=404, detail="Não existe modelo do Buyer Agent treinado para esta cultura. Treine o agente primeiro.")
    df = _market_frame(payload.train_data, load_meta(d)["fruit_key"], min_days=sim_engine.MIN_CONTEXT_DAYS + 1)
    return _sim_call(payload.user_id, payload.culture_id, lambda dd: sim_engine.start_simulation(
        dd, df, start_date=payload.start_date, initial_stock_kg=payload.initial_stock_kg))


@app.post("/api/buyer/simulation/today", tags=["Simulation"])
def simulation_update_today(payload: SimulationTodayRequest):
    """Altera as condições do dia atual (previsões, preço, clima) e recalcula a recomendação."""
    values = payload.model_dump(exclude={"user_id", "culture_id"})
    return _sim_call(payload.user_id, payload.culture_id, lambda dd: sim_engine.update_today(dd, _existing_sim(dd), values))


@app.post("/api/buyer/simulation/step", tags=["Simulation"])
def simulation_step(payload: SimulationStepRequest):
    """Fecha o dia atual (encomenda feita + procura real) e devolve a recomendação para o dia seguinte."""
    return _sim_call(payload.user_id, payload.culture_id,
                     lambda dd: sim_engine.advance_day(dd, _existing_sim(dd), payload.order_kg, payload.demand_kg))


@app.post("/api/buyer/simulation/undo", tags=["Simulation"])
def simulation_undo(payload: SimulationRef):
    return _sim_call(payload.user_id, payload.culture_id, lambda dd: sim_engine.undo_day(dd, _existing_sim(dd)))


@app.delete("/api/buyer/simulation", tags=["Simulation"])
def simulation_delete(user_id: Union[int, str] = Query(...), culture_id: Union[int, str] = Query(...)):
    d = model_dir(user_id, culture_id)
    sim_engine.delete_sim(d)
    return {"status": "success", "has_model": has_model(d), "has_simulation": False}


def _heuristics(stock_total, in_transit, pred_today, forecast):
    """Políticas de referência mostradas na interface ao lado da decisão DSAC."""
    return heuristic_orders(stock_total, in_transit, pred_today, [f.prediction for f in forecast])


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
