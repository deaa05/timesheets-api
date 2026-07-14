from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import auth, timesheets

app = FastAPI(
    title="API Timesheets CORPEI",
    description=(
        "Sistema Integral de Gestión de Timesheets para Consultores. "
        "Cubre el registro de horas, borradores, flujo de aprobación y "
        "trazabilidad de cambios (RF-01 a RF-05)."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(timesheets.router)


@app.get("/health", tags=["Sistema"])
async def health_check():
    return {"status": "ok"}
