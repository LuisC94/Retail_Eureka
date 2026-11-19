"""
Upload de um Excel/CSV global de vendas (todas as culturas e armazéns numa folha).

Colunas: Data, Cultura, Armazem, Quantidade_Kg, Preco_Venda_Euro (obrigatórias)
         Comprador, Nome_Cliente, Fatura (opcionais). Uma linha = uma venda ou o total do dia.

Fluxo em dois passos:
  1. preview_upload: lê o ficheiro, valida cada linha, simula o stock por data (da mais antiga para a mais
     recente) e deteta duplicados (vendas já registadas). Nada é gravado.
  2. commit_upload: volta a validar (o stock pode ter mudado entretanto) e grava TUDO ou NADA.
Os lotes saem por FIFO e o total diário entra no HistoricalSalesData (ver sales_service.register_sale).
"""
import datetime
import re
import unicodedata
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation

from django.db import transaction

TEMPLATE_COLUMNS = ['Data', 'Cultura', 'Armazem', 'Quantidade_Kg', 'Preco_Venda_Euro', 'Comprador', 'Nome_Cliente', 'Fatura']
REQUIRED = ['date', 'culture', 'warehouse', 'quantity', 'price']
MAX_ROWS = 5000

_ALIASES = {
    'date': ['data', 'date', 'data_venda', 'dia'],
    'culture': ['cultura', 'culture', 'produto', 'variedade'],
    'warehouse': ['armazem', 'warehouse', 'armazem_saida', 'wh'],
    'quantity': ['quantidade_kg', 'quantidade', 'kg', 'vendas_kg', 'quantity_kg', 'qty'],
    'price': ['preco_venda_euro', 'preco', 'preco_kg', 'preco_euro_kg', 'price_per_kg', 'price'],
    'buyer': ['comprador', 'buyer', 'cliente_plataforma'],
    'customer': ['nome_cliente', 'cliente', 'customer', 'customer_name'],
    'invoice': ['fatura', 'factura', 'invoice', 'n_fatura', 'num_fatura', 'numero_fatura'],
}
_LABELS = {'date': 'Data', 'culture': 'Cultura', 'warehouse': 'Armazem', 'quantity': 'Quantidade_Kg',
           'price': 'Preco_Venda_Euro'}


class UploadError(Exception):
    """Erro que impede a leitura do ficheiro inteiro."""


def _norm(text):
    text = unicodedata.normalize('NFD', str(text or '')).encode('ascii', 'ignore').decode().lower().strip()
    return re.sub(r'[^a-z0-9]+', '_', text).strip('_')


def _blank(v):
    if v is None:
        return True
    try:
        import pandas as pd
        if pd.isna(v):
            return True
    except (TypeError, ValueError):
        pass
    return str(v).strip() == ''


def _cell_text(v):
    if _blank(v):
        return ''
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def _parse_date(v):
    if isinstance(v, datetime.datetime):
        return v.date()
    if isinstance(v, datetime.date):
        return v
    if hasattr(v, 'to_pydatetime'):
        return v.to_pydatetime().date()
    s = str(v).strip()[:10]
    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%d.%m.%Y', '%Y/%m/%d', '%d/%m/%y'):
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _parse_number(v):
    if isinstance(v, (int, float, Decimal)):
        return Decimal(str(v))
    s = str(v).strip().replace(' ', '').replace('€', '')
    if ',' in s and '.' in s:          # 1.234,56 -> 1234.56
        s = s.replace('.', '').replace(',', '.')
    else:
        s = s.replace(',', '.')
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None


