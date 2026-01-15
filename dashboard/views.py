from django.db import IntegrityError, transaction
from django.db.models import Sum, Q
from django import forms
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views import View
from django.utils import timezone
from django.urls import reverse, reverse_lazy 
from .decorators import role_required 
from django.contrib.auth.models import Group
from django.contrib import messages

from .models import (
    Product, PlantationPlan, Harvest, Warehouse, Sensor, UserProfile, PlantationEvent,
    SoilCharacteristic, PlantationSoilValue, ProductSubFamily, PlantationCrop,
    FertilizerSyntheticData, FertilizerOrganicData, SoilCorrectiveData, PestControlData,
    MachineryData, FuelData, ElectricEnergyData, IrrigationWaterData, MarketplaceOrder
)
from blockchain.services import blockchain_service
from blockchain.utils import create_genesis_dossier

from .forms import (
    UserRegisterForm, ProductRegistrationForm, PlantationPlanForm, PlantationDetailForm,
    HarvestForm, WarehouseRegistrationForm, SensorRegistrationForm, PlantationEventForm,
    FertilizerSyntheticForm, FertilizerOrganicForm, SoilCorrectiveForm, PestControlForm,
    MachineryForm, FuelForm, ElectricEnergyForm, IrrigationWaterForm, SoilCharacteristicForm, PlantationCropForm, MarketplaceOrderForm,
    MarketSellOrderForm,
    TransportPlanForm, TransportDeliveryForm, ProcessorProcessingForm
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

# Transporter Dashboard
@method_decorator(login_required, name='dispatch')
@method_decorator(role_required(['Transporter']), name='dispatch')
class TransporterDashboardView(View):
    def get(self, request):
        user = request.user
        
        # 0. Mercado de Trabalho (Transações FEITAS, status=APPROVED, mas sem Transportador)
        # Mostra encomendas onde Producer e Retailer já fecharam negócio.
        open_orders = MarketplaceOrder.objects.filter(status='APPROVED', transport_status='PENDING').select_related('requester', 'culture', 'fulfilled_by').order_by('-fulfilled_at')

        # 1. Encomendas ACEITES pelo Transportador (Status Transporte = ACCEPTED) -> Passam para Planeamento
        orders_to_plan = MarketplaceOrder.objects.filter(status='APPROVED', transport_status='ACCEPTED').select_related('requester', 'culture', 'fulfilled_by').order_by('-fulfilled_at')
        
        # 2. Encomendas Planeadas, prontas para recolha (Status Transporte = PLANNED)
        orders_ready_pickup = MarketplaceOrder.objects.filter(status='APPROVED', transport_status='PLANNED').select_related('requester', 'culture', 'fulfilled_by').order_by('planned_pickup_date')
        
        # 3. Encomendas Em Trânsito (Status Transporte = IN_TRANSIT)
        orders_in_transit = MarketplaceOrder.objects.filter(status='APPROVED', transport_status='IN_TRANSIT').select_related('requester', 'culture', 'fulfilled_by').order_by('actual_pickup_date')

        # 4. Histórico de Entregas (Status Transporte = DELIVERED)
        closed_orders = MarketplaceOrder.objects.filter(status='APPROVED', transport_status='DELIVERED').select_related('requester', 'culture', 'fulfilled_by').order_by('-actual_delivery_date')
        
        try:
            user_profile = UserProfile.objects.get(user=user)
        except UserProfile.DoesNotExist:
            user_profile = None

        context = { 
            'username': user.username, 
            'role': 'Transporter',
            'user_profile': user_profile,
            
            # Listas segmentadas
            'open_market_orders': open_orders,
            'orders_to_plan': orders_to_plan,
            'orders_ready_pickup': orders_ready_pickup,
            'orders_in_transit': orders_in_transit,
            'closed_market_orders': closed_orders, # Histórico
            
            # Formulários
            'market_order_form': MarketplaceOrderForm(initial={'role': 'Transporter', 'order_type': 'BUY'}),
            'transport_plan_form': TransportPlanForm(),
            'transport_delivery_form': TransportDeliveryForm(),
        }
        return render(request, 'dashboard/transporterDash.html', context)

# Consumer Dashboard
@method_decorator(login_required, name='dispatch')
@method_decorator(role_required(['Consumer']), name='dispatch')
class ConsumerDashboardView(View):
    def get(self, request):
        user = request.user
        open_orders = MarketplaceOrder.objects.filter(status='OPEN').select_related('requester', 'culture').order_by('-created_at')
        closed_orders = MarketplaceOrder.objects.filter(Q(requester=user) | Q(fulfilled_by=user), status='APPROVED').select_related('requester', 'culture', 'fulfilled_by').order_by('-fulfilled_at')

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
            'market_order_form': MarketplaceOrderForm(initial={'role': 'Consumer', 'order_type': 'BUY'})
        }
        return render(request, 'dashboard/consumerDash.html', context)

