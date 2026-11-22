-- =====================================================================
--  L808 · Sistema de reservas del estudio de freestyle
--  Projecte guiat 2º DAM · Sprint 2 · Base de datos
--
--  Motor: MySQL 8 / MariaDB 10.11 (XAMPP)
--  Uso:   phpMyAdmin → Importar este archivo, o desde consola:
--         mysql -u root < database/l808.sql
--
--  El script es repetible: borra la base de datos y la vuelve a crear.
-- =====================================================================

SET NAMES utf8mb4;

DROP DATABASE IF EXISTS l808;
CREATE DATABASE l808 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE l808;


-- =====================================================================
--  1. DDL · TABLAS
-- =====================================================================

-- ---------------------------------------------------------------------
--  clientes: artistas que se registran desde la app móvil
-- ---------------------------------------------------------------------
CREATE TABLE clientes (
    id_cliente        INT UNSIGNED  NOT NULL AUTO_INCREMENT,
    nombre_artistico  VARCHAR(50)   NOT NULL,
    nombre_completo   VARCHAR(100)  NULL,          -- se pide en "Datos y avatar", no en el registro
    email             VARCHAR(100)  NOT NULL,
    telefono          VARCHAR(20)   NULL,
    password_hash     VARCHAR(255)  NOT NULL,
    avatar_color      CHAR(7)       NOT NULL DEFAULT '#12D3A0',
    avatar_url        VARCHAR(255)  NULL,          -- foto subida; si es NULL se usa el color
    fecha_registro    TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_clientes          PRIMARY KEY (id_cliente),
    CONSTRAINT uq_clientes_email    UNIQUE (email),
    CONSTRAINT uq_clientes_artista  UNIQUE (nombre_artistico),
    CONSTRAINT ck_clientes_color    CHECK (avatar_color REGEXP '^#[0-9A-Fa-f]{6}$')
) ENGINE = InnoDB;

-- ---------------------------------------------------------------------
--  trabajadores: personal de recepción. No se registran: las cuentas
--  las crea el negocio. Entran en la app de escritorio con su usuario.
-- ---------------------------------------------------------------------
CREATE TABLE trabajadores (
    id_trabajador   INT UNSIGNED  NOT NULL AUTO_INCREMENT,
    nombre          VARCHAR(100)  NOT NULL,
    usuario         VARCHAR(30)   NOT NULL,
    password_hash   VARCHAR(255)  NOT NULL,
    rol             ENUM('ENCARGADO', 'RECEPCION') NOT NULL DEFAULT 'RECEPCION',
    activo          BOOLEAN       NOT NULL DEFAULT TRUE,

    CONSTRAINT pk_trabajadores          PRIMARY KEY (id_trabajador),
    CONSTRAINT uq_trabajadores_usuario  UNIQUE (usuario)
) ENGINE = InnoDB;

-- ---------------------------------------------------------------------
--  servicios: catálogo que ve el móvil y que gestiona el escritorio.
--  Un servicio no se borra: se desactiva con activo_app = FALSE.
-- ---------------------------------------------------------------------
CREATE TABLE servicios (
    id_servicio   INT UNSIGNED   NOT NULL AUTO_INCREMENT,
    nombre        VARCHAR(80)    NOT NULL,
    descripcion   VARCHAR(255)   NOT NULL,
    duracion_min  SMALLINT UNSIGNED NOT NULL,
    precio        DECIMAL(6,2)   NOT NULL,
    activo_app    BOOLEAN        NOT NULL DEFAULT TRUE,

    CONSTRAINT pk_servicios         PRIMARY KEY (id_servicio),
    CONSTRAINT uq_servicios_nombre  UNIQUE (nombre),
    CONSTRAINT ck_servicios_duracion CHECK (duracion_min IN (30, 60, 120, 300)),
    CONSTRAINT ck_servicios_precio  CHECK (precio >= 0)
) ENGINE = InnoDB;