def read_rows(uploaded_file):
    """Lê o ficheiro e devolve as linhas normalizadas [{line, date, culture, ...}] (valores em texto/ISO)."""
    import pandas as pd

    name = (getattr(uploaded_file, 'name', '') or '').lower()
    try:
        if name.endswith('.csv'):
            raw = uploaded_file.read()
            import io
            text = raw.decode('utf-8-sig', errors='replace')
            sep = ';' if text.count(';') > text.count(',') else ','
            df = pd.read_csv(io.StringIO(text), sep=sep, dtype=str)
        elif name.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(uploaded_file, sheet_name=0)
        else:
            raise UploadError("Formato não suportado. Use .xlsx, .xls ou .csv.")
    except UploadError:
        raise
    except Exception as e:
        raise UploadError(f"Não foi possível ler o ficheiro: {e}")

    columns = {}
    for col in df.columns:
        key = _norm(col)
        for field, aliases in _ALIASES.items():
            if key in aliases and field not in columns:
                columns[field] = col
    missing = [_LABELS[f] for f in REQUIRED if f not in columns]
    if missing:
        raise UploadError(f"Faltam colunas obrigatórias: {', '.join(missing)}. Descarregue o modelo para ver a estrutura.")

    rows = []
    for idx, rec in df.iterrows():
        values = {f: rec[c] for f, c in columns.items()}
        if all(_blank(v) for v in values.values()):
            continue
        d = _parse_date(values['date']) if not _blank(values['date']) else None
        q = _parse_number(values['quantity']) if not _blank(values['quantity']) else None
        p = _parse_number(values['price']) if not _blank(values['price']) else None
        rows.append({
            'line': int(idx) + 2,
            'date': d.isoformat() if d else '',
            'date_raw': _cell_text(values['date']),
            'culture': _cell_text(values['culture']),
            'warehouse': _cell_text(values['warehouse']),
            'quantity': str(q) if q is not None else '',
            'quantity_raw': _cell_text(values['quantity']),
            'price': str(p) if p is not None else '',
            'price_raw': _cell_text(values['price']),
            'buyer': _cell_text(values.get('buyer')),
            'customer': _cell_text(values.get('customer'))[:150],
            'invoice': _cell_text(values.get('invoice'))[:100],
        })
    if not rows:
        raise UploadError("O ficheiro não tem linhas de vendas.")
    if len(rows) > MAX_ROWS:
        raise UploadError(f"O ficheiro tem {len(rows)} linhas; o máximo por upload é {MAX_ROWS}.")
    return rows


class _Resolver:
    """Converte os textos do ficheiro em objetos da plataforma (cultura, armazém/stock, comprador)."""

    def __init__(self, user):
        from dashboard.models import ConsolidatedStock, ProductSubFamily, Warehouse
        from dashboard.services.sales_service import platform_buyers

        self.cultures = {}
        for c in ProductSubFamily.objects.all():
            self.cultures.setdefault(_norm(c.name), c)
        self.warehouses = list(Warehouse.objects.filter(owner=user))
        self.stocks = list(ConsolidatedStock.objects.filter(owner=user).select_related('culture'))
        self.buyers = {b.username.lower(): b for b in platform_buyers(exclude_user=user)}
        self.user = user

    def culture(self, text):
        return self.cultures.get(_norm(text))

    def warehouse(self, text):
        t = str(text).strip()
        m = re.search(r'(?:wh\s*[-:#]?\s*)(\d+)', t, re.I) or re.fullmatch(r'(\d+)', t)
        if m:
            wid = int(m.group(1))
            return next((w for w in self.warehouses if w.warehouse_id == wid), None)
        key = _norm(t)
        matches = [w for w in self.warehouses if _norm(w.location) == key]
        return matches[0] if len(matches) == 1 else None

    def stock(self, culture, wh):
        ids = (f"WH: {wh.warehouse_id})", f"WH:{wh.warehouse_id})")
        for s in self.stocks:
            if s.culture_id == culture.pk and (s.warehouse_location.endswith(ids) or s.warehouse_location == wh.location):
                return s
        return None

    def buyer(self, text):
        return self.buyers.get(str(text).strip().lower())


def _dup_key(seller_date, culture_id, warehouse_location, qty, price, invoice):
    if invoice:
        return ('inv', invoice.lower(), culture_id, warehouse_location, Decimal(qty).quantize(Decimal('0.01')))
    return ('row', seller_date, culture_id, warehouse_location, Decimal(qty).quantize(Decimal('0.01')),
            Decimal(price).quantize(Decimal('0.01')))


