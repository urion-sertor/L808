"""Formatos JSON de entrada y salida de los endpoints de escritorio y agenda (Oriol)."""
from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------- entrada
class LoginTrabajadorIn(BaseModel):
    usuario: str = Field(min_length=1, examples=["dani.recepcion"])
    password: str = Field(min_length=1, examples=["recepcion808"])


# ---------------------------------------------------------------- salida
class TrabajadorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_trabajador: int
    nombre: str
    usuario: str
    rol: str


class SesionTrabajadorOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    trabajador: TrabajadorOut


class MensajeOut(BaseModel):
    detail: str
