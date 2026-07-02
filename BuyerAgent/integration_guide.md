# Guia de Integração: Agente PPO Constrained em Django & PostgreSQL

Este pacote contém os ficheiros necessários para integrar o agente de decisão de compras inteligente (PPO Limitado - Abordagem B) em qualquer plataforma desenvolvida em **Django** usando uma base de dados **PostgreSQL**.

## 📁 Estrutura do Pacote
* `agent/`: Implementação do agente e arquitetura da rede neuronal (Ator/Crítico).
* `modelos_producao_constrained/`: Checkpoints de pesos treinados (`.pth`) para cada produto SKU.
* `environment_constrained.py`: Contém a lógica física e matemática do ambiente de stock, que serve como referência para construir o vetor de estados.
* `requirements_integration.txt`: Lista mínima de dependências pip.

---

## 🛠️ Como Funciona o Agente em Produção (Inferência)

No mundo real, o agente funciona como um **Módulo de Suporte à Decisão**. Todos os dias, antes de enviar as encomendas aos fornecedores, a plataforma Django executa estes passos:
1. **Consulta a BD PostgreSQL** para extrair os dados mais recentes do armazém (stock atual, vendas de ontem, histórico de procura, encomendas pendentes).
2. **Constrói o Vetor de Estado de 17 Dimensões** ($\mathbf{s}_t \in \mathbb{R}^{17}$) seguindo exatamente a mesma lógica de normalização usada no treino.
3. **Executa o Modelo PyTorch (Ator)** para receber a sugestão de encomenda ótima em percentagem ($[0.0, 1.0]$).
4. **Converte em Unidades Físicas** multiplicando o sinal pela capacidade ou pelo limite cap (`max_order_limit`).
5. **Aplica as Restrições Físicas** (impedindo que a sugestão exceda o espaço disponível no armazém).
6. **Regista a encomenda sugerida** no fluxo de aprovação dos compradores humanos.

---

## 📐 Construção do Estado de 17 Dimensões
O vetor de estado $\mathbf{s}_t$ é composto pelos seguintes 17 valores, normalizados entre $0.0$ e $1.0$:

1. **Lags de Procura (s1 a s4):** Procura dos últimos 4 dias.
2. **Stock Físico Inicial (s5):** Stock on-hand no armazém no início do dia.
3. **Pipeline In-Transit (s6 a s8):** Quantidade a caminho (com entrega pendente a 1, 2 e 3 dias de distância).
4. **Preço de Venda Normalizado (s9):** Z-score do preço de venda com base numa janela deslizante de 15 dias.
5. **Calendário Cíclico (s10 a s13):** Seno e cosseno do dia da semana e do mês do ano.
6. **Stock Coverage Index (s14):** Dias de procura futura estimada que o stock atual consegue cobrir.
7. **Waste Urgency Ratio (s15):** Fração do stock físico que está no seu último dia de vida útil (shelf-life = 4) e corre o risco de apodrecer hoje.
8. **Erro de Previsão Recente (s16):** Desvio percentual entre a venda real de ontem e a previsão do Autoformer.
9. **Previsão de Vendas (s17):** Previsão de procura estimada para os próximos dias.

---

## 💻 Exemplo de Implementação em Django (Service Pattern)

Crie um serviço em Django (ex: `services/intelligent_ordering.py`) para gerir a inferência.

