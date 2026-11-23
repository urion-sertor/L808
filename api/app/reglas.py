"""
Reglas comunes de reservas · Responsable: Adrián

Lógica compartida entre la app móvil (reservas.py) y el escritorio (agenda.py):
  - Horario de apertura: lunes a sábado de 19:00 a 04:00 del día siguiente
  - Jornada nocturna: de 00:00 a 04:00 pertenece al día anterior
  - Control de solapes con bloqueo de fila (.with_for_update()) -> 409 Estudio lleno
  - Generación correlativa de códigos (L808-A001, L808-A002...)
"""
from datetime import date, datetime, time, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import config
from .models import Cliente, Reserva, Servicio, Trabajador

MENSAJE_FUERA_HORARIO = "Fuera de horario: el estudio abre de lunes a sábado de 19:00 a 04:00."


def _sin_zona_horaria(momento: datetime) -> datetime:
    """Convierte a datetime naive si llega con zona horaria (ej. acabado en Z)."""
    if momento.tzinfo is not None:
        return momento.replace(tzinfo=None)
    return momento


# ---------------------------------------------------------------- jornada y horario
def rango_jornada(fecha: date) -> tuple[datetime, datetime]:
    """Devuelve (fecha 19:00:00, fecha+1 04:00:00)."""
    apertura = datetime.combine(fecha, time(config.HORA_APERTURA, 0))
    cierre = datetime.combine(fecha + timedelta(days=1), time(config.HORA_CIERRE, 0))
    return apertura, cierre


def jornada_de(momento: datetime) -> date:
    """Si la hora es menor que 19:00, pertenece a la noche del día anterior."""
    momento = _sin_zona_horaria(momento)
    if momento.hour < config.HORA_APERTURA:
        return (momento - timedelta(days=1)).date()
    return momento.date()


def validar_horario(inicio: datetime, fin: datetime) -> None:
    """
    Comprueba las reglas 1, 2 y 3:
      - Horas de inicio en punto o y media, con segundos a 0.
      - Jornada de lunes a sábado.
      - Inicio y fin completos dentro de [19:00, 04:00 del día siguiente].
    """
    inicio = _sin_zona_horaria(inicio)
    fin = _sin_zona_horaria(fin)

    if fin <= inicio:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, MENSAJE_FUERA_HORARIO)

    if inicio.minute not in (0, 30) or inicio.second != 0 or inicio.microsecond != 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, MENSAJE_FUERA_HORARIO)

    jornada = jornada_de(inicio)
    if jornada.weekday() not in config.DIAS_ABIERTO:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, MENSAJE_FUERA_HORARIO)

    apertura, cierre = rango_jornada(jornada)
    if inicio < apertura or fin > cierre:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, MENSAJE_FUERA_HORARIO)


def validar_futuro(inicio: datetime) -> None:
    """Regla 4: no se permite reservar en una fecha u hora que ya ha pasado."""
    inicio = _sin_zona_horaria(inicio)
    if inicio <= datetime.now():
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "No se puede reservar en una fecha u hora que ya ha pasado.",
        )


# ---------------------------------------------------------------- solapes y códigos
def buscar_solape(
    db: Session,
    inicio: datetime,
    fin: datetime,
    excluir_id: int | None = None,
) -> Reserva | None:
    """
    Regla 5: devuelve la reserva activa que choca o None.
    Usa .with_for_update() para bloquear filas mientras se comprueba.
    """
    inicio = _sin_zona_horaria(inicio)
    fin = _sin_zona_horaria(fin)

    consulta = (
        select(Reserva)
        .where(
            Reserva.estado != "CANCELADA",
            Reserva.inicio < fin,
            Reserva.fin > inicio,
        )
        .with_for_update()
    )
    if excluir_id is not None:
        consulta = consulta.where(Reserva.id_reserva != excluir_id)

    return db.scalars(consulta).first()


