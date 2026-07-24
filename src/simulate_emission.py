# simulate_emission.py
# Live four-phase emission escalation simulation for EmissGuard.
# Phases: Safe → Moderate → Poor → Dangerous cascade across all 8 vehicles.
#
# Usage:
#   python simulate_emission.py
#   (requires app.py to be running so sim flags work correctly)

import os
import sys
import time
import random
import json
import urllib.request
from datetime import datetime, timezone

from griddb_init import griddb

import insert_data
from vehicles import VEHICLES
from sensor_simulator import generate_reading

APP_URL = os.environ.get("APP_URL", "http://127.0.0.1:5050")

# ── Phase plan: vehicle_id → status per phase ─────────────────────────────────
PHASE_PLAN = {
    0: {v: "Safe" for v in VEHICLES},
    1: {**{v: "Safe" for v in VEHICLES},
        "VH001": "Moderate", "VH007": "Moderate"},
    2: {**{v: "Safe" for v in VEHICLES},
        "VH001": "Poor", "VH007": "Poor",
        "VH004": "Moderate", "VH002": "Moderate"},
    3: {"VH001": "Dangerous", "VH007": "Dangerous",
        "VH004": "Poor",      "VH002": "Poor",
        "VH003": "Moderate",  "VH005": "Moderate",
        "VH006": "Safe",      "VH008": "Safe"},
}

PHASE_LABELS = {0: "Safe", 1: "Moderate", 2: "Poor", 3: "DANGEROUS"}


def is_sim_active():
    try:
        with urllib.request.urlopen(f"{APP_URL}/api/sim/status", timeout=2) as r:
            return json.loads(r.read().decode()).get("active", False)
    except Exception:
        return True   # keep running if app unreachable


def start_sim():
    try:
        req = urllib.request.Request(f"{APP_URL}/api/sim/start", method="POST")
        urllib.request.urlopen(req, timeout=2)
    except Exception:
        pass


def trigger_emission():
    """
    Run a live emission simulation that escalates across all 8 vehicles.
    Phase advances every 4 ticks (4 seconds at 1 s/tick).
    Runs until the dashboard operator clicks 'Issue Resolved'.
    """
    try:
        store = insert_data.get_gridstore()
        print("=" * 52)
        print("  EmissGuard — Emission Simulation Starting")
        print("=" * 52)
        start_sim()

        i = 0
        while is_sim_active():
            ts    = datetime.now(timezone.utc)
            phase = min(i // 4, 3)
            batch = {}

            for vid, cfg in VEHICLES.items():
                status = PHASE_PLAN[phase].get(vid, "Safe")
                r      = generate_reading(vid, status, timestamp=ts)
                batch[cfg["container"]] = [[
                    ts,
                    r["mq2"], r["mq135"], r["co2_ppm"], r["co_ppm"],
                    r["nox_ppb"], r["pm25_ugm3"], r["temperature"],
                    r["humidity"], r["aqi_status"],
                ]]

            store.multi_put(batch)
            print(f"  [{ts.strftime('%H:%M:%S')}] Phase {phase}: {PHASE_LABELS[phase]}")
            i += 1
            time.sleep(1)

        print("\n  Issue Resolved by operator. Injecting recovery batch ...")
        ts    = datetime.now(timezone.utc)
        batch = {}
        for vid, cfg in VEHICLES.items():
            r = generate_reading(vid, "Safe", timestamp=ts)
            batch[cfg["container"]] = [[
                ts,
                r["mq2"], r["mq135"], r["co2_ppm"], r["co_ppm"],
                r["nox_ppb"], r["pm25_ugm3"], r["temperature"],
                r["humidity"], r["aqi_status"],
            ]]
        store.multi_put(batch)
        print("  ✓ Simulation complete. Fleet emissions normal.")

    except KeyboardInterrupt:
        print("\n  Simulation interrupted by user.")
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    trigger_emission()
