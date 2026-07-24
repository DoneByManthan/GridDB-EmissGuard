# ml_pipeline.py
# Machine Learning pipeline for EmissGuard.
# Reads all vehicle emission data from GridDB, builds features,
# trains three classifiers, evaluates them, and saves model artifacts.
#
# Tasks:
#   1. Binary classification   — Safe (0) vs Unsafe (1)
#   2. Multi-class             — Safe / Moderate / Poor / Dangerous
#   3. Risk-level classification — Low / Medium / High risk band
#
# ⚠️  All data is simulated. Models trained here are for demonstration
#    purposes only and must not be used for regulatory decisions.
#
# Usage:
#   python ml_pipeline.py              # fetch from GridDB + train
#   python ml_pipeline.py --from-csv  # reuse previously exported CSV

import os
import sys
import argparse
import warnings
import pickle

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    accuracy_score,
    roc_auc_score,
)

import matplotlib
matplotlib.use("Agg")   # non-interactive backend, safe for headless servers
import matplotlib.pyplot as plt
import seaborn as sns

from griddb_init import griddb
from vehicles import VEHICLES

warnings.filterwarnings("ignore")

# ── Paths ─────────────────────────────────────────────────────────────────────
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "ml", "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

CSV_PATH   = os.path.join(OUTPUT_DIR, "emissguard_dataset.csv")
MODEL_PATH = os.path.join(OUTPUT_DIR, "emissguard_models.pkl")

# ── Connection parameters ─────────────────────────────────────────────────────
NOTIFICATION_MEMBER = os.environ.get("GRIDDB_NOTIFICATION_MEMBER", "127.0.0.1:10001")
CLUSTER_NAME        = os.environ.get("GRIDDB_CLUSTER_NAME",        "myCluster")
USERNAME            = os.environ.get("GRIDDB_USERNAME",            "admin")
PASSWORD            = os.environ.get("GRIDDB_PASSWORD",            "admin")


# ── 1. Data fetch from GridDB ─────────────────────────────────────────────────

def fetch_from_griddb():
    """
    Connect to GridDB and pull every stored row from all 8 vehicle containers.
    Returns a pandas DataFrame with one row per sensor reading.
    """
    factory = griddb.StoreFactory.get_instance()
    store   = factory.get_store(
        notification_member=NOTIFICATION_MEMBER,
        cluster_name=CLUSTER_NAME,
        username=USERNAME,
        password=PASSWORD,
    )

    rows = []
    for vid, cfg in VEHICLES.items():
        container = store.get_container(cfg["container"])
        if container is None:
            print(f"  ⚠  Container not found: {cfg['container']} — skipping.")
            continue

        query = container.query("select * order by timestamp asc")
        rs    = query.fetch()

        count = 0
        while rs.has_next():
            row = rs.next()
            rows.append({
                "vehicle_id":   vid,
                "fuel_type":    cfg["fuel_type"],
                "vehicle_type": cfg["vehicle_type"],
                "timestamp":    str(row[0]),
                "mq2":          float(row[1]),
                "mq135":        float(row[2]),
                "co2_ppm":      float(row[3]),
                "co_ppm":       float(row[4]),
                "nox_ppb":      float(row[5]),
                "pm25_ugm3":    float(row[6]),
                "temperature":  float(row[7]),
                "humidity":     float(row[8]),
                "aqi_status":   str(row[9]),
            })
            count += 1
        print(f"  ✓ {count} rows fetched from {cfg['container']}")

    if not rows:
        raise RuntimeError(
            "No data found in GridDB. "
            "Run 'python insert_data.py' first to populate the database."
        )

    df = pd.DataFrame(rows)
    df.to_csv(CSV_PATH, index=False)
    print(f"  ✓ Dataset exported to {CSV_PATH}")
    return df


def load_from_csv():
    """Load a previously exported dataset from CSV."""
    if not os.path.exists(CSV_PATH):
        raise FileNotFoundError(
            f"CSV not found: {CSV_PATH}\n"
            "Run without --from-csv first to fetch from GridDB."
        )
    df = pd.read_csv(CSV_PATH)
    print(f"  ✓ Loaded {len(df)} rows from {CSV_PATH}")
    return df


# ── 2. Feature engineering ────────────────────────────────────────────────────

