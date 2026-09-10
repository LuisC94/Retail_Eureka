import re
from django import forms
from django.contrib.auth.models import User, Group
# Importar apenas os modelos necessários
from .models import PlantationPlan, Product, Harvest, QUALITY_SCORE_CHOICES, Sensor, UserProfile, Warehouse, SENSOR_TYPE_CHOICES, SoilCharacteristic, PlantationEvent, FertilizerSyntheticData, FertilizerOrganicData, SoilCorrectiveData, PestControlData, MachineryData, FuelData, ElectricEnergyData, IrrigationWaterData, ProductSubFamily, PlantationCrop, MarketplaceOrder, Vehicle, Route
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
        label='Role', 
        choices=ROLE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}) 
    )
    password = forms.CharField(label='Password', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Confirm Password', widget=forms.PasswordInput)
    email = forms.EmailField(label='Email', required=True) 
    
    # NOVOS CAMPOS DO PERFIL
    phone_number = forms.CharField(label='Mobile Phone', max_length=20, required=False)
    address = forms.CharField(label='Full Address', max_length=255, required=False, widget=forms.Textarea(attrs={'rows': 2}))

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
                "The passwords do not match. Please try again."
            )
        return cleaned_data

class UserProfileEditForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['phone_number', 'address']
        widgets = {
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: +351 912345678'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Full Address'}),
        }

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
    plantation_name = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def clean_quantity_of_trees(self):
        value = self.cleaned_data.get('quantity_of_trees')
        if value is not None and value <= 0:
            raise forms.ValidationError('Quantity of trees must be greater than 0.')
        return value

    def clean_area(self):
        value = self.cleaned_data.get('area')
        if value is not None and value <= 0:
            raise forms.ValidationError('Area must be greater than 0.')
        return value

    def clean_plantation_name(self):
        plantation_name = self.cleaned_data.get('plantation_name')
        if plantation_name and self.user:
            qs = PlantationPlan.objects.filter(
                plantation_name=plantation_name,
                producer=self.user
            )
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError('A plantation with this name already exists for your profile.')
        return plantation_name

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
            'quantity_of_trees': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'production_type': forms.Select(attrs={'class': 'form-control'}),
            'chemical_use': forms.Select(attrs={'class': 'form-control'}),
            'area': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
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
            'density_plants_ha': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': 0}),
            'irrigation_system': forms.Select(attrs={'class': 'form-control'}),
        }

# --- Formulário de Detalhe: Fertilizantes (Sintéticos Minerais) ---
class FertilizerSyntheticForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add HTML5 min attribute to numeric fields for UI-level validation
        self.fields['n_content'].widget = forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'max': '100', 'step': '0.01'})
        self.fields['p2o5_content'].widget = forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'max': '100', 'step': '0.01'})
        self.fields['k2o_content'].widget = forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'max': '100', 'step': '0.01'})
        self.fields['total_dose_kg_ha_year'].widget = forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'max': '100', 'step': '0.01'})
        self.fields['num_applications'].widget = forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '1'})

    def clean_n_content(self):
        value = self.cleaned_data.get('n_content')
        if value is not None and value < 0:
            raise forms.ValidationError('N Content (%) cannot be negative.')
        return value

    def clean_p2o5_content(self):
        value = self.cleaned_data.get('p2o5_content')
        if value is not None and value < 0:
            raise forms.ValidationError('P2O5 Content (%) cannot be negative.')
        return value

    def clean_k2o_content(self):
        value = self.cleaned_data.get('k2o_content')
        if value is not None and value < 0:
            raise forms.ValidationError('K2O Content (%) cannot be negative.')
        return value

    def clean_total_dose_kg_ha_year(self):
        value = self.cleaned_data.get('total_dose_kg_ha_year')
        if value < 0:
            raise forms.ValidationError('Total Dose (kg/ha/year) cannot be negative.')
        return value

    def clean_num_applications(self):
        value = self.cleaned_data.get('num_applications')
        if value is not None and value < 0:
            raise forms.ValidationError('No. of Applications cannot be negative.')
        return value

    class Meta:
        model = FertilizerSyntheticData
        # Lista todos os campos da Tabela 3
        fields = '__all__'
        
