from django import forms
from django.contrib.auth.models import User, Group
# Importar apenas os modelos necessários
from .models import PlantationPlan, Product, Harvest, QUALITY_SCORE_CHOICES, Sensor, Warehouse, SENSOR_TYPE_CHOICES, SoilCharacteristic, PlantationEvent, FertilizerSyntheticData, FertilizerOrganicData, SoilCorrectiveData, PestControlData, MachineryData, FuelData, ElectricEnergyData, IrrigationWaterData, ProductSubFamily, PlantationCrop, MarketplaceOrder 
from django.forms import CheckboxSelectMultiple

# Lista de Roles (mantida)
ROLE_CHOICES = [
    ('Producer', 'Producer'),
    ('Consumer', 'Consumer'),
    ('Transporter', 'Transporter'),
    ('Processor', 'Processor'),
    ('Retailer', 'Retailer'),
]

# --- UserRegisterForm (Mantido) ---
class UserRegisterForm(forms.ModelForm):
    # Campos existentes do User
    role = forms.ChoiceField(
        label='Selecionar Role', 
        choices=ROLE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}) 
    )
    password = forms.CharField(label='Senha', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Confirmar Senha', widget=forms.PasswordInput)
    email = forms.EmailField(label='Email', required=True) 
    
    # NOVOS CAMPOS DO PERFIL
    phone_number = forms.CharField(label='Telemóvel', max_length=20, required=False)
    address = forms.CharField(label='Morada Completa', max_length=255, required=False, widget=forms.Textarea(attrs={'rows': 2}))

    class Meta:
        model = User
        fields = ['username', 'email', 'password']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove o help_text do username
        self.fields['username'].help_text = None
    
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password2 = cleaned_data.get("password2")

        if password and password2 and password != password2:
            raise forms.ValidationError(
                "As senhas não coincidem. Por favor, tente novamente."
            )
        return cleaned_data

# --- 1. Formulário de Produto (Registar um Produto) ---
class ProductRegistrationForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            'name',
            'category',
            'price',
        ]

# --- 6. Formulário de Registo de Característica de Solo (POPUP) ---
class SoilCharacteristicForm(forms.ModelForm):
    
    class Meta:
        model = SoilCharacteristic
        fields = ['category', 'sub_category', 'unit']
        widgets = {
            'category': forms.TextInput(attrs={'class': 'form-control'}),
            'sub_category': forms.TextInput(attrs={'class': 'form-control'}),
            # ALTERADO: Agora é um forms.TextInput em vez de forms.Select
            'unit': forms.TextInput(attrs={'class': 'form-control'}), 
        }