def generar_codigo(db: Session) -> str:
    """Regla 8: genera L808-AXXX sumando 1 al mayor número existente."""
    codigos = db.scalars(
        select(Reserva.codigo_reserva).where(Reserva.codigo_reserva.like("L808-A%"))
    ).all()

    mayor = 0
    for codigo in codigos:
        sufijo = codigo.removeprefix("L808-A")
        if sufijo.isdigit():
            mayor = max(mayor, int(sufijo))

    return f"L808-A{mayor + 1:03d}"


# ---------------------------------------------------------------- disponibilidad y creación
def franjas_del_dia(db: Session, fecha: date, duracion_min: int) -> list[dict]:
    """
    Lista las franjas cada 30 min de esa jornada para un servicio de `duracion_min`,
    indicando `libre: true/false` (ocupada o ya pasada = false).
    """
    if fecha.weekday() not in config.DIAS_ABIERTO:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, MENSAJE_FUERA_HORARIO)

    apertura, cierre = rango_jornada(fecha)
    duracion = timedelta(minutes=duracion_min)
    ahora = datetime.now()

    reservas_jornada = db.scalars(
        select(Reserva).where(
            Reserva.estado != "CANCELADA",
            Reserva.inicio < cierre,
            Reserva.fin > apertura,
        )
    ).all()

    franjas: list[dict] = []
    actual = apertura
    while actual + duracion <= cierre:
        fin_franja = actual + duracion
        ocupada = any(actual < r.fin and fin_franja > r.inicio for r in reservas_jornada)
        libre = (actual > ahora) and not ocupada
        franjas.append(
            {
                "inicio": actual,
                "fin": fin_franja,
                "libre": libre,
            }
        )
        actual += timedelta(minutes=30)

    return franjas


def crear_reserva(
    db: Session,
    cliente: Cliente,
    servicio: Servicio,
    inicio: datetime,
    origen: str,
    trabajador: Trabajador | None = None,
) -> Reserva:
    """Valida todas las reglas de negocio, calcula fin/precio/código y guarda la reserva."""
    inicio = _sin_zona_horaria(inicio)

    # Regla 6: servicio activo
    if not servicio.activo_app:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Este servicio no está disponible para reservar.",
        )

    # Regla 9: coherencia entre origen y trabajador
    if origen == "APP" and trabajador is not None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Una reserva desde la app no puede tener trabajador asignado.",
        )
    if origen in ("TELEFONO", "PRESENCIAL") and trabajador is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Las reservas por teléfono o presenciales requieren un trabajador.",
        )
    if origen not in ("APP", "TELEFONO", "PRESENCIAL"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Origen de reserva no válido.")

    # Regla 7: cálculo de hora de fin
    fin = inicio + timedelta(minutes=servicio.duracion_min)

    # Reglas 1, 2, 3 y 4: horario y fecha futura
    validar_horario(inicio, fin)
    validar_futuro(inicio)

    # Regla 5: control de solapes con bloqueo
    solape = buscar_solape(db, inicio, fin)
    if solape is not None:
        hora_txt = inicio.strftime("%H:%M")
        if origen == "APP":
            detalle = f"Estudio lleno. A las {hora_txt} la cabina ya está reservada. Elige otra hora."
        else:
            artista = solape.cliente.nombre_artistico if solape.cliente else "otro cliente"
            detalle = (
                f"Estudio lleno. A las {hora_txt} la cabina ya está reservada "
                f"por {artista}. Elige otra hora."
            )
        raise HTTPException(status.HTTP_409_CONFLICT, detalle)

    # Reglas 7 y 8: precio congelado y código correlativo
    reserva = Reserva(
        codigo_reserva=generar_codigo(db),
        id_cliente=cliente.id_cliente,
        id_servicio=servicio.id_servicio,
        id_trabajador_registro=trabajador.id_trabajador if trabajador else None,
        inicio=inicio,
        fin=fin,
        precio=servicio.precio,
        origen=origen,
        estado="CONFIRMADA",
    )
    db.add(reserva)
    db.commit()
    db.refresh(reserva)
    return reserva