"""Formatos JSON de entrada y salida de los endpoints de reservas del móvil (Adrián)."""
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------- entrada
class ReservaCreateIn(BaseModel):
    id_servicio: int = Field(gt=0, examples=[2])
    inicio: datetime = Field(examples=["2026-12-04T20:00:00"])


# ---------------------------------------------------------------- salida
class ServicioResumenOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_servicio: int
    nombre: str
    duracion_min: int


class ServicioDisponibilidadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_servicio: int
    nombre: str
    duracion_min: int
    precio: float


class FranjaOut(BaseModel):
    inicio: datetime
    fin: datetime
    libre: bool


class DisponibilidadOut(BaseModel):
    fecha: date
    servicio: ServicioDisponibilidadOut
    franjas: list[FranjaOut]


class ReservaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    codigo_reserva: str
    servicio: ServicioResumenOut
    inicio: datetime
    fin: datetime
    precio: float
    estado: str
    origen: str
    creada_en: datetime


class MensajeOut(BaseModel):
    detail: str