# Processor Dashboard
@method_decorator(login_required, name='dispatch')
@method_decorator(role_required(['Processor']), name='dispatch')
class ProcessorDashboardView(View):
    def get(self, request):
        user = request.user
        open_orders = MarketplaceOrder.objects.filter(status='OPEN').select_related('requester', 'culture').order_by('-created_at')
        closed_orders = MarketplaceOrder.objects.filter(Q(requester=user) | Q(fulfilled_by=user), status='APPROVED').select_related('requester', 'culture', 'fulfilled_by').order_by('-fulfilled_at')

        try:
            user_profile = UserProfile.objects.get(user=user)
        except UserProfile.DoesNotExist:
            user_profile = None

        # Calcular Stock Atual do Processador (Baseado em Compras - Vendas)
        # Como o Processador não tem "Harvests", o stock é puramente transacional.
        stock_map = {} # { (1, 'Warehouse A'): 500, ... } (Key is ID)
        name_map = {} # { 1: "Kiwi (Hayward)" } - Store proper display name
        
        # 1. Somar entradas (Stock IN)
        # SÓ CONTA SE TIVER SIDO PROCESSADO (is_processed=True)
        purchases_made = MarketplaceOrder.objects.filter(requester=user, order_type='BUY', status='APPROVED', transport_status='DELIVERED', is_processed=True)
        sales_accepted = MarketplaceOrder.objects.filter(fulfilled_by=user, order_type='SELL', status='APPROVED', transport_status='DELIVERED', is_processed=True)
        
        # Encomendas que chegaram mas ainda não foram processadas
        unprocessed_orders = MarketplaceOrder.objects.filter(
            Q(requester=user) | Q(fulfilled_by=user),
            status='APPROVED',
            transport_status='DELIVERED',
            is_processed=False
        ).order_by('actual_delivery_date')
        
        from itertools import chain
        # Structure: key -> {'qty': net_qty, 'qty_in': total_in, 'mass_cal': 0, 'mass_brix': 0, 'mass_score': 0}
        
        for p in chain(purchases_made, sales_accepted):
            key = (p.culture.pk, p.warehouse_location)
            if key not in stock_map:
                stock_map[key] = {'qty': 0, 'qty_in': 0, 'mass_cal': 0, 'mass_brix': 0, 'mass_score': 0}
            
            qty = p.quantity_kg
            stock_map[key]['qty'] += qty
            stock_map[key]['qty_in'] += qty
            
            # Determine Quality Values (Use Actual for SELL, Min Req for BUY as proxy)
            if p.order_type == 'SELL':
                cal = float(p.caliber) if p.caliber else 0.0
                brix = float(p.soluble_solids) if p.soluble_solids else 0.0
                score = float(p.quality_score) if p.quality_score else 0.0
            else:
                cal = float(p.min_caliber) if p.min_caliber else 0.0
                brix = float(p.min_soluble_solids) if p.min_soluble_solids else 0.0
                score = float(p.min_quality_score) if p.min_quality_score else 0.0
            
            stock_map[key]['mass_cal'] += (cal * float(qty))
            stock_map[key]['mass_brix'] += (brix * float(qty))
            stock_map[key]['mass_score'] += (score * float(qty))

            if p.culture.pk not in name_map:
                name_map[p.culture.pk] = str(p.culture)

        # 2. Subtrair saídas (Stock OUT)
        sales_made = MarketplaceOrder.objects.filter(requester=user, order_type='SELL').exclude(status='CANCELLED')
        purchases_accepted = MarketplaceOrder.objects.filter(fulfilled_by=user, order_type='BUY', status='APPROVED')
        
        for s in chain(sales_made, purchases_accepted):
            key = (s.culture.pk, s.warehouse_location)
            if key in stock_map:
                stock_map[key]['qty'] -= s.quantity_kg

        # Converter para lista para o template
        processor_stock = []
        for (cult_id, warehouse), data in stock_map.items():
            net_qty = data['qty']
            if net_qty > 0.001: # Margin for float errors
                clean_wh = warehouse.split(' (WH:')[0] if warehouse and ' (WH:' in warehouse else warehouse
                
                # Calculate Averages based on INCOMING history
                total_in = data['qty_in']
                avg_cal = (data['mass_cal'] / float(total_in)) if total_in > 0 else 0
                avg_brix = (data['mass_brix'] / float(total_in)) if total_in > 0 else 0
                avg_score = (data['mass_score'] / float(total_in)) if total_in > 0 else 0

                processor_stock.append({
                    'culture_id': cult_id,
                    'culture': name_map.get(cult_id, f"ID: {cult_id}"),
                    'warehouse': clean_wh, 
                    'quantity': float(net_qty),
                    'full_warehouse': warehouse,
                    # Quality Data
                    'avg_caliber': round(avg_cal, 2),
                    'avg_brix': round(avg_brix, 2),
                    'avg_score': round(avg_score, 1)
                })

        context = { 
            'username': user.username, 
            'role': 'Processor',
            'user_profile': user_profile,
            'open_market_orders': open_orders,
            'closed_market_orders': closed_orders,
            'warehouse_form': WarehouseRegistrationForm(),
            'sensor_form': SensorRegistrationForm(),
            'processor_warehouses': Warehouse.objects.filter(owner=user).order_by('-warehouse_id'),
            'market_order_form': MarketplaceOrderForm(initial={'role': 'Processor'}),
            'processor_stock': processor_stock,
            'unprocessed_orders': unprocessed_orders,
            'processing_form': ProcessorProcessingForm(),
        }
        return render(request, 'dashboard/processorDash.html', context)

