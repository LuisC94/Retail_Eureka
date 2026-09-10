from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator

# ----------------------------------------------------------------------
# 1. CONSTANTES E CHOICES (CONSOLIDADOS)
# ----------------------------------------------------------------------

PRODUCTION_TYPE_CHOICES = [
    ('conventional', 'Conventional'),
    ('integrated', 'Integrated Production'),
    ('organic', 'Organic'),
    ('regenerative', 'Regenerative'),
    ('precision', 'Precision'),
    ('agroforestry', 'Agroforestry'),
]
CHEMICAL_USE_CHOICES = [('Yes', 'Yes'), ('No', 'No')]
QUALITY_SCORE_CHOICES = [(i, str(i)) for i in range(1, 11)]

# Choices para Plantação/Pomar
KIWI_VARIETY_CHOICES = [('Hayward', 'Hayward'), ('Actinidia deliciosa', 'Actinidia deliciosa')]
CONDUCT_SYSTEM_CHOICES = [('T-bar', 'T-bar'), ('Pergola', 'Pergola')]
SOIL_TYPE_CHOICES = [('Clay', 'Clay'), ('Sand', 'Sand'), ('Loam', 'Loam')]
WATER_REGIME_CHOICES = [('Total', 'Total Irrigation'), ('Supp', 'Supplemental'), ('Dry', 'Rainfed')]
IRRIGATION_SYSTEM_CHOICES = [('Drip', 'Drip Irrigation'), ('Sprinkler', 'Sprinkler')]

# Choices para o modelo PlantationEvent
EVENT_TYPE_CHOICES = [
    ('Fert_Min', 'Fertilizers (synthetic minerals)'),
    ('Fert_Org', 'Fertilizers (organic)'),
    ('Soil_Corr', 'Soil Correctives'),
    ('Pest', 'Phytopharmaceutical Products'),
    ('Machine_Hrs', 'Machinery Hours'),
    ('Fuel', 'Fuels'),
    ('Electric', 'Electric Energy'),
    ('Water', 'Irrigation Water'),
]

# Choices para Armazéns e Sensores
SENSOR_TYPE_CHOICES = [('Temperature', 'Temperature'), ('Humidity', 'Humidity'), ('Light', 'Light'), ('Gas', 'Gas/CO2')]
CONTROL_TYPE_CHOICES = [('Controlled', 'Controlled'), ('Non-Controlled', 'Uncontrolled')]
REGION_CHOICES = [
    ('PT-NL', 'PT-NL: North Coast (Very humid, moderate temperatures)'),
    ('PT-NI', 'PT-NI: Inland North (Cold winters, hot summers)'),
    ('PT-CL', 'PT-CL: Center Coast (Temperate maritime climate)'),
    ('PT-CI', 'PT-CI: Center Inland (Large thermal amplitude)'),
    ('PT-LVT', 'PT-LVT: Lisbon and Tagus Valley (Moderate Mediterranean)'),
    ('PT-AL', 'PT-AL: Alentejo (Very hot and dry in summer)'),
    ('PT-ALG', 'PT-ALG: Algarve (Coastal Mediterranean)'),
    ('PT-SM', 'PT-SM: Serra da Estrela and mountains (Cold and snowy in winter)'),
    ('PT-MAD', 'PT-MAD: Madeira (Oceanic subtropical)'),
    ('PT-ACO', 'PT-ACO: Azores (Oceanic humid)'),
]

