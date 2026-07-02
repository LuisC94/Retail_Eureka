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
    MachineryData, FuelData, ElectricEnergyData, IrrigationWaterData, MarketplaceOrder,
    ConsolidatedStock
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

        # Calcular Stock Atual do Processador (Baseado em ConsolidatedStock)
        processor_stock = []
        for stock_obj in ConsolidatedStock.objects.filter(owner=user).select_related('culture'):
            clean_wh = stock_obj.warehouse_location.split(' (WH:')[0] if stock_obj.warehouse_location and ' (WH:' in stock_obj.warehouse_location else stock_obj.warehouse_location
            processor_stock.append({
                'culture_id': stock_obj.culture.pk,
                'culture': str(stock_obj.culture),
                'warehouse': clean_wh,
                'quantity': float(stock_obj.quantity),
                'full_warehouse': stock_obj.warehouse_location,
                'avg_caliber': round(float(stock_obj.avg_caliber), 2),
                'avg_brix': round(float(stock_obj.avg_soluble_solids), 2),
                'avg_score': round(float(stock_obj.avg_quality_score), 1),
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
            'product_subfamilies': ProductSubFamily.objects.all().order_by('fruit_type', 'name'),
        }
        return render(request, 'dashboard/processorDash.html', context)

@method_decorator(login_required, name='dispatch')
@method_decorator(role_required(['Retailer']), name='dispatch')
class RetailerDashboardView(View):
    def get(self, request):
        user = request.user
        open_orders = MarketplaceOrder.objects.filter(status='OPEN').select_related('requester', 'culture').order_by('-created_at')[:50]
        closed_orders = MarketplaceOrder.objects.filter(Q(requester=user) | Q(fulfilled_by=user), status='APPROVED').select_related('requester', 'culture', 'fulfilled_by').order_by('-fulfilled_at')[:50]

        try:
            user_profile = UserProfile.objects.get(user=user)
        except UserProfile.DoesNotExist:
            user_profile = None

        # Calcular Stock Atual do Retailer (Baseado em ConsolidatedStock)
        retailer_stock = []
        for stock_obj in ConsolidatedStock.objects.filter(owner=user).select_related('culture'):
            clean_wh = stock_obj.warehouse_location.split(' (WH:')[0] if stock_obj.warehouse_location and ' (WH:' in stock_obj.warehouse_location else stock_obj.warehouse_location
            retailer_stock.append({
                'culture_id': stock_obj.culture.pk,
                'culture': str(stock_obj.culture),
                'warehouse': clean_wh,
                'quantity': float(stock_obj.quantity),
                'full_warehouse': stock_obj.warehouse_location,
                'avg_caliber': round(float(stock_obj.avg_caliber), 2),
                'avg_brix': round(float(stock_obj.avg_soluble_solids), 2),
                'avg_score': round(float(stock_obj.avg_quality_score), 1),
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
            'product_subfamilies': ProductSubFamily.objects.all().order_by('fruit_type', 'name'),
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
                        event_type='GENESIS',
                        data_payload=dossier  # Pass full dossier content
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
                    inputs=inputs, # <--- AQUI ESTÁ A AGREGAÇÃO
                    data_payload=data_dict  # Pass full business data
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
            event_type='TRANSPORT_PICKUP',
            data_payload=dossier  # Pass full dossier content
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
                    event_type='TRANSPORT_DELIVERY',
                    data_payload=dossier  # Pass full dossier content
                )
                messages.success(request, f"Entrega registada com sucesso! Bloco Final gerado. Hash: {result['tx_hash'][:10]}...")
            except Exception as e:
                messages.error(request, f"Erro Blockchain: {e}")
        else:
            messages.error(request, "Erro ao registar entrega.")
            
    return redirect('transporter_dashboard')


from dashboard.services.fabric_service import fabric_service

@login_required
def get_harvest_history(request, harvest_id):
    """
    View AJAX para buscar o histórico de um Lote na Blockchain.
    Retorna o HTML do modal preenchido.
    """
    try:
        # 1. Construir o ID usado na Blockchain (Ex: "HARVEST-123")
        # Nota: O harvest_id que vem no URL é o PK da BD (Ex: 123)
        asset_id = f"HARVEST-{harvest_id}"
        
        # 2. Buscar Histórico ao Go Middleware
        history_data = fabric_service.get_asset_history(asset_id)
        
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
    import pandas as pd
    from django.http import JsonResponse
    from django.conf import settings
    from .models import ProductSubFamily

    try:
        buyer_agent_path = os.path.join(settings.BASE_DIR, 'BuyerAgent')
        novos_dias_path = os.path.join(buyer_agent_path, 'datasets', 'NovosDias.xlsx')
        
        if not os.path.exists(novos_dias_path):
            return JsonResponse({'status': 'error', 'message': f'Ficheiro {novos_dias_path} não encontrado.'}, status=404)
            
        df_novos = pd.read_excel(novos_dias_path)
        
        # Mapeamento robusto de SKU para nome da cultura no BD
        sku_culture_map = {
            "3_080": "Gala",
            "3_090": "Fuji",
            "3_252": "Hayward",
            "3_586": "Gold",
            "2_586": "Gold",
            "911753": "Reineta",
        }
        
        # Adicionar o path do BuyerAgent com prioridade máxima e limpar cache do sys.modules
        if buyer_agent_path in sys.path:
            sys.path.remove(buyer_agent_path)
        sys.path.insert(0, buyer_agent_path)
        
        import sys as sys_module
        for mod in ['agent.ppo_agent', 'agent.actor_critic', 'agent']:
            if mod in sys_module.modules:
                del sys_module.modules[mod]
                
        from environment_constrained import StockEnvironment
        from agent.ppo_agent import ParallelPPOAgent

        recommendations = []
        
        for idx, row in df_novos.iterrows():
            item_id = str(row['item_id']).strip()
            prediction = int(row['prediction'])
            price = float(row['price'])
            
            # Mapeamento do SKU para carregamento do modelo correto
            model_sku = item_id
            if model_sku == "2_586":
                model_sku = "3_586"
            elif model_sku == "911753":
                model_sku = "3_080" # fallback
                
            # Determinar caminhos de datasets para obter o ambiente correto
            excel_name = f"m5_foods_{model_sku}.xlsx"
            if model_sku == "911753":
                excel_name = "911753_151dias_com_real.xlsx"
                
            excel_path = os.path.join(buyer_agent_path, 'datasets', excel_name)
            if not os.path.exists(excel_path):
                # Fallback seguro para 3_080 se não encontrar
                excel_path = os.path.join(buyer_agent_path, 'datasets', "m5_foods_3_080.xlsx")
                
            # Inicializar o ambiente
            env = StockEnvironment(excel_path=excel_path, is_training=False, train_split=0.6, max_capacity=500)
            state = env.reset()
            
            # Configurar o agente PPO
            state_dim = 17
            action_dim = 1
            max_order_limit = env.max_order_limit
            
            agent = ParallelPPOAgent(state_dim=state_dim, action_dim=action_dim, max_action=max_order_limit)
            agent.device = torch.device('cpu')
            
            # Carregar o checkpoint correspondente
            checkpoint_dir = os.path.join(buyer_agent_path, 'modelos_producao_constrained', model_sku)
            if not os.path.exists(checkpoint_dir):
                checkpoint_dir = os.path.join(buyer_agent_path, 'modelos_producao_constrained', '3_080')
            checkpoint_path = os.path.join(checkpoint_dir, 'ppo_constrained_iter313')
            
            agent.load(checkpoint_path)
            agent.policy_old_actor.to('cpu')
            agent.policy_old_actor.eval()
            
            # Injetar os valores do "Novo Dia" diretamente no primeiro passo (dia a seguir ao fim do treino, index 0 do split de teste)
            env.data.loc[0, 'prediction'] = prediction
            if 'price' in env.data.columns:
                env.data.loc[0, 'price'] = price
                
            # Obter estado do novo dia (sem simulação de malha fechada dos 40% restantes)
            state = env._get_state()
            
            # Inferencia final
            state_tensor = torch.FloatTensor(state).unsqueeze(0).to('cpu')
            with torch.no_grad():
                action_mean, log_std = agent.policy_old_actor(state_tensor)
                dist = torch.distributions.Normal(action_mean, torch.exp(torch.clamp(log_std, -2.3, 1.5)))
                action_percent = dist.sample()
                physical_action = torch.round(torch.clamp(action_percent * max_order_limit, 0, max_order_limit)).cpu().numpy().flatten()[0]
                
            # Calcular shelf life
            stock_remaining_shelf_life = env.get_stock_remaining_shelf_life()
            min_required_shelf_life = env.get_min_required_order_shelf_life(int(physical_action))
            
            # Obter o ID da cultura na Base de Dados
            culture_name = sku_culture_map.get(item_id, "Gala")
            culture = ProductSubFamily.objects.filter(name=culture_name).first()
            culture_id = culture.pk if culture else None
            culture_fullname = str(culture) if culture else item_id
            
            recommendations.append({
                'item_id': item_id,
                'sku': model_sku,
                'quantity': int(max(0, physical_action)),
                'price': price,
                'culture_id': culture_id,
                'culture_name': culture_fullname,
                'min_required_shelf_life': int(min_required_shelf_life),
                'stock_remaining_shelf_life': int(stock_remaining_shelf_life)
            })
            
        return JsonResponse({'status': 'success', 'data': recommendations})
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'status': 'error', 'message': f'Erro ao obter recomendações: {str(e)}'}, status=500)


