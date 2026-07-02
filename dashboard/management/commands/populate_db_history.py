import datetime
import random
import json
import math
from django.core.management.base import BaseCommand
from django.db import transaction, connection
from django.contrib.auth.models import User, Group
from django.utils import timezone
from dashboard.models import (
    ProductSubFamily, Harvest, Warehouse, Sensor, MarketplaceOrder, WarehouseSensorReading, Product,
    PlantationPlan, PlantationCrop, PlantationEvent, FertilizerSyntheticData, FertilizerOrganicData,
    SoilCorrectiveData, PestControlData, MachineryData, FuelData, ElectricEnergyData, IrrigationWaterData,
    ConsolidatedStock
)
from blockchain.models import BlockchainBlock
from blockchain.services import blockchain_service
from blockchain.utils import create_genesis_dossier

class Command(BaseCommand):
    help = "Limpa dados transacionais e popula a base de dados com 3 anos de histórico de sensores e transações."

    def handle(self, *args, **options):
        self.stdout.write("A iniciar processo de limpeza e sementeira de 3 anos de histórico...")

        # 1. Definir Presets Biológicos
        maca_gala = {
            "label": "Maçã (Gala)",
            "Tref_C": 5.0, "Ea_J": 48000.0, "k_firm_ref": 0.04, "alpha_E": 1.3,
            "beta_RH": 0.9, "RH_ref": 90.0,
            "dureza_min": 9.0, "dureza_0_default": 60.0,
            "brix_min": 12.5, "brix_max": 17.0, "brix_g": 0.25, "brix_0_default": 13.0,
            "qual_firm_threshold": 28.0, "qual_brix_target": 14.5,
            "E0_int": 0.015, "Eref_prod": 0.18, "E_t0": 10.0, "E_g": 0.9, "E_auto": 0.5,
            "E_decay": 0.65, "Ea_E_J": 52000.0, "E_ext_shift": 2.2,
            "RH_mold_thr": 95.0, "mold_rate_ref": 0.05, "mold_sens_RH": 9.0,
            "mold_max_penalty": 0.65, "Ea_mold_J": 43000.0,
            "elasticity": 1.6
        }
        maca_fuji = {
            "label": "Maçã (Fuji)",
            "Tref_C": 5.0, "Ea_J": 47000.0, "k_firm_ref": 0.018, "alpha_E": 0.6,
            "beta_RH": 0.7, "RH_ref": 90.0,
            "dureza_min": 15.0, "dureza_0_default": 80.0,
            "brix_min": 13.0, "brix_max": 19.0, "brix_g": 0.15, "brix_0_default": 14.0,
            "qual_firm_threshold": 40.0, "qual_brix_target": 16.0,
            "E0_int": 0.008, "Eref_prod": 0.06, "E_t0": 25.0, "E_g": 0.5, "E_auto": 0.25,
            "E_decay": 0.45, "Ea_E_J": 52000.0, "E_ext_shift": 1.4,
            "RH_mold_thr": 95.0, "mold_rate_ref": 0.035, "mold_sens_RH": 8.0,
            "mold_max_penalty": 0.55, "Ea_mold_J": 42000.0,
            "elasticity": 1.5
        }
        kiwi_hayward = {
            "label": "Kiwi (Hayward)",
            "Tref_C": 5.0, "Ea_J": 60000.0, "k_firm_ref": 0.06, "alpha_E": 1.8,
            "beta_RH": 1.2, "RH_ref": 90.0,
            "dureza_min": 3.0, "dureza_0_default": 45.0,
            "brix_min": 11.0, "brix_max": 17.0, "brix_g": 0.35, "brix_0_default": 11.0,
            "qual_firm_threshold": 8.0, "qual_brix_target": 15.0,
            "E0_int": 0.02, "Eref_prod": 0.12, "E_t0": 10.0, "E_g": 0.9, "E_auto": 0.35,
            "E_decay": 0.7, "Ea_E_J": 52000.0, "E_ext_shift": 2.0,
            "RH_mold_thr": 95.0, "mold_rate_ref": 0.05, "mold_sens_RH": 9.0,
            "mold_max_penalty": 0.65, "Ea_mold_J": 43000.0,
            "elasticity": 1.5
        }

        # 2. Criar ou Obter Grupos e Utilizadores
        roles = ['Producer', 'Processor', 'Retailer', 'Transporter', 'Consumer']
        groups = {r: Group.objects.get_or_create(name=r)[0] for r in roles}

        users_config = [
            # Producers (3)
            ('ProducerBraga', 'Producer'),
            ('ProducerPorto', 'Producer'),
            ('ProducerCoimbra', 'Producer'),
            # Processors (3)
            ('Processor', 'Processor'),
            ('ProcessorNorte', 'Processor'),
            ('ProcessorSul', 'Processor'),
            # Retailer
            ('RetailStore', 'Retailer'),
            # Transporter
            ('Transportes', 'Transporter'),
            # Consumers (8: 4 standard, 4 mercearias)
            ('Antonio', 'Consumer'),
            ('Maria', 'Consumer'),
            ('Jose', 'Consumer'),
            ('Manuel', 'Consumer'),
            ('MerceariaIdeal', 'Consumer'),
            ('MerceariaDoBairro', 'Consumer'),
            ('MerceariaCentral', 'Consumer'),
            ('MerceariaNova', 'Consumer')
        ]
        users = {}
        for username, role in users_config:
            user = User.objects.filter(username__iexact=username).first()
            if user:
                # Atualizar a password para "123"
                user.set_password("123")
                user.save()
            else:
                user = User.objects.create_user(username=username, password="123")
                self.stdout.write(f"Utilizador {username} criado com a senha '123'")
            user.groups.add(groups[role])
            if role not in users:
                users[role] = []
            users[role].append(user)

        # 3. Limpeza dos Dados Transacionais com Transação SQL
        with transaction.atomic():
            self.stdout.write("A remover dados antigos de forma instantanea (TRUNCATE)...")
            with connection.cursor() as cursor:
                cursor.execute("""
                    TRUNCATE TABLE 
                        marketplace_orders, 
                        harvest_records, 
                        blockchain_blocks, 
                        warehouse_sensor_readings, 
                        plantation_crops, 
                        plantation_events, 
                        plantation_plan, 
                        event_fertilizer_synthetic, 
                        event_fertilizer_organic, 
                        event_soil_corrective, 
                        event_pest_control, 
                        event_machinery, 
                        event_fuel, 
                        event_electric_energy, 
                        event_irrigation_water,
                        consolidated_stock,
                        products, 
                        warehouses
                    RESTART IDENTITY CASCADE;
                """)

            # 4. Configurar Subfamílias de Produtos
            subfamilies_data = [
                ("Gala", "Apple", maca_gala),
                ("Fuji", "Apple", maca_fuji),
                ("Hayward", "Kiwi", kiwi_hayward)
            ]
            sf_objects = {}
            for name, fruit_type, presets in subfamilies_data:
                subfamily, _ = ProductSubFamily.objects.get_or_create(name=name, fruit_type=fruit_type)
                subfamily.lifecycle_presets = presets
                subfamily.save()
                sf_objects[name] = subfamily

            # 5. Configurar Plantações e Culturas do zero para os Produtores
            plantations = {}
            # Braga growing Gala
            pb_user = User.objects.get(username='ProducerBraga')
            pb_prod = Product.objects.get_or_create(name="Maçã Gala", category="Apple", producer=pb_user)[0]
            pb_plan = PlantationPlan.objects.create(
                producer=pb_user, product=pb_prod, plantation_name="Pomar Braga Gala",
                quantity_of_trees=1200, production_type='integrated', chemical_use='No',
                area=50000.0, location="Braga", plantation_date=datetime.date(2022, 1, 1)
            )
            PlantationCrop.objects.create(plantation=pb_plan, subfamily=sf_objects['Gala'])
            plantations['ProducerBraga'] = pb_plan

            # Porto growing Fuji
            pp_user = User.objects.get(username='ProducerPorto')
            pp_prod = Product.objects.get_or_create(name="Maçã Fuji", category="Apple", producer=pp_user)[0]
            pp_plan = PlantationPlan.objects.create(
                producer=pp_user, product=pp_prod, plantation_name="Pomar Porto Fuji",
                quantity_of_trees=1000, production_type='organic', chemical_use='No',
                area=40000.0, location="Porto", plantation_date=datetime.date(2022, 3, 1)
            )
            PlantationCrop.objects.create(plantation=pp_plan, subfamily=sf_objects['Fuji'])
            plantations['ProducerPorto'] = pp_plan

            # Coimbra growing Hayward
            pc_user = User.objects.get(username='ProducerCoimbra')
            pc_prod = Product.objects.get_or_create(name="Kiwi Hayward", category="Kiwi", producer=pc_user)[0]
            pc_plan = PlantationPlan.objects.create(
                producer=pc_user, product=pc_prod, plantation_name="Pomar Coimbra Kiwi",
                quantity_of_trees=800, production_type='integrated', chemical_use='No',
                area=30000.0, location="Coimbra", plantation_date=datetime.date(2022, 5, 1)
            )
            PlantationCrop.objects.create(plantation=pc_plan, subfamily=sf_objects['Hayward'])
            plantations['ProducerCoimbra'] = pc_plan

            # 6. Configurar Armazéns por Dono
            warehouses = {}
            wh_configs = [
                # Producers
                ('ProducerBraga', 'Braga Warehouse', 15000.0),
                ('ProducerPorto', 'Porto Warehouse', 12000.0),
                ('ProducerCoimbra', 'Coimbra Warehouse', 10000.0),
                # Processors
                ('Processor', 'Porto Processing Centre', 25000.0),
                ('ProcessorNorte', 'Norte Processing Centre', 20000.0),
                ('ProcessorSul', 'Sul Processing Centre', 20000.0),
                # Retailer
                ('RetailStore', 'RetailStore Main Depot', 30000.0)
            ]
            for username, loc, cap in wh_configs:
                owner = User.objects.get(username=username)
                wh = Warehouse.objects.create(
                    owner=owner,
                    location=loc,
                    control_type='Controlled',
                    capacity=cap
                )
                sensor_temp, _ = Sensor.objects.get_or_create(brand="RuuviTag Pro", sensor_type="Temperature")
                sensor_hum, _ = Sensor.objects.get_or_create(brand="RuuviTag Pro", sensor_type="Humidity")
                wh.sensors.add(sensor_temp, sensor_hum)
                warehouses[username] = wh

            # 7. Gerar Leituras Diárias dos Sensores dos últimos 3 anos (1095 dias)
            self.stdout.write("A gerar leituras diárias dos sensores para os últimos 3 anos...")
            today = datetime.date.today()
            start_date = today - datetime.timedelta(days=1095)
            
            readings_list = []
            for day_offset in range(1096):
                curr_date = start_date + datetime.timedelta(days=day_offset)
                seasonal_factor = math.sin((day_offset / 365.0) * 2.0 * math.pi)
                
                # Gerar leituras para todos os 7 armazéns
                for wh_name, wh_obj in warehouses.items():
                    readings_list.append(WarehouseSensorReading(
                        warehouse=wh_obj,
                        date=curr_date,
                        temperature=round(4.2 + 0.6 * seasonal_factor + random.uniform(-0.3, 0.3), 2),
                        humidity=round(89.0 + random.uniform(-1.5, 1.5), 2),
                        ethylene=round(0.07 + 0.03 * seasonal_factor + random.uniform(-0.01, 0.01), 3)
                    ))
                
            WarehouseSensorReading.objects.bulk_create(readings_list)
            self.stdout.write(f"Geradas {len(readings_list)} leituras diárias de sensores em todos os armazéns.")

            # 8. Simular Ciclo Sequencial de Negócio Tri-anual (a cada 14 dias)
            self.stdout.write("A simular 3 anos de colheitas, compras, processamento, transportes e vendas...")
            current_sim_date = start_date
            batch_count = 0
            
            # Cadeias de fornecimento para a simulação sequencial:
            supply_chains = [
                {
                    'producer': 'ProducerBraga',
                    'subfamily': 'Gala',
                    'processor': 'Processor',
                    'wh_prod': warehouses['ProducerBraga'],
                    'wh_proc': warehouses['Processor']
                },
                {
                    'producer': 'ProducerPorto',
                    'subfamily': 'Fuji',
                    'processor': 'ProcessorNorte',
                    'wh_prod': warehouses['ProducerPorto'],
                    'wh_proc': warehouses['ProcessorNorte']
                },
                {
                    'producer': 'ProducerCoimbra',
                    'subfamily': 'Hayward',
                    'processor': 'ProcessorSul',
                    'wh_prod': warehouses['ProducerCoimbra'],
                    'wh_proc': warehouses['ProcessorSul']
                }
            ]
            
            retailer_user = User.objects.get(username='RetailStore')
            transporter_user = User.objects.get(username='Transportes')
            consumer_users = [User.objects.get(username=u[0]) for u in users_config if u[1] == 'Consumer']

            total_days = ((today - datetime.timedelta(days=15)) - start_date).days
            while current_sim_date < today - datetime.timedelta(days=15):
                days_elapsed = (current_sim_date - start_date).days
                percentage = min(100.0, (days_elapsed / total_days) * 100.0) if total_days > 0 else 100.0
                self.stdout.write(f"[PROGRESSO] {percentage:.1f}% concluido (Data simulada: {current_sim_date})...")
                for chain_info in supply_chains:
                    prod_name = chain_info['producer']
                    subfamily = sf_objects[chain_info['subfamily']]
                    proc_name = chain_info['processor']
                    wh_prod = chain_info['wh_prod']
                    wh_proc = chain_info['wh_proc']
                    
                    prod_user = User.objects.get(username=prod_name)
                    proc_user = User.objects.get(username=proc_name)
                    plantation = plantations[prod_name]
                    
                    # 8.1 Criação da Colheita (Producer)
                    harvest_qty = random.randint(2000, 4000)
                    harvest = Harvest.objects.create(
                        producer=prod_user,
                        subfamily=subfamily,
                        harvest_date=current_sim_date,
                        harvest_quantity_kg=harvest_qty,
                        delivered_quantity_kg=harvest_qty,
                        avg_quality_score=random.randint(8, 10),
                        utilized_quantity_kg=0.0,
                        caliber=round(random.uniform(70.0, 80.0), 1),
                        soluble_solids=round(random.uniform(11.5, 14.5), 1),
                        warehouse=wh_prod,
                        plantation=plantation
                    )
                    
                    # Registar bloco GENESIS na blockchain
                    dossier = create_genesis_dossier(harvest)
                    data_hash = blockchain_service.generate_dossier_hash(dossier)
                    blockchain_service.sign_and_submit_block(
                        user_role='Producer',
                        batch_id=f"LOTE-{harvest.pk}",
                        data_hash=data_hash,
                        event_type="Genesis",
                        data_payload=dossier
                    )
                    
                    # 8.2 Compra pelo Processador com registo de Transporte e Bloco de Transporte
                    order_date = current_sim_date + datetime.timedelta(days=1)
                    order_proc = MarketplaceOrder.objects.create(
                        requester=proc_user,
                        role='Processor',
                        order_type='BUY',
                        culture=subfamily,
                        harvest_origin=harvest,
                        quantity_kg=harvest_qty,
                        price_per_kg=round(random.uniform(0.8, 1.1), 2),
                        warehouse_location=wh_proc.location,
                        caliber=harvest.caliber,
                        soluble_solids=harvest.soluble_solids,
                        quality_score=harvest.avg_quality_score,
                        status='APPROVED',
                        fulfilled_by=prod_user,
                        created_at=timezone.make_aware(datetime.datetime.combine(order_date, datetime.time(9, 0))),
                        fulfilled_at=timezone.make_aware(datetime.datetime.combine(order_date, datetime.time(10, 0))),
                        transport_status='DELIVERED',
                        planned_pickup_date=timezone.make_aware(datetime.datetime.combine(order_date, datetime.time(13, 0))),
                        planned_delivery_date=timezone.make_aware(datetime.datetime.combine(order_date, datetime.time(17, 0))),
                        actual_pickup_date=timezone.make_aware(datetime.datetime.combine(order_date, datetime.time(13, 10))),
                        actual_delivery_date=timezone.make_aware(datetime.datetime.combine(order_date, datetime.time(16, 50))),
                        transport_sensor_data=json.dumps([
                            {"time": "13:30", "temp": 5.0, "humidity": 88.0},
                            {"time": "14:30", "temp": 4.8, "humidity": 89.0},
                            {"time": "15:30", "temp": 4.9, "humidity": 88.5}
                        ])
                    )
                    
                    # Bloco de Transporte (Supplier Purchase)
                    dossier_transport1 = {
                        "event": "Supplier_Purchase_Transport",
                        "order_id": order_proc.pk,
                        "from_warehouse": wh_prod.location,
                        "to_warehouse": wh_proc.location,
                        "transporter": "Transportes",
                        "planned_pickup": order_proc.planned_pickup_date.isoformat(),
                        "planned_delivery": order_proc.planned_delivery_date.isoformat(),
                        "actual_pickup": order_proc.actual_pickup_date.isoformat(),
                        "actual_delivery": order_proc.actual_delivery_date.isoformat(),
                        "sensor_summary": "Transit environment verified (T ~ 4.9 C, RH ~ 88.5 %)",
                        "date": order_date.isoformat()
                    }
                    blockchain_service.sign_and_submit_block(
                        user_role='Transporter',
                        batch_id=f"LOTE-{harvest.pk}",
                        data_hash=blockchain_service.generate_dossier_hash(dossier_transport1),
                        event_type="Supplier_Purchase_Transport",
                        data_payload=dossier_transport1
                    )
                    
                    # 8.3 Processador processa o produto
                    process_date = current_sim_date + datetime.timedelta(days=2)
                    order_proc.is_processed = True
                    order_proc.packaging_type = 'Cardboard'
                    order_proc.preservation_treatment = 'Natural'
                    order_proc.save()
                    
                    dossier_processing = {
                        "event": "Batch_Processing",
                        "order_id": order_proc.pk,
                        "processor": proc_name,
                        "packaging": "Cardboard",
                        "treatment": "Natural",
                        "date": process_date.isoformat()
                    }
                    blockchain_service.sign_and_submit_block(
                        user_role='Processor',
                        batch_id=f"LOTE-{harvest.pk}",
                        data_hash=blockchain_service.generate_dossier_hash(dossier_processing),
                        event_type="Batch_Processing",
                        inputs=[f"LOTE-{harvest.pk}"],
                        data_payload=dossier_processing
                    )
                    
                    # 8.4 RetailStore compra o lote processado (MarketplaceOrder BUY)
                    retail_date = current_sim_date + datetime.timedelta(days=3)
                    order_retail = MarketplaceOrder.objects.create(
                        requester=retailer_user,
                        role='Retailer',
                        order_type='BUY',
                        culture=subfamily,
                        harvest_origin=harvest,
                        quantity_kg=harvest_qty,
                        price_per_kg=round(order_proc.price_per_kg + random.uniform(0.5, 0.8), 2),
                        warehouse_location=warehouses['RetailStore'].location,
                        caliber=harvest.caliber,
                        soluble_solids=harvest.soluble_solids,
                        quality_score=harvest.avg_quality_score,
                        status='APPROVED',
                        fulfilled_by=proc_user,
                        created_at=timezone.make_aware(datetime.datetime.combine(retail_date, datetime.time(9, 30))),
                        fulfilled_at=timezone.make_aware(datetime.datetime.combine(retail_date, datetime.time(10, 30))),
                        transport_status='DELIVERED',
                        planned_pickup_date=timezone.make_aware(datetime.datetime.combine(retail_date, datetime.time(11, 0))),
                        planned_delivery_date=timezone.make_aware(datetime.datetime.combine(retail_date, datetime.time(15, 0))),
                        actual_pickup_date=timezone.make_aware(datetime.datetime.combine(retail_date, datetime.time(11, 15))),
                        actual_delivery_date=timezone.make_aware(datetime.datetime.combine(retail_date, datetime.time(14, 45))),
                        transport_sensor_data=json.dumps([
                            {"time": "11:30", "temp": 5.2, "humidity": 86.0},
                            {"time": "12:30", "temp": 5.4, "humidity": 86.5},
                            {"time": "13:30", "temp": 5.5, "humidity": 85.0}
                        ]),
                        is_processed=True,
                        packaging_type='Cardboard',
                        preservation_treatment='Natural'
                    )
                    
                    # Bloco de Transporte (Retail Purchase)
                    dossier_transport2 = {
                        "event": "Retail_Purchase_Transport",
                        "order_id": order_retail.pk,
                        "from_warehouse": wh_proc.location,
                        "to_warehouse": warehouses['RetailStore'].location,
                        "transporter": "Transportes",
                        "planned_pickup": order_retail.planned_pickup_date.isoformat(),
                        "planned_delivery": order_retail.planned_delivery_date.isoformat(),
                        "actual_pickup": order_retail.actual_pickup_date.isoformat(),
                        "actual_delivery": order_retail.actual_delivery_date.isoformat(),
                        "sensor_summary": "Transit environment verified (T ~ 5.3 C, RH ~ 85.8 %)",
                        "date": retail_date.isoformat()
                    }
                    blockchain_service.sign_and_submit_block(
                        user_role='Transporter',
                        batch_id=f"LOTE-{harvest.pk}",
                        data_hash=blockchain_service.generate_dossier_hash(dossier_transport2),
                        event_type="Retail_Purchase_Transport",
                        data_payload=dossier_transport2
                    )

                    # 8.5 Vendas diárias com sazonalidade e ruído para os 8 Consumidores
                    remaining_qty = harvest_qty
                    sales_days = list(range(3, 14))  # Vendas contínuas do dia 3 ao dia 13
                    
                    # 1. Calcular pesos baseados no dia da semana + ruído
                    day_weights = []
                    for idx, ds in enumerate(sales_days):
                        sale_date = current_sim_date + datetime.timedelta(days=ds)
                        
                        # Feriados nacionais principais em Portugal (fechados -> peso 0)
                        if (sale_date.month == 12 and sale_date.day == 25) or (sale_date.month == 1 and sale_date.day == 1):
                            weight = 0.0
                        else:
                            # Sazonalidade Semanal (0 = Segunda, 5 = Sábado, 6 = Domingo)
                            weekday = sale_date.weekday()
                            weekday_map = {0: 0.8, 1: 0.85, 2: 0.9, 3: 1.0, 4: 1.25, 5: 1.4, 6: 0.6}
                            weight = weekday_map.get(weekday, 1.0) * random.uniform(0.8, 1.2)
                        
                        day_weights.append((sale_date, weight, idx))
                    
                    total_weight = sum(w[1] for w in day_weights)
                    
                    # 2. Distribuir e criar as ordens
                    for idx_w, (sale_date, weight, day_idx) in enumerate(day_weights):
                        if remaining_qty <= 0:
                            break
                            
                        if total_weight > 0:
                            if idx_w == len(day_weights) - 1:
                                sale_qty = remaining_qty
                            else:
                                sale_qty = round((weight / total_weight) * harvest_qty, 2)
                                sale_qty = min(sale_qty, remaining_qty)
                        else:
                            sale_qty = 0
                            
                        # Limites de segurança da quantidade de venda individual
                        sale_qty = max(0.0, sale_qty)
                        if sale_qty < 5.0 and idx_w < len(day_weights) - 1:
                            continue  # ignora vendas insignificantes exceto no último dia
                            
                        remaining_qty -= sale_qty
                        consumer_user = random.choice(consumer_users)
                        
                        order_sale = MarketplaceOrder.objects.create(
                            requester=consumer_user,
                            role='Consumer',
                            order_type='BUY',
                            culture=subfamily,
                            harvest_origin=harvest,
                            quantity_kg=sale_qty,
                            price_per_kg=round(order_retail.price_per_kg + random.uniform(0.7, 1.2), 2),
                            warehouse_location="Consumer Location",
                            caliber=harvest.caliber,
                            soluble_solids=harvest.soluble_solids,
                            quality_score=max(1, harvest.avg_quality_score - (day_idx // 2)),
                            status='APPROVED',
                            fulfilled_by=retailer_user,
                            created_at=timezone.make_aware(datetime.datetime.combine(sale_date, datetime.time(15, 0))),
                            fulfilled_at=timezone.make_aware(datetime.datetime.combine(sale_date, datetime.time(16, 0))),
                            transport_status='DELIVERED',
                            is_processed=True
                        )
                        
                        dossier_sale = {
                            "event": "Final_Consumer_Sale",
                            "order_id": order_sale.pk,
                            "buyer": consumer_user.username,
                            "seller": "RetailStore",
                            "qty_kg": float(sale_qty),
                            "price_per_kg": float(order_sale.price_per_kg),
                            "date": sale_date.isoformat()
                        }
                        
                        try:
                            blockchain_service.sign_and_submit_block(
                                user_role='Consumer',
                                batch_id=f"LOTE-{harvest.pk}-VENDA-{day_idx}",
                                data_hash=blockchain_service.generate_dossier_hash(dossier_sale),
                                event_type="Final_Consumer_Sale",
                                inputs=[f"LOTE-{harvest.pk}"],
                                data_payload=dossier_sale
                            )
                        except Exception as e:
                            # Evita falhar se houver algum erro de blockchain
                            pass
                            
                    batch_count += 1
                
                # Avança 14 dias no tempo da simulação
                current_sim_date += datetime.timedelta(days=14)

        self.stdout.write(self.style.SUCCESS(
            f"Base de dados populada com sucesso! Criadas {batch_count} colheitas e transações sequenciais complexas cobrindo os últimos 3 anos para 3 Produtores, 3 Processadores, RetailStore e 8 Consumidores. Todos os blocos Genesis e de Transporte foram registados."
        ))
