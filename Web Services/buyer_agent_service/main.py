import os
import json
import math
import datetime
from typing import List, Optional, Dict, Any, Union
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import numpy as np
import pandas as pd
import torch

from engine.actor_critic_v2 import ActorMLP
from engine.training_engine import train_buyer_agent

app = FastAPI(
    title="Retail Eureka - Buyer Agent Web Service",
    description="Microserviço independente de Tomada de Decisão de Compras e Encomendas (PPO Reinforcement Learning) com isolamento multi-tenant por utilizador e cultura.",
    version="1.0.0"
)

# Permitir CORS para chamadas da plataforma Django ou clientes externos
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STORAGE_DIR = os.path.join(BASE_DIR, "models_storage")
os.makedirs(STORAGE_DIR, exist_ok=True)


def get_culture_model_dir(user_id: Union[int, str], culture_id: Union[int, str]) -> str:
    """ Retorna a pasta de armazenamento isolada para o utilizador e cultura. """
    path = os.path.join(STORAGE_DIR, f"user_{user_id}", f"culture_{culture_id}")
    os.makedirs(path, exist_ok=True)
    return path


# ============================================================
# PYDANTIC SCHEMAS (CONTRATOS DE DADOS)
# ============================================================

class MarketRecord(BaseModel):
    date: str = Field(..., example="2026-08-01", description="Data no formato YYYY-MM-DD")
    real_value: float = Field(..., example=120.0, description="Vendas/procura real registada em Kg")
    prediction: float = Field(..., example=125.0, description="Previsão gerada pelo Forecast Agent em Kg")
    price: Optional[float] = Field(2.0, example=2.15, description="Preço de venda por Kg")
    temperature: Optional[float] = Field(1.5, example=1.5, description="Temperatura em câmara fria (°C)")
    humidity: Optional[float] = Field(92.0, example=92.0, description="Humidade relativa (%)")
    ethylene: Optional[float] = Field(0.05, example=0.05, description="Nível de etileno (ppm)")
    volume: Optional[float] = Field(0.002, example=0.002, description="Volume do produto por Kg (m3)")


class TrainRequest(BaseModel):
    user_id: Union[int, str] = Field(..., example=1, description="ID do Utilizador na plataforma")
    culture_id: Union[int, str] = Field(..., example=3, description="ID da Cultura / Subfamília de produto")
    fruit_key: Optional[str] = Field("maca_gala", example="maca_gala", description="Preset biológico: maca_gala, maca_fuji, kiwi_hayward, maca_golden, maca_reineta")
    max_capacity: Optional[float] = Field(500.0, example=500.0, description="Capacidade máxima de armazenamento em armazém")
    episodes: Optional[int] = Field(300, example=300, description="Número de episódios de simulação PPO para treino")
    train_data: List[MarketRecord] = Field(..., description="Série histórica de mercado com previsões integradas")


class TrainResponse(BaseModel):
    status: str
    message: str
    user_id: Union[int, str]
    culture_id: Union[int, str]
    fruit_key: str
    max_order_limit: float
    avg_profit: float
    training_time_seconds: float
    saved_path: str
    trained_at: str


class DecideRequest(BaseModel):
    user_id: Union[int, str] = Field(..., example=1, description="ID do Utilizador")
    culture_id: Union[int, str] = Field(..., example=3, description="ID da Cultura")
    date: Optional[str] = Field(None, example="2026-09-16", description="Data da decisão (default: hoje)")
    current_stock_profile: Optional[List[float]] = Field(
        None, example=[50.0, 20.0, 10.0, 5.0],
        description="Stock por prateleira [G0 (>=4d), G1 (3d), G2 (2d), G3 (1d)] em Kg"
    )
    current_stock_total_kg: Optional[float] = Field(
        None, example=85.0,
        description="Stock total em armazém em Kg (usado se current_stock_profile não for fornecido)"
    )
    in_transit_kg: float = Field(0.0, example=0.0, description="Quantidade já encomendada a chegar amanhã")
    prediction_today_kg: float = Field(..., example=140.0, description="Previsão de procura para hoje em Kg")
    prediction_tomorrow_kg: Optional[float] = Field(None, example=135.0, description="Previsão de procura para amanhã em Kg")
    recent_sales_lags: Optional[List[float]] = Field(
        None, example=[130.0, 125.0],
        description="Vendas reais mais recentes [t-1, t-2] em Kg"
    )
    price_today: Optional[float] = Field(2.0, example=2.15, description="Preço de venda hoje por Kg")
    recent_prices: Optional[List[float]] = Field(
        None, example=[2.10, 2.15, 2.05, 2.20],
        description="Histórico de preços recentes (janela de 15 dias)"
    )
    max_capacity: Optional[float] = Field(None, example=500.0, description="Capacidade máxima de armazém (sobrescreve o default)")
    max_order_limit: Optional[float] = Field(None, example=200.0, description="Limite máximo diário de encomenda")


