"""Guardar / carregar o modelo do Stock Agent como ZIP (config.json + policy.pt + historico_treino.csv)."""
import io
import json
import os
import zipfile

import pandas as pd
import torch

from .policy import SetActorCritic

FORMAT_VERSION = 1


def build_model(config):
    return SetActorCritic(config["f_item"], config["f_ctx"], config["mode"], hidden=config.get("hidden", 128))


def bundle_to_zip_bytes(model, config, history: pd.DataFrame = None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        cfg = dict(config, format_version=FORMAT_VERSION)
        z.writestr("config.json", json.dumps(cfg, indent=2, default=str, ensure_ascii=False))
        sd = io.BytesIO()
        torch.save(model.state_dict(), sd)
        z.writestr("policy.pt", sd.getvalue())
        if history is not None and len(history):
            z.writestr("historico_treino.csv", history.to_csv(index=False))
    return buf.getvalue()


def load_zip(source):
    """source: caminho, bytes ou ficheiro carregado. Devolve (modelo, config, histórico)."""
    if isinstance(source, (bytes, bytearray)):
        source = io.BytesIO(source)
    with zipfile.ZipFile(source) as z:
        config = json.loads(z.read("config.json").decode("utf-8"))
        state = torch.load(io.BytesIO(z.read("policy.pt")), map_location="cpu", weights_only=True)
        hist = pd.read_csv(io.BytesIO(z.read("historico_treino.csv"))) if "historico_treino.csv" in z.namelist() else None
    model = build_model(config)
    model.load_state_dict(state)
    model.eval()
    return model, config, hist


def storage_path(root, perfil, cultura, mode):
    """Estrutura usada pelo web service: <root>/<perfil>/<cultura>/<modo>/modelo.zip"""
    safe = lambda x: "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(x))
    return os.path.join(root, safe(perfil), safe(cultura), mode, "modelo.zip")


DEFAULT_PROFILE = "_default"
FAMILY_FALLBACK = {"kiwi": "kiwi_hayward", "apple": "apple_gala"}


def default_storage_path(root, fruit_key, mode):
    """Modelos por defeito (treinados com dados sintéticos), um por fruta do Lifecycle: <root>/_default/<fruta>/<modo>/modelo.zip"""
    return storage_path(root, DEFAULT_PROFILE, fruit_key, mode)


def find_model_path(root, perfil, cultura, mode, fruit_key=None):
    """
    Ordem de procura:
      1. modelo próprio do perfil e cultura;
      2. modelo por defeito da fruta (ex: kiwi_gold);
      3. modelo por defeito da família (kiwi -> kiwi_hayward, apple -> apple_gala).
    Devolve (caminho, origem) com origem em {"perfil", "defeito_fruta", "defeito_familia"} ou (None, None).
    """
    p = storage_path(root, perfil, cultura, mode)
    if os.path.exists(p):
        return p, "perfil"
    if fruit_key:
        p = default_storage_path(root, fruit_key, mode)
        if os.path.exists(p):
            return p, "defeito_fruta"
        fam = FAMILY_FALLBACK.get(fruit_key.split("_")[0])
        if fam:
            p = default_storage_path(root, fam, mode)
            if os.path.exists(p):
                return p, "defeito_familia"
    return None, None


def save_to_storage(root, zip_bytes, perfil, cultura, mode):
    path = storage_path(root, perfil, cultura, mode)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(zip_bytes)
    return path