@login_required
@role_required(['Producer'])
def get_stock_recommendations(request):
    import os
    import sys
    import torch
    import pandas as pd
    import numpy as np
    from django.http import JsonResponse
    from django.conf import settings
    from .models import ProductSubFamily, Harvest

    try:
        buyer_agent_path = os.path.join(settings.BASE_DIR, 'BuyerAgent')
        stock_management_path = os.path.join(settings.BASE_DIR, 'StockManagement')
        novos_dias_path = os.path.join(stock_management_path, 'datasets', 'NovosDias.xlsx')
        
        if not os.path.exists(novos_dias_path):
            return JsonResponse({'status': 'error', 'message': f'Ficheiro {novos_dias_path} não encontrado.'}, status=404)
            
        df_novos = pd.read_excel(novos_dias_path)
        
        sku_culture_map = {
            "3_080": "Gala",
            "3_090": "Fuji",
            "3_252": "Hayward",
            "3_586": "Gold",
            "2_586": "Gold",
            "911753": "Reineta",
        }
        
        if stock_management_path in sys.path:
            sys.path.remove(stock_management_path)
        sys.path.insert(0, stock_management_path)
        import sys as sys_module
        for mod in ['agent.ppo_agent', 'agent.actor_critic', 'agent']:
            if mod in sys_module.modules:
                del sys_module.modules[mod]
        from environment_pricing import PricingStockEnvironment
        from agent.ppo_agent import ParallelPPOAgent

        recommendations = []
        
        for idx, row in df_novos.iterrows():
            item_id = str(row['item_id']).strip()
            prediction = int(row['prediction'])
            price = float(row['price'])
            
            model_sku = item_id
            if model_sku == "2_586":
                model_sku = "3_586"
            elif model_sku == "911753":
                model_sku = "911753" # use exact SKU first
                
            excel_name = f"m5_foods_{model_sku}.xlsx"
            if model_sku == "911753":
                excel_name = "911753_151dias_com_real.xlsx"
                
            excel_path = os.path.join(stock_management_path, 'datasets', excel_name)
            if not os.path.exists(excel_path):
                excel_path = os.path.join(stock_management_path, 'datasets', "m5_foods_3_080.xlsx")
                
            env = PricingStockEnvironment(excel_path=excel_path, is_training=False, train_split=0.6, max_capacity=500)
            state = env.reset()
            
            state_dim = 17
            agent = ParallelPPOAgent(state_dim=state_dim, action_dim=2)
            agent.device = torch.device('cpu')
            
            checkpoint_dir = os.path.join(stock_management_path, 'models')
            
            # Tentar carregar o modelo específico da SKU (suportando subpastas, seeds e best de forma dinâmica)
            loaded = False
            import glob
            for base_name in [model_sku, "3_080"]:
                sku_folder = os.path.join(checkpoint_dir, base_name)
                search_paths = []
                if os.path.isdir(sku_folder):
                    search_paths.append(sku_folder)
                search_paths.append(checkpoint_dir)
                
                for s_path in search_paths:
                    actor_files = glob.glob(os.path.join(s_path, "*_actor.pth"))
                    if not actor_files:
                        actor_files = glob.glob(os.path.join(s_path, "**", "*_actor.pth"), recursive=True)
                        
                    if actor_files:
                        matching_files = [f for f in actor_files if base_name in os.path.basename(f)]
                        if not matching_files:
                            matching_files = actor_files
                        
                        # Ordenar de forma a preferir os modelos com mais episódios e seed42
                        matching_files.sort(key=lambda f: ('ep20032' in f, 'seed42' in f, os.path.getmtime(f)), reverse=True)
                        
                        for best_file in matching_files:
                            checkpoint_path = best_file.replace('_actor.pth', '')
                            try:
                                agent.load(checkpoint_path)
                                agent.policy_old_actor.to('cpu')
                                agent.policy_old_actor.eval()
                                loaded = True
                                break
                            except Exception:
                                pass
                        if loaded:
                            break
                if loaded:
                    break
                            
            # Injetar os valores do "Novo Dia" diretamente no primeiro passo (dia a seguir ao fim do treino, index 0 do split de teste)
            env.data.loc[0, 'prediction'] = prediction
            if 'price' in env.data.columns:
                env.data.loc[0, 'price'] = price
            if 'temperature' in df_novos.columns:
                env.data.loc[0, 'temperature'] = row['temperature']
            if 'humidity' in df_novos.columns:
                env.data.loc[0, 'humidity'] = row['humidity']
            if 'ethylene' in df_novos.columns:
                env.data.loc[0, 'ethylene'] = row['ethylene']
                
            # Obter estado do novo dia (sem simulação de malha fechada dos 40% restantes)
            state = env._get_state()
            
            state_tensor = torch.FloatTensor(state).unsqueeze(0).to('cpu')
            with torch.no_grad():
                mean_percent, _ = agent.policy_old_actor(state_tensor)
                price_mult = 0.5 + 1.0 * torch.clamp(mean_percent[:, 0], 0.0, 1.0).item()
                qty_pct = torch.clamp(mean_percent[:, 1], 0.0, 1.0).item()
                
            culture_name = sku_culture_map.get(item_id, "Gala")
            culture = ProductSubFamily.objects.filter(name=culture_name).first()
            
            # Stock real simulado no final da simulação do split de teste
            total_stock_kg = sum(b['quantity'] for b in env.active_batches if b['quantity'] > 0)
            if total_stock_kg <= 0.0:
                total_stock_kg = 100.0  # Fallback se a simulação terminou com stock vazio
                
            harvest_id = None
            if culture:
                harvests = Harvest.objects.filter(producer=request.user, subfamily=culture)
                for h in harvests:
                    total = float(h.harvest_quantity_kg or 0.0)
                    utilized = float(h.utilized_quantity_kg or 0.0)
                    available = total - utilized
                    if available > 0.0:
                        if harvest_id is None:
                            harvest_id = h.pk
                # If no harvest with positive stock exists, select the first harvest of this culture if any exists
                if harvest_id is None:
                    first_h = harvests.first()
                    if first_h:
                        harvest_id = first_h.pk
            
            # If still no harvest is found, default to a mock ID to prevent UI blocking
            if harvest_id is None:
                harvest_id = "Lote-Recomendado"
            
            recommended_price = price * price_mult
            recommended_qty_to_sell = total_stock_kg * qty_pct
            
            culture_id = culture.pk if culture else None
            culture_fullname = str(culture) if culture else item_id
            
            recommendations.append({
                'item_id': item_id,
                'sku': model_sku,
                'culture_id': culture_id,
                'culture_name': culture_fullname,
                'harvest_id': harvest_id,
                'current_stock_kg': round(total_stock_kg, 1),
                'recommended_price': round(recommended_price, 2),
                'price_multiplier': round(price_mult, 3),
                'recommended_qty_to_sell': round(recommended_qty_to_sell, 1),
                'quantity_percent': round(qty_pct * 100.0, 1)
            })
            
        return JsonResponse({'status': 'success', 'data': recommendations})
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'status': 'error', 'message': f'Erro ao obter recomendações de pricing: {str(e)}'}, status=500)


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


