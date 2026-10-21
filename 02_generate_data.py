"""
Genera datos coherentes para la base TiendaOnline en SQL Server.
Volumen por defecto: ~12.800 registros en total (el taller pide > 5.000).

Uso:  python 02_generate_data.py
Antes: ejecutar 01_schema.sql en SQL Server.
"""
import random
from datetime import datetime, timedelta

import pyodbc
from faker import Faker

# --- Conexión (ajusta SERVER y el método de autenticación) -------------------
CONN = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=DESKTOP-LI82RG6\\SQLEXPRESS01;"
    "DATABASE=TiendaOnline;"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)

# --- Volúmenes ----------------------------------------------------------------
N_PROVEEDORES = 30
N_PRODUCTOS = 300
N_CLIENTES = 800
N_PEDIDOS = 2000
N_RESENAS = 1500

random.seed(42)
Faker.seed(42)
fake = Faker("es_CO")
AHORA = datetime.now()

CATEGORIAS = {
    "Electrónica": ["Audífonos", "Parlante", "Cargador", "Teclado", "Mouse", "Cámara web"],
    "Hogar": ["Lámpara", "Cojín", "Juego de sábanas", "Organizador", "Licuadora"],
    "Deportes": ["Balón", "Guantes", "Botella", "Colchoneta", "Cuerda para saltar"],
    "Moda": ["Camiseta", "Chaqueta", "Gorra", "Mochila", "Jean"],
    "Juguetes": ["Rompecabezas", "Carro de control", "Muñeco", "Juego de mesa"],
    "Libros": ["Novela", "Manual técnico", "Libro infantil", "Cómic"],
    "Belleza": ["Crema facial", "Perfume", "Shampoo", "Set de maquillaje"],
    "Mascotas": ["Comedero", "Cama para perro", "Juguete para gato", "Correa"],
    "Oficina": ["Cuaderno", "Silla ergonómica", "Agenda", "Set de marcadores"],
    "Cocina": ["Sartén", "Juego de cuchillos", "Termo", "Cafetera"],
}
ADJ = ["Pro", "Plus", "Max", "Lite", "Classic", "Eco", "Premium", "Mini", "Smart", "Ultra"]

UBICACIONES = [
    ("Medellín", "Antioquia"), ("Bello", "Antioquia"), ("Envigado", "Antioquia"),
    ("Bogotá", "Cundinamarca"), ("Cali", "Valle del Cauca"), ("Barranquilla", "Atlántico"),
    ("Cartagena", "Bolívar"), ("Bucaramanga", "Santander"), ("Pereira", "Risaralda"),
    ("Manizales", "Caldas"),
]
METODOS = ["Tarjeta de crédito", "Tarjeta débito", "PSE", "Nequi", "Contra entrega"]
COMENTARIOS = {
    5: ["Excelente producto", "Superó mis expectativas", "Muy buena calidad"],
    4: ["Muy bueno, llegó a tiempo", "Buena relación precio-calidad"],
    3: ["Cumple, nada especial", "Regular, esperaba más"],
    2: ["La calidad no es la mejor", "Tardó mucho en llegar"],
    1: ["No lo recomiendo", "Llegó dañado"],
}


def fecha_aleatoria(desde, hasta):
    delta = int((hasta - desde).total_seconds())
    return desde + timedelta(seconds=random.randint(0, delta))


def bulk(cur, sql, rows):
    cur.fast_executemany = True
    cur.executemany(sql, rows)
    print(f"  {len(rows):>6} filas -> {sql.split()[2]}")


