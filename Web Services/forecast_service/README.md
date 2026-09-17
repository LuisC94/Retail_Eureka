# 🧠 Demand Forecast Web Service (FastAPI)

Microserviço independente de Machine Learning para Previsão de Procura com isolamento de modelos por utilizador e cultura (`models_storage/user_{user_id}/`).

---

## 🚀 Como Iniciar o Serviço

### 1. Ativar o venv e iniciar o servidor:
```bash
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

* **URL base do serviço:** `http://localhost:8001`
* **Swagger UI Interativo:** `http://localhost:8001/docs`

---

## 📡 Endpoints da API

### 1. Verificar Estado do Modelo do Utilizador
* **Método:** `GET /api/forecast/status`
* **Query Params:** `user_id=1&culture_id=3`
* **Exemplo de Resposta:**
```json
{
  "user_id": 1,
  "culture_id": 3,
  "has_model": true,
  "available_models": ["mlp"],
  "last_modified": "2026-09-15T15:30:00"
}
```

---

### 2. Treinar Modelo
* **Método:** `POST /api/forecast/train`
* **Payload:**
```json
{
  "user_id": 1,
  "culture_id": 3,
  "model_type": "mlp",
  "sales_history": [
    {"date": "2026-08-01", "sales_quantity_kg": 120.0, "price_per_kg": 2.10},
    {"date": "2026-08-02", "sales_quantity_kg": 135.0, "price_per_kg": 2.10},
    {"date": "2026-08-03", "sales_quantity_kg": 110.0, "price_per_kg": 2.15},
    {"date": "2026-08-04", "sales_quantity_kg": 140.0, "price_per_kg": 2.20},
    {"date": "2026-08-05", "sales_quantity_kg": 125.0, "price_per_kg": 2.10},
    {"date": "2026-08-06", "sales_quantity_kg": 130.0, "price_per_kg": 2.15},
    {"date": "2026-08-07", "sales_quantity_kg": 150.0, "price_per_kg": 2.20},
    {"date": "2026-08-08", "sales_quantity_kg": 145.0, "price_per_kg": 2.10},
    {"date": "2026-08-09", "sales_quantity_kg": 160.0, "price_per_kg": 2.25},
    {"date": "2026-08-10", "sales_quantity_kg": 155.0, "price_per_kg": 2.20}
  ]
}
```

---

### 3. Fazer Previsão (Inferência)
* **Método:** `POST /api/forecast/predict`
* **Payload:**
```json
{
  "user_id": 1,
  "culture_id": 3,
  "model_type": "mlp",
  "horizon_days": 14,
  "start_date": "2026-09-16",
  "recent_sales_lags": [140.0, 125.0, 130.0, 150.0, 145.0, 160.0, 155.0],
  "avg_price": 2.15
}
```