class HeuristicsComparison(BaseModel):
    dos_3d_kg: float = Field(..., description="Recomendação baseada em Days of Supply (3 dias)")
    cnn_naive_kg: float = Field(..., description="Recomendação Heurística Naive (Procura amanhã - stock fim do dia)")
    min_max_kg: float = Field(..., description="Recomendação baseada em política clássica Min-Max")


class StateSummary(BaseModel):
    total_stock_kg: float
    coverage_days: float
    urgency_index: float
    in_transit_kg: float
    forecast_today_kg: float
    forecast_tomorrow_kg: float


class DecideResponse(BaseModel):
    status: str
    user_id: Union[int, str]
    culture_id: Union[int, str]
    decision_date: str
    recommended_order_kg: float
    order_percentage: float
    state_summary: StateSummary
    heuristics_comparison: HeuristicsComparison
    model_metadata: Dict[str, Any]


class StatusResponse(BaseModel):
    user_id: Union[int, str]
    culture_id: Union[int, str]
    has_model: bool
    fruit_key: Optional[str] = None
    max_order_limit: Optional[float] = None
    max_capacity: Optional[float] = None
    last_trained: Optional[str] = None
    avg_profit: Optional[float] = None


# ============================================================
# ROTAS / ENDPOINTS DA API
# ============================================================

@app.get("/", tags=["Info"])
def root_info():
    return {
        "service": "Retail Eureka - Buyer Agent Web Service",
        "status": "online",
        "architecture": "Federated Microservice (PPO Reinforcement Learning)",
        "docs_url": "/docs"
    }


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "healthy", "timestamp": datetime.datetime.utcnow().isoformat()}


@app.get("/api/buyer/status", response_model=StatusResponse, tags=["Status"])
def get_model_status(
    user_id: Union[int, str] = Query(..., description="ID do Utilizador"),
    culture_id: Union[int, str] = Query(..., description="ID da Cultura")
):
    """ Verifica se o utilizador já tem um agente de compras treinado para a cultura especificada. """
    model_dir = get_culture_model_dir(user_id, culture_id)
    actor_path = os.path.join(model_dir, "actor.pth")
    meta_path = os.path.join(model_dir, "meta.json")

    if not os.path.exists(actor_path) or not os.path.exists(meta_path):
        return StatusResponse(
            user_id=user_id,
            culture_id=culture_id,
            has_model=False
        )

    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        return StatusResponse(
            user_id=user_id,
            culture_id=culture_id,
            has_model=True,
            fruit_key=meta.get("fruit_key"),
            max_order_limit=meta.get("max_order_limit"),
            max_capacity=meta.get("max_capacity"),
            last_trained=meta.get("trained_at"),
            avg_profit=meta.get("avg_profit")
        )
    except Exception as e:
        return StatusResponse(
            user_id=user_id,
            culture_id=culture_id,
            has_model=True,
            last_trained=None
        )


@app.post("/api/buyer/train", response_model=TrainResponse, tags=["Training"])
def train_buyer_policy(payload: TrainRequest):
    """
    Treina uma política personalizada de PPO para o utilizador e cultura especificados.
    Recebe os dados históricos com vendas reais e previsões já enriquecidas.
    """
    if len(payload.train_data) < 7:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A série histórica deve conter no mínimo 7 registos diários para treinar o Buyer Agent."
        )

    # 1. Converter payload em DataFrame
    records = [r.dict() for r in payload.train_data]
    df = pd.DataFrame(records)

    save_dir = get_culture_model_dir(payload.user_id, payload.culture_id)

    try:
        result = train_buyer_agent(
            data=df,
            save_dir=save_dir,
            user_id=payload.user_id,
            culture_id=payload.culture_id,
            fruit_key=payload.fruit_key or "maca_gala",
            max_capacity=payload.max_capacity or 500.0,
            total_episodes=payload.episodes or 300
        )
        return TrainResponse(**result)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro durante o treino do Buyer Agent: {str(e)}"
        )