class UserProfile(models.Model):
    PRODUCER_TYPE_CHOICES = [
        ('manual', 'Manual/Traditional'),
        ('instant', 'Direct Purchase (Makro)'),
        ('contract', 'Future Contract'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone_number = models.CharField(max_length=20, blank=True, null=True, verbose_name="Phone Number")
    address = models.CharField(max_length=255, blank=True, null=True, verbose_name="Full Address")
    producer_type = models.CharField(
        max_length=20, 
        choices=PRODUCER_TYPE_CHOICES, 
        default='manual', 
        verbose_name="Producer Type"
    )
    buyer_agent_active = models.BooleanField(default=False, verbose_name="Shopping Agent Active")
    
    class Meta: db_table = 'user_profile'
    def __str__(self): return f"Profile of {self.user.username} ({self.get_producer_type_display()})"
    
    def save(self, *args, **kwargs):
        # If it's a contract producer type, we automatically append the -Contract suffix
        if self.producer_type == 'contract':
            user_obj = self.user
            if user_obj and not user_obj.username.endswith('-Contract'):
                user_obj.username = f"{user_obj.username}-Contract"
                user_obj.save()
        super().save(*args, **kwargs)

class Product(models.Model):
    product_id = models.AutoField(primary_key=True) 
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Selling Price (€)")
    producer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    class Meta: db_table = 'products' 
    def __str__(self): return f"{self.product_id} - {self.name}"

class ProductSubFamily(models.Model):
    FRUIT_TYPE_CHOICES = [('Kiwi', 'Kiwi'), ('Apple', 'Apple')]
    
    subfamily_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, verbose_name="Subfamily")
    fruit_type = models.CharField(max_length=50, choices=FRUIT_TYPE_CHOICES, verbose_name="Fruit Type")
    lifecycle_presets = models.JSONField(default=dict, blank=True, null=True, verbose_name="Lifecycle Presets (Biological Coefficients)")

    class Meta: db_table = 'product_subfamilies'
    def __str__(self): return f"{self.name} ({self.fruit_type})"

class CultureShelfLife(models.Model):
    subfamily = models.OneToOneField(ProductSubFamily, on_delete=models.CASCADE, related_name='shelf_life', verbose_name="Culture (Subfamily)")
    default_shelf_life_days = models.IntegerField(default=10, verbose_name="Default Shelf Life (Days)")

    class Meta:
        db_table = 'culture_shelf_life'
        verbose_name = "Culture Shelf Life"
        verbose_name_plural = "Culture Shelf Lives"

    def __str__(self):
        return f"{self.subfamily.name} - {self.default_shelf_life_days} days"

class SupplyContract(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('fulfilled', 'Fulfilled'),
        ('cancelled', 'Cancelled'),
    ]
    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='buyer_contracts', verbose_name="Buyer (Retailer/Processor)")
    producer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='producer_contracts', verbose_name="Virtual Producer (Type 3)")
    subfamily = models.ForeignKey(ProductSubFamily, on_delete=models.CASCADE, verbose_name="Culture (Subfamily)")
    quantity_kg = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Contracted Quantity (Kg)")
    delivery_date = models.DateField(verbose_name="Planned Delivery Date (Day X)")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Contract Status")
    warehouse_location = models.CharField(max_length=255, blank=True, null=True, verbose_name="Delivery Location (Warehouse)")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'supply_contract'
        verbose_name = "Supply Contract"
        verbose_name_plural = "Supply Contracts"

    def __str__(self):
        return f"Contract #{self.pk} ({self.subfamily.name}) - {self.buyer.username} & {self.producer.username}"
    
class SoilCharacteristic(models.Model):
    category = models.CharField(max_length=100, verbose_name="Category")
    sub_category = models.CharField(max_length=100, verbose_name="Sub-Category")
    unit = models.CharField(max_length=50, verbose_name="Measurement Unit")
    class Meta:
        db_table = 'soil_characteristic'
        unique_together = ('category', 'sub_category', 'unit')
    def __str__(self): return f"{self.category}: {self.sub_category} ({self.unit})"

class Sensor(models.Model):
    sensor_id = models.AutoField(primary_key=True)
    brand = models.CharField(max_length=100, verbose_name="Sensor Brand")
    sensor_type = models.CharField(max_length=50, choices=SENSOR_TYPE_CHOICES, verbose_name="Sensor Type")
    class Meta: db_table = 'sensors'
    def __str__(self): return f"{self.sensor_id} - {self.brand} ({self.get_sensor_type_display()})"
    
class Warehouse(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'groups__name': 'Producer'}, verbose_name="Owner/Profile")
    warehouse_id = models.AutoField(primary_key=True)
    location = models.CharField(max_length=255, verbose_name="Location")
    region = models.CharField(max_length=10, choices=REGION_CHOICES, default='PT-LVT', verbose_name="Climate Region")
    control_type = models.CharField(max_length=20, choices=CONTROL_TYPE_CHOICES, verbose_name="Warehouse Type")
    capacity = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Capacity (m² or Kg)")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, verbose_name="Latitude")
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, verbose_name="Longitude")
    sensors = models.ManyToManyField(Sensor, blank=True, verbose_name="Installed Sensors")
    class Meta: db_table = 'warehouses'
    def __str__(self): return f"Warehouse {self.warehouse_id} - {self.location} - {self.get_control_type_display()}"

