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
    commercial_product = models.CharField(max_length=100, verbose_name="Produto Comercial")
    form_npk = models.CharField(max_length=50, verbose_name="Forma (NPK, etc.)")
    n_content = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Teor N (%)", null=True, blank=True)
    p2o5_content = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Teor P₂O₅ (%)", null=True, blank=True)
    k2o_content = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Teor K₂O (%)", null=True, blank=True)
    total_dose_kg_ha_year = models.DecimalField(max_digits=8, decimal_places=2, verbose_name="Dose Total (kg/ha/ano)")
    num_applications = models.IntegerField(verbose_name="Nº de Aplicações")
    application_season = models.CharField(max_length=50, verbose_name="Épocas de Aplicação (mês)")
    class Meta: db_table = 'event_fertilizer_synthetic'
    def __str__(self): return f"{self.commercial_product} ({self.n_content}N)"
        
class FertilizerOrganicData(models.Model):
    organic_fertilizer_type = models.CharField(max_length=100, verbose_name="Tipo de Fertilizante Orgânico")
    origin = models.CharField(max_length=50, verbose_name="Origem (pecuária, composto, etc.)")
    n_content_kgt = models.DecimalField(max_digits=6, decimal_places=2, verbose_name="Teor N (kg/t ou %)")
    p_content_kgt = models.DecimalField(max_digits=6, decimal_places=2, verbose_name="Teor P (kg/t ou %)")
    k_content_kgt = models.DecimalField(max_digits=6, decimal_places=2, verbose_name="Teor K (kg/t ou %)")
    dose_tha_year = models.DecimalField(max_digits=8, decimal_places=2, verbose_name="Dose (t/ha/ano)")
    application_mode = models.CharField(max_length=100, verbose_name="Modo de Aplicação")
    class Meta: db_table = 'event_fertilizer_organic'
    def __str__(self): return f"{self.organic_fertilizer_type} ({self.origin})"

class SoilCorrectiveData(models.Model):
    commercial_product = models.CharField(max_length=100, verbose_name="Produto Comercial")
    corrective_type = models.CharField(max_length=100, verbose_name="Tipo (calcário, dolomite, gesso, etc.)")
    caco3_content = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Teor CaCO₃ equivalente (%)")
    dose_kg_ha_year = models.DecimalField(max_digits=8, decimal_places=2, verbose_name="Dose (kg/ha/ano)")
    frequency_years = models.IntegerField(verbose_name="Frequência (anos)")
    observations = models.TextField(blank=True, null=True, verbose_name="Observações")
    class Meta: db_table = 'event_soil_corrective'
    def __str__(self): return f"{self.commercial_product} ({self.corrective_type})"

class PestControlData(models.Model):
    commercial_product = models.CharField(max_length=100, verbose_name="Produto Comercial")
    active_substance = models.CharField(max_length=100, verbose_name="Substância Ativa")
    pest_type = models.CharField(max_length=100, verbose_name="Tipo (fungicida, inseticida, etc.)")
    dose_per_application = models.CharField(max_length=50, verbose_name="Dose (kg ou L/ha/aplicação)") # CharField to allow units if needed, or strict Decimal? User said "kg ou L", let's stick to Char or Decimal. Let's use Char for flexibility as unit is mixed, or Decimal if strictly number. User prompt: "Dose (kg ou L/ha/aplicação)". Let's use CharField to be safe with "10 kg" or just "10". Actually, usually these are numbers. Let's use Decimal for calculation potential, but name implies unit. Let's use CharField max 50 to be safe.
    num_applications_year = models.IntegerField(verbose_name="Nº aplicações/ano")
    application_mode = models.CharField(max_length=100, verbose_name="Modo de aplicação")
    class Meta: db_table = 'event_pest_control'
    def __str__(self): return f"{self.commercial_product} ({self.pest_type})"

class MachineryData(models.Model):
    machinery_type = models.CharField(max_length=100, verbose_name="Tipo de maquinaria")
    main_operation = models.CharField(max_length=100, verbose_name="Principal operação")
    hours_per_year = models.DecimalField(max_digits=8, decimal_places=2, verbose_name="Nº horas/ano")
    power = models.CharField(max_length=50, verbose_name="Potência (kW ou CV)")
    observations = models.TextField(blank=True, null=True, verbose_name="Observações")
    class Meta: db_table = 'event_machinery'
    def __str__(self): return f"{self.machinery_type} - {self.main_operation}"

class FuelData(models.Model):
    fuel_type = models.CharField(max_length=100, verbose_name="Tipo de combustível")
    annual_consumption = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Consumo anual")
    unit = models.CharField(max_length=20, verbose_name="Unidade")
    main_usage_season = models.CharField(max_length=100, verbose_name="Época principal de uso")
    notes = models.TextField(blank=True, null=True, verbose_name="Notas")
    class Meta: db_table = 'event_fuel'
    def __str__(self): return f"{self.fuel_type} ({self.annual_consumption} {self.unit})"

