"""
Agenda y trabajadores del escritorio · Responsable: Oriol

  POST  /api/trabajadores/login                     Login de trabajador              200 · 400 · 401
  GET   /api/trabajadores/me                        Ver perfil del trabajador        200 · 401
  GET   /api/agenda                                 Reservas del día                 200 · 400 · 401
  GET   /api/agenda/buscar                          Buscar reservas                  200 · 400 · 401
  GET   /api/agenda/clientes                        Buscador de clientes             200 · 401
  POST  /api/agenda/reservas                        Crear reserva de escritorio      201 · 400 · 401 · 404 · 409
  PATCH /api/agenda/reservas/{codigo}/realizada     Marcar reserva realizada         200 · 400 · 401 · 404 · 409
  PATCH /api/agenda/reservas/{codigo}/cancelar      Cancelar reserva                 200 · 401 · 404 · 409
"""
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from .. import config, reglas
from ..database import get_db
from ..models import Cliente, Reserva, Servicio, Trabajador
from ..schemas.agenda import (
    AgendaDiaOut,
    AgendaReservaOut,
    ClienteAgendaOut,
    ClienteBusquedaItemOut,
    LoginTrabajadorIn,
    MensajeOut,
    ReservaEscritorioCreateIn,
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


def _buscar_reserva_por_codigo(db: Session, codigo: str) -> Reserva:
    """Busca una reserva por su código con relaciones cargadas; si no existe, 404."""
    codigo_limpio = codigo.strip().upper()
    reserva = db.scalar(
        select(Reserva)
        .options(
            joinedload(Reserva.servicio),
            joinedload(Reserva.cliente),
            joinedload(Reserva.trabajador),
        )
        .where(Reserva.codigo_reserva == codigo_limpio)
    )
    if reserva is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reserva no encontrada.")
    return reserva


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


# ---------------------------------------------------------------- gestión de reservas
@router.post(
    "/agenda/reservas",
    response_model=AgendaReservaOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear reserva por teléfono o presencial desde el escritorio (pantalla E-03)",
    responses={
        400: {"model": MensajeOut, "description": "Origen no válido, datos contradictorios o fuera de horario"},
        401: {"model": MensajeOut, "description": "Falta token de trabajador o no es válido"},
        404: {"model": MensajeOut, "description": "Cliente no encontrado o servicio inexistente"},
        409: {"model": MensajeOut, "description": "Estudio lleno (solape de reserva)"},
    },
)
def crear_reserva_escritorio(
    datos: ReservaEscritorioCreateIn,
    trabajador: Trabajador = Depends(get_trabajador_actual),
    db: Session = Depends(get_db),
):
    # Validar que se envíe exclusivamente teléfono o id_cliente
    tiene_telefono = bool(datos.telefono and datos.telefono.strip())
    tiene_id_cliente = datos.id_cliente is not None

    if (tiene_telefono and tiene_id_cliente) or (not tiene_telefono and not tiene_id_cliente):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Debes indicar o bien el teléfono o bien el id del cliente, pero no ambos ni ninguno.",
        )

    if datos.origen not in ("TELEFONO", "PRESENCIAL"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "El origen de la reserva de escritorio solo puede ser TELEFONO o PRESENCIAL.",
        )

    # Localizar al cliente
    if tiene_telefono:
        tel_limpio = datos.telefono.replace(" ", "").replace("-", "")
        cliente = db.scalar(
            select(Cliente).where(
                func.replace(func.replace(Cliente.telefono, " ", ""), "-", "") == tel_limpio
            )
        )
    else:
        cliente = db.get(Cliente, datos.id_cliente)

    if cliente is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Ese cliente no tiene cuenta. Pídele que se registre en la app.",
        )

    servicio = db.get(Servicio, datos.id_servicio)
    if servicio is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El servicio no existe.")

    reserva = reglas.crear_reserva(
        db=db,
        cliente=cliente,
        servicio=servicio,
        inicio=datos.inicio,
        origen=datos.origen,
        trabajador=trabajador,
    )

    db.refresh(reserva)
    return _a_salida_reserva(reserva)


@router.patch(
    "/agenda/reservas/{codigo}/realizada",
    response_model=AgendaReservaOut,
    summary="Marcar reserva confirmada como realizada (pantalla E-02)",
    responses={
        400: {"model": MensajeOut, "description": "La reserva aún no ha empezado"},
        401: {"model": MensajeOut, "description": "Falta token de trabajador o no es válido"},
        404: {"model": MensajeOut, "description": "Reserva no encontrada"},
        409: {"model": MensajeOut, "description": "La reserva no está confirmada"},
    },
)
def marcar_reserva_realizada(
    codigo: str,
    trabajador: Trabajador = Depends(get_trabajador_actual),
    db: Session = Depends(get_db),
):
    reserva = _buscar_reserva_por_codigo(db, codigo)

    if reserva.estado != "CONFIRMADA":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "La reserva no está confirmada.",
        )

    if reserva.inicio > datetime.now():
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "No se puede marcar como realizada una reserva que aún no ha empezado.",
        )

    reserva.estado = "REALIZADA"
    db.commit()
    db.refresh(reserva)
    return _a_salida_reserva(reserva)


@router.patch(
    "/agenda/reservas/{codigo}/cancelar",
    response_model=AgendaReservaOut,
    summary="Cancelar una reserva confirmada desde el escritorio (pantallas E-02 y E-04)",
    responses={
        401: {"model": MensajeOut, "description": "Falta token de trabajador o no es válido"},
        404: {"model": MensajeOut, "description": "Reserva no encontrada"},
        409: {"model": MensajeOut, "description": "Esta reserva ya no se puede cancelar"},
    },
)
def cancelar_reserva_escritorio(
    codigo: str,
    trabajador: Trabajador = Depends(get_trabajador_actual),
    db: Session = Depends(get_db),
):
    reserva = _buscar_reserva_por_codigo(db, codigo)

    if reserva.estado != "CONFIRMADA":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Esta reserva ya no se puede cancelar.",
        )

    reserva.estado = "CANCELADA"
    db.commit()
    db.refresh(reserva)
    return _a_salida_reserva(reserva)