# --- NOVOS MODELOS DE DETALHE DE EVENTO (Devem vir antes de PlantationEvent) ---
class FertilizerSyntheticData(models.Model):
    commercial_product = models.CharField(max_length=100, verbose_name="Commercial Product")
    form_npk = models.CharField(max_length=50, verbose_name="Form (NPK, etc.)")
    n_content = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="N Content (%)", null=True, blank=True, validators=[MinValueValidator(0, 'N Content cannot be negative.')])
    p2o5_content = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="P2O5 Content (%)", null=True, blank=True, validators=[MinValueValidator(0, 'P2O5 Content cannot be negative.')])
    k2o_content = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="K2O Content (%)", null=True, blank=True, validators=[MinValueValidator(0, 'K2O Content cannot be negative.')])
    total_dose_kg_ha_year = models.DecimalField(max_digits=8, decimal_places=2, verbose_name="Total Dose (kg/ha/year)", validators=[MinValueValidator(0, 'Total Dose cannot be negative.')])
    num_applications = models.IntegerField(verbose_name="No. of Applications", validators=[MinValueValidator(0, 'Number of applications cannot be negative.')])
    application_season = models.CharField(max_length=50, verbose_name="Application Season (month)")
    class Meta: db_table = 'event_fertilizer_synthetic'
    def __str__(self): return f"{self.commercial_product} ({self.n_content}N)"
        
class FertilizerOrganicData(models.Model):
    organic_fertilizer_type = models.CharField(max_length=100, verbose_name="Organic Fertilizer Type")
    origin = models.CharField(max_length=50, verbose_name="Origin (livestock, compost, etc.)")
    n_content_kgt = models.DecimalField(max_digits=6, decimal_places=2, verbose_name="N Content (kg/t or %)", validators=[MinValueValidator(0)])
    p_content_kgt = models.DecimalField(max_digits=6, decimal_places=2, verbose_name="P Content (kg/t or %)", validators=[MinValueValidator(0)])
    k_content_kgt = models.DecimalField(max_digits=6, decimal_places=2, verbose_name="K Content (kg/t or %)", validators=[MinValueValidator(0)])
    dose_tha_year = models.DecimalField(max_digits=8, decimal_places=2, verbose_name="Dose (t/ha/year)", validators=[MinValueValidator(0)])
    application_mode = models.CharField(max_length=100, verbose_name="Application Mode")
    class Meta: db_table = 'event_fertilizer_organic'
    def __str__(self): return f"{self.organic_fertilizer_type} ({self.origin})"

class SoilCorrectiveData(models.Model):
    commercial_product = models.CharField(max_length=100, verbose_name="Commercial Product")
    corrective_type = models.CharField(max_length=100, verbose_name="Type (limestone, dolomite, gypsum, etc.)")
    caco3_content = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="CaCO3 Equivalent Content (%)", validators=[MinValueValidator(0), MaxValueValidator(100)])
    dose_kg_ha_year = models.DecimalField(max_digits=8, decimal_places=2, verbose_name="Dose (kg/ha/year)", validators=[MinValueValidator(0)])
    frequency_years = models.IntegerField(verbose_name="Frequency (years)", validators=[MinValueValidator(0)])
    observations = models.TextField(blank=True, null=True, verbose_name="Observations")
    class Meta: db_table = 'event_soil_corrective'
    def __str__(self): return f"{self.commercial_product} ({self.corrective_type})"

class PestControlData(models.Model):
    commercial_product = models.CharField(max_length=100, verbose_name="Commercial Product")
    active_substance = models.CharField(max_length=100, verbose_name="Active Substance")
    pest_type = models.CharField(max_length=100, verbose_name="Type (fungicide, insecticide, etc.)")
    dose_per_application = models.CharField(max_length=50, verbose_name="Dose (kg or L/ha/application)") # CharField to allow units if needed, or strict Decimal? User said "kg ou L", let's stick to Char or Decimal. Let's use Char for flexibility as unit is mixed, or Decimal if strictly number. User prompt: "Dose (kg ou L/ha/aplicação)". Let's use CharField to be safe with "10 kg" or just "10". Actually, usually these are numbers. Let's use Decimal for calculation potential, but name implies unit. Let's use CharField max 50 to be safe.
    num_applications_year = models.IntegerField(verbose_name="No. Applications/Year", validators=[MinValueValidator(0, 'Number of applications cannot be negative.')])
    application_mode = models.CharField(max_length=100, verbose_name="Application Mode")
    class Meta: db_table = 'event_pest_control'
    def __str__(self): return f"{self.commercial_product} ({self.pest_type})"