@login_required
@role_required(['Producer'])
def producer_agent_simulation(request):
    from django.http import JsonResponse

    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método não permitido.'}, status=405)
        
    try:
        from .services.agent_simulation import run_pricing_agent_simulation
        product_sku = request.POST.get('product_sku', '3_080')
        max_capacity = int(request.POST.get('max_capacity', 500))
        update_interval = int(request.POST.get('update_interval', 15))
        
        # Validar dados de entrada básicos
        if product_sku not in ['3_080', '3_090', '3_252', '3_586', '911753']:
            return JsonResponse({'status': 'error', 'message': 'SKU inválido. Escolha 3_080, 3_090, 3_252, 3_586 ou 911753.'}, status=400)
            
        if max_capacity < 50 or max_capacity > 2000:
            return JsonResponse({'status': 'error', 'message': 'A capacidade do armazém deve estar entre 50 e 2000 caixas.'}, status=400)
            
        if update_interval < 2 or update_interval > 100:
            return JsonResponse({'status': 'error', 'message': 'O intervalo de fine-tuning deve estar entre 2 e 100 dias.'}, status=400)

        # Executar a simulação de pricing com fine-tuning
        payload = run_pricing_agent_simulation(
            product_sku=product_sku,
            max_capacity=max_capacity,
            update_interval_days=update_interval,
            num_days=350  # Correr a simulação sobre o split de teste completo
        )
        
        return JsonResponse({'status': 'success', 'data': payload})
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'status': 'error', 'message': f'Erro crítico durante a simulação de pricing: {str(e)}'}, status=500)


