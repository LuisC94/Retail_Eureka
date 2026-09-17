from datetime import datetime, timezone
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from schemas import (
    ListingCreate,
    ListingResponse,
    BidCreate,
    BidResponse,
    InstantBuyRequest,
    SupplyContractRequest,
    DealResponse,
    MarketStatsResponse,
)
from engine.order_book import order_book

app = FastAPI(
    title="Retail Eureka - Agri-Food Marketplace Web Service",
    description="Microserviço centralizado de Order Book, Matching e Clearinghouse para transações agroalimentares e inteligência de mercado.",
    version="1.0.0"
)

# Enable CORS for Django edge nodes and external integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# HEALTH & MONITORING ENDPOINTS
# =============================================================================

@app.get("/health", tags=["Health"])
def health_check():
    """Verifica a saúde do Marketplace Web Service."""
    return {
        "status": "healthy",
        "service": "marketplace_service",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/status", tags=["Health"])
def service_status():
    """Estatísticas globais e estado da clearinghouse."""
    stats = order_book.get_market_stats()
    return {
        "service": "marketplace_service",
        "status": "operational",
        "stats": stats
    }


# =============================================================================
# 1. LISTINGS (OFERTAS DE VENDA)
# =============================================================================

@app.post("/listings", response_model=ListingResponse, status_code=status.HTTP_201_CREATED, tags=["Listings"])
def create_listing(payload: ListingCreate):
    """
    Publica uma nova oferta de venda no Order Book.
    """
    try:
        created = order_book.create_listing(payload.dict())
        return created
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao criar oferta de venda: {str(e)}")


@app.get("/listings", response_model=List[ListingResponse], tags=["Listings"])
def list_listings(
    culture_name: Optional[str] = Query(None, description="Filtrar por nome de cultura (ex: 'Maçã Gala')"),
    seller_id: Optional[str] = Query(None, description="Filtrar por ID de vendedor"),
    max_price: Optional[float] = Query(None, description="Preço máximo por kg em EUR"),
    status: Optional[str] = Query("OPEN", description="Estado: OPEN, MATCHED, FULFILLED, CANCELLED ou vazio para todos")
):
    """
    Lista ofertas de venda ativas no mercado com filtros opcionais.
    """
    filter_status = status if status else None
    return order_book.list_listings(
        culture_name=culture_name,
        seller_id=seller_id,
        max_price=max_price,
        status=filter_status
    )


@app.get("/listings/{listing_id}", response_model=ListingResponse, tags=["Listings"])
def get_listing(listing_id: str):
    """
    Obtém os detalhes de uma oferta de venda específica.
    """
    listing = order_book.get_listing(listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail=f"Oferta {listing_id} não encontrada.")
    return listing


@app.delete("/listings/{listing_id}", tags=["Listings"])
def cancel_listing(listing_id: str):
    """
    Cancela uma oferta de venda existente.
    """
    success = order_book.cancel_listing(listing_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Oferta {listing_id} não encontrada ou já cancelada.")
    return {"message": f"Oferta {listing_id} cancelada com sucesso.", "status": "CANCELLED"}


# =============================================================================
# 2. BIDS (ORDENS DE COMPRA / PROCURA)
# =============================================================================

@app.post("/bids", response_model=BidResponse, status_code=status.HTTP_201_CREATED, tags=["Bids"])
def create_bid(payload: BidCreate):
    """
    Regista uma ordem de compra ou procura por um produto/cultura.
    """
    try:
        created = order_book.create_bid(payload.dict())
        return created
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao registar ordem de compra: {str(e)}")


@app.get("/bids", response_model=List[BidResponse], tags=["Bids"])
def list_bids(
    culture_name: Optional[str] = Query(None, description="Filtrar por cultura"),
    buyer_id: Optional[str] = Query(None, description="Filtrar por comprador"),
    status: Optional[str] = Query("OPEN", description="Estado da ordem: OPEN, MATCHED, CANCELLED")
):
    """
    Lista ordens de compra ativas no mercado.
    """
    filter_status = status if status else None
    return order_book.list_bids(
        culture_name=culture_name,
        buyer_id=buyer_id,
        status=filter_status
    )


@app.get("/bids/{bid_id}", response_model=BidResponse, tags=["Bids"])
def get_bid(bid_id: str):
    """
    Obtém os detalhes de uma ordem de compra específica.
    """
    bid = order_book.get_bid(bid_id)
    if not bid:
        raise HTTPException(status_code=404, detail=f"Ordem {bid_id} não encontrada.")
    return bid


# =============================================================================
# 3. DEALS & CLEARING (TRANSAÇÕES E CONTRATOS)
# =============================================================================

@app.post("/deals/instant_buy", response_model=DealResponse, status_code=status.HTTP_201_CREATED, tags=["Deals"])
def execute_instant_buy(payload: InstantBuyRequest):
    """
    Executa uma compra imediata contra uma oferta de venda existente (Listing).
    Deduz a quantidade disponível e cria a transação de clearing.
    """
    deal, err = order_book.execute_instant_buy(payload.dict())
    if err:
        raise HTTPException(status_code=400, detail=err)
    return deal


@app.post("/deals/contract", response_model=DealResponse, status_code=status.HTTP_201_CREATED, tags=["Deals"])
def create_supply_contract(payload: SupplyContractRequest):
    """
    Cria um contrato de fornecimento futuro bilateral entre comprador e produtor.
    """
    try:
        deal = order_book.create_supply_contract(payload.dict())
        return deal
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao criar contrato de fornecimento: {str(e)}")


@app.get("/deals", response_model=List[DealResponse], tags=["Deals"])
def list_deals(
    buyer_id: Optional[str] = Query(None, description="Filtrar por comprador"),
    seller_id: Optional[str] = Query(None, description="Filtrar por vendedor"),
    culture_name: Optional[str] = Query(None, description="Filtrar por cultura")
):
    """
    Lista transações e contratos registados no marketplace.
    """
    return order_book.list_deals(
        buyer_id=buyer_id,
        seller_id=seller_id,
        culture_name=culture_name
    )


@app.get("/deals/{deal_id}", response_model=DealResponse, tags=["Deals"])
def get_deal(deal_id: str):
    """
    Obtém detalhes de um deal específico.
    """
    deal = order_book.get_deal(deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail=f"Deal {deal_id} não encontrado.")
    return deal


# =============================================================================
# 4. INTELIGÊNCIA DE MERCADO (TICKERS & ESTATÍSTICAS)
# =============================================================================

@app.get("/market/prices", response_model=MarketStatsResponse, tags=["Market Intelligence"])
def get_market_prices():
    """
    Retorna cotações de preços em tempo real, volume de oferta/procura aberta e transações agregadas por cultura.
    """
    return order_book.get_market_stats()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8004, reload=True)