class MachineryData(models.Model):
    machinery_type = models.CharField(max_length=100, verbose_name="Machinery Type")
    main_operation = models.CharField(max_length=100, verbose_name="Main Operation")
    hours_per_year = models.DecimalField(max_digits=8, decimal_places=2, verbose_name="Hours/Year", validators=[MinValueValidator(0, 'Hours/Year cannot be negative.')],)
    power = models.CharField(max_length=50, verbose_name="Power (kW or CV)", validators=[RegexValidator(regex=r'^\d+(\.\d+)?\s*(kW|CV)$',message="Power must be a positive number followed by 'kW' or 'CV' (e.g., '15.5kW', '100 CV').",code='invalid_power')],)
    observations = models.TextField(blank=True, null=True, verbose_name="Observations")
    class Meta: db_table = 'event_machinery'
    def __str__(self): return f"{self.machinery_type} - {self.main_operation}"

class FuelData(models.Model):
    fuel_type = models.CharField(max_length=100, verbose_name="Fuel Type")
    annual_consumption = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Annual Consumption", validators=[MinValueValidator(0)])
    unit = models.CharField(max_length=20, verbose_name="Unit")
    main_usage_season = models.CharField(max_length=100, verbose_name="Main Usage Season")
    notes = models.TextField(blank=True, null=True, verbose_name="Notes")
    class Meta: db_table = 'event_fuel'
    def __str__(self): return f"{self.fuel_type} ({self.annual_consumption} {self.unit})"

class ElectricEnergyData(models.Model):
    main_usage = models.CharField(max_length=100, verbose_name="Main Usage")
    total_consumption_kwh_year = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Total Consumption (kWh/year)", validators=[MinValueValidator(0)])
    percent_grid = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="% Grid", validators=[MinValueValidator(0), MaxValueValidator(100)])
    percent_photovoltaic = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="% Photovoltaic (Self)", validators=[MinValueValidator(0), MaxValueValidator(100)])
    percent_other_renewable = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="% Other Renewable", validators=[MinValueValidator(0), MaxValueValidator(100)])
    notes = models.TextField(blank=True, null=True, verbose_name="Notes")
    class Meta: db_table = 'event_electric_energy'
    def __str__(self): return f"Energy: {self.main_usage}"

class IrrigationWaterData(models.Model):
    water_source = models.CharField(max_length=100, verbose_name="Water Source")
    volume_m3_year = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Volume (m3/year)", validators=[MinValueValidator(0)])
    extraction_method = models.CharField(max_length=100, verbose_name="Extraction Method")
    pumping_height_m = models.DecimalField(max_digits=6, decimal_places=2, verbose_name="Pumping Height (m)", null=True, blank=True, validators=[MinValueValidator(0)])
    irrigation_system = models.CharField(max_length=100, verbose_name="Irrigation System")
    estimated_efficiency = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Estimated Efficiency (%)", null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    class Meta: db_table = 'event_irrigation_water'
    def __str__(self): return f"Water: {self.water_source} ({self.volume_m3_year} m3)"

# ----------------------------------------------------------------------
# 3. MODELO DE PLANTAÇÃO (ÚNICO E CORRIGIDO)
# ----------------------------------------------------------------------

class PlantationPlan(models.Model):
    plantation_id = models.AutoField(primary_key=True)
    producer = models.ForeignKey(User, on_delete=models.CASCADE) 
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    # subfamilies removed: moved to separate model PlantationCrop 

    # --- Campos Existentes ---
    plantation_name = models.CharField(max_length=100, verbose_name="Plantation Name")
    quantity_of_trees = models.IntegerField(verbose_name="Number of Trees")
    production_type = models.CharField(max_length=20, choices=PRODUCTION_TYPE_CHOICES, verbose_name="Agriculture Type")
    chemical_use = models.CharField(max_length=5, choices=CHEMICAL_USE_CHOICES, verbose_name="Chemical Use")
    area = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Area (m²)")
    location = models.CharField(max_length=100)
    plantation_date = models.DateField(verbose_name="Plantation Date")
    
    # --- 11 CARACTERÍSTICAS DO POMAR/SOLO ---
    total_area_ha = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Total orchard area (m²)", blank=True, null=True)
    # avg_plant_age_years removed
    # kiwi_variety removed
    # rootstock removed
    # density_plants_ha removed
    conduct_system = models.CharField(max_length=50, choices=CONDUCT_SYSTEM_CHOICES, verbose_name="Conduct System", blank=True, null=True)
    soil_type = models.CharField(max_length=50, choices=SOIL_TYPE_CHOICES, verbose_name="Soil Type", blank=True, null=True)
    ph_soil = models.DecimalField(max_digits=4, decimal_places=2, verbose_name="Soil pH", blank=True, null=True)
    organic_matter_percent = models.DecimalField(max_digits=4, decimal_places=2, verbose_name="Soil Organic Matter (%)", blank=True, null=True)
    water_regime = models.CharField(max_length=20, choices=WATER_REGIME_CHOICES, verbose_name="Water Regime", blank=True, null=True)
    # irrigation_system removed
    
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
        elif self.product:
            return f"Plan {self.plantation_id} - Product: {self.product.name}"
        else:
            return f"Plan {self.plantation_id}"

