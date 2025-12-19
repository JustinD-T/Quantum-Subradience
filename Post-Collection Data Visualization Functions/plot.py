#!/usr/bin/env python3
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

def process_dataframe(csv_path):
    """Reads a CSV file, processes timestamps, and cleans data."""
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
    return df

def calculate_fit(df):
    """Calculates a 2nd order polynomial fit in log-log space and its derivative."""
    # Prepare data for polynomial fit, excluding non-positive values for log.
    fit_df = df[df["hours"] > 0].copy()

    if len(fit_df) > 1:
        # Perform 2nd-order polynomial fit on log-transformed data
        log_x = np.log(fit_df["hours"])
        log_y = np.log(fit_df["pressure"])
        fit_coeffs = np.polyfit(log_x, log_y, 2)
        fit_poly = np.poly1d(fit_coeffs)
        fit_poly_deriv = fit_poly.deriv()

        # Generate points for the fit line
        x_fit = np.linspace(fit_df["hours"].min(), fit_df["hours"].max(), 200)
        log_x_fit = np.log(x_fit)
        log_y_fit = fit_poly(log_x_fit)
        y_fit = np.exp(log_y_fit)

        # Calculate the derivative of the fit function y = exp(P(log(x)))
        # dy/dx = y * P'(log(x)) * (1/x)
        y_deriv = y_fit * fit_poly_deriv(log_x_fit) / x_fit
        
        return x_fit, y_fit, y_deriv
    return None, None, None

# --- Main Script ---

# Define input files and output path
csv_paths = [Path("Recomp_NEW.csv"), Path("IsoRecomp_NEW.csv"), Path('Recomp_OLD.csv')] # Example file names
csv_titles = ['Full Chamber', 'Isolated Gauge', 'Full Chamber (Bad Valve)']
out_path = Path("pressure_vs_time_comparison.png")
deriv_out_path = Path("pressure_derivative_vs_time.png")

# Prepare plot
plt.figure(figsize=(6.5, 4))
colors = ['C0', 'C1', 'C2']
line_styles = ['-', '--', '-.']

# Process and plot each file
all_dfs = []
fit_results = []
for i, csv_path in enumerate(csv_paths):
    if not csv_path.exists():
        print(f"Warning: File not found at {csv_path}. Skipping.")
        continue

    df = process_dataframe(csv_path)
    all_dfs.append(df)

    # Plot data
    plt.plot(df["hours"], df["pressure"], marker="o", linestyle=line_styles[i], color=colors[i], label=f"Data: {csv_titles[i]}", alpha=0.1)

    # Add vertical line when pressure surpasses 0.1
    above_threshold = df[df["pressure"] > 0.1]
    if not above_threshold.empty:
        plt.axvline(x=above_threshold["hours"].iloc[0], color=colors[i], linestyle='-', alpha=0.6)

    # Calculate and plot best fit line
    x_fit, y_fit, y_deriv = calculate_fit(df)
    fit_results.append({'x': x_fit, 'y_deriv': y_deriv, 'path': csv_path})
    if x_fit is not None:
        plt.plot(x_fit, y_fit, color=colors[i], linestyle=':', label=f"Fit: {csv_titles[i]}")

# Configure and save the first plot
if not all_dfs:
    print("No data to plot. Exiting.")
    plt.close()
else:
    # Determine units for y-axis label from the first available dataframe
    first_df = all_dfs[0]
    unit_str = first_df['unit'].iloc[0] if 'unit' in first_df.columns and not first_df.empty else 'units'

    plt.legend()
    plt.xscale("linear")
    plt.yscale("linear")
    plt.xlabel("Time since start (hours)")
    plt.ylabel(f"Pressure ({unit_str})")
    plt.title("Pressure vs Time Comparison (Recompression)")
    plt.grid(True, which="both", ls="--", alpha=0.6)
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=300)
    print(f"Plot saved to {out_path}")
    plt.close()

    # --- Create and save the derivative plot ---
    plt.figure(figsize=(8, 4)) # Increased width to accommodate legend
    has_deriv_data = False
    STEADY_STATE_POINTS = 20 # Number of final points to average for steady state

    for i, result in enumerate(fit_results):
        if result['x'] is not None and result['y_deriv'] is not None:
            plt.plot(result['x'], result['y_deriv'], color=colors[i], linestyle=':', label=f"Fit Derivative: {csv_titles[i]}")
            has_deriv_data = True

            # Calculate and plot steady state of the derivative
            num_points = len(result['y_deriv'])
            if num_points > 0:
                # Use last points for the mean, or all points if there are fewer than STEADY_STATE_POINTS
                points_to_avg = min(num_points, STEADY_STATE_POINTS)
                steady_state_value = np.mean(result['y_deriv'][-points_to_avg:])
                
                # Plot horizontal line for steady state
                plt.axhline(y=steady_state_value, color=colors[i], linestyle='--', 
                            label=f"Steady State: {csv_titles[i]} \n ({steady_state_value:.2e}) (mbar/hour)")
    
    # Move legend to the side
    ax = plt.gca()
    box = ax.get_position()
    ax.set_position([box.x0, box.y0, box.width * 1, box.height])

    # Put a legend to the right of the current axis
    ax.legend(loc='center left', bbox_to_anchor=(1, 0.5))


    if has_deriv_data:
        # plt.legend()
        plt.xlabel("Time since start (hours)")
        plt.ylabel(f"Derivative of Pressure Fit (d/dt) [{unit_str}/hour]")
        plt.title("Derivative of Pressure Fit vs. Time (Recompression)")
        plt.grid(True, which="both", ls="--", alpha=0.6)
        plt.tight_layout()
        plt.savefig(deriv_out_path, dpi=300)
        print(f"Derivative plot saved to {deriv_out_path}")
    else:
        print("No derivative data to plot.")
    
    # plt.show() # uncomment to display interactively
    plt.close()
