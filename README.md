# 🛵 Delivery System Simulator

A discrete-event simulation of a food delivery operation, built to analyze how different numbers of couriers affect service performance. The simulator uses historical order data to fit statistical distributions and runs multiple replicas per scenario to produce stable, averaged results.

---

## Table of Contents

- [Overview](#overview)
- [How the Simulation Works](#how-the-simulation-works)
- [Dataset](#dataset)
- [Metrics](#metrics)
- [Main Findings](#main-findings)
- [Installation](#installation)
- [Usage](#usage)
- [Project Structure](#project-structure)

---

## Overview

The goal is to answer a practical operations question: **how many couriers does a delivery service actually need?**

The simulator models a full day of orders, starting at 9:00 AM, for a given delivery distance radius. It tests scenarios with 1 to 4 couriers and compares them across service time, queue length, courier idle time, completed orders and simulated revenue.

Two delivery radii are analyzed separately: **2 km** and **3 km**. This allows the model to compare a more limited service area against a wider delivery coverage.

---

## How the Simulation Works

The simulation follows a **discrete-event** approach: time jumps from event to event, such as order arrivals and delivery completions, rather than ticking forward in fixed steps.

### 1. Data Loading & Filtering

Historical orders are loaded from a CSV file and filtered by a maximum delivery distance. For example, when simulating the 2 km scenario, only orders within 2 km are used to calibrate the model. The same logic is applied to the 3 km scenario.

### 2. Statistical Model Fitting (FDPs)

From the filtered data, the simulator fits probability distributions to key variables using `scipy.stats`. The fitted distributions are selected separately for each delivery radius.

| Variable | Distribution for 2 km | Distribution for 3 km | Notes |
|---|---|---|---|
| Inter-arrival time (general) | Beta Prime | Beta Prime | Time between consecutive orders |
| Inter-arrival time — morning | Truncated Pareto | Truncated Pareto | Fitted for the morning time slot |
| Inter-arrival time — midday | Dpareto Lognormal | Beta Prime | Fitted for the midday time slot |
| Inter-arrival time — afternoon | Generalized Gamma | Beta Prime | Fitted for the afternoon time slot |
| Inter-arrival time — night | Exponential Weibull | Exponential Weibull | Fitted for the night time slot |
| Attention time — normal weather | Burr | Gauss Hypergeometric | Delivery service time without rain |
| Attention time — rainy weather | Burr | Gauss Hypergeometric | Delivery service time with rain |
| Order value | Levy Stable | Rice | Fitted to historical order values |

Attention time (TA) is calculated deterministically from order characteristics before fitting:

```text
TA = 2 min (base) + distance × 4 min/km × 2 (round trip)
If raining: TA × 2
```

### 3. Event Loop

Each simulation day runs as follows:

- A rain flag is sampled from the historical rain probability.
- Orders arrive at random intervals drawn from the fitted inter-arrival distributions, which change based on the current time slot.
- Each order is classified as **express** or **normal** based on historical rates per time slot.
- Express orders are prioritized in a separate queue.
- When a courier becomes free, they pick up the highest-priority pending order.
- If all couriers are busy, the order waits in queue.
- The simulation ends when all orders have been delivered.

### 4. Multiple Replicas

Each scenario is run `REPLICAS` times. In the current configuration, `REPLICAS = 180`, so each courier-distance scenario is simulated over 180 independent days. Results are averaged to reduce randomness and obtain more stable estimates.

### 5. Scenario Comparison

Each scenario is compared using multiple performance indicators: total PPS, average queue length, maximum queue length, courier idle time, completed orders and simulated revenue.

The analysis focuses on finding a balanced configuration rather than only minimizing service time. A lower number of couriers may reduce resource usage, but it can increase waiting times and queue accumulation. On the other hand, adding too many couriers may reduce PPS but increase idle time.

---

## Dataset

**File:** `pedidos_delivery.csv`

Contains historical delivery orders with the following columns:

| Column | Description |
|---|---|
| `id_pedido` | Unique order identifier |
| `fecha_hora` | Order timestamp (`YYYY-MM-DD HH:MM:SS`) |
| `zona_destino` | Destination neighborhood |
| `distancia_km` | Delivery distance in kilometers |
| `valor_pedido` | Order value in ARS |
| `clima` | Weather at time of order (`normal` / `lluvia`) |
| `dia_semana` | Day of the week |
| `prioridad` | Order priority (`normal` / `express`) |

The dataset covers approximately 60 days of orders across several Buenos Aires neighborhoods, including Palermo, Almagro and Caballito. Distances range from 0.3 km to 3.0 km, and order values range from $7,000 to $29,400 ARS.

---

## Metrics

| Metric | Full Name | Description |
|---|---|---|
| **PPS** | Promedio en el Sistema (Average Time in System) | Average minutes from order arrival to delivery completion. Reported separately for normal and express orders. Lower is better. |
| **PTO** | Percentage Time Off | Percentage of the simulated day that a courier spent idle, with no active delivery. Higher PTO means lower utilization. |
| **Cola promedio** | Average Queue Length | Time-weighted average number of orders waiting in queue. |
| **Cola máxima** | Maximum Queue Length | Peak number of orders simultaneously waiting. |
| **Pedidos completados** | Completed Orders | Total orders delivered during the simulated period. |
| **Corridas con lluvia** | Rainy Replicas | Number of replicas, out of 180, in which rain was simulated. |
| **Ganancia total** | Total Simulated Revenue | Sum of generated order values across all replicas for a scenario. |

---

## Main Findings

The simulations show that using only one courier leads to high PPS values and queue accumulation, especially when the delivery radius is extended to 3 km.

For both analyzed distances, the 3-courier scenario provides a strong operational balance. In the 2 km radius, it achieves low service times and almost negligible queue accumulation. In the 3 km radius, it maintains acceptable service times while achieving the highest total simulated revenue among the evaluated scenarios.

Therefore, the recommended base configuration is **3 couriers**, with the 3 km radius being the most convenient option when the objective is to increase revenue while maintaining an acceptable service level.

---

## Installation

**Requirements:** Python 3.8+

```bash
# Clone the repository
git clone https://github.com/your-username/your-repo-name.git
cd your-repo-name

# Install dependencies
pip install scipy
```

No additional setup needed — the standard library handles CSV reading and random number generation.

---

## Usage

```bash
python simulacion.py
```

You will be prompted to choose a delivery distance to simulate:

```text
¿Que distancia desea simular? [2, 3](o presione Enter para simular todas):
```

- Enter `2` to simulate only orders within 2 km.
- Enter `3` to simulate only orders within 3 km.
- Press **Enter** to run both distances sequentially.

### Example Output

```text
============================================================
 SIMULACION PARA DISTANCIA = 2 KM
============================================================

FDPs utilizadas (distancia: 2 km)
- TA normal: burr
- TA lluvia: burr
- IA general: betaprime
- IA manana: truncpareto
- IA mediodia: dpareto_lognorm
- IA tarde: gengamma
- IA noche: exponweib
- Valor pedido: levy_stable

Simulando escenario con 1 repartidores...
Simulando escenario con 2 repartidores...
Simulando escenario con 3 repartidores...
Simulando escenario con 4 repartidores...

Escenario: (R = 3 | 2 km)
- Repartidores: 3
- PPS total: 14.00 min
- Cola promedio normal: 0.06
- PTO promedio: 76.10%

============================================================
 SIMULACION PARA DISTANCIA = 3 KM
============================================================

Escenario: (R = 3 | 3 km)
- Repartidores: 3
- PPS total: 17.18 min
- Cola promedio normal: 0.11
- Ganancia total (180 días): $245,616,810.40
```

### Configuration

Key constants at the top of `simulacion.py`:

| Constant | Default | Description |
|---|---|---|
| `REPLICAS` | `180` | Number of simulated days per scenario |
| `ESCENARIOS_REPARTIDORES` | `[1, 2, 3, 4]` | Courier counts to test |
| `DISTANCIAS` | `[2, 3]` | Delivery distance radii to simulate, in km |
| `SEMILLA` | `42` | Random seed for reproducibility |

---

## Project Structure

```text
.
├── simulacion.py          # Main simulation script
├── pedidos_delivery.csv   # Historical order dataset
└── README.md              # Project documentation
```