# --- NOVO MODELO: Detalhes da Cultura na Plantação ---
class PlantationCrop(models.Model):
    plantation = models.ForeignKey(PlantationPlan, on_delete=models.CASCADE, related_name='crops', verbose_name="Plantation Plan")
    subfamily = models.ForeignKey(ProductSubFamily, on_delete=models.CASCADE, verbose_name="Culture (Subfamily)")
    
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
    value = models.DecimalField(max_digits=10, decimal_places=4, verbose_name="Recorded Value")

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
    def __str__(self): return f"Event {self.get_event_type_display()} on {self.event_date}"

class Harvest(models.Model):
    harvest_id = models.AutoField(primary_key=True)
    plantation = models.ForeignKey( 
        PlantationPlan, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='harvest_records',
        verbose_name="Plantation Plan"
    )
    
    producer = models.ForeignKey(User, on_delete=models.CASCADE) 
    subfamily = models.ForeignKey(ProductSubFamily, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Culture (Subfamily)") 
    harvest_date = models.DateField(verbose_name="Harvest Date")
    expiration_date = models.DateField(null=True, blank=True, verbose_name="Expiration Date (Shelf Life)")
    harvest_quantity_kg = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Harvest Quantity (Kg)")
    delivered_quantity_kg = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Delivered Quantity (Kg)")
    avg_quality_score = models.IntegerField(choices=QUALITY_SCORE_CHOICES, verbose_name="Average Quality Score (1-10)")
    utilized_quantity_kg = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Waste (Kg)")
    
    # New fields requested by user
    caliber = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Caliber (mm)")
    soluble_solids = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Soluble Solids (Brix)")
    
    warehouse = models.ForeignKey(Warehouse, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Stored In Warehouse")
    
    class Meta: db_table = 'harvest_records'
    
    @property
    def current_stock_kg(self):
        return self.harvest_quantity_kg - self.utilized_quantity_kg

    def __str__(self): return f"Harvest {self.pk} - {self.subfamily.name if self.subfamily else 'N/A'} ({self.current_stock_kg}kg available)"
    
    @property
    def pk_str(self): return str(self.pk)

class Vehicle(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='vehicles', limit_choices_to={'groups__name': 'Transporter'}, verbose_name="Owner")
    license_plate = models.CharField(max_length=20, verbose_name="License Plate")
    brand_model = models.CharField(max_length=100, verbose_name="Brand/Model")
    capacity_kg = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Capacity (Kg)")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'vehicles'

    def __str__(self):
        return f"{self.brand_model} ({self.license_plate}) - {self.capacity_kg}kg"


class Route(models.Model):
    ROUTE_STATUS_CHOICES = [
        ('PENDING', 'Pending (Auto-Created)'),
        ('ACCEPTED', 'Accepted by Transporter'),
        ('PLANNED', 'Planned'),
        ('IN_TRANSIT', 'In Transit'),
        ('DELIVERED', 'Delivered'),
    ]
    transporter = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='routes', limit_choices_to={'groups__name': 'Transporter'}, verbose_name="Transporter")
    vehicle = models.ForeignKey(Vehicle, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Vehicle")
    route_date = models.DateField(default=timezone.now, verbose_name="Route Date")
    status = models.CharField(max_length=20, choices=ROUTE_STATUS_CHOICES, default='PENDING', verbose_name="Route Status")
    optimized_path = models.TextField(null=True, blank=True, verbose_name="Optimized Path (Points)")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'routes'

    def __str__(self):
        return f"Route #{self.pk} - {self.route_date} ({self.get_status_display()})"

    @property
    def total_weight_kg(self):
        return sum(order.quantity_kg for order in self.orders.all())


# ----------------------------------------------------------------------
# 6. MODELO DE MARKETPLACE (TRANSAÇÕES)
# ----------------------------------------------------------------------

class MarketplaceOrder(models.Model):
    ORDER_TYPE_CHOICES = [
        ('BUY', 'Purchase Request'),
        ('SELL', 'Export Offer'),
    ]
    STATUS_CHOICES = [
        ('OPEN', 'Open'),
        ('NEGOTIATING', 'Negotiating'),
        ('APPROVED', 'Approved/Fulfilled'),
        ('CANCELLED', 'Cancelled'),
    ]

    # Quem criou o pedido
    requester = models.ForeignKey(User, on_delete=models.CASCADE, related_name='market_orders_requested')
    # Perfil de quem criou (Ex: 'Retailer', 'Producer') - útil para filtragem visual
    role = models.CharField(max_length=50, verbose_name="Requester Profile")

    order_type = models.CharField(max_length=10, choices=ORDER_TYPE_CHOICES, verbose_name="Tipo de Pedido")
    
    # O que está a ser transacionado
    culture = models.ForeignKey(ProductSubFamily, on_delete=models.CASCADE, verbose_name="Culture")
    
    # Só faz sentido para SELL orders (Produtor -> Mercado)
    harvest_origin = models.ForeignKey(Harvest, on_delete=models.SET_NULL, null=True, blank=True, related_name='market_orders', verbose_name="Origin (Harvest)")
    
    quantity_kg = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Quantity (Kg)")
    price_per_kg = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Price / Kg (€)")
    
    # Detalhes Logísticos
    warehouse_location = models.CharField(max_length=255, verbose_name="Warehouse Location")
    
    # --- Quality Metrics (Premium Market) ---
    # For SELL Orders (Specific Batch Data)
    caliber = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Caliber (mm)")
    soluble_solids = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Soluble Solids (Brix)")
    quality_score = models.IntegerField(null=True, blank=True, verbose_name="Quality Score (1-10)")

    # For BUY Orders (Minimum Requirements)
    min_caliber = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Min Caliber (mm)")
    min_soluble_solids = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Min Soluble Solids (Brix)")
    min_quality_score = models.IntegerField(null=True, blank=True, verbose_name="Min Quality Score (1-10)")
    
    # Estado e Aprovação
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OPEN')
    fulfilled_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='market_orders_fulfilled')
    
    created_at = models.DateTimeField(auto_now_add=True)
    fulfilled_at = models.DateTimeField(null=True, blank=True)

    # --- CAMPOS DE LOGÍSTICA (TRANSPORTE LIACC) ---
    TRANSPORT_STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('ACCEPTED', 'Job Accepted'),
        ('PLANNED', 'Planned'),
        ('IN_TRANSIT', 'In Transit'),
        ('DELIVERED', 'Delivered'),
    ]
    
    transport_status = models.CharField(max_length=20, choices=TRANSPORT_STATUS_CHOICES, default='PENDING', verbose_name="Transport Status")
    
    # Planning (LIACC Input)
    planned_pickup_date = models.DateTimeField(null=True, blank=True, verbose_name="Planned Pickup Date")
    planned_delivery_date = models.DateTimeField(null=True, blank=True, verbose_name="Planned Delivery Date")
    
    # Real Execution (Transporter/Blocks Input)
    actual_pickup_date = models.DateTimeField(null=True, blank=True, verbose_name="Actual Pickup Date")
    actual_delivery_date = models.DateTimeField(null=True, blank=True, verbose_name="Actual Delivery Date")
    
    # Sensor Data (LIACC JSON Dump)
    # Using TextField for simplicity (can contain JSON)
    transport_sensor_data = models.TextField(null=True, blank=True, verbose_name="Sensor Data (JSON)")

    # Relacionamento com Frota e Otimização de Rotas
    vehicle = models.ForeignKey(Vehicle, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Vehicle")
    route = models.ForeignKey(Route, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders', verbose_name="Route")

    # --- PROCESSOR: PROCESSING FIELDS ---
    is_processed = models.BooleanField(default=False, verbose_name="Processed?")
    packaging_type = models.CharField(
        max_length=50, 
        choices=[('Plastic', 'Plastic'), ('Cardboard', 'Cardboard'), ('Other', 'Other')],
        null=True, blank=True,
        verbose_name="Packaging Type"
    )
    preservation_treatment = models.CharField(
        max_length=50,
        choices=[('Natural', 'Natural Treatment'), ('Conventional', 'Conventional/Chemical'), ('None', 'None')],
        null=True, blank=True,
        verbose_name="Preservation Treatment"
    )
    
    class Meta:
        db_table = 'marketplace_orders'
        ordering = ['-created_at']

    @property
    def pk_str(self):
        return str(self.pk)

    @property
    def total_price(self):
        if self.price_per_kg and self.quantity_kg:
            return self.price_per_kg * self.quantity_kg
        return 0.0

    @property
    def destination_warehouse(self):
        if self.warehouse_location and ' (WH:' in self.warehouse_location:
            try:
                wh_id = int(self.warehouse_location.split(' (WH:')[-1].replace(')', '').strip())
                from .models import Warehouse
                return Warehouse.objects.filter(pk=wh_id).first()
            except Exception:
                pass
        return None

    @property
    def destination_latitude(self):
        wh = self.destination_warehouse
        return wh.latitude if wh else None

    @property
    def destination_longitude(self):
        wh = self.destination_warehouse
        return wh.longitude if wh else None

    def __str__(self):
        return f"{self.order_type} - {self.culture.name} ({self.quantity_kg}kg) by {self.requester.username}"

class OrderNegotiation(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('ACCEPTED', 'Accepted'),
        ('REJECTED', 'Rejected'),
    ]
    order = models.ForeignKey(MarketplaceOrder, on_delete=models.CASCADE, related_name='negotiations')
    proposed_by = models.ForeignKey(User, on_delete=models.CASCADE)
    proposed_price_per_kg = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Proposed Price (€/Kg)")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', verbose_name="Status")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'order_negotiations'
        ordering = ['-created_at']

    def __str__(self):
        return f"Negotiation for {self.order.pk} by {self.proposed_by.username} - {self.status}"


class WarehouseSensorReading(models.Model):
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='sensor_readings')
    date = models.DateField(verbose_name="Reading Date")
    temperature = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Temperature (°C)")
    humidity = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Humidity (%)")
    ethylene = models.DecimalField(max_digits=6, decimal_places=3, verbose_name="Ethylene (ppm)")

    class Meta:
        db_table = 'warehouse_sensor_readings'
        unique_together = ('warehouse', 'date')
        ordering = ['-date']

    def __str__(self):
        return f"Reading {self.date} - Warehouse {self.warehouse.warehouse_id}"


class ConsolidatedStock(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='consolidated_stocks')
    culture = models.ForeignKey(ProductSubFamily, on_delete=models.CASCADE)
    warehouse_location = models.CharField(max_length=255, verbose_name="Warehouse Location")
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0.0, verbose_name="Stock Quantity (Kg)")
    
    # Average Quality Metrics
    avg_caliber = models.DecimalField(max_digits=5, decimal_places=2, default=0.0, verbose_name="Average Caliber (mm)")
    avg_soluble_solids = models.DecimalField(max_digits=5, decimal_places=2, default=0.0, verbose_name="Average Soluble Solids (Brix)")
    avg_quality_score = models.DecimalField(max_digits=4, decimal_places=1, default=0.0, verbose_name="Average Quality Score")

    class Meta:
        db_table = 'consolidated_stock'
        unique_together = ('owner', 'culture', 'warehouse_location')

    def __str__(self):
        return f"Stock of {self.owner.username} - {self.culture.name} ({self.quantity}kg) at {self.warehouse_location}"


