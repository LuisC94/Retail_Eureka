import os
import sys
import unittest
import tempfile
import json
from datetime import datetime

# Add root of service to sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from engine.order_book import OrderBookEngine
from schemas import (
    ListingCreate,
    BidCreate,
    InstantBuyRequest,
    SupplyContractRequest,
    QualityMetrics
)

class TestMarketplaceService(unittest.TestCase):

    def setUp(self):
        # Usar uma base de dados SQLite temporária isolada para cada execução de testes
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        self.engine = OrderBookEngine(db_path=self.temp_db_path)

    def tearDown(self):
        os.close(self.temp_db_fd)
        if os.path.exists(self.temp_db_path):
            os.remove(self.temp_db_path)

    def test_create_and_get_listing(self):
        listing_data = {
            "seller_id": "Produtor_Joao",
            "seller_role": "Producer",
            "culture_name": "Maçã Gala de Alcobaça",
            "fruit_type": "apple",
            "quantity_kg": 1500.0,
            "price_per_kg": 1.35,
            "warehouse_location": "Quinta dos Pomares, Alcobaça",
            "batch_id": "LOTE-MACA-2026-001",
            "quality_metrics": {
                "caliber_mm": 72.5,
                "soluble_solids_brix": 13.2,
                "quality_score": 9.2
            },
            "packaging_type": "Caixas de Madeira 15kg",
            "preservation_treatment": "Natural"
        }

        created = self.engine.create_listing(listing_data)
        self.assertIsNotNone(created)
        self.assertTrue(created["listing_id"].startswith("LST-"))
        self.assertEqual(created["status"], "OPEN")
        self.assertEqual(created["quantity_kg"], 1500.0)
        self.assertEqual(created["price_per_kg"], 1.35)

        fetched = self.engine.get_listing(created["listing_id"])
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["culture_name"], "Maçã Gala de Alcobaça")
        self.assertEqual(fetched["quality_metrics"]["soluble_solids_brix"], 13.2)

    def test_list_and_cancel_listing(self):
        self.engine.create_listing({
            "seller_id": "Produtor_Joao",
            "culture_name": "Maçã Gala",
            "quantity_kg": 1000.0,
            "price_per_kg": 1.20,
            "warehouse_location": "Alcobaça"
        })
        l2 = self.engine.create_listing({
            "seller_id": "Produtor_Maria",
            "culture_name": "Kiwi Hayward",
            "quantity_kg": 800.0,
            "price_per_kg": 2.10,
            "warehouse_location": "Viana do Castelo"
        })

        # List all open
        all_open = self.engine.list_listings()
        self.assertEqual(len(all_open), 2)

        # Filter by culture
        kiwis = self.engine.list_listings(culture_name="Kiwi")
        self.assertEqual(len(kiwis), 1)
        self.assertEqual(kiwis[0]["seller_id"], "Produtor_Maria")

        # Cancel listing
        success = self.engine.cancel_listing(l2["listing_id"])
        self.assertTrue(success)

        # Confirm canceled
        after_cancel = self.engine.list_listings()
        self.assertEqual(len(after_cancel), 1)
        self.assertEqual(after_cancel[0]["seller_id"], "Produtor_Joao")

    def test_create_bid_and_list(self):
        bid_data = {
            "buyer_id": "Supermercado_Continente",
            "buyer_role": "Retailer",
            "culture_name": "Maçã Gala",
            "fruit_type": "apple",
            "quantity_kg": 2000.0,
            "max_price_per_kg": 1.40,
            "destination_warehouse": "Entreposto Central Azambuja",
            "min_caliber_mm": 70.0,
            "min_soluble_solids_brix": 12.0
        }

        created = self.engine.create_bid(bid_data)
        self.assertIsNotNone(created)
        self.assertTrue(created["bid_id"].startswith("BID-"))
        self.assertEqual(created["buyer_id"], "Supermercado_Continente")

        bids = self.engine.list_bids(culture_name="Maçã Gala")
        self.assertEqual(len(bids), 1)

    def test_instant_buy_execution_partial_and_full(self):
        listing = self.engine.create_listing({
            "seller_id": "Produtor_Joao",
            "seller_role": "Producer",
            "culture_name": "Pera Rocha",
            "fruit_type": "pear",
            "quantity_kg": 1000.0,
            "price_per_kg": 1.50,
            "warehouse_location": "Cadaval",
            "batch_id": "LOTE-PERA-01"
        })

        # Compra parcial: 400kg de 1000kg
        buy_req1 = {
            "listing_id": listing["listing_id"],
            "buyer_id": "Distribuidor_Silva",
            "buyer_role": "Wholesaler",
            "quantity_kg": 400.0,
            "destination_warehouse": "Porto"
        }
        deal1, err = self.engine.execute_instant_buy(buy_req1)
        self.assertIsNone(err)
        self.assertIsNotNone(deal1)
        self.assertEqual(deal1["quantity_kg"], 400.0)
        self.assertEqual(deal1["price_per_kg"], 1.50)
        self.assertEqual(deal1["total_amount"], 600.0)

        # Verificar stock remanescente na listagem (600kg)
        updated_listing = self.engine.get_listing(listing["listing_id"])
        self.assertEqual(updated_listing["quantity_kg"], 600.0)
        self.assertEqual(updated_listing["status"], "OPEN")

        # Tentativa de compra em excesso (700kg > 600kg disponíveis)
        buy_req_fail = {
            "listing_id": listing["listing_id"],
            "buyer_id": "Distribuidor_Silva",
            "quantity_kg": 700.0,
            "destination_warehouse": "Porto"
        }
        deal_fail, err_fail = self.engine.execute_instant_buy(buy_req_fail)
        self.assertIsNone(deal_fail)
        self.assertIn("exceeds available", err_fail)

        # Compra do remanescente (600kg)
        buy_req2 = {
            "listing_id": listing["listing_id"],
            "buyer_id": "Supermercado_Continente",
            "quantity_kg": 600.0,
            "destination_warehouse": "Azambuja"
        }
        deal2, err2 = self.engine.execute_instant_buy(buy_req2)
        self.assertIsNone(err2)
        self.assertEqual(deal2["quantity_kg"], 600.0)
        self.assertEqual(deal2["total_amount"], 900.0)

        # Verificar que a listagem agora está FULFILLED
        final_listing = self.engine.get_listing(listing["listing_id"])
        self.assertEqual(final_listing["quantity_kg"], 0.0)
        self.assertEqual(final_listing["status"], "FULFILLED")

    def test_supply_contract_creation(self):
        contract_req = {
            "buyer_id": "Supermercado_Continente",
            "buyer_role": "Retailer",
            "seller_id": "Produtor_Joao",
            "seller_role": "Producer",
            "culture_name": "Maçã Gala",
            "quantity_kg": 5000.0,
            "price_per_kg": 1.25,
            "delivery_date": "2026-10-15",
            "destination_warehouse": "Entreposto Azambuja"
        }

        deal = self.engine.create_supply_contract(contract_req)
        self.assertIsNotNone(deal)
        self.assertTrue(deal["deal_id"].startswith("DEAL-CTR-"))
        self.assertEqual(deal["deal_type"], "FUTURE_CONTRACT")
        self.assertEqual(deal["total_amount"], 6250.0)
        self.assertEqual(deal["delivery_date"], "2026-10-15")

    def test_market_stats_and_tickers(self):
        # Inserir listings
        self.engine.create_listing({
            "seller_id": "P1",
            "culture_name": "Maçã Gala",
            "quantity_kg": 1000.0,
            "price_per_kg": 1.20,
            "warehouse_location": "Alcobaça"
        })
        self.engine.create_listing({
            "seller_id": "P2",
            "culture_name": "Maçã Gala",
            "quantity_kg": 2000.0,
            "price_per_kg": 1.40,
            "warehouse_location": "Viseu"
        })
        # Inserir bid
        self.engine.create_bid({
            "buyer_id": "B1",
            "culture_name": "Maçã Gala",
            "quantity_kg": 1500.0,
            "max_price_per_kg": 1.30,
            "destination_warehouse": "Porto"
        })

        stats = self.engine.get_market_stats()
        self.assertEqual(stats["total_active_listings"], 2)
        self.assertEqual(stats["total_active_bids"], 1)

        tickers = stats["market_tickers"]
        maca_ticker = next((t for t in tickers if t["culture_name"] == "Maçã Gala"), None)
        self.assertIsNotNone(maca_ticker)
        self.assertEqual(maca_ticker["min_price_eur"], 1.20)
        self.assertEqual(maca_ticker["max_price_eur"], 1.40)
        self.assertEqual(maca_ticker["current_avg_price_eur"], 1.30)
        self.assertEqual(maca_ticker["total_open_supply_kg"], 3000.0)
        self.assertEqual(maca_ticker["total_open_demand_kg"], 1500.0)


if __name__ == "__main__":
    unittest.main()
