from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

# ----------------------------------------------------------------------
# 1. CONSTANTES E CHOICES (CONSOLIDADOS)
# ----------------------------------------------------------------------

PRODUCTION_TYPE_CHOICES = [
    ('conventional', 'Convencional'),
    ('integrated', 'Produção Integrada'),
    ('organic', 'Biológica'),
    ('regenerative', 'Regenerativa'),
    ('precision', 'Precisão'),
    ('agroforestry', 'Agroflorestal'),
]
CHEMICAL_USE_CHOICES = [('Yes', 'Sim'), ('No', 'Não')]
QUALITY_SCORE_CHOICES = [(i, str(i)) for i in range(1, 11)]

# Choices para Plantação/Pomar
KIWI_VARIETY_CHOICES = [('Hayward', 'Hayward'), ('Actinidia deliciosa', 'Actinidia deliciosa')]
CONDUCT_SYSTEM_CHOICES = [('T-bar', 'T-bar'), ('Pergola', 'Pérgola')]
SOIL_TYPE_CHOICES = [('Clay', 'Argiloso'), ('Sand', 'Arenoso'), ('Loam', 'Franco')]
WATER_REGIME_CHOICES = [('Total', 'Rega Total'), ('Supp', 'Suplementar'), ('Dry', 'Sequeiro')]
IRRIGATION_SYSTEM_CHOICES = [('Drip', 'Gota-a-gota'), ('Sprinkler', 'Aspersão')]

# Choices para o modelo PlantationEvent
EVENT_TYPE_CHOICES = [
    ('Fert_Min', 'Fertilizantes (sintéticos minerais)'),
    ('Fert_Org', 'Fertilizantes (orgânicos)'),
    ('Soil_Corr', 'Corretivos do solo'),
    ('Pest', 'Produtos fitofarmacêuticos'),
    ('Machine_Hrs', 'Horas de utilização da maquinaria'),
    ('Fuel', 'Combustíveis'),
    ('Electric', 'Energia elétrica'),
    ('Water', 'Água de rega'),
]

# Choices para Armazéns e Sensores
SENSOR_TYPE_CHOICES = [('Temperature', 'Temperatura'), ('Humidity', 'Humidade'), ('Light', 'Luminosidade'), ('Gas', 'Gás/CO2')]
CONTROL_TYPE_CHOICES = [('Controlled', 'Controlado'), ('Non-Controlled', 'Não Controlado')]
METEO_SOURCE_CHOICES = [
    ('FIXED', 'Valores Fixos'),
    ('IPMA', 'IPMA (Estação Regional)'),
    ('JSON', 'Ficheiro JSON de Sensores'),
]
JSON_FALLBACK_CHOICES = [
    ('NONE', 'Nenhum / Sem Fallback'),
    ('FIXED', 'Valores Fixos'),
    ('IPMA', 'IPMA (Estação Regional)'),
]
REGION_CHOICES = [
    ('PT-NL', 'Norte Litoral (Muito húmido, temperaturas moderadas)'),
    ('PT-NI', 'Norte Interior (Invernos frios, verões quentes)'),
    ('PT-CL', 'Centro Litoral (Clima marítimo temperado)'),
    ('PT-CI', 'Centro Interior (Grande amplitude térmica)'),
    ('PT-LVT', 'Lisboa e Vale do Tejo (Mediterrânico moderado)'),
    ('PT-AL', 'Alentejo (Muito quente e seco no verão)'),
    ('PT-ALG', 'Algarve (Mediterrânico costeiro)'),
    ('PT-SM', 'Serra da Estrela e montanhas (Frio e neve no inverno)'),
    ('PT-MAD', 'Madeira (Subtropical oceânico)'),
    ('PT-ACO', 'Açores (Oceânico húmido)'),
]

# --- CONSTANTES LOGÍSTICAS DE ACONDICIONAMENTO E FROTAS ---
STORAGE_UNIT_CHOICES = [
    ('CRATES', 'Grades (20 Kg / Caixa)'),
    ('PALLETS', 'Paletes (800 Kg / Euro-Palete)'),
]

