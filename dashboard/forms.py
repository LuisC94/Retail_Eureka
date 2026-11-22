import re
from django import forms
from django.contrib.auth.models import User, Group
from .models import PlantationPlan, Harvest, QUALITY_SCORE_CHOICES, Sensor, Warehouse, SENSOR_TYPE_CHOICES, SoilCharacteristic, PlantationEvent, FertilizerSyntheticData, FertilizerOrganicData, SoilCorrectiveData, PestControlData, MachineryData, FuelData, ElectricEnergyData, IrrigationWaterData, ProductSubFamily, PlantationCrop, Vehicle, Route
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
    plantation = forms.ModelChoiceField(
        queryset=PlantationPlan.objects.all(), 
        label='Plano de Plantação',
        empty_label="--- Select Plantation ---",
        required=False,
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'harvest_plantation_select'})
    )
    
    subfamily = forms.ModelChoiceField(
        queryset=ProductSubFamily.objects.all(),
        label='Cultura / Variedade',
        empty_label="--- Select Culture ---",
        required=True,
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'harvest_subfamily_select'})
    )
    
    utilized_quantity_kg = forms.DecimalField(
        required=False,
        initial=0.0,
        label='Desperdício / Waste (Kg)',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'id': 'id_utilized_quantity_kg', 'placeholder': '0.0'})
    )
    
    firmness = forms.DecimalField(
        required=False,
        label='Firmeza (N / kg/cm²)',
        widget=forms.NumberInput(attrs={
            'class': 'form-control quality-input',
            'step': '0.1',
            'id': 'id_harvest_firmness',
            'placeholder': 'Ex: 35.0 (N)'
        })
    )
    
    soluble_solids = forms.DecimalField(
        required=False,
        label='Brix / Teor de Açúcar (°Bx)',
        widget=forms.NumberInput(attrs={
            'class': 'form-control quality-input',
            'step': '0.1',
            'id': 'id_harvest_brix',
            'placeholder': 'Ex: 14.5 (°Bx)'
        })
    )
    
    acidity = forms.DecimalField(
        required=False,
        label='Acidez (g/L / %)',
        widget=forms.NumberInput(attrs={
            'class': 'form-control quality-input',
            'step': '0.01',
            'id': 'id_harvest_acidity',
            'placeholder': 'Ex: 0.45 (g/L)'
        })
    )
    
    caliber = forms.DecimalField(
        required=False,
        label='Calibre (mm)',
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.1',
            'id': 'id_harvest_caliber',
            'placeholder': 'Ex: 75.0 (mm)'
        })
    )

    def clean_utilized_quantity_kg(self):
        val = self.cleaned_data.get('utilized_quantity_kg')
        if val is None:
            return 0.0
        return val

    def save(self, commit=True):
        instance = super().save(commit=False)
        subfamily = self.cleaned_data.get('subfamily')
        firmness = self.cleaned_data.get('firmness')
        brix = self.cleaned_data.get('soluble_solids')
        acidity = self.cleaned_data.get('acidity')
        culture_name = subfamily.name if subfamily else ""
        
        from dashboard.services.lc_service import calculate_harvest_quality
        quality_100 = calculate_harvest_quality(culture_name, firmness, brix, acidity)
        # Escala 0.0 a 10.0
        instance.avg_quality_score = round(quality_100 / 10.0, 2)
        
        if commit:
            instance.save()
        return instance

    class Meta:
        model = Harvest
        fields = [
            'plantation', 
            'subfamily',
            'harvest_date', 
            'harvest_quantity_kg', 
            'utilized_quantity_kg',
            'warehouse',
            'firmness',
            'soluble_solids',
            'acidity',
            'caliber',
        ]
        labels = {
            'plantation': 'Plano de Plantação',
            'subfamily': 'Cultura / Variedade',
            'harvest_date': 'Data da Colheita',
            'harvest_quantity_kg': 'Quantidade Colhida (Kg)',
            'utilized_quantity_kg': 'Desperdício / Waste (Kg)',
            'warehouse': 'Armazém de Destino',
            'firmness': 'Firmeza (N / kg/cm²)',
            'soluble_solids': 'Brix / Teor de Açúcar (°Bx)',
            'acidity': 'Acidez (g/L / %)',
            'caliber': 'Calibre (mm)',
        }
        widgets = {
            'harvest_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control', 'id': 'id_harvest_date'}),
            'plantation': forms.Select(attrs={'class': 'form-control', 'id': 'harvest_plantation_select'}),
            'subfamily': forms.Select(attrs={'class': 'form-control', 'id': 'harvest_subfamily_select'}),
            'harvest_quantity_kg': forms.NumberInput(attrs={'class': 'form-control', 'id': 'id_harvest_quantity_kg', 'placeholder': 'Ex: 500.0'}),
            'warehouse': forms.Select(attrs={'class': 'form-control', 'id': 'id_harvest_warehouse'}),
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
        fields = [
            'location', 'region', 'control_type', 
            'capacity', 'sensors', 'latitude', 'longitude',
            'meteo_source', 'json_fallback_mode', 'fixed_temperature', 'fixed_humidity'
        ]
        
        widgets = {
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Armazém Central Lisboa'}),
            'region': forms.Select(attrs={'class': 'form-control'}),
            'control_type': forms.Select(attrs={'class': 'form-control'}),
            'capacity': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'placeholder': 'Capacidade em Kg'}),
            'sensors': forms.CheckboxSelectMultiple(),
            'latitude': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.000001', 'placeholder': 'Ex: 38.7223 (Opcional)'}),
            'longitude': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.000001', 'placeholder': 'Ex: -9.1393 (Opcional)'}),
            'meteo_source': forms.Select(attrs={'class': 'form-control', 'id': 'id_meteo_source'}),
            'json_fallback_mode': forms.Select(attrs={'class': 'form-control', 'id': 'id_json_fallback_mode'}),
            'fixed_temperature': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'placeholder': 'Ex: 4.0'}),
            'fixed_humidity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'placeholder': 'Ex: 90.0'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        control_type = cleaned_data.get('control_type')
        sensors = cleaned_data.get('sensors')

        if control_type == 'Controlled' and not sensors:
            self.add_error('sensors', "Armazéns controlados devem ter pelo menos um sensor associado.")
        
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
# 6. FORMULÁRIOS DE MARKETPLACE (DESACOPLADOS / WEB SERVICE)
# ----------------------------------------------------------------------

