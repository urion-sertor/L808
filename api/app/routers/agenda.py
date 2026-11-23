"""
Agenda y trabajadores del escritorio · Responsable: Oriol

  POST  /api/trabajadores/login                     Login de trabajador          200 · 400 · 401
  GET   /api/trabajadores/me                        Ver perfil del trabajador    200 · 401
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Trabajador
from ..schemas.agenda import (
    LoginTrabajadorIn,
    MensajeOut,
    SesionTrabajadorOut,
    TrabajadorOut,
)
from ..security import crear_token, get_trabajador_actual, verificar_password

router = APIRouter(prefix="/api", tags=["Escritorio (trabajadores)"])


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
