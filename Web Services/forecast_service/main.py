import os
import io
import datetime
from typing import List, Optional, Dict, Any, Union
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import pandas as pd

from engine.mlp_engine import train_mlp_model, predict_mlp_horizon
from engine.autoformer_engine import train_model as train_autoformer_model, predict_horizon as predict_autoformer_horizon

app = FastAPI(
    title="Retail Eureka - Demand Forecast Web Service",
    description="Microserviço independente de Previsão de Procura (MLP e Autoformer) com isolamento de modelos por utilizador e cultura.",
    version="1.1.0"
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


def get_user_storage_dir(user_id: Union[int, str]) -> str:
    """
    Garante e retorna o caminho da pasta isolada para o utilizador especificado.
    Exemplo: models_storage/user_1/
    """
    user_dir = os.path.join(STORAGE_DIR, f"user_{user_id}")
    os.makedirs(user_dir, exist_ok=True)
    return user_dir


# ============================================================
# PYDANTIC SCHEMAS (CONTRATOS DE DADOS)
# ============================================================

class HistoricalSaleItem(BaseModel):
    date: str = Field(..., example="2026-08-01", description="Data da venda YYYY-MM-DD")
    sales_quantity_kg: float = Field(..., example=125.5, description="Quantidade vendida em Kg")
    price_per_kg: Optional[float] = Field(2.0, example=2.15, description="Preço de venda por Kg")


class TrainRequest(BaseModel):
    user_id: Union[int, str] = Field(..., example=1, description="ID do Utilizador autenticado na plataforma")
    culture_id: Union[int, str] = Field(..., example=3, description="ID da Cultura / Subfamília de produto")
    model_type: str = Field("mlp", example="mlp", description="Tipo de modelo: 'mlp' ou 'autoformer'")
    sales_history: List[HistoricalSaleItem] = Field(..., description="Lista de dados históricos diários")


class TrainResponse(BaseModel):
    status: str
    message: str
    user_id: Union[int, str]
    culture_id: Union[int, str]
    model_type: str
    saved_file: str
    samples_used: int
    trained_at: str


class PredictRequest(BaseModel):
    user_id: Union[int, str] = Field(..., example=1, description="ID do Utilizador")
    culture_id: Union[int, str] = Field(..., example=3, description="ID da Cultura")
    model_type: Optional[str] = Field("mlp", example="mlp", description="Tipo de modelo a utilizar ('mlp' ou 'autoformer')")
    horizon_days: int = Field(30, example=30, description="Número de dias futuros a prever")
    start_date: Optional[str] = Field(None, example="2026-09-16", description="Data inicial da previsão (default: hoje)")
    recent_sales_lags: List[float] = Field(..., example=[120.0, 130.0, 140.0, 115.0, 125.0, 130.0, 135.0], description="Últimos valores reais registados (mínimo 7 para lags)")
    avg_price: Optional[float] = Field(2.0, example=2.15, description="Preço médio de mercado de referência")


class PredictionDay(BaseModel):
    date: str
    predicted_kg: float


class PredictResponse(BaseModel):
    status: str
    user_id: Union[int, str]
    culture_id: Union[int, str]
    model_type: str
    horizon_days: int
    predictions: List[PredictionDay]


class StatusResponse(BaseModel):
    user_id: Union[int, str]
    culture_id: Union[int, str]
    has_model: bool
    available_models: List[str]
    last_modified: Optional[str] = None


# ============================================================
# ROTAS / ENDPOINTS DA API
# ============================================================

@app.get("/", tags=["Info"])
def root_info():
    return {
        "service": "Retail Eureka - Demand Forecast Web Service",
        "status": "online",
        "architecture": "Federated Microservice (Per-User Storage)",
        "supported_models": ["mlp", "autoformer"],
        "docs_url": "/docs"
    }


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "healthy", "timestamp": datetime.datetime.utcnow().isoformat()}


@app.get("/api/forecast/status", response_model=StatusResponse, tags=["Forecast"])
def get_forecast_status(
    user_id: Union[int, str] = Query(..., description="ID do Utilizador"),
    culture_id: Union[int, str] = Query(..., description="ID da Cultura / Subfamília")
):
    """
    Verifica se já existe modelo treinado na pasta do utilizador para a cultura especificada.
    """
    user_dir = get_user_storage_dir(user_id)
    available = []
    last_mod = None
    
    mlp_file = os.path.join(user_dir, f"culture_{culture_id}_mlp.joblib")
    auto_file = os.path.join(user_dir, f"culture_{culture_id}_autoformer.pt")
    
    if os.path.exists(mlp_file):
        available.append("mlp")
        mtime = os.path.getmtime(mlp_file)
        last_mod = datetime.datetime.fromtimestamp(mtime).isoformat()
        
    if os.path.exists(auto_file):
        available.append("autoformer")
        mtime = os.path.getmtime(auto_file)
        last_mod = datetime.datetime.fromtimestamp(mtime).isoformat()
        
    return StatusResponse(
        user_id=user_id,
        culture_id=culture_id,
        has_model=len(available) > 0,
        available_models=available,
        last_modified=last_mod
    )