# --- Formulário de Detalhe: Fertilizantes (Orgânicos) ---
class FertilizerOrganicForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ['n_content_kgt', 'p_content_kgt', 'k_content_kgt', 'dose_tha_year']:
            if field_name in self.fields:
                self.fields[field_name].widget.attrs['min'] = '0'
    class Meta:
        model = FertilizerOrganicData
        # Lista todos os campos da Tabela 4
        fields = '__all__'

# --- Formulário de Detalhe: Corretivos do Solo ---
class SoilCorrectiveForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add widget-specific attributes if needed
        self.fields['caco3_content'].widget.attrs.update({
            'min': 0,
            'max': 100,
            'step': '0.01'
        })
        self.fields['dose_kg_ha_year'].widget.attrs.update({
            'min': 0,
            'step': '0.01'
        })
        self.fields['frequency_years'].widget.attrs.update({
            'min': 0,
            'step': 1
        })
    
    def clean_caco3_content(self):
        value = self.cleaned_data['caco3_content']
        if value < 0 or value > 100:
            raise forms.ValidationError('CaCO3 Equivalent Content must be between 0 and 100.')
        return value
    
    def clean_dose_kg_ha_year(self):
        value = self.cleaned_data['dose_kg_ha_year']
        if value < 0:
            raise forms.ValidationError('Dose cannot be negative.')
        return value
    
    def clean_frequency_years(self):
        value = self.cleaned_data['frequency_years']
        if value < 0:
            raise forms.ValidationError('Frequency cannot be negative.')
        return value
    class Meta:
        model = SoilCorrectiveData
        fields = '__all__'

# --- Formulário de Detalhe: Produtos Fitofarmacêuticos ---
class PestControlForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add HTML5 number input with min constraint
        self.fields['num_applications_year'].widget = forms.NumberInput(
            attrs={'min': '0', 'step': '1'}
        )
    class Meta:
        model = PestControlData
        fields = '__all__'

# --- Formulário de Detalhe: Maquinaria ---
class MachineryForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add HTML5 number input with min constraint for hours_per_year
        self.fields['hours_per_year'].widget = forms.NumberInput(
            attrs={'class': 'form-control', 'min': '0', 'step': '0.01'}
        )
        # Add pattern hint for power field
        self.fields['power'].widget = forms.TextInput(
            attrs={'class': 'form-control', 'placeholder': 'e.g., 15.5kW or 100 CV'}
        )
    def clean_hours_per_year(self):
        value = self.cleaned_data.get('hours_per_year')
        if value is not None and value < 0:
            raise forms.ValidationError('Hours/Year cannot be negative.')
        return value

    def clean_power(self):
        value = self.cleaned_data.get('power')
        if value:
            import re
            if not re.match(r'^\d+(\.\d+)?\s*(kW|CV)$', value.strip()):
                raise forms.ValidationError(
                    "Power must be a positive number followed by 'kW' or 'CV' (e.g., '15.5kW', '100 CV')."
                )
        return value
    class Meta:
        model = MachineryData
        fields = '__all__'

# --- Formulário de Detalhe: Combustíveis ---
class FuelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['annual_consumption'].widget = forms.NumberInput(
            attrs={'class': 'form-control', 'min': '0', 'step': '0.01'}
        )
    class Meta:
        model = FuelData
        fields = '__all__'

# --- Formulário de Detalhe: Energia Elétrica ---
class ElectricEnergyForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Total Consumption (kWh/year) - non-negative
        self.fields['total_consumption_kwh_year'].widget = forms.NumberInput(
            attrs={'class': 'form-control', 'min': '0', 'step': '0.01'}
        )
        # % Grid - between 0-100
        self.fields['percent_grid'].widget = forms.NumberInput(
            attrs={'class': 'form-control', 'min': '0', 'max': '100', 'step': '0.01'}
        )
        # % Photovoltaic (Self) - between 0-100
        self.fields['percent_photovoltaic'].widget = forms.NumberInput(
            attrs={'class': 'form-control', 'min': '0', 'max': '100', 'step': '0.01'}
        )
        # % Other Renewable - between 0-100
        self.fields['percent_other_renewable'].widget = forms.NumberInput(
            attrs={'class': 'form-control', 'min': '0', 'max': '100', 'step': '0.01'}
        )
    class Meta:
        model = ElectricEnergyData
        fields = '__all__'

