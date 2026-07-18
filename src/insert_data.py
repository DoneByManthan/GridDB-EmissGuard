# insert_data.py
# GridDB connection, container setup, bulk dataset insert, and live heartbeat.
#
# Usage:
#   python insert_data.py           # seed historical dataset (1,480 rows)
#   python insert_data.py --live    # continuous 5-second heartbeat producer

import os
import sys
import time
import argparse
from datetime import datetime, timezone

import griddb_python as griddb

import sensor_simulator
from vehicles import VEHICLES

# ── Connection parameters ─────────────────────────────────────────────────────
NOTIFICATION_MEMBER = os.environ.get("GRIDDB_NOTIFICATION_MEMBER", "127.0.0.1:10001")
CLUSTER_NAME        = os.environ.get("GRIDDB_CLUSTER_NAME",        "myCluster")
USERNAME            = os.environ.get("GRIDDB_USERNAME",            "admin")
PASSWORD            = os.environ.get("GRIDDB_PASSWORD",            "admin")


def get_gridstore():
    """Return a GridDB store connection using the local notification member."""
    factory = griddb.StoreFactory.get_instance()
    return factory.get_store(
        notification_member=NOTIFICATION_MEMBER,
        cluster_name=CLUSTER_NAME,
        username=USERNAME,
        password=PASSWORD,
    )


def setup_containers(store):
    """
    Create one TIME_SERIES container per vehicle.

    Schema (columns in order):
      timestamp   TIMESTAMP  ← row key; UTC
      mq2         DOUBLE
      mq135       DOUBLE
      co2_ppm     DOUBLE
      co_ppm      DOUBLE
      nox_ppb     DOUBLE
      pm25_ugm3   DOUBLE
      temperature DOUBLE
      humidity    DOUBLE
      aqi_status  STRING     ← simulation label for ML

    put_container is idempotent — safe to call on existing containers.
    """
    containers = {}
    for vid, cfg in VEHICLES.items():
        con_info = griddb.ContainerInfo(
            cfg["container"],
            [
                ["timestamp",   griddb.Type.TIMESTAMP],
                ["mq2",         griddb.Type.DOUBLE],
                ["mq135",       griddb.Type.DOUBLE],
                ["co2_ppm",     griddb.Type.DOUBLE],
                ["co_ppm",      griddb.Type.DOUBLE],
                ["nox_ppb",     griddb.Type.DOUBLE],
                ["pm25_ugm3",   griddb.Type.DOUBLE],
                ["temperature", griddb.Type.DOUBLE],
                ["humidity",    griddb.Type.DOUBLE],
                ["aqi_status",  griddb.Type.STRING],
            ],
            griddb.ContainerType.TIME_SERIES,
        )
        containers[vid] = store.put_container(con_info)
        print(f"  ✓ Container ready: {cfg['container']}")
    return containers


def insert_dataset(store, dataset):
    """
    Bulk-insert the full simulated dataset using multi_put.
    multi_put writes rows to multiple containers in a single request,
    significantly improving ingestion throughput.
    """
    batch = {}
    for vid, readings in dataset.items():
        container_name = VEHICLES[vid]["container"]
        rows = []
        for r in readings:
            ts = datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00"))
            rows.append([
                ts,
                r["mq2"], r["mq135"], r["co2_ppm"], r["co_ppm"],
                r["nox_ppb"], r["pm25_ugm3"], r["temperature"],
                r["humidity"], r["aqi_status"],
            ])
        batch[container_name] = rows

    store.multi_put(batch)

    for vid, readings in dataset.items():
        print(f"  ✓ Inserted {len(readings)} rows → {VEHICLES[vid]['container']}")


def live_producer(store):
    """
    Continuously insert Safe readings every 5 seconds as a heartbeat.
    Keeps the EmissGuard dashboard feed alive between simulation runs.
    """
    print("EmissGuard Heartbeat Producer — sending Safe readings every 5 s")
    print("Press Ctrl+C to stop.\n")

    while True:
        try:
            ts    = datetime.now(timezone.utc)
            batch = {}
            for vid, cfg in VEHICLES.items():
                r = sensor_simulator.generate_reading(vid, "Safe", timestamp=ts)
                batch[cfg["container"]] = [[
                    ts,
                    r["mq2"], r["mq135"], r["co2_ppm"], r["co_ppm"],
                    r["nox_ppb"], r["pm25_ugm3"], r["temperature"],
                    r["humidity"], r["aqi_status"],
                ]]
            store.multi_put(batch)
            print(f"  [{ts.strftime('%H:%M:%S')}] Heartbeat sent — all vehicles safe.")
            time.sleep(5)

        except KeyboardInterrupt:
            print("\nProducer stopped.")
            break
        except Exception as e:
            print(f"  Producer error: {e}")
            time.sleep(10)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EmissGuard data inserter")
    parser.add_argument("--live", action="store_true", help="Run continuous heartbeat producer")
    args = parser.parse_args()

    try:
        print("Connecting to GridDB ...")
        store = get_gridstore()
        print("✓ Connected\n")

        print("Setting up containers ...")
        setup_containers(store)
        print()

        if args.live:
            live_producer(store)
        else:
            print("Generating vehicle emission dataset ...")
            dataset = sensor_simulator.generate_dataset(safe_count=120, escalate=True)
            total   = sum(len(v) for v in dataset.values())
            print(f"  Generated {total} total rows across {len(dataset)} vehicles\n")

            print("Inserting into GridDB ...")
            insert_dataset(store, dataset)
            print("\n✓ Dataset ingested successfully.")
            print("  Run: python query_data.py  to verify.")

    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)
