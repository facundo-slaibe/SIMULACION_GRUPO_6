"""
================================================
======= SIMULADOR DE SISTEMA DE DELIVERY =======
================================================
Este programa simula un sistema de entregas con múltiples repartidores,
analizando diferentes escenarios para optimizar tiempos de espera y entregas.

"""
import csv
import math
import random
import warnings
from datetime import datetime

from scipy import stats


# Suprime advertencias de runtime que no son críticas
warnings.filterwarnings("ignore", category=RuntimeWarning)


# ============ CONFIGURACIÓN GENERAL ============
ARCHIVO = "pedidos_delivery.csv"  # Archivo con datos históricos de pedidos
MINUTOS_DIA = 24 * 60  # Minutos totales en un día (1440)
SEMILLA = 42  # Semilla para reproducibilidad de números aleatorios
REPLICAS = 10  # Cantidad de simulaciones por escenario (TODO: CAMBIAR TIEMPO A 180 dias)
ESCENARIOS_REPARTIDORES = [1, 2, 3, 4]  # Número de repartidores a probar


# ============ FUNCIONES DE FRANJAS HORARIAS ============

def franja_horaria(fecha):
    """
    Clasifica una fecha en una franja horaria (mañana, mediodía, tarde, noche).
    Usada para cargar datos históricos.
    
    Args:
        fecha: objeto datetime a clasificar
    
    Returns:
        string: "manana", "mediodia", "tarde" o "noche"
    """
    hora = fecha.hour
    if 8 <= hora < 12:
        return "manana"
    if 12 <= hora < 16:
        return "mediodia"
    if 16 <= hora < 20:
        return "tarde"
    return "noche"


