import csv
import math
import random
import warnings
from datetime import datetime

from scipy import stats


warnings.filterwarnings("ignore", category=RuntimeWarning)


ARCHIVO = "pedidos_delivery.csv"
MINUTOS_DIA = 24 * 60
SEMILLA = 42
REPLICAS = 10
ESCENARIOS_REPARTIDORES = [2, 3, 4, 5]


def franja_horaria(fecha):
    hora = fecha.hour
    if 6 <= hora < 11:
        return "manana"
    if 11 <= hora < 15:
        return "mediodia"
    if 15 <= hora < 20:
        return "tarde"
    return "noche"


def franja_por_minuto(tiempo):
    hora = int((tiempo % MINUTOS_DIA) // 60)
    if 6 <= hora < 11:
        return "manana"
    if 11 <= hora < 15:
        return "mediodia"
    if 15 <= hora < 20:
        return "tarde"
    return "noche"


def cargar_datos():
    pedidos = []

    with open(ARCHIVO, encoding="utf-8") as archivo:
        lector = csv.DictReader(archivo)
        for fila in lector:
            fecha = datetime.strptime(fila["fecha_hora"], "%Y-%m-%d %H:%M:%S")
            pedidos.append(
                {
                    "fecha": fecha,
                    "dia": fecha.date(),
                    "franja": franja_horaria(fecha),
                    "distancia": float(fila["distancia_km"]),
                    "clima": fila["clima"].strip().lower(),
                    "prioridad": fila["prioridad"].strip().lower(),
                }
            )

    pedidos.sort(key=lambda pedido: pedido["fecha"])
    return pedidos


def ajustar_fdp(valores, nombre):
    valores = [max(0.01, valor) for valor in valores]
    distribucion = getattr(stats, nombre)
    parametros = distribucion.fit(valores)
    return distribucion, parametros


def generar_muestra_ta(pedidos):
    muestra = []

    for pedido in pedidos:
        base = 6
        viaje = pedido["distancia"] * 4.5
        lluvia = 3 if pedido["clima"] == "lluvia" else 0
        express = -0.75 if pedido["prioridad"] == "express" else 0
        muestra.append(max(1, base + viaje + lluvia + express))

    return muestra


def preparar_modelos(pedidos):
    tiempos = [pedido["fecha"] for pedido in pedidos]

    ia_general = []
    for anterior, actual in zip(tiempos, tiempos[1:]):
        ia_general.append(max(0.01, (actual - anterior).total_seconds() / 60))

    ia_por_franja = {
        "manana": [],
        "mediodia": [],
        "tarde": [],
        "noche": [],
    }

    for franja in ia_por_franja:
        pedidos_franja = [p for p in pedidos if p["franja"] == franja]
        pedidos_por_dia = {}

        for pedido in pedidos_franja:
            pedidos_por_dia.setdefault(pedido["dia"], []).append(pedido["fecha"])

        for lista_fechas in pedidos_por_dia.values():
            lista_fechas.sort()
            for anterior, actual in zip(lista_fechas, lista_fechas[1:]):
                ia_por_franja[franja].append(max(0.01, (actual - anterior).total_seconds() / 60))

    ta_todos = generar_muestra_ta(pedidos)
    ta_normal = generar_muestra_ta([p for p in pedidos if p["clima"] == "normal"])
    ta_lluvia = generar_muestra_ta([p for p in pedidos if p["clima"] == "lluvia"])

    modelos = {
        "ia_general": ajustar_fdp(ia_general, "betaprime"),
        "ia_manana": ajustar_fdp(ia_por_franja["manana"], "truncpareto"),
        "ia_mediodia": ajustar_fdp(ia_por_franja["mediodia"], "betaprime"),
        "ia_tarde": ajustar_fdp(ia_por_franja["tarde"], "betaprime"),
        "ia_noche": ajustar_fdp(ia_por_franja["noche"], "exponweib"),
        "ta_general": ajustar_fdp(ta_todos, "gausshyper"),
        "ta_normal": ajustar_fdp(ta_normal, "gausshyper"),
        "ta_lluvia": ajustar_fdp(ta_lluvia, "gausshyper"),
    }

    tasas_express = {}
    for franja in ["manana", "mediodia", "tarde", "noche"]:
        pedidos_franja = [p for p in pedidos if p["franja"] == franja]
        if pedidos_franja:
            tasas_express[franja] = sum(p["prioridad"] == "express" for p in pedidos_franja) / len(pedidos_franja)
        else:
            tasas_express[franja] = 0.15

    dias = {p["dia"] for p in pedidos}
    dias_lluvia = {p["dia"] for p in pedidos if p["clima"] == "lluvia"}
    prob_lluvia = len(dias_lluvia) / len(dias)

    return modelos, tasas_express, prob_lluvia


def generar_ia(modelos, tiempo_actual):
    franja = franja_por_minuto(tiempo_actual)

    if franja == "manana":
        distribucion, parametros = modelos["ia_manana"]
    elif franja == "mediodia":
        distribucion, parametros = modelos["ia_mediodia"]
    elif franja == "tarde":
        distribucion, parametros = modelos["ia_tarde"]
    else:
        distribucion, parametros = modelos["ia_noche"]

    return max(0.01, float(distribucion.rvs(*parametros)))


def generar_ta(modelos, hay_lluvia):
    if hay_lluvia:
        distribucion, parametros = modelos["ta_lluvia"]
    else:
        distribucion, parametros = modelos["ta_normal"]

    return max(0.01, float(distribucion.rvs(*parametros)))


def buscar_repartidor_libre(tiempos_fin):
    for i in range(len(tiempos_fin)):
        if math.isinf(tiempos_fin[i]):
            return i
    return None


def siguiente_entrega(tiempos_fin):
    minimo = min(tiempos_fin)
    return tiempos_fin.index(minimo), minimo


def asignar_pedido(
    cola_normal,
    cola_express,
    tiempos_fin,
    tipos,
    llegadas,
    inicios_ociosos,
    tiempos_ociosos,
    repartidor,
    tiempo_actual,
    tiempo_atencion,
):
    if cola_express:
        llegada = cola_express.pop(0)
        tipo = "express"
    elif cola_normal:
        llegada = cola_normal.pop(0)
        tipo = "normal"
    else:
        tiempos_fin[repartidor] = math.inf
        tipos[repartidor] = ""
        llegadas[repartidor] = 0
        inicios_ociosos[repartidor] = tiempo_actual
        return

    if math.isinf(tiempos_fin[repartidor]):
        tiempos_ociosos[repartidor] += tiempo_actual - inicios_ociosos[repartidor]

    tiempos_fin[repartidor] = tiempo_actual + tiempo_atencion
    tipos[repartidor] = tipo
    llegadas[repartidor] = llegada


def simular_una_vez(nombre, repartidores, modelos, tasas_express, prob_lluvia):
    tiempo_final = MINUTOS_DIA
    tiempo_actual = 0
    tiempo_proximo_pedido = generar_ia(modelos, 0)
    hay_lluvia = random.random() <= prob_lluvia

    cola_normal = []
    cola_express = []

    tiempos_fin = [math.inf] * repartidores
    tipos = [""] * repartidores
    llegadas = [0] * repartidores
    inicios_ociosos = [0] * repartidores
    tiempos_ociosos = [0] * repartidores

    sumatoria_pps_normal = 0
    sumatoria_pps_express = 0
    completados_normal = 0
    completados_express = 0

    area_cola_normal = 0
    area_cola_express = 0
    max_cola_normal = 0
    max_cola_express = 0

    while True:
        indice_entrega, tiempo_proxima_entrega = siguiente_entrega(tiempos_fin)

        if tiempo_proximo_pedido > tiempo_final and math.isinf(tiempo_proxima_entrega):
            break

        proximo_evento = min(tiempo_proximo_pedido, tiempo_proxima_entrega)
        delta = proximo_evento - tiempo_actual
        area_cola_normal += len(cola_normal) * delta
        area_cola_express += len(cola_express) * delta
        tiempo_actual = proximo_evento

        if tiempo_proximo_pedido <= tiempo_proxima_entrega and tiempo_proximo_pedido <= tiempo_final:
            franja = franja_por_minuto(tiempo_actual)
            if random.random() <= tasas_express[franja]:
                cola_express.append(tiempo_actual)
            else:
                cola_normal.append(tiempo_actual)

            max_cola_normal = max(max_cola_normal, len(cola_normal))
            max_cola_express = max(max_cola_express, len(cola_express))

            libre = buscar_repartidor_libre(tiempos_fin)
            if libre is not None:
                tiempo_atencion = generar_ta(modelos, hay_lluvia)
                asignar_pedido(
                    cola_normal,
                    cola_express,
                    tiempos_fin,
                    tipos,
                    llegadas,
                    inicios_ociosos,
                    tiempos_ociosos,
                    libre,
                    tiempo_actual,
                    tiempo_atencion,
                )

            if tiempo_actual < tiempo_final:
                tiempo_proximo_pedido = tiempo_actual + generar_ia(modelos, tiempo_actual)
            else:
                tiempo_proximo_pedido = math.inf

        else:
            if tipos[indice_entrega] == "normal":
                completados_normal += 1
                sumatoria_pps_normal += tiempo_actual - llegadas[indice_entrega]
            elif tipos[indice_entrega] == "express":
                completados_express += 1
                sumatoria_pps_express += tiempo_actual - llegadas[indice_entrega]

            tiempo_atencion = generar_ta(modelos, hay_lluvia)
            asignar_pedido(
                cola_normal,
                cola_express,
                tiempos_fin,
                tipos,
                llegadas,
                inicios_ociosos,
                tiempos_ociosos,
                indice_entrega,
                tiempo_actual,
                tiempo_atencion,
            )

    for i in range(repartidores):
        if math.isinf(tiempos_fin[i]):
            tiempos_ociosos[i] += tiempo_actual - inicios_ociosos[i]

    completados_totales = completados_normal + completados_express
    sumatoria_total = sumatoria_pps_normal + sumatoria_pps_express

    return {
        "nombre": nombre,
        "repartidores": repartidores,
        "pps_normal": sumatoria_pps_normal / completados_normal if completados_normal else 0,
        "pps_express": sumatoria_pps_express / completados_express if completados_express else 0,
        "pps_total": sumatoria_total / completados_totales if completados_totales else 0,
        "completados_normal": completados_normal,
        "completados_express": completados_express,
        "completados_totales": completados_totales,
        "cola_promedio_normal": area_cola_normal / tiempo_actual if tiempo_actual else 0,
        "cola_promedio_express": area_cola_express / tiempo_actual if tiempo_actual else 0,
        "cola_maxima_normal": max_cola_normal,
        "cola_maxima_express": max_cola_express,
        "pto": [tiempo_ocioso * 100 / tiempo_actual if tiempo_actual else 0 for tiempo_ocioso in tiempos_ociosos],
        "lluvia": hay_lluvia,
    }


def promedio(lista):
    return sum(lista) / len(lista) if lista else 0


def resumir_escenario(nombre, repartidores, modelos, tasas_express, prob_lluvia):
    resultados = []

    for _ in range(REPLICAS):
        resultados.append(
            simular_una_vez(
                nombre,
                repartidores,
                modelos,
                tasas_express,
                prob_lluvia,
            )
        )

    return {
        "nombre": nombre,
        "repartidores": repartidores,
        "pps_normal": promedio([r["pps_normal"] for r in resultados]),
        "pps_express": promedio([r["pps_express"] for r in resultados]),
        "pps_total": promedio([r["pps_total"] for r in resultados]),
        "completados": promedio([r["completados_totales"] for r in resultados]),
        "cola_promedio_normal": promedio([r["cola_promedio_normal"] for r in resultados]),
        "cola_promedio_express": promedio([r["cola_promedio_express"] for r in resultados]),
        "cola_maxima_normal": promedio([r["cola_maxima_normal"] for r in resultados]),
        "cola_maxima_express": promedio([r["cola_maxima_express"] for r in resultados]),
        "pto_promedio": promedio([promedio(r["pto"]) for r in resultados]),
        "corridas_con_lluvia": sum(r["lluvia"] for r in resultados),
    }


def imprimir_fdp(modelos, tasas_express, prob_lluvia):
    print("FDPs utilizadas")
    print(f"- TA: gausshyper")
    print(f"- IA general: betaprime")
    print(f"- IA manana: truncpareto")
    print(f"- IA mediodia: betaprime")
    print(f"- IA tarde: betaprime")
    print(f"- IA noche: exponweib")
    print()
    print("Probabilidades usadas")
    print(f"- Dia lluvioso: {prob_lluvia:.4f}")
    print(f"- Express manana: {tasas_express['manana']:.4f}")
    print(f"- Express mediodia: {tasas_express['mediodia']:.4f}")
    print(f"- Express tarde: {tasas_express['tarde']:.4f}")
    print(f"- Express noche: {tasas_express['noche']:.4f}")
    print()


def imprimir_resultado(resultado):
    print(f"Escenario: {resultado['nombre']}")
    print(f"- Repartidores: {resultado['repartidores']}")
    print(f"- Pedidos completados: {resultado['completados']:.2f}")
    print(f"- PPS normal: {resultado['pps_normal']:.2f} min")
    print(f"- PPS express: {resultado['pps_express']:.2f} min")
    print(f"- PPS total: {resultado['pps_total']:.2f} min")
    print(f"- Cola promedio normal: {resultado['cola_promedio_normal']:.2f}")
    print(f"- Cola promedio express: {resultado['cola_promedio_express']:.2f}")
    print(f"- Cola maxima normal: {resultado['cola_maxima_normal']:.2f}")
    print(f"- Cola maxima express: {resultado['cola_maxima_express']:.2f}")
    print(f"- PTO promedio: {resultado['pto_promedio']:.2f}%")
    print(f"- Corridas con lluvia: {resultado['corridas_con_lluvia']} de {REPLICAS}")
    print()


def main():
    random.seed(SEMILLA)

    pedidos = cargar_datos()
    modelos, tasas_express, prob_lluvia = preparar_modelos(pedidos)

    imprimir_fdp(modelos, tasas_express, prob_lluvia)

    resultados = []
    for repartidores in ESCENARIOS_REPARTIDORES:
        resultados.append(
            resumir_escenario(
                f"Escenario R={repartidores}",
                repartidores,
                modelos,
                tasas_express,
                prob_lluvia,
            )
        )

    print("Resultados de simulacion")
    print("------------------------")
    for resultado in resultados:
        imprimir_resultado(resultado)

    recomendado = min(resultados, key=lambda x: x["pps_total"])
    peor = max(resultados, key=lambda x: x["pps_total"])
    print(
        "Escenario con mejor resultado: "
        f"{recomendado['nombre']} "
        f"(menor PPS total: {recomendado['pps_total']:.2f} min)"
    )
    print(
        "Escenario con peor resultado: "
        f"{peor['nombre']} "
        f"(mayor PPS total: {peor['pps_total']:.2f} min)"
    )


if __name__ == "__main__":
    main()
