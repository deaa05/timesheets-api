import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user, require_roles
from app.database import get_db
from app.models import (
    EstadoTimesheet,
    Proyecto,
    RolUsuario,
    TimesheetDetalle,
    TimesheetHistorial,
    Timesheet,
    TipoEventoHistorial,
    Usuario,
)
from app.notifications import notificar
from app.schemas import (
    RevisionTimesheet,
    TimesheetCreate,
    TimesheetOut,
    TimesheetUpdate,
)

router = APIRouter(prefix="/timesheets", tags=["Timesheets"])


async def _get_timesheet_o_404(db: AsyncSession, timesheet_id: uuid.UUID) -> Timesheet:
    result = await db.execute(select(Timesheet).where(Timesheet.id == timesheet_id))
    timesheet = result.scalar_one_or_none()
    if timesheet is None:
        raise HTTPException(status_code=404, detail="Timesheet no encontrado")
    return timesheet


def _recalcular_total_horas(timesheet: Timesheet) -> None:
    timesheet.total_horas = sum(float(d.horas) for d in timesheet.detalles)


# ------------------------------------------------------------
# RF-01 / RF-02: registrar horas y guardar como borrador
# ------------------------------------------------------------
@router.post("", response_model=TimesheetOut, status_code=status.HTTP_201_CREATED)
async def crear_timesheet(
    payload: TimesheetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(RolUsuario.consultor)),
):
    proyecto = await db.get(Proyecto, payload.proyecto_id)
    if proyecto is None or not proyecto.activo:
        raise HTTPException(status_code=400, detail="Proyecto inválido o inactivo")

    timesheet = Timesheet(
        consultor_id=current_user.id,
        proyecto_id=payload.proyecto_id,
        centro_costo_id=payload.centro_costo_id,
        periodo=payload.periodo,
        estado=EstadoTimesheet.borrador,
        detalles=[
            TimesheetDetalle(fecha=d.fecha, actividad=d.actividad, horas=d.horas) for d in payload.detalles
        ],
    )
    _recalcular_total_horas(timesheet)
    timesheet.historial.append(
        TimesheetHistorial(usuario_id=current_user.id, tipo_evento=TipoEventoHistorial.creado)
    )

    db.add(timesheet)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Ya existe un timesheet para este consultor, proyecto y periodo",
        )
    await db.refresh(timesheet)
    return timesheet


# ------------------------------------------------------------
# RF-10: búsqueda y filtrado
# ------------------------------------------------------------
@router.get("", response_model=list[TimesheetOut])
async def listar_timesheets(
    estado: EstadoTimesheet | None = Query(default=None),
    proyecto_id: uuid.UUID | None = Query(default=None),
    periodo: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    query = select(Timesheet)

    # Un consultor solo ve lo suyo; roles de gestión ven todo (RF-08, RF-13)
    if current_user.rol == RolUsuario.consultor:
        query = query.where(Timesheet.consultor_id == current_user.id)

    if estado is not None:
        query = query.where(Timesheet.estado == estado)
    if proyecto_id is not None:
        query = query.where(Timesheet.proyecto_id == proyecto_id)
    if periodo is not None:
        query = query.where(Timesheet.periodo == periodo)

    result = await db.execute(query.order_by(Timesheet.creado_en.desc()))
    return result.scalars().all()


@router.get("/{timesheet_id}", response_model=TimesheetOut)
async def obtener_timesheet(
    timesheet_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    timesheet = await _get_timesheet_o_404(db, timesheet_id)
    if current_user.rol == RolUsuario.consultor and timesheet.consultor_id != current_user.id:
        raise HTTPException(status_code=403, detail="No tienes acceso a este timesheet")
    return timesheet


# ------------------------------------------------------------
# RF-02 / RF-11: editar borrador (o corregir tras solicitud de correcciones)
# ------------------------------------------------------------
@router.put("/{timesheet_id}", response_model=TimesheetOut)
async def editar_timesheet(
    timesheet_id: uuid.UUID,
    payload: TimesheetUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(RolUsuario.consultor)),
):
    timesheet = await _get_timesheet_o_404(db, timesheet_id)
    if timesheet.consultor_id != current_user.id:
        raise HTTPException(status_code=403, detail="No tienes acceso a este timesheet")
    if timesheet.estado not in (EstadoTimesheet.borrador, EstadoTimesheet.correccion_solicitada):
        raise HTTPException(
            status_code=400,
            detail="Solo se puede editar un timesheet en borrador o con corrección solicitada",
        )

    if payload.detalles is not None:
        timesheet.detalles.clear()
        for d in payload.detalles:
            timesheet.detalles.append(
                TimesheetDetalle(fecha=d.fecha, actividad=d.actividad, horas=d.horas)
            )
        _recalcular_total_horas(timesheet)

    timesheet.version += 1
    timesheet.estado = EstadoTimesheet.borrador
    timesheet.historial.append(
        TimesheetHistorial(usuario_id=current_user.id, tipo_evento=TipoEventoHistorial.editado)
    )

    await db.commit()
    await db.refresh(timesheet)
    return timesheet


# ------------------------------------------------------------
# RF-03: enviar para revisión + notificar al coordinador
# ------------------------------------------------------------
@router.post("/{timesheet_id}/enviar", response_model=TimesheetOut)
async def enviar_timesheet(
    timesheet_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(RolUsuario.consultor)),
):
    timesheet = await _get_timesheet_o_404(db, timesheet_id)
    if timesheet.consultor_id != current_user.id:
        raise HTTPException(status_code=403, detail="No tienes acceso a este timesheet")
    if timesheet.estado not in (EstadoTimesheet.borrador, EstadoTimesheet.correccion_solicitada):
        raise HTTPException(status_code=400, detail="El timesheet no está en un estado enviable")
    if not timesheet.detalles:
        raise HTTPException(status_code=400, detail="No se puede enviar un timesheet sin horas registradas")

    timesheet.estado = EstadoTimesheet.enviado
    timesheet.enviado_en = datetime.now(timezone.utc)
    timesheet.historial.append(
        TimesheetHistorial(usuario_id=current_user.id, tipo_evento=TipoEventoHistorial.enviado)
    )
    await db.commit()
    await db.refresh(timesheet)

    proyecto = await db.get(Proyecto, timesheet.proyecto_id)
    if proyecto and proyecto.coordinador_id:
        coordinador = await db.get(Usuario, proyecto.coordinador_id)
        if coordinador:
            await notificar(
                destinatario_email=coordinador.email,
                asunto="Nuevo timesheet para revisión",
                mensaje=(
                    f"El consultor {current_user.nombre_completo} envió el timesheet "
                    f"del periodo {timesheet.periodo} para el proyecto {proyecto.nombre}."
                ),
            )

    return timesheet


