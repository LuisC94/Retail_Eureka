"""
Esquema do Excel do Stock Agent (5 folhas), alinhado com as entidades da plataforma Retail Eureka (Django).

| Folha      | Entidade Django                          | Uma linha por            |
|------------|------------------------------------------|--------------------------|
| Armazens   | Warehouse                                | armazém                  |
| Lotes      | Harvest (lote = colheita guardada)       | lote                     |
| Leituras   | WarehouseSensorReading                   | armazém x dia            |
| Mercado    | HistoricalSalesData + DemandForecast     | perfil x cultura x dia   |

(A folha opcional "LEIA-ME" é ignorada na leitura.)
"""
import io

import pandas as pd

SHEETS = {
    "Armazens": {
        "armazem_id": "Identificador do armazém (Warehouse.warehouse_id)",
        "perfil": "Dono do armazém (Warehouse.owner / username)",
        "localizacao": "Localização (Warehouse.location)",
        "regiao": "Região climática IPMA, ex: PT-LVT (Warehouse.region)",
        "tipo_controlo": "'Controlled' = atmosfera controlada, 'Non-Controlled' = frio normal (Warehouse.control_type)",
        "capacidade_kg": "Capacidade em kg (Warehouse.capacity)",
    },
    "Lotes": {
        "lote_id": "Identificador do lote (Harvest.harvest_id -> batch 'LOTE-<id>')",
        "perfil": "Produtor dono do lote (Harvest.producer)",
        "armazem_id": "Armazém onde o lote está guardado (Harvest.warehouse)",
        "cultura": "Nome da cultura / subfamília (ProductSubFamily.name), ex: 'Kiwi Hayward'",
        "tipo_fruta": "Chave da fruta para o Lifecycle, ex: kiwi_hayward, pear, apple_gala",
        "temporada": "Campanha / temporada do lote (ex: 2021)",
        "data_colheita": "Data de colheita (Harvest.harvest_date)",
        "data_entrada": "Data de entrada no armazém",
        "quantidade_kg": "Quantidade em kg (Harvest.harvest_quantity_kg - utilized_quantity_kg)",
        "firmeza": "Firmeza à colheita em N (Harvest.firmness)",
        "brix": "Sólidos solúveis à colheita em °Brix (Harvest.soluble_solids)",
        "acidez": "Acidez à colheita (Harvest.acidity)",
        "calibre_mm": "Calibre em mm (Harvest.caliber)",
        "score_qualidade": "Score de qualidade 1-10 (Harvest.avg_quality_score)",
    },
    "Leituras": {
        "armazem_id": "Armazém (WarehouseSensorReading.warehouse)",
        "data": "Dia da leitura",
        "temperatura": "Temperatura média do dia em °C",
        "humidade": "Humidade relativa média do dia em %",
        "etileno": "Etileno em ppm",
    },
    "Mercado": {
        "perfil": "Produtor (HistoricalSalesData.owner)",
        "cultura": "Cultura (HistoricalSalesData.culture)",
        "data": "Dia",
        "preco_kg": "Preço de venda de mercado em EUR/kg (HistoricalSalesData.price_per_kg)",
        "vendas_kg": "Procura real absorvida pelo mercado nesse dia em kg (HistoricalSalesData.sales_quantity_kg)",
        "procura_prevista_kg": "Previsão de procura para esse dia em kg (DemandForecast.predicted_quantity_kg)",
    },
}

OPTIONAL_COLUMNS = {
    "Lotes": {"firmeza", "brix", "acidez", "calibre_mm", "score_qualidade", "temporada", "data_entrada"},
    "Armazens": {"localizacao", "regiao", "capacidade_kg"},
    "Leituras": {"etileno"},
    "Mercado": {"procura_prevista_kg"},
}

DATE_COLUMNS = {
    "Lotes": ["data_colheita", "data_entrada"],
    "Leituras": ["data"],
    "Mercado": ["data"],
}


class DataValidationError(ValueError):
    pass


def read_excel(source) -> dict:
    """Lê o Excel (caminho, bytes ou ficheiro carregado) e devolve {folha: DataFrame} validado e normalizado."""
    if isinstance(source, (bytes, bytearray)):
        source = io.BytesIO(source)
    raw = pd.read_excel(source, sheet_name=None)
    return normalize(raw)