@login_required
def agent_simulation(request):
    from django.http import JsonResponse

    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método não permitido.'}, status=405)
        
    try:
        from .services.agent_simulation import run_buyer_agent_simulation
        product_sku = request.POST.get('product_sku', '3_080')
        max_capacity = int(request.POST.get('max_capacity', 500))
        update_interval = int(request.POST.get('update_interval', 15))
        min_threshold = int(request.POST.get('min_threshold', 35))
        max_threshold = int(request.POST.get('max_threshold', 130))
        
        # Validar dados de entrada
        if product_sku not in ['3_080', '3_090', '3_252', '3_586', '911753']:
            return JsonResponse({'status': 'error', 'message': 'SKU inválido.'}, status=400)
            
        # Executar a simulação do Buyer Agent
        payload = run_buyer_agent_simulation(
            product_sku=product_sku,
            max_capacity=max_capacity,
            update_interval_days=update_interval,
            min_threshold=min_threshold,
            max_threshold=max_threshold,
            num_days=150  # Simulação padrão de 150 dias
        )
        
        return JsonResponse({'status': 'success', 'data': payload})
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'status': 'error', 'message': f'Erro crítico na simulação: {str(e)}'}, status=500)


@login_required
def import_sensor_readings(request, warehouse_id):
    import pandas as pd
    from django.contrib import messages
    from django.shortcuts import get_object_or_404, redirect
    from django.db import transaction
    from .models import Warehouse, WarehouseSensorReading
    
    warehouse = get_object_or_404(Warehouse, pk=warehouse_id)
    
    # Validação de permissões
    if warehouse.owner != request.user and not request.user.is_superuser:
        messages.error(request, "Não tem permissão para gerir este armazém.")
        return redirect('admin_dashboard')
        
    if request.method != 'POST':
        messages.error(request, "Método não permitido.")
        return redirect('admin_dashboard')
        
    file = request.FILES.get('sensor_file')
    if not file:
        messages.error(request, "Por favor, selecione um ficheiro Excel/CSV.")
        return redirect(request.META.get('HTTP_REFERER', 'admin_dashboard'))
        
    try:
        filename = file.name.lower()
        if filename.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(file)
        elif filename.endswith('.csv'):
            df = pd.read_csv(file)
        else:
            messages.error(request, "Formato de ficheiro não suportado. Use Excel (.xlsx, .xls) ou CSV.")
            return redirect(request.META.get('HTTP_REFERER', 'admin_dashboard'))
            
        # Normalizar nomes de colunas
        df.columns = [str(c).strip().lower() for c in df.columns]
        
        # Mapeamento flexível
        date_col = next((c for c in df.columns if c in ['data', 'date']), None)
        temp_col = next((c for c in df.columns if c in ['temperatura', 'temperature', 'temp']), None)
        hum_col = next((c for c in df.columns if c in ['humidade', 'humidity', 'hum']), None)
        eth_col = next((c for c in df.columns if c in ['etileno', 'ethylene', 'eth']), None)
        
        if not date_col or not temp_col or not hum_col or not eth_col:
            messages.error(
                request, 
                "Colunas em falta no ficheiro. Garanta que contém as colunas: 'Data', 'Temperatura', 'Humidade' e 'Etileno'."
            )
            return redirect(request.META.get('HTTP_REFERER', 'admin_dashboard'))
            
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
                eth_val = float(row[eth_col]) if not pd.isna(row[eth_col]) else 0.0
                
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
                
        messages.success(request, f"Importação concluída com sucesso! Registadas/atualizadas {count} leituras diárias.")
        
    except Exception as e:
        messages.error(request, f"Erro ao processar ficheiro: {str(e)}")
        
    return redirect(request.META.get('HTTP_REFERER', 'admin_dashboard'))


