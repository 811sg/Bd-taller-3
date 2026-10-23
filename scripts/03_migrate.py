
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal

import pyodbc
from pymongo import MongoClient

SQL_CONN = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=DESKTOP-LI82RG6\\SQLEXPRESS01;"
    "DATABASE=TiendaOnline;"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)
MONGO_URI = "mongodb://localhost:27017"
MONGO_DB = "tienda_online"


def limpiar(v):

    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, date) and not isinstance(v, datetime):
        return datetime(v.year, v.month, v.day)
    return v


def leer(cur, tabla):
    cur.execute(f"SELECT * FROM {tabla}")
    cols = [c[0] for c in cur.description]
    return [{c: limpiar(v) for c, v in zip(cols, fila)} for fila in cur.fetchall()]


def main():
    cur = pyodbc.connect(SQL_CONN).cursor()
    mongo = MongoClient(MONGO_URI)
    mongo.drop_database(MONGO_DB)  # permite re-ejecutar la migración
    db = mongo[MONGO_DB]

    categorias = {r["id_categoria"]: r for r in leer(cur, "Categoria")}
    proveedores = leer(cur, "Proveedor")
    metodos = leer(cur, "MetodoPago")
    clientes = leer(cur, "Cliente")
    direcciones = leer(cur, "Direccion")
    productos = leer(cur, "Producto")
    pedidos = leer(cur, "Pedido")
    detalles = leer(cur, "DetallePedido")
    pagos = leer(cur, "Pago")
    resenas = leer(cur, "Resena")

    prod_por_id = {p["id_producto"]: p for p in productos}
    dir_por_id = {d["id_direccion"]: d for d in direcciones}

    # --- proveedores y metodos_pago: colecciones independientes (referencing)
    db.proveedores.insert_many([
        {"_id": p["id_proveedor"], "nombre": p["nombre"], "email": p["email"],
         "telefono": p["telefono"], "ciudad": p["ciudad"]} for p in proveedores])
    db.metodos_pago.insert_many([{"_id": m["id_metodo"], "nombre": m["nombre"]} for m in metodos])

    # --- clientes con direcciones embebidas
    dirs_por_cli = defaultdict(list)
    for d in direcciones:
        dirs_por_cli[d["id_cliente"]].append({
            "id_direccion": d["id_direccion"], "ciudad": d["ciudad"],
            "departamento": d["departamento"], "direccion": d["direccion"],
            "es_principal": bool(d["es_principal"])})
    db.clientes.insert_many([
        {"_id": c["id_cliente"], "nombre": c["nombre"], "email": c["email"],
         "telefono": c["telefono"], "fecha_registro": c["fecha_registro"],
         "direcciones": dirs_por_cli[c["id_cliente"]]} for c in clientes])

    # --- productos con categoría embebida y proveedor referenciado
    db.productos.insert_many([
        {"_id": p["id_producto"], "nombre": p["nombre"], "descripcion": p["descripcion"],
         "precio": p["precio"], "stock": p["stock"],
         "categoria": {"id_categoria": p["id_categoria"],
                       "nombre": categorias[p["id_categoria"]]["nombre"]},
         "proveedor_id": p["id_proveedor"]} for p in productos])

    # --- pedidos: items (array), pago (subdocumento), dirección de envío (snapshot)
    items_por_ped = defaultdict(list)
    for d in detalles:
        prod = prod_por_id[d["id_producto"]]
        items_por_ped[d["id_pedido"]].append({
            "detalle_id": d["id_detalle"], "producto_id": d["id_producto"],
            "nombre_producto": prod["nombre"], "cantidad": d["cantidad"],
            "precio_unitario": d["precio_unitario"],
            "subtotal": d["cantidad"] * d["precio_unitario"]})
    pago_por_ped = {p["id_pedido"]: {
        "pago_id": p["id_pago"], "metodo_id": p["id_metodo"], "monto": p["monto"],
        "fecha_pago": p["fecha_pago"], "estado": p["estado"]} for p in pagos}

    docs_pedidos = []
    for p in pedidos:
        d = dir_por_id[p["id_direccion"]]
        docs_pedidos.append({
            "_id": p["id_pedido"], "cliente_id": p["id_cliente"], "fecha": p["fecha"],
            "estado": p["estado"], "total": p["total"],
            "direccion_envio": {"ciudad": d["ciudad"], "departamento": d["departamento"],
                                "direccion": d["direccion"]},
            "items": items_por_ped[p["id_pedido"]],
            "pago": pago_por_ped[p["id_pedido"]]})
    db.pedidos.insert_many(docs_pedidos)

    # --- reseñas: colección propia (crece sin límite, se consulta por producto)
    db.resenas.insert_many([
        {"_id": r["id_resena"], "cliente_id": r["id_cliente"], "producto_id": r["id_producto"],
         "calificacion": r["calificacion"], "comentario": r["comentario"], "fecha": r["fecha"]}
        for r in resenas])

    # --- índices que respaldan los $lookup y filtros más usados
    db.pedidos.create_index("cliente_id")
    db.pedidos.create_index("items.producto_id")
    db.resenas.create_index("producto_id")
    db.productos.create_index("proveedor_id")

    print("Migración completada:")
    for nombre in db.list_collection_names():
        print(f"  {nombre:<14} {db[nombre].count_documents({})} documentos")


if __name__ == "__main__":
    main()
