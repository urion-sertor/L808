"""
Agenda y trabajadores del escritorio · Responsable: Oriol

  POST  /api/trabajadores/login                     Login de trabajador          200 · 400 · 401
  GET   /api/trabajadores/me                        Ver perfil del trabajador    200 · 401
  GET   /api/agenda                                 Reservas del día             200 · 400 · 401
  GET   /api/agenda/buscar                          Buscar reservas              200 · 400 · 401
  GET   /api/agenda/clientes                        Buscador de clientes         200 · 401
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from .. import config, reglas
from ..database import get_db
from ..models import Cliente, Reserva, Trabajador
from ..schemas.agenda import (
    AgendaDiaOut,
    AgendaReservaOut,
    ClienteAgendaOut,
    ClienteBusquedaItemOut,
    LoginTrabajadorIn,
    MensajeOut,
    ServicioAgendaOut,
    SesionTrabajadorOut,
    TrabajadorOut,
    TrabajadorResumenOut,
)
from ..security import crear_token, get_trabajador_actual, verificar_password

router = APIRouter(prefix="/api", tags=["Escritorio (trabajadores)"])


# ---------------------------------------------------------------- ayudas
def _a_salida_reserva(r: Reserva) -> AgendaReservaOut:
    """Convierte un modelo Reserva al formato de salida de la agenda (AgendaReservaOut)."""
    return AgendaReservaOut(
        codigo_reserva=r.codigo_reserva,
        inicio=r.inicio,
        fin=r.fin,
        estado=r.estado,
        origen=r.origen,
        precio=float(r.precio),
        servicio=ServicioAgendaOut.model_validate(r.servicio),
        cliente=ClienteAgendaOut.model_validate(r.cliente),
        registrada_por=TrabajadorResumenOut.model_validate(r.trabajador) if r.trabajador else None,
    )


# ---------------------------------------------------------------- trabajadores
@router.post(
    "/trabajadores/login",
    response_model=SesionTrabajadorOut,
    summary="Iniciar sesión como trabajador (pantalla E-01)",
    responses={
        400: {"model": MensajeOut, "description": "Datos de inicio de sesión no válidos"},
        401: {"model": MensajeOut, "description": "Usuario o contraseña incorrectos o cuenta desactivada"},
    },
)
def login_trabajador(datos: LoginTrabajadorIn, db: Session = Depends(get_db)):
    trabajador = db.scalar(select(Trabajador).where(Trabajador.usuario == datos.usuario.strip()))
    if trabajador is None or not verificar_password(datos.password, trabajador.password_hash):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Usuario o contraseña incorrectos.",
        )
    if not trabajador.activo:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Cuenta de trabajador desactivada.",
        )

    return SesionTrabajadorOut(
        access_token=crear_token(trabajador.id_trabajador, "trabajador"),
        trabajador=trabajador,
    )


@router.get(
    "/trabajadores/me",
    response_model=TrabajadorOut,
    summary="Ver perfil del trabajador actual (barra lateral)",
    responses={401: {"model": MensajeOut, "description": "Falta token de trabajador o no es válido"}},
)
def ver_perfil_trabajador(
    trabajador: Trabajador = Depends(get_trabajador_actual),
):
    return trabajador


# ---------------------------------------------------------------- agenda y consultas
@router.get(
    "/agenda",
    response_model=AgendaDiaOut,
    summary="Ver reservas del día de la agenda del escritorio (pantalla E-02)",
    responses={
        400: {"model": MensajeOut, "description": "Día no abierto o fecha no válida"},
        401: {"model": MensajeOut, "description": "Falta token de trabajador o no es válido"},
    },
)
def ver_agenda(
    fecha: date = Query(description="Fecha de la jornada en formato AAAA-MM-DD", examples=["2026-11-13"]),
    trabajador: Trabajador = Depends(get_trabajador_actual),
    db: Session = Depends(get_db),
):
    if fecha.weekday() not in config.DIAS_ABIERTO:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, reglas.MENSAJE_FUERA_HORARIO)

    apertura, cierre = reglas.rango_jornada(fecha)

    consulta = (
        select(Reserva)
        .options(
            joinedload(Reserva.servicio),
            joinedload(Reserva.cliente),
            joinedload(Reserva.trabajador),
        )
        .where(
            Reserva.estado != "CANCELADA",
            Reserva.inicio >= apertura,
            Reserva.inicio < cierre,
        )
        .order_by(Reserva.inicio.asc())
    )
    reservas = db.scalars(consulta).all()

    return AgendaDiaOut(
        fecha=fecha,
        reservas=[_a_salida_reserva(r) for r in reservas],
    )


@router.get(
    "/agenda/buscar",
    response_model=list[AgendaReservaOut],
    summary="Búsqueda de reservas con filtros opcionales (pantallas E-04 y E-04b)",
    responses={
        400: {"model": MensajeOut, "description": "Rango de fechas no válido o estado incorrecto"},
        401: {"model": MensajeOut, "description": "Falta token de trabajador o no es válido"},
    },
)
def buscar_reservas(
    cliente: Optional[str] = Query(default=None, description="Nombre artístico, nombre completo o teléfono del cliente", examples=["Kroma"]),
    desde: Optional[date] = Query(default=None, description="Fecha jornada inicial", examples=["2026-11-01"]),
    hasta: Optional[date] = Query(default=None, description="Fecha jornada final", examples=["2026-11-30"]),
    estado: Optional[str] = Query(default=None, description="CONFIRMADA, REALIZADA o CANCELADA", examples=["CONFIRMADA"]),
    trabajador: Trabajador = Depends(get_trabajador_actual),
    db: Session = Depends(get_db),
):
    if desde and hasta and desde > hasta:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "La fecha 'desde' no puede ser posterior a 'hasta'.",
        )

    estados_validos = {"CONFIRMADA", "REALIZADA", "CANCELADA"}
    if estado and estado.upper() not in estados_validos:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Estado no válido. Valores permitidos: CONFIRMADA, REALIZADA, CANCELADA.",
        )

    consulta = select(Reserva).options(
        joinedload(Reserva.servicio),
        joinedload(Reserva.cliente),
        joinedload(Reserva.trabajador),
    )

    if cliente:
        cadena = cliente.strip()
        tel_limpio = cadena.replace(" ", "").replace("-", "")
        consulta = consulta.join(Reserva.cliente).where(
            or_(
                Cliente.nombre_artistico.ilike(f"%{cadena}%"),
                Cliente.nombre_completo.ilike(f"%{cadena}%"),
                Cliente.telefono.contains(tel_limpio),
            )
        )

    if desde:
        apertura_desde, _ = reglas.rango_jornada(desde)
        consulta = consulta.where(Reserva.inicio >= apertura_desde)

    if hasta:
        _, cierre_hasta = reglas.rango_jornada(hasta)
        consulta = consulta.where(Reserva.inicio < cierre_hasta)

    if estado:
        consulta = consulta.where(Reserva.estado == estado.upper())

    consulta = consulta.order_by(Reserva.inicio.desc())
    reservas = db.scalars(consulta).all()

    return [_a_salida_reserva(r) for r in reservas]


@router.get(
    "/agenda/clientes",
    response_model=list[ClienteBusquedaItemOut],
    summary="Buscador de clientes con cuenta (pantalla E-03)",
    responses={401: {"model": MensajeOut, "description": "Falta token de trabajador o no es válido"}},
)
def buscar_clientes(
    q: str = Query(description="Nombre artístico, nombre o teléfono", examples=["Marta"]),
    trabajador: Trabajador = Depends(get_trabajador_actual),
    db: Session = Depends(get_db),
):
    cadena = q.strip()
    tel_limpio = cadena.replace(" ", "").replace("-", "")

    consulta = (
        select(Cliente)
        .where(
            or_(
                Cliente.nombre_artistico.ilike(f"%{cadena}%"),
                Cliente.nombre_completo.ilike(f"%{cadena}%"),
                Cliente.telefono.contains(tel_limpio),
            )
        )
        .order_by(Cliente.nombre_artistico.asc())
    )
    clientes = db.scalars(consulta).all()
    return clientes
