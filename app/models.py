import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class RolUsuario(str, enum.Enum):
    consultor = "consultor"
    coordinador = "coordinador"
    finanzas = "finanzas"
    contabilidad = "contabilidad"
    presidencia = "presidencia"


class EstadoTimesheet(str, enum.Enum):
    borrador = "borrador"
    enviado = "enviado"
    aprobado = "aprobado"
    rechazado = "rechazado"
    correccion_solicitada = "correccion_solicitada"


class TipoEventoHistorial(str, enum.Enum):
    creado = "creado"
    editado = "editado"
    enviado = "enviado"
    aprobado = "aprobado"
    rechazado = "rechazado"
    correccion_solicitada = "correccion_solicitada"
    comentario = "comentario"


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre_completo: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    rol: Mapped[RolUsuario] = mapped_column(Enum(RolUsuario, name="rol_usuario"), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CentroCosto(Base):
    __tablename__ = "centros_costo"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    codigo: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Proyecto(Base):
    __tablename__ = "proyectos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    codigo: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    centro_costo_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("centros_costo.id"))
    coordinador_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("usuarios.id"))
    presupuesto_asignado: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Timesheet(Base):
    __tablename__ = "timesheets"
    __table_args__ = (UniqueConstraint("consultor_id", "proyecto_id", "periodo"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    consultor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)
    proyecto_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("proyectos.id"), nullable=False)
    centro_costo_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("centros_costo.id"), nullable=False)
    periodo: Mapped[str] = mapped_column(String, nullable=False)  # 'YYYY-MM'
    estado: Mapped[EstadoTimesheet] = mapped_column(
        Enum(EstadoTimesheet, name="estado_timesheet"), default=EstadoTimesheet.borrador
    )
    version: Mapped[int] = mapped_column(default=1)
    total_horas: Mapped[float] = mapped_column(Numeric(6, 2), default=0)
    enviado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revisado_por: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=True)
    revisado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    detalles: Mapped[list["TimesheetDetalle"]] = relationship(
        back_populates="timesheet", cascade="all, delete-orphan", lazy="selectin"
    )
    historial: Mapped[list["TimesheetHistorial"]] = relationship(
        back_populates="timesheet", cascade="all, delete-orphan", lazy="selectin",
        order_by="TimesheetHistorial.creado_en",
    )


class TimesheetDetalle(Base):
    __tablename__ = "timesheet_detalles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timesheet_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("timesheets.id", ondelete="CASCADE"))
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    actividad: Mapped[str] = mapped_column(Text, nullable=False)
    horas: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    timesheet: Mapped["Timesheet"] = relationship(back_populates="detalles")


class TimesheetHistorial(Base):
    __tablename__ = "timesheet_historial"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timesheet_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("timesheets.id", ondelete="CASCADE"))
    usuario_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)
    tipo_evento: Mapped[TipoEventoHistorial] = mapped_column(
        Enum(TipoEventoHistorial, name="tipo_evento_historial"), nullable=False
    )
    comentario: Mapped[str | None] = mapped_column(Text, nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    timesheet: Mapped["Timesheet"] = relationship(back_populates="historial")