# Retailer Dashboard
@method_decorator(login_required, name='dispatch')
@method_decorator(role_required(['Retailer']), name='dispatch')
class RetailerDashboardView(View):
    def get(self, request):
        user = request.user
        open_orders = MarketplaceOrder.objects.filter(status='OPEN').select_related('requester', 'culture').order_by('-created_at')
        closed_orders = MarketplaceOrder.objects.filter(Q(requester=user) | Q(fulfilled_by=user), status='APPROVED').select_related('requester', 'culture', 'fulfilled_by').order_by('-fulfilled_at')

        try:
            user_profile = UserProfile.objects.get(user=user)
        except UserProfile.DoesNotExist:
            user_profile = None

        # Calcular Stock Atual do Retailer (Baseado em Compras - Vendas)
        stock_map = {} 
        name_map = {} 
        
        # 1. Somar entradas (Stock IN)
        # a) Pedidos de COMPRA feitos por mim e aprovados E ENTREGUES
        purchases_made = MarketplaceOrder.objects.filter(requester=user, order_type='BUY', status='APPROVED', transport_status='DELIVERED')
        # b) Ofertas de VENDA de outros que eu aceitei (Eu sou o comprador/fulfilled_by) E ENTREGUES
        sales_accepted = MarketplaceOrder.objects.filter(fulfilled_by=user, order_type='SELL', status='APPROVED', transport_status='DELIVERED')
        
        from itertools import chain
        # Structure: key -> {'qty': net_qty, 'qty_in': total_in, 'mass_cal': 0, 'mass_brix': 0, 'mass_score': 0}
        
        for p in chain(purchases_made, sales_accepted):
            key = (p.culture.pk, p.warehouse_location)
            if key not in stock_map:
                stock_map[key] = {'qty': 0, 'qty_in': 0, 'mass_cal': 0, 'mass_brix': 0, 'mass_score': 0}
            
            qty = p.quantity_kg
            stock_map[key]['qty'] += qty
            stock_map[key]['qty_in'] += qty
            
            # Determine Quality Values (Use Actual for SELL, Min Req for BUY as proxy)
            if p.order_type == 'SELL':
                cal = float(p.caliber) if p.caliber else 0.0
                brix = float(p.soluble_solids) if p.soluble_solids else 0.0
                score = float(p.quality_score) if p.quality_score else 0.0
            else:
                cal = float(p.min_caliber) if p.min_caliber else 0.0
                brix = float(p.min_soluble_solids) if p.min_soluble_solids else 0.0
                score = float(p.min_quality_score) if p.min_quality_score else 0.0
            
            stock_map[key]['mass_cal'] += (cal * float(qty))
            stock_map[key]['mass_brix'] += (brix * float(qty))
            stock_map[key]['mass_score'] += (score * float(qty))

            if p.culture.pk not in name_map:
                name_map[p.culture.pk] = str(p.culture)

        # 2. Subtrair saídas (Stock OUT)
        # a) Vendas de volta ao mercado (Ex: Excesso de stock)
        sales_made = MarketplaceOrder.objects.filter(requester=user, order_type='SELL').exclude(status='CANCELLED')
        # b) Compras de Consumidores (Eu sou o vendedor/fulfilled_by)
        purchases_accepted = MarketplaceOrder.objects.filter(fulfilled_by=user, order_type='BUY', status='APPROVED')
        
        for s in chain(sales_made, purchases_accepted):
            key = (s.culture.pk, s.warehouse_location)
            if key in stock_map:
                stock_map[key]['qty'] -= s.quantity_kg

        # Converter para lista para o template
        retailer_stock = []
        for (cult_id, warehouse), data in stock_map.items():
            net_qty = data['qty']
            if net_qty > 0.001: 
                clean_wh = warehouse.split(' (WH:')[0] if warehouse and ' (WH:' in warehouse else warehouse
                
                # Calculate Averages
                total_in = data['qty_in']
                avg_cal = (data['mass_cal'] / float(total_in)) if total_in > 0 else 0
                avg_brix = (data['mass_brix'] / float(total_in)) if total_in > 0 else 0
                avg_score = (data['mass_score'] / float(total_in)) if total_in > 0 else 0

                retailer_stock.append({
                    'culture_id': cult_id,
                    'culture': name_map.get(cult_id, f"ID: {cult_id}"),
                    'warehouse': clean_wh, 
                    'quantity': float(net_qty),
                    'full_warehouse': warehouse,
                    # Quality Data
                    'avg_caliber': round(avg_cal, 2),
                    'avg_brix': round(avg_brix, 2),
                    'avg_score': round(avg_score, 1)
                })

        # Prepare Market Order Form with Warehouse Dropdown
        market_order_form = MarketplaceOrderForm(initial={'role': 'Retailer', 'order_type': 'BUY'})
        retailer_warehouses = Warehouse.objects.filter(owner=user).order_by('warehouse_id')
        
        if retailer_warehouses.exists():
            # Create choices tuple list: (Location Name, Location Name)
            # We use location name as value because the model expects a CharField
            wh_choices = [(w.location, w.location) for w in retailer_warehouses]
            market_order_form.fields['warehouse_location'].widget = forms.Select(choices=wh_choices, attrs={'class': 'form-control'})
        else:
            # Fallback if no warehouses (though retailer should create one)
            market_order_form.fields['warehouse_location'].widget.attrs.update({'placeholder': 'No warehouses found. Please register one.'})


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
            'retailer_stock': retailer_stock, 
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
        
        registered_products = Product.objects.filter(producer=user).order_by('name')
        
        base_plantation_query = PlantationPlan.objects.filter(producer=user).order_by('-plantation_date')
        
        plantation_plans = base_plantation_query.select_related(
            'product'
        ).prefetch_related(
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
        
        # AGGREGATION: Total Kgs per Product (Current Stock)
        harvest_sums = Harvest.objects.filter(producer=user).values(
            'plantation__plantation_name', 
            'subfamily__name',
            'subfamily'
        ).annotate(
        ).annotate(
            total_kg=Sum('harvest_quantity_kg'),
            delivered_kg=Sum('delivered_quantity_kg'),
            utilized_kg=Sum('utilized_quantity_kg')
        ).order_by('plantation__plantation_name', 'subfamily__name')
        
        for item in harvest_sums:
            # Stock disponível = Total - O que já foi vendido/utilizado
            item['current_stock'] = (item['total_kg'] or 0) - (item['utilized_kg'] or 0)

        
        # 4. BUSCAR EVENTOS DO POMAR
        plantation_events = PlantationEvent.objects.filter(plantation__producer=user).select_related('plantation', 'subfamily').order_by('-event_date')
        
        product_subfamilies = ProductSubFamily.objects.all().order_by('fruit_type', 'name')
        
        producer_warehouses = Warehouse.objects.filter(owner=user).order_by('warehouse_id')
        all_sensors = Sensor.objects.all().order_by('sensor_id')

        # 5. MARKETPLACE DATA
        open_market_orders = MarketplaceOrder.objects.filter(status='OPEN').select_related('requester', 'culture').order_by('-created_at')
        closed_market_orders = MarketplaceOrder.objects.filter(Q(requester=user) | Q(fulfilled_by=user), status='APPROVED').select_related('requester', 'culture', 'fulfilled_by').order_by('-fulfilled_at')


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
            'registered_products': registered_products,
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
                request.session['db_error'] = f"Erro ao adicionar cultura: {e}"
            except Exception as e:
                request.session['db_error'] = f"Erro desconhecido: {e}"
        else:
             request.session['db_error'] = f"Formulário de Cultura Inválido: {form.errors}"
             
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
            request.session['db_error'] = db_error # Armazena o erro para mostrar no dashboard
            
        return redirect(reverse('producer_dashboard')) # Garante que o fluxo HTTP termina
        
    return redirect(reverse('producer_dashboard')) # Bloquear acesso GET

@login_required
@role_required(['Producer'])
def producer_submit_harvest(request):
    db_error = None

    if request.method == 'POST':
        form = HarvestForm(request.POST)

        # Filtro de Segurança: Garante que só pode colher os seus planos
        form.fields['plantation'].queryset = PlantationPlan.objects.filter(producer=request.user)

        if form.is_valid():
            try:
                harvest_record = form.save(commit=False)
                harvest_record.producer = request.user
                
                harvest_record.save()
                
                # --- AUTO-GENESIS BLOCK ---
                # Criar o dossier e submeter o Bloco #0 automaticamente
                try:
                    dossier = create_genesis_dossier(harvest_record)
                    data_hash = blockchain_service.generate_dossier_hash(dossier)
                    
                    result = blockchain_service.sign_and_submit_block(
                        user_role='Producer',
                        batch_id=dossier['batch_id'],
                        data_hash=data_hash,
                        event_type='GENESIS'
                    )
                    messages.success(request, f"Colheita registada e Bloco Genesis minado! Hash: {result['tx_hash'][:10]}...")
                except Exception as e:
                    # Se falhar a blockchain, não invalida a colheita, mas avisa
                    messages.warning(request, f"Colheita salva, mas erro ao gerar Bloco Blockchain: {e}")

                return redirect('producer_dashboard')
                
            except IntegrityError as e:
                db_error = f"Erro ao salvar Colheita: Detalhe: {e}"
                request.session['db_error'] = db_error
            except Exception as e:
                db_error = f"Erro desconhecido: {e}"
                request.session['db_error'] = db_error
        
        # Redirecionamento após lógica/erro
        return redirect('producer_dashboard')
        
    return redirect('producer_dashboard')

@login_required
@role_required(['Producer'])
def producer_submit_warehouse(request):
    db_error = None

    if request.method == 'POST':
        # Instanciar o formulário com os dados POST
        form = WarehouseRegistrationForm(request.POST)

        if form.is_valid():
            try:
                # 1. Salva o objeto (sem commit)
                warehouse_record = form.save(commit=False)
                
                # 2. Injeta os dados que não estão no formulário: o Dono/Owner
                warehouse_record.owner = request.user
                
                # 3. Salva na base de dados (guarda os campos que não são ManyToMany)
                warehouse_record.save()
                
                # 4. Salva a relação Many-to-Many para os sensores (APÓS salvar o objeto principal)
                form.save_m2m() 
                
                # Sucesso
                return redirect('producer_dashboard')
                
            except IntegrityError as e:
                db_error = f"Erro ao salvar Armazém na DB: Detalhe: {e}"
                # Pode usar request.session['db_error'] = db_error para mostrar o erro

        # Se houver erro de validação ou DB, redireciona de volta
        return redirect('producer_dashboard')
        
    return redirect('producer_dashboard') # Não permitir GET a esta rota

@login_required
@role_required(['Producer'])
def producer_submit_sensor(request):
    if request.method == 'POST':
        form = SensorRegistrationForm(request.POST)

        if form.is_valid():
            try:
                # O Sensor não precisa de FK para o Produtor (é um item de referência)
                form.save()
                
                # Sucesso: Redireciona para o dashboard principal
                # A próxima seção (JavaScript) irá garantir que o dropdown do Warehouse seja atualizado.
                return redirect('producer_dashboard') 
                
            except IntegrityError as e:
                # Se o sensor_id for uma chave primária e já existir
                db_error = f"Erro ao salvar Sensor na DB: O ID '{request.POST.get('sensor_id')}' já existe. Detalhe: {e}"
                request.session['db_error'] = db_error # Use sessions para passar o erro
        
        # Se houver erro de validação ou DB, redireciona de volta
        return redirect('producer_dashboard')
        
    return redirect('producer_dashboard') # Não permitir GET a esta rota

@login_required
@role_required(['Processor'])
def processor_submit_warehouse(request):
    db_error = None
    if request.method == 'POST':
        form = WarehouseRegistrationForm(request.POST)
        if form.is_valid():
            try:
                warehouse_record = form.save(commit=False)
                warehouse_record.owner = request.user
                warehouse_record.save()
                form.save_m2m() 
                return redirect('processor_dashboard')
            except IntegrityError as e:
                db_error = f"Erro ao salvar Armazém na DB: {e}"
                request.session['db_error'] = db_error

        return redirect('processor_dashboard')
        
    return redirect('processor_dashboard')

@login_required
@role_required(['Processor'])
def processor_submit_sensor(request):
    if request.method == 'POST':
        form = SensorRegistrationForm(request.POST)
        if form.is_valid():
            # Não associamos user diretamente ao sensor, mas ao armazém depois
            # Mas aqui apenas criamos o sensor solto? 
            # O sistema atual parece assumir que sensor é criado e depois ligado ao armazém
            # Mas o form create sensor não liga a armazém.
            # Vamos assumir que é criado com sucesso.
            form.save()
            return redirect('processor_dashboard')
    return redirect('processor_dashboard')

@login_required
@login_required
@role_required(['Processor'])
def processor_submit_processing(request):
    if request.method == 'POST':
        order_id = request.POST.get('order_id')
        order = get_object_or_404(MarketplaceOrder, pk=order_id)
        
        # Verify ownership
        if order.requester != request.user and order.fulfilled_by != request.user:
             return redirect('processor_dashboard')

        form = ProcessorProcessingForm(request.POST, instance=order)
        if form.is_valid():
            processing = form.save(commit=False)
            processing.is_processed = True
            processing.save()
            
            # --- BLOCKCHAIN AGGREGATION LOGIC ---
            try:
                # 1. Definir o Input Batch (Lot de Origem)
                # Alteração para Rastreabilidade Completa:
                # Usamos o ID da ENCOMENDA (ORDER-X) como input.
                # Como a Encomenda tem os blocos de Transporte e o link para a Harvest, 
                # a chain ficará: Transformation -> Delivery -> Pickup -> Harvest
                input_batch_id = f"ORDER-{order.id}"
                
                # 2. Definir o Output Batch (Novo Lote Processado)
                # Ex: PROC-{order_id}-{timestamp}
                new_batch_id = f"LOTE-PROC-{order.id}"
                
                # 3. Preparar Metadados (Inputs)
                inputs = [
                    {
                        "batch_id": input_batch_id, 
                        "quantity_kg": float(order.quantity_kg),
                        "origin_producer": order.fulfilled_by.username if order.fulfilled_by else "N/A"
                    }
                ]
                
                # 4. Dados do Processamento (Payload)
                data_dict = {
                    "product": order.culture.name,
                    "packaging": processing.packaging_type,
                    "treatment": processing.preservation_treatment,
                    "output_quantity": float(order.quantity_kg) # Assumindo 1:1 para simplificação
                }
                
                # 5. Minar o Bloco de Transformação
                data_hash = blockchain_service.generate_dossier_hash(data_dict)
                
                blockchain_service.sign_and_submit_block(
                    user_role='Processor',
                    batch_id=new_batch_id,
                    data_hash=data_hash,
                    event_type='TRANSFORMATION',
                    inputs=inputs # <--- AQUI ESTÁ A AGREGAÇÃO
                )
                
                messages.success(request, f"Processamento registado e Bloco '{new_batch_id}' minado!")
                
            except Exception as e:
                print(f"Erro na Blockchain: {e}")
                messages.warning(request, f"Processado, mas erro na Blockchain: {e}")

            return redirect('processor_dashboard')
    
    return redirect('processor_dashboard')

@login_required
@role_required(['Processor'])
def processor_accept_order(request):
    if request.method == 'POST':
        order_id = request.POST.get('order_id')
        warehouse_id = request.POST.get('warehouse_id')
        
        try:
            # 1. Obter a encomenda
            order = MarketplaceOrder.objects.get(pk=order_id, status='OPEN')
            
            # 2. Obter o armazém selecionado e verificar posse
            warehouse = Warehouse.objects.get(pk=warehouse_id, owner=request.user)
            
            # 3. Atualizar a encomenda
            order.status = 'APPROVED'
            order.fulfilled_by = request.user
            order.fulfilled_at = timezone.now()
            
            # Atualizar localização com base no armazém escolhido
            # Guardamos o ID e Localização para referência futura (ou podíamos criar FK se alterássemos o modelo)
            order.warehouse_location = f"{warehouse.location} (WH: {warehouse.warehouse_id})"
            
            order.save()
            
            return redirect('processor_dashboard')
            
        except (MarketplaceOrder.DoesNotExist, Warehouse.DoesNotExist):
            # Em caso de erro (hack ou dados inválidos), redirecionar
            return redirect('processor_dashboard')
            
    return redirect('processor_dashboard')

# RETAILER VIEWS
@login_required
@role_required(['Retailer'])
def retailer_submit_warehouse(request):
    db_error = None
    if request.method == 'POST':
        form = WarehouseRegistrationForm(request.POST)
        if form.is_valid():
            try:
                warehouse_record = form.save(commit=False)
                warehouse_record.owner = request.user
                warehouse_record.save()
                form.save_m2m() 
                return redirect('retailer_dashboard')
            except IntegrityError as e:
                db_error = f"Erro ao salvar Armazém na DB: {e}"
                request.session['db_error'] = db_error

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
                request.session['db_error'] = db_error
        return redirect('retailer_dashboard')
    return redirect('retailer_dashboard')

@login_required
@role_required(['Retailer'])
def retailer_accept_order(request):
    if request.method == 'POST':
        order_id = request.POST.get('order_id')
        warehouse_id = request.POST.get('warehouse_id')
        
        try:
            order = MarketplaceOrder.objects.get(pk=order_id, status='OPEN')
            warehouse = Warehouse.objects.get(pk=warehouse_id, owner=request.user)
            
            order.status = 'APPROVED'
            order.fulfilled_by = request.user
            order.fulfilled_at = timezone.now()
            order.warehouse_location = f"{warehouse.location} (WH: {warehouse.warehouse_id})"
            
            order.save()
            return redirect('retailer_dashboard')
            
        except (MarketplaceOrder.DoesNotExist, Warehouse.DoesNotExist):
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
            request.session['db_error'] = db_error 
        
        # Se algum formulário for inválido (detail_form ou base_form),
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
            request.session['db_error'] = db_error 
        
        # Redirecionamento após lógica/erro
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
            request.session['db_error'] = db_error 
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
            request.session['db_error'] = db_error 
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
            request.session['db_error'] = db_error 
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
            request.session['db_error'] = db_error 
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
            request.session['db_error'] = db_error 
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
            request.session['db_error'] = db_error 
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
            request.session['db_error'] = db_error 
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
            request.session['db_error'] = db_error 
        return redirect(REDIRECT_URL)

# ----------------------------------------------------------------------
# 5. VIEWS DE MARKETPLACE
# ----------------------------------------------------------------------

@login_required
def market_submit_order(request):
    if request.method == 'POST':
        # VERIFICAR ROLE
        if request.user.groups.filter(name='Producer').exists():
            # lógica para PRODUTOR (Venda com abate de stock)
            form = MarketSellOrderForm(request.POST, user=request.user)
            if form.is_valid():
                with transaction.atomic():
                    order = form.save(commit=False)
                    order.requester = request.user
                    order.role = 'Producer'
                    order.status = 'OPEN'

                    # AUTOMATIZAÇÃO DE ARMAZÉM:
                    # Se tiver origem numa Colheita, usamos o armazém dessa colheita como local de recolha.
                    if order.harvest_origin and order.harvest_origin.warehouse:
                        order.warehouse_location = order.harvest_origin.warehouse.location
                    
                    order.save()
                    
                    # Abater Stock ao Lote Selecionado
                    harvest = order.harvest_origin
                    # (A validação de stock > disponível já foi feita no form.clean)
                    harvest.utilized_quantity_kg += order.quantity_kg
                    harvest.save()
                    
                    order.save()
                    messages.success(request, f"Oferta de Venda criada! {order.quantity_kg}kg abatidos ao lote #{harvest.pk}.")
                    return redirect(request.META.get('HTTP_REFERER', 'producer_dashboard'))
            else:
                 messages.error(request, f"Erro ao criar oferta: {form.errors}")
        
        else:
            # Lógica Genérica (Retalhista a comprar, etc.)
            form = MarketplaceOrderForm(request.POST)
            if form.is_valid():
                order = form.save(commit=False)
                order.requester = request.user
                
                groups = request.user.groups.all()
                user_role = groups[0].name if groups else 'Unknown'
                order.role = user_role
                
                # Logic for Processor/Retailer SELL Orders (Export/Sales):
                # The form uses min_caliber/etc for input, but for SELL orders these are ACTUAL values.
                if order.order_type == 'SELL':
                    order.caliber = order.min_caliber
                    order.soluble_solids = order.min_soluble_solids
                    order.quality_score = order.min_quality_score
                    # Clear "Min" fields as they don't apply to specific items being sold
                    order.min_caliber = None
                    order.min_soluble_solids = None
                    order.min_quality_score = None
                
                order.save()
                messages.success(request, "Pedido criado no Mercado!")
                return redirect(request.META.get('HTTP_REFERER', 'producer_dashboard'))
            else:
                messages.error(request, f"Erro ao criar pedido: {form.errors}")
    
    return redirect(request.META.get('HTTP_REFERER', 'producer_dashboard'))

@login_required
def market_accept_order(request):
    if request.method == 'POST':
        order_id = request.POST.get('order_id')
        harvest_id = request.POST.get('harvest_id') # NEW: ID do Lote selecionado no Modal
        
        order = get_object_or_404(MarketplaceOrder, pk=order_id)
        
        if order.status == 'OPEN':
            # Validação Extra: Se for Producer aceitando uma compra (BUY), DEVE ter um harvest_id
            if request.user.groups.filter(name='Producer').exists() and order.order_type == 'BUY':
                if not harvest_id:
                     messages.error(request, "Erro: Tens de selecionar um Lote (Harvest) para abastecer este pedido!")
                     return redirect(request.META.get('HTTP_REFERER', 'producer_dashboard'))
                
                # Obter Lote e Validar Stock
                harvest = get_object_or_404(Harvest, pk=harvest_id, producer=request.user)
                if harvest.current_stock_kg < order.quantity_kg:
                    messages.error(request, f"Stock insuficiente no Lote #{harvest.pk}. Disponível: {harvest.current_stock_kg}kg")
                    return redirect(request.META.get('HTTP_REFERER', 'producer_dashboard'))

                # Lógica de Dedução e Link
                with transaction.atomic():
                    # 1. Atualizar Order
                    order.status = 'APPROVED'
                    order.fulfilled_by = request.user
                    order.fulfilled_at = timezone.now()
                    
                    # LINK CRÍTICO: Associar a origem
                    order.harvest_origin = harvest
                    # Herdar warehouse do lote
                    if harvest.warehouse:
                         order.warehouse_location = harvest.warehouse.location
                    
                    # 2. Atualizar Stock do Lote
                    harvest.utilized_quantity_kg += order.quantity_kg
                    harvest.save()
                    order.save()
                    
                    messages.success(request, f"Pedido aceite! {order.quantity_kg}kg alocados do Lote #{harvest.pk}.")
            
            else:
                # Fallback para outros roles ou SELL orders (onde stock já foi abatido na criação)
                order.status = 'APPROVED'
                order.fulfilled_by = request.user
                order.fulfilled_at = timezone.now()
                order.save()
                messages.success(request, f"Pedido #{order.pk} aceite!")
            
    return redirect(request.META.get('HTTP_REFERER', 'producer_dashboard'))

# ----------------------------------------------------------------------
# 6. VIEWS DE LOGÍSTICA (TRANSPORTER)
# ----------------------------------------------------------------------

@login_required
@role_required(['Transporter'])
def transporter_accept_job(request):
    """
    Passo 1: Aceitar o trabalho (Move de 'PENDING' para 'ACCEPTED').
    Significa "Eu vou transportar isto!".
    """
    if request.method == "POST":
        order_id = request.POST.get('order_id')
        order = get_object_or_404(MarketplaceOrder, pk=order_id)
        
        # Só aceitar se estiver livre (PENDING)
        if order.transport_status == 'PENDING':
            order.transport_status = 'ACCEPTED'
            # Aqui poderiamos guardar order.transport_fulfilled_by = request.user se tivessemos o campo
            order.save()
            messages.success(request, f"Trabalho aceite! Encomenda #{order.pk} movida para Planeamento.")
        else:
            messages.error(request, "Esta encomenda já não está disponível.")
            
    return redirect('transporter_dashboard')

@login_required
@role_required(['Transporter'])
def transporter_submit_plan(request):
    if request.method == "POST":
        order_id = request.POST.get('order_id')
        order = get_object_or_404(MarketplaceOrder, pk=order_id)
        
        form = TransportPlanForm(request.POST, instance=order)
        if form.is_valid():
            order.transport_status = 'PLANNED'
            form.save()
            messages.success(request, f"Plano de transporte registado para Encomenda #{order.pk}!")
        else:
            messages.error(request, "Erro ao registar plano. Verifique as datas.")
            
    return redirect('transporter_dashboard')

@login_required
@role_required(['Transporter'])
def transporter_validate_pickup(request):
    if request.method == "POST":
        order_id = request.POST.get('order_id')
        order = get_object_or_404(MarketplaceOrder, pk=order_id)
        
        # 1. Atualizar BD
        order.actual_pickup_date = timezone.now()
        order.transport_status = 'IN_TRANSIT'
        order.save()
        
        # 2. Blockchain Event (Proof of Custody)
        # Assumindo que o Produtor já criou o batch (se não, criamos um novo ORDER-ID)
        dossier = {
            "action": "TRANSPORT_PICKUP",
            "order_id": order.pk,
            "transporter": request.user.username,
            "pickup_time": order.actual_pickup_date.isoformat(),
            "origin": order.warehouse_location,
            "planned_pickup": order.planned_pickup_date.isoformat() if order.planned_pickup_date else "N/A",
            # LINK CRÍTICO PARA RASTREABILIDADE TOTAL:
            "harvest_origin": order.harvest_origin.pk if order.harvest_origin else "N/A"
        }
        
        data_hash = blockchain_service.generate_dossier_hash(dossier)
        
        blockchain_service.sign_and_submit_block(
            user_role='Transporter',
            batch_id=f"ORDER-{order.pk}",
            data_hash=data_hash,
            event_type='TRANSPORT_PICKUP'
        )
        
        messages.success(request, f"Carga validada! Bloco de Custódia gerado para Encomenda #{order.pk}.")
        
    return redirect('transporter_dashboard')

@login_required
@role_required(['Transporter'])
def transporter_submit_delivery(request):
    if request.method == "POST":
        order_id = request.POST.get('order_id')
        order = get_object_or_404(MarketplaceOrder, pk=order_id)
        
        form = TransportDeliveryForm(request.POST, instance=order)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # 1. Atualizar BD (Order)
                    order.actual_delivery_date = timezone.now()
                    order.transport_status = 'DELIVERED'
                    order.save()
                    
                    # 2. Salvar dados do form (Sensores)
                    # Nota: Como o form é um ModelForm, save() salva o order, 
                    # mas precisamos garantir que os campos acima persistam.
                    # O form.save() vai sobrepor se o form tiver esses campos, 
                    # mas o TransportDeliveryForm só tem o sensor_data.
                    form.save() 

                    # 3. Atualizar Stock de "Delivered" no Lote de Origem (Harvest)
                    if order.harvest_origin:
                        harvest = order.harvest_origin
                        # Incrementa o delivered com a quantidade desta entrega
                        # Isto garante que a tabela "Stock Status" do Produtor 
                        # reflita que esta quantidade saiu fisicamente.
                        harvest.delivered_quantity_kg = (harvest.delivered_quantity_kg or 0) + order.quantity_kg
                        harvest.save()
            except Exception as e:
                messages.error(request, f"Erro ao processar entrega: {e}")
                return redirect('transporter_dashboard')
            
            # 2. Blockchain Event (Proof of Delivery + Sensors)
            dossier = {
                "action": "TRANSPORT_DELIVERY",
                "order_id": order.pk,
                "transporter": request.user.username,
                "delivery_time": order.actual_delivery_date.isoformat(),
                "sensor_data": order.transport_sensor_data or "No Data",
                # LINK CRÍTICO (REFORÇO NA ENTREGA)
                "harvest_origin": order.harvest_origin.pk if order.harvest_origin else "N/A"
            }
            
            data_hash = blockchain_service.generate_dossier_hash(dossier)
            
            try:
                result = blockchain_service.sign_and_submit_block(
                    user_role='Transporter',
                    batch_id=f"ORDER-{order.pk}",
                    data_hash=data_hash,
                    event_type='TRANSPORT_DELIVERY'
                )
                messages.success(request, f"Entrega registada com sucesso! Bloco Final gerado. Hash: {result['tx_hash'][:10]}...")
            except Exception as e:
                messages.error(request, f"Erro Blockchain: {e}")
        else:
            messages.error(request, "Erro ao registar entrega.")
            
    return redirect('transporter_dashboard')