# --- Formulário de Detalhe: Água de Rega ---
class IrrigationWaterForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Volume (m3/year) - non-negative
        self.fields['volume_m3_year'].widget = forms.NumberInput(
            attrs={'class': 'form-control', 'min': '0', 'step': '0.01'}
        )
        # Pumping Height (m) - non-negative (nullable field)
        self.fields['pumping_height_m'].widget = forms.NumberInput(
            attrs={'class': 'form-control', 'min': '0', 'step': '0.01'}
        )
        # Estimated Efficiency (%) - between 0-100 (nullable field)
        self.fields['estimated_efficiency'].widget = forms.NumberInput(
            attrs={'class': 'form-control', 'min': '0', 'max': '100', 'step': '0.01'}
        )
    class Meta:
        model = IrrigationWaterData
        fields = '__all__'

# B. Criar PlantationEventForm
class PlantationEventForm(forms.ModelForm):
    
    # NOVO CAMPO CRÍTICO: Dropdown para selecionar a plantação à qual o evento pertence
    plantation = forms.ModelChoiceField(
        queryset=PlantationPlan.objects.all(), # Will be filtered in views.py
        label='Plantation Plan',
        empty_label="--- Select Orchard ---",
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'event_plantation_select'})
    )

    subfamily = forms.ModelChoiceField(
        queryset=ProductSubFamily.objects.all(),
        label='Culture',
        empty_label="--- Select Culture ---",
        required=True, # Required
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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'warehouse' in self.fields:
            self.fields['warehouse'].required = True
            self.fields['warehouse'].empty_label = "--- Select Warehouse ---"
    
    # 2 -> Dropdown para selecionar "Plantation ID - Product Name"
    # Este campo será filtrado na view para mostrar apenas planos ATIVOS do produtor.
    # O queryset inicial é irrelevante, mas o ModelChoiceField é necessário.
    plantation = forms.ModelChoiceField(
        # Será filtrado em views.py
        queryset=PlantationPlan.objects.all(), 
        label='Plantation',
        empty_label="--- Select Plantation ---",
        required=False,
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'harvest_plantation_select'})
    )
    
    subfamily = forms.ModelChoiceField(
        queryset=ProductSubFamily.objects.all(),
        label='Cultures',
        empty_label="--- Select Culture ---",
        required=True, # Obrigatório
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'harvest_subfamily_select'})
    )
    
    utilized_quantity_kg = forms.DecimalField(
        required=False,
        initial=0.0,
        label='Waste (Kg)',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.01'})
    )
    
    avg_quality_score = forms.ChoiceField(
        choices=QUALITY_SCORE_CHOICES,
        required=False,
        initial=10,
        label='Average Quality Score (1-10)',
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    def clean_harvest_quantity_kg(self):
        val = self.cleaned_data.get('harvest_quantity_kg')
        if val is not None and val < 0:
            raise forms.ValidationError('Harvest Quantity (Kg) cannot be negative.')
        return val

    def clean_utilized_quantity_kg(self):
        val = self.cleaned_data.get('utilized_quantity_kg')
        if val is None:
            return 0.0
        if val < 0:
            raise forms.ValidationError('Waste (Kg) cannot be negative.')
        return val

    def clean_caliber(self):
        val = self.cleaned_data.get('caliber')
        if val is not None and val < 0:
            raise forms.ValidationError('Caliber (mm) cannot be negative.')
        return val

    def clean_soluble_solids(self):
        val = self.cleaned_data.get('soluble_solids')
        if val is not None and val < 0:
            raise forms.ValidationError('Soluble Solids (Brix) cannot be negative.')
        return val

    def clean_avg_quality_score(self):
        val = self.cleaned_data.get('avg_quality_score')
        if val is None or val == '':
            return 10
        return int(val)

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
            'harvest_quantity_kg': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.01'}),
            'avg_quality_score': forms.Select(attrs={'class': 'form-control'}),
            'utilized_quantity_kg': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.01'}),
            'caliber': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'placeholder': 'mm'}),
            'soluble_solids': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'placeholder': 'Brix'}),
            'warehouse': forms.Select(attrs={'class': 'form-control'}),
        }