from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from itertools import chain

def update_consolidated_stock(user, culture, warehouse_location):
    is_processor = user.groups.filter(name='Processor').exists()
    
    incoming_qs = MarketplaceOrder.objects.filter(
        status='APPROVED',
        warehouse_location=warehouse_location,
        culture=culture
    )
    
    if is_processor:
        purchases_in = incoming_qs.filter(requester=user, order_type='BUY', transport_status='DELIVERED', is_processed=True)
        sales_in = incoming_qs.filter(fulfilled_by=user, order_type='SELL', transport_status='DELIVERED', is_processed=True)
    else:
        purchases_in = incoming_qs.filter(requester=user, order_type='BUY', transport_status='DELIVERED')
        sales_in = incoming_qs.filter(fulfilled_by=user, order_type='SELL', transport_status='DELIVERED')
        
    total_qty = 0.0
    mass_cal = 0.0
    mass_brix = 0.0
    mass_score = 0.0
    
    for p in chain(purchases_in, sales_in):
        qty = float(p.quantity_kg)
        total_qty += qty
        
        if p.order_type == 'SELL':
            cal = float(p.caliber) if p.caliber else 0.0
            brix = float(p.soluble_solids) if p.soluble_solids else 0.0
            score = float(p.quality_score) if p.quality_score else 0.0
        else:
            cal = float(p.min_caliber) if p.min_caliber else 0.0
            brix = float(p.min_soluble_solids) if p.min_soluble_solids else 0.0
            score = float(p.min_quality_score) if p.min_quality_score else 0.0
            
        mass_cal += (cal * qty)
        mass_brix += (brix * qty)
        mass_score += (score * qty)
        
    outgoing_qs = MarketplaceOrder.objects.filter(
        warehouse_location=warehouse_location,
        culture=culture
    )
    
    sales_out = outgoing_qs.filter(requester=user, order_type='SELL').exclude(status='CANCELLED')
    purchases_out = outgoing_qs.filter(fulfilled_by=user, order_type='BUY', status='APPROVED')
    
    total_out = 0.0
    for s in chain(sales_out, purchases_out):
        total_out += float(s.quantity_kg)
        
    net_qty = max(0.0, total_qty - total_out)
    
    avg_cal = (mass_cal / total_qty) if total_qty > 0 else 0.0
    avg_brix = (mass_brix / total_qty) if total_qty > 0 else 0.0
    avg_score = (mass_score / total_qty) if total_qty > 0 else 0.0
    
    if net_qty > 0.001:
        obj, created = ConsolidatedStock.objects.get_or_create(
            owner=user,
            culture=culture,
            warehouse_location=warehouse_location
        )
        obj.quantity = net_qty
        obj.avg_caliber = avg_cal
        obj.avg_soluble_solids = avg_brix
        obj.avg_quality_score = avg_score
        obj.save()
    else:
        ConsolidatedStock.objects.filter(
            owner=user,
            culture=culture,
            warehouse_location=warehouse_location
        ).delete()

