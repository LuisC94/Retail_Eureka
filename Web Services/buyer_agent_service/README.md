# Retail Eureka - Buyer Agent Web Service

Microserviço independente de Tomada de Decisão de Compras e Encomendas baseado em **Aprendizagem por Reforço Profunda (PPO - Proximal Policy Optimization)** com física biológica e isolamento de modelos por utilizador e cultura.

---

## 📌 Funcionalidades Principais

1. **Tomada de Decisão em Tempo Real (`/api/buyer/decide`)**:
   - Analisa o vetor de 17 variáveis de estado: perfil de validade de stock ($G_0-G_3$), encomendas em trânsito, previsão de procura para hoje e amanhã, vendas passadas ($t-1, t-2$), preços relativos (z-score), sazonalidade temporal (seno/cosseno dia da semana e mês), cobertura de stock, índice de urgência e erro de previsão recente.
   - Aplica os constrangimentos físicos de capacidade de armazém e limites diários de fornecedor.
   - Compara a recomendação do agente com 3 baselines heurísticas: **DOS 3D**, **CNN Naive** e **Min-Max**.

2. **Treino Autónomo Multi-Tenant (`/api/buyer/train`)**:
   - Treina uma rede Actor-Critic PPO personalizada por utilizador e cultura (`models_storage/user_{user_id}/culture_{culture_id}/`).
   - Recebe dados históricos de vendas enriquecidos com previsões do Forecast Service.
   - Simula o ambiente de degradação biológica de frutos (*FruitModel2*) e política de consumo FEFO (*First-Expired, First-Out*).

3. **Monitorização de Estado (`/api/buyer/status`)**:
   - Consulta metadados, lucro médio obtido no treino e limites operacionais.

---

## 🚀 Como Iniciar o Serviço

### 1. Instalar dependências
```bash
cd "Web Services/buyer_agent_service"
pip install -r requirements.txt
```

### 2. Iniciar o Servidor FastAPI (Porta 8002)
```bash
uvicorn main:app --host 127.0.0.1 --port 8002 --reload
```

A documentação interativa Swagger estará disponível em: **`http://127.0.0.1:8002/docs`**

---

## 📡 Endpoints & Exemplos de Comunicação

### 1. Health Check
- **Rota:** `GET /health`
- **Resposta:**
```json
{
  "status": "healthy",
  "timestamp": "2026-09-15T17:30:00.000000"
}
```

---

### 2. Verificar Estado do Modelo
- **Rota:** `GET /api/buyer/status?user_id=1&culture_id=3`
- **Resposta:**
```json
{
  "user_id": 1,
  "culture_id": 3,
  "has_model": true,
  "fruit_key": "maca_gala",
  "max_order_limit": 185.0,
  "max_capacity": 500.0,
  "last_trained": "2026-09-15T16:45:12.123456",
  "avg_profit": 142.50
}
```

---

### 3. Treinar Política PPO
- **Rota:** `POST /api/buyer/train`
- **Payload:**
```json
{
  "user_id": 1,
  "culture_id": 3,
  "fruit_key": "maca_gala",
  "max_capacity": 500.0,
  "episodes": 300,
  "train_data": [
    {
      "date": "2026-08-01",
      "real_value": 125.0,
      "prediction": 128.0,
      "price": 2.15,
      "temperature": 1.5,
      "humidity": 92.0,
      "ethylene": 0.05,
      "volume": 0.002
    }
  ]
}
```
- **Resposta:**
```json
{
  "status": "success",
  "message": "Buyer Agent treinado com sucesso (304 episódios em 12.4s).",
  "user_id": 1,
  "culture_id": 3,
  "fruit_key": "maca_gala",
  "max_order_limit": 185.0,
  "avg_profit": 142.50,
  "training_time_seconds": 12.4,
  "saved_path": ".../models_storage/user_1/culture_3",
  "trained_at": "2026-09-15T16:45:12.123456"
}
```

---

### 4. Decisão de Encomenda Diária
- **Rota:** `POST /api/buyer/decide`
- **Payload:**
```json
{
  "user_id": 1,
  "culture_id": 3,
  "date": "2026-09-16",
  "current_stock_profile": [40.0, 30.0, 20.0, 10.0],
  "in_transit_kg": 0.0,
  "prediction_today_kg": 140.0,
  "prediction_tomorrow_kg": 135.0,
  "recent_sales_lags": [130.0, 125.0],
  "price_today": 2.15,
  "recent_prices": [2.10, 2.15, 2.05, 2.20],
  "max_capacity": 500.0
}
```
- **Resposta:**
```json
{
  "status": "success",
  "user_id": 1,
  "culture_id": 3,
  "decision_date": "2026-09-16",
  "recommended_order_kg": 145.0,
  "order_percentage": 0.7838,
  "state_summary": {
    "total_stock_kg": 100.0,
    "coverage_days": 0.71,
    "urgency_index": 0.10,
    "in_transit_kg": 0.0,
    "forecast_today_kg": 140.0,
    "forecast_tomorrow_kg": 135.0
  },
  "heuristics_comparison": {
    "dos_3d_kg": 310.0,
    "cnn_naive_kg": 135.0,
    "min_max_kg": 150.0
  },
  "model_metadata": {
    "fruit_key": "maca_gala",
    "max_order_limit": 185.0,
    "max_capacity": 500.0,
    "trained_at": "2026-09-15T16:45:12.123456",
    "has_trained_model": true
  }
}
```
