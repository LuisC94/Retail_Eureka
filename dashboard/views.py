from django.db import IntegrityError
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views import View
from django.urls import reverse, reverse_lazy 
from .decorators import role_required 
from django.contrib.auth.models import Group

# Importações ATUALIZADAS
from .forms import UserRegisterForm, PlantationPlanForm, ProductRegistrationForm, HarvestForm
from .models import PlantationPlan, Product, UserProfile, Harvest

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

method_decorator(login_required, name='dispatch')
@method_decorator(role_required(['Producer']), name='dispatch')
class ProducerDashboardView(View):
    def get(self, request):
        user = request.user
        
        # 1. BUSCAR PRODUTOS (Variável do Template: registered_products)
        # Lista completa dos produtos registados pelo produtor.
        registered_products = Product.objects.filter(producer=user).order_by('name')
        
        # 2. BUSCAR PLANOS DE PLANTAÇÃO (Variável do Template: plantation_plans)
        # Lista dos planos que AINDA NÃO FORAM colhidos (os colhidos foram apagados pela view de Harvest).
        # Isto representa a lista de Planos Ativos para a tabela geral.
        all_plantation_plans = PlantationPlan.objects.filter(producer=user).order_by('-plantation_date')
        
        # 3. BUSCAR REGISTOS DE COLHEITA (Variável do Template: harvest_records)
        # Histórico de todas as colheitas concluídas.
        harvest_records = Harvest.objects.filter(producer=user).order_by('-harvest_date')
        
        # 4. INSTANCIAR FORMULÁRIOS
        # Mantemos os nomes do primeiro código para compatibilidade de contexto:
        product_registration_form = ProductRegistrationForm()
        plantation_plan_form = PlantationPlanForm()
        harvest_form = HarvestForm() 
        
        # 5. FILTRO CRUCIAL para HarvestForm
        # Apenas os planos existentes são planos ativos (prontos a colher).
        harvest_form.fields['plantation'].queryset = all_plantation_plans 
        
        try:
            # Buscando UserProfile (mantido do seu código original)
            user_profile = UserProfile.objects.get(user=user)
        except UserProfile.DoesNotExist:
            user_profile = None

        # 6. CONTEXTO
        context = {
            'username': user.username,
            'role': 'Producer',
            
            # Formulários
            'product_registration_form': product_registration_form, # Para registar produto
            'plantation_plan_form': plantation_plan_form,         # Para registar plantação
            'harvest_form': harvest_form,                          # Para registar colheita (NOVO)
            
            # Listas de Dados
            'registered_products': registered_products,  # Lista de Produtos (Completa)
            'plantation_plans': all_plantation_plans,    # Lista de Planos (Ativos)
            'harvest_records': harvest_records,          # Lista de Colheitas (Concluídas)
            'user_profile': user_profile,
            
            # Mensagens de erro/sucesso 
            'db_error': request.session.pop('db_error', None),
        }
        
        return render(request, 'dashboard/producerDash.html', context)

# ----------------------------------------------------------------------
# 4. VIEWS DE SUBMISSÃO DO PRODUTOR (NOVAS)
# ----------------------------------------------------------------------

@login_required
@role_required(['Producer'])
def producer_submit_product(request):
    """ Processa o registo de um novo Produto na tabela 'products' """
    if request.method == 'POST':
        form = ProductRegistrationForm(request.POST)
        if form.is_valid():
            product_record = form.save(commit=False)
            product_record.producer = request.user 
            try:
                product_record.save()
                return redirect('producer_dashboard')
            except IntegrityError as e:
                db_error = f"Erro ao salvar Produto na DB: ID '{product_record.product_id}' já existe. Detalhe: {e}"
                print(db_error)
                
        return redirect('producer_dashboard')
    return redirect('producer_dashboard') 


@login_required
@role_required(['Producer'])
def producer_submit_plantation(request):
    db_error = None

    if request.method == 'POST':
        # Instanciar o formulário com os dados POST
        form = PlantationPlanForm(request.POST)

        if form.is_valid():
            try:
                # 1. Salva o objeto (sem commit)
                plantation_record = form.save(commit=False)
                
                # 2. Injeta os dados que não estão no formulário:
                # O 'product' (instância Product) JÁ ESTÁ na instância do formulário,
                # graças ao ModelChoiceField.
                plantation_record.producer = request.user # Liga à FK do Produtor
                
                # 3. Salva na base de dados (o ID é gerado automaticamente)
                plantation_record.save()
                
                # Sucesso
                return redirect('producer_dashboard')
                
            except IntegrityError as e:
                db_error = f"Erro ao salvar Plantação na DB: Detalhe: {e}"

        return redirect('producer_dashboard')
    return redirect('producer_dashboard')

@login_required
@role_required(['Producer'])
def producer_submit_harvest(request):
    """
    Processa o formulário de colheita. 
    Lógica Crucial: Cria o registo Harvest e REMOVE o PlantationPlan.
    """
    if request.method == 'POST':
        form = HarvestForm(request.POST)

        # 1. Replicar o filtro de segurança (garante que só pode colher os seus planos ativos)
        active_plans = PlantationPlan.objects.filter(producer=request.user).exclude(harvest__isnull=False)
        form.fields['plantation'].queryset = active_plans

        if form.is_valid():
            # O Django já converteu o ID do formulário na instância PlantationPlan
            plantation_instance_to_delete = form.cleaned_data['plantation']
            
            try:
                # 2. Salvar o novo registo de Colheita
                harvest_record = form.save(commit=False)
                harvest_record.producer = request.user
                harvest_record.save()
                
                # 3. Lógica CRUCIAL: Remover o registo da PlantationPlan
                plantation_instance_to_delete.delete()
                
                # Sucesso
                return redirect('producer_dashboard')
                
            except IntegrityError as e:
                db_error = f"Erro ao salvar Colheita na DB: Detalhe: {e}"
                request.session['db_error'] = db_error
            except Exception as e:
                db_error = f"Ocorreu um erro inesperado: {e}"
                request.session['db_error'] = db_error
        
        # Se houver erro de validação ou DB, redireciona
        return redirect('producer_dashboard')
        
    # Bloquear acesso GET
    return redirect('producer_dashboard')