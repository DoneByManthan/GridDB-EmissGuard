# app.py
# Flask REST API backend for EmissGuard dashboard.
# Serves the dashboard UI and all JSON API endpoints.
# Run: python app.py  →  http://localhost:5050

import os
import random
import threading
from datetime import datetime, timezone
from flask import Flask, jsonify, send_from_directory

import query_data
from vehicles import VEHICLES, aqi_label

app       = Flask(__name__, static_folder="../dashboard", static_url_path="")
_local    = threading.local()
sim_state = {"active": False}


def get_store():
    """Return (or lazily create) the per-thread GridDB connection."""
    if not hasattr(_local, "store") or _local.store is None:
        _local.store = query_data.get_gridstore()
    return _local.store


def inject_recovery():
    """Write one Safe reading per vehicle immediately after simulation ends."""
    try:
        store = get_store()
        ts    = datetime.now(timezone.utc)
        batch = {}
        for vid, cfg in VEHICLES.items():
            nrm = cfg["normal"]
            batch[cfg["container"]] = [[
                ts,
                random.uniform(*nrm["mq2"]),
                random.uniform(*nrm["mq135"]),
                random.uniform(*nrm["co2_ppm"]),
                random.uniform(*nrm["co_ppm"]),
                random.uniform(*nrm["nox_ppb"]),
                random.uniform(*nrm["pm25_ugm3"]),
                random.uniform(*nrm["temperature"]),
                random.uniform(*nrm["humidity"]),
                "Safe",
            ]]
        store.multi_put(batch)
        print(f"  [EmissGuard] Recovery batch injected at {ts.strftime('%H:%M:%S')}")
    except Exception as e:
        print(f"  [EmissGuard] Recovery injection failed: {e}")


# ── Static dashboard ──────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


# ── Fleet status ──────────────────────────────────────────────────────────────

@app.route("/api/fleet")
def fleet():
    """Main endpoint — all vehicle statuses + fleet emission index."""
    try:
        return jsonify(query_data.get_fleet_status(get_store()))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Per-vehicle endpoints ─────────────────────────────────────────────────────

@app.route("/api/vehicle/<vehicle_id>")
def vehicle(vehicle_id):
    """Full sensor history + current status for one vehicle."""
    if vehicle_id not in VEHICLES:
        return jsonify({"error": f"Unknown vehicle: {vehicle_id}"}), 404
    try:
        store   = get_store()
        history = query_data.query_history(store, vehicle_id, limit=200)
        recent  = query_data.query_recent(store, vehicle_id, limit=20)
        status  = query_data.analyze_vehicle(vehicle_id, recent)
        return jsonify({
            "vehicle_id":   vehicle_id,
            "display_name": VEHICLES[vehicle_id]["display_name"],
            "vehicle_type": VEHICLES[vehicle_id]["vehicle_type"],
            "fuel_type":    VEHICLES[vehicle_id]["fuel_type"],
            "description":  VEHICLES[vehicle_id]["description"],
            "status":       status,
            "history":      history,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/latest")
def latest():
    """Latest single reading per vehicle — lightweight polling endpoint."""
    try:
        store  = get_store()
        result = {}
        for vid in VEHICLES:
            rows = query_data.query_recent(store, vid, limit=1)
            result[vid] = rows[0] if rows else None
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/stats/<vehicle_id>")
def stats(vehicle_id):
    """Min / max / avg for all sensors over recent history."""
    if vehicle_id not in VEHICLES:
        return jsonify({"error": f"Unknown vehicle: {vehicle_id}"}), 404
    try:
        store   = get_store()
        history = query_data.query_history(store, vehicle_id, limit=200)
        if not history:
            return jsonify({"error": "No data available"}), 404

        sensors = ["mq2", "mq135", "co2_ppm", "co_ppm", "nox_ppb", "pm25_ugm3", "temperature", "humidity"]
        result  = {}
        for s in sensors:
            vals = [r[s] for r in history]
            result[s] = {
                "min":     round(min(vals), 2),
                "max":     round(max(vals), 2),
                "avg":     round(sum(vals) / len(vals), 2),
                "current": round(history[-1][s], 2),
            }
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Timeline ──────────────────────────────────────────────────────────────────

@app.route("/api/timeline")
def timeline():
    """Recent status-change events across all vehicles."""
    try:
        store  = get_store()
        events = []
        for vid in VEHICLES:
            history     = query_data.query_history(store, vid, limit=200)
            last_status = "Safe"
            for r in history:
                s = query_data.analyze_vehicle(vid, [r])["status"]
                if s != "Safe" and s != last_status:
                    events.append({
                        "timestamp":    r["timestamp"],
                        "vehicle_id":   vid,
                        "display_name": VEHICLES[vid]["display_name"],
                        "fuel_type":    VEHICLES[vid]["fuel_type"],
                        "status":       s,
                    })
                last_status = s
        events.sort(key=lambda e: e["timestamp"], reverse=True)
        return jsonify(events[:40])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Vehicle metadata ──────────────────────────────────────────────────────────

@app.route("/api/vehicles")
def vehicles_meta():
    """Vehicle metadata for sidebar and card population."""
    return jsonify({
        vid: {
            "display_name": cfg["display_name"],
            "vehicle_type": cfg["vehicle_type"],
            "fuel_type":    cfg["fuel_type"],
            "description":  cfg["description"],
        }
        for vid, cfg in VEHICLES.items()
    })


# ── Simulation control ────────────────────────────────────────────────────────

@app.route("/api/sim/start", methods=["POST"])
def sim_start():
    sim_state["active"] = True
    return jsonify({"status": "EmissGuard emission simulation active"})

@app.route("/api/sim/resolve", methods=["POST"])
def sim_resolve():
    sim_state["active"] = False
    inject_recovery()
    return jsonify({"status": "Issue resolved — emissions returning to normal"})

@app.route("/api/sim/status")
def sim_status():
    return jsonify(sim_state)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 52)
    print("  EmissGuard — Vehicle Emission Monitor")
    print("=" * 52)
    print("  Dashboard : http://localhost:5050")
    print("  Fleet API : http://localhost:5050/api/fleet")
    print()
    app.run(host="0.0.0.0", port=5050, debug=False)
