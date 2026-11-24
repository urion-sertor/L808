"""Formatos JSON de entrada y salida de los endpoints de escritorio y agenda (Oriol)."""
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------- entrada
class LoginTrabajadorIn(BaseModel):
    usuario: str = Field(min_length=1, examples=["dani.recepcion"])
    password: str = Field(min_length=1, examples=["recepcion808"])


class ReservaEscritorioCreateIn(BaseModel):
    id_servicio: int = Field(gt=0, examples=[1])
    inicio: datetime = Field(examples=["2026-12-05T19:00:00"])
    origen: str = Field(examples=["TELEFONO"])
    telefono: Optional[str] = Field(default=None, examples=["600 222 999"])
    id_cliente: Optional[int] = Field(default=None, examples=[4])


# ---------------------------------------------------------------- salida: perfil y login
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


# ---------------------------------------------------------------- salida: reservas y agenda
class ServicioAgendaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_servicio: int
    nombre: str
    duracion_min: int


class ClienteAgendaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_cliente: int
    nombre_artistico: str
    telefono: Optional[str] = None


class TrabajadorResumenOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_trabajador: int
    nombre: str


class AgendaReservaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    codigo_reserva: str
    inicio: datetime
    fin: datetime
    estado: str
    origen: str
    precio: float
    servicio: ServicioAgendaOut
    cliente: ClienteAgendaOut
    registrada_por: Optional[TrabajadorResumenOut] = None


class AgendaDiaOut(BaseModel):
    fecha: date
    reservas: list[AgendaReservaOut]


class ClienteBusquedaItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_cliente: int
    nombre_artistico: str
    nombre_completo: Optional[str] = None
    telefono: Optional[str] = None
    email: str


class MensajeOut(BaseModel):
    detail: str
