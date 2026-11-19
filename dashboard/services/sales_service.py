"""
Registo de vendas do Processor e do Retailer.

Uma venda sai diretamente do stock (ConsolidatedStock) do armazém escolhido, sem passar pelo marketplace.
  - O stock desce no armazém de saída. Os lotes (receções) que saem são os mais antigos (FIFO): os agentes e o
    ciclo de vida já calculam os lotes presentes a partir da quantidade atual, das receções mais recentes para
    as mais antigas, por isso baixar o stock "consome" automaticamente os lotes mais antigos.
  - O total do dia (kg e preço médio pesado) é somado ao HistoricalSalesData, o histórico usado pelo forecast
    e pelos agentes. Não há retreino.
  - Comprador vazio = cliente externo. Se o comprador for um utilizador da plataforma (Processor/Retailer),
    cria-se uma receção pendente do lado dele: o stock só lhe entra quando a confirmar.
  - Vendas fechadas no marketplace ficam registadas automaticamente (origem MARKETPLACE), sem voltar a
    descontar o stock (o marketplace já o faz).
"""
import datetime
import logging
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

BUYER_ROLES = ('Processor', 'Retailer')
TWO = Decimal('0.01')


class SaleError(Exception):
    """Erro de validação apresentado ao utilizador."""


def _decimal(value, label, required=True):
    if value is None or str(value).strip() == '':
        if required:
            raise SaleError(f"Indique {label}.")
        return None
    try:
        return Decimal(str(value).replace(',', '.').strip())
    except (InvalidOperation, ValueError):
        raise SaleError(f"Valor inválido para {label}: '{value}'.")


def _date(value):
    if not value:
        return timezone.now().date()
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except ValueError:
        raise SaleError(f"Data inválida: '{value}'.")


def platform_buyers(exclude_user=None):
    """Utilizadores da plataforma a quem se pode registar uma venda (Processor/Retailer)."""
    qs = User.objects.filter(groups__name__in=BUYER_ROLES, is_active=True).distinct().order_by('username')
    if exclude_user is not None:
        qs = qs.exclude(pk=exclude_user.pk)
    return qs


def add_to_daily_history(owner, culture, sale_date, quantity_kg, price_per_kg):
    """Soma a venda ao total diário (HistoricalSalesData): kg somados, preço médio pesado pelos kg."""
    from dashboard.models import HistoricalSalesData

    qty = Decimal(str(quantity_kg))
    price = Decimal(str(price_per_kg))
    row = (HistoricalSalesData.objects.select_for_update()
           .filter(owner=owner, culture=culture, date=sale_date).first())
    if row is None:
        HistoricalSalesData.objects.create(owner=owner, culture=culture, date=sale_date,
                                           sales_quantity_kg=qty, price_per_kg=price.quantize(TWO, ROUND_HALF_UP))
        return
    old_qty = Decimal(str(row.sales_quantity_kg or 0))
    old_price = Decimal(str(row.price_per_kg or 0))
    total = old_qty + qty
    row.price_per_kg = ((old_qty * old_price + qty * price) / total).quantize(TWO, ROUND_HALF_UP) if total > 0 else price
    row.sales_quantity_kg = total
    row.save(update_fields=['sales_quantity_kg', 'price_per_kg'])


def _open_buyer_reception(sale, seller, buyer):
    """Venda a um utilizador da plataforma: receção pendente do lado do comprador (stock só entra ao confirmar)."""
    from dashboard.models import Warehouse
    from dashboard.services.reception_service import register_pending_reception, warehouse_label

    wh = Warehouse.objects.filter(owner=buyer).order_by('location').first()
    deal = {
        'deal_id': f"SALE-{sale.pk}",
        'deal_type': 'DIRECT_SALE',
        'seller_id': seller.username,
        'culture_name': sale.culture.name,
        'quantity_kg': float(sale.quantity_kg),
        'delivery_date': sale.sale_date.isoformat(),
    }
    return register_pending_reception(deal, buyer, warehouse_label(wh) if wh else '',
                                      expected_date=sale.sale_date, culture=sale.culture)


