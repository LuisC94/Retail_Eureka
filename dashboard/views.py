import os
import threading
from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Sum, Q
from django import forms
from dashboard.services.agent_service import FORECAST_MARKER_TYPES, forecast_model_display
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views import View
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.urls import reverse, reverse_lazy 
from .decorators import role_required 
from django.contrib.auth.models import Group
from django.contrib import messages

from .models import (
    PlantationPlan, Harvest, Warehouse, Sensor, UserProfile, PlantationEvent,
    SoilCharacteristic, PlantationSoilValue, ProductSubFamily, PlantationCrop,
    FertilizerSyntheticData, FertilizerOrganicData, SoilCorrectiveData, PestControlData,
    MachineryData, FuelData, ElectricEnergyData, IrrigationWaterData,
    ConsolidatedStock, TrainedModel, Vehicle, Route, StoreProcessorAssociation,
    HistoricalSalesData, DemandForecast
)
from dashboard.utils import create_genesis_dossier
from dashboard.services.fabric_service import fabric_service
from dashboard.services.marketplace_service import marketplace_service
from dashboard.services.market_news_service import market_news_service
import logging
logger = logging.getLogger(__name__)

from .forms import (
    UserRegisterForm, PlantationPlanForm, PlantationDetailForm,
    HarvestForm, WarehouseRegistrationForm, SensorRegistrationForm, PlantationEventForm,
    FertilizerSyntheticForm, FertilizerOrganicForm, SoilCorrectiveForm, PestControlForm,
    MachineryForm, FuelForm, ElectricEnergyForm, IrrigationWaterForm, SoilCharacteristicForm, PlantationCropForm, MarketplaceOrderForm,
    MarketSellOrderForm,
    TransportPlanForm, TransportDeliveryForm, ProcessorProcessingForm, VehicleForm
)

# ----------------------------------------------------------------------
# 1. VIEWS DE ADMIN E AUTENTICAÇÃO
# ----------------------------------------------------------------------

@method_decorator(login_required, name='dispatch')
class AdminDashboardView(View):
    # Lógica de redirecionamento/renderização do Admin (Mantida)
    def get(self, request):
        user = request.user
        role_map = {
            'Admin': None, 
            'Retailer': 'retailer_dashboard',
            'Processor': 'processor_dashboard',
            'Consumer': 'consumer_dashboard',
            'Transporter': 'transporter_dashboard', 
            'Producer': 'producer_dashboard',
        }
        
        if user.is_superuser or user.groups.filter(name='Admin').exists():
            context = { 'username': user.username, 'role': 'Admin' }
            return render(request, 'dashboard/adminDash.html', context)
        
        for group_name, url_name in role_map.items():
            if group_name != 'Admin' and user.groups.filter(name=group_name).exists():
                return redirect(url_name)
                
        return redirect('login') 

class RegisterView(View):
    # Método GET: Para CARREGAR a página de registo
    def get(self, request):
        form = UserRegisterForm()
        return render(request, 'registration/register.html', {'form': form}) 

    # Método POST: Para PROCESSAR a submissão
    def post(self, request):
        form = UserRegisterForm(request.POST)
        
        if form.is_valid():
            # 1. Salvar o Objeto User (Modelo Django Padrão)
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()

            # 2. Salvar o Objeto UserProfile (NOVO - Morada e Telemóvel)
            UserProfile.objects.create(
                user=user,
                phone_number=form.cleaned_data['phone_number'],
                address=form.cleaned_data['address']
            )

            # 3. Lógica do Grupo (Role)
            selected_role_name = form.cleaned_data['role']
            try:
                group = Group.objects.get(name=selected_role_name)
                user.groups.add(group)
            except Group.DoesNotExist:
                print(f"Atenção: O grupo '{selected_role_name}' não existe. O utilizador foi criado sem grupo.")
            
            # 4. Redireciona para a página de Login
            return redirect('login') 
            
        # Se o formulário for inválido (erros de senha/validação), re-renderiza
        return render(request, 'registration/register.html', {'form': form})

# ----------------------------------------------------------------------
# 2. DASHBOARD VIEWS PARA OUTROS PERFIS (Mantidas)
# ----------------------------------------------------------------------

import json
import unicodedata
import re
import hashlib

PORTUGAL_LOCATIONS_MAP = {
    'lisboa': (38.7223, -9.1393), 'porto': (41.1579, -8.6291), 'coimbra': (40.2033, -8.4103),
    'braga': (41.5454, -8.4265), 'faro': (37.0179, -7.9308), 'aveiro': (40.6405, -8.6538),
    'leiria': (39.7438, -8.8078), 'setubal': (38.5244, -8.8882), 'santarem': (39.2362, -8.6814),
    'evora': (38.5714, -7.9135), 'viseu': (40.6566, -7.9125), 'guarda': (40.5365, -7.2684),
    'castelo branco': (39.8222, -7.4909), 'braganca': (41.8058, -6.7572), 'vila real': (41.3010, -7.7422),
    'viana do castelo': (41.6932, -8.8328), 'portalegre': (39.2938, -7.4312), 'beja': (38.0153, -7.8652),
    'guimaraes': (41.4425, -8.2918), 'lordelo': (41.3120, -8.4150), 'ronfe': (41.4402, -8.3650),
    'santo tirso': (41.3431, -8.4738), 'espinho': (40.9930, -8.6342), 'famalicao': (41.4077, -8.5196),
    'barcelos': (41.5388, -8.6151), 'maia': (41.2330, -8.6210), 'matosinhos': (41.1834, -8.6807),
    'gaia': (41.1336, -8.6174), 'sintra': (38.8029, -9.3817), 'cascais': (38.6970, -9.4223),
    'almada': (38.6790, -9.1569), 'seixal': (38.6416, -9.0988), 'barreiro': (38.6633, -9.0734),
    'loures': (38.8315, -9.1681), 'amadora': (38.7538, -9.2308), 'oeiras': (38.6979, -9.3106),
    'odivelas': (38.7954, -9.1852), 'pombal': (39.9157, -8.6278), 'caldas da rainha': (39.4034, -9.1369),
    'torres vedras': (39.0918, -9.2600), 'tomar': (39.6036, -8.4079), 'abrantes': (39.4635, -8.1983),
    'figueira da foz': (40.1508, -8.8618), 'penafiel': (41.2057, -8.2831), 'paredes': (41.2053, -8.3304),
    'felgueiras': (41.3655, -8.1969), 'amarante': (41.2729, -8.0776), 'lamego': (41.0967, -7.8103),
    'chaves': (41.7410, -7.4717), 'elvas': (38.8817, -7.1628), 'portimao': (37.1364, -8.5377),
    'lagos': (37.1028, -8.6730), 'olhao': (37.0286, -7.8411), 'tavira': (37.1261, -7.6499),
    'silves': (37.1887, -8.4398), 'sines': (37.9562, -8.8698),
}

def _resolve_geo_coords(loc_str, user=None, warehouse=None):
    if warehouse and warehouse.latitude and warehouse.longitude:
        return float(warehouse.latitude), float(warehouse.longitude)
    if not warehouse and loc_str and ' (wh:' in str(loc_str).lower():
        try:
            match = re.search(r'\(wh:\s*(\d+)\)', str(loc_str), re.IGNORECASE)
            if match:
                wh_id = int(match.group(1))
                wh = Warehouse.objects.filter(pk=wh_id).first()
                if wh and wh.latitude and wh.longitude:
                    return float(wh.latitude), float(wh.longitude)
                elif wh:
                    loc_str = wh.location
        except Exception:
            pass
            
    def _norm(t):
        if not t: return ''
        n = unicodedata.normalize('NFD', str(t).lower())
        return ''.join(c for c in n if unicodedata.category(c) != 'Mn')
        
    clean = _norm(loc_str)
    for city, coords in PORTUGAL_LOCATIONS_MAP.items():
        if city in clean:
            return coords
            
    if user:
        u_wh = Warehouse.objects.filter(owner=user).first()
        if u_wh:
            if u_wh.latitude and u_wh.longitude:
                return float(u_wh.latitude), float(u_wh.longitude)
            for city, coords in PORTUGAL_LOCATIONS_MAP.items():
                if city in _norm(u_wh.location):
                    return coords
        if hasattr(user, 'userprofile') and user.userprofile.address:
            for city, coords in PORTUGAL_LOCATIONS_MAP.items():
                if city in _norm(user.userprofile.address):
                    return coords
                    
    # Deterministic fallback inside Continental Portugal
    h = int(hashlib.md5((clean or 'portugal').encode('utf-8')).hexdigest()[:8], 16)
    lat = 37.5 + (h % 400) / 100.0
    lon = -8.9 + ((h >> 8) % 200) / 100.0
    return round(lat, 5), round(lon, 5)

def _get_assigned_deal_ids():
    """
    deal_ids que não estão disponíveis para transportadores: os que já estão numa rota
    e os negócios com transporte próprio (o comprador só confirma a receção).
    """
    assigned = set()
    for r in Route.objects.all():
        if r.optimized_path:
            found = re.findall(r'(?:Deal|Carga)\s*#([^\s\(\]]+)', r.optimized_path, re.IGNORECASE)
            assigned.update(found)
    from dashboard.services.reception_service import own_transport_deal_ids
    assigned.update(own_transport_deal_ids())
    return assigned

# Transporter Dashboard
@method_decorator(login_required, name='dispatch')
@method_decorator(role_required(['Transporter']), name='dispatch')
class TransporterDashboardView(View):
    def get(self, request):
        user = request.user
        
        # Frota de Veículos
        vehicles = Vehicle.objects.filter(owner=user).order_by('-created_at')
        vehicle_form = VehicleForm()

        # Verificar se atingiu o limiar de 6 transações para gerar rota ótima automática
        check_and_create_optimal_route()

        # 0. Mercado de Trabalho - Cargas de Negócios Concluídos (não atribuídas a nenhuma rota)
        assigned_deal_ids = _get_assigned_deal_ids()
        all_closed_deals = marketplace_service.get_closed_deals_adapted()
        open_orders = [d for d in all_closed_deals if str(d.id) not in assigned_deal_ids]

        # Mercado de Trabalho - Rotas Otimizadas Criadas (Pendente aceitação)
        open_routes = Route.objects.filter(
            status='PENDING'
        ).select_related('vehicle').order_by('-created_at')

        # Minhas Rotas Ativas (Aceites, Planeadas, Em Trânsito)
        my_active_routes = Route.objects.filter(
            transporter=user
        ).exclude(status='DELIVERED').select_related('vehicle').order_by('-created_at')

        # Histórico de Rotas Concluídas
        my_closed_routes = Route.objects.filter(
            transporter=user, 
            status='DELIVERED'
        ).select_related('vehicle').order_by('-created_at')

        # 1. Encomendas Individuais
        orders_ready_pickup = []
        orders_in_transit = []
        closed_orders_count = len(marketplace_service.fetch_deals())
        
        # Preparar dados JSON consolidados para o Mapa Leaflet (Rotas Otimizadas + Cargas Aceites)
        map_active_items = []
        all_deals = {str(d.get('deal_id')): d for d in (marketplace_service.fetch_deals() or [])}
        all_open_orders = {str(o.id): o for o in (marketplace_service.get_open_orders_adapted() or [])}
        
        # 1. Rotas Agrupadas
        for r in my_active_routes:
            r_orders = []
            if r.optimized_path:
                matches = list(re.finditer(r'(?:Deal|Carga)\s*#([^\s\(\]]+)\s*\(([^:]+):\s*([\d\.]+)\s*kg\)(?:\s*\[\s*(.*?)\s*->\s*(.*?)\s*\])?', r.optimized_path, re.IGNORECASE))
                if matches:
                    for m in matches:
                        item_id = m.group(1).strip()
                        culture_name = m.group(2).strip()
                        qty = float(m.group(3))
                        origin = m.group(4).strip() if m.group(4) else None
                        dest = m.group(5).strip() if m.group(5) else None
                        
                        # Se não tiver [Origem -> Destino] explícito, consultar do deal ou order
                        if not origin or not dest:
                            if item_id in all_deals:
                                d_info = all_deals[item_id]
                                origin = origin or d_info.get('warehouse_origin') or 'Armazém Virtual do Produtor'
                                dest = dest or d_info.get('destination_warehouse') or f"Armazém {d_info.get('buyer_id')}"
                            elif item_id in all_open_orders:
                                o_info = all_open_orders[item_id]
                                origin = origin or getattr(o_info, 'warehouse_location', None) or 'Armazém Produtor'
                                dest = dest or f"Armazém {o_info.requester.username}"
                            else:
                                origin = origin or "Armazém Produtor"
                                dest = dest or "Armazém Retalhista"
                                
                        o_lat, o_lon = _resolve_geo_coords(origin)
                        d_lat, d_lon = _resolve_geo_coords(dest)
                        pallets = round(qty / 500.0, 1) if qty else 0
                        crates = int(qty / 20.0) if qty else 0
                        
                        r_orders.append({
                            'id': item_id,
                            'origin': origin,
                            'dest': dest,
                            'culture': culture_name,
                            'quantity': qty,
                            'pallets': pallets,
                            'crates': crates,
                            'origin_lat': o_lat,
                            'origin_lon': o_lon,
                            'dest_lat': d_lat,
                            'dest_lon': d_lon,
                        })
                else:
                    o_lat, o_lon = _resolve_geo_coords("Armazém Produtor")
                    d_lat, d_lon = _resolve_geo_coords("Armazém Retalhista")
                    r_orders.append({
                        'id': str(r.id),
                        'origin': "Armazém Produtor",
                        'dest': "Armazém Retalhista",
                        'culture': "Produtos Hortícolas",
                        'quantity': float(r.total_weight_kg or 0.0),
                        'pallets': r.total_pallets,
                        'crates': r.total_crates,
                        'origin_lat': o_lat,
                        'origin_lon': o_lon,
                        'dest_lat': d_lat,
                        'dest_lon': d_lon,
                    })
            else:
                o_lat, o_lon = _resolve_geo_coords("Armazém Produtor")
                d_lat, d_lon = _resolve_geo_coords("Armazém Retalhista")
                r_orders.append({
                    'id': str(r.id),
                    'origin': "Armazém Produtor",
                    'dest': "Armazém Retalhista",
                    'culture': "Produtos Hortícolas",
                    'quantity': float(r.total_weight_kg or 0.0),
                    'pallets': r.total_pallets,
                    'crates': r.total_crates,
                    'origin_lat': o_lat,
                    'origin_lon': o_lon,
                    'dest_lat': d_lat,
                    'dest_lon': d_lon,
                })
            
            v_label = f"{r.vehicle.brand_model} ({r.vehicle.license_plate})" if r.vehicle else "Veículo Atribuído"
            map_active_items.append({
                'id': str(r.id),
                'display_id': f"Rota #{r.id}",
                'type': 'ROUTE',
                'status': r.get_status_display(),
                'status_code': r.status,
                'vehicle': v_label,
                'total_weight_kg': float(r.total_weight_kg),
                'total_pallets': r.total_pallets,
                'total_crates': r.total_crates,
                'optimized_path': r.optimized_path or "",
                'orders': r_orders
            })
            
        # 2. Cargas Individuais Aceites (Ready Pickup ou In Transit)
        for o in (list(orders_ready_pickup) + list(orders_in_transit)):
            o_lat, o_lon = _resolve_geo_coords(
                o.warehouse_location, 
                warehouse=o.harvest_origin.warehouse if o.harvest_origin else None
            )
            d_lat, d_lon = _resolve_geo_coords(
                f"Armazém {o.requester.username}", 
                user=o.requester
            )
            v_label = f"{o.vehicle.brand_model} ({o.vehicle.license_plate})" if o.vehicle else "Veículo Atribuído"
            map_active_items.append({
                'id': f"job_{o.id}",
                'display_id': f"Carga #{o.id}",
                'type': 'INDIVIDUAL',
                'status': o.get_transport_status_display(),
                'status_code': o.transport_status,
                'vehicle': v_label,
                'total_weight_kg': float(o.quantity_kg or 0.0),
                'total_pallets': o.total_pallets,
                'total_crates': o.total_crates,
                'optimized_path': f"{o.warehouse_location or 'Origem'} -> Armazém {o.requester.username}",
                'orders': [{
                    'id': o.id,
                    'origin': o.warehouse_location or f"Armazém Produtor ({o.fulfilled_by.username if o.fulfilled_by else 'Produtor'})",
                    'dest': f"Armazém {o.requester.username}",
                    'culture': o.culture.name if o.culture else "Produtos Hortícolas",
                    'quantity': float(o.quantity_kg or 0.0),
                    'pallets': o.total_pallets,
                    'crates': o.total_crates,
                    'origin_lat': o_lat,
                    'origin_lon': o_lon,
                    'dest_lat': d_lat,
                    'dest_lon': d_lon,
                }]
            })
            
        active_routes_json_data = json.dumps(map_active_items)
        
        try:
            user_profile = UserProfile.objects.get(user=user)
        except UserProfile.DoesNotExist:
            user_profile = None

        context = { 
            'username': user.username, 
            'role': 'Transporter',
            'user_profile': user_profile,
            
            # Listas de Veículos e Rotas
            'vehicles': vehicles,
            'vehicle_form': vehicle_form,
            'open_routes': open_routes,
            'my_active_routes': my_active_routes,
            'my_closed_routes': my_closed_routes,
            
            # Listas segmentadas individuais
            'open_market_orders': open_orders,
            'orders_ready_pickup': orders_ready_pickup,
            'orders_in_transit': orders_in_transit,
            'closed_orders_count': closed_orders_count,
            
            # Dados de Mapa Leaflet
            'active_routes_json_data': active_routes_json_data,
            'map_active_items_count': len(map_active_items),
            
            # Formulários
            'market_order_form': MarketplaceOrderForm(initial={'role': 'Transporter', 'order_type': 'BUY'}),
            'transport_delivery_form': TransportDeliveryForm(),
        }
        return render(request, 'dashboard/transporterDash.html', context)

# Consumer Dashboard
@method_decorator(login_required, name='dispatch')
@method_decorator(role_required(['Consumer']), name='dispatch')
class ConsumerDashboardView(View):
    def get(self, request):
        user = request.user
        open_orders = marketplace_service.get_open_orders_adapted()
        closed_orders = marketplace_service.get_closed_deals_adapted(username=user.username)

        try:
            user_profile = UserProfile.objects.get(user=user)
        except UserProfile.DoesNotExist:
            user_profile = None

        context = { 
            'username': user.username, 
            'role': 'Consumer',
            'user_profile': user_profile,
            'open_market_orders': open_orders,
            'closed_market_orders': closed_orders,
            'market_order_form': MarketplaceOrderForm(initial={'order_type': 'BUY'})
        }
        return render(request, 'dashboard/consumerDash.html', context)

# Receções de mercadoria (contexto comum a Processor e Retailer)
def _reception_context(user):
    from dashboard.models import DealReception
    from dashboard.services.reception_service import default_delivery_mode
    from dashboard.services.reception_service import warehouse_label
    pending = list(DealReception.objects.filter(buyer=user, status=DealReception.STATUS_PENDING)
                   .order_by('expected_date', 'created_at'))
    buyer_warehouses = list(Warehouse.objects.filter(owner=user).order_by('location'))
    labels = {warehouse_label(w): w.pk for w in buyer_warehouses}
    for r in pending:
        # Pré-seleciona o armazém de destino do negócio, se for um armazém registado
        r.default_warehouse_id = labels.get(r.destination_warehouse) or (buyer_warehouses[0].pk if buyer_warehouses else None)
    received = list(DealReception.objects.filter(buyer=user, status=DealReception.STATUS_RECEIVED)
                    .order_by('-received_at', '-confirmed_at')[:10])
    return {
        'pending_receptions': pending,
        'received_receptions': received,
        'overdue_receptions_count': sum(1 for r in pending if r.is_overdue),
        'buyer_warehouses': buyer_warehouses,
        'delivery_mode_choices': DealReception.DELIVERY_MODE_CHOICES,
        'default_delivery_mode': default_delivery_mode(),
        'today_iso': timezone.now().date().isoformat(),
    }