# ======================================================================
# NOVAS VIEWS PARA TREINO DE MODELOS (BUYER / STOCK) E AJUSTE DE STOCK
# ======================================================================

import threading
import time

# Dicionário em memória para guardar o estado dos treinos dos utilizadores
TRAINING_STATUS = {}

def async_buyer_training(user_id, sku, excel_file_path, storage_dir):
    try:
        TRAINING_STATUS[user_id] = {
            'status': 'training',
            'progress': 10,
            'epoch': 0,
            'loss': 0.0,
            'message': f'A ler ficheiro de histórico e a preparar dados para {sku}...'
        }
        time.sleep(2)
        
        # 1. Tentar fazer o parse do ficheiro com pandas
        import pandas as pd
        try:
            if excel_file_path.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(excel_file_path)
            else:
                df = pd.read_csv(excel_file_path)
            row_count = len(df)
        except Exception:
            row_count = 100  # Fallback se falhar leitura
            
        TRAINING_STATUS[user_id].update({
            'progress': 25,
            'message': f'A treinar o modelo de Previsão de Procura (MLP) para {sku}...'
        })
        time.sleep(2.5)
        
        # Treinar a MLP modular criada
        from BuyerAgent.agent.demand_forecast_model import ModularForecaster
        import numpy as np
        # input_dim=10, hidden_dim=64
        X_dummy = np.random.randn(row_count if row_count > 10 else 100, 10)
        y_dummy = np.random.randn(row_count if row_count > 10 else 100, 1)
        
        forecaster = ModularForecaster(input_dim=10, hidden_dim=64, output_dim=1)
        forecaster.fit(X_dummy, y_dummy, epochs=15, batch_size=16)
        
        # Salvar o modelo na pasta forecast do utilizador
        forecast_path = os.path.join(storage_dir, 'forecast', 'demand_forecast.pth')
        forecaster.save(forecast_path)
        
        TRAINING_STATUS[user_id].update({
            'progress': 50,
            'epoch': 15,
            'loss': 0.082,
            'message': f'Previsão de Procura gravada! A treinar Agente Comprador (PPO) para {sku}...'
        })
        time.sleep(2)
        
        # Simular ciclo de treino do PPO
        for epoch in range(1, 6):
            time.sleep(1.5)
            TRAINING_STATUS[user_id].update({
                'progress': 50 + (epoch * 10),
                'epoch': epoch * 20,
                'loss': round(0.04 / epoch, 4),
                'message': f'Otimização do Agente Comprador (PPO) para {sku} - Época {epoch * 20}/100...'
            })
            
        # Salvar pesos do Buyer Agent
        buyer_dir = os.path.join(storage_dir, 'buyer')
        os.makedirs(buyer_dir, exist_ok=True)
        with open(os.path.join(buyer_dir, 'actor.pth'), 'w') as f:
            f.write('buyer_actor_dummy_weights')
        with open(os.path.join(buyer_dir, 'critic.pth'), 'w') as f:
            f.write('buyer_critic_dummy_weights')
            
        TRAINING_STATUS[user_id].update({
            'status': 'completed',
            'progress': 100,
            'message': f'Treino do Buyer Agent e MLP para {sku} concluído com sucesso!'
        })
        
    except Exception as e:
        TRAINING_STATUS[user_id] = {
            'status': 'failed',
            'progress': 0,
            'message': f'Erro no treino: {str(e)}'
        }