def build_features(df):
    """
    Construct the feature matrix X from raw sensor columns plus
    three domain-informed derived features:

      pulse_ratio     = mq2 / mq135          (combustion balance indicator)
      co_nox_ratio    = co_ppm / (nox_ppb + 1) (rich-vs-lean combustion proxy)
      pm_co_product   = pm25_ugm3 * co_ppm   (combined incomplete-combustion score)

    These derived features give the models additional signal without
    requiring extra hardware sensors.

    Labels:
      aqi_status_enc  — original 4-class label (Safe/Moderate/Poor/Dangerous)
      is_unsafe       — binary: 0 = Safe, 1 = anything else
    """
    df = df.copy()

    # Derived features
    df["pulse_ratio"]   = df["mq2"]       / (df["mq135"]  + 1e-6)
    df["co_nox_ratio"]  = df["co_ppm"]    / (df["nox_ppb"]  + 1.0)
    df["pm_co_product"] = df["pm25_ugm3"] *  df["co_ppm"]

    # Binary label
    df["is_unsafe"] = (df["aqi_status"] != "Safe").astype(int)

    FEATURE_COLS = [
        "mq2", "mq135", "co2_ppm", "co_ppm",
        "nox_ppb", "pm25_ugm3", "temperature", "humidity",
        "pulse_ratio", "co_nox_ratio", "pm_co_product",
    ]

    X = df[FEATURE_COLS].values
    return df, X, FEATURE_COLS


# ── 3. Plot helpers ───────────────────────────────────────────────────────────

def save_confusion_matrix(cm, class_names, title, filename):
    fig, ax = plt.subplots(figsize=(6, 5))
    sns.heatmap(
        cm, annot=True, fmt="d", cmap="Blues",
        xticklabels=class_names, yticklabels=class_names, ax=ax
    )
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Actual")
    ax.set_title(title)
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, filename)
    plt.savefig(path, dpi=120)
    plt.close()
    print(f"  ✓ Saved: {path}")


def save_feature_importance(importances, feature_names, title, filename):
    idx  = np.argsort(importances)[::-1]
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar(range(len(importances)), importances[idx], color="#6366F1")
    ax.set_xticks(range(len(importances)))
    ax.set_xticklabels(
        [feature_names[i] for i in idx], rotation=35, ha="right", fontsize=9
    )
    ax.set_ylabel("Importance")
    ax.set_title(title)
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, filename)
    plt.savefig(path, dpi=120)
    plt.close()
    print(f"  ✓ Saved: {path}")


def save_aqi_distribution(df, filename):
    order  = ["Safe", "Moderate", "Poor", "Dangerous"]
    colors = ["#22C55E", "#F59E0B", "#F97316", "#EF4444"]
    counts = df["aqi_status"].value_counts().reindex(order, fill_value=0)
    fig, ax = plt.subplots(figsize=(6, 4))
    counts.plot(kind="bar", color=colors, ax=ax, edgecolor="white")
    ax.set_xlabel("AQI Status")
    ax.set_ylabel("Count")
    ax.set_title("Dataset Distribution by AQI Status")
    ax.set_xticklabels(order, rotation=0)
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, filename)
    plt.savefig(path, dpi=120)
    plt.close()
    print(f"  ✓ Saved: {path}")


def save_sensor_boxplots(df, filename):
    sensors = ["mq2", "mq135", "co2_ppm", "co_ppm", "nox_ppb", "pm25_ugm3"]
    order   = ["Safe", "Moderate", "Poor", "Dangerous"]
    palette = ["#22C55E", "#F59E0B", "#F97316", "#EF4444"]
    fig, axes = plt.subplots(2, 3, figsize=(13, 7))

    for ax, sensor in zip(axes.flatten(), sensors):
        present = [s for s in order if s in df["aqi_status"].unique()]
        data    = [df[df["aqi_status"] == s][sensor].values for s in present]
        bp      = ax.boxplot(data, patch_artist=True, labels=present)
        for patch, color in zip(
            bp["boxes"],
            [palette[order.index(s)] for s in present]
        ):
            patch.set_facecolor(color)
            patch.set_alpha(0.72)
        ax.set_title(sensor.replace("_", " "))
        ax.set_xlabel("AQI Status")
        ax.tick_params(axis="x", labelsize=8)

    plt.suptitle("Sensor Readings by AQI Status", fontsize=12, fontweight="bold")
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, filename)
    plt.savefig(path, dpi=120)
    plt.close()
    print(f"  ✓ Saved: {path}")


