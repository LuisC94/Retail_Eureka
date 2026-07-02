import os
import django
import sys
import logging
import time
import requests

# Setup Django Environment
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

# Configure logging to see output
logging.basicConfig(level=logging.DEBUG)

from dashboard.services.fabric_service import fabric_service, FABRIC_API_URL

test_id = "TEST-HARVEST-999"
print(f"--- Attempting to create {test_id} ---")

result = fabric_service.create_order(
    order_id=test_id,
    producer_id="TestProducer",
    culture_type="Test Apple",
    quantity=100.0,
    harvest_date="2024-02-20"
)

print(f"Creation Result: {result}")

print("--- Waiting 5 seconds for Block Commit ---")
time.sleep(5)

# Verify immediately with raw request to see error
print("--- Verifying creation (RAW) ---")
url = f"{FABRIC_API_URL}/query"
params = {
    "channelid": "mychannel",
    "chaincodeid": "saip",
    "function": "ReadOrder",
    "args": test_id
}
resp = requests.get(url, params=params)
print(f"Raw Status: {resp.status_code}")
print(f"Raw Body: {resp.text}")