@app.post("/api/buyer/decide", response_model=DecideResponse, tags=["Inference"])
def make_buying_decision(payload: DecideRequest):
    """
    Calcula a recomendação ótima de encomenda para hoje com base no estado de stock e mercado.
    Retorna também a comparação com baselines heurísticas (DOS 3D, CNN Naive, Min-Max).
    """
    model_dir = get_culture_model_dir(payload.user_id, payload.culture_id)
    actor_path = os.path.join(model_dir, "actor.pth")
    meta_path = os.path.join(model_dir, "meta.json")

    # Carregar metadados ou aplicar fallbacks
    meta = {}
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except Exception:
            pass

    max_capacity = float(payload.max_capacity or meta.get("max_capacity", 500.0))
    max_order_limit = float(payload.max_order_limit or meta.get("max_order_limit", 200.0))

    # Preparar Stock Profile [G0, G1, G2, G3]
    if payload.current_stock_profile and len(payload.current_stock_profile) == 4:
        stock_profile = [float(x) for x in payload.current_stock_profile]
    elif payload.current_stock_total_kg is not None:
        tot = float(payload.current_stock_total_kg)
        # Distribuir por defeito no bucket de maior validade G0
        stock_profile = [tot, 0.0, 0.0, 0.0]
    else:
        stock_profile = [100.0, 0.0, 0.0, 0.0]

    total_stock_kg = sum(stock_profile)
    in_transit_kg = float(payload.in_transit_kg)
    pred_today = float(payload.prediction_today_kg)
    pred_tomorrow = float(payload.prediction_tomorrow_kg if payload.prediction_tomorrow_kg is not None else pred_today)

    # Vendas reais passadas
    if payload.recent_sales_lags and len(payload.recent_sales_lags) >= 2:
        real_t_minus_1 = float(payload.recent_sales_lags[0])
        real_t_minus_2 = float(payload.recent_sales_lags[1])
    elif payload.recent_sales_lags and len(payload.recent_sales_lags) == 1:
        real_t_minus_1 = float(payload.recent_sales_lags[0])
        real_t_minus_2 = real_t_minus_1
    else:
        real_t_minus_1 = pred_today
        real_t_minus_2 = pred_today

    # Extração de componentes temporais e sazonais
    if payload.date:
        try:
            dt = datetime.datetime.strptime(payload.date, "%Y-%m-%d").date()
        except Exception:
            dt = datetime.date.today()
    else:
        dt = datetime.date.today()

    day_of_week = dt.isoweekday()  # 1..7
    day_of_year = dt.timetuple().tm_yday  # 1..366
    month = dt.month  # 1..12

    sin_day = math.sin(2 * math.pi * day_of_week / 7.0)
    cos_day = math.cos(2 * math.pi * day_of_week / 7.0)
    sin_month = math.sin(2 * math.pi * month / 12.0)
    cos_month = math.cos(2 * math.pi * month / 12.0)

    # Preço relativo (z-score)
    price_today = float(payload.price_today or 2.0)
    if payload.recent_prices and len(payload.recent_prices) > 0:
        prices_window = [float(p) for p in payload.recent_prices]
        if price_today not in prices_window:
            prices_window.append(price_today)
        m_p = np.mean(prices_window)
        s_p = np.std(prices_window)
        preco_relativo = (price_today - m_p) / (s_p + 1e-8)
    else:
        preco_relativo = 0.0

    preco_relativo_safe = float(np.clip(preco_relativo, -3.0, 3.0))

    # Features de engenharia
    cobertura_dias = total_stock_kg / (pred_today + 1e-8)
    cobertura_norm = float(np.clip(cobertura_dias, 0, 7) / 7.0)
    urgencia_norm = float(stock_profile[3] / (total_stock_kg + 1e-8))

    erro_previsao = (real_t_minus_1 - pred_today) / (pred_today + 1e-8)
    erro_norm = float(np.clip(erro_previsao, -1.0, 1.0))

    # Montagem do vetor de 17 variáveis
    via1_absolutas = [
        stock_profile[0],
        stock_profile[1],
        stock_profile[2],
        stock_profile[3],
        in_transit_kg,
        pred_today,
        pred_tomorrow,
        real_t_minus_1,
        real_t_minus_2
    ]

    # Obter limites do scaler a partir dos metadados
    scaler_min = meta.get("scaler_min", [0.0] * 9)
    scaler_max = meta.get("scaler_max", [max_capacity] * 5 + [max(100.0, max_order_limit * 1.5)] * 4)

    scaled_via1 = []
    for val, s_min, s_max in zip(via1_absolutas, scaler_min, scaler_max):
        denom = max(1e-6, s_max - s_min)
        scaled_via1.append(float(np.clip((val - s_min) / denom, 0.0, 1.0)))

    via2_bypass = [
        preco_relativo_safe,
        sin_day,
        cos_day,
        sin_month,
        cos_month,
        cobertura_norm,
        urgencia_norm,
        erro_norm
    ]

    state_17 = np.concatenate([scaled_via1, via2_bypass]).astype(np.float32)

    # Executar Inferência do Agente (ou Heurística Base se modelo não existir)
    order_percentage = 0.0
    recommended_order_kg = 0.0

    if os.path.exists(actor_path):
        try:
            actor = ActorMLP(state_dim=17, action_dim=1, max_action=max_order_limit)
            actor.load_state_dict(torch.load(actor_path, map_location='cpu', weights_only=False))
            actor.eval()

            with torch.no_grad():
                st_tensor = torch.FloatTensor(state_17).unsqueeze(0)
                action_mean, _ = actor(st_tensor)
                order_percentage = float(action_mean.numpy().flatten()[0])

            # Escalar e aplicar constrangimentos físicos de capacidade
            available_capacity = max(0.0, max_capacity - total_stock_kg)
            raw_order = order_percentage * max_order_limit
            constrained_order = min(raw_order, max_order_limit, available_capacity)
            recommended_order_kg = float(round(max(0.0, constrained_order)))
        except Exception as e:
            # Fallback seguro caso haja erro na leitura do ficheiro .pth
            pass

    if not os.path.exists(actor_path) or recommended_order_kg == 0.0:
        # Fallback Heurístico DOS-3D caso não haja modelo treinado
        current_available = total_stock_kg + in_transit_kg
        demand_need = (pred_today + pred_tomorrow) - current_available
        if not os.path.exists(actor_path):
            recommended_order_kg = float(round(max(0.0, min(demand_need, max_capacity - total_stock_kg, max_order_limit))))
            order_percentage = float(recommended_order_kg / (max_order_limit + 1e-8))

    # Calcular Baselines para comparação
    total_pipeline = total_stock_kg + in_transit_kg
    # 1. DOS 3-Day
    dos_3d_kg = float(round(max(0.0, (pred_today + pred_tomorrow * 2) - total_pipeline)))
    # 2. CNN Naive
    stock_fim_do_dia = max(0.0, total_pipeline - pred_today)
    cnn_naive_kg = float(round(max(0.0, pred_tomorrow - stock_fim_do_dia)))
    # 3. Min-Max
    min_thresh = max_capacity * 0.2
    target_stock = max_capacity * 0.5
    min_max_kg = float(round(max(0.0, target_stock - total_pipeline))) if total_pipeline <= min_thresh else 0.0

    return DecideResponse(
        status="success",
        user_id=payload.user_id,
        culture_id=payload.culture_id,
        decision_date=dt.isoformat(),
        recommended_order_kg=recommended_order_kg,
        order_percentage=round(order_percentage, 4),
        state_summary=StateSummary(
            total_stock_kg=round(total_stock_kg, 2),
            coverage_days=round(cobertura_dias, 2),
            urgency_index=round(urgencia_norm, 4),
            in_transit_kg=round(in_transit_kg, 2),
            forecast_today_kg=round(pred_today, 2),
            forecast_tomorrow_kg=round(pred_tomorrow, 2)
        ),
        heuristics_comparison=HeuristicsComparison(
            dos_3d_kg=dos_3d_kg,
            cnn_naive_kg=cnn_naive_kg,
            min_max_kg=min_max_kg
        ),
        model_metadata={
            "fruit_key": meta.get("fruit_key", "maca_gala"),
            "max_order_limit": max_order_limit,
            "max_capacity": max_capacity,
            "trained_at": meta.get("trained_at", "pre-trained/heuristic"),
            "has_trained_model": os.path.exists(actor_path)
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=True)

