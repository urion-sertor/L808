"""
Reservas de la app móvil · Responsable: Adrián

  GET   /api/reservas/disponibilidad      Horas libres de una noche     200 · 400 · 404
  POST  /api/reservas                     Crear reserva desde móvil     201 · 400 · 401 · 404 · 409
  GET   /api/reservas/mias                Mis próximas o historial      200 · 400 · 401
  GET   /api/reservas/{codigo}            Detalle de una reserva mía    200 · 401 · 404
  PATCH /api/reservas/{codigo}/cancelar   Cancelar reserva confirmada   200 · 400 · 401 · 404 · 409
"""
from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from .. import reglas
from ..database import get_db
from ..models import Cliente, Reserva, Servicio
from ..schemas.reservas import (
    DisponibilidadOut,
    MensajeOut,
    ReservaCreateIn,
    ReservaOut,
)
from ..security import get_cliente_actual

router = APIRouter(prefix="/api/reservas", tags=["Reservas (móvil)"])


# ---------------------------------------------------------------- ayudas
def _buscar_reserva_cliente(db: Session, codigo: str, id_cliente: int) -> Reserva:
    """Devuelve la reserva si existe y pertenece al cliente; si no, 404."""
    codigo_limpio = codigo.strip().upper()
    reserva = db.scalar(
        select(Reserva)
        .options(joinedload(Reserva.servicio))
        .where(
            Reserva.codigo_reserva == codigo_limpio,
            Reserva.id_cliente == id_cliente,
        )
    )
    if reserva is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reserva no encontrada.")
    return reserva


# ---------------------------------------------------------------- endpoints
@router.get(
    "/disponibilidad",
    response_model=DisponibilidadOut,
    summary="Horas libres de una noche para un servicio (pantallas M-05 y M-06)",
    responses={
        400: {"model": MensajeOut, "description": "Domingo o fecha no válida"},
        404: {"model": MensajeOut, "description": "Servicio no existe o está desactivado"},
    },
)
def ver_disponibilidad(
    fecha: date = Query(description="Fecha de la jornada en formato AAAA-MM-DD", examples=["2026-12-04"]),
    id_servicio: int = Query(gt=0, description="ID del servicio", examples=[2]),
    db: Session = Depends(get_db),
):
    servicio = db.get(Servicio, id_servicio)
    if servicio is None or not servicio.activo_app:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "El servicio no existe o no está disponible.",
        )

    franjas = reglas.franjas_del_dia(db, fecha, servicio.duracion_min)
    return DisponibilidadOut(fecha=fecha, servicio=servicio, franjas=franjas)


@router.post(
    "",
    response_model=ReservaOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una reserva desde la app móvil (pantallas M-05 a M-07)",
    responses={
        400: {"model": MensajeOut, "description": "Fuera de horario, fecha pasada o servicio inactivo"},
        401: {"model": MensajeOut, "description": "Falta token de cliente o no es válido"},
        404: {"model": MensajeOut, "description": "Servicio no encontrado"},
        409: {"model": MensajeOut, "description": "Estudio lleno (franja ocupada)"},
    },
)
def crear_reserva_movil(
    datos: ReservaCreateIn,
    cliente: Cliente = Depends(get_cliente_actual),
    db: Session = Depends(get_db),
):
    servicio = db.get(Servicio, datos.id_servicio)
    if servicio is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El servicio no existe.")

    reserva = reglas.crear_reserva(
        db=db,
        cliente=cliente,
        servicio=servicio,
        inicio=datos.inicio,
        origen="APP",
        trabajador=None,
    )
    # Recargamos la relación servicio para la serialización de salida
    db.refresh(reserva)
    return reserva


@router.get(
    "/mias",
    response_model=list[ReservaOut],
    summary="Listar mis reservas próximas o mi historial (pantallas M-08 y M-09)",
    responses={
        400: {"model": MensajeOut, "description": "Parámetro tipo no válido"},
        401: {"model": MensajeOut, "description": "Falta token de cliente"},
    },
)
def listar_mis_reservas(
    tipo: Literal["proximas", "historial"] = Query(
        default="proximas",
        description="Filtrar por 'proximas' o 'historial'",
    ),
    cliente: Cliente = Depends(get_cliente_actual),
    db: Session = Depends(get_db),
):
    ahora = datetime.now()
    consulta = select(Reserva).options(joinedload(Reserva.servicio)).where(
        Reserva.id_cliente == cliente.id_cliente
    )

    if tipo == "proximas":
        consulta = consulta.where(
            Reserva.estado == "CONFIRMADA",
            Reserva.fin > ahora,
        ).order_by(Reserva.inicio.asc())
    else:
        consulta = consulta.where(
            or_(Reserva.estado != "CONFIRMADA", Reserva.fin <= ahora)
        ).order_by(Reserva.inicio.desc())

    return db.scalars(consulta).all()


@router.get(
    "/{codigo}",
    response_model=ReservaOut,
    summary="Ver el detalle de una reserva mía (pantalla M-10)",
    responses={
        401: {"model": MensajeOut, "description": "Falta token de cliente"},
        404: {"model": MensajeOut, "description": "Reserva no existe o pertenece a otro cliente"},
    },
)
def detalle_reserva(
    codigo: str,
    cliente: Cliente = Depends(get_cliente_actual),
    db: Session = Depends(get_db),
):
    return _buscar_reserva_cliente(db, codigo, cliente.id_cliente)


@router.patch(
    "/{codigo}/cancelar",
    response_model=ReservaOut,
    summary="Cancelar una reserva confirmada que aún no ha empezado (pantalla M-10)",
    responses={
        400: {"model": MensajeOut, "description": "La reserva ya ha empezado"},
        401: {"model": MensajeOut, "description": "Falta token de cliente"},
        404: {"model": MensajeOut, "description": "Reserva no existe o pertenece a otro cliente"},
        409: {"model": MensajeOut, "description": "Esta reserva ya no se puede cancelar"},
    },
)
def cancelar_reserva(
    codigo: str,
    cliente: Cliente = Depends(get_cliente_actual),
    db: Session = Depends(get_db),
):
    reserva = _buscar_reserva_cliente(db, codigo, cliente.id_cliente)

    if reserva.estado != "CONFIRMADA":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Esta reserva ya no se puede cancelar.",
        )

    if reserva.inicio <= datetime.now():
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "No se puede cancelar una reserva que ya ha empezado.",
        )

    reserva.estado = "CANCELADA"
    db.commit()
    db.refresh(reserva)
    return reserva