def register_sale(seller, stock_id, quantity_kg, price_per_kg, sale_date=None, buyer_id=None,
                  customer_name='', invoice_ref='', notes='', source=None, check_duplicates=True):
    """
    Regista uma venda a partir de uma linha de stock do vendedor (cultura + armazém).
    Devolve a SaleRecord criada. Lança SaleError com mensagem legível em caso de dados inválidos.
    """
    from dashboard.models import ConsolidatedStock, SaleRecord

    qty = _decimal(quantity_kg, "a quantidade (kg)")
    price = _decimal(price_per_kg, "o preço (€/kg)")
    if qty <= 0:
        raise SaleError("A quantidade tem de ser superior a 0.")
    if price < 0:
        raise SaleError("O preço não pode ser negativo.")
    sale_date = _date(sale_date)
    if sale_date > timezone.now().date():
        raise SaleError("A data da venda não pode ser no futuro.")

    buyer = None
    if buyer_id not in (None, ''):
        buyer = platform_buyers(exclude_user=seller).filter(pk=buyer_id).first() if str(buyer_id).isdigit() else None
        if buyer is None:
            raise SaleError("O comprador escolhido não existe na plataforma.")

    invoice_ref = (invoice_ref or '').strip()

    with transaction.atomic():
        stock = (ConsolidatedStock.objects.select_for_update().select_related('culture')
                 .filter(pk=stock_id, owner=seller).first()) if str(stock_id or '').isdigit() else None
        if stock is None:
            raise SaleError("Selecione a cultura e o armazém de onde sai a venda.")
        # Uma fatura pode ter várias linhas (culturas); duplicado = mesma fatura, cultura, armazém e kg
        if check_duplicates and invoice_ref and SaleRecord.objects.filter(
                seller=seller, invoice_ref__iexact=invoice_ref, culture=stock.culture,
                warehouse_location=stock.warehouse_location, quantity_kg=qty.quantize(TWO)).exists():
            raise SaleError(f"Esta venda já está registada (fatura '{invoice_ref}', {stock.culture.name}, {qty} kg).")
        available = Decimal(str(stock.quantity or 0))
        if qty > available:
            raise SaleError(f"Stock insuficiente: {stock.culture.name} em {stock.warehouse_location} tem "
                            f"{available.quantize(TWO)} kg disponíveis.")

        stock.quantity = available - qty
        stock.save(update_fields=['quantity'])

        sale = SaleRecord.objects.create(
            seller=seller, sale_date=sale_date, culture=stock.culture, stock=stock,
            warehouse_location=stock.warehouse_location, quantity_kg=qty, price_per_kg=price.quantize(TWO, ROUND_HALF_UP),
            buyer=buyer, customer_name='' if buyer else (customer_name or '').strip()[:150],
            invoice_ref=invoice_ref, notes=(notes or '').strip(), source=source or SaleRecord.SOURCE_MANUAL,
        )
        add_to_daily_history(seller, stock.culture, sale_date, qty, sale.price_per_kg)

        if buyer is not None:
            sale.reception = _open_buyer_reception(sale, seller, buyer)
            sale.save(update_fields=['reception'])
    return sale


def record_marketplace_sale(deal):
    """
    Regista do lado do vendedor (Processor/Retailer) uma venda fechada no marketplace. Idempotente por deal_id.
    Não mexe no stock: o marketplace já o descontou.
    """
    from dashboard.models import ProductSubFamily, SaleRecord

    if not deal or deal.get('seller_role') not in BUYER_ROLES:
        return None
    deal_id = str(deal.get('deal_id') or '').strip()
    qty = Decimal(str(deal.get('quantity_kg') or 0))
    seller = User.objects.filter(username=deal.get('seller_id')).first()
    culture = ProductSubFamily.objects.filter(name=deal.get('culture_name')).first()
    if not deal_id or qty <= 0 or seller is None or culture is None:
        return None
    if SaleRecord.objects.filter(deal_id=deal_id).exists():
        return None
    try:
        sale_date = _date(deal.get('timestamp'))
    except SaleError:
        sale_date = timezone.now().date()
    price = Decimal(str(deal.get('price_per_kg') or 0)).quantize(TWO, ROUND_HALF_UP)
    buyer = User.objects.filter(username=deal.get('buyer_id')).first()

    with transaction.atomic():
        sale = SaleRecord.objects.create(
            seller=seller, sale_date=sale_date, culture=culture,
            warehouse_location=str(deal.get('warehouse_origin') or ''), quantity_kg=qty, price_per_kg=price,
            buyer=buyer, customer_name='' if buyer else str(deal.get('buyer_id') or ''),
            source=SaleRecord.SOURCE_MARKETPLACE, deal_id=deal_id,
        )
        add_to_daily_history(seller, culture, sale_date, qty, price)
    return sale


def sales_context(user, limit=50):
    """Contexto da aba Vendas: linhas de stock disponíveis, compradores da plataforma e últimas vendas."""
    from dashboard.models import ConsolidatedStock, SaleRecord

    stock_options = []
    for s in (ConsolidatedStock.objects.filter(owner=user, quantity__gt=0).select_related('culture')
              .order_by('culture__name', 'warehouse_location')):
        stock_options.append({'pk': s.pk, 'culture': s.culture.name, 'warehouse': s.warehouse_location,
                              'quantity': float(s.quantity)})
    sales = list(SaleRecord.objects.filter(seller=user)
                 .select_related('culture', 'buyer', 'reception')[:limit])
    today = timezone.now().date()
    today_sales = SaleRecord.objects.filter(seller=user, sale_date=today)
    today_kg = sum((s.quantity_kg for s in today_sales), Decimal('0'))
    today_eur = sum((s.quantity_kg * s.price_per_kg for s in today_sales), Decimal('0'))
    return {
        'sale_stock_options': stock_options,
        'sale_buyers': list(platform_buyers(exclude_user=user)),
        'recent_sales': sales,
        'sales_today_kg': today_kg,
        'sales_today_eur': today_eur,
    }
