#!/usr/bin/env python3
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

csv_path = Path("vacuum_log.csv")
out_path = Path("pressure_vs_time.png")

df = pd.read_csv(csv_path)

# If there's a timestamp column, convert and compute hours since start
if "timestamp" in df.columns:
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    start = df["timestamp"].iloc[0]
    df["hours"] = (df["timestamp"] - start).dt.total_seconds() / 3600.0
else:
    # otherwise use row index as time
    df["hours"] = range(len(df))

# Ensure numeric pressure column
df["pressure"] = pd.to_numeric(df["pressure"], errors="coerce")
df = df.dropna(subset=["pressure", "hours"]).reset_index(drop=True)

plt.figure(figsize=(6.5, 4))
plt.plot(df["hours"], df["pressure"], marker="o", linestyle="-")
plt.yscale("log")
plt.xlabel("Time since start (hours)")
plt.ylabel(f"Pressure ({df['unit'].iloc[0] if 'unit' in df.columns else 'units'})")
plt.title("Pressure vs Time (log scale)")
plt.grid(True, which="both", ls="--", alpha=0.6)
plt.tight_layout()
out_path.parent.mkdir(parents=True, exist_ok=True)
plt.savefig(out_path, dpi=300)
# plt.show()  # uncomment to display interactively
plt.close()
