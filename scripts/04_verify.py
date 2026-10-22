"""
Verificaciones posteriores a la migración (evidencia para la sustentación).
Compara SQL Server vs MongoDB: conteos, sumas, referencias y un pedido de muestra.
"""
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

cur = pyodbc.connect(SQL_CONN).cursor()
db = MongoClient(MONGO_URI)[MONGO_DB]
resultados = []


def sql_val(q):
    cur.execute(q)
    v = cur.fetchone()[0]
    return float(v) if v is not None and not isinstance(v, int) else v


def check(nombre, sql, mongo):
    ok = abs(float(sql) - float(mongo)) < 0.01
    resultados.append(ok)
    print(f"[{'OK' if ok else 'FALLO'}] {nombre:<48} SQL={sql}  Mongo={mongo}")


def suma_mongo(coleccion, pipeline):
    r = list(db[coleccion].aggregate(pipeline))
    return r[0]["n"] if r else 0


print("== 1. Conteos ==")
check("Clientes", sql_val("SELECT COUNT(*) FROM Cliente"), db.clientes.count_documents({}))
check("Productos", sql_val("SELECT COUNT(*) FROM Producto"), db.productos.count_documents({}))
check("Proveedores", sql_val("SELECT COUNT(*) FROM Proveedor"), db.proveedores.count_documents({}))
check("Métodos de pago", sql_val("SELECT COUNT(*) FROM MetodoPago"), db.metodos_pago.count_documents({}))
check("Pedidos", sql_val("SELECT COUNT(*) FROM Pedido"), db.pedidos.count_documents({}))
check("Reseñas", sql_val("SELECT COUNT(*) FROM Resena"), db.resenas.count_documents({}))

print("\n== 2. Estructuras embebidas (filas SQL = elementos de array) ==")
check("Direccion -> clientes.direcciones", sql_val("SELECT COUNT(*) FROM Direccion"),
      suma_mongo("clientes", [{"$group": {"_id": None, "n": {"$sum": {"$size": "$direcciones"}}}}]))
check("DetallePedido -> pedidos.items", sql_val("SELECT COUNT(*) FROM DetallePedido"),
      suma_mongo("pedidos", [{"$group": {"_id": None, "n": {"$sum": {"$size": "$items"}}}}]))
check("Pago -> pedidos.pago (1 por pedido)", sql_val("SELECT COUNT(*) FROM Pago"),
      db.pedidos.count_documents({"pago.pago_id": {"$exists": True}}))
check("Categoria -> productos.categoria", sql_val("SELECT COUNT(DISTINCT id_categoria) FROM Producto"),
      len(db.productos.distinct("categoria.id_categoria")))

print("\n== 3. Integridad de valores ==")
check("Suma total de pedidos", sql_val("SELECT SUM(total) FROM Pedido"),
      suma_mongo("pedidos", [{"$group": {"_id": None, "n": {"$sum": "$total"}}}]))
check("Suma de DetallePedido (cant*precio)", sql_val("SELECT SUM(cantidad*precio_unitario) FROM DetallePedido"),
      suma_mongo("pedidos", [{"$unwind": "$items"}, {"$group": {"_id": None, "n": {"$sum": "$items.subtotal"}}}]))
check("Pedidos cuyo total != suma de items (debe ser 0)", 0,
      suma_mongo("pedidos", [{"$addFields": {"s": {"$sum": "$items.subtotal"}}},
                             {"$match": {"$expr": {"$ne": ["$s", "$total"]}}},
                             {"$count": "n"}]))

print("\n== 4. Referencias huérfanas (todas deben ser 0) ==")
huerfanas = {
    "pedidos.cliente_id sin cliente": ("pedidos", "cliente_id", "clientes"),
    "productos.proveedor_id sin proveedor": ("productos", "proveedor_id", "proveedores"),
    "resenas.producto_id sin producto": ("resenas", "producto_id", "productos"),
    "resenas.cliente_id sin cliente": ("resenas", "cliente_id", "clientes"),
    "pedidos.pago.metodo_id sin método": ("pedidos", "pago.metodo_id", "metodos_pago"),
}
for nombre, (col, campo, destino) in huerfanas.items():
    n = suma_mongo(col, [
        {"$lookup": {"from": destino, "localField": campo, "foreignField": "_id", "as": "r"}},
        {"$match": {"r": {"$size": 0}}}, {"$count": "n"}])
    check(nombre, 0, n)

print("\n== 5. Comparación de un pedido de muestra ==")
cur.execute("SELECT TOP 1 id_pedido, id_cliente, estado, total FROM Pedido ORDER BY id_pedido DESC")
id_ped, id_cli, estado, total = cur.fetchone()
doc = db.pedidos.find_one({"_id": id_ped})
print(f"SQL   : pedido={id_ped} cliente={id_cli} estado={estado} total={float(total)}")
print(f"Mongo : pedido={doc['_id']} cliente={doc['cliente_id']} estado={doc['estado']} "
      f"total={doc['total']} items={len(doc['items'])}")
resultados.append(doc["cliente_id"] == id_cli and doc["estado"] == estado
                  and abs(doc["total"] - float(total)) < 0.01)

print(f"\nResumen: {sum(resultados)}/{len(resultados)} verificaciones correctas")
