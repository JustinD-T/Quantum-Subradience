import pandas as pd
import numpy as np
import os
from scipy.signal import savgol_filter
import matplotlib.pyplot as plt

# --- 1. Configuration & Path Setup ---
experiment_name = "Jan23_BaselineTest"
data_file = rf'Lab Notes\Tests\Noise Floor (Jan 20)\Data\BaselineTestjan23.csv'
save_dir = r"Lab Notes\Tests\Noise Floor (Jan 20)\Plots"
baseline_save_dir = r"Lab Notes\Tests\Noise Floor (Jan 20)\Baselines"

# Baseline Parameters
sg_window = 81
sg_poly = 3

if not os.path.exists(save_dir):
    os.makedirs(save_dir)
if not os.path.exists(baseline_save_dir):
    os.makedirs(baseline_save_dir)

# Load data - skipping metadata comments
df = pd.read_csv(data_file, comment='#')
freq_cols = [c for c in df.columns if 'Hz' in c]
spectrum_matrix = df[freq_cols].values 
sample_rate = df['Absolute Cycle Time (ms)'].mean() / 1000.0 

# --- 2. Allan Deviation Calculation ---
def calculate_allan_deviation(data, rate):
    n = len(data)
    avg_data = np.mean(data, axis=1) 
    taus = np.logspace(0, np.log10(n // 5), 50).astype(int)
    adevs = []
    actual_taus = []
    for m in taus:
        if m <= 0: continue
        m_samples = n - 2*m
        if m_samples <= 0: break
        sum_sq = 0
        for i in range(m_samples):
            block1 = np.mean(avg_data[i : i+m])
            block2 = np.mean(avg_data[i+m : i+2*m])
            sum_sq += (block2 - block1)**2
        adevs.append(np.sqrt(sum_sq / (2 * m_samples)))
        actual_taus.append(m * rate)
    return np.array(actual_taus), np.array(adevs)

taus, adevs = calculate_allan_deviation(spectrum_matrix, sample_rate)

# --- 3. Detect Optimal Integration Time (Maximum SNR) ---
min_idx = np.argmin(adevs)
opt_tau = taus[min_idx]
min_adev = adevs[min_idx]

# --- 4. Baseline Extraction & Export ---
raw_mean = np.mean(spectrum_matrix, axis=0)
# Savitzky-Golay filtering used to isolate the instrumental IF response
smooth_baseline = savgol_filter(raw_mean, window_length=sg_window, polyorder=sg_poly)

# Save as numpy array with metadata in the filename/header context
np.save(os.path.join(baseline_save_dir, f"Baseline_{experiment_name}.npy"), smooth_baseline)

# --- 5. Plotting ---

# Allan Deviation Plot
plt.figure(figsize=(12, 7))
plt.loglog(taus, adevs * 1e12, 'b-o', markersize=4, label='Measured Stability')
plt.loglog(taus, (adevs[0] * (taus[0] / taus)**0.5)*1e12, 'r--', alpha=0.6, label='White Noise Limit ($1/\sqrt{\\tau}$)')
plt.axvline(x=opt_tau, color='green', linestyle=':', linewidth=2, label=f'Max SNR at {opt_tau:.1f}s')
plt.annotate(f'Optimal Integration Time: {opt_tau:.1f}s\n(Min Dev: {min_adev*1e12:.2f} pW)',
             xy=(opt_tau, min_adev*1e12), xytext=(opt_tau*1.2, min_adev*2e12),
             arrowprops=dict(facecolor='black', shrink=0.05, width=1, headwidth=5),
             fontsize=10)
plt.title(f"Allan Deviation - Experiment: {experiment_name}")
plt.xlabel("Integration Time $\\tau$ (seconds)")
plt.ylabel("Allan Deviation $\sigma(\\tau)$ (Picowatts)")
plt.legend()
plt.grid(True, which="both", ls="-", alpha=0.3)
plt.savefig(os.path.join(save_dir, "allan_variance_snr_optimized.png"))
plt.close()

# Wide Baseline Plot
plt.figure(figsize=(18, 6)) # Expanded width
freq_axis = np.array([float(c.split(' ')[0]) for c in freq_cols]) / 1e9
plt.plot(freq_axis, raw_mean * 1e12, alpha=0.2, color='gray', label='Raw Mean (Temporal Average)')
plt.plot(freq_axis, smooth_baseline * 1e12, 'r', linewidth=2, label=f'Extracted Baseline (SG Filter)')

# Adding Methods/Numbers to Plot Text
info_text = (f"Baseline Method: Savitzky-Golay\n"
             f"Window Length: {sg_window}\n"
             f"Poly Order: {sg_poly}\n"
             f"Total Sweeps: {len(df)}")
plt.text(0.02, 0.95, info_text, transform=plt.gca().transAxes, verticalalignment='top', 
         bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

plt.title(f"Wide Spectrum Baseline (pW) - Exp: {experiment_name}")
plt.xlabel("Frequency (GHz)")
plt.ylabel("Power (pW)")
plt.legend(loc='upper right')
plt.grid(True, alpha=0.2)
plt.savefig(os.path.join(save_dir, "wide_spectrum_baseline.png"))
plt.close()

print(f"Optimal integration time: {opt_tau:.1f}s")
print(f"Baseline saved as: Baseline_{experiment_name}.npy")
print(f"Plots saved to: {save_dir}")