VEHICLE_ACCESS_CHOICES = [
    ('VAN', 'Apenas Carrinha Ligeira (<= 3.5t)'),
    ('RIGID_TRUCK', 'Até Camião Ligeiro (<= 12t)'),
    ('HEAVY_TIR', 'Todos / Camião TIR (<= 40t)'),
]

CRATE_WEIGHT_KG = 20.0
PALLET_WEIGHT_KG = 800.0
CRATES_PER_PALLET = 40

VEHICLE_TYPE_CHOICES = [
    ('VAN', 'Carrinha Ligeira (3.5t)'),
    ('RIGID_TRUCK', 'Camião Ligeiro (12t)'),
    ('HEAVY_TIR', 'Camião TIR (40t)'),
]

VEHICLE_DEFAULT_CAPACITIES = {
    'VAN': 1200.0,
    'RIGID_TRUCK': 5000.0,
    'HEAVY_TIR': 24000.0,
}

class UserProfile(models.Model):
    PRODUCER_TYPE_CHOICES = [
        ('manual', 'Manual/Tradicional'),
        ('instant', 'Compra Direta (Makro)'),
        ('contract', 'Contrato Futuro'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone_number = models.CharField(max_length=20, blank=True, null=True, verbose_name="Telemóvel")
    address = models.CharField(max_length=255, blank=True, null=True, verbose_name="Morada Completa")
    producer_type = models.CharField(
        max_length=20, 
        choices=PRODUCER_TYPE_CHOICES, 
        default='manual', 
        verbose_name="Tipo de Produtor"
    )
    buyer_agent_active = models.BooleanField(default=False, verbose_name="Agente de Compras Ativo")
    
    class Meta: db_table = 'user_profile'
    def __str__(self): return f"Perfil de {self.user.username} ({self.get_producer_type_display()})"
    
    def save(self, *args, **kwargs):
        # Se for um produtor do tipo Contrato, acrescentamos automaticamente o sufixo -Contract
        if self.producer_type == 'contract':
            user_obj = self.user
            if user_obj and not user_obj.username.endswith('-Contract'):
                user_obj.username = f"{user_obj.username}-Contract"
                user_obj.save()
        super().save(*args, **kwargs)

class ProductSubFamily(models.Model):
    FRUIT_TYPE_CHOICES = [('Kiwi', 'Kiwi'), ('Apple', 'Maçã')]
    
    subfamily_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, verbose_name="Subfamília")
    fruit_type = models.CharField(max_length=50, choices=FRUIT_TYPE_CHOICES, verbose_name="Tipo de Fruta")
    default_shelf_life_days = models.IntegerField(default=10, verbose_name="Tempo de Vida Padrão (Dias)")
    lifecycle_presets = models.JSONField(default=dict, blank=True, null=True, verbose_name="Lifecycle Presets (Biological Coefficients)")

    class Meta:
        db_table = 'product_subfamilies'
        verbose_name = "Subfamília / Cultura"
        verbose_name_plural = "Subfamílias / Culturas"

    def __str__(self):
        return f"{self.name} ({self.fruit_type})"


class SoilCharacteristic(models.Model):
    category = models.CharField(max_length=100, verbose_name="Categoria")
    sub_category = models.CharField(max_length=100, verbose_name="Sub-Categoria")
    unit = models.CharField(max_length=50, verbose_name="Unidade de Medida") 
    class Meta:
        db_table = 'soil_characteristic'
        unique_together = ('category', 'sub_category', 'unit')
    def __str__(self): return f"{self.category}: {self.sub_category} ({self.unit})"

class Sensor(models.Model):
    sensor_id = models.AutoField(primary_key=True)
    brand = models.CharField(max_length=100, verbose_name="Marca do Sensor")
    sensor_type = models.CharField(max_length=50, choices=SENSOR_TYPE_CHOICES, verbose_name="Tipo de Sensor")
    class Meta: db_table = 'sensors'
    def __str__(self): return f"{self.sensor_id} - {self.brand} ({self.get_sensor_type_display()})"
    
class Warehouse(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Dono/Perfil")
    warehouse_id = models.AutoField(primary_key=True)
    location = models.CharField(max_length=255, verbose_name="Localização")
    region = models.CharField(max_length=10, choices=REGION_CHOICES, default='PT-LVT', verbose_name="Região Climática")
    control_type = models.CharField(max_length=20, choices=CONTROL_TYPE_CHOICES, verbose_name="Tipo de Armazém")
    storage_unit = models.CharField(max_length=20, choices=STORAGE_UNIT_CHOICES, default='PALLETS', verbose_name="Acondicionamento de Stock")
    max_vehicle_access = models.CharField(max_length=20, choices=VEHICLE_ACCESS_CHOICES, default='HEAVY_TIR', verbose_name="Acesso Máximo de Veículo")
    capacity = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Capacidade (m² ou Kg)")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, verbose_name="Latitude")
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, verbose_name="Longitude")
    sensors = models.ManyToManyField(Sensor, blank=True, verbose_name="Sensores Instalados")
    meteo_source = models.CharField(max_length=20, choices=METEO_SOURCE_CHOICES, default='FIXED', verbose_name="Fonte Meteorológica / Sensores")
    json_fallback_mode = models.CharField(max_length=20, choices=JSON_FALLBACK_CHOICES, default='FIXED', verbose_name="Modo de Preenchimento de Falhas (Fallback)")
    fixed_temperature = models.DecimalField(max_digits=5, decimal_places=2, default=4.0, null=True, blank=True, verbose_name="Temperatura Fixa (°C)")
    fixed_humidity = models.DecimalField(max_digits=5, decimal_places=2, default=90.0, null=True, blank=True, verbose_name="Humidade Fixa (%)")
    class Meta: db_table = 'warehouses'
    def __str__(self): return f"Armazém {self.warehouse_id} - {self.location} ({self.get_storage_unit_display()})"

# --- NOVOS MODELOS DE DETALHE DE EVENTO (Devem vir antes de PlantationEvent) ---
class FertilizerSyntheticData(models.Model):
    commercial_product = models.CharField(max_length=100, verbose_name="Commercial Product")
    form_npk = models.CharField(max_length=50, verbose_name="Form (NPK, etc.)")
    n_content = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="N Content (%)", null=True, blank=True)
    p2o5_content = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="P2O5 Content (%)", null=True, blank=True)
    k2o_content = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="K2O Content (%)", null=True, blank=True)
    total_dose_kg_ha_year = models.DecimalField(max_digits=8, decimal_places=2, verbose_name="Total Dose (kg/ha/year)")
    num_applications = models.IntegerField(verbose_name="No. of Applications")
    application_season = models.CharField(max_length=50, verbose_name="Application Season (month)")
    class Meta: db_table = 'event_fertilizer_synthetic'
    def __str__(self): return f"{self.commercial_product} ({self.n_content}N)"
        
