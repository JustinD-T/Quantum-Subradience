from Utils import load_data
import pandas as pd
import numpy as np
from matplotlib import pyplot as plt
from scipy.interpolate import make_interp_spline
from scipy.signal import savgol_filter

def Rolling_Variance(spec_df, sweep_time=2.5):
    vars = spec_df.expanding(axis=0).var()
    mean_var = vars.mean(axis=1)

    taus = np.arange(1, len(mean_var)+1) * sweep_time

    return taus, mean_var, vars

def plot_rolling_noise_reduction(spec_df):
    taus, mean_var, vars = Rolling_Variance(spec_df)

    plt.figure(figsize=(10, 6))
    plt.loglog(taus, mean_var, label='Mean Rolling Variance', color='black', linewidth=2)

    for col in vars.columns:
        plt.loglog(taus, vars[col], alpha=0.01, color='blue')

    plt.xlabel('Tau (s)')
    plt.ylabel('Variance')
    plt.title('Rolling Variance of Spectrum Over Time')
    plt.legend()
    plt.grid(True, which="both", ls="--")
    plt.show()

def mean_amplitude_vs_time(spec_df):
    integration_times = np.arange(1, len(spec_df)+1) * 2.5  # assuming 2.5s sweep time
    mean_amplitudes = spec_df.mean(axis=1)
    return integration_times, mean_amplitudes

def plot_mean_amplitude_vs_time(spec_df):
    integration_times, mean_amplitudes = mean_amplitude_vs_time(spec_df)

    plt.figure(figsize=(10, 6))
    plt.scatter(integration_times, mean_amplitudes, marker='o')
    plt.xlabel('Integration Time (s)')
    plt.ylabel('Mean Amplitude')
    plt.title('Mean Amplitude vs Integration Time')
    plt.grid(True)
    plt.show()

def fit_baseline_sv(spec_df):
    mean_spectrum = spec_df.mean(axis=0)
    window_size = 101  # Must be odd
    polyorder = 4
    sv = savgol_filter(mean_spectrum, window_size, polyorder)
    return sv

def hist_amplitudes(mean_amplitudes, bins=1000):
    plt.figure(figsize=(10, 6))
    
    # Get histogram data
    counts, bin_edges = np.histogram(mean_amplitudes, bins=bins)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    
    # Plot histogram
    plt.hist(mean_amplitudes, bins=bins, alpha=0.7, color='blue', label='Histogram')
    
    # Overlay plot of points at the top of each bin
    # Create a smoother set of x-values for the curve
    x_smooth = np.linspace(bin_centers.min(), bin_centers.max(), 300)
    
    # Create a spline interpolation function
    spl = make_interp_spline(bin_centers, counts, k=3)  # k=3 for a cubic spline
    y_smooth = spl(x_smooth)
    
    plt.plot(x_smooth, y_smooth, '-', alpha=0.4, color='red', label='Smooth Curve')
    
    plt.xlabel('Mean Amplitude')
    plt.ylabel('Frequency')
    plt.title('Histogram of Mean Amplitudes')
    plt.legend()
    plt.grid(True)
    plt.show()

def plot_baseline(spectrum_df, baseline):
    plt.figure(figsize=(12, 6))
    freq_axis = np.array([float(c.split(' ')[0]) for c in spectrum_df.columns]) / 1e9  # Convert to GHz
    
    plt.plot(freq_axis, spectrum_df.mean(axis=0) * 1e12, alpha=0.3, label='Mean Spectrum (pW)')
    plt.plot(freq_axis, baseline * 1e12, 'r-', linewidth=2, label='Determined Baseline (pW)')
    
    plt.xlabel('Frequency (GHz)')
    plt.ylabel('Power (pW)')
    plt.title('Spectrum Baseline Determination')
    plt.legend()
    plt.grid(True)
    plt.show()

def plot_avrg_spectrum(spectrum_df):
    plt.figure(figsize=(12, 6))
    freq_axis = np.array([float(c.split(' ')[0]) for c in spectrum_df.columns]) / 1e9  # Convert to GHz
    
    plt.plot(freq_axis, spectrum_df[:300].mean(axis=0) * 1e12, 'b-', alpha=0.7, label='Mean Spectrum (pW)')
    
    # Highlight +/- 250kHz area around the center frequency
    center_freq = freq_axis.mean()
    highlight_width_ghz = 250e3 / 1e9  # 250 kHz in GHz
    plt.axvspan(center_freq - highlight_width_ghz, center_freq + highlight_width_ghz, color='yellow', alpha=0.3, label='Center Freq +/- 250kHz')

    plt.xlabel('Frequency (GHz)')
    plt.ylabel('Power (pW)')
    plt.title('Average Spectrum')
    plt.legend()
    plt.grid(True)
    plt.show()

def bin_spec(spec_df, binning_factor=10):
    """
    Bins the spectrum data by averaging adjacent frequency points.

    :param spec_df: DataFrame where each column is a frequency and each row is a time step.
    :param binning_factor: The number of frequency points to average together.
                           A factor of 1 returns the original spectrum.
                           A factor of 2 halves the number of frequency points.
    :return: A tuple containing the binned DataFrame and a list of the new mean frequencies.
    """
    if binning_factor <= 0:
        raise ValueError("binning_factor must be a positive integer.")
    if binning_factor == 1:
        return spec_df, [float(c.split(' ')[0]) for c in spec_df.columns]

    num_cols = spec_df.shape[1]
    binned_ampl = pd.DataFrame()
    freqs = []

    for i in range(0, num_cols, binning_factor):
        end = min(i + binning_factor, num_cols)
        chunk = spec_df.iloc[:, i:end]
        
        # Calculate mean frequency for the bin
        col_names = chunk.columns
        start_freq = float(col_names[0].split(' ')[0])
        end_freq = float(col_names[-1].split(' ')[0])
        mean_freq = (start_freq + end_freq) / 2
        freqs.append(mean_freq)
        
        # Calculate mean amplitude for the bin
        binned_ampl[f'{mean_freq} Hz'] = chunk.mean(axis=1)
    return binned_ampl, freqs

if __name__ == "__main__":
    path = r'ExperimentLogs\ExperimentLog_20260202-130123.csv'
    _, spec = load_data(path)
    bin_spec_df, freqs = bin_spec(spec, binning_factor=5)
    plot_avrg_spectrum(bin_spec_df)
    # plot_rolling_noise_reduction(spec)
    # sv = fit_baseline_sv(spec)
    # spec = spec - sv
    # plot_mean_amplitude_vs_time(spec)
    # plot_baseline(spec, sv)

    # integration_times, mean_amplitudes = mean_amplitude_vs_time(spec)
    # hist_amplitudes(mean_amplitudes)