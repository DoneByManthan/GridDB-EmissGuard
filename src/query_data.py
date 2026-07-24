# query_data.py
# Reads emission data from GridDB, computes per-vehicle AQI scores,
# detects cross-sensor emission correlations, and returns fleet-wide status.

import os
import sys

from griddb_init import griddb

from vehicles import VEHICLES, EMISSION_RULES, SENSOR_WEIGHTS, VEHICLE_WEIGHTS, aqi_label

# ── Connection parameters ─────────────────────────────────────────────────────
NOTIFICATION_MEMBER = os.environ.get("GRIDDB_NOTIFICATION_MEMBER", "127.0.0.1:10001")
CLUSTER_NAME        = os.environ.get("GRIDDB_CLUSTER_NAME",        "myCluster")
USERNAME            = os.environ.get("GRIDDB_USERNAME",            "admin")
PASSWORD            = os.environ.get("GRIDDB_PASSWORD",            "admin")


def get_gridstore():
    """Return a GridDB store connection."""
    factory = griddb.StoreFactory.get_instance()
    return factory.get_store(
        notification_member=NOTIFICATION_MEMBER,
        cluster_name=CLUSTER_NAME,
        username=USERNAME,
        password=PASSWORD,
    )


# ── TQL helpers ───────────────────────────────────────────────────────────────

def query_recent(store, vehicle_id, limit=30):
    """
    Retrieve the most recent `limit` readings for a vehicle using TQL.
    'order by timestamp desc' → index 0 is always the latest reading.
    """
    container = store.get_container(VEHICLES[vehicle_id]["container"])
    if container is None:
        return []

    query = container.query(f"select * order by timestamp desc limit {limit}")
    rs    = query.fetch()

    readings = []
    while rs.has_next():
        row = rs.next()
        readings.append({
            "timestamp":   row[0].isoformat() if hasattr(row[0], "isoformat") else str(row[0]),
            "mq2":         row[1],
            "mq135":       row[2],
            "co2_ppm":     row[3],
            "co_ppm":      row[4],
            "nox_ppb":     row[5],
            "pm25_ugm3":   row[6],
            "temperature": row[7],
            "humidity":    row[8],
            "aqi_status":  row[9],
        })
    return readings


def query_history(store, vehicle_id, limit=200):
    """Return up to `limit` readings in chronological order (oldest first) for charts."""
    return list(reversed(query_recent(store, vehicle_id, limit=limit)))


# ── AQI risk scoring ──────────────────────────────────────────────────────────

def sensor_severity(value, normal_max, warning, critical):
    """
    Map a sensor value to 0.0–1.5 severity score.
      0.0       → within safe range
      0.0–0.30  → drifting toward warning
      0.30–1.00 → between warning and critical
      1.00–1.50 → past critical (danger zone)
    """
    if value <= normal_max:
        return 0.0
    elif value <= warning:
        return 0.30 * (value - normal_max) / max(warning - normal_max, 1e-9)
    elif value <= critical:
        return 0.30 + 0.70 * (value - warning) / max(critical - warning, 1e-9)
    else:
        return min(1.0 + ((value - critical) / max(abs(critical - warning), 1e-9)) * 0.5, 1.5)


def vehicle_aqi_score(vehicle_id, avgs):
    """Calculate 0–100 AQI score from averaged sensor values."""
    thr = VEHICLES[vehicle_id]["thresholds"]
    nrm = VEHICLES[vehicle_id]["normal"]

    scores = {
        "mq2":       sensor_severity(avgs["mq2"],       nrm["mq2"][1],       thr["mq2"]["warning"],       thr["mq2"]["critical"]),
        "mq135":     sensor_severity(avgs["mq135"],     nrm["mq135"][1],     thr["mq135"]["warning"],     thr["mq135"]["critical"]),
        "co2_ppm":   sensor_severity(avgs["co2_ppm"],   nrm["co2_ppm"][1],   thr["co2_ppm"]["warning"],   thr["co2_ppm"]["critical"]),
        "co_ppm":    sensor_severity(avgs["co_ppm"],    nrm["co_ppm"][1],    thr["co_ppm"]["warning"],    thr["co_ppm"]["critical"]),
        "nox_ppb":   sensor_severity(avgs["nox_ppb"],   nrm["nox_ppb"][1],   thr["nox_ppb"]["warning"],   thr["nox_ppb"]["critical"]),
        "pm25_ugm3": sensor_severity(avgs["pm25_ugm3"], nrm["pm25_ugm3"][1], thr["pm25_ugm3"]["warning"], thr["pm25_ugm3"]["critical"]),
    }
    weighted = sum(scores[k] * SENSOR_WEIGHTS[k] for k in SENSOR_WEIGHTS)
    return min(round(weighted * 100), 100)


# ── Single-vehicle health analysis ────────────────────────────────────────────

