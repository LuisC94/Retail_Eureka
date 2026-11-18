"""
Receção de mercadoria dos negócios do marketplace.

Fluxo:
  1. Ao fechar o negócio cria-se uma DealReception PENDENTE (o stock do comprador não muda).
  2. O comprador confirma a receção (data, quantidade e, opcionalmente, brix/acidez/firmeza/calibre).
  3. Na confirmação o stock entra no ConsolidatedStock e regista-se o evento DELIVERED no lote do ledger.
"""
import datetime
import logging
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class ReceptionError(Exception):
    """Erro de validação apresentado ao utilizador."""


def default_delivery_mode():
    from dashboard.models import DealReception
    mode = str(getattr(settings, 'DEFAULT_DELIVERY_MODE', DealReception.DELIVERY_OWN)).strip().lower()
    valid = {c[0] for c in DealReception.DELIVERY_MODE_CHOICES}
    return mode if mode in valid else DealReception.DELIVERY_OWN


def resolve_delivery_mode(value):
    from dashboard.models import DealReception
    valid = {c[0] for c in DealReception.DELIVERY_MODE_CHOICES}
    value = str(value or '').strip().lower()
    return value if value in valid else default_delivery_mode()


def _parse_date(value):
    if not value:
        return None
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _to_decimal(value, field_label):
    if value is None or str(value).strip() == '':
        return None
    try:
        return Decimal(str(value).replace(',', '.').strip())
    except (InvalidOperation, ValueError):
        raise ReceptionError(f"Valor inválido para {field_label}: '{value}'.")


def warehouse_label(warehouse):
    """Identificação do armazém usada no ConsolidatedStock e nos negócios."""
    return f"{warehouse.location} (WH: {warehouse.warehouse_id})"


def register_pending_reception(deal, buyer, destination_warehouse, delivery_mode=None,
                               expected_date=None, culture=None):
    """
    Cria a receção pendente de um negócio acabado de fechar. Idempotente por deal_id.
    `deal` é o dicionário devolvido pelo Marketplace Web Service.
    """
    from dashboard.models import DealReception, ProductSubFamily

    deal_id = str(deal.get('deal_id') or deal.get('id') or '').strip()
    if not deal_id:
        raise ReceptionError("O negócio não tem identificador (deal_id).")

    culture_name = deal.get('culture_name') or (culture.name if culture else '')
    if culture is None and culture_name:
        culture = ProductSubFamily.objects.filter(name=culture_name).first()

    reception, _ = DealReception.objects.get_or_create(
        deal_id=deal_id,
        defaults={
            'deal_type': deal.get('deal_type') or 'INSTANT',
            'buyer': buyer,
            'seller_id': str(deal.get('seller_id') or ''),
            'culture': culture,
            'culture_name': culture_name,
            'batch_id': str(deal.get('batch_id') or ''),
            'quantity_kg': Decimal(str(deal.get('quantity_kg') or 0)),
            'destination_warehouse': destination_warehouse or deal.get('destination_warehouse') or '',
            'delivery_mode': resolve_delivery_mode(delivery_mode),
            'expected_date': _parse_date(expected_date) or _parse_date(deal.get('delivery_date')),
        },
    )
    return reception


def _weighted(old_avg, old_qty, new_val, new_qty):
    old_avg = Decimal(str(old_avg or 0))
    old_qty = Decimal(str(old_qty or 0))
    total = old_qty + new_qty
    if old_qty <= 0 or old_avg <= 0 or total <= 0:
        return new_val
    return (old_avg * old_qty + new_val * new_qty) / total


