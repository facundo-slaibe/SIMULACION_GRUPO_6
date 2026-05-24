# Contexto de trabajo - Simulacion Grupo 6

## Objetivo del proyecto
Este proyecto corresponde al TP5 de Simulacion: **simular un sistema real**.

El sistema elegido es un **servicio de delivery** con:
- llegadas de pedidos
- dos colas: `normal` y `express`
- una cantidad variable de repartidores `R`
- prioridad de atencion para pedidos `express`

La idea del trabajo es correr distintos escenarios cambiando **solo la cantidad de repartidores** y luego concluir, a partir de los resultados, cual escenario es mejor y cual peor.

## Archivos importantes
- `pedidos_delivery.csv`: dataset base del sistema real
- `prompt fdps.txt`: define las FDP elegidas por el grupo
- `SIMULACION - GUIAS - TP_5.pdf`: diagrama / guia del modelo del grupo
- `TP5 Simular un sistema real.pdf`: consigna general del TP
- `simu_grupo_6.py`: codigo actual de la simulacion
- `simulacion.py`: ejemplo de otro grupo usado como referencia de estilo simple

## FDPs definidas por el grupo
Segun `prompt fdps.txt`, las distribuciones a usar son:

- `TA`: `gausshyper`
- `IA general`: `betaprime`
- `IA manana`: `truncpareto`
- `IA mediodia`: `betaprime`
- `IA tarde`: `betaprime`
- `IA noche`: `exponweib`

## Modelo conceptual actual
La simulacion implementada sigue la idea del diagrama del grupo:

- evento 1: llega un pedido
- evento 2: se completa una entrega
- los pedidos se clasifican en `normal` o `express`
- si hay cola `express`, se atiende antes que `normal`
- si no hay repartidores libres, el pedido queda en cola
- si hay repartidor libre, se le asigna un pedido de inmediato

## Variables del sistema
### Variables de control
- `R`: cantidad de repartidores

### Variables aleatorias
- `IA`: tiempo entre llegadas
- `TA`: tiempo de atencion / entrega

### Variables de resultado
- `PPS normal`
- `PPS express`
- `PPS total`
- `PTO promedio`
- cola promedio y cola maxima para `normal` y `express`

## Definicion actual de escenarios
Actualmente el script corre **4 escenarios** y cambia solo `R`.

Lista actual:
- `R = 2`
- `R = 3`
- `R = 4`
- `R = 5`

Importante:
- **TA debe ser igual en todos los escenarios**
- el mejor o peor escenario **no se define a priori**
- se determina **despues de correr la simulacion**, comparando resultados

## Decision importante ya acordada
No usar factores de mejora/empeoramiento sobre `TA` por escenario.

Antes existia la idea de multiplicar `TA` para representar mejor o peor operacion, pero eso se descarto.

Ahora:
- todos los escenarios usan la misma logica de `TA`
- solo cambia la cantidad de repartidores

## Logica actual del codigo
El archivo `simu_grupo_6.py` fue simplificado para que quede cercano al estilo de `simulacion.py`.

Caracteristicas del codigo actual:
- estructura simple, lineal y con pocas abstracciones
- usa `scipy.stats`
- ajusta las distribuciones a partir del dataset
- separa `IA` por franjas horarias
- estima `TA` a partir de una muestra proxy, porque el dataset no trae un `TA` real explicito
- ejecuta varias replicas por escenario y promedia resultados

## Como se esta construyendo hoy el TA
El dataset no trae una columna real de tiempo de entrega.

Por eso el codigo actual genera una muestra proxy con esta logica:
- base fija
- componente por distancia
- penalizacion por lluvia
- pequeño ajuste para express

Luego sobre esa muestra se ajusta `gausshyper`.

Esto es una **aproximacion de trabajo**, no un dato real del dataset.

## Comportamiento observado en resultados recientes
Resultados observados:
- `PPS` relativamente alto
- `PTO` tambien alto en casi todos los escenarios

Interpretacion actual:
- la cola suele ser baja
- por lo tanto gran parte del `PPS` viene del `TA`
- el `PTO` alto indica capacidad ociosa, sobre todo cuando `R` sube

Lectura de eso:
- el sistema no esta necesariamente muy congestionado
- el tiempo en sistema esta dominado por el tiempo operativo de entrega
- puede haber demasiados repartidores para el nivel de demanda modelado

## Posibles mejoras futuras
Si otro agente va a continuar, los focos mas utiles serian:

### 1. Revisar la formula proxy de TA
Es probablemente la fuente principal del nivel de `PPS`.

Ideas:
- recalibrar el tiempo base
- recalibrar la relacion distancia -> minutos
- revisar la penalizacion por lluvia

### 2. Revisar si los escenarios de R son los adecuados
Si se quiere ver mas contraste entre escenarios, probar:
- `R = 1, 2, 3, 4`

### 3. Acercar nombres del codigo al diagrama del TP
Por ejemplo usar nombres mas alineados con:
- `TPP`
- `TPE`
- `Ns_N`
- `Ns_E`
- `PPS_N`
- `PPS_E`
- `PTO`

Esto no es estrictamente necesario para ejecutar, pero puede ayudar en la defensa / entrega.

### 4. Mejorar trazabilidad con la TEI / TEF
Si hace falta documentacion extra, agregar comentarios cortos en el codigo explicando:
- que bloque corresponde a llegada
- que bloque corresponde a entrega
- como se actualizan colas y repartidores

## Restricciones deseadas para futuras modificaciones
- mantener el codigo relativamente simple
- evitar sobreingenieria
- evitar estructuras demasiado complejas
- no volver a una version excesivamente abstracta o extensa
- priorizar un estilo parecido al ejemplo `simulacion.py`, pero adaptado al sistema de delivery del grupo

## Comando de ejecucion usado
Se estuvo ejecutando con:

```powershell
uv run --with scipy python simu_grupo_6.py
```

## Resumen ejecutivo para otro agente
Si retomás este proyecto:
- no cambies la idea central del sistema de delivery con colas `normal` y `express`
- mantené las FDP acordadas en `prompt fdps.txt`
- mantené escenarios definidos solo por cantidad de repartidores
- el punto mas sensible a revisar es la construccion de `TA`
- conservá el codigo en un nivel de simplicidad razonable
