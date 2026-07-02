import os
import django
import sys

# Setup Django Environment
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from dashboard.models import Harvest
from django.contrib.auth import get_user_model
User = get_user_model()

print("--- Data Verification ---")
# Assuming the user is likely the first one or we can filter by username if known.
# The user's username is 'luis.carvalho' based on paths, but checking all harvests is safer.
harvests = Harvest.objects.all().order_by('-pk')[:5]

for h in harvests:
    print(f"ID: {h.pk} | Producer: {h.producer.username} | Plantation: {h.plantation} | Subfamily: {h.subfamily} | Date: {h.harvest_date}")
