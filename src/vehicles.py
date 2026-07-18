# vehicles.py
# Central configuration for EmissGuard vehicle emission monitoring.
# Defines all vehicle profiles, sensor ranges, thresholds, and GridDB container names.
# Every other module imports from here — single source of truth.

# ── Vehicle sensor profiles ──────────────────────────────────────────────────
# Sensors per vehicle:
#   mq2          → LPG / Methane / Smoke / Hydrogen   (raw ADC 0–1023)
#   mq135        → CO2 / Ammonia / Benzene / Air QI   (raw ADC 0–1023)
#   co2_ppm      → estimated CO2 concentration (ppm)
#   co_ppm       → estimated CO concentration  (ppm)
#   nox_ppb      → estimated NOx               (ppb)
#   pm25_ugm3    → estimated PM2.5             (µg/m³)
#   temperature  → exhaust / ambient temperature (°C)
#   humidity     → ambient humidity (%)

VEHICLES = {
    "VH001": {
        "display_name":  "Truck Alpha",
        "vehicle_type":  "Heavy Truck",
        "fuel_type":     "Diesel",
        "container":     "emissguard_vh001",
        "description":   "Long-haul freight truck. Diesel engine, high NOx emitter.",
        "normal": {
            "mq2":         (100, 300),
            "mq135":       (100, 350),
            "co2_ppm":     (400, 600),
            "co_ppm":      (0,   9),
            "nox_ppb":     (10,  80),
            "pm25_ugm3":   (0,   15),
            "temperature": (55,  90),
            "humidity":    (35,  65),
        },
        "thresholds": {
            "mq2":         {"warning": 450,  "critical": 700},
            "mq135":       {"warning": 500,  "critical": 750},
            "co2_ppm":     {"warning": 1000, "critical": 2000},
            "co_ppm":      {"warning": 15,   "critical": 35},
            "nox_ppb":     {"warning": 150,  "critical": 300},
            "pm25_ugm3":   {"warning": 35,   "critical": 75},
            "temperature": {"warning": 120,  "critical": 160},
            "humidity":    {"warning": 80,   "critical": 95},
        },
    },
    "VH002": {
        "display_name":  "Sedan Beta",
        "vehicle_type":  "Passenger Car",
        "fuel_type":     "Petrol",
        "container":     "emissguard_vh002",
        "description":   "City commuter petrol car. Lower baseline but sensitive to cold starts.",
        "normal": {
            "mq2":         (80,  220),
            "mq135":       (80,  280),
            "co2_ppm":     (380, 550),
            "co_ppm":      (0,   7),
            "nox_ppb":     (5,   60),
            "pm25_ugm3":   (0,   10),
            "temperature": (45,  80),
            "humidity":    (40,  70),
        },
        "thresholds": {
            "mq2":         {"warning": 380,  "critical": 600},
            "mq135":       {"warning": 420,  "critical": 650},
            "co2_ppm":     {"warning": 900,  "critical": 1800},
            "co_ppm":      {"warning": 12,   "critical": 30},
            "nox_ppb":     {"warning": 120,  "critical": 250},
            "pm25_ugm3":   {"warning": 25,   "critical": 60},
            "temperature": {"warning": 110,  "critical": 150},
            "humidity":    {"warning": 82,   "critical": 96},
        },
    },
    "VH003": {
        "display_name":  "Bus Gamma",
        "vehicle_type":  "City Bus",
        "fuel_type":     "CNG",
        "container":     "emissguard_vh003",
        "description":   "CNG public transit bus. Lower CO2 but higher methane risk.",
        "normal": {
            "mq2":         (120, 280),
            "mq135":       (90,  260),
            "co2_ppm":     (360, 520),
            "co_ppm":      (0,   5),
            "nox_ppb":     (8,   50),
            "pm25_ugm3":   (0,   8),
            "temperature": (50,  85),
            "humidity":    (38,  68),
        },
        "thresholds": {
            "mq2":         {"warning": 500,  "critical": 800},
            "mq135":       {"warning": 440,  "critical": 680},
            "co2_ppm":     {"warning": 850,  "critical": 1700},
            "co_ppm":      {"warning": 10,   "critical": 25},
            "nox_ppb":     {"warning": 100,  "critical": 220},
            "pm25_ugm3":   {"warning": 20,   "critical": 50},
            "temperature": {"warning": 115,  "critical": 155},
            "humidity":    {"warning": 80,   "critical": 95},
        },
    },
    "VH004": {
        "display_name":  "Van Delta",
        "vehicle_type":  "Delivery Van",
        "fuel_type":     "Diesel",
        "container":     "emissguard_vh004",
        "description":   "Urban delivery diesel van. Frequent stop-start cycle increases PM2.5.",
        "normal": {
            "mq2":         (110, 310),
            "mq135":       (110, 330),
            "co2_ppm":     (410, 620),
            "co_ppm":      (0,   10),
            "nox_ppb":     (12,  90),
            "pm25_ugm3":   (0,   18),
            "temperature": (58,  92),
            "humidity":    (33,  63),
        },
        "thresholds": {
            "mq2":         {"warning": 460,  "critical": 720},
            "mq135":       {"warning": 510,  "critical": 760},
            "co2_ppm":     {"warning": 1050, "critical": 2100},
            "co_ppm":      {"warning": 16,   "critical": 38},
            "nox_ppb":     {"warning": 160,  "critical": 320},
            "pm25_ugm3":   {"warning": 38,   "critical": 80},
            "temperature": {"warning": 125,  "critical": 165},
            "humidity":    {"warning": 80,   "critical": 95},
        },
    },
    "VH005": {
        "display_name":  "SUV Epsilon",
        "vehicle_type":  "SUV",
        "fuel_type":     "Petrol",
        "container":     "emissguard_vh005",
        "description":   "Large petrol SUV. Higher fuel consumption, moderate emission profile.",
        "normal": {
            "mq2":         (90,  250),
            "mq135":       (90,  300),
            "co2_ppm":     (390, 570),
            "co_ppm":      (0,   8),
            "nox_ppb":     (8,   70),
            "pm25_ugm3":   (0,   12),
            "temperature": (48,  82),
            "humidity":    (38,  68),
        },
        "thresholds": {
            "mq2":         {"warning": 400,  "critical": 630},
            "mq135":       {"warning": 450,  "critical": 700},
            "co2_ppm":     {"warning": 950,  "critical": 1900},
            "co_ppm":      {"warning": 14,   "critical": 32},
            "nox_ppb":     {"warning": 130,  "critical": 270},
            "pm25_ugm3":   {"warning": 30,   "critical": 65},
            "temperature": {"warning": 112,  "critical": 152},
            "humidity":    {"warning": 81,   "critical": 96},
        },
    },
    "VH006": {
        "display_name":  "Bike Zeta",
        "vehicle_type":  "Motorcycle",
        "fuel_type":     "Petrol",
        "container":     "emissguard_vh006",
        "description":   "Two-wheeler petrol motorcycle. Small engine but high HC emissions.",
        "normal": {
            "mq2":         (70,  190),
            "mq135":       (70,  210),
            "co2_ppm":     (360, 510),
            "co_ppm":      (0,   6),
            "nox_ppb":     (5,   45),
            "pm25_ugm3":   (0,   8),
            "temperature": (40,  75),
            "humidity":    (42,  72),
        },
        "thresholds": {
            "mq2":         {"warning": 340,  "critical": 560},
            "mq135":       {"warning": 390,  "critical": 620},
            "co2_ppm":     {"warning": 850,  "critical": 1700},
            "co_ppm":      {"warning": 11,   "critical": 28},
            "nox_ppb":     {"warning": 110,  "critical": 230},
            "pm25_ugm3":   {"warning": 22,   "critical": 55},
            "temperature": {"warning": 105,  "critical": 145},
            "humidity":    {"warning": 83,   "critical": 97},
        },
    },
    "VH007": {
        "display_name":  "Lorry Eta",
        "vehicle_type":  "Heavy Lorry",
        "fuel_type":     "Diesel",
        "container":     "emissguard_vh007",
        "description":   "Mining/construction heavy lorry. Worst-case emission profile.",
        "normal": {
            "mq2":         (150, 380),
            "mq135":       (140, 370),
            "co2_ppm":     (450, 700),
            "co_ppm":      (2,   14),
            "nox_ppb":     (20,  110),
            "pm25_ugm3":   (5,   25),
            "temperature": (65,  100),
            "humidity":    (30,  60),
        },
        "thresholds": {
            "mq2":         {"warning": 550,  "critical": 850},
            "mq135":       {"warning": 560,  "critical": 830},
            "co2_ppm":     {"warning": 1200, "critical": 2400},
            "co_ppm":      {"warning": 22,   "critical": 45},
            "nox_ppb":     {"warning": 200,  "critical": 400},
            "pm25_ugm3":   {"warning": 50,   "critical": 100},
            "temperature": {"warning": 135,  "critical": 175},
            "humidity":    {"warning": 78,   "critical": 92},
        },
    },
    "VH008": {
        "display_name":  "Taxi Theta",
        "vehicle_type":  "Taxi",
        "fuel_type":     "CNG",
        "container":     "emissguard_vh008",
        "description":   "CNG taxi. High daily mileage, generally lower emission profile.",
        "normal": {
            "mq2":         (100, 240),
            "mq135":       (85,  240),
            "co2_ppm":     (370, 530),
            "co_ppm":      (0,   6),
            "nox_ppb":     (6,   55),
            "pm25_ugm3":   (0,   9),
            "temperature": (48,  83),
            "humidity":    (36,  66),
        },
        "thresholds": {
            "mq2":         {"warning": 450,  "critical": 720},
            "mq135":       {"warning": 420,  "critical": 660},
            "co2_ppm":     {"warning": 870,  "critical": 1750},
            "co_ppm":      {"warning": 12,   "critical": 28},
            "nox_ppb":     {"warning": 110,  "critical": 240},
            "pm25_ugm3":   {"warning": 22,   "critical": 52},
            "temperature": {"warning": 113,  "critical": 153},
            "humidity":    {"warning": 80,   "critical": 95},
        },
    },
}

