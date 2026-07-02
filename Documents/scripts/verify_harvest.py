import os
import django
import sys

# Setup Django Environment
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from dashboard.services.fabric_service import fabric_service

asset_id = "HARVEST-34"
print(f"--- Checking Blockchain for {asset_id} ---")
result = fabric_service.get_order(asset_id)
print(f"Result: {result}")

if result is None:
    print("Asset NOT found.")
else:
    print("Asset FOUND.")