# --- 4. Formulário de Registo de Sensor (Para o Popup) ---
class SensorRegistrationForm(forms.ModelForm):
    class Meta:
        model = Sensor
        fields = ['sensor_id', 'brand', 'sensor_type']
        widgets = {
            'sensor_id': forms.TextInput(attrs={'class': 'form-control'}),
            'brand': forms.TextInput(attrs={'class': 'form-control'}),
            'sensor_type': forms.Select(attrs={'class': 'form-control'}),
        }

# --- 5. Formulário de Registo de Warehouse (Com Widget Melhorado) ---
class WarehouseRegistrationForm(forms.ModelForm):
    
    class Meta:
        model = Warehouse
        fields = ['location', 'region', 'control_type', 'storage_unit', 'max_vehicle_access', 'capacity', 'sensors', 'latitude', 'longitude']
        
        # Usar CheckboxSelectMultiple para facilitar a seleção de múltiplos sensores
        widgets = {
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'region': forms.Select(attrs={'class': 'form-control'}),
            'control_type': forms.Select(attrs={'class': 'form-control'}),
            'storage_unit': forms.Select(attrs={'class': 'form-control'}),
            'max_vehicle_access': forms.Select(attrs={'class': 'form-control'}),
            'capacity': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'sensors': forms.CheckboxSelectMultiple(), # Renderiza checkboxes em vez de um seletor simples
            'latitude': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.000001', 'placeholder': 'Ex: 38.7223 (Opcional)'}),
            'longitude': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.000001', 'placeholder': 'Ex: -9.1393 (Opcional)'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        control_type = cleaned_data.get('control_type')
        sensors = cleaned_data.get('sensors')

        if control_type == 'Controlled' and not sensors:
            self.add_error('sensors', "Controlled warehouses must have at least one associated sensor.")
        
        return cleaned_data

class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = ['license_plate', 'brand_model', 'vehicle_type']
        widgets = {
            'license_plate': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: AA-11-BB',
                'maxlength': '8',
                'pattern': r'[A-Za-z]{2}-[0-9]{2}-[A-Za-z]{2}',
                'style': 'text-transform: uppercase; font-family: monospace; font-weight: bold; letter-spacing: 1.5px;',
                'title': 'Formato obrigatório: AA-11-BB (2 letras - 2 números - 2 letras)',
                'id': 'id_license_plate'
            }),
            'brand_model': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Scania R450 / Renault Master'}),
            'vehicle_type': forms.Select(attrs={'class': 'form-control', 'id': 'id_vehicle_type'}),
        }

    def clean_license_plate(self):
        plate = self.cleaned_data.get('license_plate', '').strip().upper()
        
        # Se inserido sem hífen (ex: AA11BB), formata automaticamente
        if re.match(r'^[A-Z]{2}\d{2}[A-Z]{2}$', plate):
            plate = f"{plate[:2]}-{plate[2:4]}-{plate[4:6]}"
            
        pattern = r'^[A-Z]{2}-\d{2}-[A-Z]{2}$'
        if not re.match(pattern, plate):
            raise forms.ValidationError("A matrícula deve estar no formato oficial 'AA-11-BB' (2 letras, 2 números e 2 letras, ex: AA-01-BB).")
            
        return plate

# ----------------------------------------------------------------------
# 6. FORMULÁRIO DE MARKETPLACE
# ----------------------------------------------------------------------

