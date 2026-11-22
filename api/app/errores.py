"""
Respuestas de error con el mismo formato en toda la API:

    {"detail": "Mensaje para mostrar al usuario"}

y, en los errores de validación, además la lista de campos con problemas:

    {"detail": "Datos no válidos", "errores": [{"campo": "email", "mensaje": "..."}]}

Códigos que usamos: 400, 401, 404, 409 (y 503 si la base de datos no responde).
"""
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError


def _traducir(e: dict) -> str:
    """Pasa al castellano los mensajes de validación más habituales."""
    tipo, ctx = e.get("type", ""), e.get("ctx") or {}
    if tipo == "missing":
        return "Campo obligatorio"
    if tipo == "string_too_short":
        return f"Mínimo {ctx.get('min_length')} caracteres"
    if tipo == "string_too_long":
        return f"Máximo {ctx.get('max_length')} caracteres"
    if tipo == "string_pattern_mismatch":
        return "Formato no válido"
    if tipo in ("int_parsing", "int_type"):
        return "Tiene que ser un número entero"
    if tipo in ("decimal_parsing", "float_parsing", "decimal_type"):
        return "Tiene que ser un número"
    if tipo in ("datetime_parsing", "datetime_from_date_parsing", "datetime_type"):
        return "Fecha y hora no válidas (formato AAAA-MM-DDTHH:MM)"
    if tipo in ("date_parsing", "date_from_datetime_parsing"):
        return "Fecha no válida (formato AAAA-MM-DD)"
    if tipo == "literal_error" or tipo == "enum":
        return f"Valor no permitido. Opciones: {ctx.get('expected')}"
    if tipo in ("greater_than", "greater_than_equal"):
        return f"Tiene que ser mayor que {ctx.get('gt', ctx.get('ge'))}"
    if tipo == "json_invalid":
        return "El JSON está mal escrito"
    if tipo == "value_error":
        msg = str(e.get("msg", ""))
        if "email" in msg.lower():
            return "Email no válido"
        return msg.replace("Value error, ", "")
    return e.get("msg", "Valor no válido")


def registrar_manejadores(app: FastAPI) -> None:

    @app.exception_handler(RequestValidationError)
    async def datos_no_validos(request: Request, exc: RequestValidationError):
        errores = []
        for e in exc.errors():
            campo = ".".join(str(p) for p in e.get("loc", []) if p not in ("body", "query", "path"))
            errores.append({"campo": campo or "body", "mensaje": _traducir(e)})
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "Datos no válidos", "errores": errores},
        )

    @app.exception_handler(IntegrityError)
    async def conflicto_bd(request: Request, exc: IntegrityError):
        mensaje = str(exc.orig)
        if "Franja ocupada" in mensaje:
            return JSONResponse(status.HTTP_409_CONFLICT, {"detail": "Estudio lleno: esa franja ya está reservada."})
        if "Duplicate entry" in mensaje:
            return JSONResponse(status.HTTP_409_CONFLICT, {"detail": "Ese dato ya existe y no se puede repetir."})
        if "foreign key" in mensaje.lower():
            return JSONResponse(status.HTTP_409_CONFLICT, {"detail": "No se puede: hay datos relacionados."})
        return JSONResponse(status.HTTP_400_BAD_REQUEST, {"detail": "Los datos no cumplen las reglas de la base de datos."})

    @app.exception_handler(OperationalError)
    async def bd_caida(request: Request, exc: OperationalError):
        mensaje = str(exc.orig)
        if "Franja ocupada" in mensaje:  # el trigger de MariaDB a veces llega como OperationalError
            return JSONResponse(status.HTTP_409_CONFLICT, {"detail": "Estudio lleno: esa franja ya está reservada."})
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "No hay conexión con la base de datos. ¿Está MySQL arrancado en XAMPP?"},
        )