def confirm_reception(reception_id, user, warehouse_id=None, received_at=None, received_quantity_kg=None,
                      soluble_solids=None, acidity=None, firmness=None, caliber=None, notes=''):
    """
    Confirma a receção: dá entrada ao stock do comprador no armazém escolhido
    (tem de ser um armazém registado do próprio comprador) e regista DELIVERED no ledger.
    Devolve (reception, ledger_result).
    """
    from dashboard.models import DealReception, ConsolidatedStock, Warehouse
    from dashboard.services.lc_service import calculate_harvest_quality

    if not Warehouse.objects.filter(owner=user).exists():
        raise ReceptionError("Tem de registar pelo menos um armazém antes de confirmar receções.")
    warehouse = None
    if warehouse_id and str(warehouse_id).isdigit():
        warehouse = Warehouse.objects.filter(pk=int(warehouse_id), owner=user).first()
    if warehouse is None:
        raise ReceptionError("Selecione o armazém que recebeu a mercadoria.")

    today = timezone.now().date()
    received_at = _parse_date(received_at) or today
    if received_at > today:
        raise ReceptionError("A data de receção não pode ser no futuro.")

    brix = _to_decimal(soluble_solids, "Brix")
    acid = _to_decimal(acidity, "Acidez")
    firm = _to_decimal(firmness, "Firmeza")
    cal = _to_decimal(caliber, "Calibre")
    qty_input = _to_decimal(received_quantity_kg, "Quantidade recebida")
    for label, v in (("Brix", brix), ("Acidez", acid), ("Firmeza", firm), ("Calibre", cal)):
        if v is not None and v < 0:
            raise ReceptionError(f"{label} não pode ser negativo.")

    with transaction.atomic():
        reception = (DealReception.objects.select_for_update()
                     .filter(pk=reception_id, buyer=user).first())
        if reception is None:
            raise ReceptionError("Receção não encontrada.")
        if reception.status != DealReception.STATUS_PENDING:
            raise ReceptionError(f"A receção do negócio #{reception.deal_id} já foi confirmada.")
        if reception.culture is None:
            raise ReceptionError(f"A cultura '{reception.culture_name}' não existe na plataforma; não é possível dar entrada ao stock.")

        qty = qty_input if qty_input is not None else reception.quantity_kg
        if qty <= 0:
            raise ReceptionError("A quantidade recebida tem de ser superior a 0.")

        quality_score = None
        if any(v is not None for v in (brix, acid, firm)):
            q100 = calculate_harvest_quality(reception.culture.name, firm, brix, acid)
            quality_score = Decimal(str(round(q100 / 10.0, 1)))

        reception.destination_warehouse = warehouse_label(warehouse)
        stock, _ = ConsolidatedStock.objects.select_for_update().get_or_create(
            owner=user,
            culture=reception.culture,
            warehouse_location=reception.destination_warehouse,
            defaults={'quantity': 0, 'avg_quality_score': 10.0},
        )
        old_qty = Decimal(str(stock.quantity))
        if brix is not None:
            stock.avg_soluble_solids = round(_weighted(stock.avg_soluble_solids, old_qty, brix, qty), 2)
        if cal is not None:
            stock.avg_caliber = round(_weighted(stock.avg_caliber, old_qty, cal, qty), 2)
        if quality_score is not None:
            stock.avg_quality_score = round(_weighted(stock.avg_quality_score, old_qty, quality_score, qty), 1)
        stock.quantity = old_qty + qty
        stock.save()

        reception.status = DealReception.STATUS_RECEIVED
        reception.received_at = received_at
        reception.received_quantity_kg = qty
        reception.soluble_solids = brix
        reception.acidity = acid
        reception.firmness = firm
        reception.caliber = cal
        reception.quality_score = quality_score
        reception.notes = (notes or '').strip()
        reception.stock = stock
        reception.confirmed_at = timezone.now()
        reception.save()

    ledger_result = _record_delivery_on_ledger(reception, user)
    if ledger_result.get('status') == 'success' and ledger_result.get('tx_id'):
        type(reception).objects.filter(pk=reception.pk).update(ledger_tx_id=str(ledger_result['tx_id'])[:128])
    return reception, ledger_result


def _record_delivery_on_ledger(reception, user):
    """Regista a entrega na cadeia de custódia do lote de origem (se o negócio tiver lote)."""
    if not reception.batch_id:
        return {"status": "skipped", "message": "Negócio sem lote de origem associado."}
    from dashboard.services.fabric_service import fabric_service

    measurements = {k: float(v) for k, v in (
        ("soluble_solids_brix", reception.soluble_solids), ("acidity", reception.acidity),
        ("firmness", reception.firmness), ("caliber_mm", reception.caliber),
    ) if v is not None}
    details = {
        "deal_id": reception.deal_id,
        "delivery_mode": reception.delivery_mode,
        "received_at": reception.received_at.isoformat(),
        "received_quantity_kg": float(reception.received_quantity_kg),
        "contracted_quantity_kg": float(reception.quantity_kg),
        "destination_warehouse": reception.destination_warehouse,
        "measurements": measurements,
        "notes": reception.notes,
    }
    try:
        result = fabric_service.transfer_custody(reception.batch_id, user.username, "DELIVERED", details)
    except Exception as e:
        result = {"status": "error", "message": str(e)}
    if result.get('status') != 'success':
        logger.warning("[Reception] Ledger não registou a entrega de %s: %s", reception.batch_id, result.get('message'))
    return result


def own_transport_deal_ids():
    """deal_ids com transporte próprio: não devem aparecer como trabalhos de transporte."""
    from dashboard.models import DealReception
    return set(DealReception.objects.filter(delivery_mode=DealReception.DELIVERY_OWN)
               .values_list('deal_id', flat=True))