class MarketplaceOrderForm(forms.ModelForm):
    class Meta:
        model = MarketplaceOrder
        fields = ['order_type', 'culture', 'quantity_kg', 'warehouse_location', 
                  'min_caliber', 'min_soluble_solids', 'min_quality_score', 'price_per_kg']
        widgets = {
            'order_type': forms.Select(attrs={'class': 'form-control'}),
            'culture': forms.Select(attrs={'class': 'form-control'}),
            'quantity_kg': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.01'}),
            'price_per_kg': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.01', 'id': 'id_price_per_kg_dynamic'}),
            'warehouse_location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Armazém Norte / Sede'}),
            
            # Quality Filters (Buy)
            'min_caliber': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.01', 'placeholder': 'Min mm'}),
            'min_soluble_solids': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.01', 'placeholder': 'Min Brix'}),
            'min_quality_score': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '10', 'placeholder': 'Min Score (1-10)'}),
        }
        labels = {
            'warehouse_location': 'Delivery/Pickup Location',
            'min_caliber': 'Minimum Caliber (> mm)',
            'min_soluble_solids': 'Minimum Brix (> Brix)',
            'min_quality_score': 'Minimum Quality (> 0-10)',
            'price_per_kg': 'Price (€/kg)',
        }



class RetailerMarketplaceOrderForm(MarketplaceOrderForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make quality fields mandatory for Retailers
        self.fields['min_caliber'].required = True
        self.fields['min_soluble_solids'].required = True
        self.fields['min_quality_score'].required = True

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
        fields = ['harvest_origin', 'quantity_kg', 'price_per_kg', 'warehouse_location',
                  'caliber', 'soluble_solids', 'quality_score']
        widgets = {
            'harvest_origin': forms.Select(attrs={'class': 'form-control', 'id': 'id_sell_harvest_origin'}),
            'quantity_kg': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01', 'id': 'id_sell_quantity_kg'}),
            'price_per_kg': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01', 'id': 'id_sell_price_per_kg'}),
            'warehouse_location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Armazém Central', 'id': 'id_sell_warehouse_location'}),
            
            # Read-only Auto-filled Quality Data
            'caliber': forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly', 'style': 'background-color: #e9ecef;', 'id': 'id_sell_caliber'}),
            'soluble_solids': forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly', 'style': 'background-color: #e9ecef;', 'id': 'id_sell_soluble_solids'}),
            'quality_score': forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly', 'style': 'background-color: #e9ecef;', 'id': 'id_sell_quality_score'}),
        }
        labels = {
            'harvest_origin': 'Origin Batch (Available Stock)',
            'quantity_kg': 'Selling Quantity (Kg)',
            'price_per_kg': 'Selling Price (€/kg)',
            'warehouse_location': 'Pickup Location',
            'caliber': 'Caliber (mm)',
            'soluble_solids': 'Brix',
            'quality_score': 'Score',
        }

    def clean_quantity_kg(self):
        val = self.cleaned_data.get('quantity_kg')
        if val is not None and val <= 0:
            raise forms.ValidationError('Selling quantity must be greater than 0.')
        return val

    def clean_price_per_kg(self):
        val = self.cleaned_data.get('price_per_kg')
        if val is not None and val <= 0:
            raise forms.ValidationError('Selling price must be greater than 0.')
        return val

    def clean(self):
        cleaned_data = super().clean()
        harvest = cleaned_data.get('harvest_origin')
        qty = cleaned_data.get('quantity_kg')
        price = cleaned_data.get('price_per_kg')
        
        # Validate quantity does not exceed stock
        if harvest and qty:
            if qty > harvest.current_stock_kg:
                raise forms.ValidationError(f"Quantity exceeds available stock ({harvest.current_stock_kg} kg).")
            
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
            'planned_pickup_date': 'ETA Pickup (Planned)',
            'planned_delivery_date': 'ETA Delivery (Planned)',
        }

class TransportDeliveryForm(forms.ModelForm):
    class Meta:
        model = MarketplaceOrder
        fields = ['transport_sensor_data']
        widgets = {
            'transport_sensor_data': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Cole aqui o JSON dos sensores...'})
        }
        labels = {
            'transport_sensor_data': 'Sensor Report (JSON)',
        }

# --- PROCESSOR FORMS ---

class ProcessorProcessingForm(forms.ModelForm):
    class Meta:
        model = MarketplaceOrder
        fields = ['packaging_type', 'preservation_treatment']
        labels = {
            'packaging_type': 'Packaging Type',
            'preservation_treatment': 'Preservation Treatment',
        }
        widgets = {
            'packaging_type': forms.Select(attrs={'class': 'form-control'}),
            'preservation_treatment': forms.Select(attrs={'class': 'form-control'}),
        }