import os
import io
import datetime
from typing import Dict, List, Tuple, Any
import numpy as np
import pandas as pd
from sklearn.neural_network import MLPRegressor
import joblib

def train_mlp_model(df_data: pd.DataFrame) -> bytes:
    """
    Treina a MLPRegressor com features temporais e lags (1 e 7).
    df_data deve conter as colunas:
      - 'date' ou 'Data'
      - 'sales_quantity_kg' ou 'Valor'
      - 'price_per_kg' (opcional, default 2.0)
    """
    df = df_data.copy()
    
    if "Data" in df.columns and "date" not in df.columns:
        df = df.rename(columns={"Data": "date"})
    if "Valor" in df.columns and "sales_quantity_kg" not in df.columns:
        df = df.rename(columns={"Valor": "sales_quantity_kg"})
    if "price_per_kg" not in df.columns:
        df["price_per_kg"] = 2.0

    df["date"] = pd.to_datetime(df["date"])
    df["sales_quantity_kg"] = pd.to_numeric(df["sales_quantity_kg"], errors="coerce")
    df["price_per_kg"] = pd.to_numeric(df["price_per_kg"], errors="coerce").fillna(2.0)
    
    df = df.dropna(subset=["date", "sales_quantity_kg"])
    df = df.sort_values(by="date").reset_index(drop=True)
    
    if len(df) < 10:
        raise ValueError("São necessários pelo menos 10 dias de histórico para treinar o modelo MLP de vendas.")
        
    df["day_of_week"] = df["date"].apply(lambda x: x.weekday() + 1)
    df["month"] = df["date"].apply(lambda x: x.month)
    
    df["real_value_lag1"] = df["sales_quantity_kg"].shift(1)
    df["real_value_lag7"] = df["sales_quantity_kg"].shift(7)
    
    df_clean = df.dropna().reset_index(drop=True)
    if len(df_clean) < 3:
        raise ValueError("Histórico insuficiente após aplicação de lags temporais (mínimo 8 dias no total).")
        
    X = df_clean[["real_value_lag1", "real_value_lag7", "price_per_kg", "day_of_week", "month"]].values
    y = df_clean["sales_quantity_kg"].values
    
    mlp = MLPRegressor(hidden_layer_sizes=(64, 32, 16), max_iter=10000, random_state=42)
    mlp.fit(X, y)
    
    buffer = io.BytesIO()
    joblib.dump(mlp, buffer)
    return buffer.getvalue()


def predict_mlp_horizon(
    model_bytes: bytes,
    recent_lags: List[float],
    avg_price: float = 2.0,
    horizon_days: int = 30,
    start_date: datetime.date = None
) -> List[Tuple[datetime.date, float]]:
    """
    Executa inferência recursiva com a MLPRegressor para o número de dias especificado.
    recent_lags: lista com os últimos N valores reais (mínimo 7 dias).
    """
    if len(recent_lags) < 7:
        raise ValueError("É necessário fornecer pelo menos 7 valores recentes de vendas para os lags.")
        
    mlp = joblib.load(io.BytesIO(model_bytes))
    
    if start_date is None:
        start_date = datetime.date.today()
    elif isinstance(start_date, str):
        start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
        
    running_history = list(recent_lags)
    predictions = []
    
    for step in range(horizon_days):
        current_date = start_date + datetime.timedelta(days=step)
        day_of_week = current_date.weekday() + 1
        month = current_date.month
        
        lag1 = float(running_history[-1])
        lag7 = float(running_history[-7])
        
        X_pred = np.array([[lag1, lag7, float(avg_price), day_of_week, month]])
        y_pred = float(mlp.predict(X_pred)[0])
        y_pred = max(0.0, y_pred)
        
        predictions.append((current_date, round(y_pred, 2)))
        running_history.append(y_pred)
        
    return predictions
