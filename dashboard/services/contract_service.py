import datetime
from django.utils import timezone
from django.db import transaction
from dashboard.models import Harvest, ProductSubFamily, Warehouse, ConsolidatedStock
from dashboard.services.marketplace_service import marketplace_service
from django.contrib.auth.models import User

def get_default_warehouse(producer):
    """Retorna um armazém existente do produtor ou cria um virtual padrão."""
    warehouse = Warehouse.objects.filter(owner=producer).first()
    if not warehouse:
        warehouse = Warehouse.objects.create(
            owner=producer,
            location="Armazém Virtual do Produtor",
            control_type="Controlled",
            capacity=999999.0
        )
    return warehouse

def get_culture_shelf_life(subfamily):
    """Retorna o tempo de vida padrão em dias para uma dada cultura."""
    if hasattr(subfamily, 'default_shelf_life_days') and subfamily.default_shelf_life_days:
        return subfamily.default_shelf_life_days
    return 10  # Padrão: 10 dias se não estiver parametrizado

def process_instant_purchase(buyer, producer, subfamily, quantity_kg, warehouse_location=None,
                             firmness=None, brix=None, acidity=None, caliber=None):
    """
    Executa uma compra rápida e instantânea comunicando com o Marketplace Web Service.
    A mercadoria entra logo em stock e fica registada como receção confirmada, com as medições à chegada
    (opcionais): os agentes e o ciclo de vida usam-nas; sem elas, usam os valores por omissão da variedade.
    """
    with transaction.atomic():
        # 1. Obter armazém do produtor
        warehouse = get_default_warehouse(producer)
        
        # 2. Calcular validade
        days = get_culture_shelf_life(subfamily)
        today = timezone.now().date()
        expiration_date = today + datetime.timedelta(days=days)
        
        # 3. Criar a colheita em nome do produtor instantâneo
        harvest = Harvest.objects.create(
            plantation=None,
            producer=producer,
            subfamily=subfamily,
            harvest_date=today,
            expiration_date=expiration_date,
            harvest_quantity_kg=quantity_kg,
            delivered_quantity_kg=quantity_kg,
            avg_quality_score=10,
            utilized_quantity_kg=quantity_kg,
            warehouse=warehouse
        )
        
        # 4. Determinar armazém de destino
        buyer_role = buyer.groups.first().name if buyer.groups.exists() else 'Retailer'
        if warehouse_location:
            warehouse_loc = warehouse_location
        else:
            buyer_warehouse = Warehouse.objects.filter(owner=buyer).first()
            if buyer_warehouse:
                warehouse_loc = f"{buyer_warehouse.location} (WH: {buyer_warehouse.warehouse_id})"
            else:
                warehouse_loc = "Armazém Virtual do Comprador"
        
        # 5. Publicar listing no Marketplace Web Service e executar compra imediata
        listing = marketplace_service.publish_listing(
            seller_id=producer.username,
            seller_role="Producer",
            culture_name=subfamily.name,
            fruit_type=subfamily.fruit_type,
            quantity_kg=float(quantity_kg),
            price_per_kg=2.0,
            warehouse_location=warehouse.location,
            batch_id=f"LOTE-{harvest.pk}",
            quality_metrics={"caliber_mm": 70.0, "soluble_solids_brix": 12.0, "quality_score": 10.0}
        )
        
        deal_info = None
        if listing and listing.get("listing_id"):
            deal_info = marketplace_service.execute_instant_buy(
                listing_id=listing["listing_id"],
                buyer_id=buyer.username,
                buyer_role=buyer_role,
                quantity_kg=float(quantity_kg),
                destination_warehouse=warehouse_loc
            )
            
        # 6. Atualizar ConsolidatedStock do Comprador
        stock_obj, _ = ConsolidatedStock.objects.get_or_create(
            owner=buyer,
            culture=subfamily,
            warehouse_location=warehouse_loc,
            defaults={'quantity': 0.0, 'avg_quality_score': 10.0}
        )
        stock_obj.quantity = float(stock_obj.quantity) + float(quantity_kg)
        stock_obj.save()

        # 6b. Lote rastreável (receção já confirmada) com as medições à chegada, se existirem
        from dashboard.services.reception_service import register_received_lot
        reception = register_received_lot(
            buyer=buyer, culture=subfamily, stock=stock_obj, quantity_kg=quantity_kg,
            deal_id=(deal_info or {}).get("deal_id") or f"INSTANT-{harvest.pk}", deal_type='INSTANT_PURCHASE',
            seller_id=producer.username, batch_id=f"LOTE-{harvest.pk}",
            firmness=firmness, brix=brix, acidity=acidity, caliber=caliber,
        )
        
        # 7. Gravar na Blockchain Real (Hyperledger Fabric)
        try:
            from dashboard.services.fabric_service import fabric_service
            from dashboard.utils import create_genesis_dossier
            
            # Bloco 0 (Genesis)
            dossier = create_genesis_dossier(harvest)
            fabric_service.create_order(
                order_id=dossier['batch_id'],
                producer_id=harvest.producer.username,
                culture_type=harvest.subfamily.name if harvest.subfamily else "N/A",
                quantity=float(harvest.harvest_quantity_kg),
                harvest_date=harvest.harvest_date.strftime("%Y-%m-%d"),
                additional_data=dossier
            )
            
            # Bloco de Entrega (Direct Delivery)
            dossier_del = {
                "action": "TRANSPORT_DELIVERY",
                "deal_id": deal_info.get("deal_id") if deal_info else f"DEAL-INSTANT-{harvest.pk}",
                "transporter": "System-InstantBuy",
                "delivery_time": timezone.now().isoformat(),
                "sensor_data": "Direct purchase from wholesaler",
                "harvest_origin": harvest.pk
            }
            fabric_service.update_order(
                order_id=f"LOTE-{harvest.pk}",
                new_status="DELIVERED",
                additional_data=dossier_del
            )
            
        except Exception as blockchain_err:
            print(f"[Contract Service] Blockchain sync error in instant buy: {blockchain_err}")
            
        return {"deal": deal_info, "harvest_id": harvest.pk, "reception": reception}

def process_pending_contracts():
    """Verifica contratos pendentes no Marketplace Web Service."""
    try:
        deals = marketplace_service.fetch_deals()
        pending_contracts = [d for d in deals if d.get('deal_type') == 'CONTRACT' and d.get('status') == 'PENDING']
        return len(pending_contracts)
    except Exception as e:
        print(f"[Contract Service] Error fetching pending contracts: {e}")
        return 0
