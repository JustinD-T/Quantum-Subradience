import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from scipy.signal import savgol_filter
from mpl_toolkits.mplot3d import Axes3D

def load_experiment_log(path):
    """Parses metadata from comments and spectrum data from CSV."""
    metadata = {}
    with open(path, 'r') as f:
        for line in f:
            if line.startswith('#'):
                if ':' in line:
                    key = line.split(':')[0].replace('#', '').strip()
                    val = line.split(':', 1)[1].strip()
                    metadata[key] = val
            else:
                break 

    full_df = pd.read_csv(path, comment='#')
    spec_cols = [c for c in full_df.columns if c.endswith(' Hz')]
    aux_cols = [c for c in full_df.columns if c not in spec_cols]
    
    freqs = np.array([float(c.split(' ')[0]) for c in spec_cols])
    return metadata, full_df[spec_cols], freqs, full_df[aux_cols]

def process_and_subtract(amps, freqs, aux_cols, sigma=1e6, n=200, deg=2):
    center_freq = np.mean(freqs)
    fitting_mask = (freqs < (center_freq - sigma)) | (freqs > (center_freq + sigma))

    # --- 1. Global Simple Mean Subtraction ---
    global_mean = amps.mean(axis=0).values
    global_coeffs = np.polyfit(freqs[fitting_mask], global_mean[fitting_mask], deg=deg)
    global_baseline = np.polyval(global_coeffs, freqs)
    global_subtracted = global_mean - global_baseline

    # --- 2. Local Bin-wise Subtraction ---
    num_bins = len(amps) // n
    subtracted_amps_collector = np.zeros((len(freqs), num_bins))

    for group_idx in range(num_bins):
        start_row = group_idx * n
        end_row = (group_idx + 1) * n
        
        bin_avg_spectrum = amps.iloc[start_row:end_row].mean(axis=0).values
        
        # Fit polynomial to the baseline region for the current bin
        bin_coeffs = np.polyfit(freqs[fitting_mask], bin_avg_spectrum[fitting_mask], deg=deg)
        bin_baseline = np.polyval(bin_coeffs, freqs)
        
        subtracted_amps_collector[:, group_idx] = bin_avg_spectrum - bin_baseline

    local_subtracted = np.mean(subtracted_amps_collector, axis=1)

    # --- 3D Plot: Subtracted Amplitudes vs Frequency and Bins ---

    # fig = plt.figure(figsize=(12, 8))
    # ax = fig.add_subplot(111, projection='3d')

    # freq_mesh, bin_mesh = np.meshgrid(freqs, np.arange(num_bins), indexing='ij')
    
    # # Apply Savitzky-Golay filter for smooth surface
    # subtracted_amps_smooth = savgol_filter(subtracted_amps_collector, window_length=51, polyorder=3, axis=0)
    
    # ax.plot_surface(bin_mesh, freq_mesh / 1e6, subtracted_amps_smooth, cmap='viridis', alpha=0.8)

    # ax.set_xlabel('Bin Index')
    # ax.set_ylabel('Frequency (MHz)')
    # ax.set_zlabel('Power (Watts)')
    # ax.set_title('Subtracted Amplitudes: Bins vs Frequency (Smoothed)')
    # plt.show()

    # --- 3. Median Background Level vs Time ---
    # bin_baselines = []
    # for group_idx in range(num_bins):
    #     start_row = group_idx * n
    #     end_row = (group_idx + 1) * n
    #     bin_avg_spectrum = amps.iloc[start_row:end_row].mean(axis=0).values
    #     bin_baseline = savgol_filter(bin_avg_spectrum, window_length=101, polyorder=1)
    #     bin_baselines.append(np.median(bin_baseline))

    # median_bg_level = np.median(bin_baselines)

    # plt.figure(figsize=(10, 6))
    # plt.scatter(range(num_bins), bin_baselines, alpha=0.6, s=50)
    # plt.axhline(median_bg_level, color='red', linestyle='--', label=f'Median: {median_bg_level:.2e}')
    # plt.xlabel('Bin Index (Time)')
    # plt.ylabel('Median Background Level (Watts)')
    # plt.title('Background Level vs Time')
    # plt.legend()
    # plt.grid(True, linestyle=':', alpha=0.6)
    # plt.show()
    
    # # --- 3. Integration within ±100 kHz of center frequency ---
    # center_freq = np.mean(freqs)
    # integration_mask = (freqs >= (center_freq - 100e3)) & (freqs <= (center_freq + 100e3))
    # freq_resolution = freqs[1] - freqs[0]

    # integrated_powers = []
    # mean_pressures = []
    # for group_idx in range(num_bins):
    #     # Cumulative integration for power
    #     num_bins_used = group_idx + 1
    #     bin_avg = np.mean(subtracted_amps_collector[:, :num_bins_used], axis=1)
    #     bin_avg_sg = savgol_filter(bin_avg, window_length=51, polyorder=3)
    #     integrated_power = np.sum(bin_avg_sg[integration_mask]) * freq_resolution
    #     integrated_powers.append(integrated_power)

    #     # Mean pressure for the current bin
    #     start_row = group_idx * n
    #     end_row = (group_idx + 1) * n
    #     mean_pressure = aux_cols['Pressure'].iloc[start_row:end_row].mean()
    #     mean_pressures.append(mean_pressure)


    # fig, ax1 = plt.subplots(figsize=(12, 7))

    # # Plot Integrated Power
    # color = 'tab:blue'
    # ax1.set_xlabel('Number of Bins Used / Bin Index')
    # ax1.set_ylabel('Integrated Power (Watts)', color=color)
    # ax1.plot(range(1, num_bins + 1), integrated_powers, marker='o', linewidth=2, color=color, label='Integrated Power')
    # ax1.tick_params(axis='y', labelcolor=color)
    # ax1.grid(True, linestyle=':', alpha=0.6)

    # # Create a second y-axis for the mean pressure
    # ax2 = ax1.twinx()
    # color = 'tab:red'
    # ax2.set_ylabel('Mean Pressure (mbar)', color=color)
    # ax2.plot(range(1, num_bins + 1), mean_pressures, marker='x', linestyle='--', color=color, label='Mean Pressure')
    # ax2.tick_params(axis='y', labelcolor=color)

    # fig.tight_layout()
    # plt.title('Integrated Power and Mean Pressure vs. Bins')
    # plt.show()
    
    return local_subtracted, global_subtracted

