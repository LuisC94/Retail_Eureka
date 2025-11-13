from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
import random
import pandas as pd
import numpy as np

# --- FUNÇÕES DE ML/DADOS (Simulação) ---

def run_ml_model_prediction(data_input):
    """
    Função Placeholder para simular a execução de um modelo de Machine Learning.
    """
    
    base_prediction = 28.5
    complexity_factor = data_input.get('complexity', 1) 
    
    # Simulação de variação de previsão
    if complexity_factor > 1:
        variation = random.uniform(-0.5, 1.5)
    else:
        variation = random.uniform(-0.1, 0.5)
        
    final_prediction = round(base_prediction + variation, 1)
    
    return final_prediction

# --- ROTA DE API PARA O DASHBOARD ---

@api_view(['GET'])
@permission_classes([IsAuthenticated]) # Garante que apenas utilizadores logados acedem
def get_kpis_data(request):
    """
    Endpoint que o JavaScript do dashboard chamará para obter os dados.
    """
    
    waste_reduction_pred = run_ml_model_prediction(data_input={'complexity': 1.5})
    
    # Lógica de autorização baseada no grupo (Role) do utilizador
    # Verifica se o utilizador logado pertence ao grupo 'Admin'
    is_admin = request.user.groups.filter(name='Admin').exists()
    
    data = {
        'waste_reduction': {
            'value': f"{waste_reduction_pred}%",
            'trend': 'Up',
            'title': 'Waste Reduction % (ML Pred.)'
        },
        'delivery_rate': {
            'value': "92.1%",
            'trend': 'Up',
            'title': 'On-Time Delivery Rate'
        },
        # Exemplo de dado restrito: Apenas Admin vê a Forecast Accuracy real
        'forecast_accuracy': {
            'value': "88.9%" if is_admin else "N/A (Restrito)",
            'trend': 'Down',
            'title': 'Forecast Accuracy'
        }
    }
    return Response(data)