def main():
    conn = pyodbc.connect(CONN)
    cur = conn.cursor()

    # Limpieza previa (orden por FKs) para poder re-ejecutar el script
    for t in ["Resena", "Pago", "DetallePedido", "Pedido", "Direccion",
              "Producto", "Cliente", "MetodoPago", "Proveedor", "Categoria"]:
        cur.execute(f"DELETE FROM {t}")

    # 1) Categoria
    nombres_cat = list(CATEGORIAS)
    categorias = [(i + 1, n, f"Productos de {n.lower()}") for i, n in enumerate(nombres_cat)]
    bulk(cur, "INSERT INTO Categoria VALUES (?,?,?)", categorias)

    # 2) Proveedor
    proveedores = []
    for i in range(1, N_PROVEEDORES + 1):
        ciudad = random.choice(UBICACIONES)[0]
        proveedores.append((i, fake.company()[:120], f"contacto{i}@proveedor.com",
                            fake.phone_number()[:40], ciudad))
    bulk(cur, "INSERT INTO Proveedor VALUES (?,?,?,?,?)", proveedores)

    # 3) MetodoPago
    bulk(cur, "INSERT INTO MetodoPago VALUES (?,?)", [(i + 1, n) for i, n in enumerate(METODOS)])

    # 4) Producto
    productos = []
    for i in range(1, N_PRODUCTOS + 1):
        id_cat = random.randint(1, len(nombres_cat))
        base = random.choice(CATEGORIAS[nombres_cat[id_cat - 1]])
        nombre = f"{base} {random.choice(ADJ)} {i}"
        precio = random.randrange(10_000, 3_000_000, 500)
        productos.append((i, nombre, f"{nombre} - {nombres_cat[id_cat-1]}", precio,
                          random.randint(0, 200), id_cat, random.randint(1, N_PROVEEDORES)))
    bulk(cur, "INSERT INTO Producto VALUES (?,?,?,?,?,?,?)", productos)
    precio_prod = {p[0]: p[3] for p in productos}

    # 5) Cliente
    clientes = []
    for i in range(1, N_CLIENTES + 1):
        clientes.append((i, fake.name(), f"{fake.user_name()}{i}@correo.com",
                         fake.phone_number()[:40],
                         fecha_aleatoria(AHORA - timedelta(days=900), AHORA - timedelta(days=30))))
    bulk(cur, "INSERT INTO Cliente VALUES (?,?,?,?,?)", clientes)

    # 6) Direccion (1 a 3 por cliente; la primera es la principal)
    direcciones, dirs_cliente, id_dir = [], {}, 1
    for c in clientes:
        dirs_cliente[c[0]] = []
        for k in range(random.randint(1, 3)):
            ciudad, depto = random.choice(UBICACIONES)
            direcciones.append((id_dir, c[0], ciudad, depto,
                                fake.street_address()[:150], 1 if k == 0 else 0))
            dirs_cliente[c[0]].append(id_dir)
            id_dir += 1
    bulk(cur, "INSERT INTO Direccion VALUES (?,?,?,?,?,?)", direcciones)

    # 7-9) Pedido, DetallePedido, Pago (total = suma de detalles, monto = total)
    pedidos, detalles, pagos, id_det = [], [], [], 1
    estados = ["Pendiente", "Pagado", "Enviado", "Entregado", "Cancelado"]
    pesos = [8, 12, 15, 55, 10]
    for id_ped in range(1, N_PEDIDOS + 1):
        id_cli = random.randint(1, N_CLIENTES)
        id_dir_ped = random.choice(dirs_cliente[id_cli])
        fecha = fecha_aleatoria(AHORA - timedelta(days=540), AHORA)
        estado = random.choices(estados, pesos)[0]
        total = 0
        for id_prod in random.sample(range(1, N_PRODUCTOS + 1), random.randint(1, 5)):
            cant = random.randint(1, 4)
            pu = precio_prod[id_prod]
            detalles.append((id_det, id_ped, id_prod, cant, pu))
            total += cant * pu
            id_det += 1
        pedidos.append((id_ped, id_cli, id_dir_ped, fecha, estado, total))
        estado_pago = {"Cancelado": "Rechazado", "Pendiente": "Pendiente"}.get(estado, "Aprobado")
        pagos.append((id_ped, id_ped, random.randint(1, len(METODOS)), total,
                      fecha + timedelta(minutes=random.randint(1, 120)), estado_pago))
    bulk(cur, "INSERT INTO Pedido VALUES (?,?,?,?,?,?)", pedidos)
    bulk(cur, "INSERT INTO DetallePedido VALUES (?,?,?,?,?)", detalles)
    bulk(cur, "INSERT INTO Pago VALUES (?,?,?,?,?,?)", pagos)

    # 10) Resena (sin repetir cliente+producto)
    resenas, vistos = [], set()
    while len(resenas) < N_RESENAS:
        par = (random.randint(1, N_CLIENTES), random.randint(1, N_PRODUCTOS))
        if par in vistos:
            continue
        vistos.add(par)
        cal = random.choices([1, 2, 3, 4, 5], [4, 6, 15, 30, 45])[0]
        resenas.append((len(resenas) + 1, par[0], par[1], cal,
                        random.choice(COMENTARIOS[cal]),
                        fecha_aleatoria(AHORA - timedelta(days=500), AHORA)))
    bulk(cur, "INSERT INTO Resena VALUES (?,?,?,?,?,?)", resenas)

    conn.commit()
    total_reg = (len(categorias) + len(proveedores) + len(METODOS) + len(productos) +
                 len(clientes) + len(direcciones) + len(pedidos) + len(detalles) +
                 len(pagos) + len(resenas))
    print(f"\nTotal de registros insertados: {total_reg}")
    conn.close()


if __name__ == "__main__":
    main()
