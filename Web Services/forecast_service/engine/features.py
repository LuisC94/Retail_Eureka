"""
Construção dos dados no formato dos notebooks (colunas ds, y, item_id, store_id, node_idx, calendário, Lag-k).

Nos notebooks as variáveis de calendário vinham pré-calculadas em processed_data/*.parquet (o código que as
gerou não está nos notebooks). Aqui são calculadas a partir da data com as mesmas formas funcionais usadas
no serviço anterior (proximidade exponencial, efeito de Natal assimétrico, etc.). thanksgiving_effect usa a
mesma forma do efeito de Natal, centrado no 4.º quinta-feira de novembro (feriado dos dados M5).
"""
import numpy as np
import pandas as pd

from .notebook_code import lags, numeric_features, categorical_features

ITEM_ID = "single_item"
STORE_ID = "single_store"
ITEM_STORE_TO_IDX = {f"{ITEM_ID}_{STORE_ID}": 0}
LAG_COLS = [f"Lag-{lag}" for lag in lags]


def _season(date):
    m, d = date.month, date.day
    if (m == 12 and d >= 21) or m in (1, 2) or (m == 3 and d < 20):
        return "winter"
    if (m == 3 and d >= 20) or m in (4, 5) or (m == 6 and d < 21):
        return "spring"
    if (m == 6 and d >= 21) or m in (7, 8) or (m == 9 and d < 23):
        return "summer"
    return "autumn"


def _payday_distance(date):
    last_day = (date + pd.offsets.MonthEnd(0)).day
    return min(abs(date.day - 15), abs(date.day - last_day))


def _asymmetric_effect(date, anchors):
    d = min(((date - a).days for a in anchors), key=abs)
    return float(np.exp(-0.1 * abs(d)) if d < 0 else np.exp(-0.3 * abs(d)))


def _christmas_effect(date):
    return _asymmetric_effect(date, [pd.Timestamp(year=y, month=12, day=25) for y in (date.year - 1, date.year, date.year + 1)])


def _thanksgiving(year):
    nov1 = pd.Timestamp(year=year, month=11, day=1)
    first_thu = nov1 + pd.Timedelta(days=(3 - nov1.dayofweek) % 7)
    return first_thu + pd.Timedelta(weeks=3)


def _thanksgiving_effect(date):
    return _asymmetric_effect(date, [_thanksgiving(y) for y in (date.year - 1, date.year, date.year + 1)])


def _holiday_proximity(date):
    y = date.year
    fixed = [pd.Timestamp(year=y, month=1, day=1), pd.Timestamp(year=y, month=5, day=1),
             pd.Timestamp(year=y, month=12, day=25), pd.Timestamp(year=y, month=12, day=31)]
    return float(np.exp(-min(abs((date - d).days) for d in fixed) / 7.0))


def _school_break_proximity(date):
    y = date.year
    intervals = [(pd.Timestamp(year=y, month=7, day=15), pd.Timestamp(year=y, month=9, day=15)),
                 (pd.Timestamp(year=y, month=12, day=15), pd.Timestamp(year=y + 1, month=1, day=10)),
                 (pd.Timestamp(year=y, month=3, day=15), pd.Timestamp(year=y, month=4, day=15))]
    dist = [0 if s <= date <= e else min(abs((date - s).days), abs((date - e).days)) for s, e in intervals]
    return float(np.exp(-min(dist) / 7.0))


def _festive_proximity(date):
    y = date.year
    days = list(pd.date_range(f"{y}-12-20", f"{y}-12-26")) + list(pd.date_range(f"{y}-12-31", f"{y + 1}-01-02")) \
        + list(pd.date_range(f"{y}-04-01", f"{y}-04-10"))
    return float(np.exp(-min(abs((date - d).days) for d in days) / 7.0))


