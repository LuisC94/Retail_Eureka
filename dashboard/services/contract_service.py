import datetime
from django.utils import timezone
from django.db import transaction
from dashboard.models import Harvest, MarketplaceOrder, CultureShelfLife, SupplyContract, Warehouse
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
    shelf_life = CultureShelfLife.objects.filter(subfamily=subfamily).first()
    if shelf_life:
        return shelf_life.default_shelf_life_days
    return 10  # Padrão: 10 dias se não estiver parametrizado

def fulfill_contract(contract):
    """Executa a liquidação física e em blockchain de um contrato individual."""
    with transaction.atomic():
        # 1. Obter armazém do produtor
        warehouse = get_default_warehouse(contract.producer)
        
        # 2. Calcular validade
        days = get_culture_shelf_life(contract.subfamily)
        delivery_date = contract.delivery_date
        expiration_date = delivery_date + datetime.timedelta(days=days)
        
        # 3. Criar a colheita virtual do produtor
        harvest = Harvest.objects.create(
            plantation=None,
            producer=contract.producer,
            subfamily=contract.subfamily,
            harvest_date=delivery_date,
            expiration_date=expiration_date,
            harvest_quantity_kg=contract.quantity_kg,
            delivered_quantity_kg=contract.quantity_kg,
            avg_quality_score=10,  # Máxima qualidade assumida para automação
            utilized_quantity_kg=0,
            warehouse=warehouse
        )
        
        # 4. Criar a encomenda no marketplace de forma imediata (Já Aprovada e Entregue)
        buyer_role = contract.buyer.groups.first().name if contract.buyer.groups.exists() else 'Retailer'
        if contract.warehouse_location:
            warehouse_loc = contract.warehouse_location
        else:
            buyer_warehouse = Warehouse.objects.filter(owner=contract.buyer).first()
            if buyer_warehouse:
                warehouse_loc = f"{buyer_warehouse.location} (WH: {buyer_warehouse.warehouse_id})"
            else:
                warehouse_loc = "Armazém Virtual do Comprador"
            
        order = MarketplaceOrder.objects.create(
            requester=contract.buyer,
            role=buyer_role,
            order_type='BUY',
            culture=contract.subfamily,
            quantity_kg=contract.quantity_kg,
            harvest_origin=harvest,
            price_per_kg=0.0,  # Transação interna/contrato
            warehouse_location=warehouse_loc,
            status='APPROVED',
            fulfilled_by=contract.producer,
            fulfilled_at=timezone.now(),
            transport_status='DELIVERED',
            actual_delivery_date=timezone.now(),
            is_processed=True if buyer_role == 'Processor' else False
        )
        
        # 5. Atualizar o estado do contrato
        contract.status = 'fulfilled'
        contract.save()
        
        # 6. Gravar na Blockchain (Simulação e Rede Real)
        try:
            from dashboard.services.fabric_service import fabric_service
            from blockchain.services import blockchain_service
            from blockchain.utils import create_genesis_dossier
            
            # Bloco 0 (Genesis)
            dossier = create_genesis_dossier(harvest)
            data_hash = blockchain_service.generate_dossier_hash(dossier)
            blockchain_service.sign_and_submit_block(
                user_role='Producer',
                batch_id=dossier['batch_id'],
                data_hash=data_hash,
                event_type='GENESIS',
                data_payload=dossier
            )
            
            fabric_service.create_order(
                order_id=dossier['batch_id'],
                producer_id=harvest.producer.username,
                culture_type=harvest.subfamily.name,
                quantity=float(harvest.harvest_quantity_kg),
                harvest_date=harvest.harvest_date.strftime("%Y-%m-%d"),
                additional_data=dossier
            )
            
            # Bloco de Entrega (Direct Delivery)
            dossier_del = {
                "action": "TRANSPORT_DELIVERY",
                "order_id": order.pk,
                "transporter": "System-Contract",
                "delivery_time": timezone.now().isoformat(),
                "sensor_data": "Automated delivery for contract",
                "harvest_origin": harvest.pk
            }
            data_hash_del = blockchain_service.generate_dossier_hash(dossier_del)
            blockchain_service.sign_and_submit_block(
                user_role='Transporter',
                batch_id=f"ORDER-{order.pk}",
                data_hash=data_hash_del,
                event_type='TRANSPORT_DELIVERY',
                data_payload=dossier_del
            )
            
            fabric_service.update_order(
                order_id=f"LOTE-{harvest.pk}",
                new_status="DELIVERED",
                additional_data=dossier_del
            )
            
        except Exception as blockchain_err:
            print(f"[Contract Service] Blockchain sync error: {blockchain_err}")
            
        return order