class PlantationPlanForm(forms.ModelForm):
    # Campos base, mantidos no formulário principal

    class Meta:
        model = PlantationPlan
        fields = [
            'plantation_name',
            'quantity_of_trees', 
            'production_type',   
            'chemical_use',      
            'area',
            'location',
            'plantation_date',
        ]
        # Adicione os widgets aqui
        widgets = {
            'plantation_name': forms.TextInput(attrs={'class': 'form-control'}),
            'quantity_of_trees': forms.NumberInput(attrs={'class': 'form-control'}),
            'production_type': forms.Select(attrs={'class': 'form-control'}),
            'chemical_use': forms.Select(attrs={'class': 'form-control'}),
            'area': forms.NumberInput(attrs={'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'plantation_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }

# NOVO FORMULÁRIO AUXILIAR para os 11 campos detalhados (opcionais)
# NOVO FORMULÁRIO AUXILIAR para os campos detalhados (opcionais do SOLO/LOCAL)
class PlantationDetailForm(forms.ModelForm):
    class Meta:
        model = PlantationPlan
        fields = [
            'conduct_system',
            'soil_type',
            'ph_soil',
            'organic_matter_percent',
            'water_regime',
        ]

        widgets = {
            'conduct_system': forms.Select(attrs={'class': 'form-control'}),
            'soil_type': forms.Select(attrs={'class': 'form-control'}),
            'ph_soil': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'organic_matter_percent': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'water_regime': forms.Select(attrs={'class': 'form-control'}),
        }

# --- NOVO: Formulário para Adicionar Cultura à Plantação ---
class PlantationCropForm(forms.ModelForm):
    # plantation field will be hidden or handled in view, but useful to keep in form for validation if needed.
    # We will exclude 'plantation' from user input in the template and inject it in the view, 
    # OR let user select it if this is a standalone form.
    # The requirement says: "ter uma secção onde adicione uma cultura de cada vez ás plantações criadas".
    # So user selects plantation, then crop.
    
    plantation = forms.ModelChoiceField(
        queryset=PlantationPlan.objects.all(),
        label='Plantation',
        empty_label="--- Select Plantation ---",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    subfamily = forms.ModelChoiceField(
        queryset=ProductSubFamily.objects.all(),
        label='Culture',
        empty_label="--- Select Culture ---",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['plantation'].queryset = PlantationPlan.objects.filter(producer=user).order_by('-plantation_date')

    class Meta:
        model = PlantationCrop
        fields = [
            'plantation',
            'subfamily',
            'avg_plant_age_years',
            'rootstock',
            'density_plants_ha',
            'irrigation_system'
        ]
        widgets = {
            'avg_plant_age_years': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'rootstock': forms.TextInput(attrs={'class': 'form-control'}),
            'density_plants_ha': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'irrigation_system': forms.Select(attrs={'class': 'form-control'}),
        }

# --- Formulário de Detalhe: Fertilizantes (Sintéticos Minerais) ---
class FertilizerSyntheticForm(forms.ModelForm):
    class Meta:
        model = FertilizerSyntheticData
        # Lista todos os campos da Tabela 3
        fields = '__all__'
        
# --- Formulário de Detalhe: Fertilizantes (Orgânicos) ---
class FertilizerOrganicForm(forms.ModelForm):
    class Meta:
        model = FertilizerOrganicData
        # Lista todos os campos da Tabela 4
        fields = '__all__'

# --- Formulário de Detalhe: Corretivos do Solo ---
class SoilCorrectiveForm(forms.ModelForm):
    class Meta:
        model = SoilCorrectiveData
        fields = '__all__'

# --- Formulário de Detalhe: Produtos Fitofarmacêuticos ---
class PestControlForm(forms.ModelForm):
    class Meta:
        model = PestControlData
        fields = '__all__'

# --- Formulário de Detalhe: Maquinaria ---
class MachineryForm(forms.ModelForm):
    class Meta:
        model = MachineryData
        fields = '__all__'

# --- Formulário de Detalhe: Combustíveis ---
class FuelForm(forms.ModelForm):
    class Meta:
        model = FuelData
        fields = '__all__'

# --- Formulário de Detalhe: Energia Elétrica ---
class ElectricEnergyForm(forms.ModelForm):
    class Meta:
        model = ElectricEnergyData
        fields = '__all__'

# --- Formulário de Detalhe: Água de Rega ---
class IrrigationWaterForm(forms.ModelForm):
    class Meta:
        model = IrrigationWaterData
        fields = '__all__'

# B. Criar PlantationEventForm
class PlantationEventForm(forms.ModelForm):
    
    # NOVO CAMPO CRÍTICO: Dropdown para selecionar a plantação à qual o evento pertence
    plantation = forms.ModelChoiceField(
        queryset=PlantationPlan.objects.all(), # Será filtrado em views.py
        label='Plano de Plantação',
        empty_label="--- Selecione o Pomar ---",
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'event_plantation_select'})
    )

    subfamily = forms.ModelChoiceField(
        queryset=ProductSubFamily.objects.all(),
        label='Cultura',
        empty_label="--- Selecione a Cultura ---",
        required=True, # Obrigatório
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'event_subfamily_select'})
    )
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['plantation'].queryset = PlantationPlan.objects.filter(producer=user).order_by('-plantation_date')

    class Meta:
        model = PlantationEvent
        # Adicionar 'plantation' à lista de fields
        fields = ['plantation', 'subfamily', 'event_date', 'event_type', 'notes'] 
        
        widgets = {
            'event_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'event_type': forms.Select(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }

# --- 3. Formulário de Colheita (Registar Colheita) ---
class HarvestForm(forms.ModelForm):
    
    # 2 -> Dropdown para selecionar "Plantation ID - Product Name"
    # Este campo será filtrado na view para mostrar apenas planos ATIVOS do produtor.
    # O queryset inicial é irrelevante, mas o ModelChoiceField é necessário.
    plantation = forms.ModelChoiceField(
        # Será filtrado em views.py
        queryset=PlantationPlan.objects.all(), 
        label='Plantation',
        empty_label="--- Select Plantation ---",
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'harvest_plantation_select'})
    )
    
    subfamily = forms.ModelChoiceField(
        queryset=ProductSubFamily.objects.all(),
        label='Cultures',
        empty_label="--- Select Culture ---",
        required=True, # Obrigatório
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'harvest_subfamily_select'})
    )

    class Meta:
        model = Harvest
        # Campos a serem exibidos no formulário (o harvest_id é automático)
        fields = [
            'plantation', 
            'subfamily',
            'harvest_date', 
            'harvest_quantity_kg', 
            'avg_quality_score', 
            'utilized_quantity_kg',
            'caliber',
            'soluble_solids',
            'warehouse'
        ]
        widgets = {
            # 3 -> Data de Colheita
            'harvest_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'plantation': forms.Select(attrs={'class': 'form-control', 'id': 'harvest_plantation_select'}), # ID para JS
            'subfamily': forms.Select(attrs={'class': 'form-control', 'id': 'harvest_subfamily_select'}), # ID para JS
            'harvest_quantity_kg': forms.NumberInput(attrs={'class': 'form-control'}),
            'avg_quality_score': forms.Select(attrs={'class': 'form-control'}),
            'utilized_quantity_kg': forms.NumberInput(attrs={'class': 'form-control'}),
            'caliber': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'mm'}),
            'soluble_solids': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Brix'}),
            'warehouse': forms.Select(attrs={'class': 'form-control'}),
        }

