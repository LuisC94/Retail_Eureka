from django.contrib import admin
from .models import UserProfile, CultureShelfLife, SupplyContract, ProductSubFamily, Harvest, HistoricalSalesData, DemandForecast, TrainedModel

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'producer_type', 'phone_number')
    list_filter = ('producer_type',)
    search_fields = ('user__username', 'phone_number')

@admin.register(CultureShelfLife)
class CultureShelfLifeAdmin(admin.ModelAdmin):
    list_display = ('subfamily', 'default_shelf_life_days')
    search_fields = ('subfamily__name',)

@admin.register(SupplyContract)
class SupplyContractAdmin(admin.ModelAdmin):
    list_display = ('id', 'buyer', 'producer', 'subfamily', 'quantity_kg', 'delivery_date', 'status')
    list_filter = ('status', 'delivery_date')
    search_fields = ('buyer__username', 'producer__username', 'subfamily__name')

@admin.register(HistoricalSalesData)
class HistoricalSalesDataAdmin(admin.ModelAdmin):
    list_display = ('owner', 'culture', 'date', 'sales_quantity_kg', 'price_per_kg')
    list_filter = ('date', 'culture')
    search_fields = ('owner__username', 'culture__name')

@admin.register(DemandForecast)
class DemandForecastAdmin(admin.ModelAdmin):
    list_display = ('owner', 'culture', 'date', 'predicted_quantity_kg', 'created_at')
    list_filter = ('date', 'culture')
    search_fields = ('owner__username', 'culture__name')

@admin.register(TrainedModel)
class TrainedModelAdmin(admin.ModelAdmin):
    list_display = ('owner', 'culture', 'model_type', 'file_name', 'updated_at')
    list_filter = ('model_type', 'culture')
    search_fields = ('owner__username', 'culture__name', 'file_name')

