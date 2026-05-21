import random
import math

# invweibull
c_intervaloEntrePedidos = 9.483695881549721
loc_intervaloEntrePedidos = -487.33933467366745
scale_intervaloEntrePedidos =  646.6242381147263

def inversaDeLaProbabilidadAcumuladaIntervaloEntrePedidos(x):
    return loc_intervaloEntrePedidos + (scale_intervaloEntrePedidos ** c_intervaloEntrePedidos / math.log(1 / x)) ** (1 / c_intervaloEntrePedidos)

c_tiempoEntrega = 5.586531403642143
loc_tiempoEntrega = -125.50862490552205
scale_tiempoEntrega = 1521.0504701231052

# weibull_min
def inversaDeLaProbabilidadAcumuladaTiempoEntrega(x):
    k = math.e ** (- (-loc_tiempoEntrega / scale_tiempoEntrega) ** c_tiempoEntrega) # 0.9999991145575681
    return loc_tiempoEntrega + scale_tiempoEntrega * (-math.log(-x + k)) ** (1 / c_tiempoEntrega)

# Variables de control
cantidadMotos = 10

# Variables resultado
promedioTiempoEspera = 0
porcentajePersonasArrepentidas = 0
porcentajesTiemposOciosos = []

def arrepentimiento(tiempoActual, tiempoComprometidoMinimoMoto):
    tiempo = tiempoComprometidoMinimoMoto - tiempoActual
    
    return tiempo > 60 * 60 or not tiempo < 40 * 60 and random.random() < 0.5
    
def menorTCM(tiemposComprometidosMotos):
    global cantidadMotos

    min = 0

    for i in range(1, cantidadMotos):
        if tiemposComprometidosMotos[i] < tiemposComprometidosMotos[min]:
            min = i
    
    return min

def generarIntervaloEntrePedidos():
    r = random.uniform(1e-10, 1)
    
    return inversaDeLaProbabilidadAcumuladaIntervaloEntrePedidos(r)

def generarTiempoEntrega():
    r = random.uniform(0, 0.9999991145575681 - 1e-10)
        
    return inversaDeLaProbabilidadAcumuladaTiempoEntrega(r)

def simulacion():
    global promedioTiempoEspera, porcentajePersonasArrepentidas, porcentajesTiemposOciosos

    # Inicializaciones
    tiempoFinal = 2 * 365 * 6 * 60 * 60 * 60
    tiempoActual = 0
    cantidadPersonas = 0
    
    sumatoriaPersonasArrepentidas = 0
    sumatoriaTiempoEspera = 0
    tiempoProximoPedido = 0

    tiempoEntrega = 0

    tiemposComprometidosMotos = []
    sumatoriasTiemposOciosos = []
    for _ in range(cantidadMotos):
        tiemposComprometidosMotos.append(0)
        sumatoriasTiemposOciosos.append(0)

    # Simulación
    while tiempoActual < tiempoFinal:
        tiempoActual = tiempoProximoPedido
        
        tiempoProximoPedido = tiempoActual + generarIntervaloEntrePedidos()

        min = menorTCM(tiemposComprometidosMotos)

        if arrepentimiento(tiempoActual, tiemposComprometidosMotos[min]):
            sumatoriaPersonasArrepentidas += 1
        else:
            cantidadPersonas += 1
            
            tiempoEntrega = generarTiempoEntrega()

            if tiempoActual > tiemposComprometidosMotos[min]:
                sumatoriasTiemposOciosos[min] += tiempoActual - tiemposComprometidosMotos[min]
                tiemposComprometidosMotos[min] = tiempoActual + tiempoEntrega
                sumatoriaTiempoEspera += tiempoEntrega
            else:
                tiemposComprometidosMotos[min] += tiempoEntrega
                sumatoriaTiempoEspera += tiempoEntrega + tiemposComprometidosMotos[min] - tiempoActual
    
    
    promedioTiempoEspera = sumatoriaTiempoEspera / cantidadPersonas
    porcentajePersonasArrepentidas = sumatoriaPersonasArrepentidas * 100 / (sumatoriaPersonasArrepentidas + cantidadPersonas)

    for i in range(cantidadMotos):
        porcentajesTiemposOciosos.append(sumatoriasTiemposOciosos[i] / tiempoActual * 100)
    

simulacion()
print(f"\nCantidad de motos utilizada: {cantidadMotos}\n")
print(f"Promedio de tiempo de espera: {promedioTiempoEspera:.2f}\n")
print(f"Porcentaje de personas arrepentidas: {porcentajePersonasArrepentidas:.2f}%\n")

print(f"Promedios de tiempos ociosos:")
for i in range(len(porcentajesTiemposOciosos)):
    print(f"Moto {i + 1}: {porcentajesTiemposOciosos[i]:.2f}%")