class FertilizerOrganicData(models.Model):
    organic_fertilizer_type = models.CharField(max_length=100, verbose_name="Organic Fertilizer Type")
    origin = models.CharField(max_length=50, verbose_name="Origin (livestock, compost, etc.)")
    n_content_kgt = models.DecimalField(max_digits=6, decimal_places=2, verbose_name="N Content (kg/t or %)")
    p_content_kgt = models.DecimalField(max_digits=6, decimal_places=2, verbose_name="P Content (kg/t or %)")
    k_content_kgt = models.DecimalField(max_digits=6, decimal_places=2, verbose_name="K Content (kg/t or %)")
    dose_tha_year = models.DecimalField(max_digits=8, decimal_places=2, verbose_name="Dose (t/ha/year)")
    application_mode = models.CharField(max_length=100, verbose_name="Application Mode")
    class Meta: db_table = 'event_fertilizer_organic'
    def __str__(self): return f"{self.organic_fertilizer_type} ({self.origin})"

class SoilCorrectiveData(models.Model):
    commercial_product = models.CharField(max_length=100, verbose_name="Commercial Product")
    corrective_type = models.CharField(max_length=100, verbose_name="Type (limestone, dolomite, gypsum, etc.)")
    caco3_content = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="CaCO3 Equivalent Content (%)")
    dose_kg_ha_year = models.DecimalField(max_digits=8, decimal_places=2, verbose_name="Dose (kg/ha/year)")
    frequency_years = models.IntegerField(verbose_name="Frequency (years)")
    observations = models.TextField(blank=True, null=True, verbose_name="Observations")
    class Meta: db_table = 'event_soil_corrective'
    def __str__(self): return f"{self.commercial_product} ({self.corrective_type})"

