import requests
import json
import time
import random
import datetime

BASE_URL = "http://127.0.0.1:8002"

def generate_sample_data(days=60):
    start_date = datetime.date(2026, 1, 1)
    records = []
    base_demand = 120.0
    for i in range(days):
        dt = start_date + datetime.timedelta(days=i)
        # Seasonal weekend bump
        is_weekend = dt.weekday() >= 5
        multiplier = 1.3 if is_weekend else 1.0
        real_val = round(base_demand * multiplier + random.uniform(-15, 15), 1)
        # Forecast with some reasonable noise
        forecast_val = round(real_val + random.uniform(-8, 8), 1)
        price = round(2.10 + random.uniform(-0.15, 0.15), 2)
        
        records.append({
            "date": dt.isoformat(),
            "real_value": real_val,
            "prediction": forecast_val,
            "price": price,
            "temperature": 1.5,
            "humidity": 92.0,
            "ethylene": 0.05,
            "volume": 0.002
        })
    return records

def test_buyer_service():
    print("==================================================")
    print("   TESTING BUYER AGENT WEB SERVICE (PORT 8002)   ")
    print("==================================================")
    
    # 1. Test Health & Root
    print("\n1. Testing GET /health...")
    try:
        r = requests.get(f"{BASE_URL}/health")
        print(f"Status Code: {r.status_code}, Response: {r.json()}")
        assert r.status_code == 200
    except Exception as e:
        print(f"[ERRO] Falha ao ligar ao serviço: {e}")
        return
        
    # 2. Test Model Status (before training)
    print("\n2. Testing GET /api/buyer/status?user_id=1&culture_id=3...")
    r = requests.get(f"{BASE_URL}/api/buyer/status", params={"user_id": 1, "culture_id": 3})
    print(f"Status Code: {r.status_code}, Response: {r.json()}")
    
    # 3. Test Decision Heuristic (Fallback before training)
    print("\n3. Testing POST /api/buyer/decide (Before Training)...")
    decide_payload = {
        "user_id": 1,
        "culture_id": 3,
        "date": "2026-09-16",
        "current_stock_profile": [40.0, 30.0, 20.0, 10.0],
        "in_transit_kg": 0.0,
        "prediction_today_kg": 140.0,
        "prediction_tomorrow_kg": 135.0,
        "recent_sales_lags": [130.0, 125.0],
        "price_today": 2.15,
        "recent_prices": [2.10, 2.15, 2.05, 2.20],
        "max_capacity": 500.0
    }
    r = requests.post(f"{BASE_URL}/api/buyer/decide", json=decide_payload)
    print(f"Status Code: {r.status_code}")
    print(json.dumps(r.json(), indent=2))
    assert r.status_code == 200
    
    # 4. Test Training
    print("\n4. Testing POST /api/buyer/train (Training custom PPO policy)...")
    sample_data = generate_sample_data(days=60)
    train_payload = {
        "user_id": 1,
        "culture_id": 3,
        "fruit_key": "maca_gala",
        "max_capacity": 500.0,
        "episodes": 64, # Fast test run
        "train_data": sample_data
    }
    t0 = time.time()
    r = requests.post(f"{BASE_URL}/api/buyer/train", json=train_payload)
    print(f"Status Code: {r.status_code} (took {round(time.time() - t0, 2)}s)")
    print(json.dumps(r.json(), indent=2))
    assert r.status_code == 200
    
    # 5. Test Status (after training)
    print("\n5. Testing GET /api/buyer/status (After Training)...")
    r = requests.get(f"{BASE_URL}/api/buyer/status", params={"user_id": 1, "culture_id": 3})
    print(f"Status Code: {r.status_code}, Response: {r.json()}")
    assert r.json().get("has_model") is True
    
    # 6. Test Decision with Trained RL Policy
    print("\n6. Testing POST /api/buyer/decide (With Trained PPO Policy)...")
    r = requests.post(f"{BASE_URL}/api/buyer/decide", json=decide_payload)
    print(f"Status Code: {r.status_code}")
    res_data = r.json()
    print(json.dumps(res_data, indent=2))
    assert r.status_code == 200
    print(f"\n[OK] Agente recomendou encomenda de: {res_data['recommended_order_kg']} Kg ({res_data['order_percentage']*100:.1f}%)")
    print(f"[OK] Baselines: DOS-3D={res_data['heuristics_comparison']['dos_3d_kg']}Kg | CNN Naive={res_data['heuristics_comparison']['cnn_naive_kg']}Kg | Min-Max={res_data['heuristics_comparison']['min_max_kg']}Kg")

if __name__ == "__main__":
    test_buyer_service()