# ── Emission correlation rules ────────────────────────────────────────────────
EMISSION_RULES = [
    {
        "source":  "co_ppm",
        "target":  "pm25_ugm3",
        "message": (
            "Incomplete Combustion: Elevated CO is correlated with rising PM2.5. "
            "Rich fuel mixture may be causing unburnt particulate matter in exhaust."
        ),
    },
    {
        "source":  "temperature",
        "target":  "nox_ppb",
        "message": (
            "Thermal NOx Formation: High exhaust temperature is correlated with "
            "elevated NOx levels. High-temperature combustion promotes nitrogen oxide formation."
        ),
    },
    {
        "source":  "mq2",
        "target":  "co2_ppm",
        "message": (
            "Rich Mixture Alert: High MQ2 (unburnt hydrocarbons/LPG) is correlated "
            "with elevated CO2. Fuel-rich combustion detected."
        ),
    },
]

# ── Sensor weights for AQI score ─────────────────────────────────────────────
SENSOR_WEIGHTS = {
    "mq2":       0.15,
    "mq135":     0.15,
    "co2_ppm":   0.10,
    "co_ppm":    0.20,
    "nox_ppb":   0.20,
    "pm25_ugm3": 0.20,
}

# ── Vehicle weights for fleet emission index ──────────────────────────────────
VEHICLE_WEIGHTS = {
    "VH001": 0.16,
    "VH002": 0.12,
    "VH003": 0.12,
    "VH004": 0.14,
    "VH005": 0.12,
    "VH006": 0.08,
    "VH007": 0.18,
    "VH008": 0.08,
}

# ── AQI status bands ──────────────────────────────────────────────────────────
AQI_BANDS = [
    (0,  20,  "Safe",      "#22C55E"),
    (20, 40,  "Moderate",  "#F59E0B"),
    (40, 65,  "Poor",      "#F97316"),
    (65, 100, "Dangerous", "#EF4444"),
]

def aqi_label(score):
    for lo, hi, label, color in AQI_BANDS:
        if score < hi:
            return label, color
    return "Dangerous", "#EF4444"
