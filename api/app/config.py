"""Configuración leída del archivo .env de la raíz del repo."""
import os
from pathlib import Path

from dotenv import load_dotenv

RAIZ_REPO = Path(__file__).resolve().parents[2]
load_dotenv(RAIZ_REPO / ".env")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "l808")

JWT_SECRET = os.getenv("JWT_SECRET", "cambia_esto_por_una_frase_larga_y_secreta")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MIN = int(os.getenv("JWT_EXPIRE_MIN", "120"))

# Carpeta donde se guardan las fotos de avatar (se sirven en /uploads)
CARPETA_UPLOADS = Path(__file__).resolve().parents[1] / "uploads"

# Horario del estudio: abre a las 19:00 y cierra a las 04:00 del día
# siguiente, de lunes a sábado (lunes = 0 ... domingo = 6).
HORA_APERTURA = 19
HORA_CIERRE = 4
DIAS_ABIERTO = {0, 1, 2, 3, 4, 5}