class PestControlData(models.Model):
    commercial_product = models.CharField(max_length=100, verbose_name="Commercial Product")
    active_substance = models.CharField(max_length=100, verbose_name="Active Substance")
    pest_type = models.CharField(max_length=100, verbose_name="Type (fungicide, insecticide, etc.)")
    dose_per_application = models.CharField(max_length=50, verbose_name="Dose (kg or L/ha/application)") # CharField to allow units if needed, or strict Decimal? User said "kg ou L", let's stick to Char or Decimal. Let's use Char for flexibility as unit is mixed, or Decimal if strictly number. User prompt: "Dose (kg ou L/ha/aplicação)". Let's use CharField to be safe with "10 kg" or just "10". Actually, usually these are numbers. Let's use Decimal for calculation potential, but name implies unit. Let's use CharField max 50 to be safe.
    num_applications_year = models.IntegerField(verbose_name="No. Applications/Year")
    application_mode = models.CharField(max_length=100, verbose_name="Application Mode")
    class Meta: db_table = 'event_pest_control'
    def __str__(self): return f"{self.commercial_product} ({self.pest_type})"

class MachineryData(models.Model):
    machinery_type = models.CharField(max_length=100, verbose_name="Machinery Type")
    main_operation = models.CharField(max_length=100, verbose_name="Main Operation")
    hours_per_year = models.DecimalField(max_digits=8, decimal_places=2, verbose_name="Hours/Year")
    power = models.CharField(max_length=50, verbose_name="Power (kW or CV)")
    observations = models.TextField(blank=True, null=True, verbose_name="Observations")
    class Meta: db_table = 'event_machinery'
    def __str__(self): return f"{self.machinery_type} - {self.main_operation}"

class FuelData(models.Model):
    fuel_type = models.CharField(max_length=100, verbose_name="Fuel Type")
    annual_consumption = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Annual Consumption")
    unit = models.CharField(max_length=20, verbose_name="Unit")
    main_usage_season = models.CharField(max_length=100, verbose_name="Main Usage Season")
    notes = models.TextField(blank=True, null=True, verbose_name="Notes")
    class Meta: db_table = 'event_fuel'
    def __str__(self): return f"{self.fuel_type} ({self.annual_consumption} {self.unit})"

class ElectricEnergyData(models.Model):
    main_usage = models.CharField(max_length=100, verbose_name="Main Usage")
    total_consumption_kwh_year = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Total Consumption (kWh/year)")
    percent_grid = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="% Grid")
    percent_photovoltaic = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="% Photovoltaic (Self)")
    percent_other_renewable = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="% Other Renewable")
    notes = models.TextField(blank=True, null=True, verbose_name="Notes")
    class Meta: db_table = 'event_electric_energy'
    def __str__(self): return f"Energia: {self.main_usage}"

class IrrigationWaterData(models.Model):
    water_source = models.CharField(max_length=100, verbose_name="Water Source")
    volume_m3_year = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Volume (m3/year)")
    extraction_method = models.CharField(max_length=100, verbose_name="Extraction Method")
    pumping_height_m = models.DecimalField(max_digits=6, decimal_places=2, verbose_name="Pumping Height (m)", null=True, blank=True)
    irrigation_system = models.CharField(max_length=100, verbose_name="Irrigation System")
    estimated_efficiency = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Estimated Efficiency (%)", null=True, blank=True)
    class Meta: db_table = 'event_irrigation_water'
    def __str__(self): return f"Água: {self.water_source} ({self.volume_m3_year} m3)"