def franja_por_minuto(tiempo):
    """
    Convierte un tiempo (en minutos) a su franja horaria.
    Usada durante la simulación.
    
    Args:
        tiempo: entero con minutos desde el inicio del día
    
    Returns:
        string: "manana", "mediodia", "tarde" o "noche"
    """
    hora = int((tiempo % MINUTOS_DIA) // 60)
    if 8 <= hora < 12:
        return "manana"
    if 12 <= hora < 16:
        return "mediodia"
    if 16 <= hora < 20:
        return "tarde"
    return "noche"


# ============ CARGA Y PROCESAMIENTO DE DATOS ============

def cargar_datos():
    """
    Carga datos históricos del archivo CSV y los procesa.
    Estructura: fecha, distancia, clima, prioridad, franja horaria.
    
    Returns:
        lista de diccionarios con datos de pedidos ordenados por fecha
    """
    pedidos = []

    # Abre y lee el archivo CSV
    with open(ARCHIVO, encoding="utf-8") as archivo:
        lector = csv.DictReader(archivo)
        for fila in lector:
            # Convierte string de fecha a objeto datetime
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

    # Ordena por fecha para mantener cronología
    pedidos.sort(key=lambda pedido: pedido["fecha"])
    return pedidos


# ============ ANÁLISIS ESTADÍSTICO ============

def calcular_score_eficiencia(resultado_corrida, resultados_todas_corridas):
        """
        Calcula un score que combina PPS y cantidad de repartidores (normalizado).
        Considera el costo de repartidores vs la mejora en tiempo de servicio.
        Menor score es mejor (más eficiente).
        """
        # Normalizar PPS a rango 0-1
        pps_values = [r["pps_total"] for r in resultados_todas_corridas]
        pps_min, pps_max = min(pps_values), max(pps_values)
        pps_normalizado = (resultado_corrida["pps_total"] - pps_min) / (pps_max - pps_min) if pps_max > pps_min else 0
        
        # Normalizar repartidores a rango 0-1
        rep_values = [r["repartidores"] for r in resultados_todas_corridas]
        rep_min, rep_max = min(rep_values), max(rep_values)
        rep_normalizado = (resultado_corrida["repartidores"] - rep_min) / (rep_max - rep_min) if rep_max > rep_min else 0
        
        # Combinar: igual peso a ambos factores (50% PPS, 50% costo repartidores)
        score = pps_normalizado + rep_normalizado
        return score


def ajustar_fdp(valores, nombre):
    """
    Ajusta una distribución de probabilidad a datos históricos.
    FDP = Función de Densidad de Probabilidad
    
    Args:
        valores: lista de valores observados en datos históricos
        nombre: nombre de distribución scipy a usar (ej: "betaprime")
    
    Returns:
        tupla (distribución, parámetros ajustados)
    """
    # Asegura que no hay valores cero o negativos
    valores = [max(0.01, valor) for valor in valores]
    distribucion = getattr(stats, nombre)  # Obtiene distribución de scipy
    parametros = distribucion.fit(valores)  # Ajusta parámetros a los datos
    return distribucion, parametros


def generar_muestra_ta(pedidos):
    """
    Calcula tiempos de atención (TA) basados en características del pedido.
    TA = Tiempo que tarda un repartidor en entregar un pedido.
    
    Fórmula: TA = 6 min (base) + distancia*4.5 + lluvia +/- prioridad
    
    Args:
        pedidos: lista de pedidos con distancia, clima, prioridad
    
    Returns:
        lista de tiempos de atención (minutos)
    """
    muestra = []

    for pedido in pedidos:
        base = 2  # Tiempo base para cualquier entrega
        viaje = pedido["distancia"] * 4 * 2  # 4 min por km, eso dos veces (ida y vuelta)
        lluvia = True if pedido["clima"] == "lluvia" else False  # 3 min extra si llueve
        if lluvia:
            total = (base + viaje) * 2  # Si llueve, el viaje se hace más lento (divide por 2)
        else:
            total = base + viaje
        muestra.append(max(1, total))  # Mínimo 1 minuto

    return muestra


def preparar_modelos(pedidos):
    """
    Prepara modelos estadísticos para simular eventos aleatorios.
    
    IA = Inter-Arrival time = tiempo entre llegadas de pedidos
    TA = Time Attention = tiempo de atención de repartidor
    
    Returns:
        tupla (modelos, tasas_express, prob_lluvia)
        - modelos: dict con distribuciones para IA y TA
        - tasas_express: dict con % de pedidos express por franja
        - prob_lluvia: probabilidad de lluvia en un día
    """
    # ========== INTER-ARRIVALS (IA) - TIEMPO ENTRE LLEGADAS ==========
    tiempos = [pedido["fecha"] for pedido in pedidos]

    # Calcula IA general (entre todos los pedidos)
    ia_general = []
    for anterior, actual in zip(tiempos, tiempos[1:]):
        ia_general.append(max(0.01, (actual - anterior).total_seconds() / 60))

    # Calcula IA por franja horaria (mañana, mediodía, tarde, noche)
    ia_por_franja = {
        "manana": [],
        "mediodia": [],
        "tarde": [],
        "noche": [],
    }

    for franja in ia_por_franja:
        # Filtra pedidos de esta franja
        pedidos_franja = [p for p in pedidos if p["franja"] == franja]
        pedidos_por_dia = {}

        # Agrupa por día para evitar saltos entre días
        for pedido in pedidos_franja:
            pedidos_por_dia.setdefault(pedido["dia"], []).append(pedido["fecha"])

        # Calcula IA dentro de cada día
        for lista_fechas in pedidos_por_dia.values():
            lista_fechas.sort()
            for anterior, actual in zip(lista_fechas, lista_fechas[1:]):
                ia_por_franja[franja].append(max(0.01, (actual - anterior).total_seconds() / 60))

    # ========== TIEMPOS DE ATENCIÓN (TA) ==========
    ta_todos = generar_muestra_ta(pedidos)  # TA general
    ta_normal = generar_muestra_ta([p for p in pedidos if p["clima"] == "normal"])
    ta_lluvia = generar_muestra_ta([p for p in pedidos if p["clima"] == "lluvia"])

    # Ajusta distribuciones de probabilidad a cada modelo
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

    # ========== TASA DE PEDIDOS EXPRESS ==========
    tasas_express = {}
    for franja in ["manana", "mediodia", "tarde", "noche"]:
        pedidos_franja = [p for p in pedidos if p["franja"] == franja]
        if pedidos_franja:
            tasas_express[franja] = sum(p["prioridad"] == "express" for p in pedidos_franja) / len(pedidos_franja)
        else:
            tasas_express[franja] = 0.15  # Valor por defecto si no hay datos

    # ========== PROBABILIDAD DE LLUVIA ==========
    dias = {p["dia"] for p in pedidos}
    dias_lluvia = {p["dia"] for p in pedidos if p["clima"] == "lluvia"}
    prob_lluvia = len(dias_lluvia) / len(dias)

    return modelos, tasas_express, prob_lluvia


# ============ GENERADORES DE EVENTOS ALEATORIOS ============

def generar_ia(modelos, tiempo_actual):
    """
    Genera un tiempo entre arribos aleatorio (tiempo hasta el próximo pedido).
    Usa la franja horaria actual para seleccionar la distribución.
    
    Args:
        modelos: dict con distribuciones ajustadas
        tiempo_actual: minutos desde inicio del día
    
    Returns:
        float: minutos hasta el próximo pedido
    """
    franja = franja_por_minuto(tiempo_actual)

    # Elige distribución según franja horaria
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
    """
    Genera un tiempo de atención aleatorio (cuánto tarda la entrega).
    Depende del clima (lluvia afecta el tiempo).
    
    Args:
        modelos: dict con distribuciones ajustadas
        hay_lluvia: booleano indicando si llueve hoy
    
    Returns:
        float: minutos de tiempo de atención
    """
    # Si llueve, usa TA para días lluviosos; si no, para días normales
    if hay_lluvia:
        distribucion, parametros = modelos["ta_lluvia"]
    else:
        distribucion, parametros = modelos["ta_normal"]

    return max(0.01, float(distribucion.rvs(*parametros)))


# ============ GESTIÓN DE REPARTIDORES ============

def buscar_repartidor_libre(tiempos_fin):
    """
    Busca el primer repartidor que esté libre (disponible).
    
    Args:
        tiempos_fin: lista con tiempo en que cada repartidor termina su actual pedido.
                     math.inf significa que está libre.
    
    Returns:
        int: índice del repartidor libre, o None si todos están ocupados
    """
    for i in range(len(tiempos_fin)):
        if math.isinf(tiempos_fin[i]):  # math.inf indica repartidor libre
            return i
    return None


def siguiente_entrega(tiempos_fin):
    """
    Encuentra cuál repartidor termina su entrega primero.
    
    Args:
        tiempos_fin: lista con tiempo final de cada repartidor
    
    Returns:
        tupla (índice del repartidor, tiempo de su entrega)
    """
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
    """
    Asigna un pedido a un repartidor, sacándolo de la cola correspondiente.
    Maneja dos colas: express (mayor prioridad) y normal.
    
    Args:
        cola_normal/express: listas de pedidos en espera
        tiempos_fin: cuándo termina cada repartidor
        tipos: tipo de pedido asignado a cada repartidor
        llegadas: hora de llegada del pedido asignado
        inicios_ociosos: cuándo comenzó el tiempo ocioso del repartidor
        tiempos_ociosos: tiempo total ocioso acumulado
        repartidor: índice del repartidor
        tiempo_actual: hora actual de la simulación
        tiempo_atencion: cuánto tardará esta entrega
    """
    # Prioriza pedidos express, luego normales
    if cola_express:
        llegada = cola_express.pop(0)
        tipo = "express"
    elif cola_normal:
        llegada = cola_normal.pop(0)
        tipo = "normal"
    else:
        # Sin pedidos, repartidor queda libre y empieza tiempo ocioso
        tiempos_fin[repartidor] = math.inf
        tipos[repartidor] = ""
        llegadas[repartidor] = 0
        inicios_ociosos[repartidor] = tiempo_actual
        return

    # Si estaba ocioso, acumula el tiempo ocioso
    if math.isinf(tiempos_fin[repartidor]):
        tiempos_ociosos[repartidor] += tiempo_actual - inicios_ociosos[repartidor]

    # Asigna el pedido al repartidor
    tiempos_fin[repartidor] = tiempo_actual + tiempo_atencion
    tipos[repartidor] = tipo
    llegadas[repartidor] = llegada


# ============ SIMULACIÓN DISCRETA ============

def simular_una_vez(nombre, repartidores, modelos, tasas_express, prob_lluvia):
    """
    Ejecuta UNA simulación completa de un día de entregas.
    Usa simulación de eventos discretos: procesa eventos (llegadas, entregas) en orden.
    
    Args:
        nombre: identificador del escenario
        repartidores: cantidad de repartidores
        modelos: distribuciones de probabilidad
        tasas_express: porcentaje de express por franja
        prob_lluvia: probabilidad de lluvia
    
    Returns:
        dict con métricas: PPS, colas, tiempos ociosos, etc.
    """
    tiempo_final = MINUTOS_DIA  # Simula hasta fin del día
    tiempo_actual = 540  # Comienza a las 9:00 AM (540 minutos desde medianoche)
    tiempo_proximo_pedido = generar_ia(modelos, tiempo_actual)  # Primer pedido
    hay_lluvia = random.random() <= prob_lluvia  # Define si llueve hoy

    # Colas de pedidos esperando repartidor
    cola_normal = []
    cola_express = []

    # Estado de cada repartidor
    tiempos_fin = [math.inf] * repartidores  # Cuándo termina cada uno (inf = libre)
    tipos = [""] * repartidores  # Tipo de pedido asignado
    llegadas = [0] * repartidores  # Hora de llegada del pedido
    inicios_ociosos = [0] * repartidores  # Cuándo comenzó a estar ocioso
    tiempos_ociosos = [0] * repartidores  # Tiempo ocioso acumulado

    # Métricas para cálculos finales
    sumatoria_pps_normal = 0  # Suma de tiempos en sistema (normal)
    sumatoria_pps_express = 0  # Suma de tiempos en sistema (express)
    completados_normal = 0  # Cantidad de normal completados
    completados_express = 0  # Cantidad de express completados

    area_cola_normal = 0  # Integral de cola normal en el tiempo
    area_cola_express = 0  # Integral de cola express en el tiempo
    max_cola_normal = 0  # Máximo tamaño de cola normal
    max_cola_express = 0  # Máximo tamaño de cola express

    # ========== LOOP DE SIMULACIÓN DISCRETA ==========
    while True:
        # Encuentra el próximo evento (entrega más cercana)
        indice_entrega, tiempo_proxima_entrega = siguiente_entrega(tiempos_fin)

        # Condición de salida: no hay más pedidos y todos los repartidores terminaron
        if tiempo_proximo_pedido > tiempo_final and math.isinf(tiempo_proxima_entrega):
            break

        # Determina qué evento ocurre primero (llegada o entrega)
        proximo_evento = min(tiempo_proximo_pedido, tiempo_proxima_entrega)
        
        # Avanza el tiempo y acumula área bajo la curva de colas
        delta = proximo_evento - tiempo_actual
        area_cola_normal += len(cola_normal) * delta
        area_cola_express += len(cola_express) * delta
        tiempo_actual = proximo_evento

        # ========== EVENTO: LLEGA UN NUEVO PEDIDO ==========
        if tiempo_proximo_pedido <= tiempo_proxima_entrega and tiempo_proximo_pedido <= tiempo_final:
            franja = franja_por_minuto(tiempo_actual)
            
            # Determina si es pedido express o normal
            if random.random() <= tasas_express[franja]:
                cola_express.append(tiempo_actual)
            else:
                cola_normal.append(tiempo_actual)

            # Actualiza máximo de cola
            max_cola_normal = max(max_cola_normal, len(cola_normal))
            max_cola_express = max(max_cola_express, len(cola_express))

            # Si hay repartidor libre, le asigna pedido
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

            # Genera hora del próximo pedido
            if tiempo_actual < tiempo_final:
                tiempo_proximo_pedido = tiempo_actual + generar_ia(modelos, tiempo_actual)
            else:
                tiempo_proximo_pedido = math.inf

        # ========== EVENTO: UN REPARTIDOR TERMINA ENTREGA ==========
        else:
            # Registra el pedido como completado
            if tipos[indice_entrega] == "normal":
                completados_normal += 1
                # PPS = Tiempo en sistema = tiempo_fin - tiempo_llegada
                sumatoria_pps_normal += tiempo_actual - llegadas[indice_entrega]
            elif tipos[indice_entrega] == "express":
                completados_express += 1
                sumatoria_pps_express += tiempo_actual - llegadas[indice_entrega]

            # Asigna nuevo pedido al repartidor libre
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

    # ========== FINALIZACIÓN ==========
    # Contabiliza tiempo ocioso de los repartidores al final del día
    for i in range(repartidores):
        if math.isinf(tiempos_fin[i]):
            tiempos_ociosos[i] += tiempo_actual - inicios_ociosos[i]

    completados_totales = completados_normal + completados_express
    sumatoria_total = sumatoria_pps_normal + sumatoria_pps_express

    return {
        "nombre": nombre,
        "repartidores": repartidores,
        # PPS = Promedio de Tiempo en Sistema (desde llegada hasta entrega)
        "pps_normal": sumatoria_pps_normal / completados_normal if completados_normal else 0,
        "pps_express": sumatoria_pps_express / completados_express if completados_express else 0,
        "pps_total": sumatoria_total / completados_totales if completados_totales else 0,
        "completados_normal": completados_normal,
        "completados_express": completados_express,
        "completados_totales": completados_totales,
        # Colas promedio = integral de cola / tiempo total
        "cola_promedio_normal": area_cola_normal / tiempo_actual if tiempo_actual else 0,
        "cola_promedio_express": area_cola_express / tiempo_actual if tiempo_actual else 0,
        "cola_maxima_normal": max_cola_normal,
        "cola_maxima_express": max_cola_express,
        # PTO = Percentage Time Off = porcentaje de tiempo ocioso de cada repartidor
        "pto": [tiempo_ocioso * 100 / tiempo_actual if tiempo_actual else 0 for tiempo_ocioso in tiempos_ociosos],
        "lluvia": hay_lluvia,
    }


# ============ ANÁLISIS DE RESULTADOS ============

def promedio(lista):
    """Calcula el promedio de una lista, retorna 0 si está vacía."""
    return sum(lista) / len(lista) if lista else 0


def resumir_escenario(nombre, repartidores, modelos, tasas_express, prob_lluvia):
    """
    Ejecuta múltiples simulaciones del mismo escenario y promedia los resultados.
    Esto reduce la variabilidad de la aleatoriedad.
    
    Args:
        nombre: identificador del escenario
        repartidores: cantidad de repartidores
        modelos, tasas_express, prob_lluvia: configuración de la simulación
    
    Returns:
        dict con promedios de REPLICAS simulaciones
    """
    resultados = []

    # Ejecuta REPLICAS veces la misma simulación
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

    # Promedia todas las métricas
    return {
        "nombre": nombre,
        "repartidores": repartidores,
        "pps_normal": promedio([r["pps_normal"] for r in resultados]),
        "pps_express": promedio([r["pps_express"] for r in resultados]),
        "pps_total": promedio([r["pps_total"] for r in resultados]),
        "completados": math.ceil(promedio([r["completados_totales"] for r in resultados])),
        "cola_promedio_normal": promedio([r["cola_promedio_normal"] for r in resultados]),
        "cola_promedio_express": promedio([r["cola_promedio_express"] for r in resultados]),
        "cola_maxima_normal": math.ceil(promedio([r["cola_maxima_normal"] for r in resultados])),
        "cola_maxima_express": math.ceil(promedio([r["cola_maxima_express"] for r in resultados])),
        "pto_promedio": promedio([promedio(r["pto"]) for r in resultados]),
        "corridas_con_lluvia": sum(r["lluvia"] for r in resultados),
    }


# ============ PRESENTACIÓN DE RESULTADOS ============

def imprimir_fdp(modelos, tasas_express, prob_lluvia):
    """Muestra qué distribuciones y probabilidades se usaron en la simulación."""
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
    """Imprime en formato legible los resultados de un escenario."""
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


# ============ FUNCIÓN PRINCIPAL ============

def main():
    """
    Orquesta todo el proceso de simulación:
    1. Carga datos históricos del CSV
    2. Prepara modelos estadísticos (FDPs)
    3. Prueba diferentes escenarios de repartidores
    4. Compara resultados y recomienda el mejor
    """
    # Fija semilla para reproducibilidad
    random.seed(SEMILLA)

    # Carga datos históricos y prepara modelos
    pedidos = cargar_datos()
    modelos, tasas_express, prob_lluvia = preparar_modelos(pedidos)

    # Muestra configuración de la simulación
    imprimir_fdp(modelos, tasas_express, prob_lluvia)

    # Prueba cada escenario (cantidad diferente de repartidores)
    resultados = []
    for repartidores in ESCENARIOS_REPARTIDORES:
        print(f"Simulando escenario con {repartidores} repartidores...")
        resultados.append(
            resumir_escenario(
                f"Escenario R={repartidores}",
                repartidores,
                modelos,
                tasas_express,
                prob_lluvia,
            )
        )

    # Imprime resultados de todos los escenarios
    print("Resultados de simulacion")
    print("------------------------")
    for resultado in resultados:
        imprimir_resultado(resultado)

    # Identifica y muestra el mejor y peor escenario
    # El mejor se define por una combinación de bajo PPS y bajo número de repartidores
    recomendado = min(resultados, key=lambda x: calcular_score_eficiencia(x, resultados))
    peor = max(resultados, key=lambda x: calcular_score_eficiencia(x, resultados))
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


# ============ PUNTO DE ENTRADA ============

if __name__ == "__main__":
    main()