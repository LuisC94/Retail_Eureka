from django import forms
from django.contrib.auth.models import User, Group
# Importar apenas os modelos necessários
from .models import PlantationPlan, Product, Harvest, QUALITY_SCORE_CHOICES, Sensor, Warehouse, SENSOR_TYPE_CHOICES, SoilCharacteristic, PlantationEvent, FertilizerSyntheticData, FertilizerOrganicData, SoilCorrectiveData, PestControlData, MachineryData, FuelData, ElectricEnergyData, IrrigationWaterData 
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
    product = forms.ModelChoiceField(
        queryset=Product.objects.all(), 
        label='Produto a Selecionar', 
        empty_label="--- Selecione um Produto Registado ---",
        widget=forms.Select(attrs={'class': 'form-control'}) 
    )

    class Meta:
        model = PlantationPlan
        fields = [
            'product',
            'quantity_of_seeds', 
            'production_type',   
            'chemical_use',      
            'area',
            'location',
            'plantation_date',
        ]
        # Adicione os widgets aqui
        widgets = {
            'quantity_of_seeds': forms.NumberInput(attrs={'class': 'form-control'}),
            'production_type': forms.Select(attrs={'class': 'form-control'}),
            'chemical_use': forms.Select(attrs={'class': 'form-control'}),
            'area': forms.NumberInput(attrs={'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'plantation_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }

# NOVO FORMULÁRIO AUXILIAR para os 11 campos detalhados (opcionais)
class PlantationDetailForm(forms.ModelForm):
    # Nota: Este formulário não precisa de campos extras, apenas os campos do modelo

    class Meta:
        model = PlantationPlan
        fields = [
            'total_area_ha',
            'avg_plant_age_years',
            'kiwi_variety',
            'rootstock',
            'density_plants_ha',
            'conduct_system',
            'soil_type',
            'ph_soil',
            'organic_matter_percent',
            'water_regime',
            'irrigation_system',
        ]

        widgets = {
            'total_area_ha': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'avg_plant_age_years': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'kiwi_variety': forms.Select(attrs={'class': 'form-control'}),
            'rootstock': forms.TextInput(attrs={'class': 'form-control'}),
            'density_plants_ha': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'conduct_system': forms.Select(attrs={'class': 'form-control'}),
            'soil_type': forms.Select(attrs={'class': 'form-control'}),
            'ph_soil': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'organic_matter_percent': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'water_regime': forms.Select(attrs={'class': 'form-control'}),
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
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    class Meta:
        model = PlantationEvent
        # Adicionar 'plantation' à lista de fields
        fields = ['plantation', 'event_date', 'event_type', 'notes'] 
        
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
        label='Plano de Plantação a Colher',
        empty_label="--- Selecione um Plano Ativo ---"
    )
    
    class Meta:
        model = Harvest
        # Campos a serem exibidos no formulário (o harvest_id é automático)
        fields = [
            'plantation', 
            'harvest_date', 
            'harvest_quantity_kg', 
            'avg_quality_score', 
            'utilized_quantity_kg'
        ]
        widgets = {
            # 3 -> Data de Colheita
            'harvest_date': forms.DateInput(attrs={'type': 'date'}), 
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