# Processor Dashboard
@method_decorator(login_required, name='dispatch')
@method_decorator(role_required(['Processor']), name='dispatch')
class ProcessorDashboardView(View):
    def get(self, request):
        user = request.user
        
        # Processar contratos pendentes automáticos do Dia X
        from dashboard.services.contract_service import process_pending_contracts
        process_pending_contracts()
        
        # Produtores Virtuais e Contratos de Fornecimento
        from django.contrib.auth.models import User
        instant_producers = User.objects.filter(groups__name='Producer', userprofile__producer_type='instant').order_by('username')
        contract_producers = User.objects.filter(groups__name='Producer', userprofile__producer_type='contract').order_by('username')
        contracts = marketplace_service.get_contracts_adapted(buyer_username=user.username)
        
        open_orders = marketplace_service.get_open_orders_adapted()
        closed_orders = marketplace_service.get_closed_deals_adapted(username=user.username)
        unprocessed_orders = []

        try:
            user_profile = UserProfile.objects.get(user=user)
        except UserProfile.DoesNotExist:
            user_profile = None

        # Calcular Stock Atual do Processador (Baseado em ConsolidatedStock)
        processor_stock = []
        for stock_obj in ConsolidatedStock.objects.filter(owner=user).select_related('culture'):
            clean_wh = stock_obj.warehouse_location.split(' (WH:')[0] if stock_obj.warehouse_location and ' (WH:' in stock_obj.warehouse_location else stock_obj.warehouse_location
            has_sales_model = TrainedModel.objects.filter(
                owner=user,
                culture=stock_obj.culture,
                model_type__in=FORECAST_MARKER_TYPES
            ).exists()
            has_agent_model = TrainedModel.objects.filter(
                owner=user,
                culture=stock_obj.culture,
                model_type='buyer_agent'
            ).exists()
            processor_stock.append({
                'pk': stock_obj.pk,
                'culture_id': stock_obj.culture.pk,
                'culture': str(stock_obj.culture),
                'warehouse': clean_wh,
                'quantity': float(stock_obj.quantity),
                'full_warehouse': stock_obj.warehouse_location,
                'avg_caliber': round(float(stock_obj.avg_caliber), 2),
                'avg_brix': round(float(stock_obj.avg_soluble_solids), 2),
                'avg_score': round(float(stock_obj.avg_quality_score), 1),
                'has_sales_model': has_sales_model,
                'has_agent_model': has_agent_model,
            })

        # Check and heal empty warehouses
        from .services.lc_service import generate_fallback_sensor_readings
        processor_warehouses = list(Warehouse.objects.filter(owner=user).order_by('-warehouse_id'))
        for wh in processor_warehouses:
            wh_stock = ConsolidatedStock.objects.filter(
                Q(warehouse_location=wh.location) | Q(warehouse_location__contains=f"WH:{wh.warehouse_id}") | Q(warehouse_location__contains=f"WH: {wh.warehouse_id}")
            ).filter(owner=user).aggregate(total=Sum('quantity'))['total'] or 0
            wh.current_stock = float(wh_stock)
            wh.occupancy_percentage = min(100.0, round((float(wh_stock) / float(wh.capacity)) * 100.0, 2)) if wh.capacity > 0 else 0.0
            
            if wh.sensor_readings.count() < 30:
                try:
                    generate_fallback_sensor_readings(wh)
                except Exception:
                    pass

        # Central Warehouse (Lojas/Retalhistas Associadas)
        from dashboard.models import StoreProcessorAssociation
        my_associations = StoreProcessorAssociation.objects.filter(processor=user).select_related('retailer')
        
        associated_retailer_ids = my_associations.values_list('retailer_id', flat=True)
        available_retailers = User.objects.filter(groups__name='Retailer').exclude(id__in=associated_retailer_ids).order_by('username')
        
        approved_stores_data = []
        for assoc in my_associations.filter(status='APPROVED'):
            store = assoc.retailer
            # Fetch store warehouses and calculate capacity/occupancy
            store_warehouses = list(Warehouse.objects.filter(owner=store).order_by('-warehouse_id'))
            for wh in store_warehouses:
                wh_stock = ConsolidatedStock.objects.filter(
                    Q(warehouse_location=wh.location) | Q(warehouse_location__contains=f"WH:{wh.warehouse_id}") | Q(warehouse_location__contains=f"WH: {wh.warehouse_id}")
                ).filter(owner=store).aggregate(total=Sum('quantity'))['total'] or 0
                wh.current_stock = float(wh_stock)
                wh.occupancy_percentage = min(100.0, round((float(wh_stock) / float(wh.capacity)) * 100.0, 2)) if wh.capacity > 0 else 0.0
            
            # Fetch store detailed stock
            store_stock = ConsolidatedStock.objects.filter(owner=store).select_related('culture')
            
            # Fetch store daily orders (from marketplace web service)
            store_orders = marketplace_service.get_closed_deals_adapted(username=store.username)
            
            approved_stores_data.append({
                'store': store,
                'association_id': assoc.pk,
                'warehouses': store_warehouses,
                'stock': store_stock,
                'orders': store_orders
            })

        context = { 
            'username': user.username, 
            'role': 'Processor',
            'user_profile': user_profile,
            'open_market_orders': open_orders,
            'closed_market_orders': closed_orders,
            'warehouse_form': WarehouseRegistrationForm(),
            'sensor_form': SensorRegistrationForm(),
            'processor_warehouses': processor_warehouses,
            'all_sensors': Sensor.objects.all(),
            'market_order_form': MarketplaceOrderForm(initial={'role': 'Processor'}),
            'processor_stock': processor_stock,
            'unprocessed_orders': unprocessed_orders,
            'processing_form': ProcessorProcessingForm(),
            'product_subfamilies': ProductSubFamily.objects.all().order_by('fruit_type', 'name'),
            'instant_producers': instant_producers,
            'contract_producers': contract_producers,
            'contracts': contracts,
            # Novos campos para Armazém Central
            'my_associations': my_associations,
            'available_retailers': available_retailers,
            'approved_stores_data': approved_stores_data,

            # Receções de mercadoria
            **_reception_context(user),
        }
        return render(request, 'dashboard/processorDash.html', context)

@method_decorator(login_required, name='dispatch')
@method_decorator(role_required(['Retailer']), name='dispatch')
class RetailerDashboardView(View):
    def get(self, request):
        user = request.user
        
        # Processar contratos pendentes automáticos do Dia X
        from dashboard.services.contract_service import process_pending_contracts
        process_pending_contracts()
        
        # Produtores Virtuais e Contratos de Fornecimento
        from django.contrib.auth.models import User
        instant_producers = User.objects.filter(groups__name='Producer', userprofile__producer_type='instant').order_by('username')
        contract_producers = User.objects.filter(groups__name='Producer', userprofile__producer_type='contract').order_by('username')
        contracts = marketplace_service.get_contracts_adapted(buyer_username=user.username)

        open_orders = marketplace_service.get_open_orders_adapted()[:50]
        closed_orders = marketplace_service.get_closed_deals_adapted(username=user.username)[:50]

        try:
            user_profile = UserProfile.objects.get(user=user)
        except UserProfile.DoesNotExist:
            user_profile = None

        # Calcular Stock Atual do Retailer (Baseado em ConsolidatedStock)
        retailer_stock = []
        for stock_obj in ConsolidatedStock.objects.filter(owner=user).select_related('culture'):
            clean_wh = stock_obj.warehouse_location.split(' (WH:')[0] if stock_obj.warehouse_location and ' (WH:' in stock_obj.warehouse_location else stock_obj.warehouse_location
            has_sales_model = TrainedModel.objects.filter(
                owner=user,
                culture=stock_obj.culture,
                model_type__in=FORECAST_MARKER_TYPES
            ).exists()
            has_agent_model = TrainedModel.objects.filter(
                owner=user,
                culture=stock_obj.culture,
                model_type='buyer_agent'
            ).exists()
            retailer_stock.append({
                'pk': stock_obj.pk,
                'culture_id': stock_obj.culture.pk,
                'culture': str(stock_obj.culture),
                'warehouse': clean_wh,
                'quantity': float(stock_obj.quantity),
                'full_warehouse': stock_obj.warehouse_location,
                'avg_caliber': round(float(stock_obj.avg_caliber), 2),
                'avg_brix': round(float(stock_obj.avg_soluble_solids), 2),
                'avg_score': round(float(stock_obj.avg_quality_score), 1),
                'has_sales_model': has_sales_model,
                'has_agent_model': has_agent_model,
            })

        # Prepare Market Order Form with Warehouse Dropdown
        market_order_form = MarketplaceOrderForm(initial={'role': 'Retailer', 'order_type': 'BUY'})
        # Check and heal empty warehouses
        from .services.lc_service import generate_fallback_sensor_readings
        retailer_warehouses = list(Warehouse.objects.filter(owner=user).order_by('warehouse_id'))
        for wh in retailer_warehouses:
            wh_stock = ConsolidatedStock.objects.filter(
                Q(warehouse_location=wh.location) | Q(warehouse_location__contains=f"WH:{wh.warehouse_id}") | Q(warehouse_location__contains=f"WH: {wh.warehouse_id}")
            ).filter(owner=user).aggregate(total=Sum('quantity'))['total'] or 0
            wh.current_stock = float(wh_stock)
            wh.occupancy_percentage = min(100.0, round((float(wh_stock) / float(wh.capacity)) * 100.0, 2)) if wh.capacity > 0 else 0.0
            
            if wh.sensor_readings.count() < 30:
                try:
                    generate_fallback_sensor_readings(wh)
                except Exception:
                    pass

        if len(retailer_warehouses) > 0:
            # Create choices tuple list: (Location Name, Location Name)
            # We use location name as value because the model expects a CharField
            wh_choices = [(w.location, w.location) for w in retailer_warehouses]
            market_order_form.fields['warehouse_location'].widget = forms.Select(choices=wh_choices, attrs={'class': 'form-control'})
        else:
            # Fallback if no warehouses (though retailer should create one)
            market_order_form.fields['warehouse_location'].widget.attrs.update({'placeholder': 'No warehouses found. Please register one.'})

        # Central Warehouse Associations
        from dashboard.models import StoreProcessorAssociation
        incoming_associations = StoreProcessorAssociation.objects.filter(retailer=user, status='PENDING').select_related('processor')
        active_associations = StoreProcessorAssociation.objects.filter(retailer=user, status='APPROVED').select_related('processor')

        context = { 
            'username': user.username, 
            'role': 'Retailer',
            'user_profile': user_profile,
            'open_market_orders': open_orders,
            'closed_market_orders': closed_orders,
            'market_order_form': market_order_form,
            'warehouse_form': WarehouseRegistrationForm(),
            'sensor_form': SensorRegistrationForm(),
            'retailer_warehouses': retailer_warehouses,
            'all_sensors': Sensor.objects.all(),
            'retailer_stock': retailer_stock,
            'product_subfamilies': ProductSubFamily.objects.all().order_by('fruit_type', 'name'),
            'instant_producers': instant_producers,
            'contract_producers': contract_producers,
            'contracts': contracts,
            # Novos campos para Armazém Central
            'incoming_associations': incoming_associations,
            'active_associations': active_associations,

            # Receções de mercadoria
            **_reception_context(user),
        }
        return render(request, 'dashboard/retailerDash.html', context)

# ----------------------------------------------------------------------
# 3. PRODUCER DASHBOARD (ATUALIZADA)
# ----------------------------------------------------------------------

# views.py (ProducerDashboardView)
@method_decorator(login_required, name='dispatch')
@method_decorator(role_required(['Producer']), name='dispatch')
class ProducerDashboardView(View):
    def get(self, request):
        user = request.user
        
        base_plantation_query = PlantationPlan.objects.filter(producer=user).order_by('-plantation_date')
        
        plantation_plans = base_plantation_query.prefetch_related(
            'soil_values', 
            'soil_values__characteristic',
            'crops',
            'crops__subfamily'
        )
        
        harvest_records = Harvest.objects.filter(producer=user).select_related('plantation', 'subfamily', 'warehouse').order_by('-harvest_date')

        # MAP para Auto-Preenchimento Frontend (Harvest ID -> Warehouse Location)
        # MAP para Auto-Preenchimento Frontend (Harvest ID -> Details)
        harvest_data_map = {}
        for h in harvest_records:
            harvest_data_map[h.pk] = {
                'location': h.warehouse.location if h.warehouse else "",
                'caliber': float(h.caliber) if h.caliber is not None else "",
                'brix': float(h.soluble_solids) if h.soluble_solids is not None else "",
                'score': h.avg_quality_score if h.avg_quality_score is not None else ""
            }
        
        # AGGREGATION: Total Kgs per Product per Warehouse (Current Stock)
        harvest_sums = Harvest.objects.filter(producer=user).values(
            'warehouse__location', 
            'subfamily__name',
            'subfamily'
        ).annotate(
            total_kg=Sum('harvest_quantity_kg'),
            delivered_kg=Sum('delivered_quantity_kg'),
            utilized_kg=Sum('utilized_quantity_kg')
        ).order_by('warehouse__location', 'subfamily__name')
        
        for item in harvest_sums:
            # Stock disponível = Total - O que já foi vendido/utilizado
            item['current_stock'] = (item['total_kg'] or 0) - (item['utilized_kg'] or 0)
            
            # Check if this subfamily has a sales forecast model trained
            item['has_sales_model'] = TrainedModel.objects.filter(
                owner=user,
                culture_id=item['subfamily'],
                model_type__in=FORECAST_MARKER_TYPES
            ).exists()
            
        # 4. BUSCAR EVENTOS DO POMAR
        plantation_events = PlantationEvent.objects.filter(plantation__producer=user).select_related('plantation', 'subfamily').order_by('-event_date')
        
        product_subfamilies = ProductSubFamily.objects.all().order_by('fruit_type', 'name')
        
        producer_warehouses_qs = Warehouse.objects.filter(owner=user).order_by('warehouse_id')
        producer_warehouses = list(producer_warehouses_qs)
        for wh in producer_warehouses:
            wh_stock = ConsolidatedStock.objects.filter(
                Q(warehouse_location=wh.location) | Q(warehouse_location__contains=f"WH:{wh.warehouse_id}") | Q(warehouse_location__contains=f"WH: {wh.warehouse_id}")
            ).filter(owner=user).aggregate(total=Sum('quantity'))['total'] or 0
            wh.current_stock = float(wh_stock)
            wh.occupancy_percentage = min(100.0, round((float(wh_stock) / float(wh.capacity)) * 100.0, 2)) if wh.capacity > 0 else 0.0
        all_sensors = Sensor.objects.all().order_by('sensor_id')

        # 5. MARKETPLACE DATA
        open_market_orders = marketplace_service.get_open_orders_adapted()
        closed_market_orders = marketplace_service.get_closed_deals_adapted(username=user.username)


        plantation_plan_form = PlantationPlanForm()
        plantation_detail_form = PlantationDetailForm()
        harvest_form = HarvestForm() 

        # Filter Marketplace Order Form to only show cultures in stock (Harvested)
        available_subfamily_ids = set(item['subfamily'] for item in harvest_sums if item['subfamily'])
        
        # WE USE A SPECIAL SELL FORM FOR PRODUCERS TO DEDUCT STOCK
        market_order_form = None 
        sell_order_form = MarketSellOrderForm(user=user, initial={'role': 'Producer'})

        warehouse_form = WarehouseRegistrationForm()
        sensor_form = SensorRegistrationForm()
        fertilizer_synthetic_form = FertilizerSyntheticForm() 
        fertilizer_organic_form = FertilizerOrganicForm()
        soil_corrective_form = SoilCorrectiveForm()
        pest_control_form = PestControlForm()
        machinery_form = MachineryForm()
        fuel_form = FuelForm()
        electric_energy_form = ElectricEnergyForm()
        irrigation_water_form = IrrigationWaterForm()
        
        harvest_form.fields['plantation'].queryset = base_plantation_query 
        harvest_form.fields['warehouse'].queryset = producer_warehouses_qs
        
        # --- MAP for Dynamic Filtering in Harvest Form ---
        plantation_subfamilies_map = {}
        for plan in plantation_plans:
            # Create list of {id, name} for each subfamily
            # Now queries PlantationCrop table
            crops = PlantationCrop.objects.filter(plantation=plan).select_related('subfamily')
            subs = [{'id': c.subfamily.subfamily_id, 'name': c.subfamily.name} for c in crops]
            plantation_subfamilies_map[plan.plantation_id] = subs

        
        try:
            user_profile = UserProfile.objects.get(user=user)
        except UserProfile.DoesNotExist:
            user_profile = None

        context = {
            'username': user.username,
            'role': 'Producer',
            
            'plantation_subfamilies_map': plantation_subfamilies_map, # Pass map to template
            'harvest_data_map': harvest_data_map, # Updated for Quality
            
            'plantation_plan_form': plantation_plan_form,
            'plantation_detail_form': plantation_detail_form,
            'plantation_crop_form': PlantationCropForm(user=user), # NEW FORM
            'harvest_form': harvest_form, 
            'warehouse_form': warehouse_form, 
            'sensor_form': sensor_form,
            'fertilizer_synthetic_form': fertilizer_synthetic_form, 
            'fertilizer_organic_form': fertilizer_organic_form,
            'soil_corrective_form': soil_corrective_form,
            'pest_control_form': pest_control_form,
            'machinery_form': machinery_form,
            'fuel_form': fuel_form,
            'electric_energy_form': electric_energy_form,
            'irrigation_water_form': irrigation_water_form,       
            
            'plantation_plans': plantation_plans,
            'product_subfamilies': product_subfamilies,
            'harvest_records': harvest_records, 
            'harvest_sums': harvest_sums, 
            'plantation_events': plantation_events,
            'producer_warehouses': producer_warehouses,
            'all_sensors': all_sensors,
            'user_profile': user_profile,               
            
            'db_error': request.session.pop('db_error', None),

            'plantation_event_form': PlantationEventForm(user=user),
            'market_order_form': market_order_form,
            'sell_order_form': sell_order_form, # New Producer Form
            'open_market_orders': open_market_orders,
            'closed_market_orders': closed_market_orders,
        }
        
        return render(request, 'dashboard/producerDash.html', context)

@login_required
@role_required(['Producer'])
def producer_submit_delivery(request):
    if request.method == 'POST':
        try:
            harvest_id = request.POST.get('harvest_id')
            quantity_to_deliver = float(request.POST.get('quantity_to_deliver'))
            
            harvest = get_object_or_404(Harvest, pk=harvest_id, producer=request.user)
            
            current_delivered = float(harvest.delivered_quantity_kg or 0)
            total_harvested = float(harvest.harvest_quantity_kg)
            remaining = total_harvested - current_delivered
            
            if quantity_to_deliver <= 0:
                 messages.error(request, "Quantity must be greater than 0.")
            elif quantity_to_deliver > remaining:
                messages.error(request, f"Cannot deliver {quantity_to_deliver}kg. Only {remaining}kg available.")
            else:
                harvest.delivered_quantity_kg = current_delivered + quantity_to_deliver
                harvest.save()
                messages.success(request, f"Successfully delivered {quantity_to_deliver}kg.")
                
        except (ValueError, TypeError):
             messages.error(request, "Invalid quantity.")
        except Exception as e:
            messages.error(request, f"Error processing delivery: {str(e)}")
            
    return redirect('producer_dashboard')
    
@login_required
@role_required(['Producer'])
def producer_submit_soil_characteristic(request):
    if request.method == 'POST':
        form = SoilCharacteristicForm(request.POST)

        if form.is_valid():
            try:
                form.save()
                # Sucesso: Redireciona para forçar o reload da dashboard e atualizar o select múltiplo
                return redirect('producer_dashboard') 
            except IntegrityError as e:
                print(f"Erro ao salvar Característica de Solo na DB: Detalhe: {e}")

    # Bloquear acesso GET ou formulário inválido
    return redirect('producer_dashboard')

# ----------------------------------------------------------------------
# 4. VIEWS DE SUBMISSÃO DO PRODUTOR (NOVAS)
# ----------------------------------------------------------------------



@login_required
@role_required(['Producer'])
def producer_submit_plantation_crop(request):
    """
    View to add a crop (ProductSubFamily) to an existing PlantationPlan.
    """
    if request.method == 'POST':
        form = PlantationCropForm(request.POST, user=request.user)
        
        # Security: Validate that the plantation belongs to the user?
        # Form cleaning or explicit check logic.
        
        if form.is_valid():
            try:
                # 1. Check if plantation belongs to user
                plantation = form.cleaned_data['plantation']
                if plantation.producer != request.user:
                    raise IntegrityError("Não autorizado: Plantação não pertence ao utilizador.")
                
                # 2. Save
                form.save()
                return redirect('producer_dashboard')
                
            except IntegrityError as e:
                # e.g. duplicate entry (pair plantation-subfamily unique)
                messages.error(request, f"Erro ao adicionar cultura: {e}")
            except Exception as e:
                messages.error(request, f"Erro desconhecido: {e}")
        else:
             messages.error(request, f"Formulário de Cultura Inválido: {form.errors}")
        return redirect('producer_dashboard')
    
    return redirect('producer_dashboard')

@login_required
@role_required(['Producer'])
def producer_submit_plantation(request):
    db_error = None

    if request.method == 'POST':
        form = PlantationPlanForm(request.POST) 
        detail_form = PlantationDetailForm(request.POST) 
        
        # Filtros de segurança e validação
        # registered_products = Product.objects.filter(producer=request.user)
        # form.fields['product'].queryset = registered_products
        
        # Assume que a validação do solo/características foi feita antes de 'is_valid'
        # e que o form.is_valid() não está a falhar aqui.

        if form.is_valid() and detail_form.is_valid():
            
            # --- BLOC DE SALVAMENTO E TRANSAÇÃO ---
            try:
                # 1. Inicia a transação atómica
                with transaction.atomic():
                    
                    # 2. Salvar o PlantationPlan (código existente)
                    plantation_record = form.save(commit=False)
                    for field in detail_form.fields:
                        setattr(plantation_record, field, detail_form.cleaned_data[field])

                    plantation_record.producer = request.user
                    plantation_record.save()
                    
                    # form.save_m2m() REMOVIDO: Agora gerido via PlantationCrop separado
                    # form.save_m2m()
                    
                    # 3. Processar e salvar os Valores Dinâmicos do Solo
                    soil_data = {}
                    
                    for key, value in request.POST.items():
                        if key.startswith('characteristic_id_') and value:
                            suffix = key.split('characteristic_id_')[1]
                            value_key = f'characteristic_value_{suffix}'
                            
                            # Obtém o valor
                            soil_value = request.POST.get(value_key)
                            
                            # Adiciona ao dicionário de dados do solo se o valor existir
                            if soil_value is not None and soil_value.strip():
                                soil_data[value] = soil_value
                    
                    if soil_data:
                        characteristics = SoilCharacteristic.objects.in_bulk(soil_data.keys()) 
                        
                        for char_id, soil_value_str in soil_data.items():
                            char_obj = characteristics.get(int(char_id))
                            
                            if char_obj:
                                # Tentativa de criação do registo PlantationSoilValue
                                PlantationSoilValue.objects.create(
                                    plantation=plantation_record,
                                    characteristic=char_obj,
                                    value=float(soil_value_str) # PONTO CRÍTICO: CONVERSÃO PARA FLOAT
                                )
                    
                    # 4. SUCESSO: O redirect ocorre dentro da transação em caso de sucesso
                    return redirect(reverse('producer_dashboard')) # Use reverse se for o nome da URL base
                
            except IntegrityError as e:
                # Captura erros de DB e rolls back a transação
                db_error = f"Erro de Integridade (Chave Duplicada/FK): {e}"
            except ValueError as e:
                # Captura erros de conversão de string para float/decimal
                db_error = f"Erro de Conversão de Valor: Verifique se os valores do solo são números válidos. Detalhe: {e}"
            except Exception as e:
                # Captura qualquer outro erro inesperado (o verdadeiro causador do crash/hang)
                db_error = f"ERRO CRÍTICO DESCONHECIDO: {e}"
                print(f"ERRO CRÍTICO DURANTE A SUBMISSÃO: {e}") # <<<<<<<<< DEBUG AQUI
                
        
        # 5. Tratamento de Erro e Redirecionamento Final
        if db_error:
            messages.error(request, db_error)
            
        return redirect(reverse('producer_dashboard')) # Garante que o fluxo HTTP termina
        
    return redirect(reverse('producer_dashboard')) # Bloquear acesso GET