-- ---------------------------------------------------------------------
--  reservas: la agenda compartida entre las dos apps.
--  - Siempre hay un cliente con cuenta (id_cliente NOT NULL).
--  - id_trabajador_registro: quién la creó en el escritorio
--    ("Registrada por"). Es NULL cuando el cliente reserva desde la app.
--  - inicio y fin son DATETIME porque el estudio abre de noche
--    (19:00 a 04:00) y una sesión puede pasar de un día al siguiente.
--  - precio: se guarda el precio del momento de la reserva, para que
--    el historial no cambie si más adelante se modifica el servicio.
-- ---------------------------------------------------------------------
CREATE TABLE reservas (
    id_reserva              INT UNSIGNED  NOT NULL AUTO_INCREMENT,
    codigo_reserva          VARCHAR(15)   NOT NULL,
    id_cliente              INT UNSIGNED  NOT NULL,
    id_servicio             INT UNSIGNED  NOT NULL,
    id_trabajador_registro  INT UNSIGNED  NULL,
    inicio                  DATETIME      NOT NULL,
    fin                     DATETIME      NOT NULL,
    precio                  DECIMAL(6,2)  NOT NULL,
    origen                  ENUM('APP', 'TELEFONO', 'PRESENCIAL') NOT NULL,
    estado                  ENUM('CONFIRMADA', 'REALIZADA', 'CANCELADA') NOT NULL DEFAULT 'CONFIRMADA',
    creada_en               TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_reservas          PRIMARY KEY (id_reserva),
    CONSTRAINT uq_reservas_codigo   UNIQUE (codigo_reserva),

    CONSTRAINT fk_reservas_cliente
        FOREIGN KEY (id_cliente) REFERENCES clientes (id_cliente)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_reservas_servicio
        FOREIGN KEY (id_servicio) REFERENCES servicios (id_servicio)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_reservas_trabajador
        FOREIGN KEY (id_trabajador_registro) REFERENCES trabajadores (id_trabajador)
        ON UPDATE RESTRICT ON DELETE RESTRICT,

    CONSTRAINT ck_reservas_horas    CHECK (fin > inicio),
    CONSTRAINT ck_reservas_precio   CHECK (precio >= 0),
    -- Desde la app no hay trabajador; por teléfono o presencial, sí.
    CONSTRAINT ck_reservas_origen   CHECK (
        (origen = 'APP' AND id_trabajador_registro IS NULL) OR
        (origen <> 'APP' AND id_trabajador_registro IS NOT NULL)
    )
) ENGINE = InnoDB;

-- Búsquedas de la agenda (por día) y del historial (por cliente y fecha)
CREATE INDEX idx_reservas_inicio         ON reservas (inicio);
CREATE INDEX idx_reservas_cliente_inicio ON reservas (id_cliente, inicio);
CREATE INDEX idx_reservas_estado_inicio  ON reservas (estado, inicio);


-- =====================================================================
--  2. TRIGGERS · ANTI-SOLAPES
--  Segunda barrera, por si algo se salta la validación de la API:
--  ninguna reserva activa (no cancelada) puede pisar a otra.
--  Dos franjas se solapan si: nueva.inicio < otra.fin AND nueva.fin > otra.inicio
-- =====================================================================

DELIMITER $$

