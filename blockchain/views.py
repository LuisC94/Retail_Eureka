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
    Visualizar a cadeia de blocos de um lote (para debug/transparência).
    Agora suporta 'Cross-Chain Linking': Se for uma Order vinda de uma Harvest, mostra ambas.
    """
    full_chain = blockchain_service.get_chain()
    
    # --- LÓGICA DE UNIFICAÇÃO DE CORRENTES (BIDIRECIONAL) ---
    # Queremos que, entre-se pelo Lote ou pela Encomenda, se veja TUDO.
    
    harvest_pk = None
    order_pk = None
    
    # 1. Identificar Ponto de Entrada
    if batch_id.startswith("LOTE-"):
        try:
            harvest_pk = batch_id.split("-")[1]
        except IndexError:
            pass
    elif batch_id.startswith("ORDER-"):
        try:
            order_pk = batch_id.split("-")[1]
        except IndexError:
            pass
            
    # 2. Se entrámos por uma Encomenda, descobrimos o Lote de Origem (BACKWARD LOOKUP)
    if order_pk:
        primary_chain = [b for b in full_chain if b['batch_id'] == batch_id]
        # Procurar 'harvest_origin' (frequentemente no Genesis da Order)
        for block in primary_chain:
            content = block.get('content', {})
            possible_pk = content.get('harvest_origin')
            # Verifica se existe e não é N/A
            if possible_pk and str(possible_pk) != "N/A":
                harvest_pk = str(possible_pk)
                break
    
    # 3. Se temos um Lote (seja entrada direta ou descoberto via Order), 
    # procuramos TODAS as Encomendas filhas (FORWARD LOOKUP)
    related_orders_pks = set()
    if harvest_pk:
        # A. Procurar blocos de encomendas que digam "Minha origem é harvest_pk"
        for block in full_chain:
            # Só nos interessa blocos de encomendas (GENESIS ou outro evento que traga o link)
            if block['batch_id'].startswith("ORDER-"):
                content = block.get('content', {})
                origin = str(content.get('harvest_origin', ''))
                if origin == str(harvest_pk):
                    # Encontrámos uma encomenda filha!
                    b_id = block['batch_id']
                    related_orders_pks.add(b_id)
        
        # B. Se entrámos por uma Order específica, garantimos que ela está na lista
        if batch_id.startswith("ORDER-"):
            related_orders_pks.add(batch_id)

    # 4. Construir a Chain Final
    final_chain = []
    
    # A. Adicionar blocos do Lote (Se existir)
    if harvest_pk:
        lote_id = f"LOTE-{harvest_pk}"
        final_chain.extend([b for b in full_chain if b['batch_id'] == lote_id])
        
    # B. Adicionar blocos de TODAS as Encomendas Relacionadas
    for o_id in related_orders_pks:
        final_chain.extend([b for b in full_chain if b['batch_id'] == o_id])

    # C. Se não houver relações (caso isolado), mostra apenas a chain do ID pedido
    if not final_chain:
        final_chain = [b for b in full_chain if b['batch_id'] == batch_id]

    # 5. Ordenação Cronológica e Indexação Visual
    # Ordenar por timestamp (assumindo formato ISO8601 string que é ordenável)
    final_chain.sort(key=lambda x: x['timestamp'])
    
    # Criar índice visual sequencial (1, 2, 3...) para a View
    for idx, block in enumerate(final_chain):
        block['visual_index'] = idx + 1
    
    return render(request, 'blockchain/blockchain_explorer.html', {
        'chain': final_chain, 
        'batch_id': batch_id 
    })