@app.post("/api/forecast/train", response_model=TrainResponse, tags=["Forecast"])
def train_forecast_model(payload: TrainRequest):
    """
    Treina o modelo de previsão (MLP ou Autoformer) e guarda o artefacto na subpasta do utilizador.
    """
    if len(payload.sales_history) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="São necessários pelo menos 10 dias de histórico para treinar o modelo."
        )
        
    df_data = pd.DataFrame([item.dict() for item in payload.sales_history])
    model_type = payload.model_type.lower()
    user_dir = get_user_storage_dir(payload.user_id)
    
    try:
        if model_type == "autoformer":
            binary_data = train_autoformer_model(df_data)
            filename = f"culture_{payload.culture_id}_autoformer.pt"
            filepath = os.path.join(user_dir, filename)
            with open(filepath, "wb") as f:
                f.write(binary_data)
        elif model_type == "mlp":
            binary_data = train_mlp_model(df_data)
            filename = f"culture_{payload.culture_id}_mlp.joblib"
            filepath = os.path.join(user_dir, filename)
            with open(filepath, "wb") as f:
                f.write(binary_data)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"model_type desconhecido: '{model_type}'. Use 'mlp' ou 'autoformer'."
            )
            
        relative_saved_path = f"user_{payload.user_id}/{filename}"
        
        return TrainResponse(
            status="SUCCESS",
            message=f"Modelo {model_type.upper()} treinado e gravado com sucesso para o utilizador {payload.user_id}.",
            user_id=payload.user_id,
            culture_id=payload.culture_id,
            model_type=model_type,
            saved_file=relative_saved_path,
            samples_used=len(df_data),
            trained_at=datetime.datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro durante o treino do modelo: {str(e)}"
        )


@app.post("/api/forecast/predict", response_model=PredictResponse, tags=["Forecast"])
def predict_forecast(payload: PredictRequest):
    """
    Executa inferência com o modelo treinado que reside na pasta do utilizador.
    """
    model_type = payload.model_type.lower() if payload.model_type else "mlp"
    user_dir = get_user_storage_dir(payload.user_id)
    
    filename = f"culture_{payload.culture_id}_{model_type}.joblib" if model_type == "mlp" else f"culture_{payload.culture_id}_{model_type}.pt"
    filepath = os.path.join(user_dir, filename)
    
    # Fallback: Se não encontrar o modelo pedido, procurar o outro formato na pasta do user
    if not os.path.exists(filepath):
        alt_type = "autoformer" if model_type == "mlp" else "mlp"
        alt_filename = f"culture_{payload.culture_id}_{alt_type}.pt" if alt_type == "autoformer" else f"culture_{payload.culture_id}_{alt_type}.joblib"
        alt_filepath = os.path.join(user_dir, alt_filename)
        
        if os.path.exists(alt_filepath):
            filepath = alt_filepath
            model_type = alt_type
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Nenhum modelo treinado encontrado para user_id={payload.user_id} e culture_id={payload.culture_id}. Execute o treino primeiro."
            )
            
    try:
        with open(filepath, "rb") as f:
            model_bytes = f.read()
            
        predictions_out: List[PredictionDay] = []
        
        if model_type == "mlp":
            start_dt = None
            if payload.start_date:
                start_dt = datetime.datetime.strptime(payload.start_date, "%Y-%m-%d").date()
                
            preds = predict_mlp_horizon(
                model_bytes=model_bytes,
                recent_lags=payload.recent_sales_lags,
                avg_price=payload.avg_price or 2.0,
                horizon_days=payload.horizon_days,
                start_date=start_dt
            )
            for dt, val in preds:
                predictions_out.append(PredictionDay(date=str(dt), predicted_kg=val))
                
        elif model_type == "autoformer":
            preds_raw = predict_autoformer_horizon(
                model_bytes=model_bytes,
                running_history=payload.recent_sales_lags,
                avg_price=payload.avg_price or 2.0,
                horizon_days=payload.horizon_days
            )
            start_dt = datetime.date.today()
            if payload.start_date:
                start_dt = datetime.datetime.strptime(payload.start_date, "%Y-%m-%d").date()
                
            for step, val in enumerate(preds_raw):
                cur_dt = start_dt + datetime.timedelta(days=step)
                predictions_out.append(PredictionDay(date=str(cur_dt), predicted_kg=round(float(val), 2)))
                
        return PredictResponse(
            status="SUCCESS",
            user_id=payload.user_id,
            culture_id=payload.culture_id,
            model_type=model_type,
            horizon_days=payload.horizon_days,
            predictions=predictions_out
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro durante a inferência: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)