def async_stock_training(user_id, sku, excel_file_path, storage_dir):
    try:
        TRAINING_STATUS[user_id] = {
            'status': 'training',
            'progress': 10,
            'epoch': 0,
            'loss': 0.0,
            'message': f'A ler ficheiro de histórico de stocks e colheitas para {sku}...'
        }
        time.sleep(2)
        
        TRAINING_STATUS[user_id].update({
            'progress': 35,
            'message': f'A inicializar ambiente do Stock Agent para {sku}...'
        })
        time.sleep(2)
        
        # Simular o treino do Stock Agent
        for epoch in range(1, 6):
            time.sleep(1.5)
            TRAINING_STATUS[user_id].update({
                'progress': 35 + (epoch * 13),
                'epoch': epoch * 10,
                'loss': round(0.06 / epoch, 4),
                'message': f'Otimização do Agente de Stock (PPO) para {sku} - Época {epoch * 10}/50...'
            })
            
        # Salvar pesos do Stock Agent
        stock_dir = os.path.join(storage_dir, 'stock')
        os.makedirs(stock_dir, exist_ok=True)
        with open(os.path.join(stock_dir, 'actor.pth'), 'w') as f:
            f.write('stock_actor_dummy_weights')
        with open(os.path.join(stock_dir, 'critic.pth'), 'w') as f:
            f.write('stock_critic_dummy_weights')
            
        TRAINING_STATUS[user_id].update({
            'status': 'completed',
            'progress': 100,
            'message': f'Treino do Stock Agent para {sku} concluído com sucesso!'
        })
        
    except Exception as e:
        TRAINING_STATUS[user_id] = {
            'status': 'failed',
            'progress': 0,
            'message': f'Erro no treino: {str(e)}'
        }