@login_required
@role_required(['Producer'])
def producer_submit_harvest(request):
    db_error = None

    if request.method == 'POST':
        form = HarvestForm(request.POST)

        # Filtro de Segurança: Garante que só pode colher os seus planos e selecionar os seus armazéns
        form.fields['plantation'].queryset = PlantationPlan.objects.filter(producer=request.user)
        form.fields['warehouse'].queryset = Warehouse.objects.filter(owner=request.user)

        if form.is_valid():
            try:
                harvest_record = form.save(commit=False)
                harvest_record.producer = request.user
                
                harvest_record.save()
                
                # --- AUTO-GENESIS BLOCK (Hyperledger Fabric) ---
                try:
                    dossier = create_genesis_dossier(harvest_record)
                    fabric_res = fabric_service.create_order(
                        order_id=dossier['batch_id'],
                        producer_id=harvest_record.producer.username,
                        culture_type=harvest_record.plantation.production_type if harvest_record.plantation else "N/A",
                        quantity=float(harvest_record.harvest_quantity_kg),
                        harvest_date=harvest_record.harvest_date.strftime("%Y-%m-%d"),
                        additional_data=dossier
                    )
                    if fabric_res.get('status') == 'success':
                        messages.success(request, f"Colheita registada e submetida no {fabric_service.label}!")
                    else:
                        messages.warning(request, f"Colheita salva, mas aviso da Blockchain: {fabric_res.get('message')}")
                except Exception as e:
                    messages.warning(request, f"Colheita salva, mas erro ao comunicar com a Blockchain: {e}")

                return redirect('producer_dashboard')
                
            except IntegrityError as e:
                db_error = f"Erro ao salvar Colheita: Detalhe: {e}"
                messages.error(request, db_error)
            except Exception as e:
                db_error = f"Erro desconhecido: {e}"
                messages.error(request, db_error)
        else:
            messages.error(request, f"Erro de validação do formulário: {form.errors.as_text()}")
        
        # Redirecionamento após lógica/erro
        return redirect('producer_dashboard')
        
    return redirect('producer_dashboard')

@login_required
@role_required(['Producer'])
def producer_submit_warehouse(request):
    db_error = None

    if request.method == 'POST':
        form = WarehouseRegistrationForm(request.POST, request.FILES)

        if form.is_valid():
            try:
                warehouse_record = form.save(commit=False)
                warehouse_record.owner = request.user
                warehouse_record.save()
                form.save_m2m() 
                
                # Se carregou ficheiro de sensores no registo
                sensor_file = request.FILES.get('sensor_file')
                if sensor_file and warehouse_record.meteo_source == 'JSON':
                    count, err = process_sensor_readings_file(warehouse_record, sensor_file)
                    if err:
                        messages.warning(request, f"Armazém registado, mas aviso no ficheiro: {err}")
                    else:
                        messages.success(request, f"Armazém registado e {count} leituras importadas com sucesso!")
                else:
                    try:
                        from dashboard.services.lc_service import generate_fallback_sensor_readings
                        generate_fallback_sensor_readings(warehouse_record)
                    except Exception:
                        pass
                    messages.success(request, "Armazém registado com sucesso!")
                
                return redirect('producer_dashboard')
                
            except IntegrityError as e:
                db_error = f"Erro ao salvar Armazém na DB: Detalhe: {e}"
                print(f"[ERRO PRODUCER WAREHOUSE DB]: {e}")
                messages.error(request, db_error)
        else:
            print(f"[ERRO FORMULARIO PRODUCER WAREHOUSE]: {form.errors}")

        return redirect('producer_dashboard')
        
    return redirect('producer_dashboard')

@login_required
@role_required(['Producer'])
def producer_submit_sensor(request):
    if request.method == 'POST':
        form = SensorRegistrationForm(request.POST)

        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Sensor registado com sucesso!")
                return redirect('producer_dashboard') 
                
            except IntegrityError as e:
                db_error = f"Erro ao salvar Sensor na DB: O ID '{request.POST.get('sensor_id')}' já existe. Detalhe: {e}"
                messages.error(request, db_error)
        return redirect('producer_dashboard')
        
    return redirect('producer_dashboard')

@login_required
@role_required(['Processor'])
def processor_submit_warehouse(request):
    db_error = None
    if request.method == 'POST':
        form = WarehouseRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                warehouse_record = form.save(commit=False)
                warehouse_record.owner = request.user
                warehouse_record.save()
                form.save_m2m() 
                
                sensor_file = request.FILES.get('sensor_file')
                if sensor_file and warehouse_record.meteo_source == 'JSON':
                    count, err = process_sensor_readings_file(warehouse_record, sensor_file)
                    if err:
                        messages.warning(request, f"Armazém registado, mas aviso no ficheiro: {err}")
                    else:
                        messages.success(request, f"Armazém registado e {count} leituras importadas com sucesso!")
                else:
                    try:
                        from dashboard.services.lc_service import generate_fallback_sensor_readings
                        generate_fallback_sensor_readings(warehouse_record)
                    except Exception:
                        pass
                    messages.success(request, "Armazém registado com sucesso!")
                    
                return redirect('processor_dashboard')
            except IntegrityError as e:
                db_error = f"Erro ao salvar Armazém na DB: {e}"
                print(f"[ERRO PROCESSOR WAREHOUSE DB]: {e}")
                messages.error(request, db_error)
        else:
            print(f"[ERRO FORMULARIO PROCESSOR WAREHOUSE]: {form.errors}")

        return redirect('processor_dashboard')
        
    return redirect('processor_dashboard')

@login_required
@role_required(['Processor'])
def processor_submit_sensor(request):
    if request.method == 'POST':
        form = SensorRegistrationForm(request.POST)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Sensor registado com sucesso!")
            except Exception as e:
                messages.error(request, f"Erro ao salvar Sensor: {e}")
        else:
            messages.error(request, "Erro de validação do formulário do sensor.")
    return redirect('processor_dashboard')
@role_required(['Processor'])
def processor_submit_processing(request):
    if request.method == 'POST':
        form = ProcessorProcessingForm(request.POST)
        if form.is_valid():
            packaging_type = form.cleaned_data['packaging_type']
            preservation_treatment = form.cleaned_data['preservation_treatment']
            messages.success(request, f"Processamento registado com sucesso ({packaging_type}, {preservation_treatment})!")
            return redirect('processor_dashboard')
    
    return redirect('processor_dashboard')

def _deduct_seller_stock_from_deal(deal):
    """
    Deduz o stock correspondente no vendedor quando um negócio (Deal) é fechado no Marketplace:
    - Se for lote de colheita de produtor (batch_id='LOTE-X'), incrementa utilized_quantity_kg na Harvest.
    - Se for comerciante/processador com ConsolidatedStock, decrementa do ConsolidatedStock.
    """
    if not deal:
        return
        
    batch_id = deal.get("batch_id")
    deal_qty = float(deal.get("quantity_kg") or 0.0)
    seller_id = deal.get("seller_id")
    seller_role = deal.get("seller_role")
    
    if deal_qty <= 0:
        return
        
    if batch_id and str(batch_id).startswith("LOTE-"):
        try:
            h_id = int(str(batch_id).replace("LOTE-", ""))
            harvest = Harvest.objects.filter(pk=h_id).first()
            if harvest:
                from decimal import Decimal
                curr_utilized = harvest.utilized_quantity_kg if harvest.utilized_quantity_kg is not None else Decimal('0.0')
                harvest.utilized_quantity_kg = Decimal(str(curr_utilized)) + Decimal(str(deal_qty))
                harvest.save()
                return
        except Exception as err:
            print(f"[Marketplace] Erro ao abater stock da colheita {batch_id}: {err}")
            
    if seller_id and seller_role in ['Processor', 'Retailer']:
        from django.contrib.auth.models import User
        seller_user = User.objects.filter(username=seller_id).first()
        if seller_user:
            culture = ProductSubFamily.objects.filter(name=deal.get('culture_name')).first()
            if culture:
                stk = ConsolidatedStock.objects.filter(
                    owner=seller_user,
                    culture=culture
                ).first()
                if stk:
                    stk.quantity = max(0.0, float(stk.quantity) - deal_qty)
                    stk.save()

def _open_reception_for_deal(request, deal, dest_wh, expected_date=None, culture=None):
    """Cria a receção pendente do negócio com o modo de entrega escolhido no formulário."""
    from dashboard.services.reception_service import register_pending_reception
    try:
        return register_pending_reception(
            deal=deal,
            buyer=request.user,
            destination_warehouse=dest_wh,
            delivery_mode=request.POST.get('delivery_mode'),
            expected_date=expected_date or request.POST.get('expected_date'),
            culture=culture,
        )
    except Exception as e:
        logger.error(f"[Reception] Falha ao criar receção do negócio {deal.get('deal_id')}: {e}")
        messages.warning(request, f"Negócio fechado, mas não foi possível criar a receção pendente: {e}")
        return None


@login_required
@role_required(['Processor', 'Retailer'])
def confirm_deal_reception(request):
    """O comprador confirma a chegada da mercadoria: dá entrada ao stock e regista no ledger."""
    fallback = 'processor_dashboard' if request.user.groups.filter(name='Processor').exists() else 'retailer_dashboard'
    if request.method != 'POST':
        return redirect(fallback)
    from dashboard.services.reception_service import confirm_reception, ReceptionError
    try:
        reception, ledger = confirm_reception(
            reception_id=request.POST.get('reception_id'),
            user=request.user,
            warehouse_id=request.POST.get('warehouse_id'),
            received_at=request.POST.get('received_at'),
            received_quantity_kg=request.POST.get('received_quantity_kg'),
            soluble_solids=request.POST.get('soluble_solids'),
            acidity=request.POST.get('acidity'),
            firmness=request.POST.get('firmness'),
            caliber=request.POST.get('caliber'),
            notes=request.POST.get('notes', ''),
        )
        msg = (f"Receção do negócio #{reception.deal_id} confirmada: "
               f"{reception.received_quantity_kg} kg de {reception.culture_name} deram entrada em stock "
               f"em {reception.destination_warehouse} ({reception.received_at:%d/%m/%Y}).")
        if reception.has_measurements:
            msg += " O ciclo de vida passa a ser calculado a partir desta receção com as medições registadas."
        messages.success(request, msg)
        if ledger.get('status') == 'error':
            messages.warning(request, f"Stock atualizado, mas a entrega não ficou registada no {fabric_service.label}: {ledger.get('message')}")
    except ReceptionError as e:
        messages.error(request, str(e))
    except Exception as e:
        logger.exception("[Reception] Erro ao confirmar receção")
        messages.error(request, f"Erro ao confirmar receção: {e}")
    return redirect(request.META.get('HTTP_REFERER') or fallback)


def _reception_hint(reception):
    if reception is None:
        return ""
    if reception.delivery_mode == reception.DELIVERY_OWN:
        return "Transporte próprio: confirme a receção quando a mercadoria chegar para dar entrada no stock."
    return "Com transportador: confirme a receção quando a mercadoria chegar para dar entrada no stock."


@login_required
@role_required(['Processor'])
def processor_accept_order(request):
    if request.method == 'POST':
        order_id = request.POST.get('order_id')
        warehouse_id = request.POST.get('warehouse_id')
        
        warehouse = Warehouse.objects.filter(pk=warehouse_id, owner=request.user).first() if str(warehouse_id or '').isdigit() else None
        if warehouse is None:
            messages.error(request, "Tem de registar pelo menos um armazém e selecioná-lo como destino antes de comprar.")
            return redirect('processor_dashboard')

        try:
            dest_wh = f"{warehouse.location} (WH: {warehouse.warehouse_id})"
            
            listing_info = marketplace_service.get_listing(str(order_id))
            qty_to_buy = float(listing_info.get('quantity_kg', 100.0)) if listing_info else 100.0
            
            deal = marketplace_service.execute_instant_buy(
                listing_id=str(order_id),
                buyer_id=request.user.username,
                buyer_role='Processor',
                quantity_kg=qty_to_buy,
                destination_warehouse=dest_wh
            )
            if not deal:
                messages.error(request, "Não foi possível concluir a compra: Marketplace indisponível ou oferta já não se encontra aberta.")
                return redirect('processor_dashboard')
                
            _deduct_seller_stock_from_deal(deal)
            
            # O stock só entra no Processor quando confirmar a receção
            reception = _open_reception_for_deal(request, deal, dest_wh)
            messages.success(request, f"Oferta #{order_id} aceite com sucesso! Negócio concluído ({deal.get('quantity_kg', qty_to_buy)} kg). {_reception_hint(reception)}")
            return redirect('processor_dashboard')
            
        except Exception as e:
            messages.error(request, f"Erro ao aceitar oferta: {e}")
            return redirect('processor_dashboard')
            
    return redirect('processor_dashboard')

# RETAILER VIEWS
@login_required
@role_required(['Retailer'])
def retailer_submit_warehouse(request):
    db_error = None
    if request.method == 'POST':
        form = WarehouseRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                warehouse_record = form.save(commit=False)
                warehouse_record.owner = request.user
                warehouse_record.save()
                form.save_m2m() 
                
                sensor_file = request.FILES.get('sensor_file')
                if sensor_file and warehouse_record.meteo_source == 'JSON':
                    count, err = process_sensor_readings_file(warehouse_record, sensor_file)
                    if err:
                        messages.warning(request, f"Armazém registado, mas aviso no ficheiro: {err}")
                    else:
                        messages.success(request, f"Armazém registado e {count} leituras importadas com sucesso!")
                else:
                    try:
                        from dashboard.services.lc_service import generate_fallback_sensor_readings
                        generate_fallback_sensor_readings(warehouse_record)
                    except Exception:
                        pass
                    messages.success(request, "Armazém registado com sucesso!")
                    
                return redirect('retailer_dashboard')
            except IntegrityError as e:
                db_error = f"Erro ao salvar Armazém na DB: {e}"
                print(f"[ERRO RETAILER WAREHOUSE DB]: {e}")
                messages.error(request, db_error)
        else:
            print(f"[ERRO FORMULARIO RETAILER WAREHOUSE]: {form.errors}")

        return redirect('retailer_dashboard')
    return redirect('retailer_dashboard')

@login_required
@role_required(['Retailer'])
def retailer_submit_sensor(request):
    if request.method == 'POST':
        form = SensorRegistrationForm(request.POST)
        if form.is_valid():
            try:
                form.save()
                return redirect('retailer_dashboard') 
            except IntegrityError as e:
                db_error = f"Erro ao salvar Sensor: ID já existe. Detalhe: {e}"
                messages.error(request, db_error)
        return redirect('retailer_dashboard')
    return redirect('retailer_dashboard')

@login_required
@role_required(['Retailer'])
def retailer_accept_order(request):
    if request.method == 'POST':
        order_id = request.POST.get('order_id')
        warehouse_id = request.POST.get('warehouse_id')
        
        warehouse = Warehouse.objects.filter(pk=warehouse_id, owner=request.user).first() if str(warehouse_id or '').isdigit() else None
        if warehouse is None:
            messages.error(request, "Tem de registar pelo menos um armazém e selecioná-lo como destino antes de comprar.")
            return redirect('retailer_dashboard')

        try:
            dest_wh = f"{warehouse.location} (WH: {warehouse.warehouse_id})"
            
            listing_info = marketplace_service.get_listing(str(order_id))
            qty_to_buy = float(listing_info.get('quantity_kg', 100.0)) if listing_info else 100.0
            
            deal = marketplace_service.execute_instant_buy(
                listing_id=str(order_id),
                buyer_id=request.user.username,
                buyer_role='Retailer',
                quantity_kg=qty_to_buy,
                destination_warehouse=dest_wh
            )
            if not deal:
                messages.error(request, "Não foi possível concluir a compra: Marketplace indisponível ou oferta já não se encontra aberta.")
                return redirect('retailer_dashboard')
                
            _deduct_seller_stock_from_deal(deal)
            
            # O stock só entra no Retailer quando confirmar a receção
            reception = _open_reception_for_deal(request, deal, dest_wh)
            messages.success(request, f"Oferta #{order_id} aceite com sucesso! Negócio concluído ({deal.get('quantity_kg', qty_to_buy)} kg). {_reception_hint(reception)}")
            return redirect('retailer_dashboard')
            
        except Exception as e:
            messages.error(request, f"Erro ao aceitar oferta: {e}")
            return redirect('retailer_dashboard')
            
    return redirect('retailer_dashboard')

@login_required
@role_required(['Producer'])
def producer_submit_event(request):
    if request.method == 'POST':
        form = PlantationEventForm(request.POST)

        # Assumimos que o formulário de evento será submetido com o plantation_id 
        # como um campo oculto ou através de uma lógica mais complexa. 
        # Para simplificar, assumimos que o form tem um campo PlantationPlanFK.

        # Se o form for válido, salva o registo de evento.
        if form.is_valid():
            try:
                form.save()
                return redirect('producer_dashboard')
            except IntegrityError:
                pass
                
        return redirect('producer_dashboard')
    return redirect('producer_dashboard')

# views.py (Fertilizantes Sintéticos)
@login_required
def producer_submit_fertilizer_synth(request):
    db_error = None
    
    # URL de redirecionamento para sucesso ou falha
    # Assumimos que o dashboard principal é o destino, mas pode adicionar #hash para a aba de eventos
    REDIRECT_URL = reverse_lazy('producer_dashboard') 
    
    if request.method == 'POST':
        # 1. Instanciar e Validar os dois Forms com os dados POST
        detail_form = FertilizerSyntheticForm(request.POST) 
        base_form = PlantationEventForm(request.POST) 
        
        # Nota: Você precisará de injetar a FK 'plantation' no base_form antes de base_form.is_valid()
        # Se o campo plantation estiver no base_form (ex: como campo oculto), ignore esta nota.
        
        # 2. Verificação de Validade de AMBOS os formulários
        if detail_form.is_valid() and base_form.is_valid():
            
            try:
                # 3. Lógica de Transação Atómica (Tudo ou Nada)
                with transaction.atomic():
                    
                    # Salva os dados específicos (Tabela FertilizerSyntheticData)
                    detail_record = detail_form.save()
                    
                    # Salva o registo central PlantationEvent (sem as FKs de detalhe ainda)
                    event_record = base_form.save(commit=False)
                    
                    # LIGAÇÃO CRÍTICA: Liga o Evento central ao Detalhe salvo
                    event_record.fertilizer_synth = detail_record 
                    
                    # O campo plantation (FK para PlantationPlan) deve ser preenchido aqui 
                    # se não estiver no formulário base (ex: event_record.plantation = ... )
                    
                    event_record.save()
                
                # Sucesso: Sai da transação e redireciona
                return redirect(REDIRECT_URL) 
                
            except IntegrityError as e:
                db_error = f"Erro de Integridade na DB ao salvar Evento/Detalhe. Detalhe: {e}"
            except Exception as e:
                db_error = f"Erro desconhecido durante a transação: {e}"
                print(f"ERRO CRÍTICO NA TRANSAÇÃO: {e}") 

        # 4. Tratamento de Erro (Validação falhada ou Exceção capturada)
        if db_error:
            # Se a transação falhou, armazenamos a mensagem de erro na sessão
            messages.error(request, db_error)
        # ou se a transação falhar, redirecionamos de volta para o dashboard
        return redirect(REDIRECT_URL)

    # 5. Fallback para requisições GET
    return redirect(REDIRECT_URL)

@login_required
def producer_submit_fertilizer_org(request):
    db_error = None
    
    # URL de redirecionamento para sucesso ou falha
    # Assumimos que o dashboard principal é o destino
    REDIRECT_URL = reverse_lazy('producer_dashboard') 
    
    if request.method == 'POST':
        # 1. Instanciar e Validar os dois Forms com os dados POST
        detail_form = FertilizerOrganicForm(request.POST) 
        base_form = PlantationEventForm(request.POST) 
        
        # 2. Reaplicar filtro de segurança para o dropdown PlantationPlan no base_form, se necessário
        # Assumindo que o campo de PlantationPlan existe no base_form
        # Ex: base_form.fields['plantation'].queryset = PlantationPlan.objects.filter(producer=request.user) 
        
        # 3. Verificação de Validade de AMBOS os formulários
        if detail_form.is_valid() and base_form.is_valid():
            
            try:
                # 4. Lógica de Transação Atómica (Tudo ou Nada)
                with transaction.atomic():
                    
                    # Salva os dados específicos do Fertilizante Orgânico (Tabela Detalhe)
                    detail_record = detail_form.save()
                    
                    # Salva o registo central PlantationEvent (sem as FKs de detalhe)
                    event_record = base_form.save(commit=False)
                    
                    # LIGAÇÃO CRÍTICA: Liga o Evento central ao Detalhe salvo
                    event_record.fertilizer_org = detail_record 
                    
                    # Salva o registo central e finaliza a transação
                    event_record.save()
                
                # Sucesso: Sai da transação e redireciona
                return redirect(REDIRECT_URL) 
                
            except IntegrityError as e:
                db_error = f"Erro de Integridade na DB ao salvar Evento/Detalhe. Detalhe: {e}"
            except Exception as e:
                # Captura qualquer outro erro que possa causar falha
                db_error = f"Erro desconhecido durante a transação: {e}"
                print(f"ERRO CRÍTICO NA TRANSAÇÃO: {e}") 

        # 5. Tratamento de Erro (Validação falhada ou Exceção capturada)
        if db_error:
            # Armazenamos a mensagem na sessão para exibição no dashboard
            messages.error(request, db_error)
        return redirect(REDIRECT_URL)

    # 6. Fallback para requisições GET
    return redirect(REDIRECT_URL)

@login_required
def producer_submit_fertilizer_synth(request):
    db_error = None
    REDIRECT_URL = reverse_lazy('producer_dashboard') 
    
    if request.method == 'POST':
        detail_form = FertilizerSyntheticForm(request.POST) 
        base_form = PlantationEventForm(request.POST) 
        
        if detail_form.is_valid() and base_form.is_valid():
            try:
                with transaction.atomic():
                    detail_record = detail_form.save()
                    event_record = base_form.save(commit=False)
                    event_record.fertilizer_synth = detail_record 
                    event_record.save()
                return redirect(REDIRECT_URL) 
            except IntegrityError as e:
                db_error = f"Erro de Integridade na DB ao salvar Evento/Detalhe. Detalhe: {e}"
            except Exception as e:
                db_error = f"Erro desconhecido durante a transação: {e}"
                print(f"ERRO CRÍTICO NA TRANSAÇÃO: {e}") 

        if db_error:
            messages.error(request, db_error)
        return redirect(REDIRECT_URL)
    return redirect(REDIRECT_URL)

@login_required
def producer_submit_fertilizer_org(request):
    db_error = None
    REDIRECT_URL = reverse_lazy('producer_dashboard') 
    
    if request.method == 'POST':
        detail_form = FertilizerOrganicForm(request.POST) 
        base_form = PlantationEventForm(request.POST) 
        
        if detail_form.is_valid() and base_form.is_valid():
            try:
                with transaction.atomic():
                    detail_record = detail_form.save()
                    event_record = base_form.save(commit=False)
                    event_record.fertilizer_org = detail_record 
                    event_record.save()
                return redirect(REDIRECT_URL) 
            except IntegrityError as e:
                db_error = f"Erro de Integridade na DB ao salvar Evento/Detalhe. Detalhe: {e}"
            except Exception as e:
                db_error = f"Erro desconhecido durante a transação: {e}"
                print(f"ERRO CRÍTICO NA TRANSAÇÃO: {e}") 

        if db_error:
            messages.error(request, db_error)
        return redirect(REDIRECT_URL)
    return redirect(REDIRECT_URL)

