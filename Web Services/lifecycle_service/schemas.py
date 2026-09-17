from typing import List, Literal, Optional, Dict, Any, Union
from pydantic import BaseModel, Field

# =============================================================================
# PYDANTIC DATA CONTRACTS (SCHEMAS)
# =============================================================================

class InitialMetrics(BaseModel):
    soluble_solids_brix: Optional[float] = Field(None, description="Initial Brix / Soluble Solids")
    caliber_mm: Optional[float] = Field(None, description="Fruit caliber in mm")
    quality_score: Optional[float] = Field(None, description="Initial quality rating (1-10 or 0-100)")
    waste_kg: Optional[float] = Field(None, description="Reported discarded/waste kg")
    expiration_date: Optional[str] = Field(None, description="Expiration date string YYYY-MM-DD")
    firmness: Optional[float] = Field(None, description="Initial firmness in N or kg/cm2")
    acidity: Optional[float] = Field(None, description="Initial titratable acidity (% malic or citric acid)")


class LotIdentification(BaseModel):
    lot_id: Union[int, str] = Field(..., description="Unique Lot/Harvest primary key")
    batch_id: str = Field(..., description="Batch code e.g. LOTE-1234 or STOCK-56")
    culture_name: str = Field(..., description="Crop/Subfamily name e.g. Gala, Fuji, Rocha")
    fruit_type: str = Field(..., description="Fruit category e.g. apple, kiwi, strawberry")
    producer: str = Field(..., description="Origin producer name or identifier")
    current_owner: str = Field(..., description="Current owner username or entity")
    current_owner_type: Optional[str] = Field("Retailer (Grocery Store)", description="Stakeholder profile (Producer, Processor, Retailer, Industry)")
    harvest_date: str = Field(..., description="Harvest date string YYYY-MM-DD")
    initial_quantity_kg: float = Field(..., description="Initial harvested quantity in kg")
    current_stock_kg: float = Field(..., description="Current available quantity in kg")
    delivered_quantity_kg: float = Field(0.0, description="Quantity already delivered to downstream actors")
    initial_metrics: InitialMetrics = Field(default_factory=InitialMetrics)


class DailyReading(BaseModel):
    date: str = Field(..., description="Reading date string YYYY-MM-DD")
    temperature_celsius: Optional[float] = Field(None, description="Storage temperature in Celsius")
    humidity_percent: Optional[float] = Field(None, description="Relative humidity in percentage (0-100)")
    ethylene_ppm: Optional[float] = Field(None, description="Ethylene gas concentration in ppm")
    source: str = Field("SENSOR_RECORDING", description="Source: SENSOR_RECORDING, IPMA_REGIONAL, or FIXED_PRESET")


class WarehouseHistory(BaseModel):
    warehouse_id: Optional[Union[int, str]] = Field(None, description="Warehouse identifier")
    warehouse_location: str = Field(..., description="Warehouse name/location")
    region: str = Field("PT-LVT", description="IPMA Region code e.g. PT-LVT, PT-NL, PT-CI")
    meteo_source: str = Field("JSON", description="Meteorology source: FIXED, IPMA, or JSON")
    total_days_recorded: int = Field(0, description="Total days fruit spent in this warehouse/transport segment")
    keptancy_start_date: Optional[str] = Field(None, description="Segment start date YYYY-MM-DD")
    packaging_method: Optional[str] = Field("Granel (Sem embalagem)", description="Packaging type: Bulk, Cardboard, Perforated, MAP")
    daily_readings: List[DailyReading] = Field(default_factory=list)


class LifecycleDataRequest(BaseModel):
    version: str = Field("1.0", description="Schema payload version")
    export_metadata: Dict[str, Any] = Field(default_factory=dict)
    lot_identification: LotIdentification
    plantation_origin: Dict[str, Any] = Field(default_factory=dict)
    plantation_agricultural_events: List[Any] = Field(default_factory=list)
    current_warehouse: Dict[str, Any] = Field(default_factory=dict)
    meteorology_and_imputation_strategy: Dict[str, Any] = Field(default_factory=dict)
    blockchain_ledger: Dict[str, Any] = Field(default_factory=dict)
    transport_and_logistics: List[Any] = Field(default_factory=list)
    sensor_history_by_warehouse: List[WarehouseHistory] = Field(default_factory=list)
    plot_info: bool = Field(False, description="Flag to include full temporal continuous curve arrays in response")


class ForecastResponse(BaseModel):
    service: Literal["lifecycle_inference"] = "lifecycle_inference"
    client_id: str
    store_id: str
    algorithm: Literal["ode", "ode_academic", "ode_new"]
    product_id: str
    quality_index: float = Field(..., description="Predicted quality score (0 to 100)")
    remaining_lifetime: float = Field(..., description="Estimated remaining shelf-life days")
    firmness: float = Field(..., description="Estimated firmness (N)")
    brix: float = Field(..., description="Estimated soluble solids / sugar (°Brix)")
    continuous_data: Optional[Dict[str, List[float]]] = Field(None, description="Continuous curve series for charts")


class StatusResponse(BaseModel):
    busy: bool
    operation: Optional[str] = None
    message: Literal["Available", "Busy"]
    client_id: Optional[str] = None
    store_id: Optional[str] = None
    product_id: Optional[str] = None
    algorithm: Optional[str] = None


class PresetModel(BaseModel):
    Tref_C: float
    Ea_J: float
    k_firm_ref: float
    beta_RH: float
    RH_ref: float
    firmness_min: float
    firmness_0_default: float
    brix_min: float
    brix_max: float
    brix_g: float
    brix_0_default: float
    qual_firmness_threshold: float
    qual_brix_target: float
    acidity_0_default: Optional[float] = None
    acidity_min: Optional[float] = None
    k_acidity_ref: Optional[float] = None
    Ea_acidity_J: Optional[float] = None
    qual_acidity_target: Optional[float] = None
    SL_ref: Optional[float] = None
    E0_int: Optional[float] = None
    Eref_prod: Optional[float] = None
    E_t0: Optional[float] = None
    E_g: Optional[float] = None
    E_auto: Optional[float] = None
    E_decay: Optional[float] = None
    Ea_E_J: Optional[float] = None
    E_ext_shift: Optional[float] = None
    alpha_E: Optional[float] = None


class MoldPresetModel(BaseModel):
    RH_mold_thr: float
    mold_rate_ref: float
    mold_sens_RH: float
    mold_max_penalty: float
    Ea_mold_J: float


class PresetRequest(BaseModel):
    fruit_key: str
    preset: PresetModel
    mold_preset: MoldPresetModel
