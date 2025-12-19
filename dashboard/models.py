from django.db import models
from django.contrib.auth.models import User

# ----------------------------------------------------------------------
# 1. CONSTANTES E CHOICES (CONSOLIDADOS)
# ----------------------------------------------------------------------

PRODUCTION_TYPE_CHOICES = [('Modern', 'Moderna'), ('Traditional', 'Tradicional')]
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

# ----------------------------------------------------------------------
# 2. MODELOS DE DETALHE (ORDEM CORRIGIDA PARA FKs)
# ----------------------------------------------------------------------

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone_number = models.CharField(max_length=20, blank=True, null=True, verbose_name="Telemóvel")
    address = models.CharField(max_length=255, blank=True, null=True, verbose_name="Morada Completa")
    class Meta: db_table = 'user_profile'
    def __str__(self): return f"Perfil de {self.user.username}"

class Product(models.Model):
    product_id = models.AutoField(primary_key=True) 
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Preço de Venda (€)")
    producer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    class Meta: db_table = 'products' 
    def __str__(self): return f"{self.product_id} - {self.name}"

class ProductSubFamily(models.Model):
    FRUIT_TYPE_CHOICES = [('Kiwi', 'Kiwi'), ('Apple', 'Maçã')]
    
    subfamily_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, verbose_name="Subfamília")
    fruit_type = models.CharField(max_length=50, choices=FRUIT_TYPE_CHOICES, verbose_name="Tipo de Fruta")

    class Meta: db_table = 'product_subfamilies'
    def __str__(self): return f"{self.name} ({self.fruit_type})"
    
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
    owner = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'groups__name': 'Producer'}, verbose_name="Dono/Perfil")
    warehouse_id = models.AutoField(primary_key=True)
    location = models.CharField(max_length=255, verbose_name="Localização")
    control_type = models.CharField(max_length=20, choices=CONTROL_TYPE_CHOICES, verbose_name="Tipo de Armazém")
    capacity = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Capacidade (m² ou Kg)")
    sensors = models.ManyToManyField(Sensor, blank=True, verbose_name="Sensores Instalados")
    class Meta: db_table = 'warehouses'
    def __str__(self): return f"Armazém {self.warehouse_id} - {self.location}"

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
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    # subfamilies removed: moved to separate model PlantationCrop 

    # --- Campos Existentes ---
    plantation_name = models.CharField(max_length=100, verbose_name="Nome da Plantação", blank=True, null=True)
    quantity_of_trees = models.IntegerField(verbose_name="Quantidade de Árvores")
    production_type = models.CharField(max_length=20, choices=PRODUCTION_TYPE_CHOICES, verbose_name="Tipo de Produção")
    chemical_use = models.CharField(max_length=5, choices=CHEMICAL_USE_CHOICES, verbose_name="Uso de Químicos")
    area = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Área (m²)")
    location = models.CharField(max_length=100)
    plantation_date = models.DateField(verbose_name="Data de Plantação")
    
    # --- 11 CARACTERÍSTICAS DO POMAR/SOLO ---
    total_area_ha = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Área total do pomar (m²)", blank=True, null=True)
    # avg_plant_age_years removed
    # kiwi_variety removed
    # rootstock removed
    # density_plants_ha removed
    conduct_system = models.CharField(max_length=50, choices=CONDUCT_SYSTEM_CHOICES, verbose_name="Sistema de condução", blank=True, null=True)
    soil_type = models.CharField(max_length=50, choices=SOIL_TYPE_CHOICES, verbose_name="Tipo de solo", blank=True, null=True)
    ph_soil = models.DecimalField(max_digits=4, decimal_places=2, verbose_name="pH do solo", blank=True, null=True)
    organic_matter_percent = models.DecimalField(max_digits=4, decimal_places=2, verbose_name="Matéria orgânica do solo (%)", blank=True, null=True)
    water_regime = models.CharField(max_length=20, choices=WATER_REGIME_CHOICES, verbose_name="Regime hídrico", blank=True, null=True)
    # irrigation_system removed
    
    # M2M com Tabela de Valores do Solo
    soil_characteristics = models.ManyToManyField(
        SoilCharacteristic, 
        through='PlantationSoilValue', 
        related_name='plantations'
    )
    
    class Meta: db_table = 'plantation_plan'
    def __str__(self): 
        if self.product:
            return f"Plano {self.plantation_id} - Produto: {self.product.name}"
        else:
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
    harvest_quantity_kg = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Harvest Quantity (Kg)")
    delivered_quantity_kg = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Delivered Quantity (Kg)")
    avg_quality_score = models.IntegerField(choices=QUALITY_SCORE_CHOICES, verbose_name="Average Quality Score (1-10)")
    utilized_quantity_kg = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Utilized Quantity (Kg)")
    
    class Meta: db_table = 'harvest_records'
    def __str__(self): return f"Colheita {self.pk} - Plano {self.plantation.plantation_id if self.plantation else 'N/A'}"