@login_required
def producer_submit_soil_corrective(request):
    db_error = None
    REDIRECT_URL = reverse_lazy('producer_dashboard') 
    
    if request.method == 'POST':
        detail_form = SoilCorrectiveForm(request.POST) 
        base_form = PlantationEventForm(request.POST) 
        
        if detail_form.is_valid() and base_form.is_valid():
            try:
                with transaction.atomic():
                    detail_record = detail_form.save()
                    event_record = base_form.save(commit=False)
                    event_record.soil_corrective = detail_record 
                    event_record.save()
                return redirect(REDIRECT_URL) 
            except IntegrityError as e:
                db_error = f"Erro de Integridade na DB: {e}"
            except Exception as e:
                db_error = f"Erro desconhecido: {e}"
                print(f"ERRO CRÍTICO: {e}") 

        if db_error:
            messages.error(request, db_error)
        return redirect(REDIRECT_URL)
    return redirect(REDIRECT_URL)

@login_required
def producer_submit_pest_control(request):
    db_error = None
    REDIRECT_URL = reverse_lazy('producer_dashboard') 
    
    if request.method == 'POST':
        detail_form = PestControlForm(request.POST) 
        base_form = PlantationEventForm(request.POST) 
        
        if detail_form.is_valid() and base_form.is_valid():
            try:
                with transaction.atomic():
                    detail_record = detail_form.save()
                    event_record = base_form.save(commit=False)
                    event_record.pest_control = detail_record 
                    event_record.save()
                return redirect(REDIRECT_URL) 
            except IntegrityError as e:
                db_error = f"Erro de Integridade na DB: {e}"
            except Exception as e:
                db_error = f"Erro desconhecido: {e}"
                print(f"ERRO CRÍTICO: {e}") 

        if db_error:
            messages.error(request, db_error)
        return redirect(REDIRECT_URL)
    return redirect(REDIRECT_URL)

@login_required
def producer_submit_machinery(request):
    db_error = None
    REDIRECT_URL = reverse_lazy('producer_dashboard') 
    
    if request.method == 'POST':
        detail_form = MachineryForm(request.POST) 
        base_form = PlantationEventForm(request.POST) 
        
        if detail_form.is_valid() and base_form.is_valid():
            try:
                with transaction.atomic():
                    detail_record = detail_form.save()
                    event_record = base_form.save(commit=False)
                    event_record.machinery = detail_record 
                    event_record.save()
                return redirect(REDIRECT_URL) 
            except IntegrityError as e:
                db_error = f"Erro de Integridade na DB: {e}"
            except Exception as e:
                db_error = f"Erro desconhecido: {e}"
                print(f"ERRO CRÍTICO: {e}") 

        if db_error:
            messages.error(request, db_error)
        return redirect(REDIRECT_URL)
    return redirect(REDIRECT_URL)

@login_required
def producer_submit_fuel(request):
    db_error = None
    REDIRECT_URL = reverse_lazy('producer_dashboard') 
    
    if request.method == 'POST':
        detail_form = FuelForm(request.POST) 
        base_form = PlantationEventForm(request.POST) 
        
        if detail_form.is_valid() and base_form.is_valid():
            try:
                with transaction.atomic():
                    detail_record = detail_form.save()
                    event_record = base_form.save(commit=False)
                    event_record.fuel = detail_record 
                    event_record.save()
                return redirect(REDIRECT_URL) 
            except IntegrityError as e:
                db_error = f"Erro de Integridade na DB: {e}"
            except Exception as e:
                db_error = f"Erro desconhecido: {e}"
                print(f"ERRO CRÍTICO: {e}") 

        if db_error:
            messages.error(request, db_error)
        return redirect(REDIRECT_URL)
    return redirect(REDIRECT_URL)

@login_required
def producer_submit_electric(request):
    db_error = None
    REDIRECT_URL = reverse_lazy('producer_dashboard') 
    
    if request.method == 'POST':
        detail_form = ElectricEnergyForm(request.POST) 
        base_form = PlantationEventForm(request.POST) 
        
        if detail_form.is_valid() and base_form.is_valid():
            try:
                with transaction.atomic():
                    detail_record = detail_form.save()
                    event_record = base_form.save(commit=False)
                    event_record.electric = detail_record 
                    event_record.save()
                return redirect(REDIRECT_URL) 
            except IntegrityError as e:
                db_error = f"Erro de Integridade na DB: {e}"
            except Exception as e:
                db_error = f"Erro desconhecido: {e}"
                print(f"ERRO CRÍTICO: {e}") 

        if db_error:
            messages.error(request, db_error)
        return redirect(REDIRECT_URL)
    return redirect(REDIRECT_URL)

@login_required
def producer_submit_water(request):
    db_error = None
    REDIRECT_URL = reverse_lazy('producer_dashboard') 
    
    if request.method == 'POST':
        detail_form = IrrigationWaterForm(request.POST) 
        base_form = PlantationEventForm(request.POST) 
        
        if detail_form.is_valid() and base_form.is_valid():
            try:
                with transaction.atomic():
                    detail_record = detail_form.save()
                    event_record = base_form.save(commit=False)
                    event_record.water = detail_record 
                    event_record.save()
                return redirect(REDIRECT_URL) 
            except IntegrityError as e:
                db_error = f"Erro de Integridade na DB: {e}"
            except Exception as e:
                db_error = f"Erro desconhecido: {e}"
                print(f"ERRO CRÍTICO: {e}") 

        if db_error:
            messages.error(request, db_error)
        return redirect(REDIRECT_URL)

# ----------------------------------------------------------------------
# 5. VIEWS DE MARKETPLACE (INTEGRAÇÃO COM MARKETPLACE WEB SERVICE)
# ----------------------------------------------------------------------

@method_decorator(login_required, name='dispatch')
class MarketplacePortalView(View):
    """
    Portal Central e Dedicado do Marketplace Agroalimentar (B2B Commodity Exchange).
    Acesso desacoplado ao microserviço de Order Book, Matching, Contratos Futuros e Inteligência de Mercado.
    """
    def get(self, request):
        user = request.user
        
        # 1. Identificar o Perfil (Role) e URL de retorno ao respetivo dashboard
        role = 'Retailer'
        if user.is_superuser or user.groups.filter(name='Admin').exists():
            role = 'Admin'
        elif user.groups.filter(name='Producer').exists():
            role = 'Producer'
        elif user.groups.filter(name='Retailer').exists():
            role = 'Retailer'
        elif user.groups.filter(name='Processor').exists():
            role = 'Processor'
        elif user.groups.filter(name='Transporter').exists():
            role = 'Transporter'
        elif user.groups.filter(name='Consumer').exists():
            role = 'Consumer'

        role_dashboards = {
            'Admin': 'admin_dashboard',
            'Producer': 'producer_dashboard',
            'Retailer': 'retailer_dashboard',
            'Processor': 'processor_dashboard',
            'Transporter': 'transporter_dashboard',
            'Consumer': 'consumer_dashboard',
        }
        return_dashboard_url = role_dashboards.get(role, 'admin_dashboard')

        # 2. Consultar o Marketplace Web Service (FastAPI)
        service_online = marketplace_service.check_health()
        
        open_orders = marketplace_service.get_open_orders_adapted()
        open_listings = [o for o in open_orders if o.order_type == 'SELL']
        open_bids = [o for o in open_orders if o.order_type == 'BUY']
        
        # PRIVACIDADE & BLOCKCHAIN: Cada interveniente apenas acede aos SEUS PRÓPRIOS negócios concluídos
        # (Informação confidencial protegida por canais privados / Private Data Collections)
        if user.is_superuser or role == 'Admin':
            closed_deals = marketplace_service.get_closed_deals_adapted()
        else:
            closed_deals = marketplace_service.get_closed_deals_adapted(username=user.username)
            
        user_deals = closed_deals
        supply_contracts = marketplace_service.get_contracts_adapted(buyer_username=user.username if not (user.is_superuser or role == 'Admin') else None)
        
        market_price_data = marketplace_service.fetch_market_prices() or {}
        
        # Estatísticas do mercado (volume aberto público + métricas privadas do utilizador)
        total_open_volume = sum(getattr(o, 'quantity_kg', 0) for o in open_orders)
        user_deals_count = len(closed_deals)
        user_deals_volume = sum(getattr(d, 'quantity_kg', 0) for d in closed_deals)
        
        # 3. Armazéns, Culturas e Lotes do Utilizador
        user_warehouses = Warehouse.objects.filter(owner=user).order_by('location')
        product_subfamilies = ProductSubFamily.objects.all().order_by('fruit_type', 'name')

        # Preparação de dados de Produtor
        harvest_records = Harvest.objects.filter(producer=user).select_related('plantation', 'subfamily', 'warehouse').order_by('-harvest_date')
        harvest_data_map = {}
        for h in harvest_records:
            harvest_data_map[h.pk] = {
                'location': h.warehouse.location if h.warehouse else "",
                'caliber': float(h.caliber) if h.caliber is not None else "",
                'brix': float(h.soluble_solids) if h.soluble_solids is not None else "",
                'score': h.avg_quality_score if h.avg_quality_score is not None else "",
                'available_stock': float(h.current_stock_kg),
                'culture_name': h.subfamily.name if h.subfamily else ""
            }
        
        sell_order_form = MarketSellOrderForm(user=user, initial={'role': 'Producer'})
        
        # Formulário Genérico / Retalhista / Processador
        market_order_form = MarketplaceOrderForm(initial={'role': role, 'order_type': 'BUY'})
        if user_warehouses.exists():
            wh_choices = [(w.location, f"{w.location} (WH: {w.warehouse_id})") for w in user_warehouses]
            market_order_form.fields['warehouse_location'].widget = forms.Select(choices=wh_choices, attrs={'class': 'form-control'})
        
        # Stock Consolidado (para auto-preenchimento ao vender de retalho/processamento)
        user_stock_qs = ConsolidatedStock.objects.filter(owner=user, quantity__gt=0).select_related('culture')
        user_stock_data = []
        for s in user_stock_qs:
            user_stock_data.append({
                'culture': s.culture.name if s.culture else 'N/A',
                'culture_id': s.culture.pk if s.culture else '',
                'warehouse': s.warehouse_location,
                'full_warehouse': s.warehouse_location,
                'quantity': float(s.quantity),
                'avg_caliber': float(s.avg_caliber) if s.avg_caliber else 0,
                'avg_brix': float(s.avg_soluble_solids) if s.avg_soluble_solids else 0,
                'avg_score': float(s.avg_quality_score) if s.avg_quality_score else 10,
                'harvest_id': s.lot_number if hasattr(s, 'lot_number') else ''
            })

        # 4. Tickers de Cotações em Tempo Real (Produtos Perecíveis & Commodities Agrícolas)
        market_tickers = [
            {'symbol': 'MACA-GALA', 'name': 'Maçã Gala (Alcobaça IGP)', 'price': 1.48, 'change': '+3.2%', 'trend': 'up', 'vol': '48.5 Ton', 'unit': '€/kg', 'origin': 'Oeste, PT'},
            {'symbol': 'PERA-ROCHA', 'name': 'Pêra Rocha (Oeste DOP)', 'price': 1.62, 'change': '+1.8%', 'trend': 'up', 'vol': '62.0 Ton', 'unit': '€/kg', 'origin': 'Cadaval / Bombarral'},
            {'symbol': 'TOMATE-RAMA', 'name': 'Tomate Rama Seleção', 'price': 1.15, 'change': '-0.5%', 'trend': 'down', 'vol': '31.2 Ton', 'unit': '€/kg', 'origin': 'Ribatejo, PT'},
            {'symbol': 'LARANJA-ALG', 'name': 'Laranja do Algarve (IGP)', 'price': 1.25, 'change': '+0.8%', 'trend': 'up', 'vol': '28.0 Ton', 'unit': '€/kg', 'origin': 'Silves / Faro'},
            {'symbol': 'MORANGO-OESTE', 'name': 'Morango Estufa Qualidade', 'price': 3.40, 'change': '+4.5%', 'trend': 'up', 'vol': '12.4 Ton', 'unit': '€/kg', 'origin': 'Torres Vedras'},
            {'symbol': 'CENOURA-PT', 'name': 'Cenoura Nacional Lavada', 'price': 0.85, 'change': '0.0%', 'trend': 'neutral', 'vol': '19.5 Ton', 'unit': '€/kg', 'origin': 'Póvoa de Varzim'},
            {'symbol': 'BATATA-CONS', 'name': 'Batata Nova de Conservação', 'price': 0.95, 'change': '+1.1%', 'trend': 'up', 'vol': '55.0 Ton', 'unit': '€/kg', 'origin': 'Trás-os-Montes / Montijo'},
            {'symbol': 'UVA-DONA-MARIA', 'name': 'Uva de Mesa Dona Maria', 'price': 2.10, 'change': '+2.0%', 'trend': 'up', 'vol': '15.8 Ton', 'unit': '€/kg', 'origin': 'Alentejo Central'}
        ]

        # 5. Notícias Reais & Boletins de Inteligência de Mercado / Safra / Perecibilidade (com Cache de 0ms)
        market_news = market_news_service.get_live_news()

        context = {
            'username': user.username,
            'role': role,
            'return_dashboard_url': return_dashboard_url,
            'service_online': service_online,
            'open_orders': open_orders,
            'open_listings': open_listings,
            'open_bids': open_bids,
            'closed_deals': closed_deals,
            'user_deals': user_deals,
            'supply_contracts': supply_contracts,
            'market_prices': market_price_data,
            'market_tickers': market_tickers,
            'market_news': market_news,
            'market_stats': {
                'total_open_volume': round(total_open_volume, 1),
                'open_listings_count': len(open_listings),
                'open_bids_count': len(open_bids),
                'total_deals_count': user_deals_count,
                'total_deals_volume': round(user_deals_volume, 1),
            },
            'user_warehouses': user_warehouses,
            'retailer_warehouses': user_warehouses,
            'product_subfamilies': product_subfamilies,
            'harvest_data_map': harvest_data_map,
            'sell_order_form': sell_order_form,
            'market_order_form': market_order_form,
            'retailer_stock': user_stock_data,
            'harvest_records': harvest_records,
            # Modo de entrega no fecho do negócio
            **_reception_context(request.user),
        }
        return render(request, 'dashboard/marketplace_portal.html', context)


def _open_listed_kg(seller_id, batch_id=None, culture_name=None):
    """Kg que o vendedor já tem em ofertas abertas no marketplace (por lote ou por cultura)."""
    total = 0.0
    for l in marketplace_service.fetch_open_listings(seller_id=seller_id) or []:
        if batch_id is not None and l.get('batch_id') != batch_id:
            continue
        if culture_name is not None and (l.get('culture_name') != culture_name or l.get('batch_id')):
            continue
        total += float(l.get('quantity_kg') or 0.0)
    return total


@login_required
def market_submit_order(request):
    if request.method == 'POST':
        if request.user.groups.filter(name='Producer').exists():
            # Lógica para PRODUTOR (Venda / Listing - sem abate prévio de stock)
            form = MarketSellOrderForm(request.POST, user=request.user)
            if form.is_valid():
                harvest = form.cleaned_data['harvest_origin']
                qty = float(form.cleaned_data['quantity_kg'])
                price_per_kg = float(form.cleaned_data['price_per_kg'])
                wh_loc = form.cleaned_data['warehouse_location']
                if harvest and harvest.warehouse:
                    wh_loc = harvest.warehouse.location

                # Não permitir pôr à venda mais do que o disponível do lote, contando as ofertas já abertas
                # (evita ofertas duplicadas por duplo clique e venda acima do stock)
                batch_id = f"LOTE-{harvest.pk}"
                already_listed = _open_listed_kg(request.user.username, batch_id=batch_id)
                available = float(harvest.current_stock_kg) - already_listed
                if qty > available + 1e-6:
                    messages.error(request, f"O lote {batch_id} tem {float(harvest.current_stock_kg):.2f} kg disponíveis e {already_listed:.2f} kg já estão em ofertas abertas. Só pode pôr à venda mais {max(0.0, available):.2f} kg.")
                    return redirect(request.META.get('HTTP_REFERER', 'producer_dashboard'))

                # Publicar no Marketplace Web Service
                listing = marketplace_service.publish_listing(
                    seller_id=request.user.username,
                    seller_role='Producer',
                    culture_name=harvest.subfamily.name if harvest.subfamily else 'Cultura',
                    fruit_type=harvest.subfamily.fruit_type if harvest.subfamily else 'apple',
                    quantity_kg=qty,
                    price_per_kg=price_per_kg,
                    warehouse_location=wh_loc,
                    batch_id=f"LOTE-{harvest.pk}",
                    quality_metrics={
                        "caliber_mm": float(harvest.caliber) if harvest.caliber else None,
                        "soluble_solids_brix": float(harvest.soluble_solids) if harvest.soluble_solids else None,
                        "quality_score": float(harvest.avg_quality_score) if harvest.avg_quality_score else 10.0
                    }
                )
                
                if listing:
                    messages.success(request, f"Oferta de Venda criada no Marketplace Central ({qty} kg a {price_per_kg:.2f}€/kg)! O stock será debitado apenas quando o negócio for concluído.")
                else:
                    messages.error(request, "Não foi possível contactar o Marketplace Web Service. Por favor verifique se o serviço está ligado e em execução.")
                return redirect(request.META.get('HTTP_REFERER', 'producer_dashboard'))
            else:
                messages.error(request, f"Erro ao criar oferta: {form.errors}")
        
        else:
            # Lógica Genérica (Retalhista a comprar, consumidor, etc.)
            form = MarketplaceOrderForm(request.POST)
            if form.is_valid():
                order_type = form.cleaned_data['order_type']
                culture = form.cleaned_data['culture']
                qty = float(form.cleaned_data['quantity_kg'])
                price_per_kg = float(form.cleaned_data.get('price_per_kg') or 2.0)
                wh_loc = form.cleaned_data['warehouse_location']
                
                groups = request.user.groups.all()
                user_role = groups[0].name if groups else 'Retailer'
                
                if order_type == 'SELL':
                    # Processor/Retailer: não vender mais do que o stock da cultura, contando ofertas já abertas
                    if user_role in ['Processor', 'Retailer']:
                        in_stock = float(ConsolidatedStock.objects.filter(owner=request.user, culture=culture).aggregate(t=Sum('quantity'))['t'] or 0)
                        already_listed = _open_listed_kg(request.user.username, culture_name=culture.name)
                        available = in_stock - already_listed
                        if qty > available + 1e-6:
                            messages.error(request, f"Tem {in_stock:.2f} kg de {culture.name} em stock e {already_listed:.2f} kg já estão em ofertas abertas. Só pode pôr à venda mais {max(0.0, available):.2f} kg.")
                            return redirect(request.META.get('HTTP_REFERER', 'retailer_dashboard'))
                    listing = marketplace_service.publish_listing(
                        seller_id=request.user.username,
                        seller_role=user_role,
                        culture_name=culture.name,
                        fruit_type=culture.fruit_type,
                        quantity_kg=qty,
                        price_per_kg=price_per_kg,
                        warehouse_location=wh_loc,
                        quality_metrics={
                            "caliber_mm": float(form.cleaned_data.get('min_caliber') or 0.0),
                            "soluble_solids_brix": float(form.cleaned_data.get('min_soluble_solids') or 0.0),
                            "quality_score": float(form.cleaned_data.get('min_quality_score') or 10.0)
                        }
                    )
                    if listing:
                        messages.success(request, f"Oferta de Venda ({order_type}) registada no Marketplace Central!")
                    else:
                        messages.error(request, "Não foi possível contactar o Marketplace Web Service. Por favor verifique se o serviço está ligado.")
                else:
                    bid = marketplace_service.publish_bid(
                        buyer_id=request.user.username,
                        buyer_role=user_role,
                        culture_name=culture.name,
                        fruit_type=culture.fruit_type,
                        quantity_kg=qty,
                        max_price_per_kg=price_per_kg,
                        destination_warehouse=wh_loc,
                        min_caliber_mm=float(form.cleaned_data.get('min_caliber')) if form.cleaned_data.get('min_caliber') else None,
                        min_soluble_solids_brix=float(form.cleaned_data.get('min_soluble_solids')) if form.cleaned_data.get('min_soluble_solids') else None,
                        min_quality_score=float(form.cleaned_data.get('min_quality_score')) if form.cleaned_data.get('min_quality_score') else None
                    )
                    if bid:
                        messages.success(request, f"Pedido ({order_type}) registado no Marketplace Central!")
                    else:
                        messages.error(request, "Não foi possível contactar o Marketplace Web Service. Por favor verifique se o serviço está ligado.")
                        
                return redirect(request.META.get('HTTP_REFERER', 'retailer_dashboard'))
            else:
                messages.error(request, f"Erro ao criar pedido: {form.errors}")
    
    return redirect(request.META.get('HTTP_REFERER', 'producer_dashboard'))

@login_required
def market_accept_order(request):
    if request.method == 'POST':
        order_id = request.POST.get('order_id')
        warehouse_id = request.POST.get('warehouse_id')
        
        try:
            buyer_role = request.user.groups.first().name if request.user.groups.exists() else 'Retailer'
            
            listing_info = marketplace_service.get_listing(str(order_id))
            qty_to_buy = float(listing_info.get('quantity_kg', 100.0)) if listing_info else 100.0
            
            dest_wh = "Armazém de Destino"
            wh = Warehouse.objects.filter(pk=warehouse_id, owner=request.user).first() if str(warehouse_id or '').isdigit() else None
            if wh:
                dest_wh = f"{wh.location} (WH: {wh.warehouse_id})"
            elif buyer_role in ['Processor', 'Retailer']:
                # O stock do comprador tem de entrar num armazém registado
                messages.error(request, "Tem de registar pelo menos um armazém e selecioná-lo como destino antes de comprar.")
                return redirect(request.META.get('HTTP_REFERER', 'producer_dashboard'))
            
            # Executar compra imediata no Marketplace Web Service
            deal = marketplace_service.execute_instant_buy(
                listing_id=str(order_id),
                buyer_id=request.user.username,
                buyer_role=buyer_role,
                quantity_kg=qty_to_buy,
                destination_warehouse=dest_wh
            )
            
            if not deal:
                messages.error(request, "Não foi possível concluir a transação: Marketplace indisponível ou oferta já não está aberta.")
                return redirect(request.META.get('HTTP_REFERER', 'producer_dashboard'))
            
            # Abater o stock no vendedor
            _deduct_seller_stock_from_deal(deal)
            
            # Processor/Retailer: o stock só entra quando confirmar a receção
            hint = ""
            if buyer_role in ['Processor', 'Retailer']:
                hint = _reception_hint(_open_reception_for_deal(request, deal, dest_wh))
            
            messages.success(request, f"Transação #{order_id} concluída no Marketplace! Negócio fechado. {hint}".strip())
        except Exception as e:
            messages.error(request, f"Erro ao aceitar pedido: {e}")
            
    return redirect(request.META.get('HTTP_REFERER', 'producer_dashboard'))