def save_fuel_type_aqi(df, filename):
    """Bar chart showing AQI status breakdown per fuel type."""
    pivot = (
        df.groupby(["fuel_type", "aqi_status"])
        .size()
        .unstack(fill_value=0)
        .reindex(columns=["Safe", "Moderate", "Poor", "Dangerous"], fill_value=0)
    )
    colors = ["#22C55E", "#F59E0B", "#F97316", "#EF4444"]
    ax = pivot.plot(kind="bar", figsize=(7, 4), color=colors, edgecolor="white")
    ax.set_xlabel("Fuel Type")
    ax.set_ylabel("Reading Count")
    ax.set_title("AQI Status Distribution by Fuel Type")
    ax.legend(title="AQI Status", bbox_to_anchor=(1.01, 1), loc="upper left")
    plt.xticks(rotation=0)
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, filename)
    plt.savefig(path, dpi=120)
    plt.close()
    print(f"  ✓ Saved: {path}")


# ── 4. Model training and evaluation ─────────────────────────────────────────

def task_binary(X_tr, X_te, y_tr, y_te, scaler):
    """
    Task 1: Binary classification — Safe (0) vs Unsafe (1).
    Uses Logistic Regression for interpretability.
    """
    print("\n── Task 1: Binary Classification (Safe vs Unsafe) ──────────────────")

    X_tr_s = scaler.transform(X_tr)
    X_te_s = scaler.transform(X_te)

    model = LogisticRegression(max_iter=500, random_state=42, C=1.0)
    model.fit(X_tr_s, y_tr)

    y_pred = model.predict(X_te_s)
    acc    = accuracy_score(y_te, y_pred)

    try:
        y_prob = model.predict_proba(X_te_s)[:, 1]
        roc    = roc_auc_score(y_te, y_prob)
        print(f"  Accuracy : {acc:.4f}")
        print(f"  ROC-AUC  : {roc:.4f}")
    except Exception:
        print(f"  Accuracy : {acc:.4f}")

    print("\n  Classification Report:")
    print(classification_report(y_te, y_pred, target_names=["Safe", "Unsafe"]))

    cm = confusion_matrix(y_te, y_pred)
    save_confusion_matrix(
        cm, ["Safe", "Unsafe"],
        "Binary Classification — Safe vs Unsafe",
        "cm_binary.png"
    )
    return model


def task_multiclass(X_tr, X_te, y_tr, y_te, le, scaler, feature_names):
    """
    Task 2: Multi-class classification — Safe / Moderate / Poor / Dangerous.
    Uses Random Forest for robustness with non-linear decision boundaries.
    """
    print("\n── Task 2: Multi-class AQI Status Classification ───────────────────")

    X_tr_s = scaler.transform(X_tr)
    X_te_s = scaler.transform(X_te)

    model = RandomForestClassifier(
        n_estimators=150,
        max_depth=8,
        min_samples_split=4,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_tr_s, y_tr)

    y_pred      = model.predict(X_te_s)
    acc         = accuracy_score(y_te, y_pred)
    class_names = le.classes_.tolist()

    print(f"  Accuracy : {acc:.4f}")
    print("\n  Classification Report:")
    print(classification_report(y_te, y_pred, target_names=class_names))

    cm = confusion_matrix(y_te, y_pred)
    save_confusion_matrix(
        cm, class_names,
        "Multi-class AQI Status Confusion Matrix",
        "cm_multiclass.png"
    )
    save_feature_importance(
        model.feature_importances_,
        feature_names,
        "Random Forest Feature Importances",
        "feature_importance.png"
    )
    return model


def task_risk_level(X_tr, X_te, y_tr_state, y_te_state, scaler):
    """
    Task 3: Risk-level classification — Low / Medium / High.
    Maps the four AQI states to three risk bands and trains
    a Gradient Boosting classifier.

    Risk mapping:
      Safe       → 0  (Low)
      Moderate   → 1  (Medium)
      Poor       → 2  (High)
      Dangerous  → 2  (High)
    """
    print("\n── Task 3: Risk Level Classification (Gradient Boosting) ───────────")

    risk_map = {"Safe": 0, "Moderate": 1, "Poor": 2, "Dangerous": 2}
    y_tr = np.array([risk_map.get(s, 0) for s in y_tr_state])
    y_te = np.array([risk_map.get(s, 0) for s in y_te_state])

    X_tr_s = scaler.transform(X_tr)
    X_te_s = scaler.transform(X_te)

    model = GradientBoostingClassifier(
        n_estimators=100,
        learning_rate=0.1,
        max_depth=4,
        random_state=42,
    )
    model.fit(X_tr_s, y_tr)

    y_pred = model.predict(X_te_s)
    acc    = accuracy_score(y_te, y_pred)
    print(f"  Accuracy : {acc:.4f}")

    print("\n  Classification Report:")
    print(classification_report(
        y_te, y_pred,
        target_names=["Low Risk", "Medium Risk", "High Risk"],
        labels=[0, 1, 2],
    ))

    cm = confusion_matrix(y_te, y_pred, labels=[0, 1, 2])
    save_confusion_matrix(
        cm, ["Low Risk", "Medium Risk", "High Risk"],
        "Risk Level Classification Confusion Matrix",
        "cm_risk_level.png"
    )
    return model


