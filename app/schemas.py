import uuid
from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field

from app.models import EstadoTimesheet, RolUsuario, TipoEventoHistorial

# ------------------------------------------------------------
# Auth / Usuarios
# ------------------------------------------------------------


class UsuarioCreate(BaseModel):
    nombre_completo: str
    email: EmailStr
    password: str = Field(min_length=8)
    rol: RolUsuario = RolUsuario.consultor


class UsuarioLogin(BaseModel):
    email: EmailStr
    password: str


class UsuarioOut(BaseModel):
    id: uuid.UUID
    nombre_completo: str
    email: EmailStr
    rol: RolUsuario
    activo: bool

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ------------------------------------------------------------
# Timesheet detalle
# ------------------------------------------------------------


class TimesheetDetalleCreate(BaseModel):
    fecha: date
    actividad: str
    horas: float = Field(gt=0, le=24)


class TimesheetDetalleOut(BaseModel):
    id: uuid.UUID
    fecha: date
    actividad: str
    horas: float

    class Config:
        from_attributes = True


# ------------------------------------------------------------
# Timesheet cabecera (RF-01, RF-02)
# ------------------------------------------------------------


class TimesheetCreate(BaseModel):
    proyecto_id: uuid.UUID
    centro_costo_id: uuid.UUID
    periodo: str = Field(description="Formato YYYY-MM, ej. 2026-07")
    detalles: list[TimesheetDetalleCreate] = []


class TimesheetUpdate(BaseModel):
    """Solo editable mientras el timesheet está en borrador o requiere corrección (RF-02)."""

    detalles: list[TimesheetDetalleCreate] | None = None


class TimesheetHistorialOut(BaseModel):
    id: uuid.UUID
    usuario_id: uuid.UUID
    tipo_evento: TipoEventoHistorial
    comentario: str | None
    creado_en: datetime

    class Config:
        from_attributes = True


class TimesheetOut(BaseModel):
    id: uuid.UUID
    consultor_id: uuid.UUID
    proyecto_id: uuid.UUID
    centro_costo_id: uuid.UUID
    periodo: str
    estado: EstadoTimesheet
    version: int
    total_horas: float
    enviado_en: datetime | None
    revisado_por: uuid.UUID | None
    revisado_en: datetime | None
    creado_en: datetime
    actualizado_en: datetime
    detalles: list[TimesheetDetalleOut] = []
    historial: list[TimesheetHistorialOut] = []

    class Config:
        from_attributes = True


# ------------------------------------------------------------
# Flujo de aprobación (RF-04, RF-05, RF-12)
# ------------------------------------------------------------


class RevisionTimesheet(BaseModel):
    """Usado por el coordinador para aprobar, rechazar o pedir correcciones."""

    comentario: str | None = None
