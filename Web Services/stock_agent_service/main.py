"""
Stock Agent Web Service (FastAPI, porta 8005) - integração com a plataforma Retail Eureka (Django).

Modelos guardados em  <STOCK_AGENT_MODELS>/<perfil>/<cultura>/<modo>/modelo.zip   (modo = lot | warehouse)

Endpoints:
  GET  /health
  GET  /models                                   -> modelos disponíveis
  POST /models/upload            (multipart zip) -> publica um modelo treinado na interface Streamlit
  POST /train                    (multipart)     -> treino em background a partir do Excel; devolve job_id
  GET  /train/{job_id}                           -> estado / logs / métricas do treino
  POST /decide                   (JSON)          -> decisão para hoje (lotes a colocar à venda ou armazém a abrir)
"""
import os
import sys
import threading
import traceback
import uuid
from datetime import datetime
from typing import List, Optional, Literal

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

HERE = os.path.dirname(os.path.abspath(__file__))
# Funciona tanto em "Stock Agent/service/main.py" (laboratório) como em "Web Services/stock_agent_service/main.py"
ROOT = HERE if os.path.isdir(os.path.join(HERE, "stock_agent")) else os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from stock_agent.inference import decide_snapshot  # noqa: E402
from stock_agent.lc_kernel import resolve_lc_fruit_key  # noqa: E402
from stock_agent.model_io import load_zip, save_to_storage, storage_path, find_model_path, default_storage_path  # noqa: E402
from stock_agent.schema import read_excel  # noqa: E402
from stock_agent.simulator import SimParams  # noqa: E402
from stock_agent.training import TrainConfig, train_generator  # noqa: E402

MODELS_ROOT = os.environ.get("STOCK_AGENT_MODELS", os.path.join(ROOT, "models_storage"))
app = FastAPI(title="Stock Agent Web Service", version="1.0.0",
              description="Decide que lotes colocar à venda (diário) ou que armazém abrir (semanal), por perfil e cultura.")

_model_cache = {}
_jobs = {}
_lock = threading.Lock()


# ------------------------------------------------------------------ contratos
class Armazem(BaseModel):
    armazem_id: str
    tipo_controlo: Literal["Controlled", "Non-Controlled"] = Field(..., description="Warehouse.control_type")
    localizacao: Optional[str] = None
    aberto: Optional[bool] = Field(False, description="Só agente de armazéns: armazém já aberto")


class Lote(BaseModel):
    lote_id: str = Field(..., description="Harvest.harvest_id")
    armazem_id: str
    data_colheita: str
    data_entrada: Optional[str] = None
    quantidade_kg: float = Field(..., description="Stock atual em kg")
    firmeza: Optional[float] = None
    brix: Optional[float] = None
    acidez: Optional[float] = None
    estado: Optional[Literal["armazenado", "a_venda"]] = "armazenado"


class Leitura(BaseModel):
    armazem_id: str
    data: str
    temperatura: float
    humidade: float
    etileno: Optional[float] = None


class DiaMercado(BaseModel):
    data: str
    preco_kg: float
    procura_prevista_kg: float
    vendas_kg: Optional[float] = None


class DecideRequest(BaseModel):
    perfil: str
    cultura: str
    tipo_fruta: Optional[str] = Field(None, description="Fruta/variedade para o Lifecycle (ex: 'Kiwi Green', 'Apple Fuji')")
    modo: Literal["lot", "warehouse"] = "lot"
    data: str = Field(..., description="Dia da decisão YYYY-MM-DD")
    armazens: List[Armazem]
    lotes: List[Lote]
    leituras: List[Leitura] = Field(default_factory=list, description="Leituras diárias desde a entrada dos lotes")
    mercado: List[DiaMercado] = Field(..., description="Pelo menos 30 dias antes da data e previsão para os 14 dias seguintes")


# ------------------------------------------------------------------ helpers
def _get_model(perfil, cultura, modo, fruit_key=None):
    path, origem = find_model_path(MODELS_ROOT, perfil, cultura, modo, fruit_key)
    if path is None:
        raise HTTPException(404, f"Sem modelo para {perfil} / {cultura} / {modo} (nem modelo por defeito para '{fruit_key}')")
    mtime = os.path.getmtime(path)
    if path not in _model_cache or _model_cache[path][0] != mtime:
        model, cfg, _ = load_zip(path)
        _model_cache[path] = (mtime, model, cfg)
    return _model_cache[path][1], _model_cache[path][2], origem


