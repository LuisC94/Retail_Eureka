from typing import List, Optional, Dict, Any, Union, Literal
from datetime import datetime
from pydantic import BaseModel, Field

# =============================================================================
# PYDANTIC DATA CONTRACTS FOR MARKETPLACE WEB SERVICE
# =============================================================================

class QualityMetrics(BaseModel):
    caliber_mm: Optional[float] = Field(None, description="Fruit caliber in mm (e.g. 75.0)")
    soluble_solids_brix: Optional[float] = Field(None, description="Soluble solids in °Brix (e.g. 13.5)")
    quality_score: Optional[float] = Field(None, description="Overall quality score (1 to 10 or 0 to 100)")
    acidity_percent: Optional[float] = Field(None, description="Acidity percentage")


class ListingCreate(BaseModel):
    seller_id: str = Field(..., description="Seller username or enterprise identifier (e.g. 'Produtor_Joao')")
    seller_role: str = Field("Producer", description="Role of seller: 'Producer', 'Processor', 'Wholesaler'")
    culture_name: str = Field(..., description="Crop / Variety name (e.g. 'Maçã Gala', 'Kiwi Hayward')")
    fruit_type: str = Field("apple", description="Fruit category (e.g. 'apple', 'kiwi', 'strawberry')")
    quantity_kg: float = Field(..., gt=0, description="Quantity available for sale in Kg")
    price_per_kg: float = Field(..., gt=0, description="Asking price per Kg in EUR")
    warehouse_location: str = Field(..., description="Origin warehouse/city (e.g. 'Armazém Alcobaça')")
    batch_id: Optional[str] = Field(None, description="Batch reference code (e.g. 'LOTE-101')")
    quality_metrics: QualityMetrics = Field(default_factory=QualityMetrics)
    packaging_type: Optional[str] = Field("Granel (Sem embalagem)", description="Packaging type")
    preservation_treatment: Optional[str] = Field("Natural", description="Preservation method")


class ListingResponse(BaseModel):
    listing_id: str = Field(..., description="Unique Listing ID (e.g. 'LST-1001')")
    seller_id: str
    seller_role: str
    culture_name: str
    fruit_type: str
    quantity_kg: float
    price_per_kg: float
    warehouse_location: str
    batch_id: Optional[str] = None
    quality_metrics: QualityMetrics
    packaging_type: Optional[str] = None
    preservation_treatment: Optional[str] = None
    status: Literal["OPEN", "MATCHED", "FULFILLED", "CANCELLED"] = "OPEN"
    created_at: str
    updated_at: str


class BidCreate(BaseModel):
    buyer_id: str = Field(..., description="Buyer username or enterprise identifier (e.g. 'Continente_Azambuja')")
    buyer_role: str = Field("Retailer", description="Role of buyer: 'Retailer', 'Processor', 'Consumer'")
    culture_name: str = Field(..., description="Target crop / variety name")
    fruit_type: str = Field("apple", description="Target fruit category")
    quantity_kg: float = Field(..., gt=0, description="Desired quantity in Kg")
    max_price_per_kg: float = Field(..., gt=0, description="Maximum budget price per Kg in EUR")
    destination_warehouse: str = Field(..., description="Delivery destination warehouse/city")
    min_caliber_mm: Optional[float] = None
    min_soluble_solids_brix: Optional[float] = None
    min_quality_score: Optional[float] = None


class BidResponse(BaseModel):
    bid_id: str = Field(..., description="Unique Bid ID (e.g. 'BID-2001')")
    buyer_id: str
    buyer_role: str
    culture_name: str
    fruit_type: str
    quantity_kg: float
    max_price_per_kg: float
    destination_warehouse: str
    min_caliber_mm: Optional[float] = None
    min_soluble_solids_brix: Optional[float] = None
    min_quality_score: Optional[float] = None
    status: Literal["OPEN", "MATCHED", "FULFILLED", "CANCELLED"] = "OPEN"
    created_at: str


class InstantBuyRequest(BaseModel):
    listing_id: str = Field(..., description="ID of the listing to purchase")
    buyer_id: str = Field(..., description="Buyer username or enterprise ID")
    buyer_role: str = Field("Retailer", description="Buyer role")
    quantity_kg: float = Field(..., gt=0, description="Quantity to buy in Kg (can be partial or total)")
    destination_warehouse: str = Field(..., description="Destination warehouse location")
    payment_terms: Optional[str] = Field("30 dias", description="Commercial payment terms")


class SupplyContractRequest(BaseModel):
    buyer_id: str = Field(..., description="Buyer enterprise ID (e.g. 'Continente')")
    buyer_role: str = Field("Retailer", description="Buyer role")
    seller_id: str = Field(..., description="Seller enterprise ID (e.g. 'Produtor_Joao')")
    seller_role: str = Field("Producer", description="Seller role")
    culture_name: str = Field(..., description="Crop / Variety name")
    quantity_kg: float = Field(..., gt=0, description="Contracted quantity in Kg")
    price_per_kg: float = Field(..., gt=0, description="Agreed fixed price per Kg in EUR")
    delivery_date: str = Field(..., description="Future delivery date YYYY-MM-DD")
    destination_warehouse: str = Field(..., description="Delivery warehouse")
    batch_id: Optional[str] = None


class DealResponse(BaseModel):
    deal_id: str = Field(..., description="Unique Deal ID (e.g. 'DEAL-3001')")
    deal_type: Literal["INSTANT_BUY", "FUTURE_CONTRACT"]
    listing_id: Optional[str] = None
    seller_id: str
    seller_role: str
    buyer_id: str
    buyer_role: str
    culture_name: str
    quantity_kg: float
    price_per_kg: float
    total_amount: float
    warehouse_origin: str
    destination_warehouse: str
    delivery_date: Optional[str] = None
    batch_id: Optional[str] = None
    status: Literal["CONFIRMED", "IN_TRANSIT", "DELIVERED", "CANCELLED"] = "CONFIRMED"
    timestamp: str


class CulturePriceStats(BaseModel):
    culture_name: str
    current_avg_price_eur: float
    min_price_eur: float
    max_price_eur: float
    total_open_supply_kg: float
    total_open_demand_kg: float
    total_deals_24h_kg: float


class MarketStatsResponse(BaseModel):
    timestamp: str
    total_active_listings: int
    total_active_bids: int
    total_deals_executed: int
    market_tickers: List[CulturePriceStats]
