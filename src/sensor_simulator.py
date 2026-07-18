# sensor_simulator.py
# Generates realistic vehicle emission sensor readings for EmissGuard.
# Four-phase simulation: Safe → Moderate → Poor → Dangerous
#
# ⚠️  DISCLAIMER: All emission values are SIMULATED for educational/demo purposes.

import random
from datetime import datetime, timedelta, timezone
from vehicles import VEHICLES


def _interpolate(low, high, progress=None):
    """Smoothly interpolate between two values with optional random progress."""
    if progress is None:
        progress = random.uniform(0.0, 1.0)
    return low + progress * (high - low)


def generate_reading(vehicle_id, status="Safe", progress=0.0, timestamp=None):
    """
    Generate one emission reading for a vehicle at a given status.

    Parameters
    ----------
    vehicle_id : str   — key in VEHICLES dict
    status     : str   — "Safe" | "Moderate" | "Poor" | "Dangerous"
    progress   : float — 0.0–1.0, how far into the status phase we are
    timestamp  : datetime | None — defaults to now(UTC)

    Returns
    -------
    dict with all sensor fields + aqi_status label
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)

    cfg = VEHICLES[vehicle_id]
    nrm = cfg["normal"]
    thr = cfg["thresholds"]

    # ── Baseline values from normal operating range ───────────────────────────
    vals = {k: random.uniform(*nrm[k]) for k in nrm}

    # ── Per-sensor noise ──────────────────────────────────────────────────────
    noise = {
        "mq2":         random.uniform(-12, 12),
        "mq135":       random.uniform(-12, 12),
        "co2_ppm":     random.uniform(-15, 15),
        "co_ppm":      random.uniform(-0.5, 0.5),
        "nox_ppb":     random.uniform(-4, 4),
        "pm25_ugm3":   random.uniform(-1.5, 1.5),
        "temperature": random.uniform(-2, 2),
        "humidity":    random.uniform(-2, 2),
    }

    if status == "Safe":
        # Occasional micro-spikes (6% chance) — cold start or acceleration burst
        if random.random() < 0.06:
            vals["mq2"]       += random.uniform(40, 90)
            vals["co_ppm"]    += random.uniform(2, 5)
            vals["pm25_ugm3"] += random.uniform(5, 12)

    elif status == "Moderate":
        prog = random.uniform(0.2, 0.55)
        for key in ("mq2", "mq135", "co2_ppm", "co_ppm", "nox_ppb", "pm25_ugm3"):
            vals[key] = _interpolate(nrm[key][1], thr[key]["warning"], prog)
        vals["temperature"] = _interpolate(
            nrm["temperature"][1], thr["temperature"]["warning"], prog * 0.7
        )

    elif status == "Poor":
        prog = random.uniform(0.45, 0.85)
        for key in ("mq2", "mq135", "co2_ppm", "co_ppm", "nox_ppb", "pm25_ugm3"):
            vals[key] = _interpolate(thr[key]["warning"], thr[key]["critical"], prog * 0.7)
        vals["temperature"] = _interpolate(
            thr["temperature"]["warning"], thr["temperature"]["critical"], prog * 0.6
        )

    elif status == "Dangerous":
        prog = random.uniform(0.8, 1.25)
        for key in ("mq2", "mq135", "co2_ppm", "co_ppm", "nox_ppb", "pm25_ugm3"):
            overshoot = thr[key]["critical"] + (
                thr[key]["critical"] - thr[key]["warning"]
            ) * (prog - 1.0) * 0.4
            vals[key] = max(thr[key]["warning"], overshoot)
        vals["temperature"] = _interpolate(
            thr["temperature"]["warning"], thr["temperature"]["critical"], 0.9
        )

    # ── Apply noise and clip to physical limits ───────────────────────────────
    vals["mq2"]         = max(0,   min(vals["mq2"]         + noise["mq2"],         1023))
    vals["mq135"]       = max(0,   min(vals["mq135"]       + noise["mq135"],       1023))
    vals["co2_ppm"]     = max(300, min(vals["co2_ppm"]     + noise["co2_ppm"],     5000))
    vals["co_ppm"]      = max(0,   min(vals["co_ppm"]      + noise["co_ppm"],      200))
    vals["nox_ppb"]     = max(0,   min(vals["nox_ppb"]     + noise["nox_ppb"],     1000))
    vals["pm25_ugm3"]   = max(0,   min(vals["pm25_ugm3"]   + noise["pm25_ugm3"],   500))
    vals["temperature"] = max(20,  min(vals["temperature"] + noise["temperature"], 300))
    vals["humidity"]    = max(0,   min(vals["humidity"]     + noise["humidity"],    100))

    return {
        "vehicle_id":  vehicle_id,
        "timestamp":   timestamp.isoformat() + "Z",
        "mq2":         round(vals["mq2"],         1),
        "mq135":       round(vals["mq135"],       1),
        "co2_ppm":     round(vals["co2_ppm"],     1),
        "co_ppm":      round(vals["co_ppm"],      2),
        "nox_ppb":     round(vals["nox_ppb"],     1),
        "pm25_ugm3":   round(vals["pm25_ugm3"],   2),
        "temperature": round(vals["temperature"], 1),
        "humidity":    round(vals["humidity"],     1),
        "aqi_status":  status,
    }


def generate_dataset(safe_count=120, escalate=True):
    """
    Generate a full multi-phase dataset for all 8 vehicles.

    Phases (when escalate=True):
      1. Safe      — all vehicles normal                     (safe_count readings each)
      2. Moderate  — VH001, VH007 escalating                (30 readings)
      3. Poor      — VH001, VH007 poor; VH004, VH002 moderate (20 readings)
      4. Dangerous — VH001 & VH007 critical; others mixed   (15 readings)

    Total rows = 8 vehicles × (120 + 30 + 20 + 15) = 8 × 185 = 1,480 rows

    Returns
    -------
    dict { vehicle_id: [reading_dict, ...] }
    """
    vehicle_ids  = list(VEHICLES.keys())
    interval_sec = 15   # one reading every 15 seconds

    mod_count  = 30 if escalate else 0
    poor_count = 20 if escalate else 0
    crit_count = 15 if escalate else 0
    total      = safe_count + mod_count + poor_count + crit_count

    start_time = datetime.now(timezone.utc) - timedelta(seconds=total * interval_sec)
    dataset    = {v: [] for v in vehicle_ids}

    for i in range(total):
        ts = start_time + timedelta(seconds=i * interval_sec)

        # ── Phase 1: Safe ──────────────────────────────────────────────────────
        if i < safe_count:
            for v in vehicle_ids:
                dataset[v].append(generate_reading(v, "Safe", timestamp=ts))

        # ── Phase 2: Moderate ─────────────────────────────────────────────────
        elif i < safe_count + mod_count:
            prog = (i - safe_count) / mod_count
            for v in vehicle_ids:
                if v in ("VH001", "VH007"):
                    status = "Moderate" if prog < 0.6 else "Poor"
                elif v == "VH004":
                    status = "Moderate" if prog > 0.4 else "Safe"
                else:
                    status = "Safe"
                dataset[v].append(generate_reading(v, status, progress=prog, timestamp=ts))

        # ── Phase 3: Poor ─────────────────────────────────────────────────────
        elif i < safe_count + mod_count + poor_count:
            prog = (i - safe_count - mod_count) / poor_count
            for v in vehicle_ids:
                if v in ("VH001", "VH007"):
                    status = "Poor" if prog < 0.6 else "Dangerous"
                elif v in ("VH004", "VH002"):
                    status = "Moderate"
                elif v == "VH003":
                    status = "Moderate" if prog > 0.5 else "Safe"
                else:
                    status = "Safe"
                dataset[v].append(generate_reading(v, status, progress=prog, timestamp=ts))

        # ── Phase 4: Dangerous ────────────────────────────────────────────────
        else:
            prog = (i - safe_count - mod_count - poor_count) / crit_count
            for v in vehicle_ids:
                if v in ("VH001", "VH007"):
                    status = random.choice(["Dangerous", "Dangerous", "Poor"])
                elif v in ("VH004", "VH002"):
                    status = random.choice(["Poor", "Moderate", "Moderate"])
                elif v in ("VH003", "VH005"):
                    status = random.choice(["Moderate", "Safe", "Safe"])
                else:
                    status = "Safe"
                dataset[v].append(generate_reading(v, status, progress=prog, timestamp=ts))

    return dataset


# ── Self-test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    data  = generate_dataset()
    total = sum(len(v) for v in data.values())
    print(f"EmissGuard Sensor Simulator — {total} total rows generated\n")
    for vid, readings in data.items():
        r = readings[-1]
        print(
            f"  {VEHICLES[vid]['display_name']:15}  "
            f"MQ2={r['mq2']:6.1f}  MQ135={r['mq135']:6.1f}  "
            f"CO2={r['co2_ppm']:7.1f}ppm  CO={r['co_ppm']:5.2f}ppm  "
            f"NOx={r['nox_ppb']:6.1f}ppb  PM2.5={r['pm25_ugm3']:5.2f}µg/m³  "
            f"[{r['aqi_status']}]"
        )