# ------------------------------------------------------------
# RF-04 / RF-05 / RF-12: aprobar, rechazar o solicitar correcciones
# ------------------------------------------------------------
async def _resolver_revision(
    timesheet_id: uuid.UUID,
    payload: RevisionTimesheet,
    nuevo_estado: EstadoTimesheet,
    tipo_evento: TipoEventoHistorial,
    db: AsyncSession,
    current_user: Usuario,
) -> Timesheet:
    timesheet = await _get_timesheet_o_404(db, timesheet_id)
    if timesheet.estado != EstadoTimesheet.enviado:
        raise HTTPException(
            status_code=400,
            detail="Solo se pueden revisar timesheets en estado 'enviado'",
        )

    timesheet.estado = nuevo_estado
    timesheet.revisado_por = current_user.id
    timesheet.revisado_en = datetime.now(timezone.utc)
    timesheet.historial.append(
        TimesheetHistorial(
            usuario_id=current_user.id,
            tipo_evento=tipo_evento,
            comentario=payload.comentario,
        )
    )
    await db.commit()
    await db.refresh(timesheet)

    consultor = await db.get(Usuario, timesheet.consultor_id)
    if consultor:
        await notificar(
            destinatario_email=consultor.email,
            asunto=f"Tu timesheet fue {nuevo_estado.value}",
            mensaje=payload.comentario or f"Estado actualizado a: {nuevo_estado.value}",
        )

    return timesheet


@router.post("/{timesheet_id}/aprobar", response_model=TimesheetOut)
async def aprobar_timesheet(
    timesheet_id: uuid.UUID,
    payload: RevisionTimesheet,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(RolUsuario.coordinador)),
):
    return await _resolver_revision(
        timesheet_id, payload, EstadoTimesheet.aprobado, TipoEventoHistorial.aprobado, db, current_user
    )


@router.post("/{timesheet_id}/rechazar", response_model=TimesheetOut)
async def rechazar_timesheet(
    timesheet_id: uuid.UUID,
    payload: RevisionTimesheet,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(RolUsuario.coordinador)),
):
    return await _resolver_revision(
        timesheet_id, payload, EstadoTimesheet.rechazado, TipoEventoHistorial.rechazado, db, current_user
    )


@router.post("/{timesheet_id}/solicitar-correccion", response_model=TimesheetOut)
async def solicitar_correccion(
    timesheet_id: uuid.UUID,
    payload: RevisionTimesheet,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(RolUsuario.coordinador)),
):
    return await _resolver_revision(
        timesheet_id,
        payload,
        EstadoTimesheet.correccion_solicitada,
        TipoEventoHistorial.correccion_solicitada,
        db,
        current_user,
    )


# ------------------------------------------------------------
# RF-12: agregar comentario en cualquier etapa
# ------------------------------------------------------------
@router.post("/{timesheet_id}/comentarios", response_model=TimesheetOut)
async def agregar_comentario(
    timesheet_id: uuid.UUID,
    payload: RevisionTimesheet,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    timesheet = await _get_timesheet_o_404(db, timesheet_id)
    es_dueno = timesheet.consultor_id == current_user.id
    es_gestion = current_user.rol != RolUsuario.consultor
    if not (es_dueno or es_gestion):
        raise HTTPException(status_code=403, detail="No tienes acceso a este timesheet")
    if not payload.comentario:
        raise HTTPException(status_code=400, detail="El comentario no puede estar vacío")

    timesheet.historial.append(
        TimesheetHistorial(
            usuario_id=current_user.id,
            tipo_evento=TipoEventoHistorial.comentario,
            comentario=payload.comentario,
        )
    )
    await db.commit()
    await db.refresh(timesheet)
    return timesheet
