from fastapi import FastAPI
from app.api.routes_cliente import router as cliente_router
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="CRM COBRANZAS")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # en producción lo restringes
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cliente_router, prefix="/cliente")