def _list_models():
    out = []
    for dirpath, _, files in os.walk(MODELS_ROOT):
        if "modelo.zip" in files:
            try:
                _, cfg, _ = load_zip(os.path.join(dirpath, "modelo.zip"))
                out.append({"perfil": cfg["perfil"], "cultura": cfg["cultura"], "modo": cfg["mode"], "fruta": cfg["fruit_key"],
                            "treinado_em": cfg["trained_at"], "temporadas_treino": cfg["train_seasons"], "metricas": cfg["metrics"]})
            except Exception as e:  # noqa: BLE001
                out.append({"caminho": dirpath, "erro": str(e)})
    return out


# ------------------------------------------------------------------ endpoints
@app.get("/health")
def health():
    return {"status": "ok", "service": "stock_agent", "models_root": MODELS_ROOT, "time": datetime.now().isoformat(timespec="seconds")}


@app.get("/models")
def models():
    return {"modelos": _list_models()}


@app.post("/models/upload")
async def upload_model(file: UploadFile = File(...)):
    b = await file.read()
    try:
        _, cfg, _ = load_zip(b)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"ZIP de modelo inválido: {e}")
    path = save_to_storage(MODELS_ROOT, b, cfg["perfil"], cfg["cultura"], cfg["mode"])
    return {"guardado_em": path, "perfil": cfg["perfil"], "cultura": cfg["cultura"], "modo": cfg["mode"]}


@app.post("/decide")
def decide(req: DecideRequest):
    if not req.lotes:
        raise HTTPException(422, "Sem lotes em stock para decidir.")
    fruit_key = resolve_lc_fruit_key(req.tipo_fruta or req.cultura)
    model, cfg, origem = _get_model(req.perfil, req.cultura, req.modo, fruit_key)
    payload = req.model_dump()
    for lot in payload["lotes"]:
        lot["tipo_fruta"] = req.tipo_fruta or req.cultura
    try:
        # Com um modelo por defeito, normaliza o estado com as escalas deste perfil (preço, procura, tamanho dos lotes)
        out = decide_snapshot(model, cfg, payload, adapt_norm=(origem != "perfil"))
    except ValueError as e:
        raise HTTPException(422, str(e))
    out["perfil"], out["cultura"] = req.perfil, req.cultura
    out["modelo_usado"] = {"origem": origem, "perfil_treino": cfg["perfil"], "cultura_treino": cfg["cultura"],
                           "fruta_lifecycle": fruit_key, "fruta_modelo": cfg["fruit_key"], "treinado_em": cfg["trained_at"], "metricas": cfg["metrics"]}
    return out


@app.post("/train")
async def train(file: UploadFile = File(..., description="Excel no formato do Stock Agent"),
                perfil: str = Form(...), cultura: str = Form(...), modo: Literal["lot", "warehouse"] = Form("lot"),
                temporadas_treino: str = Form(..., description="Ex: 2020,2021,2022"),
                temporadas_validacao: str = Form("", description="Ex: 2023"),
                episodios: int = Form(400), peso_desperdicio: float = Form(2.0)):
    try:
        data = read_excel(await file.read())
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"Excel inválido: {e}")
    parse = lambda s: [int(x) for x in str(s).replace(";", ",").split(",") if str(x).strip()]
    job_id = uuid.uuid4().hex[:12]
    job = {"job_id": job_id, "estado": "a_correr", "perfil": perfil, "cultura": cultura, "modo": modo, "progresso": 0.0,
           "logs": [], "inicio": datetime.now().isoformat(timespec="seconds")}
    with _lock:
        _jobs[job_id] = job

    def run():
        try:
            gen = train_generator(data, perfil, cultura, modo, parse(temporadas_treino), parse(temporadas_validacao),
                                  SimParams(waste_weight=peso_desperdicio), TrainConfig(episodes=episodios))
            for ev in gen:
                if ev["type"] == "log":
                    job["logs"].append(ev["msg"])
                elif ev["type"] == "progress":
                    job["progresso"] = ev["episode"] / ev["total"]
                elif ev["type"] == "done":
                    job["modelo"] = save_to_storage(MODELS_ROOT, ev["zip_bytes"], perfil, cultura, modo)
                    job["metricas"] = ev["config"]["metrics"]
            job["estado"] = "concluido"
            job["progresso"] = 1.0
        except Exception as e:  # noqa: BLE001
            job["estado"] = "erro"
            job["erro"] = str(e)
            job["logs"].append(traceback.format_exc())

    threading.Thread(target=run, daemon=True).start()
    return {"job_id": job_id, "estado": "a_correr"}


@app.get("/train/{job_id}")
def train_status(job_id: str, ultimas_linhas: int = 30):
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(404, "job_id desconhecido")
    return dict({k: v for k, v in job.items() if k != "logs"}, logs=job["logs"][-ultimas_linhas:])


if __name__ == "__main__":
    uvicorn.run("main:app", host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", "8005")), reload=False)