@receiver(post_save, sender=MarketplaceOrder)
def order_post_save(sender, instance, **kwargs):
    if instance.requester:
        update_consolidated_stock(instance.requester, instance.culture, instance.warehouse_location)
    if instance.fulfilled_by:
        update_consolidated_stock(instance.fulfilled_by, instance.culture, instance.warehouse_location)
        
@receiver(post_delete, sender=MarketplaceOrder)
def order_post_delete(sender, instance, **kwargs):
    if instance.requester:
        update_consolidated_stock(instance.requester, instance.culture, instance.warehouse_location)
    if instance.fulfilled_by:
        update_consolidated_stock(instance.fulfilled_by, instance.culture, instance.warehouse_location)


class HistoricalSalesData(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='historical_sales', verbose_name="User")
    culture = models.ForeignKey(ProductSubFamily, on_delete=models.CASCADE, verbose_name="Culture")
    date = models.DateField(verbose_name="Sale Date")
    sales_quantity_kg = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Sales in Kg")
    price_per_kg = models.DecimalField(max_digits=8, decimal_places=2, verbose_name="Selling Price (€/Kg)")

    class Meta:
        db_table = 'historical_sales_data'
        unique_together = ('owner', 'culture', 'date')
        verbose_name = "Sales History"
        verbose_name_plural = "Sales Histories"

    def __str__(self):
        return f"{self.owner.username} - {self.culture.name} ({self.date}): {self.sales_quantity_kg}kg"


