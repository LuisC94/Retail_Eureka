import os
import django
import sys
import traceback
from django.db.models import Sum

# Setup Django environment
sys.path.append(r'c:\Users\luis.carvalho\OneDrive - Retail Consult\Projetos\Retail_2025\Retail-Eureka')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from dashboard.models import Harvest, User, PlantationPlan, Product

try:
    # Get the producer user
    # Get the producer user
    # users_with_harvests = User.objects.filter(harvest_records__isnull=False).distinct()
    # The error said 'harvest' is a choice, so let's try that, or just get users from Harvests directly.
    producer_ids = Harvest.objects.values_list('producer', flat=True).distinct()
    users_with_harvests = User.objects.filter(pk__in=producer_ids)

    print(f"Users with harvests: {users_with_harvests}")

    for user in users_with_harvests:
        print(f"\nChecking for user: {user.username}")
        
        harvests = Harvest.objects.filter(producer=user)
        print(f"Total Harvests: {harvests.count()}")
        
        # Check first harvest structure
        h = harvests.first()
        if h:
            print(f"First Harvest: {h}")
            print(f"  Plantation: {h.plantation}")
            if h.plantation:
                print(f"    Product: {h.plantation.product}")
                print(f"      Name: {h.plantation.product.name}")
        
        # Test Aggregation
        print("Attempting aggregation...")
        harvest_sums = Harvest.objects.filter(producer=user).values(
            'plantation__product__name'
        ).annotate(
            total_kg=Sum('harvest_quantity_kg')
        ).order_by('plantation__product__name')
        
        print(f"Aggregation Result: {list(harvest_sums)}")

except Exception:
    traceback.print_exc()
