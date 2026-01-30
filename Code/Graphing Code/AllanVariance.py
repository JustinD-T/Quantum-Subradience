from Utils import load_data
from scipy.signal import savgol_filter
import numpy as np
import matplotlib.pyplot as plt

def determine_baseline(spectrum_df, window_size=31):

    average = spectrum_df.mean(axis=0)

    sv = savgol_filter(average, window_size, polyorder=2)

    return sv

def subtract_baseline(spectrum_df, baseline):
    corrected_df = spectrum_df - baseline
    return corrected_df

import numpy as np
import pandas as pd

def calculate_allan_deviation_fast(df, sweep_time=2.5):
    results = {}
    n_samples = len(df)
    
    # Standard log-spaced m values (integration factors)
    max_m = n_samples // 10
    m_values = np.unique(np.logspace(0, np.log10(max_m), 100).astype(int))
    
    for col in df.columns:
        data = df[col].values
        # Precompute cumulative sum for O(1) window averaging
        c_sum = np.cumsum(np.insert(data, 0, 0))
        
        adevs = []
        taus = []
        
        for m in m_values:
            # Overlapping window sums using cumulative sum differences
            # sum(data[j : j+m]) = c_sum[j+m] - c_sum[j]
            window_1 = (c_sum[m : n_samples - m + 1] - c_sum[0 : n_samples - 2*m + 1]) / m
            window_2 = (c_sum[2*m : n_samples + 1] - c_sum[m : n_samples - m + 1]) / m
            
            # The variance is half the mean square of the differences
            variance = np.mean((window_2 - window_1)**2) / 2
            
            adevs.append(np.sqrt(variance))
            taus.append(m * sweep_time)
            
        results[col] = (np.array(taus), np.array(adevs))
        
    return results


def plot_allan_deviation(results):

    plt.figure(figsize=(10, 6))
    for freq, (taus, adevs) in results.items():
        plt.loglog(taus, adevs, alpha=0.2)
    
    # Plot average across frequencies
    all_adevs = np.array([adevs for taus, adevs in results.values()])
    plt.loglog(taus, np.mean(all_adevs, axis=0), 'k-', linewidth=2, label='Average Across Frequencies')

    plt.xlabel('Integration Time $\\tau$ (seconds)')
    plt.ylabel('Allan Deviation $\sigma(\\tau)$')
    plt.title('Noise Floor Stability Analysis')
    plt.legend()
    plt.grid(True, which="both", ls="-", alpha=0.5)
    plt.show()

def plot_baseline(spectrum_df, baseline):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)
    
    freq_axis = np.array([float(c.split(' ')[0]) for c in spectrum_df.columns]) / 1e9  # Convert to GHz
    
    # First subplot: Original spectrum and baseline
    ax1.plot(freq_axis, spectrum_df.mean(axis=0) * 1e12, alpha=0.3, label='Mean Spectrum (pW)')
    ax1.plot(freq_axis, baseline * 1e12, 'r-', linewidth=2, label='Determined Baseline (pW)')
    ax1.set_ylabel('Power (pW)')
    ax1.set_title('Spectrum Baseline Determination')
    ax1.legend()
    ax1.grid(True)
    
    # Second subplot: Subtracted baseline
    subtracted = spectrum_df.mean(axis=0) - baseline
    ax2.plot(freq_axis, subtracted * 1e12, 'g-', label='Mean Spectrum - Baseline (pW)')
    ax2.set_xlabel('Frequency (GHz)')
    ax2.set_ylabel('Power (pW)')
    ax2.set_title('Baseline Corrected Mean Spectrum')
    ax2.legend()
    ax2.grid(True)
    
    plt.tight_layout()
    plt.show()

def plot_rolling_noise_reduction(spectrum_df, sweep_time=2.5, max_window=200):
    """
    Plots the standard deviation of the signal as a function of 
    integration (window) size.
    """
    # 1. Use a single representative frequency or the mean across frequencies
    # Taking the mean across frequencies first helps see the global trend
    avg_signal = spectrum_df.mean(axis=1).values 
    
    window_sizes = np.arange(1, max_window)
    stds = []
    
    for w in window_sizes:
        # Calculate the rolling mean
        # Then take the standard deviation of that smoothed signal
        rolling_std = pd.Series(avg_signal).rolling(window=w).mean().std()
        stds.append(rolling_std)
    
    integration_times = window_sizes * sweep_time
    
    # 2. Plotting
    plt.figure(figsize=(10, 6))
    plt.plot(integration_times, stds, 'b-o', markersize=4, label='Measured Noise (Std Dev)')
    
    # 3. Plot the Theoretical Ideal (1/sqrt(N))
    # Normalized to the first data point
    theoretical = stds[0] / np.sqrt(window_sizes)
    plt.plot(integration_times, theoretical, 'r--', label='Theoretical White Noise Limit ($1/\sqrt{N}$)')
    
    plt.xscale('log')
    plt.yscale('log')
    plt.xlabel('Integration Time (seconds)')
    plt.ylabel('Standard Deviation (Power)')
    plt.title('Noise Reduction vs. Integration Time')
    plt.legend()
    plt.grid(True, which="both", ls="-", alpha=0.5)
    plt.show()

    # Find the "Efficiency"
    # Where the measured noise starts staying significantly above theoretical
    return integration_times, stds

if __name__ == "__main__":
    path = r'Code\Graphing Code\ExperimentLog_20260129-123129.csv'
    headers_df, spectrum_df = load_data(path)
    baseline = determine_baseline(spectrum_df)
    import json
    # with open('baseline.json', 'w') as f:
    #     json.dump(baseline.tolist(), f)
    # corrected_df = subtract_baseline(spectrum_df, baseline)
    # plot_rolling_noise_reduction(corrected_df)
    results = calculate_allan_deviation_fast(spectrum_df, 2.5)
    plot_allan_deviation(results)
    # plot_baseline(spectrum_df, baseline)