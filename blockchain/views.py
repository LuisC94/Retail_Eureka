from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from dashboard.models import Harvest, PlantationEvent, Warehouse, MarketplaceOrder

from .services import BlockchainService, blockchain_service

# Instância global removida (agora importada de services)

def is_producer(user):
    return user.groups.filter(name='Producer').exists()

def is_transporter(user):
    return user.groups.filter(name='Transporter').exists()

def is_retailer(user):
    return user.groups.filter(name='Retailer').exists()

@login_required
def generate_genesis_block(request, harvest_id):
    """
    View chamada pelo Produtor para criar o 1º Bloco (Origem).
    """
    if not is_producer(request.user):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
        
    harvest = get_object_or_404(Harvest, pk=harvest_id)
    plantation = harvest.plantation
    
    # --- 1. Reunir Informação - DOSSIER DIGITAL COMPLETO ---
    
    # A. Informação da Plantação (Origem)
    plantation_info = {
        "name": plantation.plantation_name if plantation else "N/A",
        "location": plantation.location if plantation else "Unknown",
        "area_m2": float(plantation.area) if plantation else 0,
        "production_type": plantation.get_production_type_display() if plantation else "N/A",
        "chemical_use": plantation.get_chemical_use_display() if plantation else "N/A",
        "soil_type": plantation.get_soil_type_display() if plantation else "Unknown",
        "water_regime": plantation.get_water_regime_display() if plantation else "Unknown"
    }

    # B. Informação do Armazém (Onde está guardado atualmente)
    # Tenta encontrar uma Warehouse do produtor (Assumindo que está num dos seus armazéns)
    warehouse = Warehouse.objects.filter(owner=harvest.producer).first()
    warehouse_info = {
        "id": warehouse.warehouse_id if warehouse else "N/A",
        "location": warehouse.location if warehouse else "Unknown",
        "type": warehouse.get_control_type_display() if warehouse else "N/A",
        "has_sensors": "Yes" if warehouse and warehouse.sensors.exists() else "No"
    }

    # C. Histórico de Eventos (Rastreabilidade Completa e Detalhada)
    events = PlantationEvent.objects.filter(plantation=plantation)
    event_history = []
    
    for event in events:
        event_entry = {
            "date": event.event_date.strftime('%Y-%m-%d'),
            "type": event.get_event_type_display(),
            "notes": event.notes
        }

        # Extração de Detalhes Técnicos baseada no tipo
        if event.fertilizer_synth:
            f = event.fertilizer_synth
            event_entry["tech_details"] = {
                "product": f.commercial_product,
                "npk": f.form_npk,
                "dose": f"{f.total_dose_kg_ha_year} kg/ha/year"
            }
        elif event.fertilizer_org:
            f = event.fertilizer_org
            event_entry["tech_details"] = {
                "type": f.organic_fertilizer_type,
                "origin": f.origin,
                "dose": f"{f.dose_tha_year} t/ha/year"
            }
        elif event.soil_corrective:
            s = event.soil_corrective
            event_entry["tech_details"] = {
                "product": s.commercial_product,
                "type": s.corrective_type,
                "dose": f"{s.dose_kg_ha_year} kg/ha/year"
            }
        elif event.pest_control:
            p = event.pest_control
            event_entry["tech_details"] = {
                "product": p.commercial_product,
                "active_substance": p.active_substance,
                "target": p.pest_type,
                "dose": p.dose_per_application
            }
        # Adicionar mais condições se necessário para água, maquinaria, etc.

        event_history.append(event_entry)
        
    # D. Dossier Final Consolidado (Estrutura Melhorada)
    dossier = {
        "batch_id": f"LOTE-{harvest.harvest_id}",
        "producer_id": harvest.producer.username,
        "creation_date": harvest.harvest_date.strftime('%Y-%m-%d'),
        
        "harvest": {
            "product": harvest.subfamily.name if harvest.subfamily else "N/A",
            "quantity_kg": float(harvest.harvest_quantity_kg),
            "quality_score": harvest.avg_quality_score,
            "origin_plantation": plantation.plantation_name if plantation else "N/A"
        },
        
        "plantation": plantation_info,  # Renomeado de origin_data para plantation
        
        "storage": warehouse_info,
        
        "events_log": event_history
    }
    
    # 2. Gerar Hash e "Assinar"
    data_hash = blockchain_service.generate_dossier_hash(dossier)
    
    # 3. Submeter à Blockchain
    result = blockchain_service.sign_and_submit_block(
        user_role='Producer',
        batch_id=dossier['batch_id'],
        data_hash=data_hash,
        event_type='GENESIS'
    )
    
    # 4. Feedback
    messages.success(request, f"Bloco Genesis criado com sucesso! Hash: {result['tx_hash'][:10]}... (Estrutura Otimizada)")
    
    return redirect('producer_dashboard')

