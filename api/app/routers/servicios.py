"""
Catálogo de servicios · Responsable: Pol

  GET   /api/servicios                     Servicios visibles en la app     200
  GET   /api/servicios/gestion             Todos (también desactivados)     200 · 401
  GET   /api/servicios/{id}                Detalle de un servicio activo    200 · 404
  POST  /api/servicios                     Crear servicio                   201 · 400 · 401 · 409
  PUT   /api/servicios/{id}                Editar todos los campos          200 · 400 · 401 · 404 · 409
  PATCH /api/servicios/{id}/visibilidad    Activar o desactivar en la app   200 · 400 · 401 · 404

No hay DELETE a propósito: los servicios no se borran, se desactivan
(borrarlos rompería el historial de reservas y la base de datos lo impide con RESTRICT).

Cambiar el precio de un servicio no cambia las reservas ya hechas: cada reserva guarda su precio.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Servicio, Trabajador
from ..schemas.servicios import MensajeOut, ServicioIn, ServicioOut, VisibilidadIn
from ..security import get_trabajador_actual

router = APIRouter(prefix="/api/servicios", tags=["Servicios"])


# ---------------------------------------------------------------- ayudas
def _buscar(db: Session, id_servicio: int) -> Servicio:
    """Devuelve el servicio o lanza 404."""
    servicio = db.get(Servicio, id_servicio)
    if servicio is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ese servicio no existe.")
    return servicio


def _comprobar_nombre(db: Session, nombre: str, excepto_id: int | None = None) -> None:
    """409 si otro servicio ya se llama igual."""
    q = select(Servicio).where(Servicio.nombre == nombre)
    if excepto_id:
        q = q.where(Servicio.id_servicio != excepto_id)
    if db.scalar(q):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe un servicio con ese nombre.")


# ---------------------------------------------------------------- endpoints
@router.get(
    "",
    response_model=list[ServicioOut],
    summary="Servicios visibles en la app (pantalla M-03 Servicios)",
)
def listar_visibles(db: Session = Depends(get_db)):
    return db.scalars(
        select(Servicio).where(Servicio.activo_app.is_(True)).order_by(Servicio.id_servicio)
    ).all()


# /gestion tiene que ir antes que /{id_servicio}; si no, FastAPI intenta leer "gestion" como un id
@router.get(
    "/gestion",
    response_model=list[ServicioOut],
    summary="Todos los servicios, también los desactivados (pantalla E-05 Servicios)",
    responses={401: {"model": MensajeOut}},
)
def listar_gestion(
    trabajador: Trabajador = Depends(get_trabajador_actual),
    db: Session = Depends(get_db),
):
    return db.scalars(select(Servicio).order_by(Servicio.id_servicio)).all()


@router.get(
    "/{id_servicio}",
    response_model=ServicioOut,
    summary="Detalle de un servicio (pantalla M-04 Detalle del servicio)",
    responses={404: {"model": MensajeOut, "description": "No existe o está desactivado"}},
)
def ver_servicio(id_servicio: int, db: Session = Depends(get_db)):
    servicio = db.get(Servicio, id_servicio)
    if servicio is None or not servicio.activo_app:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ese servicio no existe o no está disponible.")
    return servicio


@router.post(
    "",
    response_model=ServicioOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear servicio (pantalla E-06 Crear servicio)",
    responses={
        400: {"model": MensajeOut, "description": "Datos no válidos (nombre, descripción, duración o precio)"},
        401: {"model": MensajeOut},
        409: {"model": MensajeOut, "description": "Nombre repetido"},
    },
)
def crear_servicio(
    datos: ServicioIn,
    trabajador: Trabajador = Depends(get_trabajador_actual),
    db: Session = Depends(get_db),
):
    _comprobar_nombre(db, datos.nombre)

    servicio = Servicio(
        nombre=datos.nombre,
        descripcion=datos.descripcion,
        duracion_min=datos.duracion_min,
        precio=datos.precio,
        activo_app=datos.activo_app,
    )
    db.add(servicio)
    db.commit()
    db.refresh(servicio)
    return servicio


@router.put(
    "/{id_servicio}",
    response_model=ServicioOut,
    summary="Editar servicio (pantalla E-06b Editar servicio)",
    responses={
        400: {"model": MensajeOut, "description": "Datos no válidos (nombre, descripción, duración o precio)"},
        401: {"model": MensajeOut},
        404: {"model": MensajeOut, "description": "El servicio no existe"},
        409: {"model": MensajeOut, "description": "Nombre repetido"},
    },
)
def editar_servicio(
    id_servicio: int,
    datos: ServicioIn,
    trabajador: Trabajador = Depends(get_trabajador_actual),
    db: Session = Depends(get_db),
):
    servicio = _buscar(db, id_servicio)
    _comprobar_nombre(db, datos.nombre, excepto_id=id_servicio)

    servicio.nombre = datos.nombre
    servicio.descripcion = datos.descripcion
    servicio.duracion_min = datos.duracion_min
    servicio.precio = datos.precio
    servicio.activo_app = datos.activo_app  # opcional, por defecto true
    db.commit()
    db.refresh(servicio)
    return servicio


@router.patch(
    "/{id_servicio}/visibilidad",
    response_model=ServicioOut,
    summary="Activar o desactivar «Visible en la app» (pantallas E-05 y E-06b)",
    responses={
        400: {"model": MensajeOut, "description": "Falta activo_app o no es true/false"},
        401: {"model": MensajeOut},
        404: {"model": MensajeOut, "description": "El servicio no existe"},
    },
)
def cambiar_visibilidad(
    id_servicio: int,
    datos: VisibilidadIn,
    trabajador: Trabajador = Depends(get_trabajador_actual),
    db: Session = Depends(get_db),
):
    servicio = _buscar(db, id_servicio)
    servicio.activo_app = datos.activo_app
    db.commit()
    db.refresh(servicio)
    return servicio