# ----------------------------------------------------------------------
# 3. MODELO DE PLANTAÇÃO (ÚNICO E CORRIGIDO)
# ----------------------------------------------------------------------

class PlantationPlan(models.Model):
    plantation_id = models.AutoField(primary_key=True)
    producer = models.ForeignKey(User, on_delete=models.CASCADE) 

    # --- Campos Existentes ---
    plantation_name = models.CharField(max_length=100, verbose_name="Nome da Plantação", blank=True, null=True)
    quantity_of_trees = models.IntegerField(verbose_name="Quantidade de Árvores")
    production_type = models.CharField(max_length=20, choices=PRODUCTION_TYPE_CHOICES, verbose_name="Tipo de Agricultura")
    chemical_use = models.CharField(max_length=5, choices=CHEMICAL_USE_CHOICES, verbose_name="Uso de Químicos")
    area = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Área (m²)")
    location = models.CharField(max_length=100)
    plantation_date = models.DateField(verbose_name="Data de Plantação")
    
    # --- 11 CARACTERÍSTICAS DO POMAR/SOLO ---
    total_area_ha = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Área total do pomar (m²)", blank=True, null=True)
    conduct_system = models.CharField(max_length=50, choices=CONDUCT_SYSTEM_CHOICES, verbose_name="Sistema de condução", blank=True, null=True)
    soil_type = models.CharField(max_length=50, choices=SOIL_TYPE_CHOICES, verbose_name="Tipo de solo", blank=True, null=True)
    ph_soil = models.DecimalField(max_digits=4, decimal_places=2, verbose_name="pH do solo", blank=True, null=True)
    organic_matter_percent = models.DecimalField(max_digits=4, decimal_places=2, verbose_name="Matéria orgânica do solo (%)", blank=True, null=True)
    water_regime = models.CharField(max_length=20, choices=WATER_REGIME_CHOICES, verbose_name="Regime hídrico", blank=True, null=True)
    
    # M2M com Tabela de Valores do Solo
    soil_characteristics = models.ManyToManyField(
        SoilCharacteristic, 
        through='PlantationSoilValue', 
        related_name='plantations'
    )
    
    class Meta: db_table = 'plantation_plan'
    def __str__(self): 
        if self.plantation_name:
            return self.plantation_name
        return f"Plano {self.plantation_id}"

# --- NOVO MODELO: Detalhes da Cultura na Plantação ---
class PlantationCrop(models.Model):
    plantation = models.ForeignKey(PlantationPlan, on_delete=models.CASCADE, related_name='crops', verbose_name="Plano de Plantação")
    subfamily = models.ForeignKey(ProductSubFamily, on_delete=models.CASCADE, verbose_name="Cultura (Subfamília)")
    
    avg_plant_age_years = models.IntegerField(verbose_name="Average Age of Plants (years)", blank=True, null=True)
    rootstock = models.CharField(max_length=100, blank=True, null=True, verbose_name="Rootstock (if applicable)")
    density_plants_ha = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Plantation Density (plants/m²)", blank=True, null=True)
    irrigation_system = models.CharField(max_length=50, choices=IRRIGATION_SYSTEM_CHOICES, verbose_name="Irrigation System Type", blank=True, null=True)

    class Meta:
        db_table = 'plantation_crops'
        unique_together = ('plantation', 'subfamily') # Unique pair
    
    def __str__(self):
        return f"{self.plantation.plantation_id} - {self.subfamily.name}"

# --- Tabela de Valores do Solo (Tabela de Junção) ---
class PlantationSoilValue(models.Model):
    plantation = models.ForeignKey(PlantationPlan, on_delete=models.CASCADE, related_name='soil_values')
    characteristic = models.ForeignKey(SoilCharacteristic, on_delete=models.CASCADE)
    value = models.DecimalField(max_digits=10, decimal_places=4, verbose_name="Valor Registado")

    class Meta: 
        db_table = 'plantation_soil_value'
        unique_together = ('plantation', 'characteristic')
    def __str__(self): return f"{self.plantation.plantation_id} - {self.characteristic.sub_category}: {self.value}"