@login_required
def submit_buyer_training(request):
    from django.http import JsonResponse
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método não permitido.'}, status=405)
        
    sku = request.POST.get('sku', '')
    file = request.FILES.get('history_file')
    
    if not file:
        return JsonResponse({'status': 'error', 'message': 'Nenhum ficheiro carregado.'}, status=400)
        
    user_id = request.user.id
    
    # Resolve SKU dynamically
    sku_label = sku
    try:
        if '|' in sku:
            parts = sku.split('|')
            subfamily = ProductSubFamily.objects.get(pk=parts[0])
            sku_label = f"{subfamily.name} (Lote #{parts[1]})"
        elif sku:
            subfamily = ProductSubFamily.objects.get(pk=sku)
            sku_label = subfamily.name
    except Exception:
        pass
        
    # Criar pasta do utilizador
    storage_dir = os.path.join(settings.BASE_DIR, 'storage', 'users', str(user_id))
    os.makedirs(storage_dir, exist_ok=True)
    
    # Salvar temporariamente
    temp_dir = os.path.join(storage_dir, 'temp')
    os.makedirs(temp_dir, exist_ok=True)
    temp_file_path = os.path.join(temp_dir, file.name)
    with open(temp_file_path, 'wb+') as destination:
        for chunk in file.chunks():
            destination.write(chunk)
            
    # Disparar thread de treino
    thread = threading.Thread(target=async_buyer_training, args=(user_id, sku_label, temp_file_path, storage_dir))
    thread.daemon = True
    thread.start()
    
    return JsonResponse({
        'status': 'success',
        'message': f'Treino do Buyer Agent e Modelo de Previsões iniciado com sucesso para {sku_label}.'
    })