class MarketplaceOrderForm(forms.Form):
    ORDER_TYPE_CHOICES = [
        ('BUY', 'Purchase Request (Compra)'),
        ('SELL', 'Export Offer (Venda/Exportação)'),
    ]
    order_type = forms.ChoiceField(
        choices=ORDER_TYPE_CHOICES, 
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Tipo de Pedido'
    )
    culture = forms.ModelChoiceField(
        queryset=ProductSubFamily.objects.all(),
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Cultura'
    )
    quantity_kg = forms.DecimalField(
        max_digits=10, decimal_places=2, required=True,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        label='Quantidade (Kg)'
    )
    price_per_kg = forms.DecimalField(
        max_digits=10, decimal_places=2, required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'id': 'id_price_per_kg_dynamic'}),
        label='Preço (€/kg)'
    )
    warehouse_location = forms.CharField(
        max_length=255, required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Armazém Norte / Sede'}),
        label='Localização para Entrega/Recolha'
    )
    
    # Quality Filters (Buy/Sell)
    min_caliber = forms.DecimalField(
        max_digits=5, decimal_places=2, required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Min mm'}),
        label='Calibre Mínimo (> mm)'
    )
    min_soluble_solids = forms.DecimalField(
        max_digits=5, decimal_places=2, required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Min Brix'}),
        label='Brix Mínimo (> Brix)'
    )
    min_quality_score = forms.DecimalField(
        max_digits=4, decimal_places=2, required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'max': '10', 'step': '0.1', 'placeholder': 'Min Score (1-10)'}),
        label='Qualidade Mínima (> 0-10)'
    )


