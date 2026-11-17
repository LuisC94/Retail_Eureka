from django.contrib import admin
from .models import UserProfile, ProductSubFamily, Harvest, HistoricalSalesData, DemandForecast, TrainedModel

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'producer_type', 'phone_number')
    list_filter = ('producer_type',)
    search_fields = ('user__username', 'phone_number')

@admin.register(ProductSubFamily)
class ProductSubFamilyAdmin(admin.ModelAdmin):
    list_display = ('name', 'fruit_type', 'default_shelf_life_days')
    list_filter = ('fruit_type',)
    search_fields = ('name',)


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



from .models import LedgerEntry


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    """Ledger local: apenas leitura (append-only)."""
    list_display = ('block_number', 'asset_id', 'function', 'actor', 'timestamp', 'short_hash')
    list_filter = ('function',)
    search_fields = ('asset_id', 'tx_id', 'actor')
    ordering = ('-block_number',)

    def short_hash(self, obj):
        return obj.hash[:12]
    short_hash.short_description = 'Hash'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
