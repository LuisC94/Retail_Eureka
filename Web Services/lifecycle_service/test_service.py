import requests
import json
import time
from datetime import datetime, timedelta

LIFECYCLE_API_URL = "http://127.0.0.1:8003"

def test_health():
    print("\n--- 1. Test Healthcheck Endpoint ---")
    try:
        res = requests.get(f"{LIFECYCLE_API_URL}/health", timeout=5)
        print(f"Status Code: {res.status_code}")
        print(f"Response: {json.dumps(res.json(), indent=2)}")
        assert res.status_code == 200, "Healthcheck should return 200"
        print("-> [OK] Healthcheck passed!")
    except Exception as e:
        print(f"-> [ERRO] Failed connecting to {LIFECYCLE_API_URL}: {e}")
        return False
    return True

def test_presets():
    print("\n--- 2. Test Presets Endpoint ---")
    res = requests.get(f"{LIFECYCLE_API_URL}/presets", timeout=5)
    print(f"Status Code: {res.status_code}")
    print(f"Response: {json.dumps(res.json(), indent=2)}")
    assert res.status_code == 200
    print("-> [OK] Presets endpoint passed!")

def test_forecast_simulation():
    print("\n--- 3. Test Forecast Simulation (Apple Gala with 10 days of storage) ---")
    today = datetime.today()
    harvest_date = (today - timedelta(days=10)).strftime("%Y-%m-%d")

    payload = {
        "version": "1.0",
        "export_metadata": {
            "generated_at": datetime.now().isoformat(),
            "target_service": "Lifecycle Decay Prediction Model Web Service",
            "days_elapsed_total": 10
        },
        "lot_identification": {
            "lot_id": 101,
            "batch_id": "LOTE-MACA-GALA-101",
            "culture_name": "Gala",
            "fruit_type": "apple",
            "producer": "Produtor_Joao",
            "current_owner": "Continente",
            "current_owner_type": "Retailer (Grocery Store)",
            "harvest_date": harvest_date,
            "initial_quantity_kg": 1500.0,
            "current_stock_kg": 1200.0,
            "delivered_quantity_kg": 300.0,
            "initial_metrics": {
                "soluble_solids_brix": 13.2,
                "caliber_mm": 75.0,
                "quality_score": 9.5,
                "waste_kg": 0.0,
                "firmness": 68.0,
                "acidity": 0.45
            }
        },
        "plantation_origin": {
            "name": "Quinta dos Pomares",
            "location": "Alcobaça, Portugal",
            "production_type": "Integrated Pest Management"
        },
        "plantation_agricultural_events": [],
        "current_warehouse": {
            "id": 1,
            "location": "Armazém Central Lisboa",
            "region": "PT-LVT",
            "control_type": "Controlled Atmosphere",
            "storage_unit": "PALLETS"
        },
        "meteorology_and_imputation_strategy": {
            "meteo_source": "JSON",
            "json_fallback_mode": "IPMA",
            "fixed_temperature_celsius": 4.0,
            "fixed_humidity_percent": 90.0,
            "ipma_region_code": "PT-LVT"
        },
        "blockchain_ledger": {},
        "transport_and_logistics": [],
        "sensor_history_by_warehouse": [
            {
                "warehouse_id": 1,
                "warehouse_location": "Armazém Produtor Alcobaça",
                "region": "PT-LVT",
                "meteo_source": "JSON",
                "total_days_recorded": 6,
                "packaging_method": "Caixa de Cartão Aberta",
                "daily_readings": [
                    {"date": (today - timedelta(days=10)).strftime("%Y-%m-%d"), "temperature_celsius": 3.8, "humidity_percent": 91.0, "ethylene_ppm": 0.01, "source": "SENSOR"},
                    {"date": (today - timedelta(days=9)).strftime("%Y-%m-%d"), "temperature_celsius": 4.1, "humidity_percent": 89.5, "ethylene_ppm": 0.01, "source": "SENSOR"},
                    {"date": (today - timedelta(days=8)).strftime("%Y-%m-%d"), "temperature_celsius": 4.0, "humidity_percent": 90.0, "ethylene_ppm": 0.02, "source": "SENSOR"},
                    {"date": (today - timedelta(days=7)).strftime("%Y-%m-%d"), "temperature_celsius": 3.9, "humidity_percent": 90.5, "ethylene_ppm": 0.02, "source": "SENSOR"},
                    {"date": (today - timedelta(days=6)).strftime("%Y-%m-%d"), "temperature_celsius": 4.2, "humidity_percent": 88.0, "ethylene_ppm": 0.03, "source": "SENSOR"},
                    {"date": (today - timedelta(days=5)).strftime("%Y-%m-%d"), "temperature_celsius": 4.0, "humidity_percent": 89.0, "ethylene_ppm": 0.03, "source": "SENSOR"}
                ]
            },
            {
                "warehouse_id": 2,
                "warehouse_location": "Entreposto Continente Azambuja",
                "region": "PT-LVT",
                "meteo_source": "JSON",
                "total_days_recorded": 4,
                "packaging_method": "MAP (Atmosfera Modificada) / Plástico Selado",
                "daily_readings": [
                    {"date": (today - timedelta(days=4)).strftime("%Y-%m-%d"), "temperature_celsius": 3.5, "humidity_percent": 92.0, "ethylene_ppm": 0.02, "source": "SENSOR"},
                    {"date": (today - timedelta(days=3)).strftime("%Y-%m-%d"), "temperature_celsius": 3.6, "humidity_percent": 91.5, "ethylene_ppm": 0.02, "source": "SENSOR"},
                    {"date": (today - timedelta(days=2)).strftime("%Y-%m-%d"), "temperature_celsius": 3.7, "humidity_percent": 90.8, "ethylene_ppm": 0.02, "source": "SENSOR"},
                    {"date": (today - timedelta(days=1)).strftime("%Y-%m-%d"), "temperature_celsius": 3.5, "humidity_percent": 92.0, "ethylene_ppm": 0.03, "source": "SENSOR"}
                ]
            }
        ],
        "plot_info": True
    }

    res = requests.post(f"{LIFECYCLE_API_URL}/forecast", json=payload, timeout=10)
    print(f"Status Code: {res.status_code}")
    if res.status_code == 200:
        data = res.json()
        print(f"\nResultados da Inferência:")
        print(f"  - Produto Identificado: {data.get('product_id')}")
        print(f"  - Algoritmo Aplicado: {data.get('algorithm')}")
        print(f"  - Qualidade Comercial Residual: {data.get('quality_index')}/100")
        print(f"  - Dias de Vida Útil Restante (Shelf-Life): {data.get('remaining_lifetime')} dias")
        print(f"  - Firmeza Prevista: {data.get('firmness')} N")
        print(f"  - Sólidos Solúveis (°Brix): {data.get('brix')} °Bx")
        print("-> [OK] Simulação de Decaimento concluída com sucesso!")
    else:
        print(f"-> [ERRO] Response: {res.text}")

if __name__ == "__main__":
    print("==================================================================")
    print("  TESTE DO WEB SERVICE: LIFECYCLE DECAY PREDICTION (Porta 8003)   ")
    print("==================================================================")
    if test_health():
        test_presets()
        test_forecast_simulation()
