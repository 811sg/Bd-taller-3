-- Caso de estudio: TIENDA ONLINE (e-commerce)
-- 10 entidades. Los IDs los asigna el script de Python (generate_data.py),
-- por eso las PK son INT simples (sin IDENTITY).

IF DB_ID('TiendaOnline') IS NULL CREATE DATABASE TiendaOnline;
GO
USE TiendaOnline;
GO

DROP TABLE IF EXISTS Resena, Pago, DetallePedido, Pedido, Direccion, Producto, Cliente, MetodoPago, Proveedor, Categoria;
GO

CREATE TABLE Categoria (
    id_categoria INT PRIMARY KEY,
    nombre       VARCHAR(80)  NOT NULL,
    descripcion  VARCHAR(200) NULL
);

CREATE TABLE Proveedor (
    id_proveedor INT PRIMARY KEY,
    nombre       VARCHAR(120) NOT NULL,
    email        VARCHAR(120) NOT NULL,
    telefono     VARCHAR(40)  NULL,
    ciudad       VARCHAR(80)  NOT NULL
);

CREATE TABLE MetodoPago (
    id_metodo INT PRIMARY KEY,
    nombre    VARCHAR(50) NOT NULL
);

CREATE TABLE Cliente (
    id_cliente     INT PRIMARY KEY,
    nombre         VARCHAR(120) NOT NULL,
    email          VARCHAR(120) NOT NULL UNIQUE,
    telefono       VARCHAR(40)  NULL,
    fecha_registro DATETIME2    NOT NULL
);

CREATE TABLE Direccion (
    id_direccion INT PRIMARY KEY,
    id_cliente   INT NOT NULL REFERENCES Cliente(id_cliente),
    ciudad       VARCHAR(80)  NOT NULL,
    departamento VARCHAR(80)  NOT NULL,
    direccion    VARCHAR(150) NOT NULL,
    es_principal BIT NOT NULL
);

CREATE TABLE Producto (
    id_producto  INT PRIMARY KEY,
    nombre       VARCHAR(150) NOT NULL,
    descripcion  VARCHAR(300) NULL,
    precio       DECIMAL(12,2) NOT NULL CHECK (precio > 0),
    stock        INT NOT NULL CHECK (stock >= 0),
    id_categoria INT NOT NULL REFERENCES Categoria(id_categoria),
    id_proveedor INT NOT NULL REFERENCES Proveedor(id_proveedor)
);

CREATE TABLE Pedido (
    id_pedido    INT PRIMARY KEY,
    id_cliente   INT NOT NULL REFERENCES Cliente(id_cliente),
    id_direccion INT NOT NULL REFERENCES Direccion(id_direccion),
    fecha        DATETIME2 NOT NULL,
    estado       VARCHAR(20) NOT NULL
                 CHECK (estado IN ('Pendiente','Pagado','Enviado','Entregado','Cancelado')),
    total        DECIMAL(14,2) NOT NULL
);

CREATE TABLE DetallePedido (
    id_detalle      INT PRIMARY KEY,
    id_pedido       INT NOT NULL REFERENCES Pedido(id_pedido),
    id_producto     INT NOT NULL REFERENCES Producto(id_producto),
    cantidad        INT NOT NULL CHECK (cantidad > 0),
    precio_unitario DECIMAL(12,2) NOT NULL
);

CREATE TABLE Pago (
    id_pago    INT PRIMARY KEY,
    id_pedido  INT NOT NULL REFERENCES Pedido(id_pedido),
    id_metodo  INT NOT NULL REFERENCES MetodoPago(id_metodo),
    monto      DECIMAL(14,2) NOT NULL,
    fecha_pago DATETIME2 NOT NULL,
    estado     VARCHAR(20) NOT NULL CHECK (estado IN ('Aprobado','Rechazado','Pendiente'))
);

CREATE TABLE Resena (
    id_resena    INT PRIMARY KEY,
    id_cliente   INT NOT NULL REFERENCES Cliente(id_cliente),
    id_producto  INT NOT NULL REFERENCES Producto(id_producto),
    calificacion INT NOT NULL CHECK (calificacion BETWEEN 1 AND 5),
    comentario   VARCHAR(300) NULL,
    fecha        DATETIME2 NOT NULL
);
GO