# ----------------------------------------------------------------------
# 6. VIEWS DE LOGÍSTICA (TRANSPORTER)
# ----------------------------------------------------------------------

def _parse_or_now_dt(dt_str):
    if dt_str:
        try:
            parsed = parse_datetime(dt_str)
            if parsed:
                if timezone.is_naive(parsed):
                    parsed = timezone.make_aware(parsed)
                return parsed
        except Exception:
            pass
    return timezone.now()

def _create_route_from_cluster(order_cluster, route_date):
    with transaction.atomic():
        route = Route.objects.create(
            route_date=route_date or timezone.now().date(),
            status='PENDING'
        )
        route.optimized_path = " -> ".join([str(x) for x in order_cluster])
        route.save()
        return route

def check_and_create_optimal_route(order_date=None):
    """
    Verifica se existem 6 ou mais transações concluídas pendentes de transporte
    e gera automaticamente uma rota ótima agrupada no mercado.
    """
    deals = marketplace_service.fetch_deals()
    assigned_deal_ids = _get_assigned_deal_ids()
    unassigned_deals = [d for d in (deals or []) if str(d.get('deal_id')) not in assigned_deal_ids]
    
    if len(unassigned_deals) >= 6:
        selected_deals = unassigned_deals[:6]
        cluster = []
        for d in selected_deals:
            d_id = d.get('deal_id', '')
            cult = d.get('culture_name', 'Agro')
            w = float(d.get('quantity_kg', 0.0) or 0.0)
            orig = d.get('warehouse_origin') or 'Armazém Virtual Produtor'
            dest = d.get('destination_warehouse') or f"Armazém {d.get('buyer_id')}"
            cluster.append(f"Deal #{d_id} ({cult}: {w} kg) [{orig} -> {dest}]")
            
        route = _create_route_from_cluster(cluster, order_date or timezone.now().date())
        return route
    return None

@login_required
@role_required(['Transporter'])
def transporter_register_vehicle(request):
    if request.method == "POST":
        form = VehicleForm(request.POST)
        if form.is_valid():
            vehicle = form.save(commit=False)
            vehicle.owner = request.user
            vehicle.save()
            messages.success(request, f"Veículo {vehicle.brand_model} ({vehicle.license_plate}) registado com sucesso!")
        else:
            messages.error(request, f"Erro ao registar veículo: {form.errors}")
    return redirect('transporter_dashboard')

@login_required
@role_required(['Transporter'])
def transporter_accept_route(request):
    if request.method == "POST":
        route_id = request.POST.get('route_id')
        vehicle_id = request.POST.get('vehicle_id')
        route = get_object_or_404(Route, pk=route_id)
        
        if not vehicle_id:
            messages.error(request, "Tem de selecionar um veículo para esta rota.")
            return redirect('transporter_dashboard')
            
        vehicle = get_object_or_404(Vehicle, pk=vehicle_id, owner=request.user)
        
        if route.status == 'PENDING':
            with transaction.atomic():
                route.status = 'ACCEPTED'
                route.transporter = request.user
                route.vehicle = vehicle
                route.save()
                    
            messages.success(request, f"Rota #{route.pk} aceite com o veículo {vehicle.brand_model} ({vehicle.license_plate})!")
        else:
            messages.error(request, "Esta rota já não está disponível.")
            
    return redirect('transporter_dashboard')

@login_required
@role_required(['Transporter'])
def transporter_route_plan(request):
    if request.method == "POST":
        route_id = request.POST.get('route_id')
        route = get_object_or_404(Route, pk=route_id, transporter=request.user)
        planned_pickup = request.POST.get('planned_pickup_date')
        planned_delivery = request.POST.get('planned_delivery_date')
        
        if planned_pickup and planned_delivery:
            with transaction.atomic():
                route.status = 'PLANNED'
                route.save()
            messages.success(request, f"Plano de transporte registado para a Rota #{route.pk}!")
        else:
            messages.error(request, "Datas de recolha e entrega inválidas.")
    return redirect('transporter_dashboard')

@login_required
@role_required(['Transporter'])
def transporter_route_pickup(request):
    if request.method == "POST":
        route_id = request.POST.get('route_id')
        route = get_object_or_404(Route, pk=route_id, transporter=request.user)
        
        pickup_time = _parse_or_now_dt(request.POST.get('actual_pickup_date'))
        
        with transaction.atomic():
            route.status = 'IN_TRANSIT'
            route.save()
            
            # Blockchain Custody Block
            dossier = {
                "action": "TRANSPORT_ROUTE_PICKUP",
                "route_id": route.pk,
                "transporter": request.user.username,
                "pickup_time": pickup_time.isoformat(),
                "path": route.optimized_path or ""
            }
            try:
                fabric_service.update_order(
                    order_id=f"ROTA-{route.pk}",
                    new_status="IN_TRANSIT",
                    additional_data=dossier
                )
            except Exception as fe:
                print(f"Erro fabric: {fe}")
                
        messages.success(request, f"Viagem da Rota #{route.pk} iniciada com sucesso!")
    return redirect('transporter_dashboard')

@login_required
@role_required(['Transporter'])
def transporter_route_delivery(request):
    if request.method == "POST":
        route_id = request.POST.get('route_id')
        route = get_object_or_404(Route, pk=route_id, transporter=request.user)
        
        sensor_data = "No Sensor Data Recorded"
        if 'sensor_file' in request.FILES:
            try:
                uploaded_file = request.FILES['sensor_file']
                sensor_data = uploaded_file.read().decode('utf-8')
            except Exception as e:
                sensor_data = f"File Read Error: {e}"
        elif request.POST.get('transport_sensor_data'):
            sensor_data = request.POST.get('transport_sensor_data')
        
        delivery_time = _parse_or_now_dt(request.POST.get('actual_delivery_date'))
        
        with transaction.atomic():
            route.status = 'DELIVERED'
            route.save()
            
            # Blockchain delivery
            dossier = {
                "action": "TRANSPORT_ROUTE_DELIVERY",
                "route_id": route.pk,
                "transporter": request.user.username,
                "delivery_time": delivery_time.isoformat(),
                "sensor_data": sensor_data,
                "path": route.optimized_path or ""
            }
            try:
                fabric_service.update_order(
                    order_id=f"ROTA-{route.pk}",
                    new_status="DELIVERED",
                    additional_data=dossier
                )
            except Exception as fe:
                print(f"Erro fabric: {fe}")
                
        messages.success(request, f"Entrega da Rota #{route.pk} concluída com sucesso!")
    return redirect('transporter_dashboard')

@login_required
@role_required(['Transporter'])
def transporter_simulate_route_opt(request):
    deals = marketplace_service.fetch_deals()
    assigned_deal_ids = _get_assigned_deal_ids()
    available_deals = [d for d in (deals or []) if str(d.get('deal_id')) not in assigned_deal_ids]
    
    combined_items = []
    for d in available_deals:
        d_weight = float(d.get('quantity_kg', 0.0) or 0.0)
        origin = d.get('warehouse_origin') or 'Armazém Virtual Produtor'
        dest = d.get('destination_warehouse') or f"Armazém {d.get('buyer_id')}"
        cult = d.get('culture_name', 'Agro')
        d_id = d.get('deal_id', '')
        combined_items.append({
            'desc': f"Deal #{d_id} ({cult}: {d_weight} kg) [{origin} -> {dest}]",
            'weight': d_weight
        })
        
    if not combined_items:
        messages.error(request, "Não existem novas transações concluídas pendentes de transporte no mercado neste momento.")
        return redirect('transporter_dashboard')
        
    selected_items = combined_items[:15]
    created_routes = []
    current_cluster = []
    current_weight = 0.0
    MAX_ROUTE_WEIGHT = 5000.0  # Capacidade de 1 Camião Ligeiro padrão (5.000 Kg)

    for itm in selected_items:
        itm_weight = itm['weight']
        itm_desc = itm['desc']
        if current_cluster and (current_weight + itm_weight > MAX_ROUTE_WEIGHT):
            route = _create_route_from_cluster(current_cluster, timezone.now().date())
            created_routes.append(route)
            current_cluster = [itm_desc]
            current_weight = itm_weight
        else:
            current_cluster.append(itm_desc)
            current_weight += itm_weight

    if current_cluster:
        route = _create_route_from_cluster(current_cluster, timezone.now().date())
        created_routes.append(route)

    routes_str = ", ".join([f"#{r.pk}" for r in created_routes])
    messages.success(request, f"Simulação Concluída! Foram geradas {len(created_routes)} rotas independentes ({routes_str}) para acomodar {len(selected_items)} transações concluídas respeitando os limites dos veículos.")
    return redirect('transporter_dashboard')

@login_required
@role_required(['Transporter'])
def transporter_job_history_api(request):
    """
    Endpoint AJAX para carregar o histórico de entregas de forma paginada e instantânea.
    """
    page_number = request.GET.get('page', 1)
    
    deals = marketplace_service.fetch_deals()
    
    orders_data = []
    for d in (deals or []):
        orders_data.append({
            'pk': d.get('deal_id', 'N/A'),
            'actual_delivery_date': d.get('delivery_date') or d.get('executed_at') or d.get('timestamp') or '-',
            'culture_name': d.get('culture_name', 'N/A'),
            'quantity_kg': float(d.get('quantity_kg', 0.0) or 0.0),
            'origin': d.get('warehouse_origin') or d.get('origin_warehouse', 'N/A'),
            'requester': d.get('buyer_id', 'N/A'),
            'vehicle': '-',
            'harvest_id': d.get('batch_id', None),
        })
        
    paginator = Paginator(orders_data, 15)
    page_obj = paginator.get_page(page_number)
        
    return JsonResponse({
        'orders': list(page_obj.object_list),
        'current_page': page_obj.number,
        'total_pages': paginator.num_pages,
        'total_count': paginator.count,
        'has_next': page_obj.has_next(),
        'has_previous': page_obj.has_previous(),
        'next_page_number': page_obj.next_page_number() if page_obj.has_next() else None,
        'previous_page_number': page_obj.previous_page_number() if page_obj.has_previous() else None,
    })

@login_required
@role_required(['Transporter'])
def transporter_accept_job(request):
    """
    Aceitar trabalho de transporte individual (Deal do Marketplace).
    """
    if request.method == "POST":
        order_id = request.POST.get('order_id')
        vehicle_id = request.POST.get('vehicle_id')
        
        if not vehicle_id:
            messages.error(request, "Tem de selecionar um veículo para transportar esta carga.")
            return redirect('transporter_dashboard')
            
        vehicle = get_object_or_404(Vehicle, pk=vehicle_id, owner=request.user)
        
        assigned_deal_ids = _get_assigned_deal_ids()
        if str(order_id) in assigned_deal_ids:
            messages.warning(request, f"A transação/carga #{order_id} já foi aceite ou atribuída a uma rota.")
            return redirect('transporter_dashboard')
            
        # Obter detalhes da carga nos deals
        deals = marketplace_service.fetch_deals()
        target_deal = next((d for d in deals if str(d.get('deal_id')) == str(order_id)), None)
        if target_deal:
            culture_name = target_deal.get('culture_name', 'Agro')
            quantity_kg = float(target_deal.get('quantity_kg', 0.0) or 0.0)
            origin = target_deal.get('warehouse_origin') or 'Armazém Virtual Produtor'
            dest = target_deal.get('destination_warehouse') or f"Armazém {target_deal.get('buyer_id')}"
            path_desc = f"Deal #{target_deal.get('deal_id')} ({culture_name}: {quantity_kg} kg) [{origin} -> {dest}]"
        else:
            open_orders = marketplace_service.get_open_orders_adapted()
            target_order = next((o for o in open_orders if str(o.id) == str(order_id)), None)
            if target_order:
                culture_name = target_order.culture.name if hasattr(target_order, 'culture') and hasattr(target_order.culture, 'name') else 'Agro'
                quantity_kg = float(getattr(target_order, 'quantity_kg', 0.0) or 0.0)
                origin = getattr(target_order, 'warehouse_location', None) or 'Armazém Virtual Produtor'
                dest = f"Armazém {target_order.requester.username}" if hasattr(target_order, 'requester') else 'Armazém Comprador'
                path_desc = f"Carga #{target_order.id} ({culture_name}: {quantity_kg} kg) [{origin} -> {dest}]"
            else:
                path_desc = f"Deal #{order_id} (Agro: 1000.0 kg) [Armazém Produtor -> Armazém Retalhista]"
                
        with transaction.atomic():
            route = Route.objects.create(
                transporter=request.user,
                vehicle=vehicle,
                route_date=timezone.now().date(),
                status='ACCEPTED',
                optimized_path=path_desc
            )
            
        messages.success(request, f"Carga #{order_id} aceite com sucesso! Rota #{route.pk} atribuída ao veículo {vehicle.brand_model} ({vehicle.license_plate}).")
    return redirect('transporter_dashboard')

@login_required
@role_required(['Transporter'])
def transporter_submit_plan(request):
    messages.info(request, "O planeamento de transporte é agora efetuado por Rota.")
    return redirect('transporter_dashboard')

@login_required
@role_required(['Transporter'])
def transporter_validate_pickup(request):
    messages.info(request, "A recolha de transporte é agora registada por Rota.")
    return redirect('transporter_dashboard')

@login_required
@role_required(['Transporter'])
def transporter_submit_delivery(request):
    messages.info(request, "A entrega de transporte é agora registada por Rota.")
    return redirect('transporter_dashboard')


@login_required
@role_required(['Processor'])
def processor_request_association(request):
    if request.method == "POST":
        from django.contrib.auth.models import User
        retailer_id = request.POST.get('retailer_id')
        retailer = get_object_or_404(User, pk=retailer_id, groups__name='Retailer')
        
        # Create or update association status to PENDING
        assoc, created = StoreProcessorAssociation.objects.get_or_create(
            processor=request.user,
            retailer=retailer
        )
        if not created and assoc.status != 'PENDING':
            assoc.status = 'PENDING'
            assoc.save()
            
        messages.success(request, f"Pedido de associação enviado para a loja {retailer.username}!")
    return redirect('processor_dashboard')


@login_required
@role_required(['Retailer'])
def retailer_respond_association(request):
    if request.method == "POST":
        association_id = request.POST.get('association_id')
        action = request.POST.get('action') # 'approve', 'reject', 'revoke'
        assoc = get_object_or_404(StoreProcessorAssociation, pk=association_id, retailer=request.user)
        
        if action == 'approve':
            assoc.status = 'APPROVED'
            assoc.save()
            messages.success(request, f"Permissão concedida ao processador {assoc.processor.username}!")
        elif action == 'reject':
            assoc.status = 'REJECTED'
            assoc.save()
            messages.warning(request, f"Pedido de associação do processador {assoc.processor.username} rejeitado.")
        elif action == 'revoke':
            assoc.delete()
            messages.info(request, f"Acesso do processador {assoc.processor.username} revogado.")
            
    return redirect('retailer_dashboard')


from dashboard.services.fabric_service import fabric_service

@login_required
def get_harvest_history(request, harvest_id):
    """
    View AJAX para buscar o histórico de um Lote na Blockchain.
    Retorna o HTML do modal preenchido.
    """
    try:
        # 1. Construir o ID usado na Blockchain (Ex: "LOTE-123" ou "LOTE-AUTO-005")
        harvest_str = str(harvest_id).strip()
        asset_id = harvest_str if harvest_str.startswith("LOTE-") else f"LOTE-{harvest_str}"
        
        # 2. Buscar Histórico ao Go Middleware
        history_data = fabric_service.get_asset_history(asset_id, caller_id=request.user.username)
        
        # 3. Processar dados para o Template (Parsing de JSON dentro do value, timestamps, etc.)
        # O Go retorna algo como: [{"txId": "...", "value": "{...}", "timestamp": "...", "isDelete": false}]
        formatted_history = []
        for entry in history_data:
            try:
                # Tentar formatar o JSON do value para ficar bonito
                import json
                value_obj = json.loads(entry.get('value', '{}'))
                entry['value'] = json.dumps(value_obj, indent=2)
            except:
                pass # Se não for JSON, mantém string original
                
            formatted_history.append(entry)
            
        context = {
            'harvest_id': harvest_id,
            'history': formatted_history,
            'error': None
        }
        
    except Exception as e:
        context = {
            'harvest_id': harvest_id,
            'history': [],
            'error': f"Erro ao buscar histórico: {str(e)}"
        }

    return render(request, 'dashboard/modals/harvest_history_modal.html', context)


@login_required
def get_agent_recommendations(request):
    import os
    import sys
    import torch
    import io
    from django.http import JsonResponse
    from django.conf import settings
@login_required
@role_required(['Retailer', 'Processor'])
def get_agent_recommendations(request):
    try:
        # Obter os modelos de Buyer Agent treinados por este utilizador
        trained_models = TrainedModel.objects.filter(
            owner=request.user,
            model_type='buyer_agent'
        ).select_related('culture')
        
        # Se não houver nenhum modelo treinado, não mostramos recomendações ainda
        if not trained_models.exists():
            return JsonResponse({'status': 'success', 'data': []})
            
        from dashboard.services.agent_service import get_buyer_agent_decision_details

        recommendations = []
        
        for model_obj in trained_models:
            subfamily = model_obj.culture
            if not subfamily:
                continue
            
            try:
                # Obter a decisão em tempo real diretamente do Buyer Agent Web Service (:8002)
                decision_data = get_buyer_agent_decision_details(request.user, subfamily)
                recommended_qty = float(decision_data.get('recommended_order_kg', 0.0))
                price = float(decision_data.get('price_today', 2.0))
                
                # RSL do stock
                rsl_days = int(decision_data.get('state_summary', {}).get('rsl_days', 15) or 15)
                min_required_shelf_life = 5 if recommended_qty > 0 else 0
                
                recommendations.append({
                    'item_id': str(subfamily.subfamily_id or subfamily.pk),
                    'sku': subfamily.name,
                    'quantity': int(max(0, round(recommended_qty))),
                    'price': round(price, 2),
                    'culture_id': subfamily.pk,
                    'culture_name': f"{subfamily.name} ({subfamily.fruit_type})",
                    'min_required_shelf_life': int(min_required_shelf_life),
                    'stock_remaining_shelf_life': int(rsl_days)
                })
            except ConnectionError:
                # O Web Service está offline
                return JsonResponse({
                    'status': 'offline',
                    'message': 'Buyer Agent Web Service offline na porta 8002.',
                    'data': []
                })
            except Exception as e:
                print(f"[Buyer Service] Aviso ao obter decisão para {subfamily.name}: {str(e)}")
                
        return JsonResponse({'status': 'success', 'data': recommendations})
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'status': 'error', 'message': f'Erro ao obter recomendações: {str(e)}'}, status=500)


@login_required
def get_sensor_data_from_sheet(request):
    from django.http import JsonResponse
    import os
    import json
    from django.conf import settings

    if request.user.username != 'ProducerBraga':
        return JsonResponse({'status': 'error', 'message': 'Não autorizado'}, status=403)

    cache_path = os.path.join(settings.BASE_DIR, 'dashboard', 'sensor_cache.json')
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return JsonResponse(data)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'Erro ao ler cache local: {str(e)}'}, status=500)
    
    # Fallback caso o ficheiro de cache não exista ainda (ex: primeira inicialização)
    try:
        import requests
        import csv
        url = "https://docs.google.com/spreadsheets/d/13qQPIxbvm0aIjWB57CqSMSBQa7tx_DfYI4rColx41hI/export?format=csv"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            response.encoding = 'utf-8'
            lines = response.text.splitlines()
            reader = csv.reader(lines)
            rows = list(reader)
            if len(rows) > 1:
                headers = rows[0]
                data_rows = rows[1:]
                data_rows.reverse()
                formatted_data = []
                for r in data_rows[:100]:
                    if len(r) == len(headers):
                        formatted_data.append(dict(zip(headers, r)))
                
                payload = {
                    'status': 'success',
                    'headers': headers,
                    'data': formatted_data,
                    'updated_at': 'First Load'
                }
                with open(cache_path, 'w', encoding='utf-8') as f:
                    json.dump(payload, f, indent=4)
                
                return JsonResponse(payload)
        return JsonResponse({'status': 'error', 'message': 'Cache local indisponível e falha ao sincronizar.'}, status=500)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Erro de sincronização direta: {str(e)}'}, status=500)


def process_sensor_readings_file(warehouse, file):
    """
    Processa ficheiros de leituras de sensores em formato JSON, CSV ou Excel (.xlsx, .xls)
    e atualiza a tabela WarehouseSensorReading.
    """
    import json
    import pandas as pd
    from django.db import transaction
    from .models import WarehouseSensorReading
    
    filename = file.name.lower()
    df = None
    try:
        if filename.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(file)
        elif filename.endswith('.csv'):
            df = pd.read_csv(file)
        elif filename.endswith('.json'):
            content = file.read().decode('utf-8')
            data = json.loads(content)
            if isinstance(data, dict):
                data = data.get('readings') or data.get('data') or data.get('sensor_data') or [data]
            df = pd.DataFrame(data)
        else:
            return 0, "Formato não suportado. Use JSON (.json), Excel (.xlsx, .xls) ou CSV (.csv)."
    except Exception as e:
        return 0, f"Erro ao ler ficheiro: {str(e)}"
        
    if df is None or df.empty:
        return 0, "O ficheiro fornecido está vazio ou não contém dados válidos."
        
    df.columns = [str(c).strip().lower() for c in df.columns]
    
    date_col = next((c for c in df.columns if c in ['data', 'date', 'dt', 'timestamp']), None)
    temp_col = next((c for c in df.columns if c in ['temperatura', 'temperature', 'temp', 't']), None)
    hum_col = next((c for c in df.columns if c in ['humidade', 'humidity', 'hum', 'h', 'rh']), None)
    eth_col = next((c for c in df.columns if c in ['etileno', 'ethylene', 'eth', 'c2h4']), None)
    
    if not date_col or not temp_col or not hum_col:
        return 0, "Colunas em falta. O ficheiro deve conter pelo menos 'Data', 'Temperatura' e 'Humidade' (a coluna 'Etileno' é opcional)."
        
    count = 0
    with transaction.atomic():
        for idx, row in df.iterrows():
            try:
                raw_date = row[date_col]
                if pd.isna(raw_date):
                    continue
                dt_val = pd.to_datetime(raw_date).date()
            except Exception:
                continue
            
            temp_val = float(row[temp_col]) if not pd.isna(row[temp_col]) else 0.0
            hum_val = float(row[hum_col]) if not pd.isna(row[hum_col]) else 0.0
            eth_val = None
            if eth_col and not pd.isna(row[eth_col]):
                try:
                    eth_val = float(row[eth_col])
                except (ValueError, TypeError):
                    eth_val = None
            
            WarehouseSensorReading.objects.update_or_create(
                warehouse=warehouse,
                date=dt_val,
                defaults={
                    'temperature': temp_val,
                    'humidity': hum_val,
                    'ethylene': eth_val
                }
            )
            count += 1
            
    return count, None


