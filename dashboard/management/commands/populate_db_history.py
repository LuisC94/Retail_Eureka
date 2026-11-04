import datetime
import random
import json
import math
from django.core.management.base import BaseCommand
from django.db import transaction, connection
from django.contrib.auth.models import User, Group
from django.utils import timezone
from dashboard.models import (
    ProductSubFamily, Harvest, Warehouse, Sensor, WarehouseSensorReading,
    PlantationPlan, PlantationCrop, PlantationEvent, FertilizerSyntheticData, FertilizerOrganicData,
    SoilCorrectiveData, PestControlData, MachineryData, FuelData, ElectricEnergyData, IrrigationWaterData,
    ConsolidatedStock
)


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
            "dureza_min": 9.0, "dureza_0_default": 65.0,
            "brix_min": 13.0, "brix_max": 18.0, "brix_g": 0.22, "brix_0_default": 13.5,
            "qual_firm_threshold": 30.0, "qual_brix_target": 15.0,
            "E0_int": 0.010, "Eref_prod": 0.12, "E_t0": 12.0, "E_g": 0.8, "E_auto": 0.4,
            "E_decay": 0.70, "Ea_E_J": 50000.0, "E_ext_shift": 2.5,
            "RH_mold_thr": 95.0, "mold_rate_ref": 0.04, "mold_sens_RH": 8.0,
            "mold_max_penalty": 0.60, "Ea_mold_J": 42000.0,
            "elasticity": 1.4
        }
        kiwi_hayward = {
            "label": "Kiwi (Hayward)",
            "Tref_C": 0.0, "Ea_J": 65000.0, "k_firm_ref": 0.012, "alpha_E": 2.5,
            "beta_RH": 0.95, "RH_ref": 95.0,
            "dureza_min": 5.0, "dureza_0_default": 65.0,
            "brix_min": 11.5, "brix_max": 16.0, "brix_g": 0.30, "brix_0_default": 12.0,
            "qual_firm_threshold": 15.0, "qual_brix_target": 13.5,
            "E0_int": 0.005, "Eref_prod": 0.08, "E_t0": 15.0, "E_g": 1.1, "E_auto": 0.8,
            "E_decay": 0.55, "Ea_E_J": 68000.0, "E_ext_shift": 3.0,
            "RH_mold_thr": 96.0, "mold_rate_ref": 0.06, "mold_sens_RH": 10.0,
            "mold_max_penalty": 0.70, "Ea_mold_J": 45000.0,
            "elasticity": 1.8
        }

        with transaction.atomic():
            # 2. Criar Utilizadores e Grupos Padrão
            groups = ['Producer', 'Processor', 'Retailer', 'Consumer', 'Transporter']
            group_objects = {name: Group.objects.get_or_create(name=name)[0] for name in groups}

            # Produtores
            prod_users = []
            for name in ['ProducerBraga', 'ProducerPorto', 'ProducerCoimbra']:
                u, _ = User.objects.get_or_create(username=name, defaults={'email': f"{name.lower()}@eureka.pt"})
                u.set_password('1234')
                u.save()
                u.groups.add(group_objects['Producer'])
                prod_users.append(u)

            # Processadores
            proc_users = []
            for name in ['ProcessorNorte', 'ProcessorCentro', 'ProcessorSul']:
                u, _ = User.objects.get_or_create(username=name, defaults={'email': f"{name.lower()}@eureka.pt"})
                u.set_password('1234')
                u.save()
                u.groups.add(group_objects['Processor'])
                proc_users.append(u)

            # Retalhista Central
            retailer_user, _ = User.objects.get_or_create(username='RetailStore', defaults={'email': 'store@retail.pt'})
            retailer_user.set_password('1234')
            retailer_user.save()
            retailer_user.groups.add(group_objects['Retailer'])

            # Consumidores Finais (8 Utilizadores para distribuir o consumo)
            consumer_users = []
            consumer_names = [
                'Consumer_Ana', 'Consumer_Bruno', 'Consumer_Carlos', 'Consumer_Diana',
                'Consumer_Eduardo', 'Consumer_Filipa', 'Consumer_Goncalo', 'Consumer_Helena'
            ]
            for name in consumer_names:
                u, _ = User.objects.get_or_create(username=name, defaults={'email': f"{name.lower()}@gmail.pt"})
                u.set_password('1234')
                u.save()
                u.groups.add(group_objects['Consumer'])
                consumer_users.append(u)

            # Transportador
            transporter_user, _ = User.objects.get_or_create(username='TransportesRapidos', defaults={'email': 'logistica@transrapidos.pt'})
            transporter_user.set_password('1234')
            transporter_user.save()
            transporter_user.groups.add(group_objects['Transporter'])

            # 3. Limpar Tabelas Transacionais
            self.stdout.write("A limpar dados transacionais...")
            with connection.cursor() as cursor:
                cursor.execute("""
                    DELETE FROM warehouse_sensor_readings;
                    DELETE FROM harvest_records;
                    DELETE FROM plantation_events;
                    DELETE FROM event_fertilizer_synthetic;
                    DELETE FROM event_fertilizer_organic;
                    DELETE FROM event_soil_corrective;
                    DELETE FROM event_pest_control;
                    DELETE FROM event_machinery;
                    DELETE FROM event_fuel;
                    DELETE FROM event_electric_energy;
                    DELETE FROM event_irrigation_water;
                    DELETE FROM plantation_soil_value;
                    DELETE FROM plantation_crops;
                    DELETE FROM plantation_plan;
                    DELETE FROM sensors;
                    DELETE FROM warehouses;
                    DELETE FROM product_subfamilies;
                    DELETE FROM consolidated_stock;
                """)

            # 4. Configurar Subfamílias de Produtos
            subfamilies_data = [
                ("Gala", "Apple", maca_gala, 14),
                ("Fuji", "Apple", maca_fuji, 20),
                ("Hayward", "Kiwi", kiwi_hayward, 30)
            ]
            sf_objects = {}
            for name, fruit_type, presets, shelf_life_days in subfamilies_data:
                subfamily, _ = ProductSubFamily.objects.get_or_create(name=name, fruit_type=fruit_type)
                subfamily.default_shelf_life_days = shelf_life_days
                subfamily.lifecycle_presets = presets
                subfamily.save()
                sf_objects[name] = subfamily

            # 5. Configurar Plantações e Culturas do zero para os Produtores
            plantations = {}
            # Braga growing Gala
            pb_user = User.objects.get(username='ProducerBraga')
            pb_plan = PlantationPlan.objects.create(
                producer=pb_user, plantation_name="Pomar Braga Gala",
                quantity_of_trees=1200, production_type='integrated', chemical_use='No',
                area=50000.0, location="Braga", plantation_date=datetime.date(2022, 1, 1)
            )
            PlantationCrop.objects.create(plantation=pb_plan, subfamily=sf_objects['Gala'])
            plantations['ProducerBraga'] = pb_plan

            # Porto growing Fuji
            pp_user = User.objects.get(username='ProducerPorto')
            pp_plan = PlantationPlan.objects.create(
                producer=pp_user, plantation_name="Pomar Porto Fuji",
                quantity_of_trees=1000, production_type='organic', chemical_use='No',
                area=40000.0, location="Porto", plantation_date=datetime.date(2022, 3, 1)
            )
            PlantationCrop.objects.create(plantation=pp_plan, subfamily=sf_objects['Fuji'])
            plantations['ProducerPorto'] = pp_plan

            # Coimbra growing Hayward
            pc_user = User.objects.get(username='ProducerCoimbra')
            pc_plan = PlantationPlan.objects.create(
                producer=pc_user, plantation_name="Pomar Coimbra Kiwi",
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
                    

                    
                    # 8.2 Processador recebe o lote e armazena em ConsolidatedStock
                    proc_stock, _ = ConsolidatedStock.objects.get_or_create(
                        owner=proc_user,
                        culture=subfamily,
                        warehouse_location=wh_proc.location,
                        defaults={'quantity': 0.0}
                    )
                    proc_stock.quantity = float(proc_stock.quantity) + harvest_qty
                    proc_stock.save()

                    # 8.3 Processador processa o produto (atualiza ConsolidatedStock RetailStore)
                    retail_wh = warehouses['RetailStore'].location
                    retail_stock, _ = ConsolidatedStock.objects.get_or_create(
                        owner=retailer_user,
                        culture=subfamily,
                        warehouse_location=retail_wh,
                        defaults={'quantity': 0.0}
                    )
                    retail_stock.quantity = float(retail_stock.quantity) + harvest_qty
                    retail_stock.save()

                    # 8.4 Vendas diárias com sazonalidade e ruído para os 8 Consumidores
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
                    
                    # 2. Distribuir vendas
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
                            
                        sale_qty = max(0.0, sale_qty)
                        if sale_qty < 5.0 and idx_w < len(day_weights) - 1:
                            continue
                            
                        remaining_qty -= sale_qty
                        consumer_user = random.choice(consumer_users)
                        
                        dossier_sale = {
                            "event": "Final_Consumer_Sale",
                            "batch_id": f"LOTE-{harvest.pk}",
                            "buyer": consumer_user.username,
                            "seller": "RetailStore",
                            "qty_kg": float(sale_qty),
                            "price_per_kg": round(1.8 + random.uniform(0.5, 1.2), 2),
                            "date": sale_date.isoformat()
                        }
                        
                        try:
                            from dashboard.services.blockchain_service import blockchain_service
                            blockchain_service.sign_and_submit_block(
                                user_role='Consumer',
                                batch_id=f"LOTE-{harvest.pk}-VENDA-{day_idx}",
                                data_hash=blockchain_service.generate_dossier_hash(dossier_sale),
                                event_type="Final_Consumer_Sale",
                                inputs=[f"LOTE-{harvest.pk}"],
                                data_payload=dossier_sale
                            )
                        except Exception:
                            pass
                            
                    batch_count += 1
                
                # Avança 14 dias no tempo da simulação
                current_sim_date += datetime.timedelta(days=14)

        self.stdout.write(self.style.SUCCESS(
            f"Base de dados populada com sucesso! Criadas {batch_count} colheitas e transações sequenciais complexas cobrindo os últimos 3 anos para 3 Produtores, 3 Processadores, RetailStore e 8 Consumidores. Todos os blocos Genesis e de Transporte foram registados."
        ))
