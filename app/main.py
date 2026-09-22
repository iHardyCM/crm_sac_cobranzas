# main.py
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes_auth import router as auth_router
from app.api.routes_admin_metas_agentes import router as admin_metas_agentes_router
from app.api.routes_admin_pautas_evaluacion import router as admin_pautas_evaluacion_router
from app.api.routes_admin_supervisores import router as admin_supervisores_router
from app.api.routes_calibracion import router as calibracion_router
from app.api.routes_canales import router as canales_router
from app.api.routes_cliente import router as cliente_router
from app.api.routes_compromisos import router as compromisos_router
from app.api.routes_corporativo import router as corporativo_router
from app.api.routes_control_horario import router as control_horario_router
from app.api.routes_documentos import router as documentos_router
from app.api.routes_metas import router as metas_router
from app.api.routes_pagos import router as pagos_router
from app.api.routes_planes_mejora import router as planes_mejora_router
from app.api.routes_importacion import router as importacion_router
from app.api.routes_score_telefonico import router as score_telefonico_router
from app.api.routes_ia_feedback import router as ia_feedback_router
from app.api.routes_susurro_ia import router as susurro_ia_router
from app.api.routes_telefonos import router as telefonos_router

def configurar_logging():
    """Escribe el log de la aplicacion en logs/app.log.

    Sin esto, todo lo que registra el codigo con logger.info() se pierde: el
    logger de la app propaga al root, que sin handler descarta por debajo de
    WARNING. Es decir, la aplicacion no dejaba ningun rastro de lo que hacia.

    Rota a los 5 MB y conserva 5 archivos, para que no crezca sin control.
    El nivel se puede bajar con la variable de entorno CRM_LOG_LEVEL.
    """
    raiz = Path(__file__).resolve().parents[1]
    carpeta = raiz / "logs"
    carpeta.mkdir(exist_ok=True)

    nivel = getattr(logging, os.getenv("CRM_LOG_LEVEL", "INFO").upper(), logging.INFO)
    formato = logging.Formatter(
        "%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    archivo = RotatingFileHandler(
        carpeta / "app.log", maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    archivo.setFormatter(formato)

    root = logging.getLogger()
    root.setLevel(nivel)
    # Evita duplicar handlers si el modulo se recarga (uvicorn --reload).
    if not any(isinstance(h, RotatingFileHandler) for h in root.handlers):
        root.addHandler(archivo)
    logging.getLogger("app").setLevel(nivel)


configurar_logging()

app = FastAPI(title="CRM COBRANZAS")

app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/auth", tags=["Auth"])
app.include_router(admin_metas_agentes_router, prefix="/admin-metas-agentes", tags=["Administracion Metas Agentes"])
app.include_router(admin_pautas_evaluacion_router, prefix="/admin-pautas-evaluacion", tags=["Administracion Pautas Evaluacion"])
app.include_router(admin_supervisores_router, prefix="/admin-supervisores", tags=["Administracion Supervisores"])
app.include_router(calibracion_router, prefix="/calibracion", tags=["Calibracion IA"])
app.include_router(canales_router, prefix="/canales", tags=["Canales Alternos"])
app.include_router(cliente_router, prefix="/cliente", tags=["Cliente"])
app.include_router(compromisos_router, prefix="/compromisos", tags=["Compromisos"])
app.include_router(corporativo_router, prefix="/corporativo", tags=["Corporativo"])
app.include_router(control_horario_router, prefix="/control-horario", tags=["Control Horario"])
app.include_router(documentos_router, prefix="/documentos", tags=["Documentos Automatizados"])
app.include_router(importacion_router, prefix="/importacion", tags=["Importacion de Cartera"])
app.include_router(ia_feedback_router, prefix="/ia-feedback", tags=["Analisis IA"])
app.include_router(susurro_ia_router, prefix="/susurro-ia", tags=["Susurro IA"])
app.include_router(pagos_router, prefix="/pagos", tags=["Pagos"])
app.include_router(planes_mejora_router, prefix="/planes-mejora", tags=["Planes de mejora IA"])
app.include_router(metas_router, prefix="/metas", tags=["Metas"])
app.include_router(score_telefonico_router, prefix="/score-telefonico", tags=["Score Telefonico"])
app.include_router(telefonos_router, prefix="/telefonos", tags=["Validación de Teléfonos"])

@app.get("/")
def healthcheck():
    return {"ok": True, "app": "CRM SAC Cobranzas"}