CREATE TRIGGER trg_reservas_no_solape_insert
BEFORE INSERT ON reservas
FOR EACH ROW
BEGIN
    IF NEW.estado <> 'CANCELADA' AND EXISTS (
        SELECT 1 FROM reservas r
        WHERE r.estado <> 'CANCELADA'
          AND NEW.inicio < r.fin
          AND NEW.fin > r.inicio
    ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Franja ocupada: el estudio ya tiene una reserva en ese horario';
    END IF;
END$$

CREATE TRIGGER trg_reservas_no_solape_update
BEFORE UPDATE ON reservas
FOR EACH ROW
BEGIN
    IF NEW.estado <> 'CANCELADA' AND EXISTS (
        SELECT 1 FROM reservas r
        WHERE r.id_reserva <> NEW.id_reserva
          AND r.estado <> 'CANCELADA'
          AND NEW.inicio < r.fin
          AND NEW.fin > r.inicio
    ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Franja ocupada: el estudio ya tiene una reserva en ese horario';
    END IF;
END$$

DELIMITER ;


-- =====================================================================
--  3. DML · DATOS DE PRUEBA (los mismos que el prototipo de Figma)
--
--  Contraseñas de prueba:
--    clientes      → cabina808
--    trabajadores  → recepcion808
-- =====================================================================

-- ---------------------------------------------------------------------
--  Servicios (pantalla E-05 Servicios)
-- ---------------------------------------------------------------------
INSERT INTO servicios (id_servicio, nombre, descripcion, duracion_min, precio, activo_app) VALUES
(1, 'Freestyle exprés',       'Eliges beat y grabas',          30,  12.00, TRUE),
(2, 'Batalla grabada',        'Dos MCs, vídeo y audio',        60,  25.00, TRUE),
(3, 'Grabación de tema',      'Con mezcla básica',            120,  45.00, TRUE),
(4, 'Sesión para fts',        'De 3 a 5 personas por turnos', 300, 150.00, TRUE),
(5, 'Grabación de videoclip', 'Vídeo dentro de la cabina',    120, 200.00, FALSE);

-- ---------------------------------------------------------------------
--  Trabajadores (E-01: entra "dani.recepcion"; en la barra "Dani · encargado")
-- ---------------------------------------------------------------------
INSERT INTO trabajadores (id_trabajador, nombre, usuario, password_hash, rol, activo) VALUES
(1, 'Dani García', 'dani.recepcion', '$2b$10$ymNAlJSqubNoBi8CeHkwrOJ/ZVJ/J3fMWGUPMy3PAfWahYNNRZhyy', 'ENCARGADO', TRUE),
(2, 'Laia Serra',  'laia.recepcion', '$2b$10$ymNAlJSqubNoBi8CeHkwrOJ/ZVJ/J3fMWGUPMy3PAfWahYNNRZhyy', 'RECEPCION', TRUE);

-- ---------------------------------------------------------------------
--  Clientes
--  Dj Groma es el usuario de las pantallas del móvil (M-01 a M-14).
--  "Pedro Soler" NO existe a propósito: es la búsqueda sin resultados (E-04b).
-- ---------------------------------------------------------------------
INSERT INTO clientes (id_cliente, nombre_artistico, nombre_completo, email, telefono, password_hash, avatar_color, fecha_registro) VALUES
(1, 'Dj Groma',   'Guillem Rodriguez', 'djgroma@gmail.com',   '670777808', '$2b$10$3Zzzk3diyaR.L7x.BJgg2.SUSMnsQTLTJCURVP3wYhxIMyPEha7Ia', '#12D3A0', '2026-10-01 18:30:00'),
(2, 'MC Kroma',   'Marc Roca',         'mckroma@gmail.com',   '600808808', '$2b$10$3Zzzk3diyaR.L7x.BJgg2.SUSMnsQTLTJCURVP3wYhxIMyPEha7Ia', '#7AA7FF', '2026-10-03 20:10:00'),
(3, 'Iván M.',    'Iván Martín',       'ivanmartin@gmail.com','622333444', '$2b$10$3Zzzk3diyaR.L7x.BJgg2.SUSMnsQTLTJCURVP3wYhxIMyPEha7Ia', '#F5B841', '2026-10-12 19:45:00'),
(4, 'Marta Ruiz', 'Marta Ruiz',        'martaruiz@gmail.com', '600222999', '$2b$10$3Zzzk3diyaR.L7x.BJgg2.SUSMnsQTLTJCURVP3wYhxIMyPEha7Ia', '#F28AB2', '2026-10-20 21:15:00');

-- ---------------------------------------------------------------------
--  Reservas
--  Noche del viernes 13 de noviembre (E-02 Agenda del día y E-03).
--  A034 es la reserva que Dj Groma hace desde el móvil (M-05 → M-07).
--  Las horas de 00:00 en adelante ya son del sábado 14.
-- ---------------------------------------------------------------------
INSERT INTO reservas (codigo_reserva, id_cliente, id_servicio, id_trabajador_registro, inicio, fin, precio, origen, estado) VALUES
('L808-A033', 3, 2, 1,    '2026-11-13 21:00:00', '2026-11-13 22:00:00',  25.00, 'PRESENCIAL', 'CONFIRMADA'),
('L808-A036', 4, 2, 1,    '2026-11-14 00:00:00', '2026-11-14 01:00:00',  25.00, 'TELEFONO',   'CONFIRMADA'),
('L808-A034', 1, 2, NULL, '2026-11-14 01:00:00', '2026-11-14 02:00:00',  25.00, 'APP',        'CONFIRMADA');

--  Historial de Dj Groma (M-09.2) · 3 realizadas = "3 sesiones hechas" del perfil (M-11)
INSERT INTO reservas (codigo_reserva, id_cliente, id_servicio, id_trabajador_registro, inicio, fin, precio, origen, estado) VALUES
('L808-A002', 1, 1, NULL, '2026-10-30 23:00:00', '2026-10-30 23:30:00',  12.00, 'APP',        'REALIZADA'),
('L808-A004', 1, 1, NULL, '2026-11-02 19:00:00', '2026-11-02 19:30:00',  12.00, 'APP',        'CANCELADA'),
('L808-A005', 1, 2, NULL, '2026-11-03 20:00:00', '2026-11-03 21:00:00',  25.00, 'APP',        'REALIZADA'),
('L808-A007', 1, 3, NULL, '2026-11-05 22:00:00', '2026-11-06 00:00:00',  45.00, 'APP',        'REALIZADA');

--  Historial de MC Kroma (E-04 Buscar reservas), en horario del estudio (19:00–04:00)
INSERT INTO reservas (codigo_reserva, id_cliente, id_servicio, id_trabajador_registro, inicio, fin, precio, origen, estado) VALUES
('L808-A001', 2, 1, NULL, '2026-11-02 20:00:00', '2026-11-02 20:30:00',  12.00, 'APP',        'CANCELADA'),
('L808-A003', 2, 2, NULL, '2026-11-03 19:00:00', '2026-11-03 20:00:00',  25.00, 'APP',        'REALIZADA'),
('L808-A006', 2, 3, 2,    '2026-11-05 19:00:00', '2026-11-05 21:00:00',  45.00, 'TELEFONO',   'REALIZADA'),
('L808-A035', 2, 1, NULL, '2026-11-21 21:00:00', '2026-11-21 21:30:00',  12.00, 'APP',        'CONFIRMADA');

--  Próximas reservas (para probar "Próximas" en el móvil y la agenda futura)
INSERT INTO reservas (codigo_reserva, id_cliente, id_servicio, id_trabajador_registro, inicio, fin, precio, origen, estado) VALUES
('L808-A037', 1, 2, NULL, '2026-12-04 22:00:00', '2026-12-04 23:00:00',  25.00, 'APP',        'CONFIRMADA'),
('L808-A038', 2, 4, 2,    '2026-12-04 23:00:00', '2026-12-05 04:00:00', 150.00, 'PRESENCIAL', 'CONFIRMADA'),
('L808-A039', 3, 3, 1,    '2026-12-05 20:00:00', '2026-12-05 22:00:00',  45.00, 'TELEFONO',   'CONFIRMADA');


-- =====================================================================
--  4. COMPROBACIONES RÁPIDAS (opcional, solo lectura)
-- =====================================================================
-- Agenda de la noche del viernes 13 (de 19:00 a 04:00 del día siguiente):
-- SELECT r.codigo_reserva, r.inicio, r.fin, c.nombre_artistico, s.nombre, r.origen, t.nombre AS registrada_por
-- FROM reservas r
-- JOIN clientes c  ON c.id_cliente = r.id_cliente
-- JOIN servicios s ON s.id_servicio = r.id_servicio
-- LEFT JOIN trabajadores t ON t.id_trabajador = r.id_trabajador_registro
-- WHERE r.inicio >= '2026-11-13 19:00:00' AND r.inicio < '2026-11-14 04:00:00'
-- ORDER BY r.inicio;
