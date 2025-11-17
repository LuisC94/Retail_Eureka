from django import forms
from django.contrib.auth.models import User, Group
# Importar apenas os modelos necessários
from .models import PlantationPlan, Product, Harvest, QUALITY_SCORE_CHOICES, Sensor, Warehouse, SENSOR_TYPE_CHOICES
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

# --- 2. Formulário de Plantação (Registar uma Plantação) ---
class PlantationPlanForm(forms.ModelForm):
    
    product = forms.ModelChoiceField(
        queryset=Product.objects.all(), # Busca todos os produtos para a lista
        label='Produto Selecionar',
        empty_label="--- Selecione um Produto Registado ---"
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
        widgets = {
            'plantation_date': forms.DateInput(attrs={'type': 'date'}),
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