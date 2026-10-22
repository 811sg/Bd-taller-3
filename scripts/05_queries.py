"""
7 consultas (Aggregation Pipeline) con su justificación de negocio.
Ejecutar:  python 05_queries.py        (todas)
           python 05_queries.py 3      (solo la consulta 3)
"""
import sys
from pprint import pprint

from pymongo import MongoClient

db = MongoClient("mongodb://localhost:27017")["tienda_online"]

NO_CANCELADO = {"$match": {"estado": {"$ne": "Cancelado"}}}

CONSULTAS = [
    {
        "titulo": "1. Top 10 productos más vendidos",
        "coleccion": "pedidos",
        "necesidad": "Saber qué productos generan más rotación e ingresos.",
        "decision": "Reabastecer primero los más vendidos y priorizarlos en campañas.",
        "impacto": "Evita quiebres de stock en los productos que más aportan a las ventas.",
        "pipeline": [
            NO_CANCELADO,
            {"$unwind": "$items"},
            {"$group": {"_id": "$items.producto_id",
                        "unidades": {"$sum": "$items.cantidad"},
                        "ingresos": {"$sum": "$items.subtotal"}}},
            {"$sort": {"unidades": -1}},
            {"$limit": 10},
            {"$lookup": {"from": "productos", "localField": "_id",
                         "foreignField": "_id", "as": "producto"}},
            {"$unwind": "$producto"},
            {"$project": {"_id": 0, "producto": "$producto.nombre",
                          "categoria": "$producto.categoria.nombre",
                          "stock_actual": "$producto.stock", "unidades": 1, "ingresos": 1}},
        ],
    },
    {
        "titulo": "2. Ingresos por categoría",
        "coleccion": "pedidos",
        "necesidad": "Conocer qué categorías sostienen el negocio.",
        "decision": "Decidir dónde ampliar catálogo o invertir en publicidad.",
        "impacto": "Asigna presupuesto a las categorías con mejor retorno.",
        "pipeline": [
            NO_CANCELADO,
            {"$unwind": "$items"},
            {"$lookup": {"from": "productos", "localField": "items.producto_id",
                         "foreignField": "_id", "as": "producto"}},
            {"$unwind": "$producto"},
            {"$group": {"_id": "$producto.categoria.nombre",
                        "ingresos": {"$sum": "$items.subtotal"},
                        "unidades": {"$sum": "$items.cantidad"}}},
            {"$sort": {"ingresos": -1}},
            {"$project": {"_id": 0, "categoria": "$_id", "ingresos": 1, "unidades": 1}},
        ],
    },
    {
        "titulo": "3. Mejores 10 clientes por gasto (pedidos entregados)",
        "coleccion": "pedidos",
        "necesidad": "Identificar a los clientes más valiosos.",
        "decision": "Crear un programa de fidelización y ofertas personalizadas.",
        "impacto": "Retener a quienes concentran gran parte de los ingresos.",
        "pipeline": [
            {"$match": {"estado": "Entregado"}},
            {"$group": {"_id": "$cliente_id", "gasto_total": {"$sum": "$total"},
                        "pedidos": {"$sum": 1}}},
            {"$sort": {"gasto_total": -1}},
            {"$limit": 10},
            {"$lookup": {"from": "clientes", "localField": "_id",
                         "foreignField": "_id", "as": "cliente"}},
            {"$unwind": "$cliente"},
            {"$project": {"_id": 0, "cliente": "$cliente.nombre", "email": "$cliente.email",
                          "pedidos": 1, "gasto_total": 1,
                          "ticket_promedio": {"$round": [{"$divide": ["$gasto_total", "$pedidos"]}, 0]}}},
        ],
    },
    {
        "titulo": "4. Ventas mensuales",
        "coleccion": "pedidos",
        "necesidad": "Ver la evolución y estacionalidad de las ventas.",
        "decision": "Planear inventario y campañas según los meses fuertes.",
        "impacto": "Permite anticipar picos y caídas de demanda.",
        "pipeline": [
            NO_CANCELADO,
            {"$group": {"_id": {"anio": {"$year": "$fecha"}, "mes": {"$month": "$fecha"}},
                        "ventas": {"$sum": "$total"}, "pedidos": {"$sum": 1}}},
            {"$sort": {"_id.anio": 1, "_id.mes": 1}},
            {"$project": {"_id": 0, "anio": "$_id.anio", "mes": "$_id.mes",
                          "ventas": 1, "pedidos": 1}},
        ],
    },
    {
        "titulo": "5. Productos mejor calificados con su proveedor (múltiples $lookup)",
        "coleccion": "resenas",
        "necesidad": "Saber qué productos y proveedores ofrecen mejor calidad percibida.",
        "decision": "Reforzar a los mejores proveedores y revisar a los de baja calificación.",
        "impacto": "Mejora la satisfacción y reduce devoluciones.",
        "pipeline": [
            {"$group": {"_id": "$producto_id", "promedio": {"$avg": "$calificacion"},
                        "num_resenas": {"$sum": 1}}},
            {"$match": {"num_resenas": {"$gte": 3}}},
            {"$sort": {"promedio": -1, "num_resenas": -1}},
            {"$limit": 10},
            {"$lookup": {"from": "productos", "localField": "_id",
                         "foreignField": "_id", "as": "producto"}},
            {"$unwind": "$producto"},
            {"$lookup": {"from": "proveedores", "localField": "producto.proveedor_id",
                         "foreignField": "_id", "as": "proveedor"}},
            {"$unwind": "$proveedor"},
            {"$project": {"_id": 0, "producto": "$producto.nombre",
                          "categoria": "$producto.categoria.nombre",
                          "proveedor": "$proveedor.nombre", "ciudad_proveedor": "$proveedor.ciudad",
                          "promedio": {"$round": ["$promedio", 2]}, "num_resenas": 1}},
        ],
    },
    {
        "titulo": "6. Pagos rechazados con cliente y método de pago (múltiples $lookup)",
        "coleccion": "pedidos",
        "necesidad": "Detectar ventas perdidas por pagos rechazados y en qué método ocurren.",
        "decision": "Contactar al cliente y revisar fallas con ciertos métodos de pago.",
        "impacto": "Recupera ingresos que se pierden en la etapa de pago.",
        "pipeline": [
            {"$match": {"pago.estado": "Rechazado"}},
            {"$sort": {"total": -1}},
            {"$limit": 10},
            {"$lookup": {"from": "clientes", "localField": "cliente_id",
                         "foreignField": "_id", "as": "cliente"}},
            {"$unwind": "$cliente"},
            {"$lookup": {"from": "metodos_pago", "localField": "pago.metodo_id",
                         "foreignField": "_id", "as": "metodo"}},
            {"$unwind": "$metodo"},
            {"$project": {"_id": 1, "fecha": 1, "total": 1, "cliente": "$cliente.nombre",
                          "email": "$cliente.email", "telefono": "$cliente.telefono",
                          "metodo_pago": "$metodo.nombre"}},
        ],
    },
    {
        "titulo": "7. Ventas por ciudad de envío",
        "coleccion": "pedidos",
        "necesidad": "Conocer dónde está la demanda geográfica.",
        "decision": "Ubicar bodegas, negociar tarifas de envío y focalizar campañas por ciudad.",
        "impacto": "Reduce costos logísticos y tiempos de entrega.",
        "pipeline": [
            NO_CANCELADO,
            {"$group": {"_id": "$direccion_envio.ciudad", "ventas": {"$sum": "$total"},
                        "pedidos": {"$sum": 1}}},
            {"$sort": {"ventas": -1}},
            {"$project": {"_id": 0, "ciudad": "$_id", "ventas": 1, "pedidos": 1,
                          "ticket_promedio": {"$round": [{"$divide": ["$ventas", "$pedidos"]}, 0]}}},
        ],
    },
]


def main():
    seleccion = int(sys.argv[1]) if len(sys.argv) > 1 else None
    for i, q in enumerate(CONSULTAS, start=1):
        if seleccion and seleccion != i:
            continue
        print("=" * 80)
        print(q["titulo"])
        print(f"Necesidad: {q['necesidad']}\nDecisión : {q['decision']}\nImpacto  : {q['impacto']}\n")
        for fila in db[q["coleccion"]].aggregate(q["pipeline"]):
            pprint(fila, sort_dicts=False)


if __name__ == "__main__":
    main()