@login_required
def view_batch_chain(request, batch_id):
    """
    Visualizar a cadeia de blocos com rastreabilidade completa (Genealogia).
    Implementa recursividade para encontrar todos os lotes "pais" (Inputs)
    e unificar a cadeia.
    """
    full_chain = blockchain_service.get_chain()
    
    # 1. Função Recursiva para explorar a genealogia (Backwards Traceability)
    def fetch_genealogy(current_batch_id, visited=None):
        if visited is None:
            visited = set()
        
        if current_batch_id in visited:
            return []
        
        visited.add(current_batch_id)
        related_blocks = []
        
        # A. Encontrar blocos diretos deste Batch ID
        my_blocks = [b for b in full_chain if b['batch_id'] == current_batch_id]
        related_blocks.extend(my_blocks)
        
        # Flag to track if we found upstream parents in the blockchain data
        parents_found = False

        # B. Explorar Pais (Inputs/Origins) em cada bloco
        for block in my_blocks:
            # FIX: Model field is 'data_content', not 'content'
            content = block.get('data_content', {}) or {}
            if isinstance(content, str):
                try:
                    content = json.loads(content)
                except:
                    content = {}
            
            # B1. Verificar 'inputs' (Agregação/Processamento)
            inputs = content.get('inputs', [])
            if inputs and isinstance(inputs, list):
                for inp in inputs:
                    parent_id = inp.get('batch_id')
                    if parent_id:
                        parents_found = True
                        related_blocks.extend(fetch_genealogy(parent_id, visited))
            
            # B2. Verificar 'harvest_origin' (Legado/Atalhos) - caso ainda use fields flat
            # Tenta obter de 'harvest_origin' (Transport blocks often have this inside 'dossier' or root content)
            harvest_origin = content.get('harvest_origin')
            
            # Se não estiver na raiz, tenta procurar dentro de 'order_details' ou chaves similares comuns em Transport
            if not harvest_origin and 'order' in content:
                 harvest_origin = content['order'].get('harvest_origin')

            if harvest_origin and str(harvest_origin) != "N/A":
                parents_found = True
                # Se é apenas o ID numérico (ex: 15), converte para formato LOTE-15
                parent_id = f"LOTE-{harvest_origin}" if not str(harvest_origin).startswith('LOTE-') else harvest_origin
                related_blocks.extend(fetch_genealogy(parent_id, visited))

        # C. FALLBACK: Database Bridge (If Blockchain link is missing)
        # Se estamos num Batch tipo "ORDER-123" e ainda não achámos o pai via blocos (parents_found=False), vamos ao DB.
        if current_batch_id.startswith('ORDER-') and not parents_found: 
            try:
                # Extrair ID numérico
                order_pk = current_batch_id.replace('ORDER-', '')
                order_obj = MarketplaceOrder.objects.filter(pk=order_pk).first()
                if order_obj and order_obj.harvest_origin:
                    # Encontrámos o Harvest no DB! Vamos buscar os blocos dele.
                    harvest_batch_id = f"LOTE-{order_obj.harvest_origin.pk}"
                    related_blocks.extend(fetch_genealogy(harvest_batch_id, visited))
            except Exception as e:
                print(f"Error bridging Order to Harvest via DB: {e}")

        return related_blocks

    # 2. Executar a busca
    # Se o ID passado for uma ORDER (ex: ORDER-50), a função vai buscar o bloco dessa Order,
    # ver quem é o pai (harvest_origin) e buscar a cadeia do pai recursivamente.
    raw_chain = fetch_genealogy(batch_id)
    
    # 3. Remover duplicados (baseado no block_hash)
    unique_chain = {b['block_hash']: b for b in raw_chain}.values()
    
    # 4. Ordenar Cronologicamente
    final_chain = sorted(unique_chain, key=lambda x: x['timestamp'])
    
    # 5. Adicionar índice visual sequencial
    for idx, block in enumerate(final_chain):
        block['visual_index'] = idx + 1
    
    return render(request, 'blockchain/blockchain_explorer.html', {
        'chain': final_chain, 
        'batch_id': batch_id 
    })