def add_calendar_features(df):
    df = df.copy()
    ds = pd.to_datetime(df["ds"])
    df["day_of_week"] = ds.dt.dayofweek
    df["month"] = ds.dt.month
    df["day_of_year"] = ds.dt.dayofyear
    df["week"] = ds.dt.isocalendar().week.astype(int).values
    df["day_of_week_sin"] = np.sin(2 * np.pi * df["day_of_week"] / 7.0)
    df["day_of_week_cos"] = np.cos(2 * np.pi * df["day_of_week"] / 7.0)
    df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12.0)
    df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12.0)
    df["day_of_year_sin"] = np.sin(2 * np.pi * df["day_of_year"] / 365.0)
    df["day_of_year_cos"] = np.cos(2 * np.pi * df["day_of_year"] / 365.0)
    df["weekend_proximity"] = df["day_of_week"].apply(lambda x: 0.75 * np.exp(-0.5 * abs(5 - x)))
    df["payday_proximity"] = ds.apply(_payday_distance).apply(lambda x: np.exp(-0.1 * x)).values
    df["christmas_effect"] = ds.apply(_christmas_effect).values
    df["thanksgiving_effect"] = ds.apply(_thanksgiving_effect).values
    df["holiday_proximity"] = ds.apply(_holiday_proximity).values
    df["school_break_proximity"] = ds.apply(_school_break_proximity).values
    df["festive_proximity"] = ds.apply(_festive_proximity).values
    season = ds.apply(_season).values
    for s in ("autumn", "spring", "summer", "winter"):
        df[f"season_{s}"] = (season == s).astype(int)
    return df


def _base_frame(dates, y=None):
    df = pd.DataFrame({"ds": pd.to_datetime(dates).normalize()})
    df["y"] = np.nan if y is None else y
    df["item_id"] = ITEM_ID
    df["store_id"] = STORE_ID
    df["item_id_idx"] = 0
    df["store_id_idx"] = 0
    df["node_idx"] = 0
    return df


def daily_series(sales_history):
    """[{date, sales_quantity_kg}] -> série diária contínua (dias em falta = 0), como no serviço anterior."""
    df = pd.DataFrame(sales_history)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df["sales_quantity_kg"] = pd.to_numeric(df["sales_quantity_kg"], errors="coerce").fillna(0).clip(lower=0)
    s = df.groupby("date")["sales_quantity_kg"].sum().sort_index()
    full = pd.date_range(s.index.min(), s.index.max(), freq="D")
    return s.reindex(full, fill_value=0.0)


def finalize_columns(df):
    """Mesmo tratamento de colunas dos notebooks ('Garantir colunas')."""
    for col in categorical_features:
        if col not in df.columns:
            df[col] = 0
        df[col] = df[col].fillna(0).astype(int)
    for col in numeric_features:
        if col not in df.columns:
            df[col] = 0
        df[col] = df[col].fillna(0).astype(float)
    df["y"] = df["y"].fillna(0).clip(lower=0).astype(float)
    for c in ("item_id_idx", "store_id_idx", "node_idx"):
        df[c] = df[c].astype(int)
    return df


def training_frame(series):
    """Série diária -> DataFrame no formato dos parquet dos notebooks (lags reais; lags antes do início = 0)."""
    df = _base_frame(series.index, series.values.astype(float))
    df = add_calendar_features(df)
    for lag in lags:
        df[f"Lag-{lag}"] = df["y"].shift(lag)
    df[LAG_COLS] = df[LAG_COLS].fillna(0).clip(lower=0)
    return finalize_columns(df)


def history_frame(series):
    """Histórico (ds, y) usado como df_historico na inferência passo-a-passo."""
    return _base_frame(series.index, series.values.astype(float))[["item_id", "store_id", "ds", "y"]]


def future_frame(start_date, horizon_days):
    """Dias a prever (df_test da inferência), com calendário mas sem y nem lags."""
    dates = pd.date_range(pd.to_datetime(start_date).normalize(), periods=int(horizon_days), freq="D")
    return add_calendar_features(_base_frame(dates))
