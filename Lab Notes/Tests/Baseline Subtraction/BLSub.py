import numpy as np
import pandas as pd
import os
import matplotlib.pyplot as plt
from scipy.signal import savgol_filter

# --- 1. Configuration & Paths ---
experiment_name = "20260127-SIGNAL_RUN"
baseline_file = r"Experimental Values\Baseline_Jan23_BaselineTest.npy"
new_data_file = rf'ExperimentLogs\ExperimentLog_20260127-174737.csv'
save_dir = r"Lab Notes\Tests\Noise Floor (Jan 20)\Plots\Signal_Detection"

# Target CO Line (example: replace with your specific transition frequency)
CO_LINE_FREQ_GHZ = 2.500  # Based on your center frequency

if not os.path.exists(save_dir):
    os.makedirs(save_dir)

# --- 2. Load Baseline and New Data ---
# Load the .npy baseline created in the previous step
baseline_np = np.load(baseline_file)

# Load the new measurement
df_new = pd.read_csv(new_data_file, comment='#')
freq_cols = [c for c in df_new.columns if 'Hz' in c]
freq_axis_ghz = np.array([float(c.split(' ')[0]) for c in freq_cols]) / 1e9
new_signals = df_new[freq_cols].values

# --- 3. Signal Processing ---
# Average the new measurement to pull signal out of noise
mean_new_signal = np.mean(new_signals, axis=0)

# DIFFERENTIAL SUBTRACTION
# Subtracting the instrumental baseline to reveal the residual signal
residual_signal = mean_new_signal

# Optional: Apply a light SG filter to the residual to smooth "grass" noise
# but use a smaller window to avoid smoothing out a narrow CO line
residual_smoothed = savgol_filter(residual_signal, window_length=11, polyorder=2)

# --- 4. Plotting Detection Results ---
plt.figure(figsize=(18, 8))

# Subplot 1: Raw Comparison
plt.subplot(2, 1, 1)
plt.plot(freq_axis_ghz, mean_new_signal * 1e12, label='New Measurement (Mean)', alpha=0.7)
# plt.plot(freq_axis_ghz, baseline_np * 1e12, 'r--', label='Instrumental Baseline', alpha=0.7)
plt.title(f"Raw Power Levels: Signal vs. Baseline - {experiment_name}")
plt.ylabel("Power (pW)")
plt.legend()
plt.grid(True, alpha=0.2)

# Subplot 2: Residual (The Search Space)
plt.subplot(2, 1, 2)
plt.plot(freq_axis_ghz, residual_signal * 1e12, color='gray', alpha=0.4, label='Raw Residual')
plt.plot(freq_axis_ghz, residual_smoothed * 1e12, color='green', linewidth=2, label='Smoothed Residual')

# Mark the expected CO line position
plt.axvline(x=CO_LINE_FREQ_GHZ, color='orange', linestyle='--', label='Target CO Frequency')

plt.title("Residual Signal (Baseline Subtracted)")
plt.xlabel("Frequency (GHz)")
plt.ylabel("Delta Power (pW)")
# plt.ylim(np.min(residual_smoothed*1e12)*1.5, np.max(residual_smoothed*1e12)*1.5)
plt.legend()
plt.grid(True, alpha=0.2)

plt.tight_layout()
plt.savefig(os.path.join(save_dir, f"CO_Detection_Results_{experiment_name}.png"))
plt.close()

print(f"Analysis complete. Signal plot saved to {save_dir}")