class ElectricEnergyData(models.Model):
    main_usage = models.CharField(max_length=100, verbose_name="Principal uso")
    total_consumption_kwh_year = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Consumo total (kWh/ano)")
    percent_grid = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="% rede elétrica")
    percent_photovoltaic = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="% fotovoltaico próprio")
    percent_other_renewable = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="% outra renovável")
    notes = models.TextField(blank=True, null=True, verbose_name="Notas")
    class Meta: db_table = 'event_electric_energy'
    def __str__(self): return f"Energia: {self.main_usage}"

class IrrigationWaterData(models.Model):
    water_source = models.CharField(max_length=100, verbose_name="Fonte de água")
    volume_m3_year = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Volume (m³/ano)")
    extraction_method = models.CharField(max_length=100, verbose_name="Método de captação")
    pumping_height_m = models.DecimalField(max_digits=6, decimal_places=2, verbose_name="Altura de bombagem (m)", null=True, blank=True)
    irrigation_system = models.CharField(max_length=100, verbose_name="Sistema de rega")
    estimated_efficiency = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Eficiência estimada (%)", null=True, blank=True)
    class Meta: db_table = 'event_irrigation_water'
    def __str__(self): return f"Água: {self.water_source} ({self.volume_m3_year} m3)"

# ----------------------------------------------------------------------
# 3. MODELO DE PLANTAÇÃO (ÚNICO E CORRIGIDO)
# ----------------------------------------------------------------------

class PlantationPlan(models.Model):
    plantation_id = models.AutoField(primary_key=True)
    producer = models.ForeignKey(User, on_delete=models.CASCADE) 
    product = models.ForeignKey(Product, on_delete=models.PROTECT) 

    # --- Campos Existentes ---
    quantity_of_seeds = models.IntegerField(verbose_name="Nº de Sementes Plantadas")
    production_type = models.CharField(max_length=20, choices=PRODUCTION_TYPE_CHOICES, verbose_name="Tipo de Produção")
    chemical_use = models.CharField(max_length=5, choices=CHEMICAL_USE_CHOICES, verbose_name="Uso de Químicos")
    area = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Área (m²)")
    location = models.CharField(max_length=100)
    plantation_date = models.DateField(verbose_name="Data de Plantação")
    
    # --- 11 CARACTERÍSTICAS DO POMAR/SOLO ---
    total_area_ha = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Área total do pomar (m²)", blank=True, null=True)
    avg_plant_age_years = models.IntegerField(verbose_name="Idade média das plantas (anos)", blank=True, null=True)
    kiwi_variety = models.CharField(max_length=50, choices=KIWI_VARIETY_CHOICES, verbose_name="Variedade de Kiwi", blank=True, null=True)
    rootstock = models.CharField(max_length=100, blank=True, null=True, verbose_name="Porta-enxerto (se aplicável)")
    density_plants_ha = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Densidade de plantação (plantas/m²)", blank=True, null=True)
    conduct_system = models.CharField(max_length=50, choices=CONDUCT_SYSTEM_CHOICES, verbose_name="Sistema de condução", blank=True, null=True)
    soil_type = models.CharField(max_length=50, choices=SOIL_TYPE_CHOICES, verbose_name="Tipo de solo", blank=True, null=True)
    ph_soil = models.DecimalField(max_digits=4, decimal_places=2, verbose_name="pH do solo", blank=True, null=True)
    organic_matter_percent = models.DecimalField(max_digits=4, decimal_places=2, verbose_name="Matéria orgânica do solo (%)", blank=True, null=True)
    water_regime = models.CharField(max_length=20, choices=WATER_REGIME_CHOICES, verbose_name="Regime hídrico", blank=True, null=True)
    irrigation_system = models.CharField(max_length=50, choices=IRRIGATION_SYSTEM_CHOICES, verbose_name="Tipo de sistema de rega", blank=True, null=True)
    
    # M2M com Tabela de Valores do Solo
    soil_characteristics = models.ManyToManyField(
        SoilCharacteristic, 
        through='PlantationSoilValue', 
        related_name='plantations'
    )
    
    class Meta: db_table = 'plantation_plan'
    def __str__(self): return f"Plano {self.plantation_id} - Produto: {self.product.name}"

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
        verbose_name="Plano de Plantação"
    )
    event_date = models.DateField(verbose_name="Data do Evento")
    event_type = models.CharField(max_length=50, choices=EVENT_TYPE_CHOICES, verbose_name="Tipo de Evento")
    notes = models.TextField(blank=True, null=True, verbose_name="Notas/Descrição")

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
    harvest_date = models.DateField(verbose_name="Data de Colheita")
    harvest_quantity_kg = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Quantidade Colhida (Kg)")
    avg_quality_score = models.IntegerField(choices=QUALITY_SCORE_CHOICES, verbose_name="Qualidade Média (1-10)")
    utilized_quantity_kg = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Quantidade Aproveitada (Kg)")
    
    class Meta: db_table = 'harvest_records'
    def __str__(self): return f"Colheita {self.pk} - Plano {self.plantation.plantation_id if self.plantation else 'N/A'}"