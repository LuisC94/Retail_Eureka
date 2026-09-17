import requests
import json
import logging
import os
from typing import Optional, Dict, Any, List
from django.conf import settings

logger = logging.getLogger(__name__)

# Configuração da URL do Marketplace Web Service
MARKETPLACE_API_URL = getattr(
    settings, 
    'MARKETPLACE_API_URL', 
    os.environ.get("MARKETPLACE_API_URL", "http://127.0.0.1:8004")
)

REQUEST_TIMEOUT_SECONDS = 5


class MarketplaceService:
    """
    Cliente de integração Django com o Marketplace Web Service central (FastAPI).
    Permite aos nós privados locais (Edge) publicar ofertas, consultar a liquidez do mercado,
    fechar transações e aceder a inteligência de preços agroalimentares.
    """

    def __init__(self, base_url: str = None, timeout: int = REQUEST_TIMEOUT_SECONDS):
        self.base_url = (base_url or MARKETPLACE_API_URL).rstrip("/")
        self.timeout = timeout

    def check_health(self) -> bool:
        """Verifica se o microserviço de Marketplace está online e responsivo."""
        try:
            resp = requests.get(f"{self.base_url}/health", timeout=self.timeout)
            return resp.status_code == 200 and resp.json().get("status") == "healthy"
        except Exception as e:
            logger.warning(f"[MarketplaceService] Falha de comunicação com {self.base_url}/health: {e}")
            return False

    # -------------------------------------------------------------------------
    # 1. GESTÃO DE LISTINGS (VENDAS)
    # -------------------------------------------------------------------------

    def publish_listing(
        self,
        seller_id: str,
        culture_name: str,
        quantity_kg: float,
        price_per_kg: float,
        warehouse_location: str,
        batch_id: Optional[str] = None,
        quality_metrics: Optional[Dict[str, Any]] = None,
        packaging_type: str = "Granel (Sem embalagem)",
        preservation_treatment: str = "Natural",
        seller_role: str = "Producer",
        fruit_type: str = "apple"
    ) -> Optional[Dict[str, Any]]:
        """
        Publica uma nova oferta de venda no Order Book central.
        """
        url = f"{self.base_url}/listings"
        payload = {
            "seller_id": str(seller_id),
            "seller_role": str(seller_role),
            "culture_name": str(culture_name),
            "fruit_type": str(fruit_type),
            "quantity_kg": float(quantity_kg),
            "price_per_kg": float(price_per_kg),
            "warehouse_location": str(warehouse_location),
            "batch_id": str(batch_id) if batch_id else None,
            "quality_metrics": quality_metrics or {},
            "packaging_type": packaging_type,
            "preservation_treatment": preservation_treatment
        }

        try:
            resp = requests.post(url, json=payload, timeout=self.timeout)
            if resp.status_code in [200, 201]:
                return resp.json()
            else:
                logger.error(f"[MarketplaceService] Erro ao publicar listing ({resp.status_code}): {resp.text}")
                return None
        except Exception as e:
            logger.error(f"[MarketplaceService] Exceção ao contactar marketplace ({url}): {e}")
            return None

    def fetch_open_listings(
        self,
        culture_name: Optional[str] = None,
        seller_id: Optional[str] = None,
        max_price: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Consulta as ofertas de venda ativas no mercado.
        """
        url = f"{self.base_url}/listings"
        params = {"status": "OPEN"}
        if culture_name:
            params["culture_name"] = culture_name
        if seller_id:
            params["seller_id"] = seller_id
        if max_price is not None:
            params["max_price"] = max_price

        try:
            resp = requests.get(url, params=params, timeout=self.timeout)
            if resp.status_code == 200:
                return resp.json()
            logger.error(f"[MarketplaceService] Erro ao listar listings: {resp.text}")
            return []
        except Exception as e:
            logger.warning(f"[MarketplaceService] Marketplace inacessível ao listar ofertas: {e}")
            return []

    def get_listing(self, listing_id: str) -> Optional[Dict[str, Any]]:
        """Obtém detalhes de uma oferta específica."""
        url = f"{self.base_url}/listings/{listing_id}"
        try:
            resp = requests.get(url, timeout=self.timeout)
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception as e:
            logger.warning(f"[MarketplaceService] Erro ao obter listing {listing_id}: {e}")
            return None

    def cancel_listing(self, listing_id: str) -> bool:
        """Cancela uma oferta de venda."""
        url = f"{self.base_url}/listings/{listing_id}"
        try:
            resp = requests.delete(url, timeout=self.timeout)
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"[MarketplaceService] Erro ao cancelar listing {listing_id}: {e}")
            return False

    # -------------------------------------------------------------------------
    # 2. GESTÃO DE BIDS (COMPRAS / PROCURA)
    # -------------------------------------------------------------------------

    def publish_bid(
        self,
        buyer_id: str,
        culture_name: str,
        quantity_kg: float,
        max_price_per_kg: float,
        destination_warehouse: str,
        min_caliber_mm: Optional[float] = None,
        min_soluble_solids_brix: Optional[float] = None,
        min_quality_score: Optional[float] = None,
        buyer_role: str = "Retailer",
        fruit_type: str = "apple"
    ) -> Optional[Dict[str, Any]]:
        """
        Regista uma ordem de compra ou procura por produto agroalimentar.
        """
        url = f"{self.base_url}/bids"
        payload = {
            "buyer_id": str(buyer_id),
            "buyer_role": str(buyer_role),
            "culture_name": str(culture_name),
            "fruit_type": str(fruit_type),
            "quantity_kg": float(quantity_kg),
            "max_price_per_kg": float(max_price_per_kg),
            "destination_warehouse": str(destination_warehouse),
            "min_caliber_mm": min_caliber_mm,
            "min_soluble_solids_brix": min_soluble_solids_brix,
            "min_quality_score": min_quality_score
        }

        try:
            resp = requests.post(url, json=payload, timeout=self.timeout)
            if resp.status_code in [200, 201]:
                return resp.json()
            logger.error(f"[MarketplaceService] Erro ao registar bid: {resp.text}")
            return None
        except Exception as e:
            logger.error(f"[MarketplaceService] Exceção ao registar bid: {e}")
            return None

    def fetch_open_bids(
        self,
        culture_name: Optional[str] = None,
        buyer_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Consulta as ordens de compra ativas."""
        url = f"{self.base_url}/bids"
        params = {"status": "OPEN"}
        if culture_name:
            params["culture_name"] = culture_name
        if buyer_id:
            params["buyer_id"] = buyer_id

        try:
            resp = requests.get(url, params=params, timeout=self.timeout)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            logger.warning(f"[MarketplaceService] Erro ao listar bids: {e}")
            return []

    # -------------------------------------------------------------------------
    # 3. EXECUÇÃO DE DEALS & CONTRATOS
    # -------------------------------------------------------------------------

    def execute_instant_buy(
        self,
        listing_id: str,
        buyer_id: str,
        quantity_kg: float,
        destination_warehouse: str,
        buyer_role: str = "Retailer",
        payment_terms: str = "30 dias"
    ) -> Optional[Dict[str, Any]]:
        """
        Executa uma compra imediata contra uma oferta listada no Order Book.
        """
        url = f"{self.base_url}/deals/instant_buy"
        payload = {
            "listing_id": str(listing_id),
            "buyer_id": str(buyer_id),
            "buyer_role": str(buyer_role),
            "quantity_kg": float(quantity_kg),
            "destination_warehouse": str(destination_warehouse),
            "payment_terms": payment_terms
        }

        try:
            resp = requests.post(url, json=payload, timeout=self.timeout)
            if resp.status_code in [200, 201]:
                return resp.json()
            logger.error(f"[MarketplaceService] Erro ao executar instant buy: {resp.text}")
            return None
        except Exception as e:
            logger.error(f"[MarketplaceService] Exceção em instant buy: {e}")
            return None

    def create_supply_contract(
        self,
        buyer_id: str,
        seller_id: str,
        culture_name: str,
        quantity_kg: float,
        price_per_kg: float,
        delivery_date: str,
        destination_warehouse: str,
        batch_id: Optional[str] = None,
        buyer_role: str = "Retailer",
        seller_role: str = "Producer"
    ) -> Optional[Dict[str, Any]]:
        """
        Celebra um contrato de fornecimento futuro.
        """
        url = f"{self.base_url}/deals/contract"
        payload = {
            "buyer_id": str(buyer_id),
            "buyer_role": str(buyer_role),
            "seller_id": str(seller_id),
            "seller_role": str(seller_role),
            "culture_name": str(culture_name),
            "quantity_kg": float(quantity_kg),
            "price_per_kg": float(price_per_kg),
            "delivery_date": str(delivery_date),
            "destination_warehouse": str(destination_warehouse),
            "batch_id": batch_id
        }

        try:
            resp = requests.post(url, json=payload, timeout=self.timeout)
            if resp.status_code in [200, 201]:
                return resp.json()
            logger.error(f"[MarketplaceService] Erro ao criar supply contract: {resp.text}")
            return None
        except Exception as e:
            logger.error(f"[MarketplaceService] Exceção ao criar supply contract: {e}")
            return None

    def fetch_deals(
        self,
        buyer_id: Optional[str] = None,
        seller_id: Optional[str] = None,
        culture_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Consulta o histórico de transações / deals celebrados."""
        url = f"{self.base_url}/deals"
        params = {}
        if buyer_id:
            params["buyer_id"] = buyer_id
        if seller_id:
            params["seller_id"] = seller_id
        if culture_name:
            params["culture_name"] = culture_name

        try:
            resp = requests.get(url, params=params, timeout=self.timeout)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            logger.warning(f"[MarketplaceService] Erro ao listar deals: {e}")
            return []

    # -------------------------------------------------------------------------
    # 4. INTELIGÊNCIA DE PREÇOS (TICKERS)
    # -------------------------------------------------------------------------

    def fetch_market_prices(self) -> Optional[Dict[str, Any]]:
        """
        Obtém as cotações de preços em tempo real e estatísticas agregadas por cultura.
        """
        url = f"{self.base_url}/market/prices"
        try:
            resp = requests.get(url, timeout=self.timeout)
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception as e:
            logger.warning(f"[MarketplaceService] Erro ao obter market prices: {e}")
            return None


marketplace_service = MarketplaceService()
