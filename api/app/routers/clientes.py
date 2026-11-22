"""
Clientes de la app móvil · Responsable: Enrique

  POST  /api/clientes/registro      Crear cuenta            201 · 400 · 409
  POST  /api/clientes/login         Iniciar sesión          200 · 400 · 401
  GET   /api/clientes/me            Ver mi perfil           200 · 401
  PATCH /api/clientes/me            Editar datos y avatar   200 · 400 · 401 · 409
  PUT   /api/clientes/me/avatar     Subir foto de avatar    200 · 400 · 401
  DELETE /api/clientes/me/avatar    Quitar la foto          200 · 401
  PUT   /api/clientes/me/password   Cambiar contraseña      200 · 400 · 401
"""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import config
from ..database import get_db
from ..models import Cliente, Reserva
from ..schemas.clientes import (
    ClienteOut,
    LoginIn,
    MensajeOut,
    PasswordIn,
    PerfilUpdateIn,
    RegistroIn,
    SesionOut,
)
from ..security import crear_token, get_cliente_actual, hashear_password, verificar_password

router = APIRouter(prefix="/api/clientes", tags=["Clientes (móvil)"])


# ---------------------------------------------------------------- ayudas
FORMATOS_FOTO = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
TAMANO_MAX_FOTO = 2 * 1024 * 1024  # 2 MB
CARPETA_AVATARES = config.CARPETA_UPLOADS / "avatars"


def _a_salida(db: Session, cliente: Cliente) -> ClienteOut:
    """Datos del perfil + sesiones hechas (las REALIZADAS), como en la pantalla Perfil."""
    total = db.scalar(
        select(func.count()).select_from(Reserva).where(
            Reserva.id_cliente == cliente.id_cliente,
            Reserva.estado == "REALIZADA",
        )
    )
    salida = ClienteOut.model_validate(cliente)
    salida.sesiones_hechas = total or 0
    return salida


def _borrar_foto(cliente: Cliente) -> None:
    for archivo in CARPETA_AVATARES.glob(f"cliente_{cliente.id_cliente}.*"):
        archivo.unlink(missing_ok=True)
    cliente.avatar_url = None


def _comprobar_duplicados(db: Session, email: str | None, nombre_artistico: str | None, excepto_id: int | None = None):
    """409 si el email o el nombre artístico ya los usa otra cuenta."""
    if email is not None:
        q = select(Cliente).where(Cliente.email == email)
        if excepto_id:
            q = q.where(Cliente.id_cliente != excepto_id)
        if db.scalar(q):
            raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe una cuenta con ese email.")
    if nombre_artistico is not None:
        q = select(Cliente).where(Cliente.nombre_artistico == nombre_artistico)
        if excepto_id:
            q = q.where(Cliente.id_cliente != excepto_id)
        if db.scalar(q):
            raise HTTPException(status.HTTP_409_CONFLICT, "Ese nombre artístico ya está cogido.")


# ---------------------------------------------------------------- endpoints
@router.post(
    "/registro",
    response_model=SesionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear cuenta de cliente (pantalla Crea tu cuenta)",
    responses={409: {"model": MensajeOut, "description": "Email o nombre artístico repetido"}},
)
def registrar(datos: RegistroIn, db: Session = Depends(get_db)):
    email = datos.email.lower()
    _comprobar_duplicados(db, email, datos.nombre_artistico)

    cliente = Cliente(
        nombre_artistico=datos.nombre_artistico,
        email=email,
        telefono=datos.telefono,
        password_hash=hashear_password(datos.password),
    )
    db.add(cliente)
    db.commit()
    db.refresh(cliente)

    return SesionOut(access_token=crear_token(cliente.id_cliente, "cliente"), cliente=_a_salida(db, cliente))


