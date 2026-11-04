import requests
import json
import logging
import os
from typing import Optional, Dict, Any, List
from datetime import datetime
from django.conf import settings
from django.utils.dateparse import parse_datetime

logger = logging.getLogger(__name__)

def _parse_datetime(val: Any) -> Optional[datetime]:
    if not val:
        return None
    if isinstance(val, datetime):
        return val
    val_str = str(val).strip()
    try:
        dt = parse_datetime(val_str)
        if dt is not None:
            return dt
    except Exception:
        pass
    try:
        val_clean = val_str.replace('Z', '+00:00')
        return datetime.fromisoformat(val_clean)
    except Exception:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d", "%d-%m-%Y %H:%M", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(val_str, fmt)
        except Exception:
            continue
    return None

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

    # -------------------------------------------------------------------------
    # 5. ADAPTADORES DE DADOS (COMPATIBILIDADE COM TEMPLATES DJANGO)
    # -------------------------------------------------------------------------

    def get_open_orders_adapted(self, culture_name: Optional[str] = None) -> List['MarketplaceOrderItem']:
        """
        Retorna ofertas abertas (SELL) e ordens de compra abertas (BUY)
        encapsuladas em objetos compatíveis com os templates do Django.
        """
        items = []
        # 1. Listings (SELL)
        listings = self.fetch_open_listings(culture_name=culture_name)
        for l in listings:
            items.append(MarketplaceOrderItem(l, order_type='SELL'))

        # 2. Bids (BUY)
        bids = self.fetch_open_bids(culture_name=culture_name)
        for b in bids:
            items.append(MarketplaceOrderItem(b, order_type='BUY'))

        return items

    def get_closed_deals_adapted(self, username: Optional[str] = None) -> List['MarketplaceDealItem']:
        """
        Retorna transações concluídas / contratos celebrados como objetos adaptados.
        """
        deals = self.fetch_deals()
        adapted = []
        for d in deals:
            if username:
                b_id = str(d.get('buyer_id', ''))
                s_id = str(d.get('seller_id', ''))
                u_str = str(username)
                if u_str not in [b_id, s_id]:
                    continue
            adapted.append(MarketplaceDealItem(d))
        return adapted

    def get_contracts_adapted(self, buyer_username: Optional[str] = None) -> List['MarketplaceDealItem']:
        """
        Retorna apenas os contratos de fornecimento celebrados (Supply Contracts).
        """
        deals = self.fetch_deals()
        adapted = []
        for d in deals:
            if d.get('deal_type') == 'CONTRACT':
                if buyer_username and str(d.get('buyer_id')) != str(buyer_username):
                    continue
                adapted.append(MarketplaceDealItem(d))
        return adapted


class UserStub:
    def __init__(self, username: str, user_id: Any = None):
        self.username = str(username)
        self.id = user_id or username
        self.pk = self.id

    def __str__(self):
        return self.username


class CultureStub:
    def __init__(self, name: str, fruit_type: str = "apple"):
        self.name = str(name)
        self.fruit_type = fruit_type
        self.pk = name

    def __str__(self):
        return self.name


