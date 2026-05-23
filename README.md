# 🛵 Delivery System Simulator

A discrete-event simulation of a food delivery operation, built to analyze how different numbers of couriers affect service performance. The simulator uses real historical order data to fit statistical distributions and runs multiple replicas per scenario to produce stable, averaged results.

---

## Table of Contents

- [Overview](#overview)
- [How the Simulation Works](#how-the-simulation-works)
- [Dataset](#dataset)
- [Metrics](#metrics)
- [Installation](#installation)
- [Usage](#usage)
- [Project Structure](#project-structure)

---

## Overview

The goal is to answer a practical operations question: **how many couriers does a delivery service actually need?**

The simulator models a full day of orders (starting at 9:00 AM) for a given delivery distance radius. It tests scenarios with 1 to 4 couriers and compares them across service time, queue length, and courier idle time. The best scenario is selected using a combined efficiency score that balances quality of service against operational cost.

---

## How the Simulation Works

The simulation follows a **discrete-event** approach: time jumps from event to event (order arrivals and delivery completions) rather than ticking forward in fixed steps.

### 1. Data Loading & Filtering

Historical orders are loaded from a CSV file and filtered by a maximum delivery distance (e.g., only orders within 2 km or 3 km). This allows the model to be calibrated separately for different service zones.

### 2. Statistical Model Fitting (FDPs)

From the filtered data, the simulator fits probability distributions to key variables using `scipy.stats`:

| Variable | Distribution | Notes |
|---|---|---|
| Inter-arrival time (general) | Beta Prime | Time between consecutive orders |
| Inter-arrival time by time slot | Truncated Pareto / Beta Prime / Exp-Weib | Fitted per slot: morning, midday, afternoon, night |
| Attention time — normal weather | Gauss Hypergeometric | Based on distance × speed formula |
| Attention time — rainy weather | Gauss Hypergeometric | Same formula, doubled travel time |
| Order value | Rice (3 km) / Levy Stable (2 km) | Fitted to historical order values |

Attention time (TA) is calculated deterministically from order characteristics before fitting:

```
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

Each scenario (courier count) is run `REPLICAS` times (default: 10) and results are averaged. This smooths out randomness and produces more reliable estimates.

### 5. Scenario Comparison

The best scenario is selected by minimizing an **efficiency score** that combines normalized PPS (service time) and normalized courier count — giving equal weight to quality and cost.

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

The dataset covers ~60 days of orders across several Buenos Aires neighborhoods (Palermo, Almagro, Caballito, etc.), with distances ranging from 0.3 to 3.0 km and order values between $7,000 and $29,400 ARS.

---

## Metrics

| Metric | Full Name | Description |
|---|---|---|
| **PPS** | Promedio en el Sistema (Average Time in System) | Average minutes from order arrival to delivery completion. Reported separately for normal and express orders. Lower is better. |
| **PTO** | Percentage Time Off | Percentage of the simulated day that a courier spent idle (no active delivery). Higher PTO = lower utilization. |
| **Cola promedio** | Average Queue Length | Time-weighted average number of orders waiting in queue. |
| **Cola máxima** | Maximum Queue Length | Peak number of orders simultaneously waiting. |
| **Pedidos completados** | Completed Orders | Total orders delivered during the simulated day. |
| **Corridas con lluvia** | Rainy Replicas | How many of the 10 replicas had rain (affects TA). |

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
python simu_grupo_6.py
```

You will be prompted to choose a delivery distance to simulate:

```
¿Que distancia desea simular? [2, 3](o presione Enter para simular todas):
```

- Enter `2` to simulate only orders within 2 km.
- Enter `3` to simulate only orders within 3 km.
- Press **Enter** to run both distances sequentially.

### Example Output

```
============================================================
 SIMULACION PARA DISTANCIA = 2 KM
============================================================

Simulando escenario con 1 repartidores...
Simulando escenario con 2 repartidores...
...

Escenario: (R = 2 | 2 km)
- Repartidores: 2
- Pedidos completados: 79
- PPS total: 11.66 min
- PTO promedio: 72.15%
- Cola maxima normal: 3

Escenario con mejor resultado: (R = 2 | 2 km) (menor PPS total: 11.66 min)
```

### Configuration

Key constants at the top of `simu_grupo_6.py`:

| Constant | Default | Description |
|---|---|---|
| `REPLICAS` | `10` | Number of simulation runs per scenario |
| `ESCENARIOS_REPARTIDORES` | `[1, 2, 3, 4]` | Courier counts to test |
| `DISTANCIAS` | `[2, 3]` | Distance radii to simulate (km) |
| `SEMILLA` | `42` | Random seed for reproducibility |

---

## Project Structure

```
.
├── simu_grupo_6.py        # Main simulation script
├── pedidos_delivery.csv   # Historical order dataset
└── README.md
```
