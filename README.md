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
2. Clona el repo:
   ```
   git clone https://github.com/urion-sertor/L808.git
   cd L808
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
5. **Crear la base de datos.** Con MySQL arrancado en XAMPP, abre phpMyAdmin (botón *Admin* de MySQL) → pestaña **Importar** → elige `database/l808.sql` → **Importar**. Se crea la base de datos `l808` con todas las tablas y los datos de prueba. Puedes repetirlo cuando quieras: borra y vuelve a crear todo.
6. **Arrancar la API** (desde la carpeta `api`, con el venv activado):
   ```
   cd api
   uvicorn app.main:app --reload
   ```
7. Abre **http://127.0.0.1:8000/docs**: es la documentación interactiva (Swagger), desde donde se puede probar cada endpoint.

### Cuentas de prueba

| Tipo | Usuario | Contraseña |
|---|---|---|
| Cliente (móvil) | `djgroma@gmail.com`, `mckroma@gmail.com`, `ivanmartin@gmail.com`, `martaruiz@gmail.com` | `cabina808` |
| Trabajador (escritorio) | `dani.recepcion` (encargado), `laia.recepcion` (recepción) | `recepcion808` |

### Estructura de la API

```
api/app/
├── main.py          Arranque: carga sola todos los routers
├── config.py        Lee el .env (conexión, token, horario 19:00–04:00)
├── database.py      Conexión a MySQL
├── models.py        Una clase por tabla
├── security.py      Contraseñas (bcrypt) y tokens (JWT) de cliente y de trabajador
├── errores.py       Formato común de errores (400, 401, 404, 409)
├── schemas/         Formatos JSON de entrada y salida
└── routers/         Endpoints, un archivo por persona
    ├── clientes.py    Enrique · registro, login, perfil
    ├── reservas.py    Adrián  · reservas del móvil
    ├── agenda.py      Oriol   · agenda del escritorio
    └── servicios.py   Pol     · catálogo de servicios
```

## Forma de trabajar con Git

- `main`: solo lo que funciona.
- `enrique`, `adrian`, `oriol`, `pol`: una rama por persona, creada desde `main`. Cuando una parte funciona, se une a `main` con un pull request.
- Nunca se sube el archivo `.env` ni la carpeta `venv`.
