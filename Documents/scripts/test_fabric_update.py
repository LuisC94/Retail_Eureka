import os
import django
import sys
import logging
import json

# Setup Django Environment
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

# Configure logging to see output
logging.basicConfig(level=logging.DEBUG)

from dashboard.services.fabric_service import fabric_service

# Test updating HARVEST-36
test_id = "HARVEST-36"
print(f"--- Attempting to UPDATE {test_id} ---")

# Simulate Pickup Data
transport_data = {
    "transporterId": "TestTransporter",
    "pickupDate": "2026-02-19T16:20:00",
    "pickupLocation": "Test Warehouse", 
    "transportVehicle": "VI-TEST-99"
}

result = fabric_service.update_order(
    order_id=test_id,
    new_status="IN_TRANSIT",
    additional_data=transport_data
)

print(f"Update Result: {result}")

# Verify immediately
print("--- Verifying Update ---")
check = fabric_service.get_order(test_id)
print(f"Check Result: {json.dumps(check, indent=2)}")