class RetailerMarketplaceOrderForm(MarketplaceOrderForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['min_caliber'].required = True
        self.fields['min_soluble_solids'].required = True
        self.fields['min_quality_score'].required = True


class MarketSellOrderForm(forms.Form):
    harvest_origin = forms.ModelChoiceField(
        queryset=Harvest.objects.none(),
        required=True,
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_sell_harvest_origin'}),
        label='Lote de Origem (Stock Disponível)'
    )
    quantity_kg = forms.DecimalField(
        max_digits=10, decimal_places=2, required=True,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'id': 'id_sell_quantity_kg'}),
        label='Quantidade a Vender (Kg)'
    )
    price_per_kg = forms.DecimalField(
        max_digits=10, decimal_places=2, required=True,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'id': 'id_sell_price_per_kg'}),
        label='Preço de Venda (€/kg)'
    )
    warehouse_location = forms.CharField(
        max_length=255, required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Armazém Central', 'id': 'id_sell_warehouse_location'}),
        label='Local de Recolha'
    )
    caliber = forms.DecimalField(
        max_digits=5, decimal_places=2, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly', 'id': 'id_sell_caliber'}),
        label='Calibre (mm)'
    )
    soluble_solids = forms.DecimalField(
        max_digits=5, decimal_places=2, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly', 'id': 'id_sell_soluble_solids'}),
        label='Brix'
    )
    quality_score = forms.DecimalField(
        max_digits=4, decimal_places=2, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly', 'id': 'id_sell_quality_score'}),
        label='Score'
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['harvest_origin'].queryset = Harvest.objects.filter(producer=user).order_by('-harvest_date')

    def clean(self):
        cleaned_data = super().clean()
        harvest = cleaned_data.get('harvest_origin')
        qty = cleaned_data.get('quantity_kg')
        
        if harvest and qty:
            if qty > harvest.current_stock_kg:
                raise forms.ValidationError(f"Quantidade excede o stock disponível ({harvest.current_stock_kg} kg).")
            cleaned_data['culture'] = harvest.subfamily
            cleaned_data['order_type'] = 'SELL'
            
        return cleaned_data


# ----------------------------------------------------------------------
# 7. FORMS LOGISTICA TRANSPORTADOR & PROCESSADOR
# ----------------------------------------------------------------------

class TransportPlanForm(forms.Form):
    planned_pickup_date = forms.DateTimeField(
        required=True,
        widget=forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
        label='ETA Recolha (Planeado)'
    )
    planned_delivery_date = forms.DateTimeField(
        required=True,
        widget=forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
        label='ETA Entrega (Planeado)'
    )

class TransportDeliveryForm(forms.Form):
    transport_sensor_data = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Cole aqui o JSON dos sensores...'}),
        label='Relatório de Sensores (JSON)'
    )

