# Stock Agent Web Service (porta 8005)

Este serviço recomenda **que lote(s) colocar à venda hoje** (agente de Lotes, decisão diária) ou **que armazém abrir esta semana** (agente de Armazéns, decisão semanal). O objetivo é maximizar o lucro e minimizar o desperdício. O tempo de vida de cada lote é calculado pelo motor Lifecycle LC v0.2.0, embutido no serviço.

Na plataforma Django, aparece na aba **📦 Stock Agent** dos dashboards de Produtor, Retalhista e Processador.

## Executar

```bash
cd "Web Services/stock_agent_service"
pip install -r requirements.txt
python main.py                      # http://localhost:8005/docs
```

O Django aponta para `STOCK_AGENT_SERVICE_URL` (por defeito `http://127.0.0.1:8005`), definido em `core/settings.py`.

## Modelos

Os modelos ficam em `models_storage/`. Para cada pedido, o serviço procura o modelo por esta ordem:

1. `<perfil>/<cultura>/<lot|warehouse>/modelo.zip`: modelo próprio do perfil.
2. `_default/<fruta>/<modo>/modelo.zip`: modelo **por defeito** da fruta do Lifecycle (`kiwi_hayward`, `kiwi_gold`, `apple_gala`, `apple_fuji`, `apple_golden`, `apple_reineta`).
3. `_default/kiwi_hayward` ou `_default/apple_gala`: o modelo da mesma família.

Os modelos por defeito são treinados com dados sintéticos. Na decisão, o estado é normalizado com as escalas do próprio perfil (preço, procura e tamanho dos lotes), por isso servem qualquer volume de stock.

Para os voltar a treinar (6 frutas × 2 modos, cerca de 6 minutos com 6 processos):

```bash
python -m stock_agent.train_defaults --out models_storage --workers 6
```

Também é possível treinar modelos próprios na interface Streamlit (`c:\buyerAgent\Stock Agent\app.py`) e publicá-los com `POST /models/upload` ou com o botão "Publicar no repositório".

## Endpoints

| Método | Endpoint | Descrição |
|---|---|---|
| GET | `/health` | Estado do serviço |
| GET | `/models` | Modelos disponíveis e métricas (agente vs heurística FEFO) |
| POST | `/models/upload` | Publica um modelo ZIP |
| POST | `/train` | Treino em background a partir do Excel do Stock Agent |
| GET | `/train/{job_id}` | Progresso do treino |
| POST | `/decide` | Recomendação para uma data |

O Django monta o pedido `POST /decide` em `dashboard/services/stock_agent_service.py`:

- **Produtor:** um lote por `Harvest` com stock e armazém (`LOTE-<id>`). O lote é marcado "à venda" se tiver uma oferta `OPEN` no Marketplace.
- **Retalhista / Processador:** os lotes são reconstruídos a partir dos negócios do Marketplace (`batch_id = LOTE-<id>`, ligado ao `Harvest` de origem). Assume-se que o stock mais antigo saiu primeiro. Sem negócios, cada `ConsolidatedStock` é tratado como um lote.
- **Leituras:** vêm de `WarehouseSensorReading`. Os dias em falta são preenchidos com os valores fixos do armazém.
- **Mercado:**
  - Preço e vendas dos últimos 40 dias (`HistoricalSalesData`) e procura prevista dos 14 dias seguintes (`DemandForecast`).
  - Se faltarem dados, usa a cotação do Marketplace, o histórico mais antigo ou a média de outros perfis da mesma cultura.
  - Cada aproximação aparece como aviso na aba.