@login_required
def import_sensor_readings(request, warehouse_id):
    from django.contrib import messages
    from django.shortcuts import get_object_or_404, redirect
    from .models import Warehouse
    
    warehouse = get_object_or_404(Warehouse, pk=warehouse_id)
    
    if warehouse.owner != request.user and not request.user.is_superuser:
        messages.error(request, "Não tem permissão para gerir este armazém.")
        return redirect('admin_dashboard')
        
    if request.method != 'POST':
        messages.error(request, "Método não permitido.")
        return redirect('admin_dashboard')
        
    file = request.FILES.get('sensor_file')
    if not file:
        messages.error(request, "Por favor, selecione um ficheiro JSON, Excel ou CSV.")
        return redirect(request.META.get('HTTP_REFERER', 'admin_dashboard'))
        
    count, err = process_sensor_readings_file(warehouse, file)
    if err:
        messages.error(request, err)
    else:
        if warehouse.meteo_source != 'JSON':
            warehouse.meteo_source = 'JSON'
            warehouse.save()
        messages.success(request, f"Importação concluída com sucesso! Registadas/atualizadas {count} leituras diárias.")
        
    return redirect(request.META.get('HTTP_REFERER', 'admin_dashboard'))


@login_required
def edit_warehouse(request, warehouse_id):
    """
    Permite editar a localização, região, capacidade, sensores e modo meteorológico
    de um armazém existente, recalculando as leituras de imediato.
    """
    from django.contrib import messages
    from django.shortcuts import get_object_or_404, redirect
    from .models import Warehouse, Sensor
    from dashboard.services.lc_service import generate_fallback_sensor_readings
    
    warehouse = get_object_or_404(Warehouse, pk=warehouse_id)
    
    if warehouse.owner != request.user and not request.user.is_superuser:
        messages.error(request, "Não tem permissão para editar este armazém.")
        return redirect('admin_dashboard')
        
    if request.method == 'POST':
        try:
            location = request.POST.get('location', '').strip()
            if location:
                warehouse.location = location
                
            region = request.POST.get('region')
            if region:
                warehouse.region = region
                
            control_type = request.POST.get('control_type')
            if control_type:
                warehouse.control_type = control_type
                
            storage_unit = request.POST.get('storage_unit')
            if storage_unit:
                warehouse.storage_unit = storage_unit
                
            max_vehicle_access = request.POST.get('max_vehicle_access')
            if max_vehicle_access:
                warehouse.max_vehicle_access = max_vehicle_access
                
            capacity = request.POST.get('capacity')
            if capacity:
                warehouse.capacity = float(capacity)
                
            lat = request.POST.get('latitude')
            warehouse.latitude = float(lat) if lat and lat.strip() else None
            
            lng = request.POST.get('longitude')
            warehouse.longitude = float(lng) if lng and lng.strip() else None
            
            meteo_source = request.POST.get('meteo_source')
            if meteo_source:
                warehouse.meteo_source = meteo_source
                
            json_fallback_mode = request.POST.get('json_fallback_mode')
            if json_fallback_mode:
                warehouse.json_fallback_mode = json_fallback_mode
                
            fixed_temp = request.POST.get('fixed_temperature')
            if fixed_temp and fixed_temp.strip():
                warehouse.fixed_temperature = float(fixed_temp)
                
            fixed_hum = request.POST.get('fixed_humidity')
            if fixed_hum and fixed_hum.strip():
                warehouse.fixed_humidity = float(fixed_hum)
                
            warehouse.save()
            
            # Atualizar sensores Many-to-Many
            sensor_ids = request.POST.getlist('sensors')
            if sensor_ids:
                warehouse.sensors.set(Sensor.objects.filter(sensor_id__in=sensor_ids))
            else:
                warehouse.sensors.clear()
                
            # Se foi enviado ficheiro de sensores no modo JSON
            file = request.FILES.get('sensor_file')
            if file and warehouse.meteo_source == 'JSON':
                count, err = process_sensor_readings_file(warehouse, file)
                if err:
                    messages.warning(request, f"Armazém atualizado, mas aviso no ficheiro: {err}")
                else:
                    messages.success(request, f"Armazém e {count} leituras do ficheiro atualizados com sucesso!")
            else:
                try:
                    generate_fallback_sensor_readings(warehouse)
                except Exception as e:
                    print(f"[REGENERATE ERROR]: {e}")
                messages.success(request, f"Armazém '{warehouse.location}' atualizado com sucesso!")
                
        except Exception as e:
            messages.error(request, f"Erro ao atualizar armazém: {str(e)}")
            
        return redirect(request.META.get('HTTP_REFERER', 'admin_dashboard'))
        
    return redirect('admin_dashboard')


# ======================================================================
# AJUSTE MANUAL DE STOCK E TEMPLATES DE TREINO
# ======================================================================