def analyze_vehicle(vehicle_id, readings):
    """
    Analyze a 5-reading rolling window and return vehicle health status dict.
    Rolling window suppresses temporary sensor noise (anti-flicker).
    """
    if not readings:
        return {
            "status":    "Unknown",
            "message":   "No data available.",
            "latest":    None,
            "aqi_score": 0,
            "aqi_label": "Unknown",
            "aqi_color": "#6B7280",
        }

    thr    = VEHICLES[vehicle_id]["thresholds"]
    name   = VEHICLES[vehicle_id]["display_name"]
    window = readings[:5]

    avgs = {
        k: sum(r[k] for r in window) / len(window)
        for k in ("mq2", "mq135", "co2_ppm", "co_ppm", "nox_ppb", "pm25_ugm3", "temperature", "humidity")
    }

    score        = vehicle_aqi_score(vehicle_id, avgs)
    label, color = aqi_label(score)

    # ── Dangerous: any sensor past critical ───────────────────────────────────
    dangerous = [
        k for k in ("mq2", "mq135", "co2_ppm", "co_ppm", "nox_ppb", "pm25_ugm3")
        if avgs[k] > thr[k]["critical"]
    ]
    if dangerous:
        return {"status": "Dangerous", "message": f"{name}: DANGEROUS — {', '.join(dangerous)} critical.",
                "latest": readings[0], "aqi_score": score, "aqi_label": label, "aqi_color": color, "avgs": avgs}

    # ── Poor: two or more sensors above warning ───────────────────────────────
    warn_sensors = [
        k for k in ("mq2", "mq135", "co2_ppm", "co_ppm", "nox_ppb", "pm25_ugm3")
        if avgs[k] > thr[k]["warning"]
    ]
    if len(warn_sensors) >= 2:
        return {"status": "Poor", "message": f"{name}: Poor air quality ({' & '.join(warn_sensors)}).",
                "latest": readings[0], "aqi_score": score, "aqi_label": label, "aqi_color": color, "avgs": avgs}

    # ── Moderate: one sensor above warning ────────────────────────────────────
    if len(warn_sensors) == 1:
        return {"status": "Moderate", "message": f"{name}: {warn_sensors[0]} above warning threshold.",
                "latest": readings[0], "aqi_score": score, "aqi_label": label, "aqi_color": color, "avgs": avgs}

    return {"status": "Safe", "message": f"{name}: All emissions within safe limits.",
            "latest": readings[0], "aqi_score": score, "aqi_label": label, "aqi_color": color, "avgs": avgs}


# ── Cross-sensor emission correlation detection ───────────────────────────────

def detect_emission_correlations(vehicle_statuses):
    """
    Detect cross-sensor emission correlations using EMISSION_RULES.
    Fires when a vehicle is in Poor or Dangerous state.
    """
    correlations = []
    danger_states = {"Poor", "Dangerous"}
    seen          = set()

    for rule in EMISSION_RULES:
        for vid, info in vehicle_statuses.items():
            if info.get("status") in danger_states:
                key = (rule["source"], rule["target"])
                if key not in seen:
                    seen.add(key)
                    correlations.append({
                        "vehicle_id": vid,
                        "source":     rule["source"],
                        "target":     rule["target"],
                        "message":    rule["message"],
                    })
                break

    return correlations


# ── Fleet-wide status ─────────────────────────────────────────────────────────

def get_fleet_status(store):
    """
    Query all vehicles, compute per-vehicle AQI, and produce a
    weighted fleet-wide emission index.
    Active correlations add a penalty of 8 points each (max +25).
    """
    vehicle_statuses = {}
    for vid in VEHICLES:
        readings              = query_recent(store, vid, limit=20)
        vehicle_statuses[vid] = analyze_vehicle(vid, readings)

    fleet_score = sum(
        vehicle_statuses[v]["aqi_score"] * VEHICLE_WEIGHTS[v]
        for v in VEHICLES
    )
    correlations  = detect_emission_correlations(vehicle_statuses)
    penalty       = min(len(correlations) * 8, 25)
    risk_score    = min(round(fleet_score + penalty), 100)
    fleet_label, fleet_color = aqi_label(risk_score)

    return {
        "vehicles":     vehicle_statuses,
        "correlations": correlations,
        "risk_score":   risk_score,
        "risk_label":   fleet_label,
        "risk_color":   fleet_color,
    }


# ── CLI verification ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        print("Connecting to GridDB ...")
        store = get_gridstore()
        print("✓ Connected\n")

        fleet = get_fleet_status(store)

        print("=== EMISSGUARD FLEET STATUS ===")
        for vid, s in fleet["vehicles"].items():
            print(
                f"  [{s['status']:10}] {VEHICLES[vid]['display_name']:15} "
                f"(AQI: {s['aqi_score']:3}/100): {s['message']}"
            )

        if fleet["correlations"]:
            print("\nEMISSION CORRELATION ALERTS:")
            for c in fleet["correlations"]:
                print(f"  {c['source']} → {c['target']}: {c['message'][:80]}...")
        else:
            print("\nNo emission correlations detected.")

        print(f"\n  Fleet Emission Index: {fleet['risk_score']} / 100  [{fleet['risk_label']}]")

    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)
