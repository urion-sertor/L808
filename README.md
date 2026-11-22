# L808 · Sistema de reservas

Proyecto guiado de 2º DAM (Monlau) · Sprint 2: base de datos y API REST.

L808 es un estudio de grabación de freestyle con una sola cabina. El sistema tiene dos aplicaciones que comparten la misma agenda:

- **App móvil (Android):** para los clientes. Se registran, ven los servicios y reservan.
- **App de escritorio:** para los trabajadores. Gestionan la agenda, las reservas por teléfono o presenciales y los servicios.

Equipo: Adrián, Enrique, Oriol y Pol.

## Tecnologías

| Pieza | Herramienta |
|---|---|
| Base de datos | MySQL / MariaDB (XAMPP) |
| API | Python + FastAPI + Uvicorn |
| Conexión a la BD | SQLAlchemy + PyMySQL |
| Contraseñas | bcrypt |
| Login | JWT (PyJWT) |
| Pruebas | Postman |

## Estructura

```
api/        Código de la API
database/   Scripts .sql (tablas y datos de prueba)
postman/    Colección de Postman exportada
docs/       Memoria técnica y diagrama ER
```

## Puesta en marcha

Requisitos: Python 3.11 o superior, Git y XAMPP.

1. Arranca **MySQL** en el XAMPP Control Panel.
2. Clona el repo y entra en la rama `develop`:
   ```
   git clone https://github.com/urion-sertor/L808.git
   cd L808
   git checkout develop
   ```
3. Crea y activa el entorno virtual e instala las dependencias:
   ```
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```
4. Crea tu configuración local:
   ```
   copy .env.example .env
   ```
5. Base de datos y arranque de la API: se completará en cuanto estén listos.

## Forma de trabajar con Git

- `main`: solo versiones que funcionan.
- `develop`: donde se junta el trabajo del equipo.
- Una rama por tarea, creada desde `develop` (por ejemplo `feature/bd`, `feature/auth`), que se une a `develop` con un pull request.
- Nunca se sube el archivo `.env` ni la carpeta `venv`.
