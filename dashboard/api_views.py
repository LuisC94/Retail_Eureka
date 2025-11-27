# api_views.py
from django.http import JsonResponse
from .models import SoilCharacteristic # Certifique-se de importar o modelo

def get_soil_characteristics(request):
    """Retorna uma lista de características do solo em formato JSON."""
    characteristics = SoilCharacteristic.objects.all().values('id', 'category', 'sub_category', 'unit')
    
    # Formata a lista para o JavaScript consumir mais facilmente
    data = []
    for char in characteristics:
        data.append({
            'id': char['id'],
            # Cria um nome amigável para o dropdown (ex: 'pH (Unidade)')
            'name': f"{char['category']} - {char['sub_category']} ({char['unit']})" 
        })
        
    return JsonResponse(data, safe=False)