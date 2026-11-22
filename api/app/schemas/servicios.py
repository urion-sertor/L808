"""Formatos JSON de entrada y salida de los endpoints de servicios (Pol)."""
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

DURACIONES_PERMITIDAS = (30, 60, 120, 300)
PRECIO_MAXIMO = 9999.99  # la columna es DECIMAL(6,2)


# ---------------------------------------------------------------- entrada
class ServicioIn(BaseModel):
    """Crear (POST) o editar (PUT) un servicio. Los textos de error son los del Figma (E-06)."""
    nombre: str = Field(max_length=80, examples=["Sesión de mezcla"])
    descripcion: str = Field(max_length=255, examples=["Mezcla y master de un tema"])
    duracion_min: int = Field(examples=[60])
    precio: float = Field(examples=[30.0])
    activo_app: Optional[bool] = Field(default=None, examples=[True])

    @field_validator("nombre")
    @classmethod
    def nombre_obligatorio(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("El nombre es obligatorio")
        return v

    @field_validator("descripcion")
    @classmethod
    def descripcion_obligatoria(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("La descripción es obligatoria")
        return v

    @field_validator("duracion_min")
    @classmethod
    def duracion_permitida(cls, v: int) -> int:
        if v not in DURACIONES_PERMITIDAS:
            raise ValueError("Duración no permitida (30, 60, 120 o 300 minutos)")
        return v

    @field_validator("precio")
    @classmethod
    def precio_valido(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Tiene que ser mayor que 0")
        if v > PRECIO_MAXIMO:
            raise ValueError(f"El precio máximo es {PRECIO_MAXIMO}")
        return round(v, 2)


class VisibilidadIn(BaseModel):
    """Activar o desactivar «Visible en la app»."""
    activo_app: bool = Field(examples=[False])


# ---------------------------------------------------------------- salida
class ServicioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_servicio: int
    nombre: str
    descripcion: str
    duracion_min: int
    precio: float
    activo_app: bool


class MensajeOut(BaseModel):
    detail: str