# ----------------------------------------------------------------------
# RÓTULOS EM PORTUGUÊS (formulários do perfil Producer)
# Aplicados aos base_fields: não alteram modelos nem dados, só o texto mostrado.
# ----------------------------------------------------------------------
_PT_LABELS = {
    'PlantationPlanForm': {'location': 'Localização'},
    'PlantationCropForm': {
        'plantation': 'Plantação', 'subfamily': 'Cultura', 'avg_plant_age_years': 'Idade média das plantas (anos)',
        'rootstock': 'Porta-enxerto (se aplicável)', 'density_plants_ha': 'Densidade de plantação (plantas/m²)',
        'irrigation_system': 'Sistema de rega',
    },
    'PlantationEventForm': {
        'plantation': 'Plantação', 'subfamily': 'Cultura', 'event_date': 'Data do evento',
        'event_type': 'Tipo de evento', 'notes': 'Notas',
    },
    'HarvestForm': {
        'plantation': 'Plantação', 'subfamily': 'Cultura / variedade', 'harvest_date': 'Data da colheita',
        'harvest_quantity_kg': 'Quantidade colhida (kg)', 'utilized_quantity_kg': 'Desperdício (kg)',
        'warehouse': 'Armazém de destino', 'firmness': 'Firmeza (N)', 'soluble_solids': 'Brix (°Bx)',
        'acidity': 'Acidez (g/L ou %)', 'caliber': 'Calibre (mm)',
    },
    'FertilizerSyntheticForm': {
        'commercial_product': 'Produto comercial', 'form_npk': 'Fórmula (NPK, etc.)', 'n_content': 'Teor de N (%)',
        'p2o5_content': 'Teor de P₂O₅ (%)', 'k2o_content': 'Teor de K₂O (%)', 'total_dose_kg_ha_year': 'Dose total (kg/ha/ano)',
        'num_applications': 'N.º de aplicações', 'application_season': 'Época de aplicação (mês)',
    },
    'FertilizerOrganicForm': {
        'organic_fertilizer_type': 'Tipo de fertilizante orgânico', 'origin': 'Origem (pecuária, composto, etc.)',
        'n_content_kgt': 'Teor de N (kg/t ou %)', 'p_content_kgt': 'Teor de P (kg/t ou %)', 'k_content_kgt': 'Teor de K (kg/t ou %)',
        'dose_tha_year': 'Dose (t/ha/ano)', 'application_mode': 'Modo de aplicação',
    },
    'SoilCorrectiveForm': {
        'commercial_product': 'Produto comercial', 'corrective_type': 'Tipo (calcário, dolomite, gesso, etc.)',
        'caco3_content': 'Equivalente em CaCO₃ (%)', 'dose_kg_ha_year': 'Dose (kg/ha/ano)',
        'frequency_years': 'Frequência (anos)', 'observations': 'Observações',
    },
    'PestControlForm': {
        'commercial_product': 'Produto comercial', 'active_substance': 'Substância ativa',
        'pest_type': 'Tipo (fungicida, inseticida, etc.)', 'dose_per_application': 'Dose por aplicação (kg ou L/ha)',
        'num_applications_year': 'N.º de aplicações por ano', 'application_mode': 'Modo de aplicação',
    },
    'MachineryForm': {
        'machinery_type': 'Tipo de máquina', 'main_operation': 'Operação principal', 'hours_per_year': 'Horas por ano',
        'power': 'Potência (kW ou CV)', 'observations': 'Observações',
    },
    'FuelForm': {
        'fuel_type': 'Tipo de combustível', 'annual_consumption': 'Consumo anual', 'unit': 'Unidade',
        'main_usage_season': 'Época de maior utilização', 'notes': 'Notas',
    },
    'ElectricEnergyForm': {
        'main_usage': 'Utilização principal', 'total_consumption_kwh_year': 'Consumo total (kWh/ano)', 'percent_grid': '% Rede elétrica',
        'percent_photovoltaic': '% Fotovoltaico (autoconsumo)', 'percent_other_renewable': '% Outras renováveis', 'notes': 'Notas',
    },
    'IrrigationWaterForm': {
        'water_source': 'Origem da água', 'volume_m3_year': 'Volume (m³/ano)', 'extraction_method': 'Método de captação',
        'pumping_height_m': 'Altura de bombagem (m)', 'irrigation_system': 'Sistema de rega', 'estimated_efficiency': 'Eficiência estimada (%)',
    },
}
for _form_name, _labels in _PT_LABELS.items():
    _form_cls = globals().get(_form_name)
    if _form_cls is None:
        continue
    for _field_name, _label in _labels.items():
        if _field_name in _form_cls.base_fields:
            _form_cls.base_fields[_field_name].label = _label