class DemandForecast(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='demand_forecasts', verbose_name="User")
    culture = models.ForeignKey(ProductSubFamily, on_delete=models.CASCADE, verbose_name="Culture")
    date = models.DateField(verbose_name="Forecast Date")
    predicted_quantity_kg = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Predicted Quantity (Kg)")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")

    class Meta:
        db_table = 'demand_forecast'
        unique_together = ('owner', 'culture', 'date')
        verbose_name = "Demand Forecast"
        verbose_name_plural = "Demand Forecasts"

    def __str__(self):
        return f"Forecast {self.owner.username} - {self.culture.name} ({self.date}): {self.predicted_quantity_kg}kg"


class TrainedModel(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trained_models', verbose_name="User")
    culture = models.ForeignKey(ProductSubFamily, on_delete=models.CASCADE, verbose_name="Culture")
    model_type = models.CharField(max_length=50, verbose_name="Model Type") # 'sales_mlp' or 'buyer_agent'
    file_name = models.CharField(max_length=255, verbose_name="File Name") # ex: 'sales_mlp.joblib', 'buyer_agent_actor.pth'
    file_data = models.BinaryField(verbose_name="File Data (Binary)")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated At")

    class Meta:
        db_table = 'trained_model'
        unique_together = ('owner', 'culture', 'model_type', 'file_name')
        verbose_name = "Trained AI Model"
        verbose_name_plural = "Trained AI Models"

    def __str__(self):
        return f"{self.owner.username} - {self.culture.name} ({self.model_type} - {self.file_name})"


class StoreProcessorAssociation(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]
    processor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='store_associations', limit_choices_to={'groups__name': 'Processor'}, verbose_name="Processor")
    retailer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='processor_associations', limit_choices_to={'groups__name': 'Retailer'}, verbose_name="Retailer/Store")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', verbose_name="Status")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'store_processor_associations'
        unique_together = ('processor', 'retailer')
        verbose_name = "Store Association"
        verbose_name_plural = "Store Associations"

    def __str__(self):
        return f"{self.processor.username} -> {self.retailer.username} ({self.status})"