# ----------------------------------------------------------------------
# 4. MODELOS DE EVENTOS (PlatationEvent e Harvest)
# ----------------------------------------------------------------------
class PlantationEvent(models.Model):
    event_id = models.AutoField(primary_key=True)
    plantation = models.ForeignKey(
        PlantationPlan, 
        on_delete=models.CASCADE, 
        related_name='events',
        verbose_name="Plantation Plan"
    )
    event_date = models.DateField(verbose_name="Event Date")
    event_type = models.CharField(max_length=50, choices=EVENT_TYPE_CHOICES, verbose_name="Event Type")
    subfamily = models.ForeignKey(ProductSubFamily, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Culture (Subfamily)")
    notes = models.TextField(blank=True, null=True, verbose_name="Notes/Description")

    # CHAVES ESTRANGEIRAS PARA OS DETALHES
    fertilizer_synth = models.ForeignKey(FertilizerSyntheticData, on_delete=models.SET_NULL, null=True, blank=True, related_name='events_synth')
    fertilizer_org = models.ForeignKey(FertilizerOrganicData, on_delete=models.SET_NULL, null=True, blank=True, related_name='events_org')
    soil_corrective = models.ForeignKey(SoilCorrectiveData, on_delete=models.SET_NULL, null=True, blank=True, related_name='events_soil')
    pest_control = models.ForeignKey(PestControlData, on_delete=models.SET_NULL, null=True, blank=True, related_name='events_pest')
    machinery = models.ForeignKey(MachineryData, on_delete=models.SET_NULL, null=True, blank=True, related_name='events_machinery')
    fuel = models.ForeignKey(FuelData, on_delete=models.SET_NULL, null=True, blank=True, related_name='events_fuel')
    electric = models.ForeignKey(ElectricEnergyData, on_delete=models.SET_NULL, null=True, blank=True, related_name='events_electric')
    water = models.ForeignKey(IrrigationWaterData, on_delete=models.SET_NULL, null=True, blank=True, related_name='events_water')
    
    class Meta: db_table = 'plantation_events'
    def __str__(self): return f"Evento {self.get_event_type_display()} em {self.event_date}"

class Harvest(models.Model):
    harvest_id = models.AutoField(primary_key=True)
    plantation = models.ForeignKey( 
        PlantationPlan, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='harvest_records', # Adicionado related_name para evitar conflitos
        verbose_name="Plano de Plantação"
    )
    
    producer = models.ForeignKey(User, on_delete=models.CASCADE) 
    subfamily = models.ForeignKey(ProductSubFamily, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Cultura (Subfamília)") 
    harvest_date = models.DateField(verbose_name="Harvest Date")
    expiration_date = models.DateField(null=True, blank=True, verbose_name="Expiration Date (Validade)")
    harvest_quantity_kg = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Harvest Quantity (Kg)")
    delivered_quantity_kg = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Delivered Quantity (Kg)")
    avg_quality_score = models.DecimalField(max_digits=5, decimal_places=2, default=10.0, verbose_name="Score de Qualidade (Calculado)")
    utilized_quantity_kg = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, verbose_name="Waste (Kg)")
    
    # Medições Físico-Químicas da Colheita (Cálculo Automático de Qualidade)
    firmness = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, verbose_name="Firmeza (N / kg/cm²)")
    soluble_solids = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Teor de Açúcar / Brix (°Bx)")
    acidity = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True, verbose_name="Acidez (g/L / %)")
    caliber = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Calibre (mm)")
    
    warehouse = models.ForeignKey(Warehouse, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Stored In (Warehouse)")
    
    class Meta: db_table = 'harvest_records'
    
    @property
    def current_stock_kg(self):
        from decimal import Decimal
        h_qty = self.harvest_quantity_kg if self.harvest_quantity_kg is not None else Decimal('0.0')
        u_qty = self.utilized_quantity_kg if self.utilized_quantity_kg is not None else Decimal('0.0')
        return Decimal(str(h_qty)) - Decimal(str(u_qty))

    def __str__(self): return f"Colheita {self.pk} - {self.subfamily.name if self.subfamily else 'N/A'} ({self.current_stock_kg}kg disp)"
    
    @property
    def pk_str(self): return str(self.pk)

class Vehicle(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='vehicles', limit_choices_to={'groups__name': 'Transporter'}, verbose_name="Proprietário")
    license_plate = models.CharField(max_length=20, verbose_name="Matrícula")
    brand_model = models.CharField(max_length=100, verbose_name="Marca/Modelo")
    vehicle_type = models.CharField(max_length=20, choices=VEHICLE_TYPE_CHOICES, default='RIGID_TRUCK', verbose_name="Tipo de Veículo")
    capacity_kg = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Capacidade (Kg)")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'vehicles'

    def save(self, *args, **kwargs):
        if self.vehicle_type in VEHICLE_DEFAULT_CAPACITIES:
            self.capacity_kg = VEHICLE_DEFAULT_CAPACITIES[self.vehicle_type]
        elif not self.capacity_kg:
            self.capacity_kg = 5000.0
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_vehicle_type_display()} - {self.brand_model} ({self.license_plate}) - {self.capacity_kg}kg"

    @property
    def capacity_crates(self):
        return int(float(self.capacity_kg) / CRATE_WEIGHT_KG) if self.capacity_kg else 0

    @property
    def capacity_pallets(self):
        return round(float(self.capacity_kg) / PALLET_WEIGHT_KG, 1) if self.capacity_kg else 0


