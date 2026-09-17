import os
import sqlite3
import json
import uuid
import threading
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple

def get_utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def get_utc_now_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "marketplace.db")

class OrderBookEngine:
    """
    Motor de Order Book e Clearinghouse com persistência SQLite e sincronização Thread-Safe.
    """

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()

            # Tabela de Listings (Ofertas de Venda)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS listings (
                    listing_id TEXT PRIMARY KEY,
                    seller_id TEXT NOT NULL,
                    seller_role TEXT NOT NULL,
                    culture_name TEXT NOT NULL,
                    fruit_type TEXT NOT NULL,
                    quantity_kg REAL NOT NULL,
                    price_per_kg REAL NOT NULL,
                    warehouse_location TEXT NOT NULL,
                    batch_id TEXT,
                    quality_metrics TEXT,
                    packaging_type TEXT,
                    preservation_treatment TEXT,
                    status TEXT NOT NULL DEFAULT 'OPEN',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # Tabela de Bids (Ordens de Compra)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bids (
                    bid_id TEXT PRIMARY KEY,
                    buyer_id TEXT NOT NULL,
                    buyer_role TEXT NOT NULL,
                    culture_name TEXT NOT NULL,
                    fruit_type TEXT NOT NULL,
                    quantity_kg REAL NOT NULL,
                    max_price_per_kg REAL NOT NULL,
                    destination_warehouse TEXT NOT NULL,
                    min_caliber_mm REAL,
                    min_soluble_solids_brix REAL,
                    min_quality_score REAL,
                    status TEXT NOT NULL DEFAULT 'OPEN',
                    created_at TEXT NOT NULL
                )
            """)

            # Tabela de Deals (Transações Fechadas)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS deals (
                    deal_id TEXT PRIMARY KEY,
                    deal_type TEXT NOT NULL,
                    listing_id TEXT,
                    seller_id TEXT NOT NULL,
                    seller_role TEXT NOT NULL,
                    buyer_id TEXT NOT NULL,
                    buyer_role TEXT NOT NULL,
                    culture_name TEXT NOT NULL,
                    quantity_kg REAL NOT NULL,
                    price_per_kg REAL NOT NULL,
                    total_amount REAL NOT NULL,
                    warehouse_origin TEXT NOT NULL,
                    destination_warehouse TEXT NOT NULL,
                    delivery_date TEXT,
                    batch_id TEXT,
                    status TEXT NOT NULL DEFAULT 'CONFIRMED',
                    timestamp TEXT NOT NULL
                )
            """)

            conn.commit()
            conn.close()

    # -------------------------------------------------------------------------
    # 1. GESTÃO DE LISTINGS (VENDAS)
    # -------------------------------------------------------------------------

    def create_listing(self, data: dict) -> dict:
        listing_id = f"LST-{uuid.uuid4().hex[:8].upper()}"
        now_str = get_utc_now_iso()

        metrics_json = json.dumps(data.get("quality_metrics", {}))

        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO listings (
                    listing_id, seller_id, seller_role, culture_name, fruit_type,
                    quantity_kg, price_per_kg, warehouse_location, batch_id,
                    quality_metrics, packaging_type, preservation_treatment,
                    status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', ?, ?)
            """, (
                listing_id,
                data["seller_id"],
                data.get("seller_role", "Producer"),
                data["culture_name"],
                data.get("fruit_type", "apple"),
                float(data["quantity_kg"]),
                float(data["price_per_kg"]),
                data["warehouse_location"],
                data.get("batch_id"),
                metrics_json,
                data.get("packaging_type", "Granel (Sem embalagem)"),
                data.get("preservation_treatment", "Natural"),
                now_str,
                now_str
            ))
            conn.commit()
            conn.close()

        return self.get_listing(listing_id)

    def get_listing(self, listing_id: str) -> Optional[dict]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM listings WHERE listing_id = ?", (listing_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        d = dict(row)
        d["quality_metrics"] = json.loads(d["quality_metrics"]) if d.get("quality_metrics") else {}
        return d

    def list_listings(
        self, 
        culture_name: Optional[str] = None, 
        seller_id: Optional[str] = None,
        max_price: Optional[float] = None,
        status: Optional[str] = "OPEN"
    ) -> List[dict]:
        conn = self._get_conn()
        cursor = conn.cursor()

        query = "SELECT * FROM listings WHERE 1=1"
        params = []

        if status:
            query += " AND status = ?"
            params.append(status)
        if culture_name:
            query += " AND LOWER(culture_name) LIKE ?"
            params.append(f"%{culture_name.lower()}%")
        if seller_id:
            query += " AND seller_id = ?"
            params.append(seller_id)
        if max_price is not None:
            query += " AND price_per_kg <= ?"
            params.append(max_price)

        query += " ORDER BY price_per_kg ASC, created_at DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        results = []
        for r in rows:
            d = dict(r)
            d["quality_metrics"] = json.loads(d["quality_metrics"]) if d.get("quality_metrics") else {}
            results.append(d)
        return results

    def cancel_listing(self, listing_id: str) -> bool:
        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("UPDATE listings SET status = 'CANCELLED', updated_at = ? WHERE listing_id = ?", (
                get_utc_now_iso(), listing_id
            ))
            affected = cursor.rowcount
            conn.commit()
            conn.close()
        return affected > 0

    # -------------------------------------------------------------------------
    # 2. GESTÃO DE BIDS (COMPRAS)
    # -------------------------------------------------------------------------

    def create_bid(self, data: dict) -> dict:
        bid_id = f"BID-{uuid.uuid4().hex[:8].upper()}"
        now_str = get_utc_now_iso()

        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO bids (
                    bid_id, buyer_id, buyer_role, culture_name, fruit_type,
                    quantity_kg, max_price_per_kg, destination_warehouse,
                    min_caliber_mm, min_soluble_solids_brix, min_quality_score,
                    status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', ?)
            """, (
                bid_id,
                data["buyer_id"],
                data.get("buyer_role", "Retailer"),
                data["culture_name"],
                data.get("fruit_type", "apple"),
                float(data["quantity_kg"]),
                float(data["max_price_per_kg"]),
                data["destination_warehouse"],
                data.get("min_caliber_mm"),
                data.get("min_soluble_solids_brix"),
                data.get("min_quality_score"),
                now_str
            ))
            conn.commit()
            conn.close()

        return self.get_bid(bid_id)

    def get_bid(self, bid_id: str) -> Optional[dict]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM bids WHERE bid_id = ?", (bid_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def list_bids(
        self, 
        culture_name: Optional[str] = None, 
        buyer_id: Optional[str] = None,
        status: Optional[str] = "OPEN"
    ) -> List[dict]:
        conn = self._get_conn()
        cursor = conn.cursor()

        query = "SELECT * FROM bids WHERE 1=1"
        params = []

        if status:
            query += " AND status = ?"
            params.append(status)
        if culture_name:
            query += " AND LOWER(culture_name) LIKE ?"
            params.append(f"%{culture_name.lower()}%")
        if buyer_id:
            query += " AND buyer_id = ?"
            params.append(buyer_id)

        query += " ORDER BY max_price_per_kg DESC, created_at DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # -------------------------------------------------------------------------
    # 3. EXECUÇÃO DE DEALS & TRANSAÇÕES
    # -------------------------------------------------------------------------

    def execute_instant_buy(self, buy_req: dict) -> Tuple[Optional[dict], Optional[str]]:
        listing_id = buy_req["listing_id"]
        buyer_id = buy_req["buyer_id"]
        buyer_role = buy_req.get("buyer_role", "Retailer")
        requested_qty = float(buy_req["quantity_kg"])
        dest_warehouse = buy_req["destination_warehouse"]

        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM listings WHERE listing_id = ?", (listing_id,))
            listing = cursor.fetchone()

            if not listing:
                conn.close()
                return None, f"Listing {listing_id} not found."

            if listing["status"] != "OPEN":
                conn.close()
                return None, f"Listing {listing_id} is no longer OPEN (current status: {listing['status']})."

            avail_qty = float(listing["quantity_kg"])
            price_per_kg = float(listing["price_per_kg"])

            if requested_qty > avail_qty:
                conn.close()
                return None, f"Requested quantity ({requested_qty}kg) exceeds available ({avail_qty}kg)."

            deal_id = f"DEAL-{uuid.uuid4().hex[:8].upper()}"
            now_str = get_utc_now_iso()
            total_amount = round(requested_qty * price_per_kg, 2)

            # 1. Inserir Deal
            cursor.execute("""
                INSERT INTO deals (
                    deal_id, deal_type, listing_id, seller_id, seller_role,
                    buyer_id, buyer_role, culture_name, quantity_kg, price_per_kg,
                    total_amount, warehouse_origin, destination_warehouse,
                    delivery_date, batch_id, status, timestamp
                ) VALUES (?, 'INSTANT_BUY', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'CONFIRMED', ?)
            """, (
                deal_id,
                listing_id,
                listing["seller_id"],
                listing["seller_role"],
                buyer_id,
                buyer_role,
                listing["culture_name"],
                requested_qty,
                price_per_kg,
                total_amount,
                listing["warehouse_location"],
                dest_warehouse,
                get_utc_now_date(),
                listing["batch_id"],
                now_str
            ))

            # 2. Atualizar Listing (se esgotou -> FULFILLED, senão deduz quantidade)
            rem_qty = avail_qty - requested_qty
            if rem_qty <= 0.001:
                cursor.execute("UPDATE listings SET quantity_kg = 0, status = 'FULFILLED', updated_at = ? WHERE listing_id = ?", (now_str, listing_id))
            else:
                cursor.execute("UPDATE listings SET quantity_kg = ?, updated_at = ? WHERE listing_id = ?", (rem_qty, now_str, listing_id))

            conn.commit()
            conn.close()

        return self.get_deal(deal_id), None

    def create_supply_contract(self, contract_req: dict) -> dict:
        deal_id = f"DEAL-CTR-{uuid.uuid4().hex[:8].upper()}"
        now_str = get_utc_now_iso()
        qty = float(contract_req["quantity_kg"])
        price = float(contract_req["price_per_kg"])
        total_amount = round(qty * price, 2)

        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO deals (
                    deal_id, deal_type, listing_id, seller_id, seller_role,
                    buyer_id, buyer_role, culture_name, quantity_kg, price_per_kg,
                    total_amount, warehouse_origin, destination_warehouse,
                    delivery_date, batch_id, status, timestamp
                ) VALUES (?, 'FUTURE_CONTRACT', NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'CONFIRMED', ?)
            """, (
                deal_id,
                contract_req["seller_id"],
                contract_req.get("seller_role", "Producer"),
                contract_req["buyer_id"],
                contract_req.get("buyer_role", "Retailer"),
                contract_req["culture_name"],
                qty,
                price,
                total_amount,
                "Farm / Planned Harvest",
                contract_req["destination_warehouse"],
                contract_req["delivery_date"],
                contract_req.get("batch_id"),
                now_str
            ))
            conn.commit()
            conn.close()

        return self.get_deal(deal_id)

    def get_deal(self, deal_id: str) -> Optional[dict]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM deals WHERE deal_id = ?", (deal_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def list_deals(
        self, 
        buyer_id: Optional[str] = None, 
        seller_id: Optional[str] = None,
        culture_name: Optional[str] = None
    ) -> List[dict]:
        conn = self._get_conn()
        cursor = conn.cursor()

        query = "SELECT * FROM deals WHERE 1=1"
        params = []

        if buyer_id:
            query += " AND buyer_id = ?"
            params.append(buyer_id)
        if seller_id:
            query += " AND seller_id = ?"
            params.append(seller_id)
        if culture_name:
            query += " AND LOWER(culture_name) LIKE ?"
            params.append(f"%{culture_name.lower()}%")

        query += " ORDER BY timestamp DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # -------------------------------------------------------------------------
    # 4. INTELIGÊNCIA DE MERCADO (TICKERS & ESTATÍSTICAS)
    # -------------------------------------------------------------------------

    def get_market_stats(self) -> dict:
        conn = self._get_conn()
        cursor = conn.cursor()

        # Total Open Listings
        cursor.execute("SELECT COUNT(*) as c FROM listings WHERE status = 'OPEN'")
        total_active_listings = cursor.fetchone()["c"]

        # Total Open Bids
        cursor.execute("SELECT COUNT(*) as c FROM bids WHERE status = 'OPEN'")
        total_active_bids = cursor.fetchone()["c"]

        # Total Deals Executed
        cursor.execute("SELECT COUNT(*) as c FROM deals")
        total_deals_executed = cursor.fetchone()["c"]

        # Agregação por cultura
        cursor.execute("""
            SELECT 
                culture_name,
                AVG(price_per_kg) as avg_price,
                MIN(price_per_kg) as min_price,
                MAX(price_per_kg) as max_price,
                SUM(quantity_kg) as total_supply
            FROM listings 
            WHERE status = 'OPEN'
            GROUP BY culture_name
        """)
        supply_rows = {r["culture_name"]: dict(r) for r in cursor.fetchall()}

        cursor.execute("""
            SELECT 
                culture_name,
                SUM(quantity_kg) as total_demand
            FROM bids 
            WHERE status = 'OPEN'
            GROUP BY culture_name
        """)
        demand_rows = {r["culture_name"]: r["total_demand"] for r in cursor.fetchall()}

        cursor.execute("""
            SELECT 
                culture_name,
                SUM(quantity_kg) as total_traded
            FROM deals
            GROUP BY culture_name
        """)
        deals_rows = {r["culture_name"]: r["total_traded"] for r in cursor.fetchall()}

        all_cultures = set(list(supply_rows.keys()) + list(demand_rows.keys()) + list(deals_rows.keys()))
        tickers = []

        for c in sorted(all_cultures):
            sup = supply_rows.get(c, {})
            avg_p = round(sup.get("avg_price", 1.20) or 1.20, 2)
            min_p = round(sup.get("min_price", avg_p) or avg_p, 2)
            max_p = round(sup.get("max_price", avg_p) or avg_p, 2)
            supply_kg = round(sup.get("total_supply", 0.0) or 0.0, 1)
            demand_kg = round(demand_rows.get(c, 0.0) or 0.0, 1)
            traded_kg = round(deals_rows.get(c, 0.0) or 0.0, 1)

            tickers.append({
                "culture_name": c,
                "current_avg_price_eur": avg_p,
                "min_price_eur": min_p,
                "max_price_eur": max_p,
                "total_open_supply_kg": supply_kg,
                "total_open_demand_kg": demand_kg,
                "total_deals_24h_kg": traded_kg
            })

        conn.close()

        return {
            "timestamp": get_utc_now_iso(),
            "total_active_listings": total_active_listings,
            "total_active_bids": total_active_bids,
            "total_deals_executed": total_deals_executed,
            "market_tickers": tickers
        }

order_book = OrderBookEngine()