def normalize(raw: dict) -> dict:
    missing_sheets = [s for s in SHEETS if s not in raw]
    if missing_sheets:
        raise DataValidationError(f"Folhas em falta no Excel: {', '.join(missing_sheets)}. Esperadas: {', '.join(SHEETS)}")
    data = {}
    for sheet, cols in SHEETS.items():
        df = raw[sheet].copy()
        df.columns = [str(c).strip() for c in df.columns]
        required = [c for c in cols if c not in OPTIONAL_COLUMNS.get(sheet, set())]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise DataValidationError(f"Folha '{sheet}': colunas obrigatórias em falta: {', '.join(missing)}")
        for c in DATE_COLUMNS.get(sheet, []):
            if c in df.columns:
                df[c] = pd.to_datetime(df[c]).dt.normalize()
        data[sheet] = df

    lotes = data["Lotes"]
    if "data_entrada" not in lotes.columns:
        lotes["data_entrada"] = lotes["data_colheita"]
    lotes["data_entrada"] = lotes["data_entrada"].fillna(lotes["data_colheita"])
    if "temporada" not in lotes.columns:
        # Temporada = ano de início da campanha (colheitas de Jan-Jun pertencem à campanha do ano anterior)
        d = lotes["data_colheita"]
        lotes["temporada"] = d.dt.year.where(d.dt.month >= 7, d.dt.year - 1)
    for c in ("perfil", "cultura", "tipo_fruta"):
        lotes[c] = lotes[c].astype(str).str.strip()
    lotes["lote_id"] = lotes["lote_id"].astype(str)
    lotes["armazem_id"] = lotes["armazem_id"].astype(str)

    arm = data["Armazens"]
    arm["armazem_id"] = arm["armazem_id"].astype(str)
    arm["perfil"] = arm["perfil"].astype(str).str.strip()
    arm["controlado"] = arm["tipo_controlo"].astype(str).str.lower().str.startswith("controlled")

    leit = data["Leituras"]
    leit["armazem_id"] = leit["armazem_id"].astype(str)
    if "etileno" not in leit.columns:
        leit["etileno"] = 0.1

    merc = data["Mercado"]
    merc["perfil"] = merc["perfil"].astype(str).str.strip()
    merc["cultura"] = merc["cultura"].astype(str).str.strip()
    if "procura_prevista_kg" not in merc.columns:
        merc["procura_prevista_kg"] = merc["vendas_kg"]

    unknown_wh = set(lotes["armazem_id"]) - set(arm["armazem_id"])
    if unknown_wh:
        raise DataValidationError(f"Lotes referem armazéns inexistentes na folha Armazens: {sorted(unknown_wh)[:10]}")
    return data


def profiles_and_cultures(data: dict) -> pd.DataFrame:
    """Combinações perfil x cultura disponíveis (há um modelo por combinação)."""
    lotes = data["Lotes"]
    g = lotes.groupby(["perfil", "cultura"]).agg(
        tipo_fruta=("tipo_fruta", "first"),
        lotes=("lote_id", "count"),
        kg_total=("quantidade_kg", "sum"),
        temporadas=("temporada", lambda s: sorted(s.unique().tolist())),
    ).reset_index()
    return g


def to_excel_bytes(data: dict, readme: pd.DataFrame = None) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        if readme is not None:
            readme.to_excel(xw, sheet_name="LEIA-ME", index=False)
        for sheet in SHEETS:
            df = data[sheet].copy()
            df = df[[c for c in df.columns if c in SHEETS[sheet]]]
            for c in DATE_COLUMNS.get(sheet, []):
                if c in df.columns:
                    df[c] = pd.to_datetime(df[c]).dt.date
            df.to_excel(xw, sheet_name=sheet, index=False)
    return buf.getvalue()


def readme_frame() -> pd.DataFrame:
    rows = []
    for sheet, cols in SHEETS.items():
        for c, desc in cols.items():
            opt = "opcional" if c in OPTIONAL_COLUMNS.get(sheet, set()) else "obrigatória"
            rows.append({"folha": sheet, "coluna": c, "obrigatoriedade": opt, "descricao": desc})
    return pd.DataFrame(rows)