class Route(models.Model):
    ROUTE_STATUS_CHOICES = [
        ('PENDING', 'Pendente (Criada Automática)'),
        ('ACCEPTED', 'Aceite pelo Transportador'),
        ('PLANNED', 'Planeada'),
        ('IN_TRANSIT', 'Em Trânsito'),
        ('DELIVERED', 'Entregue'),
    ]
    transporter = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='routes', limit_choices_to={'groups__name': 'Transporter'}, verbose_name="Transportador")
    vehicle = models.ForeignKey(Vehicle, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Veículo")
    route_date = models.DateField(default=timezone.now, db_index=True, verbose_name="Data da Rota")
    status = models.CharField(max_length=20, choices=ROUTE_STATUS_CHOICES, default='PENDING', db_index=True, verbose_name="Estado da Rota")
    optimized_path = models.TextField(null=True, blank=True, verbose_name="Caminho Otimizado (Pontos)")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'routes'

    @property
    def total_weight_kg(self):
        if hasattr(self, 'optimized_path') and self.optimized_path:
            import re
            weights = re.findall(r':\s*([\d\.]+)\s*kg', self.optimized_path, re.IGNORECASE)
            if weights:
                try:
                    return round(sum(float(w) for w in weights), 1)
                except Exception:
                    pass
        return 0.0

    @property
    def total_crates(self):
        return int(float(self.total_weight_kg) / CRATE_WEIGHT_KG) if self.total_weight_kg else 0

    @property
    def total_pallets(self):
        return round(float(self.total_weight_kg) / PALLET_WEIGHT_KG, 1) if self.total_weight_kg else 0

    @property
    def orders_count(self):
        if hasattr(self, 'optimized_path') and self.optimized_path:
            import re
            deals = re.findall(r'(?:Deal|Carga)\s*#([^\s\(\]]+)', self.optimized_path, re.IGNORECASE)
            if deals:
                return len(deals)
            parts = [p for p in self.optimized_path.split('->') if p.strip()]
            return len(parts) if parts else 1
        return 1



class WarehouseSensorReading(models.Model):
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='sensor_readings')
    date = models.DateField(verbose_name="Data da Leitura")
    temperature = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Temperatura (°C)")
    humidity = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Humidade (%)")
    ethylene = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True, verbose_name="Etileno (ppm)")

    class Meta:
        db_table = 'warehouse_sensor_readings'
        unique_together = ('warehouse', 'date')
        ordering = ['-date']

    def __str__(self):
        return f"Leitura {self.date} - Armazém {self.warehouse.warehouse_id}"


