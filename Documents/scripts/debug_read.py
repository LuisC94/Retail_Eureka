import requests
import json
from dashboard.services.fabric_service import FABRIC_API_URL

test_id = "HARVEST-36"
url = f"{FABRIC_API_URL}/query"
params = {
    "channelid": "mychannel",
    "chaincodeid": "saip",
    "function": "ReadOrder",
    "args": test_id
}

print(f"--- Querying {test_id} ---")
try:
    resp = requests.get(url, params=params)
    print(f"Status: {resp.status_code}")
    print(f"Headers: {resp.headers}")
    print(f"Body (Text): {resp.text}")
    try:
        print(f"Body (JSON): {json.dumps(resp.json(), indent=2)}")
    except Exception as e:
        print(f"JSON Parse Error: {e}")
except Exception as e:
    print(f"Request Error: {e}")