```python
import os
import torch
import numpy as np
from django.conf import settings
from agent.ppo_agent import ParallelPPOAgent

class IntelligentOrderingService:
    def __init__(self, product_sku, max_warehouse_capacity=500):
        self.sku = product_sku
        self.max_capacity = max_warehouse_capacity
        self.state_dim = 17
        
        # 1. Obter o limite cap histórico do produto (por exemplo, lido da BD ou definido estaticamente)
        # O limite cap (max_order_limit) é a procura máxima observada no treino.
        # Exemplo: 205 unidades para o produto 3_256
        self.max_order_limit = self.get_product_order_limit(product_sku)
        
        # 2. Inicializar o agente PyTorch
        self.agent = ParallelPPOAgent(
            state_dim=self.state_dim, 
            action_dim=1, 
            max_action=self.max_order_limit
        )
        
        # 3. Carregar os pesos treinados correspondentes ao SKU
        weights_dir = os.path.join(
            settings.BASE_DIR, 
            'intelligent_ordering', 
            'modelos_producao_constrained', 
            product_sku
        )
        # Caminho para o ficheiro _actor.pth
        actor_path = os.path.join(weights_dir, 'ppo_constrained_iter313') # Sem extensão, o agent.load adiciona
        
        self.agent.load(actor_path)
        self.agent.policy_old_actor.to('cpu') # Rodar em CPU para economizar GPU de produção
        self.agent.policy_old_actor.eval()

    def get_product_order_limit(self, sku):
        # Mapeamento estático dos limites caps calculados (ou lidos do PostgreSQL)
        limits = {
            '3_256': 205,
            '3_090': 166,
            '3_252': 180,
            '3_080': 120,
        }
        return limits.get(sku, 500)

    def calculate_order(self, db_state_data):
        """
        Recebe os dados do PostgreSQL, constrói o vetor de 17 posições normalizado,
        executa o ator e devolve a encomenda sugerida em unidades físicas.
        """
        # 1. Construir o vetor de estados (np.array de forma (17,))
        # Certifique-se de usar os mesmos escaladores Min-Max (0 a Cmax ou 0 a Dmax)
        state_vector = self.normalize_db_state(db_state_data)
        
        # Converter para tensor PyTorch
        state_tensor = torch.FloatTensor(state_vector).unsqueeze(0) # shape (1, 17)
        
        # 2. Inferência pelo Modelo Ator
        with torch.no_grad():
            action_mean, _ = self.agent.policy_old_actor(state_tensor)
            action_percent = action_mean.cpu().numpy().flatten()[0]
            
        # 3. Mapear para a ação física restrita
        # Encomenda física sugerida = round(percentagem * max_order_limit)
        suggested_order = int(np.round(np.clip(action_percent * self.max_order_limit, 0, self.max_order_limit)))
        
        # 4. Aplicar a Restrição Física de Armazém (Dock Overflow Avoidance)
        stock_on_hand = db_state_data['current_stock_on_hand']
        in_transit_today = db_state_data['in_transit_arriving_today']
        
        # Espaço disponível = Capacidade Máxima - Stock Físico Atual
        available_space = max(0, self.max_capacity - (stock_on_hand + in_transit_today))
        
        # Ação real restrita
        final_order = min(suggested_order, available_space)
        
        return {
            'sku': self.sku,
            'suggested_percentage': float(action_percent),
            'suggested_order_units': suggested_order,
            'constrained_order_units': final_order,
            'applied_cap': self.max_order_limit,
            'warehouse_space_left': available_space
        }

    def normalize_db_state(self, data):
        # Exemplo de lógica de normalização:
        # Preço Z-score = (preço_hoje - média_15d) / std_15d
        price_z = (data['price_today'] - data['price_mean_15d']) / (data['price_std_15d'] + 1e-8)
        
        # Min-Max de Lags e Stock (dividido pela capacidade ou peak)
        lags = [data['lag_1'] / self.max_capacity, data['lag_2'] / self.max_capacity] # etc
        stock = data['current_stock_on_hand'] / self.max_capacity
        
        # Dia da semana trigonométrico
        day_sin = np.sin(2 * np.pi * data['day_of_week'] / 7)
        day_cos = np.cos(2 * np.pi * data['day_of_week'] / 7)
        
        # Juntar tudo no array de 17 posições de forma ordenada
        state = np.zeros(17)
        # Preencher de forma perfeitamente alinhada à rede neuronal...
        # ...
        return state
```

## 📅 Execução Periódica (Cron Job com Celery)
Em produção, crie uma tarefa agendada do Celery para correr todos os dias de madrugada (ex: às 02:00 AM) que extrai os dados consolidados do PostgreSQL, chama o `IntelligentOrderingService` para cada produto e escreve as propostas de compras numa tabela `order_suggestions` para aprovação do comprador no painel administrativo Django.