class ConsolidatedStock(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='consolidated_stocks')
    culture = models.ForeignKey(ProductSubFamily, on_delete=models.CASCADE)
    warehouse_location = models.CharField(max_length=255, verbose_name="Localização do Armazém")
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0.0, verbose_name="Quantidade em Stock (Kg)")
    
    # Average Quality Metrics
    avg_caliber = models.DecimalField(max_digits=5, decimal_places=2, default=0.0, verbose_name="Calibre Médio (mm)")
    avg_soluble_solids = models.DecimalField(max_digits=5, decimal_places=2, default=0.0, verbose_name="Sólidos Solúveis Médios (Brix)")
    avg_quality_score = models.DecimalField(max_digits=4, decimal_places=1, default=0.0, verbose_name="Score de Qualidade Médio")

    class Meta:
        db_table = 'consolidated_stock'
        unique_together = ('owner', 'culture', 'warehouse_location')

    def __str__(self):
        return f"Stock de {self.owner.username} - {self.culture.name} ({self.quantity}kg) em {self.warehouse_location}"


class HistoricalSalesData(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='historical_sales', verbose_name="Utilizador")
    culture = models.ForeignKey(ProductSubFamily, on_delete=models.CASCADE, verbose_name="Cultura")
    date = models.DateField(verbose_name="Data da Venda")
    sales_quantity_kg = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Vendas em Kg")
    price_per_kg = models.DecimalField(max_digits=8, decimal_places=2, verbose_name="Preço de Venda (€/Kg)")

    class Meta:
        db_table = 'historical_sales_data'
        unique_together = ('owner', 'culture', 'date')
        verbose_name = "Histórico de Vendas"
        verbose_name_plural = "Históricos de Vendas"

    def __str__(self):
        return f"{self.owner.username} - {self.culture.name} ({self.date}): {self.sales_quantity_kg}kg"


class DemandForecast(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='demand_forecasts', verbose_name="Utilizador")
    culture = models.ForeignKey(ProductSubFamily, on_delete=models.CASCADE, verbose_name="Cultura")
    date = models.DateField(verbose_name="Data da Previsão")
    predicted_quantity_kg = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Quantidade Prevista (Kg)")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado Em")

    class Meta:
        db_table = 'demand_forecast'
        unique_together = ('owner', 'culture', 'date')
        verbose_name = "Previsão de Procura"
        verbose_name_plural = "Previsões de Procura"

    def __str__(self):
        return f"Previsão {self.owner.username} - {self.culture.name} ({self.date}): {self.predicted_quantity_kg}kg"


class TrainedModel(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trained_models', verbose_name="Utilizador")
    culture = models.ForeignKey(ProductSubFamily, on_delete=models.CASCADE, verbose_name="Cultura")
    model_type = models.CharField(max_length=50, verbose_name="Tipo de Modelo") # 'sales_mlp' ou 'buyer_agent'
    file_name = models.CharField(max_length=255, verbose_name="Nome do Ficheiro") # ex: 'sales_mlp.joblib', 'buyer_agent_actor.pth'
    file_data = models.BinaryField(verbose_name="Dados do Ficheiro (Binário)")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado Em")

    class Meta:
        db_table = 'trained_model'
        unique_together = ('owner', 'culture', 'model_type', 'file_name')
        verbose_name = "Modelo de IA Treinado"
        verbose_name_plural = "Modelos de IA Treinados"

    def __str__(self):
        return f"{self.owner.username} - {self.culture.name} ({self.model_type} - {self.file_name})"


class StoreProcessorAssociation(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pendente'),
        ('APPROVED', 'Aprovado'),
        ('REJECTED', 'Rejeitado'),
    ]
    processor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='store_associations', limit_choices_to={'groups__name': 'Processor'}, verbose_name="Processador")
    retailer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='processor_associations', limit_choices_to={'groups__name': 'Retailer'}, verbose_name="Retalhista/Loja")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', verbose_name="Estado")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'store_processor_associations'
        unique_together = ('processor', 'retailer')
        verbose_name = "Associação de Loja"
        verbose_name_plural = "Associações de Lojas"

    def __str__(self):
        return f"{self.processor.username} -> {self.retailer.username} ({self.status})"