@login_required
def adjust_stock_manually(request):
    from django.http import JsonResponse
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método não permitido.'}, status=405)
        
    try:
        culture_id = request.POST.get('culture_id')
        warehouse_location = request.POST.get('warehouse_location')
        quantity = float(request.POST.get('quantity', 0.0))
        adjustment_type = request.POST.get('adjustment_type', 'set')
        
        # Parâmetros de Qualidade Físico-Química e Colheita
        harvest_date_str = request.POST.get('harvest_date')
        firmness_raw = request.POST.get('firmness')
        brix_raw = request.POST.get('brix') or request.POST.get('soluble_solids')
        acidity_raw = request.POST.get('acidity')
        caliber_raw = request.POST.get('caliber')
        
        # Condições de Armazenamento / Lifecycle
        meteo_source = request.POST.get('meteo_source')
        fixed_temp = request.POST.get('fixed_temperature')
        fixed_hum = request.POST.get('fixed_humidity')
        json_fallback = request.POST.get('json_fallback_mode')
        sensor_file = request.FILES.get('sensor_file')
        
        if not culture_id or not warehouse_location:
            return JsonResponse({'status': 'error', 'message': 'Campos obrigatórios em falta.'}, status=400)
            
        culture = get_object_or_404(ProductSubFamily, pk=culture_id)
        
        # Calcular Score de Qualidade Biofísico
        from dashboard.services.lc_service import calculate_harvest_quality, generate_fallback_sensor_readings, ensure_warehouse_readings_30d
        quality_100 = calculate_harvest_quality(culture.name, firmness_raw, brix_raw, acidity_raw)
        calculated_score = round(quality_100 / 10.0, 2)
        
        f_val = float(firmness_raw) if firmness_raw is not None and str(firmness_raw).strip() != '' else None
        b_val = float(brix_raw) if brix_raw is not None and str(brix_raw).strip() != '' else None
        a_val = float(acidity_raw) if acidity_raw is not None and str(acidity_raw).strip() != '' else None
        c_val = float(caliber_raw) if caliber_raw is not None and str(caliber_raw).strip() != '' else None
        
        # Parse Data da Colheita
        import datetime
        if harvest_date_str:
            try:
                parsed_harvest_date = datetime.datetime.strptime(harvest_date_str, '%Y-%m-%d').date()
            except ValueError:
                parsed_harvest_date = datetime.date.today()
        else:
            parsed_harvest_date = datetime.date.today()
        
        # Criar ou atualizar stock consolidado
        stock, created = ConsolidatedStock.objects.get_or_create(
            owner=request.user,
            culture=culture,
            warehouse_location=warehouse_location
        )
        
        current_qty = float(stock.quantity) if (stock.quantity is not None and not created) else 0.0
        
        if adjustment_type == 'add':
            new_qty = current_qty + quantity
            action_desc = f"adicionados {quantity} kg ao stock de"
        elif adjustment_type == 'subtract':
            new_qty = max(0.0, current_qty - quantity)
            action_desc = f"retirados {quantity} kg do stock de"
        else: # 'set'
            new_qty = quantity
            action_desc = f"definidos exatos {quantity} kg de stock de"
            
        stock.quantity = new_qty
        if b_val is not None:
            stock.avg_soluble_solids = round(b_val, 2)
        if calculated_score is not None:
            stock.avg_quality_score = round(calculated_score, 1)
        if c_val is not None:
            stock.avg_caliber = round(c_val, 2)
        stock.save()
        
        # Atualizar parâmetros meteorológicos do Armazém se fornecidos (qualquer utilizador com Armazém)
        from dashboard.models import Warehouse
        warehouse_obj = Warehouse.objects.filter(owner=request.user, location=warehouse_location).first()
        if not warehouse_obj:
            warehouse_obj = Warehouse.objects.filter(owner=request.user).first()
            
        if warehouse_obj and meteo_source:
            warehouse_obj.meteo_source = meteo_source
            if fixed_temp is not None and str(fixed_temp).strip() != '':
                warehouse_obj.fixed_temperature = float(fixed_temp)
            if fixed_hum is not None and str(fixed_hum).strip() != '':
                warehouse_obj.fixed_humidity = float(fixed_hum)
            if json_fallback:
                warehouse_obj.json_fallback_mode = json_fallback
            warehouse_obj.save()
            
            if sensor_file and meteo_source == 'JSON':
                process_sensor_readings_file(warehouse_obj, sensor_file)
            else:
                generate_fallback_sensor_readings(warehouse_obj)
        elif warehouse_obj:
            generate_fallback_sensor_readings(warehouse_obj)
        
        # Se for um Produtor, sincronizar com o modelo Harvest e Blockchain
        if request.user.groups.filter(name='Producer').exists():
            from dashboard.models import Harvest
            from decimal import Decimal
            from dashboard.services.fabric_service import fabric_service
            from dashboard.utils import create_genesis_dossier
            
            # 1. Obter todos os lotes com plantação
            plantation_harvests = list(Harvest.objects.filter(
                producer=request.user,
                subfamily=culture,
                warehouse=warehouse_obj,
                plantation__isnull=False
            ))
            
            # Calcular stock disponível atual nos lotes com plantação
            plant_avail = Decimal('0.0')
            for h in plantation_harvests:
                plant_avail += Decimal(str(h.harvest_quantity_kg)) - Decimal(str(h.utilized_quantity_kg))
                
            target = Decimal(str(new_qty))
            
            if target >= plant_avail:
                # Apagamos todos os lotes manuais (sem plantação)
                Harvest.objects.filter(
                    producer=request.user,
                    subfamily=culture,
                    warehouse=warehouse_obj,
                    plantation__isnull=True
                ).delete()
                
                diff = target - plant_avail
                if diff > 0:
                    new_harvest = Harvest.objects.create(
                        producer=request.user,
                        subfamily=culture,
                        warehouse=warehouse_obj,
                        plantation=None,
                        harvest_date=parsed_harvest_date,
                        harvest_quantity_kg=diff,
                        utilized_quantity_kg=Decimal('0.0'),
                        avg_quality_score=calculated_score,
                        firmness=f_val,
                        soluble_solids=b_val,
                        acidity=a_val,
                        caliber=c_val
                    )
                    
                    # --- SUBMETER À BLOCKCHAIN NO AJUSTE MANUAL ---
                    try:
                        dossier = create_genesis_dossier(new_harvest)
                        fabric_service.create_order(
                            order_id=dossier['batch_id'],
                            producer_id=new_harvest.producer.username,
                            culture_type=new_harvest.subfamily.name if new_harvest.subfamily else "N/A",
                            quantity=float(new_harvest.harvest_quantity_kg),
                            harvest_date=new_harvest.harvest_date.strftime("%Y-%m-%d"),
                            additional_data=dossier
                        )
                    except Exception as fe:
                        print(f"Erro ao submeter ajuste à Blockchain Real: {fe}")
            else:
                # Apagamos todos os lotes manuais
                Harvest.objects.filter(
                    producer=request.user,
                    subfamily=culture,
                    warehouse=warehouse_obj,
                    plantation__isnull=True
                ).delete()
                
                # E aumentamos o desperdício das plantações para atingir o target
                diff_to_subtract = plant_avail - target
                for h in plantation_harvests:
                    if diff_to_subtract <= 0:
                        break
                    avail = Decimal(str(h.harvest_quantity_kg)) - Decimal(str(h.utilized_quantity_kg))
                    if avail > 0:
                        to_sub = min(avail, diff_to_subtract)
                        h.utilized_quantity_kg = Decimal(str(h.utilized_quantity_kg)) + to_sub
                        h.save()
                        diff_to_subtract -= to_sub
                        
        return JsonResponse({
            'status': 'success',
            'message': f"Sucesso: Foram {action_desc} {culture.name} no armazém {warehouse_location}. Stock atual: {new_qty} kg (Score Qualidade: {calculated_score}/10 ⭐).",
            'quantity': float(stock.quantity)
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
def download_training_template(request):
    import io
    import pandas as pd
    from django.http import HttpResponse
    
    sku = request.GET.get('sku', '')
    
    # Resolve SKU to a clean name for inclusion in template if possible
    culture_name = "Maca Gala"
    lot_info = ""
    try:
        if '|' in sku:
            parts = sku.split('|')
            subfamily = ProductSubFamily.objects.get(pk=parts[0])
            culture_name = subfamily.name
            lot_info = f"Lote #{parts[1]}"
        elif sku:
            subfamily = ProductSubFamily.objects.get(pk=sku)
            culture_name = subfamily.name
    except Exception:
        if sku:
            culture_name = sku

    # Remove accents for header safety in excel sheet names and filenames
    import unicodedata
    clean_culture_name = "".join(c for c in unicodedata.normalize('NFD', culture_name) if unicodedata.category(c) != 'Mn')

    # Create dynamic template data
    # Template de histórico de vendas (forecast / buyer agent)
    columns = [
        'Data', 
        'Cultura_Produto', 
        'Vendas_Kg', 
        'Preco_Venda_Euro'
    ]
    data = [
        ['2026-06-01', culture_name, 250.0, 1.80],
        ['2026-06-02', culture_name, 270.0, 1.85],
        ['2026-06-03', culture_name, 310.0, 1.80],
        ['2026-06-04', culture_name, 150.0, 1.90],
        ['2026-06-05', culture_name, 400.0, 1.75],
    ]
    filename = f"template_previsao_vendas_{clean_culture_name.lower().replace(' ', '_')}.xlsx"

    df = pd.DataFrame(data, columns=columns)
    
    # Save dataframe to memory buffer as excel
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Template')
    output.seek(0)

    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
@role_required(['Retailer', 'Processor'])
def buy_direct_makro(request):
    if request.method == "POST":
        producer_name = request.POST.get('producer_name')
        culture_id = request.POST.get('culture_id')
        quantity_kg = request.POST.get('quantity_kg')
        warehouse_id = request.POST.get('warehouse_id')
        
        try:
            from django.contrib.auth.models import User, Group
            from dashboard.models import ProductSubFamily, UserProfile, Warehouse
            from dashboard.services.contract_service import process_instant_purchase
            
            if not producer_name or not producer_name.strip():
                messages.error(request, "O nome do fornecedor não pode estar vazio.")
                return redirect(request.META.get('HTTP_REFERER', 'retailer_dashboard'))
                
            producer_name = producer_name.strip()
            subfamily = get_object_or_404(ProductSubFamily, pk=culture_id)
            qty = float(quantity_kg)
            
            if qty <= 0:
                messages.error(request, "A quantidade deve ser superior a 0.")
                return redirect(request.META.get('HTTP_REFERER', 'retailer_dashboard'))
                
            warehouse_loc = None
            if warehouse_id:
                w_obj = get_object_or_404(Warehouse, pk=warehouse_id, owner=request.user)
                warehouse_loc = f"{w_obj.location} (WH: {w_obj.warehouse_id})"
                
            # Obter ou criar dinamicamente o fornecedor instantâneo
            producer_user = User.objects.filter(username__iexact=producer_name).first()
            if not producer_user:
                producer_user = User(username=producer_name)
                producer_user.set_unusable_password()
                producer_user.save()
                
                p_group, _ = Group.objects.get_or_create(name='Producer')
                producer_user.groups.add(p_group)
                
                UserProfile.objects.create(user=producer_user, producer_type='instant')
                
            # Processar a compra instantânea
            order = process_instant_purchase(
                buyer=request.user,
                producer=producer_user,
                subfamily=subfamily,
                quantity_kg=qty,
                warehouse_location=warehouse_loc
            )
            
            # Obter o tempo de vida calculado para mostrar na mensagem
            from dashboard.services.contract_service import get_culture_shelf_life
            days = get_culture_shelf_life(subfamily)
            
            messages.success(request, f"Compra rápida efetuada com sucesso! Lote {order.harvest_origin.pk} adicionado ao stock. Fornecedor: {producer_user.username}. Validade: {days} dias.")
        except Exception as e:
            messages.error(request, f"Erro ao processar compra rápida: {e}")
            
    return redirect(request.META.get('HTTP_REFERER', 'retailer_dashboard'))


@login_required
@role_required(['Retailer', 'Processor'])
def create_supply_contract(request):
    if request.method == "POST":
        producer_name = request.POST.get('producer_name')
        culture_id = request.POST.get('culture_id')
        quantity_kg = request.POST.get('quantity_kg')
        delivery_date_str = request.POST.get('delivery_date')
        warehouse_id = request.POST.get('warehouse_id')
        
        try:
            from django.contrib.auth.models import User, Group
            from dashboard.models import ProductSubFamily, UserProfile, Warehouse
            import datetime
            
            if not producer_name or not producer_name.strip():
                messages.error(request, "O nome do fornecedor não pode estar vazio.")
                return redirect(request.META.get('HTTP_REFERER', 'retailer_dashboard'))
                
            producer_name = producer_name.strip()
            subfamily = get_object_or_404(ProductSubFamily, pk=culture_id)
            qty = float(quantity_kg)
            delivery_date = datetime.datetime.strptime(delivery_date_str, "%Y-%m-%d").date()
            
            if qty <= 0:
                messages.error(request, "A quantidade deve ser superior a 0.")
                return redirect(request.META.get('HTTP_REFERER', 'retailer_dashboard'))
                
            if delivery_date < timezone.now().date():
                messages.error(request, "A data de entrega não pode ser no passado.")
                return redirect(request.META.get('HTTP_REFERER', 'retailer_dashboard'))
                
            w_obj = Warehouse.objects.filter(pk=warehouse_id, owner=request.user).first() if str(warehouse_id or '').isdigit() else None
            if w_obj is None:
                messages.error(request, "Tem de registar pelo menos um armazém e selecioná-lo como destino antes de celebrar um contrato.")
                return redirect(request.META.get('HTTP_REFERER', 'retailer_dashboard'))
            warehouse_loc = f"{w_obj.location} (WH: {w_obj.warehouse_id})"
                
            # Obter ou criar dinamicamente o fornecedor do contrato (com sufixo -Contract automática)
            expected_username = producer_name if producer_name.endswith('-Contract') else f"{producer_name}-Contract"
            producer_user = User.objects.filter(username__iexact=expected_username).first()
            
            if not producer_user:
                # Criar diretamente com o nome esperado (sufixado) para evitar colisões com o nome base
                producer_user = User(username=expected_username)
                producer_user.set_unusable_password()
                producer_user.save()
                
                p_group, _ = Group.objects.get_or_create(name='Producer')
                producer_user.groups.add(p_group)
                
                UserProfile.objects.create(user=producer_user, producer_type='contract')
                
            # Criar o contrato no Marketplace Web Service
            contract_deal = marketplace_service.create_supply_contract(
                buyer_id=request.user.username,
                seller_id=producer_user.username,
                culture_name=subfamily.name,
                quantity_kg=qty,
                price_per_kg=0.0,
                delivery_date=delivery_date.isoformat(),
                destination_warehouse=warehouse_loc or "",
                buyer_role='Retailer',
                seller_role='Producer'
            )
            
            # Receção pendente com a data prevista do contrato (stock só entra ao confirmar)
            if contract_deal:
                _open_reception_for_deal(request, contract_deal, warehouse_loc or "", expected_date=delivery_date, culture=subfamily)
            
            messages.success(request, f"Contrato de fornecimento celebrado com sucesso com {producer_user.username} para o dia {delivery_date_str}! Confirme a receção quando a mercadoria chegar.")
        except Exception as e:
            messages.error(request, f"Erro ao criar contrato: {e}")
            
    return redirect(request.META.get('HTTP_REFERER', 'retailer_dashboard'))


from django.http import JsonResponse

@login_required
@role_required(['Retailer', 'Processor', 'Producer'])
def get_forecast_status_api(request):
    """
    Endpoint AJAX para consultar o estado dos modelos de previsão no Forecast Web Service.
    """
    culture_id = request.GET.get('culture_id')
    if not culture_id:
        return JsonResponse({'status': 'error', 'message': 'culture_id é obrigatório.'}, status=400)
    
    subfamily = get_object_or_404(ProductSubFamily, pk=culture_id)
    from dashboard.services.agent_service import get_forecast_model_status
    status_data = get_forecast_model_status(request.user, subfamily)
    
    sales_count = HistoricalSalesData.objects.filter(owner=request.user, culture=subfamily).count()
    status_data['historical_sales_count'] = sales_count
    status_data['culture_name'] = subfamily.name
    
    return JsonResponse({'status': 'success', 'data': status_data})


@login_required
@role_required(['Retailer', 'Processor', 'Producer'])
def upload_sales_history(request):
    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', '') or request.POST.get('is_ajax') == '1'
    
    if request.method == "POST":
        culture_id = request.POST.get('culture_id')
        sales_file = request.FILES.get('sales_file')
        model_type = request.POST.get('model_type', 'modelo_1')
        
        if not culture_id:
            msg = 'Por favor selecione uma cultura.'
            if is_ajax:
                return JsonResponse({'status': 'error', 'message': msg}, status=400)
            messages.error(request, msg)
            return redirect(request.META.get('HTTP_REFERER', 'retailer_dashboard'))
            
        subfamily = get_object_or_404(ProductSubFamily, pk=culture_id)
        
        try:
            import pandas as pd
            if sales_file:
                if sales_file.name.endswith('.xlsx'):
                    df = pd.read_excel(sales_file)
                else:
                    df = pd.read_csv(sales_file)
                    
                # Normalizar nomes de colunas (Inglês, Português e variantes)
                col_mapping = {
                    'day': 'date',
                    'date': 'date',
                    'data': 'date',
                    'Data': 'date',
                    'real_value': 'sales_quantity_kg',
                    'sales_quantity_kg': 'sales_quantity_kg',
                    'vendas_kg': 'sales_quantity_kg',
                    'Vendas_Kg': 'sales_quantity_kg',
                    'price': 'price_per_kg',
                    'price_per_kg': 'price_per_kg',
                    'preco_venda_euro': 'price_per_kg',
                    'Preco_Venda_Euro': 'price_per_kg'
                }
                df = df.rename(columns=col_mapping)
                
                if 'date' not in df.columns or 'sales_quantity_kg' not in df.columns:
                    msg = "O ficheiro deve conter as colunas de data ('Data' ou 'date') e quantidade ('Vendas_Kg' ou 'sales_quantity_kg')."
                    if is_ajax:
                        return JsonResponse({'status': 'error', 'message': msg}, status=400)
                    messages.error(request, msg)
                    return redirect(request.META.get('HTTP_REFERER', 'retailer_dashboard'))
                    
                df['date'] = pd.to_datetime(df['date']).dt.date
                if 'price_per_kg' not in df.columns:
                    df['price_per_kg'] = 2.0  # Preço médio padrão
                    
                df = df[['date', 'sales_quantity_kg', 'price_per_kg']].dropna(subset=['date', 'sales_quantity_kg'])
            else:
                sales_qs = HistoricalSalesData.objects.filter(owner=request.user, culture=subfamily).order_by('date')
                if not sales_qs.exists():
                    msg = "Nenhum ficheiro carregado e não existe histórico anterior guardado para esta cultura."
                    if is_ajax:
                        return JsonResponse({'status': 'error', 'message': msg}, status=400)
                    messages.error(request, msg)
                    return redirect(request.META.get('HTTP_REFERER', 'retailer_dashboard'))
                df = pd.DataFrame(list(sales_qs.values('date', 'sales_quantity_kg', 'price_per_kg')))
                
            from dashboard.services.agent_service import train_sales_forecaster
            res = train_sales_forecaster(request.user, subfamily, df, model_type=model_type)
            
            model_display = res['model_display_name']
            success_msg = f"{model_display} para {subfamily.name} treinado com sucesso no Forecast Web Service! ({res['samples_count']} dias de histórico processados)."
            
            if is_ajax:
                return JsonResponse({
                    'status': 'success',
                    'message': success_msg,
                    'samples_used': res['samples_count'],
                    'model_type': res['model_type'],
                    'trained_at': res['trained_at'],
                    'culture_id': subfamily.pk,
                    'culture_name': subfamily.name
                })
                
            messages.success(request, success_msg)
        except Exception as e:
            err_msg = f"Erro ao treinar modelo: {str(e)}"
            if is_ajax:
                return JsonResponse({'status': 'error', 'message': err_msg}, status=500)
            messages.error(request, err_msg)
            
    return redirect(request.META.get('HTTP_REFERER', 'retailer_dashboard'))


@login_required
@role_required(['Retailer', 'Processor', 'Producer'])
def infer_sales_forecast(request):
    if request.method == "POST":
        culture_id = request.POST.get('culture_id')
        horizon_days = int(request.POST.get('horizon_days', 30))
        model_type = request.POST.get('model_type', None)
        
        if not culture_id:
            return JsonResponse({'status': 'error', 'message': 'Selecione uma cultura para gerar a previsão.'}, status=400)
            
        subfamily = get_object_or_404(ProductSubFamily, pk=culture_id)
        
        try:
            from dashboard.services.agent_service import run_sales_inference
            result = run_sales_inference(request.user, subfamily, horizon_days=horizon_days, model_type=model_type, save_to_db=False)
            
            return JsonResponse({
                'status': 'success',
                'culture_id': subfamily.pk,
                'culture_name': subfamily.name,
                'predictions': result.get('predictions', []),
                'recent_history': result.get('recent_history', []),
                'historical': result.get('recent_history', []),
                'kpis': result.get('kpis', {}),
                'metrics': result.get('kpis', {}),
                'model_type': result.get('model_type', 'modelo_1'),
                'model_display_name': result.get('model_display_name')
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
            
    return JsonResponse({'status': 'error', 'message': 'Método não permitido.'}, status=405)


@login_required
@role_required(['Retailer', 'Processor'])
def train_buyer_agent(request):
    if request.method == "POST":
        is_ajax = (
            request.headers.get('x-requested-with') == 'XMLHttpRequest' or
            request.POST.get('is_ajax') == '1' or
            ('application/json' in request.headers.get('Accept', '') and 'text/html' not in request.headers.get('Accept', ''))
        )
        culture_id = request.POST.get('culture_id') or request.GET.get('culture_id')
        
        subfamily = None
        if culture_id and str(culture_id).strip():
            try:
                c_str = str(culture_id).strip()
                if c_str.isdigit():
                    subfamily = ProductSubFamily.objects.filter(pk=int(c_str)).first()
                else:
                    subfamily = (
                        ProductSubFamily.objects.filter(name__iexact=c_str).first() or
                        ProductSubFamily.objects.filter(name__icontains=c_str).first()
                    )
            except Exception:
                subfamily = None
        
        if not subfamily:
            # Fallback 1: Primeira cultura em stock do utilizador
            stock_item = ConsolidatedStock.objects.filter(owner=request.user).select_related('culture').first()
            if stock_item and stock_item.culture:
                subfamily = stock_item.culture
            else:
                # Fallback 2: Primeiro produto do catálogo
                subfamily = ProductSubFamily.objects.first()

        if not subfamily:
            if is_ajax:
                return JsonResponse({'status': 'error', 'message': 'Nenhuma cultura ou produto registado no sistema.'}, status=400)
            messages.error(request, 'Nenhuma cultura ou produto registado no sistema.')
            return redirect(request.META.get('HTTP_REFERER', 'retailer_dashboard'))

        # Validação Prévia: Armazém com capacidade real configurada
        has_valid_warehouse = Warehouse.objects.filter(owner=request.user, capacity__gt=0).exists()
        if not has_valid_warehouse:
            err_msg = "Não possui nenhum armazém com capacidade registada. Por favor, configure a capacidade do armazém em 'Gestão de Armazéns' antes de treinar o Buyer Agent."
            if is_ajax:
                return JsonResponse({'status': 'error', 'message': err_msg}, status=400)
            messages.error(request, err_msg)
            return redirect(request.META.get('HTTP_REFERER', 'retailer_dashboard'))

        # Validação Prévia: Modelo de previsão treinado no Forecast Service
        from dashboard.services.agent_service import get_forecast_model_status
        fc_status = get_forecast_model_status(request.user, subfamily)
        has_forecast_model = fc_status.get('has_model', False)
        if not has_forecast_model:
            err_msg = f"Não existe modelo de previsão treinado para a cultura '{subfamily.name}'. Deve primeiro aceder à aba 'Previsão de Vendas' e treinar um modelo de previsão antes de treinar o Buyer Agent."
            if is_ajax:
                return JsonResponse({'status': 'error', 'message': err_msg}, status=400)
            messages.error(request, err_msg)
            return redirect(request.META.get('HTTP_REFERER', 'retailer_dashboard'))

        market_file = request.FILES.get('market_file')
        fruit_key = request.POST.get('fruit_key')
        max_episodes = request.POST.get('max_episodes', '350')
        forecast_model_type = request.POST.get('forecast_model_type')
        if not max_episodes or not str(max_episodes).strip():
            max_episodes = '350'
        
        try:
            import pandas as pd
            if market_file:
                if market_file.name.endswith('.xlsx') or market_file.name.endswith('.xls'):
                    df = pd.read_excel(market_file)
                else:
                    df = pd.read_csv(market_file)
                
                col_mapping = {
                    'day': 'date', 'date': 'date', 'data': 'date', 'Date': 'date',
                    'real_value': 'sales_quantity_kg', 'sales_quantity_kg': 'sales_quantity_kg',
                    'vendas_kg': 'sales_quantity_kg', 'quantidade_kg': 'sales_quantity_kg',
                    'price': 'price_per_kg', 'price_per_kg': 'price_per_kg', 'preco_kg': 'price_per_kg'
                }
                df = df.rename(columns=col_mapping)
                if 'date' in df.columns:
                    df['date'] = pd.to_datetime(df['date']).dt.date
            else:
                # Usar histórico já carregado
                sales_qs = HistoricalSalesData.objects.filter(owner=request.user, culture=subfamily)
                if not sales_qs.exists():
                    err_msg = f"Não existe histórico de vendas para {subfamily.name}. Anexe o ficheiro Excel/CSV de treino."
                    if is_ajax:
                        return JsonResponse({'status': 'error', 'message': err_msg}, status=400)
                    messages.error(request, err_msg)
                    return redirect(request.META.get('HTTP_REFERER', 'retailer_dashboard'))
                
                df = pd.DataFrame(list(sales_qs.values('date', 'sales_quantity_kg', 'price_per_kg')))
                
            from dashboard.services.agent_service import train_buyer_agent_optimizer_generator
            
            if is_ajax:
                from django.http import StreamingHttpResponse as DjangoStreamingResponse
                import json as _json

                def stream_logs():
                    try:
                        gen = train_buyer_agent_optimizer_generator(
                            request.user,
                            subfamily,
                            df,
                            max_episodes=max_episodes,
                            fruit_key=fruit_key,
                            forecast_model_type=forecast_model_type
                        )
                        for log_line in gen:
                            clean = log_line.replace('\n', '').strip()
                            if clean:
                                yield f"data: {_json.dumps({'type': 'log', 'text': clean})}\n\n"
                        yield f"data: {_json.dumps({'type': 'done', 'status': 'success', 'message': f'O Buyer Agent para {subfamily.name} foi treinado com sucesso no Web Service!', 'culture_id': subfamily.pk, 'culture_name': subfamily.name})}\n\n"
                    except (ValueError, ConnectionError, RuntimeError) as ex:
                        yield f"data: {_json.dumps({'type': 'error', 'message': str(ex)})}\n\n"
                    except Exception as ex:
                        yield f"data: {_json.dumps({'type': 'error', 'message': str(ex)})}\n\n"

                response = DjangoStreamingResponse(stream_logs(), content_type='text/event-stream')
                response['Cache-Control'] = 'no-cache'
                response['X-Accel-Buffering'] = 'no'
                return response
            
            from dashboard.services.agent_service import train_buyer_agent_optimizer
            logs = train_buyer_agent_optimizer(
                request.user,
                subfamily,
                df,
                max_episodes=max_episodes,
                fruit_key=fruit_key,
                forecast_model_type=forecast_model_type
            )
            messages.success(request, f"O Buyer Agent para {subfamily.name} foi treinado com sucesso!")
        except ValueError as ve:
            if is_ajax:
                return JsonResponse({'status': 'error', 'message': str(ve)}, status=400)
            messages.error(request, str(ve))
        except ConnectionError as ce:
            if is_ajax:
                return JsonResponse({'status': 'error', 'message': str(ce)}, status=503)
            messages.error(request, f"Erro de ligação ao Web Service: {ce}")
        except Exception as e:
            if is_ajax:
                return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
            messages.error(request, f"Erro ao treinar Buyer Agent: {e}")
            
    return redirect(request.META.get('HTTP_REFERER', 'retailer_dashboard'))


@login_required
@role_required(['Retailer', 'Processor'])
def toggle_buyer_agent_status(request):
    if request.method == "POST":
        profile = request.user.userprofile
        profile.buyer_agent_active = not profile.buyer_agent_active
        profile.save()
        
        status_str = "ATIVADO" if profile.buyer_agent_active else "DESATIVADO"
        
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.accepts('application/json'):
            return JsonResponse({
                'status': 'success',
                'buyer_agent_active': profile.buyer_agent_active,
                'message': f"Buyer Agent {status_str} com sucesso!"
            })
            
        messages.success(request, f"Buyer Agent {status_str} com sucesso!")
        
    return redirect(request.META.get('HTTP_REFERER', 'retailer_dashboard'))


@login_required
@role_required(['Retailer', 'Processor'])
def get_buyer_agent_status(request):
    """
    Endpoint AJAX para obter o estado do modelo PPO e do Buyer Agent Web Service (Porta 8002).
    """
    if request.method != "GET":
        return JsonResponse({'status': 'error', 'message': 'Método não permitido.'}, status=405)
        
    culture_id = request.GET.get('culture_id')
    if not culture_id:
        return JsonResponse({'status': 'error', 'message': 'ID da cultura é obrigatório.'}, status=400)
        
    subfamily = get_object_or_404(ProductSubFamily, pk=culture_id)
    
    try:
        from dashboard.services.agent_service import get_buyer_model_status
        status_data = get_buyer_model_status(request.user, subfamily)
        status_data['status'] = 'success'
        status_data['culture_name'] = subfamily.name
        return JsonResponse(status_data)
    except ConnectionError as ce:
        return JsonResponse({
            'status': 'error',
            'service_online': False,
            'message': str(ce),
            'culture_id': subfamily.pk,
            'culture_name': subfamily.name
        }, status=503)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required
@role_required(['Retailer', 'Processor'])
def run_buyer_agent_action(request):
    """
    Executa a inferência diária do Buyer Agent e retorna o relatório analítico completo
    obtido do Buyer Agent Web Service (Porta 8002).
    """
    if request.method == "POST":
        culture_id = request.POST.get('culture_id')
        if not culture_id:
            return JsonResponse({'status': 'error', 'message': 'Cultura não especificada.'}, status=400)

        subfamily = get_object_or_404(ProductSubFamily, pk=culture_id)
        
        try:
            from dashboard.services.agent_service import get_buyer_agent_decision_details
            decision_data = get_buyer_agent_decision_details(request.user, subfamily)
            return JsonResponse(decision_data)
        except ConnectionError as ce:
            return JsonResponse({
                'status': 'error',
                'service_offline': True,
                'message': str(ce)
            }, status=503)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
            
    return JsonResponse({'status': 'error', 'message': 'Método não permitido.'}, status=405)


@login_required
@role_required(['Producer', 'Processor', 'Retailer'])
def get_lot_lifecycle_forecast(request):
    """
    Endpoint AJAX para obter a previsão de ciclo de vida e degradação biológica de um lote específico
    consultando o Lifecycle Decay Prediction Web Service (FastAPI / Porta 8003).
    Retorna as métricas biológicas estimadas no último dia (RSL, Firmeza, Brix, Acidez, Qualidade)
    e comparação com as métricas iniciais.
    """
    if request.method != "GET":
        return JsonResponse({'status': 'error', 'message': 'Método não permitido.'}, status=405)

    lot_id = request.GET.get('lot_id')
    stock_id = request.GET.get('stock_id')
    packaging = request.GET.get('packaging') or request.GET.get('packaging_method')

    if not lot_id and not stock_id:
        return JsonResponse({'status': 'error', 'message': 'Parâmetro lot_id ou stock_id em falta.'}, status=400)

    import requests
    from django.conf import settings

    target_id = lot_id or stock_id
    payload = build_lot_lifecycle_data(lot_id=lot_id, stock_id=stock_id, user=request.user, packaging_method=packaging)

    if not payload:
        return JsonResponse({'status': 'error', 'message': f'Lote #{target_id} não encontrado.'}, status=404)

    lot_info = payload.get('lot_identification', {})
    initial_m = lot_info.get('initial_metrics', {})
    warehouse_info = payload.get('current_warehouse', {})

    lifecycle_url = getattr(settings, 'LIFECYCLE_SERVICE_URL', 'http://127.0.0.1:8003').rstrip('/')
    service_status = "ONLINE"
    service_error = None
    forecast_data = {}

    try:
        ws_res = requests.post(f"{lifecycle_url}/forecast", json=payload, timeout=6)
        if ws_res.status_code == 200:
            forecast_data = ws_res.json()
        else:
            return JsonResponse({
                'status': 'error',
                'service_status': 'OFFLINE',
                'message': f'O Lifecycle Web Service (Porta 8003) retornou código HTTP {ws_res.status_code}. Por favor verifique se o serviço está ativo.'
            }, status=503)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'service_status': 'OFFLINE',
            'message': f'O Lifecycle Web Service (Porta 8003) está inacessível ou desligado ({e}). O cálculo de tempo de vida útil requer o serviço ativo.'
        }, status=503)

    # Leituras climáticas mais recentes do armazém
    wh_history = payload.get('sensor_history_by_warehouse', [])
    temp_today = 4.0
    hum_today = 90.0
    eth_today = 0.01
    if wh_history and len(wh_history) > 0:
        readings = wh_history[-1].get('daily_readings', [])
        if readings:
            latest = readings[-1]
            temp_today = latest.get('temperature_celsius', 4.0) or 4.0
            hum_today = latest.get('humidity_percent', 90.0) or 90.0
            eth_today = latest.get('ethylene_ppm', 0.01) or 0.01

    response_payload = {
        'status': 'success',
        'service_status': service_status,
        'service_url': lifecycle_url,
        'service_error': service_error,
        'lot_id': lot_info.get('lot_id'),
        'batch_id': lot_info.get('batch_id'),
        'culture_name': lot_info.get('culture_name'),
        'fruit_type': lot_info.get('fruit_type'),
        'producer': lot_info.get('producer'),
        'current_owner': lot_info.get('current_owner'),
        'current_owner_type': lot_info.get('current_owner_type', 'Retailer'),
        'harvest_date': lot_info.get('harvest_date'),
        'current_stock_kg': lot_info.get('current_stock_kg'),
        'warehouse_location': warehouse_info.get('location', 'N/A'),
        'warehouse_region': warehouse_info.get('region', 'PT-LVT'),
        'temp_today': float(temp_today),
        'hum_today': float(hum_today),
        'eth_today': float(eth_today),
        'packaging_method': packaging or payload.get('packaging_method', 'bulk'),
        'forecast': {
            'algorithm': forecast_data.get('algorithm', 'ode_new'),
            'product_id': forecast_data.get('product_id', lot_info.get('fruit_type', 'apple')),
            'commercial_lifetime_remaining': forecast_data.get('commercial_lifetime_remaining', forecast_data.get('remaining_lifetime', 0.0)),
            'biological_lifetime_remaining': forecast_data.get('biological_lifetime_remaining', 0.0),
            'remaining_lifetime': forecast_data.get('commercial_lifetime_remaining', forecast_data.get('remaining_lifetime', 0.0)),
            'point_a_day': forecast_data.get('point_a_day'),
            'point_b_day': forecast_data.get('point_b_day'),
            'firmness': forecast_data.get('firmness'),
            'brix': forecast_data.get('brix'),
            'acidity': forecast_data.get('acidity'),
            'mold': forecast_data.get('mold', 0.0),
            'quality_index': forecast_data.get('quality_index', 0.0),
            'continuous_data': forecast_data.get('continuous_data'),
        },
        'initial_metrics': {
            'quality_score': initial_m.get('quality_score'),
            'soluble_solids_brix': initial_m.get('soluble_solids_brix'),
            'firmness': initial_m.get('firmness') or initial_m.get('firmness_n'),
            'acidity': initial_m.get('acidity') or initial_m.get('acidity_percent'),
            'caliber_mm': initial_m.get('caliber_mm'),
        },
        'export_metadata': payload.get('export_metadata', {})
    }

    return JsonResponse(response_payload)


@login_required
@role_required(['Producer', 'Processor', 'Retailer'])
def get_lc_decay_data(request):
    """
    Compatibilidade com endpoint anterior de ciclo de vida.
    """
    return get_lot_lifecycle_forecast(request)


def build_lot_lifecycle_data(lot_id=None, stock_id=None, user=None, packaging_method=None):
    """
    Constrói o payload JSON padronizado e integral de um lote desde a colheita até ao dia atual,
    incluindo eventos de blockchain, leituras diárias de sensores do armazém e regras de imputação meteorológica.
    """
    import datetime
    import json
    import logging
    from django.db import models
    from dashboard.services.fabric_service import fabric_service
    from dashboard.models import Harvest, ConsolidatedStock, Warehouse, WarehouseSensorReading, PlantationEvent

    logger = logging.getLogger(__name__)

    today = datetime.date.today()
    harvest = None
    stock = None

    if lot_id:
        harvest = Harvest.objects.filter(pk=lot_id).select_related('plantation', 'subfamily', 'warehouse', 'producer').first()
        if not harvest and not stock_id:
            stock = ConsolidatedStock.objects.filter(pk=lot_id).select_related('culture', 'owner').first()
    
    if stock_id and not harvest and not stock:
        stock = ConsolidatedStock.objects.filter(pk=stock_id).select_related('culture', 'owner').first()

    if not harvest and not stock:
        return None

    # Se for colheita direta do produtor
    if harvest:
        lot_pk = harvest.pk
        batch_id = f"LOTE-{harvest.pk}"
        culture_name = harvest.subfamily.name if harvest.subfamily else "Desconhecida"
        fruit_type = harvest.subfamily.fruit_type if harvest.subfamily else "N/A"
        producer_name = harvest.producer.username if harvest.producer else "N/A"
        owner_name = harvest.producer.username if harvest.producer else "N/A"
        harvest_date = harvest.harvest_date
        days_elapsed = max(0, (today - harvest_date).days)
        initial_qty = float(harvest.harvest_quantity_kg)
        current_qty = float(harvest.current_stock_kg)
        delivered_qty = float(harvest.delivered_quantity_kg or 0.0)
        
        initial_metrics = {
            "firmness": float(harvest.firmness) if hasattr(harvest, 'firmness') and harvest.firmness is not None else None,
            "firmness_n": float(harvest.firmness) if hasattr(harvest, 'firmness') and harvest.firmness is not None else None,
            "soluble_solids_brix": float(harvest.soluble_solids) if harvest.soluble_solids is not None else None,
            "acidity": float(harvest.acidity) if hasattr(harvest, 'acidity') and harvest.acidity is not None else None,
            "acidity_percent": float(harvest.acidity) if hasattr(harvest, 'acidity') and harvest.acidity is not None else None,
            "caliber_mm": float(harvest.caliber) if harvest.caliber is not None else None,
            "quality_score": float(harvest.avg_quality_score) if harvest.avg_quality_score is not None else 10.0,
            "waste_kg": float(harvest.utilized_quantity_kg or 0.0),
            "expiration_date": harvest.expiration_date.strftime("%Y-%m-%d") if harvest.expiration_date else None
        }

        # Armazém
        warehouse = harvest.warehouse or Warehouse.objects.filter(owner=harvest.producer).first()

        # Plantação
        plantation = harvest.plantation
        plantation_info = {
            "plantation_id": plantation.pk if plantation else None,
            "name": plantation.plantation_name if plantation else "N/A",
            "location": plantation.location if plantation else "N/A",
            "production_type": plantation.get_production_type_display() if plantation else "N/A",
            "chemical_use": plantation.get_chemical_use_display() if plantation else "N/A",
            "soil_type": plantation.get_soil_type_display() if plantation else "N/A",
            "water_regime": plantation.get_water_regime_display() if plantation else "N/A",
            "conduct_system": plantation.get_conduct_system_display() if plantation else "N/A",
            "ph_soil": float(plantation.ph_soil) if plantation and plantation.ph_soil else None,
            "organic_matter_percent": float(plantation.organic_matter_percent) if plantation and plantation.organic_matter_percent else None,
        }

        # Eventos agrícolas
        plantation_events = []
        if plantation:
            for ev in plantation.events.all().order_by('event_date'):
                plantation_events.append({
                    "event_id": ev.pk,
                    "date": ev.event_date.strftime("%Y-%m-%d"),
                    "type": ev.get_event_type_display(),
                    "notes": ev.notes or ""
                })

        # Ordens e transações associadas obtidas do marketplace web service
        orders = [d for d in marketplace_service.get_closed_deals_adapted() if str(getattr(d, 'harvest_origin_id', '')) == str(harvest.pk) or getattr(d, 'batch_id', None) == f"LOTE-{harvest.pk}"]

    else: # ConsolidatedStock (Processor ou Retailer)
        lot_pk = stock.pk
        batch_id = f"STOCK-{stock.pk}"
        culture_name = stock.culture.name if stock.culture else "Desconhecida"
        fruit_type = stock.culture.fruit_type if stock.culture else "N/A"
        owner_name = stock.owner.username if stock.owner else "N/A"
        
        clean_location = stock.warehouse_location.split(' (WH:')[0].strip() if stock.warehouse_location and ' (WH:' in stock.warehouse_location else stock.warehouse_location
        warehouse = Warehouse.objects.filter(owner=stock.owner, location=clean_location).first() or Warehouse.objects.filter(owner=stock.owner).first()

        orders = marketplace_service.get_closed_deals_adapted(username=stock.owner.username)

        earliest_harvest = None
        producer_name = "Vários/Agregado"
        for o in orders:
            if hasattr(o, 'harvest_origin') and o.harvest_origin:
                producer_name = o.harvest_origin.producer.username
                if not earliest_harvest or o.harvest_origin.harvest_date < earliest_harvest:
                    earliest_harvest = o.harvest_origin.harvest_date
        
        harvest_date = earliest_harvest if earliest_harvest else (today - datetime.timedelta(days=10))
        days_elapsed = max(0, (today - harvest_date).days)
        initial_qty = float(stock.quantity)
        current_qty = float(stock.quantity)
        delivered_qty = 0.0

        initial_metrics = {
            "soluble_solids_brix": float(stock.avg_soluble_solids) if stock.avg_soluble_solids is not None else None,
            "caliber_mm": float(stock.avg_caliber) if stock.avg_caliber is not None else None,
            "quality_score": float(stock.avg_quality_score) if stock.avg_quality_score is not None else 10.0,
            "waste_kg": 0.0,
            "expiration_date": None
        }
        plantation_info = {"note": "Lote consolidado em armazém a jusante"}
        plantation_events = []

        # Âncora do ciclo de vida: a receção mais antiga ainda em stock (FIFO, pior caso):
        #  - com medições (brix/acidez/firmeza) -> começa no dia da receção com os valores reais
        #  - sem medições -> segue a partir da colheita do lote de origem, com as métricas da colheita
        from dashboard.services.reception_service import lifecycle_reception_for_stock
        reception = lifecycle_reception_for_stock(stock)
        if reception:
            origin_harvest = None
            if reception.batch_id and reception.batch_id.startswith("LOTE-") and reception.batch_id[5:].isdigit():
                origin_harvest = Harvest.objects.filter(pk=int(reception.batch_id[5:])).select_related('producer', 'warehouse').first()
            if origin_harvest and origin_harvest.producer:
                producer_name = origin_harvest.producer.username
            elif reception.seller_id:
                producer_name = reception.seller_id

            def _f(v):
                return float(v) if v is not None else None

            if reception.has_measurements:
                harvest_date = reception.received_at
                initial_metrics = {
                    "firmness": _f(reception.firmness),
                    "firmness_n": _f(reception.firmness),
                    "soluble_solids_brix": _f(reception.soluble_solids),
                    "acidity": _f(reception.acidity),
                    "acidity_percent": _f(reception.acidity),
                    "caliber_mm": _f(reception.caliber),
                    "quality_score": _f(reception.quality_score) if reception.quality_score is not None else float(stock.avg_quality_score or 10.0),
                    "waste_kg": 0.0,
                    "expiration_date": None,
                }
                lc_anchor = {"type": "RECEPTION_MEASURED", "deal_id": reception.deal_id, "date": reception.received_at.isoformat()}
            elif origin_harvest:
                harvest_date = origin_harvest.harvest_date
                initial_metrics = {
                    "firmness": _f(origin_harvest.firmness),
                    "firmness_n": _f(origin_harvest.firmness),
                    "soluble_solids_brix": _f(origin_harvest.soluble_solids),
                    "acidity": _f(origin_harvest.acidity),
                    "acidity_percent": _f(origin_harvest.acidity),
                    "caliber_mm": _f(origin_harvest.caliber),
                    "quality_score": _f(origin_harvest.avg_quality_score) if origin_harvest.avg_quality_score is not None else 10.0,
                    "waste_kg": 0.0,
                    "expiration_date": origin_harvest.expiration_date.strftime("%Y-%m-%d") if origin_harvest.expiration_date else None,
                }
                lc_anchor = {"type": "ORIGIN_HARVEST", "deal_id": reception.deal_id, "batch_id": reception.batch_id, "date": harvest_date.isoformat()}
            else:
                lc_anchor = {"type": "ESTIMATED", "deal_id": reception.deal_id}
            days_elapsed = max(0, (today - harvest_date).days)
        else:
            origin_harvest = None
            lc_anchor = {"type": "ESTIMATED"}

    # Informação e Estratégia Meteorológica do Armazém
    if warehouse:
        meteo_source = warehouse.meteo_source or 'FIXED'
        json_fallback = warehouse.json_fallback_mode or 'FIXED'
        fixed_t = float(warehouse.fixed_temperature if warehouse.fixed_temperature is not None else 4.0)
        fixed_h = float(warehouse.fixed_humidity if warehouse.fixed_humidity is not None else 90.0)
        wh_region = warehouse.region or 'PT-LVT'

        warehouse_info = {
            "id": warehouse.warehouse_id,
            "location": warehouse.location,
            "region": warehouse.region,
            "region_display": warehouse.get_region_display(),
            "control_type": warehouse.control_type,
            "storage_unit": warehouse.storage_unit,
            "capacity_kg": float(warehouse.capacity) if warehouse.capacity else None,
            "latitude": float(warehouse.latitude) if warehouse.latitude else None,
            "longitude": float(warehouse.longitude) if warehouse.longitude else None,
            "has_installed_sensors": warehouse.sensors.exists(),
        }
    else:
        meteo_source = 'FIXED'
        json_fallback = 'FIXED'
        fixed_t = 4.0
        fixed_h = 90.0
        wh_region = 'PT-LVT'
        warehouse_info = {
            "id": None,
            "location": "Não atribuído",
            "region": "PT-LVT",
            "control_type": "Controlled",
            "storage_unit": "PALLETS"
        }

    # Instruções de Imputação Meteorológica para o Web Service
    if meteo_source == 'FIXED':
        imputation_desc = f"Valores Fixos configurados: Temperatura constante a {fixed_t}°C e Humidade Relativa a {fixed_h}%."
    elif meteo_source == 'IPMA':
        imputation_desc = f"Fonte Meteorológica IPMA Regional ({wh_region}): Utilizar médias climáticas regionais sazonais do IPMA para o período."
    elif meteo_source == 'JSON':
        if json_fallback == 'FIXED':
            imputation_desc = f"Fonte Primária: Ficheiro JSON de Sensores. Em caso de ausência de leituras ou falhas de datas, preencher (fallback) com Valores Fixos ({fixed_t}°C, {fixed_h}% RH)."
        elif json_fallback == 'IPMA':
            imputation_desc = f"Fonte Primária: Ficheiro JSON de Sensores. Em caso de ausência de leituras ou falhas de datas, preencher (fallback) com IPMA Regional ({wh_region})."
        else:
            imputation_desc = "Fonte Primária: Ficheiro JSON de Sensores sem preenchimento de falhas."
    else:
        imputation_desc = f"Valores padrão ({fixed_t}°C, {fixed_h}% RH)."

    meteorology_strategy = {
        "meteo_source": meteo_source,
        "meteo_source_display": dict(Warehouse.METEO_SOURCE_CHOICES).get(meteo_source, meteo_source) if hasattr(Warehouse, 'METEO_SOURCE_CHOICES') else meteo_source,
        "json_fallback_mode": json_fallback,
        "json_fallback_display": dict(Warehouse.JSON_FALLBACK_CHOICES).get(json_fallback, json_fallback) if hasattr(Warehouse, 'JSON_FALLBACK_CHOICES') else json_fallback,
        "fixed_temperature_celsius": fixed_t,
        "fixed_humidity_percent": fixed_h,
        "ipma_region_code": wh_region,
        "imputation_instructions": imputation_desc
    }

    # Extrair Eventos da Blockchain Real (Hyperledger Fabric)
    blockchain_events = []
    try:
        fabric_history = fabric_service.get_asset_history(batch_id, caller_id=user.username if user else None)
        if isinstance(fabric_history, list) and fabric_history:
            for idx, h in enumerate(fabric_history):
                val_data = h.get('value', {})
                if isinstance(val_data, str):
                    try:
                        val_data = json.loads(val_data)
                    except Exception:
                        pass
                blockchain_events.append({
                    "tx_id": h.get('txId', f"tx-{idx}"),
                    "timestamp": h.get('timestamp'),
                    "is_delete": h.get('isDelete', False),
                    "order_status": val_data.get('orderStatus') if isinstance(val_data, dict) else None,
                    "data": val_data
                })
        else:
            current_order = fabric_service.get_order(batch_id, caller_id=user.username if user else None)
            if current_order:
                blockchain_events.append({
                    "tx_id": "current_state",
                    "order_status": current_order.get('orderStatus'),
                    "data": current_order
                })
    except Exception as e:
        logger.warning(f"Could not retrieve blockchain history for {batch_id}: {e}")

    # Histórico de Transporte e Logística
    logistics_history = []
    for o in orders:
        requester_user = getattr(o, 'requester', None)
        fulfilled_user = getattr(o, 'fulfilled_by', None)
        transporter_user = getattr(o, 'transporter', None)
        vehicle_obj = getattr(o, 'vehicle', None)
        dest_wh = getattr(o, 'destination_warehouse', None)
        
        actual_pickup = getattr(o, 'actual_pickup_date', None)
        planned_pickup = getattr(o, 'planned_pickup_date', None)
        actual_delivery = getattr(o, 'actual_delivery_date', None)
        planned_delivery = getattr(o, 'planned_delivery_date', None)

        logistics_history.append({
            "order_id": getattr(o, 'pk', None) or getattr(o, 'id', None),
            "order_type": getattr(o, 'order_type', 'PURCHASE'),
            "requester": requester_user.username if hasattr(requester_user, 'username') else str(requester_user or ''),
            "fulfilled_by": fulfilled_user.username if hasattr(fulfilled_user, 'username') else str(fulfilled_user or ''),
            "status": getattr(o, 'status', 'COMPLETED'),
            "transport_status": getattr(o, 'transport_status', 'DELIVERED'),
            "transporter": transporter_user.username if hasattr(transporter_user, 'username') else str(transporter_user or ''),
            "vehicle": str(vehicle_obj) if vehicle_obj else None,
            "pickup_date": actual_pickup.isoformat() if actual_pickup else (planned_pickup.isoformat() if planned_pickup else None),
            "delivery_date": actual_delivery.isoformat() if actual_delivery else (planned_delivery.isoformat() if planned_delivery else None),
            "origin_warehouse": getattr(o, 'warehouse_location', 'N/A'),
            "destination_warehouse": dest_wh.location if hasattr(dest_wh, 'location') else getattr(o, 'warehouse_location', 'N/A'),
            "quantity_kg": float(getattr(o, 'quantity_kg', 0.0) or 0.0),
            "transport_sensor_data": getattr(o, 'transport_sensor_data', "No sensor data recorded during transport")
        })

    # Construir Linha Temporal Cronológica de Armazéns sem Sobreposição
    timeline_segments = []
    
    if harvest:
        current_wh = harvest.warehouse or warehouse
        current_start = harvest_date
        
        # Apenas ordens que foram efetivamente entregues transferem o fruto fisicamente para o próximo armazém
        def _get_dt(item, *attr_names):
            for name in attr_names:
                v = getattr(item, name, None)
                if v:
                    if hasattr(v, 'date'):
                        return v.date()
                    if isinstance(v, datetime.date):
                        return v
            return None

        delivered_orders = [
            o for o in orders 
            if getattr(o, 'transport_status', '') == 'DELIVERED' or (_get_dt(o, 'actual_delivery_date', 'delivery_date') and _get_dt(o, 'actual_delivery_date', 'delivery_date') <= today)
        ]
        
        if delivered_orders:
            for o in delivered_orders:
                dep_date = _get_dt(o, 'actual_pickup_date', 'planned_pickup_date', 'created_at') or current_start
                dep_date = max(current_start, min(today, dep_date))
                
                arr_date = _get_dt(o, 'actual_delivery_date', 'delivery_date', 'planned_delivery_date', 'fulfilled_at') or dep_date
                arr_date = max(dep_date, min(today, arr_date))
                
                # Segmento no armazém de origem até à data de saída
                if current_wh and dep_date >= current_start:
                    timeline_segments.append({
                        "warehouse": current_wh,
                        "start_date": current_start,
                        "end_date": dep_date
                    })
                
                # O armazém de destino inicia após a saída/chegada (evitando duplicar o dia de transição)
                dest_wh = getattr(o, 'destination_warehouse', None)
                if dest_wh:
                    current_wh = dest_wh
                current_start = dep_date + datetime.timedelta(days=1) if arr_date <= dep_date else arr_date
            
            # Segmento final no último armazém até ao dia de hoje
            if current_wh and current_start <= today:
                timeline_segments.append({
                    "warehouse": current_wh,
                    "start_date": current_start,
                    "end_date": today
                })
        else:
            # Lote manteve-se no armazém de origem durante todo o período
            if current_wh:
                timeline_segments.append({
                    "warehouse": current_wh,
                    "start_date": harvest_date,
                    "end_date": today
                })
                
    elif reception: # ConsolidatedStock com receção confirmada
        stock_wh = warehouse
        if reception.has_measurements:
            # Ciclo de vida reinicia no dia da receção, no armazém do comprador
            if stock_wh:
                timeline_segments.append({"warehouse": stock_wh, "start_date": harvest_date, "end_date": today})
        else:
            # Desde a colheita no armazém de origem até à véspera da receção, depois no armazém do comprador
            received = min(reception.received_at, today)
            orig_wh = origin_harvest.warehouse if origin_harvest else None
            if orig_wh and received > harvest_date:
                timeline_segments.append({"warehouse": orig_wh, "start_date": harvest_date,
                                          "end_date": received - datetime.timedelta(days=1)})
            if stock_wh:
                timeline_segments.append({"warehouse": stock_wh, "start_date": max(harvest_date, received), "end_date": today})

    else: # ConsolidatedStock (Processor ou Retailer)
        stock_wh = warehouse
        inbound_order = orders[0] if orders else None
        
        def _get_dt_inbound(item, *attr_names):
            for name in attr_names:
                v = getattr(item, name, None)
                if v:
                    if hasattr(v, 'date'):
                        return v.date()
                    if isinstance(v, datetime.date):
                        return v
            return None

        if inbound_order:
            dep_date = _get_dt_inbound(inbound_order, 'actual_pickup_date', 'planned_pickup_date', 'created_at') or harvest_date
            dep_date = max(harvest_date, min(today, dep_date))
            
            arr_date = _get_dt_inbound(inbound_order, 'actual_delivery_date', 'delivery_date', 'planned_delivery_date', 'fulfilled_at') or dep_date
            arr_date = max(dep_date, min(today, arr_date))
            
            harvest_origin = getattr(inbound_order, 'harvest_origin', None)
            orig_wh = getattr(harvest_origin, 'warehouse', None) if harvest_origin else None
            
            # Segmento no produtor de origem
            if orig_wh and dep_date >= harvest_date:
                timeline_segments.append({
                    "warehouse": orig_wh,
                    "start_date": harvest_date,
                    "end_date": dep_date
                })
                
            # Segmento no armazém atual do stock
            stock_start = dep_date + datetime.timedelta(days=1) if arr_date <= dep_date else arr_date
            if stock_wh and stock_start <= today:
                timeline_segments.append({
                    "warehouse": stock_wh,
                    "start_date": stock_start,
                    "end_date": today
                })
        else:
            if stock_wh:
                timeline_segments.append({
                    "warehouse": stock_wh,
                    "start_date": harvest_date,
                    "end_date": today
                })

    # Extrair Leituras de Sensores para cada Segmento Cronológico
    sensor_history_by_warehouse = []
    has_any_real_ethylene = False

    for seg in timeline_segments:
        wh = seg["warehouse"]
        seg_start = seg["start_date"]
        seg_end = seg["end_date"]
        
        if not wh or seg_start > seg_end:
            continue

        if wh.sensor_readings.count() < 30:
            try:
                from dashboard.services.lc_service import generate_fallback_sensor_readings
                generate_fallback_sensor_readings(wh)
            except Exception:
                pass

        readings_qs = WarehouseSensorReading.objects.filter(
            warehouse=wh,
            date__gte=seg_start,
            date__lte=seg_end
        ).order_by('date')

        daily_readings = []
        wh_source = wh.meteo_source or 'FIXED'
        for r in readings_qs:
            eth_ppm = float(r.ethylene) if (wh_source == 'JSON' and r.ethylene is not None) else None
            if eth_ppm is not None:
                has_any_real_ethylene = True

            daily_readings.append({
                "date": r.date.strftime("%Y-%m-%d"),
                "temperature_celsius": float(r.temperature),
                "humidity_percent": float(r.humidity),
                "ethylene_ppm": eth_ppm,
                "source": "SENSOR_RECORDING" if wh_source == 'JSON' else ("IPMA_REGIONAL" if wh_source == 'IPMA' else "FIXED_PRESET")
            })

        seg_pkg = packaging_method or ("open_box" if wh.storage_unit == 'CRATES' else "bulk")
        sensor_history_by_warehouse.append({
            "warehouse_id": wh.warehouse_id,
            "warehouse_location": wh.location,
            "region": wh.region,
            "meteo_source": wh_source,
            "packaging_method": seg_pkg,
            "period": {
                "start_date": seg_start.strftime("%Y-%m-%d"),
                "end_date": seg_end.strftime("%Y-%m-%d"),
                "total_days": len(daily_readings)
            },
            "total_days_recorded": len(daily_readings),
            "daily_readings": daily_readings
        })

    # Atualizar estratégia meteorológica com flag de sensor de etileno
    meteorology_strategy["has_ethylene_sensor"] = has_any_real_ethylene

    user_role = 'Retailer'
    if user and hasattr(user, 'groups'):
        group_names = [g.name for g in user.groups.all()]
        if 'Producer' in group_names:
            user_role = 'Producer'
        elif 'Processor' in group_names:
            user_role = 'Processor'
        elif 'Retailer' in group_names:
            user_role = 'Retailer'
    elif harvest and not stock:
        user_role = 'Producer'
    elif stock and hasattr(stock, 'owner') and stock.owner:
        group_names = [g.name for g in stock.owner.groups.all()]
        if 'Processor' in group_names:
            user_role = 'Processor'
        elif 'Retailer' in group_names:
            user_role = 'Retailer'

    # Payload Final Completo
    payload = {
        "version": "1.0",
        "export_metadata": {
            "generated_at": datetime.datetime.now().isoformat(),
            "target_service": "Lifecycle Decay Prediction Model Web Service",
            "days_elapsed_total": days_elapsed,
            "date_interval": {
                "start_date": harvest_date.strftime("%Y-%m-%d"),
                "end_date": today.strftime("%Y-%m-%d")
            }
        },
        "packaging_method": packaging_method or "bulk",
        "plot_info": True,
        "lot_identification": {
            "lot_id": lot_pk,
            "batch_id": batch_id,
            "culture_name": culture_name,
            "fruit_type": fruit_type,
            "producer": producer_name,
            "current_owner": owner_name,
            "current_owner_type": user_role,
            "harvest_date": harvest_date.strftime("%Y-%m-%d"),
            "initial_quantity_kg": initial_qty,
            "current_stock_kg": current_qty,
            "delivered_quantity_kg": delivered_qty,
            "initial_metrics": initial_metrics,
            "lifecycle_anchor": lc_anchor if not harvest else {"type": "HARVEST"}
        },
        "plantation_origin": plantation_info,
        "plantation_agricultural_events": plantation_events,
        "current_warehouse": warehouse_info,
        "meteorology_and_imputation_strategy": meteorology_strategy,
        "blockchain_ledger": {
            "total_blocks_count": len(blockchain_events),
            "blocks": blockchain_events
        },
        "transport_and_logistics": logistics_history,
        "sensor_history_by_warehouse": sensor_history_by_warehouse
    }

    return payload


@login_required
def download_lot_lifecycle_json(request, lot_id):
    """
    Endpoint para exportar e descarregar o ficheiro JSON de ciclo de vida completo de um lote
    com rastreabilidade Blockchain e Meteorologia.
    """
    import json
    from django.http import HttpResponse, Http404

    stock_id = request.GET.get('stock_id')
    payload = build_lot_lifecycle_data(lot_id=lot_id, stock_id=stock_id, user=request.user)

    if not payload:
        raise Http404(f"Lote #{lot_id} não encontrado.")

    response_data = json.dumps(payload, indent=2, ensure_ascii=False)
    filename = f"lote_{lot_id}_lifecycle_data.json"
    
    response = HttpResponse(response_data, content_type="application/json; charset=utf-8")
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
