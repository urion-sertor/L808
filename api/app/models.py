"""
Modelos ORM: una clase por tabla de database/l808.sql.

Las tablas las crea el script SQL; estas clases solo sirven para leer y
escribir desde Python. Si cambiáis una columna, cambiadla en los dos sitios.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, SmallInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Cliente(Base):
    __tablename__ = "clientes"

    id_cliente: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre_artistico: Mapped[str] = mapped_column(String(50), unique=True)
    nombre_completo: Mapped[Optional[str]] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(100), unique=True)
    telefono: Mapped[Optional[str]] = mapped_column(String(20))
    password_hash: Mapped[str] = mapped_column(String(255))
    avatar_color: Mapped[str] = mapped_column(String(7), default="#12D3A0")
    avatar_url: Mapped[Optional[str]] = mapped_column(String(255))
    fecha_registro: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    reservas: Mapped[list["Reserva"]] = relationship(back_populates="cliente")


class Trabajador(Base):
    __tablename__ = "trabajadores"

    id_trabajador: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100))
    usuario: Mapped[str] = mapped_column(String(30), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    rol: Mapped[str] = mapped_column(Enum("ENCARGADO", "RECEPCION"), default="RECEPCION")
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class Servicio(Base):
    __tablename__ = "servicios"

    id_servicio: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(80), unique=True)
    descripcion: Mapped[str] = mapped_column(String(255))
    duracion_min: Mapped[int] = mapped_column(SmallInteger)
    precio: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    activo_app: Mapped[bool] = mapped_column(Boolean, default=True)


class Reserva(Base):
    __tablename__ = "reservas"

    id_reserva: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo_reserva: Mapped[str] = mapped_column(String(15), unique=True)
    id_cliente: Mapped[int] = mapped_column(ForeignKey("clientes.id_cliente"))
    id_servicio: Mapped[int] = mapped_column(ForeignKey("servicios.id_servicio"))
    id_trabajador_registro: Mapped[Optional[int]] = mapped_column(ForeignKey("trabajadores.id_trabajador"))
    inicio: Mapped[datetime] = mapped_column(DateTime)
    fin: Mapped[datetime] = mapped_column(DateTime)
    precio: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    origen: Mapped[str] = mapped_column(Enum("APP", "TELEFONO", "PRESENCIAL"))
    estado: Mapped[str] = mapped_column(Enum("CONFIRMADA", "REALIZADA", "CANCELADA"), default="CONFIRMADA")
    creada_en: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    cliente: Mapped[Cliente] = relationship(back_populates="reservas")
    servicio: Mapped[Servicio] = relationship()
    trabajador: Mapped[Optional[Trabajador]] = relationship()