@router.post(
    "/login",
    response_model=SesionOut,
    summary="Iniciar sesión (pantalla Entra en la cabina)",
    responses={401: {"model": MensajeOut, "description": "Email o contraseña incorrectos"}},
)
def login(datos: LoginIn, db: Session = Depends(get_db)):
    cliente = db.scalar(select(Cliente).where(Cliente.email == datos.email.lower()))
    if cliente is None or not verificar_password(datos.password, cliente.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email o contraseña incorrectos.")

    return SesionOut(access_token=crear_token(cliente.id_cliente, "cliente"), cliente=_a_salida(db, cliente))


@router.get(
    "/me",
    response_model=ClienteOut,
    summary="Ver mi perfil (pantalla Perfil)",
    responses={401: {"model": MensajeOut}},
)
def ver_perfil(cliente: Cliente = Depends(get_cliente_actual), db: Session = Depends(get_db)):
    return _a_salida(db, cliente)


@router.patch(
    "/me",
    response_model=ClienteOut,
    summary="Editar datos y avatar (pantalla Datos y avatar)",
    responses={401: {"model": MensajeOut}, 409: {"model": MensajeOut}},
)
def editar_perfil(
    datos: PerfilUpdateIn,
    cliente: Cliente = Depends(get_cliente_actual),
    db: Session = Depends(get_db),
):
    cambios = datos.model_dump(exclude_unset=True)
    if not cambios:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No has enviado ningún campo para cambiar.")

    if "email" in cambios and cambios["email"] is not None:
        cambios["email"] = cambios["email"].lower()
    if "nombre_artistico" in cambios and cambios["nombre_artistico"] is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El nombre artístico no puede quedar vacío.")
    if "email" in cambios and cambios["email"] is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El email no puede quedar vacío.")
    if "avatar_color" in cambios and cambios["avatar_color"] is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El color del avatar no puede quedar vacío.")

    _comprobar_duplicados(db, cambios.get("email"), cambios.get("nombre_artistico"), excepto_id=cliente.id_cliente)

    for campo, valor in cambios.items():
        if campo == "avatar_color":
            valor = valor.upper()
            _borrar_foto(cliente)  # "Sube una foto o elige un color": el color sustituye a la foto
        setattr(cliente, campo, valor)
    db.commit()
    db.refresh(cliente)
    return _a_salida(db, cliente)


@router.put(
    "/me/avatar",
    response_model=ClienteOut,
    summary="Subir foto de avatar (pantalla Datos y avatar)",
    responses={400: {"model": MensajeOut}, 401: {"model": MensajeOut}},
)
async def subir_avatar(
    foto: UploadFile = File(description="Imagen JPG, PNG o WEBP de 2 MB como máximo"),
    cliente: Cliente = Depends(get_cliente_actual),
    db: Session = Depends(get_db),
):
    extension = FORMATOS_FOTO.get(foto.content_type or "")
    if extension is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La foto tiene que ser JPG, PNG o WEBP.")
    contenido = await foto.read()
    if len(contenido) == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El archivo está vacío.")
    if len(contenido) > TAMANO_MAX_FOTO:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La foto no puede pesar más de 2 MB.")

    CARPETA_AVATARES.mkdir(parents=True, exist_ok=True)
    _borrar_foto(cliente)
    nombre = f"cliente_{cliente.id_cliente}.{extension}"
    (CARPETA_AVATARES / nombre).write_bytes(contenido)

    cliente.avatar_url = f"/uploads/avatars/{nombre}"
    db.commit()
    db.refresh(cliente)
    return _a_salida(db, cliente)


@router.delete(
    "/me/avatar",
    response_model=ClienteOut,
    summary="Quitar la foto y volver al color del avatar",
    responses={401: {"model": MensajeOut}},
)
def quitar_avatar(cliente: Cliente = Depends(get_cliente_actual), db: Session = Depends(get_db)):
    _borrar_foto(cliente)
    db.commit()
    db.refresh(cliente)
    return _a_salida(db, cliente)


@router.put(
    "/me/password",
    response_model=MensajeOut,
    summary="Cambiar contraseña (pantalla Cambiar contraseña)",
    responses={400: {"model": MensajeOut}, 401: {"model": MensajeOut}},
)
def cambiar_password(
    datos: PasswordIn,
    cliente: Cliente = Depends(get_cliente_actual),
    db: Session = Depends(get_db),
):
    if not verificar_password(datos.password_actual, cliente.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La contraseña actual no es correcta.")
    if datos.password_actual == datos.password_nueva:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La nueva contraseña tiene que ser distinta de la actual.")

    cliente.password_hash = hashear_password(datos.password_nueva)
    db.commit()
    return MensajeOut(detail="Contraseña cambiada.")