def validate_rows(user, rows):
    """
    Valida as linhas sem gravar. Devolve {'valid': [...], 'errors': [...], 'duplicates': [...], 'summary': {...}}.
    Cada linha válida leva stock_id e buyer_id resolvidos. A simulação de stock segue a ordem das datas.
    """
    from dashboard.models import SaleRecord
    from django.utils import timezone

    res = _Resolver(user)
    today = timezone.now().date()
    errors, candidates = [], []

    for r in rows:
        problems = []
        d = datetime.date.fromisoformat(r['date']) if r['date'] else None
        if d is None:
            problems.append(f"data inválida ('{r['date_raw']}')" if r['date_raw'] else "falta a data")
        elif d > today:
            problems.append("data no futuro")

        culture = res.culture(r['culture']) if r['culture'] else None
        if not r['culture']:
            problems.append("falta a cultura")
        elif culture is None:
            problems.append(f"cultura desconhecida ('{r['culture']}')")

        wh = res.warehouse(r['warehouse']) if r['warehouse'] else None
        if not r['warehouse']:
            problems.append("falta o armazém")
        elif wh is None:
            problems.append(f"armazém desconhecido ('{r['warehouse']}'); use o id (ex.: WH-3) de um armazém seu")

        q = Decimal(r['quantity']) if r['quantity'] else None
        if q is None:
            problems.append(f"quantidade inválida ('{r['quantity_raw']}')" if r['quantity_raw'] else "falta a quantidade")
        elif q <= 0:
            problems.append("a quantidade tem de ser superior a 0")

        p = Decimal(r['price']) if r['price'] else None
        if p is None:
            problems.append(f"preço inválido ('{r['price_raw']}')" if r['price_raw'] else "falta o preço")
        elif p < 0:
            problems.append("o preço não pode ser negativo")

        buyer = None
        if r['buyer']:
            buyer = res.buyer(r['buyer'])
            if buyer is None:
                problems.append(f"comprador '{r['buyer']}' não existe na plataforma (deixe vazio para cliente externo)")

        stock = res.stock(culture, wh) if (culture and wh) else None
        if culture and wh and stock is None:
            problems.append(f"não há stock de {culture.name} no WH-{wh.warehouse_id}")

        if problems:
            errors.append({'line': r['line'], 'message': '; '.join(problems)})
            continue
        candidates.append({**r, 'date': d.isoformat(), 'culture_id': culture.pk, 'culture_name': culture.name,
                           'warehouse_id': wh.warehouse_id, 'warehouse_label': stock.warehouse_location,
                           'stock_id': stock.pk, 'buyer_id': buyer.pk if buyer else None,
                           'buyer_name': buyer.username if buyer else (r['customer'] or 'Cliente externo')})

    # Duplicados: vendas já registadas com os mesmos dados (contagem, para permitir linhas iguais legítimas)
    existing = Counter()
    if candidates:
        dates = sorted({c['date'] for c in candidates})
        for s in SaleRecord.objects.filter(seller=user, sale_date__gte=dates[0], sale_date__lte=dates[-1]):
            existing[_dup_key(s.sale_date.isoformat(), s.culture_id, s.warehouse_location, s.quantity_kg,
                              s.price_per_kg, s.invoice_ref)] += 1
        invoices = {c['invoice'] for c in candidates if c['invoice']}
        if invoices:
            for s in SaleRecord.objects.filter(seller=user, invoice_ref__in=invoices).exclude(
                    sale_date__gte=dates[0], sale_date__lte=dates[-1]):
                existing[_dup_key(s.sale_date.isoformat(), s.culture_id, s.warehouse_location, s.quantity_kg,
                                  s.price_per_kg, s.invoice_ref)] += 1

    duplicates, fresh = [], []
    for c in candidates:
        key = _dup_key(c['date'], c['culture_id'], c['warehouse_label'], c['quantity'], c['price'], c['invoice'])
        if existing[key] > 0:
            existing[key] -= 1
            duplicates.append({'line': c['line'], 'message': f"{c['date']} · {c['culture_name']} · {c['quantity']} kg já registada"
                               + (f" (fatura {c['invoice']})" if c['invoice'] else '')})
        else:
            fresh.append(c)

    # Simulação do stock: por data (mais antiga primeiro) e pela ordem do ficheiro no mesmo dia
    fresh.sort(key=lambda c: (c['date'], c['line']))
    available = {s.pk: Decimal(str(s.quantity or 0)) for s in res.stocks}
    valid = []
    for c in fresh:
        q = Decimal(c['quantity'])
        if q > available[c['stock_id']]:
            errors.append({'line': c['line'], 'message': (
                f"stock insuficiente de {c['culture_name']} no WH-{c['warehouse_id']} a "
                f"{datetime.date.fromisoformat(c['date']):%d/%m/%Y}: pede {q} kg, restam {available[c['stock_id']]} kg")})
            continue
        available[c['stock_id']] -= q
        valid.append(c)

    errors.sort(key=lambda e: e['line'])
    by_culture = defaultdict(lambda: {'kg': Decimal('0'), 'eur': Decimal('0'), 'rows': 0})
    for c in valid:
        agg = by_culture[c['culture_name']]
        agg['kg'] += Decimal(c['quantity'])
        agg['eur'] += Decimal(c['quantity']) * Decimal(c['price'])
        agg['rows'] += 1
    summary = {
        'rows': len(rows), 'valid': len(valid), 'errors': len(errors), 'duplicates': len(duplicates),
        'kg': str(sum((Decimal(c['quantity']) for c in valid), Decimal('0'))),
        'eur': str(sum((Decimal(c['quantity']) * Decimal(c['price']) for c in valid), Decimal('0')).quantize(Decimal('0.01'))),
        'date_from': valid[0]['date'] if valid else '', 'date_to': valid[-1]['date'] if valid else '',
        'by_culture': [{'culture': k, 'kg': str(v['kg']), 'eur': str(v['eur'].quantize(Decimal('0.01'))), 'rows': v['rows']}
                       for k, v in sorted(by_culture.items())],
    }
    return {'valid': valid, 'errors': errors, 'duplicates': duplicates, 'summary': summary}