# ── 5. Save artifacts ─────────────────────────────────────────────────────────

def save_artifacts(binary_model, multiclass_model, risk_model, scaler, le):
    artifacts = {
        "binary_clf":     binary_model,
        "multiclass_clf": multiclass_model,
        "risk_clf":       risk_model,
        "scaler":         scaler,
        "label_encoder":  le,
    }
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(artifacts, f)
    print(f"\n  ✓ All model artifacts saved to: {MODEL_PATH}")


# ── Main pipeline ─────────────────────────────────────────────────────────────

def run_pipeline(from_csv=False):
    print("=" * 62)
    print("  EmissGuard ML Pipeline")
    print("=" * 62)

    # Step 1: Load data
    print("\n[1/6] Loading data ...")
    df = load_from_csv() if from_csv else fetch_from_griddb()

    print(f"\n  Dataset shape  : {df.shape}")
    print(f"  Vehicles       : {df['vehicle_id'].nunique()}")
    print(f"  Fuel types     : {sorted(df['fuel_type'].unique())}")
    print(f"\n  AQI distribution:")
    print(df["aqi_status"].value_counts().to_string())

    # Step 2: Visualise dataset
    print("\n[2/6] Generating dataset visualisations ...")
    save_aqi_distribution(df,       "aqi_distribution.png")
    save_sensor_boxplots(df,        "sensor_boxplots.png")
    save_fuel_type_aqi(df,          "fuel_type_aqi.png")

    # Step 3: Feature engineering
    print("\n[3/6] Building feature matrix ...")
    df, X, feature_names = build_features(df)
    print(f"  Features ({len(feature_names)}): {feature_names}")
    print(f"  X shape        : {X.shape}")

    # Step 4: Preprocessing and train/test split
    print("\n[4/6] Preprocessing ...")

    le      = LabelEncoder()
    y_multi = le.fit_transform(df["aqi_status"].values)
    y_bin   = df["is_unsafe"].values
    y_state = df["aqi_status"].values

    print(f"  Label mapping  : {dict(zip(le.classes_, range(len(le.classes_))))}")

    X_tr, X_te, y_tr_m, y_te_m = train_test_split(
        X, y_multi, test_size=0.25, random_state=42, stratify=y_multi
    )
    _, _, y_tr_b, y_te_b = train_test_split(
        X, y_bin,   test_size=0.25, random_state=42, stratify=y_multi
    )
    _, _, y_tr_s, y_te_s = train_test_split(
        X, y_state, test_size=0.25, random_state=42, stratify=y_multi
    )

    scaler = StandardScaler()
    scaler.fit(X_tr)

    print(f"  Train samples  : {X_tr.shape[0]}")
    print(f"  Test  samples  : {X_te.shape[0]}")

    # Step 5: Train and evaluate all three models
    print("\n[5/6] Training models ...")
    binary_model     = task_binary(X_tr, X_te, y_tr_b, y_te_b, scaler)
    multiclass_model = task_multiclass(X_tr, X_te, y_tr_m, y_te_m, le, scaler, feature_names)
    risk_model       = task_risk_level(X_tr, X_te, y_tr_s, y_te_s, scaler)

    # Step 6: Save artifacts
    print("\n[6/6] Saving model artifacts ...")
    save_artifacts(binary_model, multiclass_model, risk_model, scaler, le)

    print("\n" + "=" * 62)
    print("  Pipeline complete.")
    print(f"  Outputs saved to: {OUTPUT_DIR}/")
    print("=" * 62)
    print("\n  Output files:")
    for f in sorted(os.listdir(OUTPUT_DIR)):
        path = os.path.join(OUTPUT_DIR, f)
        print(f"    {f:40s}  ({os.path.getsize(path):,} bytes)")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EmissGuard ML Pipeline")
    parser.add_argument(
        "--from-csv",
        action="store_true",
        help="Load dataset from previously exported CSV instead of GridDB",
    )
    args = parser.parse_args()

    try:
        run_pipeline(from_csv=args.from_csv)
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)
