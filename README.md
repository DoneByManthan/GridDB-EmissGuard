# EmissGuard - Vehicle Emission Monitoring with GridDB

Real-time fleet emission monitoring system. Simulates 8 vehicles across
Diesel, Petrol, and CNG fuel types. Sensor data (MQ2, MQ135, CO₂, CO,
NOx, PM2.5, Temperature, Humidity) is generated, stored in **GridDB**
TIME_SERIES containers, and served to a live web dashboard.

---

## Architecture

```
Sensor Simulator (8 vehicles × 185 readings = 1,480 rows)
        │  multi_put (batch write)
        ▼
  GridDB - TIME_SERIES containers (emissguard_vh001 … emissguard_vh008)
        │  TQL: select * order by timestamp desc limit N
        ▼
  Flask REST API  ──────────────────►  Dashboard (http://localhost:5050)
        │
        ▼
  ML Pipeline (scikit-learn) — ml/outputs/
```

---

## Vehicles

| ID    | Name         | Type          | Fuel   |
|-------|-------------|--------------|--------|
| VH001 | Truck Alpha  | Heavy Truck   | Diesel |
| VH002 | Sedan Beta   | Passenger Car | Petrol |
| VH003 | Bus Gamma    | City Bus      | CNG    |
| VH004 | Van Delta    | Delivery Van  | Diesel |
| VH005 | SUV Epsilon  | SUV           | Petrol |
| VH006 | Bike Zeta    | Motorcycle    | Petrol |
| VH007 | Lorry Eta    | Heavy Lorry   | Diesel |
| VH008 | Taxi Theta   | Taxi          | CNG    |

---

## Sensors

| Sensor       | Unit   | Description                       |
|--------------|--------|-----------------------------------|
| mq2          | ADC    | LPG / Methane / Smoke / Hydrogen  |
| mq135        | ADC    | CO₂ / Ammonia / Benzene / Air QI  |
| co2_ppm      | ppm    | Carbon dioxide                    |
| co_ppm       | ppm    | Carbon monoxide                   |
| nox_ppb      | ppb    | Nitrogen oxides                   |
| pm25_ugm3    | µg/m³  | Fine particulate matter           |
| temperature  | °C     | Exhaust / ambient temperature     |
| humidity     | %      | Ambient humidity                  |

---

## Setup

```bash
cd EmissGuard
chmod +x setup.sh && ./setup.sh
source venv/bin/activate

# Set GridDB credentials (defaults match standard local install)
export GRIDDB_NOTIFICATION_MEMBER="127.0.0.1:10001"
export GRIDDB_CLUSTER_NAME="myCluster"
export GRIDDB_USERNAME="admin"
export GRIDDB_PASSWORD="admin"
```

---

## Running

```bash
cd src

# 1. Seed 1,480 rows into GridDB (8 vehicles × 185 readings)
python insert_data.py

# 2. Verify data
python query_data.py

# 3. Start API + dashboard
python app.py
# → Dashboard: http://localhost:5050

# 4. Optional: continuous heartbeat
python insert_data.py --live

# 5. Optional: live emission simulation
python simulate_emission.py

# 6. Run the ML pipeline (train 3 classifiers on GridDB data)
python ml_pipeline.py
# Outputs saved to ml/outputs/
```

---

## API Endpoints

| Endpoint                 | Description                              |
|--------------------------|------------------------------------------|
| `GET /`                  | EmissGuard dashboard UI                  |
| `GET /api/fleet`         | All vehicles + fleet emission index      |
| `GET /api/vehicle/<id>`  | Single vehicle history + AQI status      |
| `GET /api/stats/<id>`    | Min / max / avg per sensor               |
| `GET /api/latest`        | Latest reading per vehicle               |
| `GET /api/timeline`      | Emission event log                       |
| `GET /api/vehicles`      | Vehicle metadata                         |
| `POST /api/sim/start`    | Trigger emission simulation              |
| `POST /api/sim/resolve`  | Resolve simulation                       |
| `GET /api/sim/status`    | Check simulation state                   |

---

## ML Pipeline

The ML pipeline reads data directly from GridDB, engineers features, trains
three scikit-learn classifiers, and saves model artifacts to `ml/outputs/`.

```bash
cd src

# Fetch from GridDB, train all three models, save outputs
python ml_pipeline.py

# Reuse a previously exported CSV (no GridDB connection needed)
python ml_pipeline.py --from-csv
```

### Three ML Tasks

| Task | Algorithm | Target |
|------|-----------|--------|
| Binary classification | Logistic Regression | Safe (0) vs Unsafe (1) |
| Multi-class classification | Random Forest | Safe / Moderate / Poor / Dangerous |
| Risk level classification | Gradient Boosting | Low / Medium / High risk band |

### Feature Set (11 features)

Raw sensors: `mq2`, `mq135`, `co2_ppm`, `co_ppm`, `nox_ppb`, `pm25_ugm3`, `temperature`, `humidity`

Derived features:
- `pulse_ratio`   = mq2 / mq135 (combustion balance indicator)
- `co_nox_ratio`  = co_ppm / (nox_ppb + 1) (rich-vs-lean combustion proxy)
- `pm_co_product` = pm25_ugm3 * co_ppm (combined incomplete-combustion score)

### Output Files (`ml/outputs/`)

| File | Description |
|------|-------------|
| `emissguard_dataset.csv` | Full dataset exported from GridDB |
| `emissguard_models.pkl` | All three trained models + scaler + label encoder |
| `aqi_distribution.png` | Dataset class distribution bar chart |
| `sensor_boxplots.png` | Sensor value distributions by AQI status |
| `fuel_type_aqi.png` | AQI breakdown per fuel type |
| `cm_binary.png` | Binary classification confusion matrix |
| `cm_multiclass.png` | Multi-class confusion matrix |
| `cm_risk_level.png` | Risk level confusion matrix |
| `feature_importance.png` | Random Forest feature importance chart |

## Project Structure

```
EmissGuard/
├── src/
│   ├── vehicles.py            # Sensor config, thresholds, container names
│   ├── sensor_simulator.py    # Emission data generator (4 phases)
│   ├── insert_data.py         # GridDB containers + bulk insert + heartbeat
│   ├── query_data.py          # TQL queries + AQI scoring + correlations
│   ├── app.py                 # Flask REST API (serves dashboard too)
│   ├── simulate_emission.py   # Live escalation simulation
│   └── ml_pipeline.py         # scikit-learn ML pipeline (3 classifiers)
├── dashboard/
│   └── index.html             # EmissGuard monitoring dashboard
├── ml/
│   └── outputs/               # ML plots + model artifacts (auto-created)
├── requirements.txt
├── setup.sh
└── README.md
```

---

## GridDB Containers

One `TIME_SERIES` container per vehicle: `emissguard_vh001` … `emissguard_vh008`

| Column      | GridDB Type | Notes             |
|-------------|-------------|-------------------|
| timestamp   | TIMESTAMP   | Row key, UTC      |
| mq2         | DOUBLE      | ADC 0–1023        |
| mq135       | DOUBLE      | ADC 0–1023        |
| co2_ppm     | DOUBLE      | ppm               |
| co_ppm      | DOUBLE      | ppm               |
| nox_ppb     | DOUBLE      | ppb               |
| pm25_ugm3   | DOUBLE      | µg/m³             |
| temperature | DOUBLE      | °C                |
| humidity    | DOUBLE      | %                 |
| aqi_status  | STRING      | Simulation label  |