def plot_comparison(freqs, local_amps, global_amps):
    center_f = np.mean(freqs)
    offset_khz = (freqs - center_f) / 1e3

    # Compute Savitzky-Golay fit for detail retention
    sg_fit = savgol_filter(local_amps, window_length=31, polyorder=3)

    plt.figure(figsize=(12, 7))
    
    # Plot Local Bin-wise Subtraction (reduced alpha)
    plt.plot(offset_khz, local_amps, label='Bin-wise Fit Subtraction (n=200)', color='blue', lw=1.5, alpha=0.3)
    
    # Plot Global Subtraction (reduced alpha)
    plt.plot(offset_khz, global_amps, label='Global Mean Fit Subtraction', color='black', alpha=0.3, lw=1)
    
    # Plot SG fit (high detail retention)
    plt.plot(offset_khz, sg_fit, label='Savitzky-Golay Fit', color='green', lw=2)
    
    plt.axhline(0, color='red', linestyle='--', alpha=0.3)
    plt.axvspan(-500, 500, color='orange', alpha=0.1, label='Signal Zone')
    
    plt.xlabel('Frequency Offset (kHz)')
    plt.ylabel('Power (Watts)')
    plt.title('Spectrum Comparison: Local Binning vs. Global Averaging')
    plt.legend()
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.show()

def downsample_data(amps, freqs, coeff):
    """Downsample amplitude and frequency data by coefficient."""
    amps = amps.iloc[:, ::coeff].copy()
    amps.columns = range(len(amps.columns))
    freqs = freqs[::coeff]
    return amps, freqs

