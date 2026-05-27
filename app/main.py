from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_auth import router as auth_router
from app.api.routes_canales import router as canales_router
from app.api.routes_cliente import router as cliente_router
from app.api.routes_compromisos import router as compromisos_router
from app.api.routes_corporativo import router as corporativo_router
from app.api.routes_metas import router as metas_router
from app.api.routes_pagos import router as pagos_router


app = FastAPI(title="CRM COBRANZAS")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_router, prefix="/auth", tags=["Auth"])
app.include_router(canales_router, prefix="/canales", tags=["Canales Alternos"])
app.include_router(cliente_router, prefix="/cliente", tags=["Cliente"])
app.include_router(compromisos_router, prefix="/compromisos", tags=["Compromisos"])
app.include_router(corporativo_router, prefix="/corporativo", tags=["Corporativo"])
app.include_router(pagos_router, prefix="/pagos", tags=["Pagos"])
app.include_router(metas_router, prefix="/metas", tags=["Metas"])


@app.get("/")
def healthcheck():
    return {"ok": True, "app": "CRM SAC Cobranzas"}