class MarketplaceOrderItem:
    """
    Objeto de adaptação que espelha os atributos de um MarketplaceOrder
    permitindo que os templates Django existentes continuem a renderizar sem erros.
    """
    def __init__(self, data: Dict[str, Any], order_type: str = 'SELL'):
        self.raw = data
        self.pk = data.get('listing_id') or data.get('bid_id') or data.get('id')
        self.id = self.pk
        self.order_type = order_type
        
        user_id = data.get('seller_id') if order_type == 'SELL' else data.get('buyer_id')
        role = data.get('seller_role') if order_type == 'SELL' else data.get('buyer_role')
        self.role = role or ('Producer' if order_type == 'SELL' else 'Retailer')
        self.requester = UserStub(user_id or 'MarketUser', user_id)
        self.fulfilled_by = None
        
        c_name = data.get('culture_name', 'Cultura')
        f_type = data.get('fruit_type', 'apple')
        self.culture = CultureStub(c_name, f_type)
        self.subfamily = self.culture
        
        self.quantity_kg = float(data.get('quantity_kg', 0.0))
        self.price_per_kg = float(data.get('price_per_kg') or data.get('max_price_per_kg') or 0.0)
        self.warehouse_location = data.get('warehouse_location') or data.get('destination_warehouse') or 'Mercado Central'
        
        q_metrics = data.get('quality_metrics') or {}
        self.caliber = data.get('caliber') or q_metrics.get('caliber_mm')
        self.soluble_solids = data.get('soluble_solids') or q_metrics.get('soluble_solids_brix')
        self.quality_score = data.get('quality_score') or q_metrics.get('quality_score')
        
        self.min_caliber = data.get('min_caliber_mm')
        self.min_soluble_solids = data.get('min_soluble_solids_brix')
        self.min_quality_score = data.get('min_quality_score')
        
        self.packaging_type = data.get('packaging_type', 'Granel')
        self.preservation_treatment = data.get('preservation_treatment', 'Natural')
        self.batch_id = data.get('batch_id')
        
        self.status = data.get('status', 'OPEN')
        self.transport_status = 'PENDING'
        raw_created_at = data.get('created_at')
        self.created_at = _parse_datetime(raw_created_at)
        self.fulfilled_at = None

    @property
    def get_order_type_display(self):
        return 'Export Offer (Venda/Exportação)' if self.order_type == 'SELL' else 'Purchase Request (Compra)'

    @property
    def total_price(self):
        return self.quantity_kg * self.price_per_kg

    def __str__(self):
        return f"{self.order_type} - {self.culture.name} ({self.quantity_kg}kg) by {self.requester.username}"


class MarketplaceDealItem:
    """
    Objeto de adaptação para transações e contratos celebrados no Marketplace Web Service.
    """
    def __init__(self, data: Dict[str, Any]):
        self.raw = data
        self.pk = data.get('deal_id') or data.get('id')
        self.id = self.pk
        self.deal_type = data.get('deal_type', 'INSTANT') # INSTANT ou CONTRACT
        
        self.order_type = 'BUY'
        self.role = data.get('buyer_role', 'Retailer')
        
        b_id = data.get('buyer_id', 'Buyer')
        s_id = data.get('seller_id', 'Seller')
        self.requester = UserStub(b_id, b_id)
        self.fulfilled_by = UserStub(s_id, s_id)
        self.buyer = self.requester
        self.producer = self.fulfilled_by
        
        c_name = data.get('culture_name', 'Cultura')
        self.culture = CultureStub(c_name)
        self.subfamily = self.culture
        
        self.quantity_kg = float(data.get('quantity_kg', 0.0))
        self.price_per_kg = float(data.get('price_per_kg', 0.0))
        self.total_price = float(data.get('total_value', self.quantity_kg * self.price_per_kg))
        self.warehouse_origin = data.get('warehouse_origin') or 'Armazém Produtor'
        self.destination_warehouse = data.get('destination_warehouse') or data.get('warehouse_location', '')
        self.warehouse_location = self.destination_warehouse
        raw_delivery_date = data.get('delivery_date')
        self.delivery_date = _parse_datetime(raw_delivery_date) if raw_delivery_date else None
        
        # Mapeamento do status
        st = data.get('status', 'APPROVED')
        if st == 'COMPLETED':
            self.status = 'fulfilled' if self.deal_type == 'CONTRACT' else 'APPROVED'
        elif st == 'PENDING':
            self.status = 'pending'
        else:
            self.status = st
            
        self.transport_status = data.get('transport_status', 'DELIVERED')
        raw_created_at = data.get('timestamp') or data.get('executed_at') or data.get('created_at')
        self.created_at = _parse_datetime(raw_created_at)
        self.fulfilled_at = self.created_at
        self.actual_delivery_date = self.created_at
        self.harvest_origin = None
        self.vehicle = None

    @property
    def total_pallets(self):
        return round(self.quantity_kg / 500.0, 1) if self.quantity_kg else 0

    @property
    def total_crates(self):
        return int(self.quantity_kg / 20.0) if self.quantity_kg else 0

    @property
    def get_order_type_display(self):
        return 'Contrato Futuro' if self.deal_type == 'CONTRACT' else 'Compra Imediata'

    def __str__(self):
        return f"Deal #{self.pk} - {self.culture.name} ({self.quantity_kg}kg) {self.requester.username} -> {self.fulfilled_by.username}"


marketplace_service = MarketplaceService()

