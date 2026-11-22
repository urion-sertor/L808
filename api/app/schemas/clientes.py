"""Formatos JSON de entrada y salida de los endpoints de clientes (Enrique)."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

PATRON_COLOR = r"^#[0-9A-Fa-f]{6}$"
PATRON_TELEFONO = r"^\+?[0-9]{9,15}$"


def _limpiar_telefono(valor: Optional[str]) -> Optional[str]:
    if valor is None:
        return None
    valor = valor.replace(" ", "").replace("-", "")
    return valor or None


# ---------------------------------------------------------------- entrada
class RegistroIn(BaseModel):
    nombre_artistico: str = Field(min_length=2, max_length=50, examples=["Dj Groma"])
    email: EmailStr = Field(examples=["djgroma@gmail.com"])
    telefono: Optional[str] = Field(default=None, examples=["670777808"])
    password: str = Field(min_length=8, max_length=72, examples=["cabina808"])

    _tel = field_validator("telefono", mode="before")(_limpiar_telefono)

    @field_validator("telefono")
    @classmethod
    def telefono_valido(cls, v):
        import re
        if v is not None and not re.fullmatch(PATRON_TELEFONO, v):
            raise ValueError("Teléfono no válido (9 a 15 cifras)")
        return v

    @field_validator("nombre_artistico")
    @classmethod
    def sin_espacios_sobrantes(cls, v: str) -> str:
        return " ".join(v.split())


class LoginIn(BaseModel):
    email: EmailStr = Field(examples=["djgroma@gmail.com"])
    password: str = Field(min_length=1, examples=["cabina808"])


class PerfilUpdateIn(BaseModel):
    """Todos los campos son opcionales: se cambia solo lo que se envía."""
    nombre_artistico: Optional[str] = Field(default=None, min_length=2, max_length=50)
    nombre_completo: Optional[str] = Field(default=None, max_length=100, examples=["Guillem Rodríguez"])
    email: Optional[EmailStr] = None
    telefono: Optional[str] = None
    avatar_color: Optional[str] = Field(default=None, pattern=PATRON_COLOR, examples=["#7AA7FF"])

    _tel = field_validator("telefono", mode="before")(_limpiar_telefono)

    @field_validator("telefono")
    @classmethod
    def telefono_valido(cls, v):
        import re
        if v is not None and not re.fullmatch(PATRON_TELEFONO, v):
            raise ValueError("Teléfono no válido (9 a 15 cifras)")
        return v


class PasswordIn(BaseModel):
    password_actual: str = Field(min_length=1, examples=["cabina808"])
    password_nueva: str = Field(min_length=8, max_length=72, examples=["nuevaClave808"])


# ---------------------------------------------------------------- salida
class ClienteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_cliente: int
    nombre_artistico: str
    nombre_completo: Optional[str]
    email: str
    telefono: Optional[str]
    avatar_color: str
    avatar_url: Optional[str]
    fecha_registro: datetime
    sesiones_hechas: int = 0


class SesionOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    cliente: ClienteOut


class MensajeOut(BaseModel):
    detail: str