def process_pending_contracts():
    """Procura contratos pendentes que atingiram a data e liquida-os."""
    hoje = timezone.now().date()
    pending_contracts = SupplyContract.objects.filter(status='pending', delivery_date__lte=hoje)
    
    count = 0
    for contract in pending_contracts:
        try:
            fulfill_contract(contract)
            count += 1
        except Exception as e:
            print(f"[Contract Service] Error executing contract #{contract.pk}: {e}")
            
    return count

def process_instant_purchase(buyer, producer, subfamily, quantity_kg, warehouse_location=None):
    """Executa uma compra rápida e instantânea ao Produtor Tipo 2 (Makro)."""
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
            utilized_quantity_kg=0,
            warehouse=warehouse
        )
        
        # 4. Criar a encomenda no marketplace entregue de imediato
        buyer_role = buyer.groups.first().name if buyer.groups.exists() else 'Retailer'
        if warehouse_location:
            warehouse_loc = warehouse_location
        else:
            buyer_warehouse = Warehouse.objects.filter(owner=buyer).first()
            if buyer_warehouse:
                warehouse_loc = f"{buyer_warehouse.location} (WH: {buyer_warehouse.warehouse_id})"
            else:
                warehouse_loc = "Armazém Virtual do Comprador"
            
        order = MarketplaceOrder.objects.create(
            requester=buyer,
            role=buyer_role,
            order_type='BUY',
            culture=subfamily,
            quantity_kg=quantity_kg,
            harvest_origin=harvest,
            price_per_kg=0.0,
            warehouse_location=warehouse_loc,
            status='APPROVED',
            fulfilled_by=producer,
            fulfilled_at=timezone.now(),
            transport_status='DELIVERED',
            actual_delivery_date=timezone.now(),
            is_processed=True if buyer_role == 'Processor' else False
        )
        
        # 5. Gravar na Blockchain (Simulação e Rede Real)
        try:
            from dashboard.services.fabric_service import fabric_service
            from blockchain.services import blockchain_service
            from blockchain.utils import create_genesis_dossier
            
            # Bloco 0 (Genesis)
            dossier = create_genesis_dossier(harvest)
            data_hash = blockchain_service.generate_dossier_hash(dossier)
            blockchain_service.sign_and_submit_block(
                user_role='Producer',
                batch_id=dossier['batch_id'],
                data_hash=data_hash,
                event_type='GENESIS',
                data_payload=dossier
            )
            
            fabric_service.create_order(
                order_id=dossier['batch_id'],
                producer_id=harvest.producer.username,
                culture_type=harvest.subfamily.name,
                quantity=float(harvest.harvest_quantity_kg),
                harvest_date=harvest.harvest_date.strftime("%Y-%m-%d"),
                additional_data=dossier
            )
            
            # Bloco de Entrega (Direct Delivery)
            dossier_del = {
                "action": "TRANSPORT_DELIVERY",
                "order_id": order.pk,
                "transporter": "System-InstantBuy",
                "delivery_time": timezone.now().isoformat(),
                "sensor_data": "Direct purchase from wholesaler",
                "harvest_origin": harvest.pk
            }
            data_hash_del = blockchain_service.generate_dossier_hash(dossier_del)
            blockchain_service.sign_and_submit_block(
                user_role='Transporter',
                batch_id=f"ORDER-{order.pk}",
                data_hash=data_hash_del,
                event_type='TRANSPORT_DELIVERY',
                data_payload=dossier_del
            )
            
            fabric_service.update_order(
                order_id=f"LOTE-{harvest.pk}",
                new_status="DELIVERED",
                additional_data=dossier_del
            )
            
        except Exception as blockchain_err:
            print(f"[Contract Service] Blockchain sync error in instant buy: {blockchain_err}")
            
        return order