def preview_upload(user, uploaded_file):
    rows = read_rows(uploaded_file)
    result = validate_rows(user, rows)
    result['rows'] = rows
    result['file_name'] = getattr(uploaded_file, 'name', '')
    return result


def commit_upload(user, rows):
    """
    Volta a validar e grava todas as vendas válidas numa só transação.
    Se houver qualquer erro, não grava nada e devolve a nova validação.
    """
    from dashboard.models import SaleRecord
    from dashboard.services.sales_service import register_sale

    result = validate_rows(user, rows)
    if result['errors']:
        return False, result
    with transaction.atomic():
        for c in result['valid']:
            register_sale(user, c['stock_id'], c['quantity'], c['price'], c['date'], buyer_id=c['buyer_id'],
                          customer_name=c['customer'], invoice_ref=c['invoice'], source=SaleRecord.SOURCE_UPLOAD,
                          check_duplicates=False)
    return True, result


def build_template(user):
    """Modelo Excel: folha 'Vendas' com exemplos e folha 'Valores válidos' (culturas, armazéns e compradores)."""
    import io
    import pandas as pd
    from dashboard.models import ConsolidatedStock, ProductSubFamily, Warehouse
    from dashboard.services.sales_service import platform_buyers

    whs = list(Warehouse.objects.filter(owner=user).order_by('warehouse_id'))
    stocks = list(ConsolidatedStock.objects.filter(owner=user, quantity__gt=0).select_related('culture')
                  .order_by('culture__name'))
    wh_code = f"WH-{whs[0].warehouse_id}" if whs else 'WH-1'
    c1 = stocks[0].culture.name if stocks else 'Gala'
    c2 = stocks[1].culture.name if len(stocks) > 1 else c1
    buyers = list(platform_buyers(exclude_user=user))
    today = datetime.date.today().strftime('%d/%m/%Y')
    examples = pd.DataFrame([
        [today, c1, wh_code, 120, 1.45, '', 'Cliente balcão', 'FT 2026/1'],
        [today, c2, wh_code, 40, 2.10, buyers[0].username if buyers else '', '', 'FT 2026/2'],
    ], columns=TEMPLATE_COLUMNS)

    n = max(len(whs), 1)
    cultures = sorted({s.culture.name for s in stocks}) or [c.name for c in ProductSubFamily.objects.order_by('name')]
    size = max(len(cultures), n, len(buyers), 1)
    pad = lambda lst: list(lst) + [''] * (size - len(lst))
    valid = pd.DataFrame({
        'Cultura': pad(cultures),
        'Armazem': pad([f"WH-{w.warehouse_id}" for w in whs]),
        'Localização do armazém': pad([w.location for w in whs]),
        'Comprador (plataforma)': pad([b.username for b in buyers]),
    })
    notes = pd.DataFrame({'Coluna': TEMPLATE_COLUMNS, 'Obrigatória': ['Sim'] * 5 + ['Não'] * 3, 'Notas': [
        'dd/mm/aaaa',
        'Nome igual ao da plataforma (folha "Valores válidos")',
        'Id do armazém (ex.: WH-3) ou nome da localização',
        'Maior que 0',
        'Preço por kg (€/kg)',
        'Utilizador da plataforma. Vazio = cliente externo',
        'Opcional, para clientes externos',
        'Recomendado: evita duplicados se carregar o ficheiro duas vezes',
    ]})

    out = io.BytesIO()
    with pd.ExcelWriter(out, engine='openpyxl') as writer:
        examples.to_excel(writer, index=False, sheet_name='Vendas')
        valid.to_excel(writer, index=False, sheet_name='Valores válidos')
        notes.to_excel(writer, index=False, sheet_name='Instruções')
        for ws in writer.book.worksheets:
            for col in ws.columns:
                width = max(len(str(c.value or '')) for c in col) + 2
                ws.column_dimensions[col[0].column_letter].width = min(max(width, 12), 60)
    return out.getvalue()