def plot_multiple_runs(freqs, signals_list, titles_list):
    """Plot signals from multiple runs for comparison, with a transparent Savitzky-Golay overlay.
    
    Args:
        freqs: Frequency array
        signals_list: List of signal arrays (local_sig from each run)
        titles_list: List of titles for each run
    """
    center_f = np.mean(freqs)
    offset_khz = (freqs - center_f) / 1e3
    
    num_runs = len(signals_list)
    fig, axes = plt.subplots(num_runs, 1, figsize=(12, 4 * num_runs), sharex=True, sharey=True)
    
    if num_runs == 1:
        axes = [axes]
    
    # Find global min and max for y-axis scaling from raw data
    global_min = float('inf')
    global_max = float('-inf')
    for signal in signals_list:
        global_min = min(global_min, np.min(signal))
        global_max = max(global_max, np.max(signal))

    # Add some padding to the limits
    y_padding = (global_max - global_min) * 0.1
    y_min = global_min - y_padding
    y_max = global_max + y_padding

    for idx, (signal, title) in enumerate(zip(signals_list, titles_list)):
        # Plot raw data
        axes[idx].plot(offset_khz, signal, color='blue', lw=1.5, label='Raw Data')
        
        # Calculate and plot transparent Savitzky-Golay fit
        sg_fit = savgol_filter(signal, window_length=len(signal) // 10, polyorder=3 if len(signal) >= 10 else 1)
        axes[idx].plot(offset_khz, sg_fit, color='green', lw=2, alpha=0.7, label='Sav-Gol Fit')

        axes[idx].axhline(0, color='red', linestyle='--', alpha=0.5)
        axes[idx].axvspan(-500, 500, color='orange', alpha=0.1)
        axes[idx].set_ylabel('Power (Watts)')
        axes[idx].set_title(title)
        axes[idx].grid(True, linestyle=':', alpha=0.6)
        axes[idx].set_ylim(y_min, y_max)
        axes[idx].legend()
    
    axes[-1].set_xlabel('Frequency Offset (kHz)')
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    # path = r'ExperimentLogs\ExperimentLog_20260226-141459.csv'
    # CO Test
    path1 = r'ExperimentLogs\LARGE_CO_RUN.csv'
    # CO Verification Test
    path2 = r'ExperimentLogs\ExperimentLog_20260226-152453.csv'
    # No Co
    path3 = r'ExperimentLogs\NO_CO_TEST.csv'
    
    titles = ['Large CO Run', 'CO Verification Test', 'No CO Run']

    meta1, amps1, freqs1, aux1 = load_experiment_log(path1)
    meta2, amps2, freqs2, aux2 = load_experiment_log(path2)
    meta3, amps3, freqs3, aux3 = load_experiment_log(path3)

    amps1, freqs1 = downsample_data(amps1, freqs1, coeff=10)
    amps2, freqs2 = downsample_data(amps2, freqs2, coeff=10)
    amps3, freqs3 = downsample_data(amps3, freqs3, coeff=10)

    local_sig1, global_sig1 = process_and_subtract(amps1, freqs1, aux1, sigma=0.5e6, n=20, deg=2)
    local_sig2, global_sig2 = process_and_subtract(amps2, freqs2, aux2, sigma=0.5e6, n=20, deg=2)
    local_sig3, global_sig3 = process_and_subtract(amps3, freqs3, aux3, sigma=0.5e6, n=20, deg=2)

    plot_multiple_runs(freqs1, [local_sig1, local_sig2, local_sig3], titles)
    # if os.path.exists(path):
    #     meta, amps, freqs, aux = load_experiment_log(path)

    #     # Downsample: average adjacent frequency bins
    #     # amps, freqs = downsample_data(amps, freqs, coeff=2)

    #     # Process both methods
    #     local_sig, global_sig = process_and_subtract(amps, freqs, aux, sigma=1e6, n=10, deg=2)
        
    #     plot_comparison(freqs, local_sig, global_sig)
    # else:
    #     print(f"File not found.")

# Remove SG
# Look at noise profile -> STOP RUUSHING
# Downsample by at least a facotr of 10