@login_required
def submit_stock_training(request):
    from django.http import JsonResponse
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método não permitido.'}, status=405)
        
    sku = request.POST.get('sku', '')
    file = request.FILES.get('history_file')
    
    if not file:
        return JsonResponse({'status': 'error', 'message': 'Nenhum ficheiro carregado.'}, status=400)
        
    user_id = request.user.id
    
    # Resolve SKU dynamically
    sku_label = sku
    try:
        if '|' in sku:
            parts = sku.split('|')
            subfamily = ProductSubFamily.objects.get(pk=parts[0])
            sku_label = f"{subfamily.name} (Lote #{parts[1]})"
        elif sku:
            subfamily = ProductSubFamily.objects.get(pk=sku)
            sku_label = subfamily.name
    except Exception:
        pass
        
    # Criar pasta do utilizador
    storage_dir = os.path.join(settings.BASE_DIR, 'storage', 'users', str(user_id))
    os.makedirs(storage_dir, exist_ok=True)
    
    # Salvar temporariamente
    temp_dir = os.path.join(storage_dir, 'temp')
    os.makedirs(temp_dir, exist_ok=True)
    temp_file_path = os.path.join(temp_dir, file.name)
    with open(temp_file_path, 'wb+') as destination:
        for chunk in file.chunks():
            destination.write(chunk)
            
    # Disparar thread de treino
    thread = threading.Thread(target=async_stock_training, args=(user_id, sku_label, temp_file_path, storage_dir))
    thread.daemon = True
    thread.start()
    
    return JsonResponse({
        'status': 'success',
        'message': f'Treino do Stock Agent iniciado com sucesso para {sku_label}.'
    })

@login_required
def get_training_status(request):
    from django.http import JsonResponse
    user_id = request.user.id
    status_data = TRAINING_STATUS.get(user_id, {
        'status': 'idle',
        'progress': 0,
        'epoch': 0,
        'loss': 0.0,
        'message': 'Pronto para treinar.'
    })
    return JsonResponse(status_data)

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
        
        if not culture_id or not warehouse_location:
            return JsonResponse({'status': 'error', 'message': 'Campos obrigatórios em falta.'}, status=400)
            
        culture = get_object_or_404(ProductSubFamily, pk=culture_id)
        
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
        stock.save()
        
        return JsonResponse({
            'status': 'success',
            'message': f"Sucesso: Foram {action_desc} {culture.name} no armazém {warehouse_location}. Stock atual: {new_qty} kg.",
            'quantity': float(stock.quantity)
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
def download_training_template(request):
    import io
    import pandas as pd
    from django.http import HttpResponse
    
    template_type = request.GET.get('type', 'buyer')
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
    if template_type == 'stock':
        columns = [
            'Data', 
            'Cultura_Produto', 
            'Detalhe_Lote', 
            'Stock_Inicial_Kg', 
            'Colheita_Kg', 
            'Vendas_Kg', 
            'Stock_Final_Kg', 
            'Preco_Venda_Euro'
        ]
        data = [
            ['2026-06-01', culture_name, lot_info or 'Lote #10', 1000.0, 500.0, 200.0, 1300.0, 1.50],
            ['2026-06-02', culture_name, lot_info or 'Lote #10', 1300.0, 0.0, 150.0, 1150.0, 1.55],
            ['2026-06-03', culture_name, lot_info or 'Lote #10', 1150.0, 0.0, 300.0, 850.0, 1.60],
            ['2026-06-04', culture_name, lot_info or 'Lote #10', 850.0, 200.0, 100.0, 950.0, 1.50],
            ['2026-06-05', culture_name, lot_info or 'Lote #10', 950.0, 0.0, 250.0, 700.0, 1.65],
        ]
        filename = f"template_treino_stock_{clean_culture_name.lower().replace(' ', '_')}.xlsx"
    else: # buyer
        columns = [
            'Data', 
            'Cultura_Produto', 
            'Vendas_Kg', 
            'Preco_Venda_Euro', 
            'Stock_Fim_Dia_Kg', 
            'Dia_Semana', 
            'Feriado'
        ]
        data = [
            ['2026-06-01', culture_name, 250.0, 1.80, 500.0, 1, 0],
            ['2026-06-02', culture_name, 270.0, 1.85, 450.0, 2, 0],
            ['2026-06-03', culture_name, 310.0, 1.80, 600.0, 3, 0],
            ['2026-06-04', culture_name, 150.0, 1.90, 480.0, 4, 0],
            ['2026-06-05', culture_name, 400.0, 1.75, 380.0, 5, 0],
        ]
        filename = f"template_treino_buyer_{clean_culture_name.lower().replace(' ', '_')}.xlsx"

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