"""
Contraseñas (bcrypt) y login con token (JWT).

Hay dos tipos de cuenta y cada token dice de cuál es:
  - "cliente"    → app móvil
  - "trabajador" → app de escritorio
Así un cliente no puede usar los endpoints del escritorio y al revés.
"""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from . import config
from .database import get_db
from .models import Cliente, Trabajador

esquema_bearer = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------- contraseñas
def hashear_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verificar_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


# ---------------------------------------------------------------- tokens
def crear_token(id_usuario: int, tipo: str) -> str:
    """tipo: 'cliente' o 'trabajador'."""
    ahora = datetime.now(timezone.utc)
    datos = {
        "sub": str(id_usuario),
        "tipo": tipo,
        "iat": ahora,
        "exp": ahora + timedelta(minutes=config.JWT_EXPIRE_MIN),
    }
    return jwt.encode(datos, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


def _leer_token(credenciales: HTTPAuthorizationCredentials | None, tipo_esperado: str) -> int:
    if credenciales is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Falta el token. Inicia sesión.")
    try:
        datos = jwt.decode(credenciales.credentials, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "La sesión ha caducado. Vuelve a iniciar sesión.")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token no válido.")
    if datos.get("tipo") != tipo_esperado:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Este endpoint necesita una sesión de {tipo_esperado}.")
    return int(datos["sub"])


# ---------------------------------------------------------------- dependencias
def get_cliente_actual(
    credenciales: HTTPAuthorizationCredentials | None = Depends(esquema_bearer),
    db: Session = Depends(get_db),
) -> Cliente:
    """Úsala en los endpoints del móvil: devuelve el cliente que ha iniciado sesión."""
    id_cliente = _leer_token(credenciales, "cliente")
    cliente = db.get(Cliente, id_cliente)
    if cliente is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "La cuenta ya no existe.")
    return cliente


def get_trabajador_actual(
    credenciales: HTTPAuthorizationCredentials | None = Depends(esquema_bearer),
    db: Session = Depends(get_db),
) -> Trabajador:
    """Úsala en los endpoints del escritorio: devuelve el trabajador que ha iniciado sesión."""
    id_trabajador = _leer_token(credenciales, "trabajador")
    trabajador = db.get(Trabajador, id_trabajador)
    if trabajador is None or not trabajador.activo:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Cuenta de trabajador no válida o desactivada.")
    return trabajador
