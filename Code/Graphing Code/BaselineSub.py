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

def process_and_subtract(amps, freqs, sigma=1e6, n=200, deg=2):
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
        
        bin_baseline = savgol_filter(bin_avg_spectrum, window_length=101, polyorder=1)
        
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
    # for num_bins_used in range(1, num_bins + 1):
    #     bin_avg = np.mean(subtracted_amps_collector[:, :num_bins_used], axis=1)
    #     bin_avg_sg = savgol_filter(bin_avg, window_length=51, polyorder=3)
    #     integrated_power = np.sum(bin_avg_sg[integration_mask]) * freq_resolution
    #     integrated_powers.append(integrated_power)

    # plt.figure(figsize=(10, 6))
    # plt.plot(range(1, num_bins + 1), integrated_powers, marker='o', linewidth=2)
    # plt.xlabel('Number of Bins Used')
    # plt.ylabel('Integrated Power (Watts)')
    # plt.title('Integrated Power vs. Number of Bins (±100 kHz)')
    # plt.grid(True, linestyle=':', alpha=0.6)
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
    """Plot Savitzky-Golay filtered signals from multiple runs for comparison.
    
    Args:
        freqs: Frequency array
        signals_list: List of signal arrays (local_sig from each run)
        titles_list: List of titles for each run
    """
    center_f = np.mean(freqs)
    offset_khz = (freqs - center_f) / 1e3
    
    num_runs = len(signals_list)
    fig, axes = plt.subplots(num_runs, 1, figsize=(12, 4 * num_runs))
    
    if num_runs == 1:
        axes = [axes]
    
    for idx, (signal, title) in enumerate(zip(signals_list, titles_list)):
        sg_fit = savgol_filter(signal, window_length=31, polyorder=3)
        
        axes[idx].plot(offset_khz, sg_fit, color='blue', lw=2)
        axes[idx].axhline(0, color='red', linestyle='--', alpha=0.5)
        axes[idx].axvspan(-500, 500, color='orange', alpha=0.1)
        axes[idx].set_ylabel('Power (Watts)')
        axes[idx].set_title(title)
        axes[idx].grid(True, linestyle=':', alpha=0.6)
    
    axes[-1].set_xlabel('Frequency Offset (kHz)')
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    # CO Test
    path1 = r'ExperimentLogs\LARGE_CO_RUN.csv'
    # CO Verification Test
    path2 = r'ExperimentLogs\CO_VERIFICATION_TEST.csv'
    # No Co
    path3 = r'ExperimentLogs\NO_CO_TEST.csv'
    
    titles = ['Large CO Run', 'CO Verification Test', 'No CO Run']

    meta1, amps1, freqs1, aux1 = load_experiment_log(path1)
    meta2, amps2, freqs2, aux2 = load_experiment_log(path2)
    meta3, amps3, freqs3, aux3 = load_experiment_log(path3)

    local_sig1, global_sig1 = process_and_subtract(amps1.iloc[:250], freqs1, sigma=0.5e6, n=25, deg=1)
    local_sig2, global_sig2 = process_and_subtract(amps2.iloc[:250], freqs2, sigma=0.5e6, n=25, deg=1)
    local_sig3, global_sig3 = process_and_subtract(amps3.iloc[:250], freqs3, sigma=0.5e6, n=25, deg=1)

    plot_multiple_runs(freqs1, [local_sig1, local_sig2, local_sig3], titles)

    # if os.path.exists(path1):
    #     meta, amps, freqs, aux = load_experiment_log(path1)

    #     # Downsample: average adjacent frequency bins
    #     # amps, freqs = downsample_data(amps, freqs, coeff=2)

    #     # Process both methods
    #     local_sig, global_sig = process_and_subtract(amps.iloc[:150], freqs, sigma=0.5e6, n=25, deg=1)
        
    #     plot_comparison(freqs, local_sig, global_sig)
    # else:
    #     print(f"File not found.")