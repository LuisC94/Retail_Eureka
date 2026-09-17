# Retail Eureka - Marketplace Web Service (Clearinghouse & Order Book)

O **Marketplace Web Service** é um microsserviço central de alta disponibilidade baseado em **FastAPI** e **SQLite** thread-safe, operando na porta `8004`.
Permite uma arquitetura federada descentralizada (*Edge-to-Hub*), onde múltiplos nós Django privados (Produtores, Processadores, Retalhistas / Continente) publicam ofertas de venda, ordens de compra, acordam contratos futuros e consultam cotações de mercado em tempo real.

---

## 🌟 Funcionalidades Principais

1. **Gestão de Listings (Ofertas de Venda):**
   - Criação de ofertas com detalhes de cultura, lote, quantidade, preço/kg e métricas de qualidade biológica (°Brix, calibre, qualidade).
   - Consulta filtrada por cultura, preço máximo ou vendedor.
   - Cancelamento de ofertas abertas.

2. **Gestão de Bids (Ordens de Compra & Procura):**
   - Registo de ordens de compra com requisitos mínimos de qualidade e limites orçamentais.

3. **Clearinghouse & Execução de Deals:**
   - **Instant Buy:** Execução de compras imediatas com débito atómico de stock e fecho de negócio.
   - **Future Contracts:** Acordos de fornecimento futuros bilaterais com datas agendadas de entrega.

4. **Market Tickers & Inteligência de Preços:**
   - Agregação em tempo real de preços médios, mínimos, máximos, volume de oferta aberta, procura aberta e transações 24h por cultura.

---

## 🚀 Instalação & Execução

### 1. Instalar Dependências
```bash
pip install -r requirements.txt
```

### 2. Iniciar o Servidor
```bash
python main.py
# Ou com uvicorn
uvicorn main:app --host 0.0.0.0 --port 8004 --reload
```

---

## 📚 Endpoints da API

- **`GET /health`** - Estado de saúde do microsserviço.
- **`GET /status`** - Estatísticas operacionais da Clearinghouse.
- **`POST /listings`** - Publicar oferta de venda.
- **`GET /listings`** - Consultar ofertas ativas no mercado.
- **`GET /listings/{id}`** - Obter detalhes de uma oferta.
- **`DELETE /listings/{id}`** - Cancelar oferta.
- **`POST /bids`** - Publicar ordem de compra / procura.
- **`GET /bids`** - Consultar ordens de compra ativas.
- **`POST /deals/instant_buy`** - Executar compra imediata.
- **`POST /deals/contract`** - Celebrar contrato de fornecimento futuro.
- **`GET /deals`** - Listar transações registadas.
- **`GET /market/prices`** - Obter tickers e cotações de mercado.

---

## 🧪 Testes Automatizados
```bash
python test_service.py
```