# --- 4. Formulário de Registo de Sensor (Para o Popup) ---
class SensorRegistrationForm(forms.ModelForm):
    
    class Meta:
        model = Sensor
        fields = ['sensor_id', 'brand', 'sensor_type']
        # Adicione attrs para melhor estilo no seu frontend
        widgets = {
            'sensor_id': forms.TextInput(attrs={'class': 'form-control'}),
            'brand': forms.TextInput(attrs={'class': 'form-control'}),
            'sensor_type': forms.Select(attrs={'class': 'form-control'}),
        }

# --- 5. Formulário de Registo de Warehouse (Com Widget Melhorado) ---
class WarehouseRegistrationForm(forms.ModelForm):
    
    class Meta:
        model = Warehouse
        fields = ['location', 'control_type', 'capacity', 'sensors']
        
        # Usar CheckboxSelectMultiple para facilitar a seleção de múltiplos sensores
        widgets = {
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'control_type': forms.Select(attrs={'class': 'form-control'}),
            'capacity': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'sensors': forms.CheckboxSelectMultiple(), # Renderiza checkboxes em vez de um seletor simples
        }

# ----------------------------------------------------------------------
# 6. FORMULÁRIO DE MARKETPLACE
# ----------------------------------------------------------------------

class MarketplaceOrderForm(forms.ModelForm):
    class Meta:
        model = MarketplaceOrder
        fields = ['order_type', 'culture', 'quantity_kg', 'warehouse_location', 
                  'min_caliber', 'min_soluble_solids', 'min_quality_score']
        widgets = {
            'order_type': forms.Select(attrs={'class': 'form-control'}),
            'culture': forms.Select(attrs={'class': 'form-control'}),
            'quantity_kg': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'warehouse_location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Armazém Norte / Sede'}),
            
            # Quality Filters (Buy)
            'min_caliber': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Min mm'}),
            'min_soluble_solids': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Min Brix'}),
            'min_quality_score': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '10', 'placeholder': 'Min Score (1-10)'}),
        }
        labels = {
            'warehouse_location': 'Localização para Entrega/Recolha',
            'min_caliber': 'Calibre Mínimo (> mm)',
            'min_soluble_solids': 'Brix Mínimo (> Brix)',
            'min_quality_score': 'Qualidade Mínima (> 0-10)',
        }

class MarketSellOrderForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            # Filtra apenas colheitas do produtor e que tenham stock > 0
            self.fields['harvest_origin'].queryset = Harvest.objects.filter(producer=user).order_by('-harvest_date')
            
            # Atualiza labels das opções para mostrar stock
            # (O __str__ do Harvest já foi atualizado no models.py para mostrar stock)

    class Meta:
        model = MarketplaceOrder
        fields = ['harvest_origin', 'quantity_kg', 'warehouse_location',
                  'caliber', 'soluble_solids', 'quality_score']
        widgets = {
            'harvest_origin': forms.Select(attrs={'class': 'form-control', 'id': 'id_sell_harvest_origin'}),
            'quantity_kg': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'id': 'id_sell_quantity_kg'}),
            'warehouse_location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Armazém Central', 'id': 'id_sell_warehouse_location'}),
            
            # Read-only Auto-filled Quality Data
            'caliber': forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly', 'style': 'background-color: #e9ecef;', 'id': 'id_sell_caliber'}),
            'soluble_solids': forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly', 'style': 'background-color: #e9ecef;', 'id': 'id_sell_soluble_solids'}),
            'quality_score': forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly', 'style': 'background-color: #e9ecef;', 'id': 'id_sell_quality_score'}),
        }
        labels = {
            'harvest_origin': 'Lote de Origem (Stock Disponível)',
            'quantity_kg': 'Quantidade a Vender (Kg)',
            'warehouse_location': 'Local de Recolha',
            'caliber': 'Calibre (mm)',
            'soluble_solids': 'Brix',
            'quality_score': 'Score',
        }

    def clean(self):
        cleaned_data = super().clean()
        harvest = cleaned_data.get('harvest_origin')
        qty = cleaned_data.get('quantity_kg')
        
        if harvest and qty:
            if qty > harvest.current_stock_kg:
                raise forms.ValidationError(f"Quantidade excede o stock disponível ({harvest.current_stock_kg} kg).")
            
            # Preencher automaticamente
            self.instance.culture = harvest.subfamily
            self.instance.order_type = 'SELL'
            
        return cleaned_data

# ----------------------------------------------------------------------
# 7. FORMS LOGISTICA TRANSPORTADOR (LIACC INTERFACE)
# ----------------------------------------------------------------------

class TransportPlanForm(forms.ModelForm):
    class Meta:
        model = MarketplaceOrder
        fields = ['planned_pickup_date', 'planned_delivery_date']
        widgets = {
            'planned_pickup_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'planned_delivery_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
        }
        labels = {
            'planned_pickup_date': 'ETA Recolha (Planeado)',
            'planned_delivery_date': 'ETA Entrega (Planeado)',
        }

class TransportDeliveryForm(forms.ModelForm):
    class Meta:
        model = MarketplaceOrder
        fields = ['transport_sensor_data']
        widgets = {
            'transport_sensor_data': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Cole aqui o JSON dos sensores...'})
        }
        labels = {
            'transport_sensor_data': 'Relatório de Sensores (JSON)',
        }

# --- PROCESSOR FORMS ---

class ProcessorProcessingForm(forms.ModelForm):
    class Meta:
        model = MarketplaceOrder
        fields = ['packaging_type', 'preservation_treatment']
        labels = {
            'packaging_type': 'Tipo de Embalagem',
            'preservation_treatment': 'Tratamento de Conservação',
        }
        widgets = {
            'packaging_type': forms.Select(attrs={'class': 'form-control'}),
            'preservation_treatment': forms.Select(attrs={'class': 'form-control'}),
        }