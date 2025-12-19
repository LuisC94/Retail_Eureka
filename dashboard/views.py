from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views import View
from django.urls import reverse, reverse_lazy 
from .decorators import role_required 
from django.contrib.auth.models import Group

from .models import (
    Product, PlantationPlan, Harvest, Warehouse, Sensor, UserProfile, PlantationEvent,
    SoilCharacteristic, PlantationSoilValue, ProductSubFamily, PlantationCrop,
    FertilizerSyntheticData, FertilizerOrganicData, SoilCorrectiveData, PestControlData,
    MachineryData, FuelData, ElectricEnergyData, IrrigationWaterData
)

from .forms import (
    UserRegisterForm, ProductRegistrationForm, PlantationPlanForm, PlantationDetailForm,
    HarvestForm, WarehouseRegistrationForm, SensorRegistrationForm, PlantationEventForm,
    FertilizerSyntheticForm, FertilizerOrganicForm, SoilCorrectiveForm, PestControlForm,
    MachineryForm, FuelForm, ElectricEnergyForm, IrrigationWaterForm, SoilCharacteristicForm, PlantationCropForm
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
        context = { 'username': user.username, 'role': 'Transporter' }
        return render(request, 'dashboard/transporterDash.html', context)

# Consumer Dashboard
@method_decorator(login_required, name='dispatch')
@method_decorator(role_required(['Consumer']), name='dispatch')
class ConsumerDashboardView(View):
    def get(self, request):
        user = request.user
        context = { 'username': user.username, 'role': 'Consumer' }
        return render(request, 'dashboard/consumerDash.html', context)

# Processor Dashboard
@method_decorator(login_required, name='dispatch')
@method_decorator(role_required(['Processor']), name='dispatch')
class ProcessorDashboardView(View):
    def get(self, request):
        user = request.user
        context = { 'username': user.username, 'role': 'Processor' }
        return render(request, 'dashboard/processorDash.html', context)

# Retailer Dashboard
@method_decorator(login_required, name='dispatch')
@method_decorator(role_required(['Retailer']), name='dispatch')
class RetailerDashboardView(View):
    def get(self, request):
        user = request.user
        context = { 'username': user.username, 'role': 'Retailer' }
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
        
        harvest_records = Harvest.objects.filter(producer=user).select_related('plantation', 'subfamily').order_by('-harvest_date')
        
        # AGGREGATION: Total Kgs per Product (Current Stock)
        harvest_sums = Harvest.objects.filter(producer=user).values(
            'plantation__plantation_name', 
            'subfamily__name'
        ).annotate(
            total_kg=Sum('harvest_quantity_kg'),
            delivered_kg=Sum('delivered_quantity_kg')
        ).order_by('plantation__plantation_name', 'subfamily__name')
        
        for item in harvest_sums:
            item['current_stock'] = (item['total_kg'] or 0) - (item['delivered_kg'] or 0)

        
        # 4. BUSCAR EVENTOS DO POMAR
        plantation_events = PlantationEvent.objects.filter(plantation__producer=user).select_related('plantation', 'subfamily').order_by('-event_date')
        
        product_subfamilies = ProductSubFamily.objects.all().order_by('fruit_type', 'name')
        
        producer_warehouses = Warehouse.objects.filter(owner=user).order_by('warehouse_id')
        all_sensors = Sensor.objects.all().order_by('sensor_id')


        plantation_plan_form = PlantationPlanForm()
        plantation_detail_form = PlantationDetailForm()
        harvest_form = HarvestForm() 

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
            
            'plantation_plan_form': plantation_plan_form,
            'plantation_detail_form': plantation_detail_form,
            'plantation_crop_form': PlantationCropForm(), # NEW FORM
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

            'plantation_event_form': PlantationEventForm(),
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
        form = PlantationCropForm(request.POST)
        
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
    return redirect(REDIRECT_URL)