def lifecycle_reception_for_stock(stock):
    """
    Receção que serve de âncora ao ciclo de vida do stock: a MAIS ANTIGA que ainda
    está em stock (pior caso), assumindo saída FIFO (primeiro a entrar, primeiro a sair).

    O stock é agregado por cultura/armazém, por isso estima-se quais receções ainda lá estão:
    percorre-se das mais recentes para as mais antigas, somando a quantidade recebida,
    até cobrir a quantidade atual. A última incluída é a mais antiga ainda presente.
    Ex.: stock 350 kg; receções B (17/11, 200 kg) e A (10/11, 300 kg) -> A ainda presente.
         stock 150 kg -> só cabe B, logo A já se esgotou e a âncora é B.
    """
    from dashboard.models import DealReception
    receptions = list(DealReception.objects.filter(stock=stock, status=DealReception.STATUS_RECEIVED)
                      .order_by('-received_at', '-confirmed_at'))
    if not receptions:
        return None
    remaining = Decimal(str(stock.quantity or 0))
    if remaining <= 0:
        return receptions[0]
    anchor = None
    for r in receptions:
        if remaining <= 0:
            break
        anchor = r
        remaining -= Decimal(str(r.received_quantity_kg or 0))
    return anchor


def origin_harvest(batch_id):
    """Colheita de origem de um negócio (batch_id 'LOTE-<id>'), ou None."""
    import re
    from dashboard.models import Harvest
    m = re.match(r'LOTE-(\d+)$', str(batch_id or ''))
    return Harvest.objects.filter(pk=int(m.group(1))).first() if m else None


def reception_initial_state(reception):
    """
    Estado inicial de um lote recebido, comum ao Buyer Agent e ao Stock Agent:
      1) medições da receção (conjunto da receção, sem misturar com a colheita) -> início na data de receção;
      2) medições da colheita de origem -> início na data de colheita (conta o tempo até à chegada);
      3) sem medições -> valores por omissão da variedade (None), início na data de receção.
    Devolve {"start_date", "harvest_date", "firmness", "brix", "acidity", "source"}.
    """
    def _val(v):
        return float(v) if v is not None and float(v) > 0 else None

    origin = origin_harvest(reception.batch_id)
    harvest_date = origin.harvest_date if origin and origin.harvest_date else reception.received_at

    measured = {"firmness": _val(reception.firmness), "brix": _val(reception.soluble_solids), "acidity": _val(reception.acidity)}
    if any(v is not None for v in measured.values()):
        return {"start_date": reception.received_at, "harvest_date": harvest_date, **measured, "source": "rececao"}

    if origin is not None:
        harvested = {"firmness": _val(origin.firmness), "brix": _val(origin.soluble_solids), "acidity": _val(origin.acidity)}
        if any(v is not None for v in harvested.values()):
            start = harvest_date if harvest_date <= reception.received_at else reception.received_at
            return {"start_date": start, "harvest_date": harvest_date, **harvested, "source": "colheita"}

    return {"start_date": reception.received_at, "harvest_date": harvest_date,
            "firmness": None, "brix": None, "acidity": None, "source": "omissao"}


def register_received_lot(buyer, culture, stock, quantity_kg, deal_id, deal_type, received_at=None, seller_id='',
                          batch_id='', firmness=None, brix=None, acidity=None, caliber=None, notes=''):
    """
    Regista um lote que entrou em stock SEM passar pela confirmação de receção (compra rápida, ajuste manual).
    Fica como receção já confirmada, para seguir a mesma regra dos agentes e do ciclo de vida:
    com medições usa-as a partir da data de entrada; sem medições usa os valores por omissão da variedade.
    Não altera o stock (quem chama já o atualizou).
    """
    from dashboard.models import DealReception
    from dashboard.services.lc_service import calculate_harvest_quality

    f, b, a, c = (_to_decimal(firmness, "Firmeza"), _to_decimal(brix, "Brix"),
                  _to_decimal(acidity, "Acidez"), _to_decimal(caliber, "Calibre"))
    quality = None
    if any(v is not None for v in (f, b, a)):
        quality = Decimal(str(round(calculate_harvest_quality(culture.name, f, b, a) / 10.0, 1)))
    now = timezone.now()
    return DealReception.objects.create(
        deal_id=str(deal_id), deal_type=deal_type, buyer=buyer, seller_id=str(seller_id or ''),
        culture=culture, culture_name=culture.name, batch_id=str(batch_id or ''),
        quantity_kg=Decimal(str(quantity_kg)), destination_warehouse=stock.warehouse_location,
        delivery_mode=DealReception.DELIVERY_OWN, status=DealReception.STATUS_RECEIVED,
        received_at=received_at or now.date(), received_quantity_kg=Decimal(str(quantity_kg)),
        firmness=f, soluble_solids=b, acidity=a, caliber=c, quality_score=quality,
        notes=notes, stock=stock, confirmed_at=now,
    )
