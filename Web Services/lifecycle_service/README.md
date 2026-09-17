# Lifecycle Decay Prediction Web Service (FastAPI)

Microserviço autónomo de previsão de decaimento biológico e estimativa de tempo de vida útil restante (**Shelf-Life**) de frutas e produtos hortofrutícolas ao longo da cadeia de abastecimento.

---

## 1. Arquitetura e Modelos Biológicos

O serviço integra duas formulações matemáticas baseadas em **Equações Diferenciais Ordinárias (ODEs)** e **Cinética de Arrhenius**:

1. **Modelo de Decaimento com Etileno Endógeno (Prof. Luís Paulo):**
   - Modela a autocatálise de etileno ($C_2H_4$), rampa climatérica, sensibilidade à temperatura ($T$) e humidade ($RH$).
   - Simula o amolecimento e a evolução de sólidos solúveis (°Brix).

2. **Modelo de Cadeia Logística e Stakeholders (Sofia Machado):**
   - Incorpora Deficit de Pressão de Vapor (**VPD**), perda de água, degradação de ácidos orgânicos e barreira por tipo de embalagem (**Granel, Caixa Aberta, Perfurado, MAP**).
   - Avalia a conformidade do lote segundo critérios rigorosos de aceitação por interveniente (**Produtor, Processador/Indústria, Supermercado/Retalhista**).
   - **Imputação Meteorológica IPMA:** Preenchimento inteligente de leituras omissas com base em perfis climatológicos regionais de Portugal.

---

## 2. Endpoints da API

| Método | Endpoint | Descrição |
|---|---|---|
| `GET` | `/health` | Healthcheck do serviço |
| `GET` | `/status` | Estado de concorrência e inferência |
| `GET` | `/presets` | Lista todas as variedades de fruta calibradas |
| `GET` | `/presets/{fruit_key}` | Retorna os parâmetros biológicos de uma variedade |
| `POST` | `/preset` | Adiciona ou atualiza um preset dinamicamente |
| `POST` | `/forecast` | Executa a simulação de decaimento do lote |

---

## 3. Instalação e Execução

### A. Execução Local
```bash
cd "Web Services/lifecycle_service"
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# Iniciar o Web Service na porta 8003
python main.py
```

A documentação interativa Swagger estará disponível em:
👉 **`http://127.0.0.1:8003/docs`**

### B. Teste Automático
Com o serviço a correr, execute noutro terminal:
```bash
python test_service.py
```

---

## 4. Integração com o Django
O payload gerado pela função `build_lot_lifecycle_data(lot_id)` do Django (`dashboard/views.py`) é 100% compatível com o endpoint `POST /forecast`.
