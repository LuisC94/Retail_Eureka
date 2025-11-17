from django.db import models
from django.contrib.auth.models import User

# --- NOVO MODELO: User Profile ---
class UserProfile(models.Model):
    # Liga o perfil ao objeto User (relação 1 para 1)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    
    # NOVOS CAMPOS ADICIONAIS
    phone_number = models.CharField(
        max_length=20, 
        blank=True, 
        null=True, 
        verbose_name="Telemóvel"
    )
    address = models.CharField(
        max_length=255, 
        blank=True, 
        null=True, 
        verbose_name="Morada Completa"
    )

    def __str__(self):
        return f"Perfil de {self.user.username}"
        
    class Meta:
        db_table = 'user_profile'
        app_label = 'dashboard' # Garanta que pertence à sua app

# --- 1. Tabela 'products' (Registar um Produto) ---
# Este modelo resolve o erro de FK ao registar um produto antes de o usar.
class Product(models.Model):
    # Chave Primária
    product_id = models.AutoField(primary_key=True) 
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=100) # Ex: Frutas, Vegetais, etc.
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Preço de Venda (€)")
    
    # FK para o Produtor que registou o produto
    producer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        db_table = 'products' 
        
    def __str__(self):
        return f"{self.product_id} - {self.name} ({self.category})"


# DEFINIÇÃO DE CHOICES PARA OS DROPDOWNS
PRODUCTION_TYPE_CHOICES = [
    ('Modern', 'Moderna'),
    ('Traditional', 'Tradicional'),
]

CHEMICAL_USE_CHOICES = [
    ('Yes', 'Sim'),
    ('No', 'Não'),
]

# --- 2. Tabela 'plantation plan' (Registar uma Plantação) ---
class PlantationPlan(models.Model):
    # Chave Primária
    plantation_id = models.AutoField(primary_key=True)
    
    # FK para o Produtor logado
    producer = models.ForeignKey(User, on_delete=models.CASCADE) 
    
    # FK para o Produto (Garante que só pode ligar a um produto existente)
    product = models.ForeignKey(Product, on_delete=models.PROTECT) 
    quantity_of_seeds = models.IntegerField(verbose_name="Nº de Sementes Plantadas")
    production_type = models.CharField(max_length=20, choices=PRODUCTION_TYPE_CHOICES, verbose_name="Tipo de Produção")
    chemical_use = models.CharField(max_length=5, choices=CHEMICAL_USE_CHOICES, verbose_name="Uso de Químicos")
    area = models.DecimalField(max_digits=10, decimal_places=2) 
    location = models.CharField(max_length=100)
    plantation_date = models.DateField()
    
    class Meta:
        db_table = 'plantation plan'

    def __str__(self):
        return f"Plano {self.plantation_id} - Produto: {self.product.name}"

####################################################################################
# 5 -> Choices para a Qualidade
QUALITY_SCORE_CHOICES = [
    (i, str(i)) for i in range(1, 11)
]

# --- 3. Tabela 'harvest' (Registar Colheita) ---
class Harvest(models.Model):
    # 1 -> Chave Primária
    harvest_id = models.AutoField(primary_key=True)
    
    # 2 -> FK para a PlantationPlan
    # Usamos OneToOneField para garantir que um plano é colhido UMA ÚNICA VEZ.
    # on_delete=models.SET_NULL é CRUCIAL, pois o PlantationPlan será REMOVIDO pela view.
    plantation = models.OneToOneField(
        'PlantationPlan', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name="Plano de Plantação Concluído"
    )
    
    # FK para o Produtor (para listagem fácil)
    producer = models.ForeignKey(User, on_delete=models.CASCADE) 

    # 3 -> Data de Colheita
    harvest_date = models.DateField(verbose_name="Data de Colheita")
    
    # 4 -> Qt de Colheita (Kg)
    harvest_quantity_kg = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        verbose_name="Quantidade Colhida (Kg)"
    )
    
    # 5 -> avg Score quality (Dropdown de 1 a 10)
    avg_quality_score = models.IntegerField(
        choices=QUALITY_SCORE_CHOICES, 
        verbose_name="Qualidade Média (1-10)"
    )
    
    # 6 -> Qt Aproveitada da Colhida (Kg)
    utilized_quantity_kg = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        verbose_name="Quantidade Aproveitada (Kg)"
    )
    
    class Meta:
        db_table = 'harvest'
        
    def __str__(self):
        # Usamos o ID do plano de plantação para identificar o registo de colheita
        return f"Colheita {self.pk} - Plano {self.plantation_id}"
    
# DEFINIÇÃO DE CHOICES PARA DROPDOWNS
SENSOR_TYPE_CHOICES = [
    ('Temperature', 'Temperatura'),
    ('Humidity', 'Humidade'),
    ('Light', 'Luminosidade'),
    ('Gas', 'Gás/CO2'),
    # Adicione mais tipos conforme necessário
]

# --- 4. Tabela 'sensor' ---
class Sensor(models.Model):
    # Campos que pediu
    sensor_id = models.AutoField(primary_key=True)
    brand = models.CharField(max_length=100, verbose_name="Marca do Sensor")
    sensor_type = models.CharField(max_length=50, choices=SENSOR_TYPE_CHOICES, verbose_name="Tipo de Sensor")
    
    class Meta:
        db_table = 'sensors'
        
    def __str__(self):
        return f"{self.sensor_id} - {self.brand} ({self.get_sensor_type_display()})"
    
# DEFINIÇÃO DE CHOICES PARA DROPDOWNS
CONTROL_TYPE_CHOICES = [
    ('Controlled', 'Controlado'),
    ('Non-Controlled', 'Não Controlado'),
]

# --- 5. Tabela 'warehouse' ---
class Warehouse(models.Model):
    # 1. Ligação ao Produtor (o dono do armazém)
    owner = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        limit_choices_to={'groups__name': 'Producer'}, # Opcional: limita a escolha a Produtores
        verbose_name="Dono/Perfil"
    )

    # 2. Campos do Armazém
    warehouse_id = models.AutoField(primary_key=True) # ID automático para simplificar
    location = models.CharField(max_length=255, verbose_name="Localização")
    control_type = models.CharField(max_length=20, choices=CONTROL_TYPE_CHOICES, verbose_name="Tipo de Armazém")
    capacity = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Capacidade (m² ou Kg)")
    
    # 3. Relação com Sensores (Muitos-para-Muitos)
    sensors = models.ManyToManyField(
        Sensor, 
        blank=True, 
        verbose_name="Sensores Instalados"
    )

    class Meta:
        db_table = 'warehouses'
        verbose_name = 'Armazém'
        verbose_name_plural = 'Armazéns'

    def __str__(self):
        return f"Armazém {self.warehouse_id} - {self.location}"