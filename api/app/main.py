"""
Punto de entrada de la API de L808.

Arrancar (desde la carpeta api/, con el venv activado):
    uvicorn app.main:app --reload

Documentación interactiva (Swagger): http://127.0.0.1:8000/docs
"""
import importlib
import pkgutil

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from . import config, routers
from .database import get_db
from .errores import registrar_manejadores

app = FastAPI(
    title="API L808",
    description=(
        "API REST del estudio de freestyle L808. "
        "La usan la app móvil (clientes) y la app de escritorio (trabajadores), "
        "que comparten la misma agenda."
    ),
    version="1.0.0",
)

# Las apps (Android y escritorio) llaman desde otro origen
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

registrar_manejadores(app)

# Fotos de avatar subidas por los clientes: http://127.0.0.1:8000/uploads/avatars/...
config.CARPETA_UPLOADS.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=config.CARPETA_UPLOADS), name="uploads")

# Carga automática: cada archivo de app/routers con una variable `router`
for modulo in pkgutil.iter_modules(routers.__path__):
    mod = importlib.import_module(f"{routers.__name__}.{modulo.name}")
    if hasattr(mod, "router"):
        app.include_router(mod.router)


@app.get("/api/salud", tags=["Sistema"], summary="Comprobar que la API y la base de datos responden")
def salud(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"estado": "ok", "base_de_datos": "ok"}
