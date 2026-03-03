import json 
import csv
import time
import os

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt

global TEST_BOOL
TEST_BOOL = True

# Data Preperation Utilities
def loadData(path):
    """
    Given a path to an experiment log, return metadata, powers, and spectral axis.
    
    Args:
        path (str): Path to the experiment log file (CSV with comment metadata).

    Returns:
        metadata (dict): Dictionary of configuration parameters.
        powers (np.array): 2D array of power readings (frequencies x measurements).
        spectral_axis (np.array): 1D array of frequencies in Hz.
    """
    metadata = {}
    header_end_line = 0

    if TEST_BOOL:
        start = time.time()

    if path.endswith('.csv'):
        # 1. Parse Metadata from comments
        with open(path, 'r') as f:
            for i, line in enumerate(f):
                if line.startswith('#'):
                    header_end_line = i
                    # Clean up the line and split by first colon
                    content = line.lstrip('#').strip()
                    if ':' in content:
                        key, val = content.split(':', 1)
                        metadata[key.strip()] = val.strip()
                else:
                    break
        
        # 2. Load Data using pandas
        # We skip the specific number of comment lines and use the first non-comment line as header
        df = pd.read_csv(path, comment='#')
        
        # 3. Extract Spectral Axis (frequencies)
        # Frequencies start after 'Effective Integration (%)'
        # The format is "2497500000.0 Hz"
        freq_columns = [col for col in df.columns if 'Hz' in col]
        spectral_axis = np.array([float(col.split(' ')[0]) for col in freq_columns])
        
        # 4. Extract Power values
        powers = df[freq_columns].to_numpy().transpose()  # Transpose to get frequencies x measurements

        # Save as numpy arrays for faster processing
        # Create folder with the name of the file (without extension)
        folder_name = path.replace('.csv', '').split('/')[-1]
        os.makedirs(folder_name, exist_ok=True)
        
        np.save(os.path.join(folder_name, 'powers.npy'), powers)
        np.save(os.path.join(folder_name, 'freqs.npy'), spectral_axis)
        with open(os.path.join(folder_name, 'metadata.json'), 'w') as f:
            json.dump(metadata, f, indent=4)

        print(f"Data loaded and saved as numpy arrays in folder: {folder_name}")

    elif os.path.isdir(path):
        # Load from pre-saved numpy arrays
        powers = np.load(os.path.join(path, 'powers.npy'))
        spectral_axis = np.load(os.path.join(path, 'freqs.npy'))
        with open(os.path.join(path, 'metadata.json'), 'r') as f:
            metadata = json.load(f)
    
    if TEST_BOOL:
        print(f"Data loading and parsing took {time.time() - start:.4f} seconds")

    return powers, spectral_axis, metadata   

def binData(powers, spectral_axis, binning_factor=10):
    """
    Bin the power data into n groups, computing the sum of the power and 
    using the mean frequencies in each bin.

    Args:
        meta (dict): Metadata dictionary (not used in this function but can be useful for future extensions).
        powers (np.array): 2D array of power readings (frequencies x measurements).
        spectral_axis (np.array): 1D array of frequencies in Hz.
        binning_factor (int): number of bins to count as one new.
    
    Returns:
        binned_powers (np.array): 2D array of binned power values (bins x frequencies).
        binned_freqs (np.array): 1D array of mean frequencies for each bin.
    """

    if TEST_BOOL:
        start = time.time()

    n = powers.shape[0] // binning_factor  # Number of bins
    new_spectral_axis = np.zeros(n)
    new_powers = np.zeros((n, powers.shape[1]))

    for i in range(n):
        # Get start and end indices for the current bin
        start_row = i * (powers.shape[0] // n)
        end_row = (i + 1) * (powers.shape[0] // n)

        # Get mean of axis and sum of powers for the current bin
        new_spectral_axis[i] = spectral_axis[start_row:end_row].mean()
        new_powers[i, :] = powers[start_row:end_row].sum(axis=0)
    
    # Handle any remaining rows if powers.shape[0] is not perfectly divisible by n
    new_powers = new_powers[:end_row, :]

    if TEST_BOOL:
        print(f"Binning data took {time.time() - start:.4f} seconds")

    return new_powers, new_spectral_axis

def cleanData(powers, spectral_axis, freq_center, sigma):
    """
    Cleans measurements by removing outlier measurements defined by a positive derivative of rolling standard deviation

    Args:
        powers (np.array): 2D array of power readings (frequencies x measurements).
        spectral_axis (np.array): 1D array of frequencies in Hz.
        freq_center (float): Central frequency to exclude from fitting.
        sigma (float): Width around the central frequency to exclude in fitting (+/- sigma).
    Returns:
        cleaned_powers (np.array): 2D array of power readings with outliers removed.
        measurement_indices (np.array): 1D array of indices corresponding to the cleaned measurements.
    """

    if TEST_BOOL:
        start = time.time() 
    
    variance_integral, mean_integral = computeNoiseIntegral(powers, spectral_axis, freq_center, sigma)

    var_diffs = np.diff(variance_integral)

    # Reject data if variance integral increases 
    outlier_indices = np.where(var_diffs > 0)[0] + 1  # +1 to correct for the diff offset

    # create a mask to filter out outliers
    mask = np.ones(powers.shape[1], dtype=bool)
    mask[outlier_indices] = False
    masked_powers = powers[:, mask]

    print(f"Removed {len(outlier_indices)}/{powers.shape[1]} outlier measurements")

    if TEST_BOOL:
        print(f"Data cleaning took {time.time() - start:.4f} seconds")

        # Plot variance integral with masked regions for debugging
        # plt.figure(figsize=(10, 5))
        # ax1 = plt.gca()
        # ax1.plot(variance_integral, label='Variance Integral', color='blue')
        # ax1.set_ylabel('Variance Integral (W)', color='blue')
        # ax1.tick_params(axis='y', labelcolor='blue')
        
        # ax2 = ax1.twinx()
        # ax2.plot(powers.mean(axis=0), label='Mean Power per measurement', color='green')
        # ax2.set_ylabel('Mean Power (W)', color='green')
        # ax2.tick_params(axis='y', labelcolor='green')
        # plt.scatter(outlier_indices, variance_integral[outlier_indices], color='red', label='Outliers', alpha=0.3)
        # plt.xlabel('Measurement Index')
        # plt.ylabel('Variance Integral (W)')
        # plt.title('Variance Integral with Outliers Highlighted')
        # plt.legend()
        # plt.grid(True)
        # plt.yscale('log')
        # plt.show()

        # Plot correllation between variance and mean integrals diffs
        # plt.figure(figsize=(12, 6))
        
        # # Normalize both to [0, 1] for shape comparison
        # # var_diff_norm = (np.diff(variance_integral) - np.diff(variance_integral).min()) / (np.diff(variance_integral).max() - np.diff(variance_integral).min())
        # # mean_diff_norm = (np.diff(mean_integral) - np.diff(mean_integral).min()) / (np.diff(mean_integral).max() - np.diff(mean_integral).min())
        
        # var_diff_norm = np.diff(variance_integral)
        # # residuals from mean power
        # mean_diff_norm = (np.mean(powers, axis=0) - np.mean(powers, axis=0).mean())[:-1]  # Center around overall mean

        # plt.scatter(var_diff_norm, mean_diff_norm, label='Variance vs Mean Integral Diff (normalized)', color='purple', alpha=0.7)
        # plt.scatter(var_diff_norm[outlier_indices-1], mean_diff_norm[outlier_indices-1], color='red', label='Outliers', alpha=0.2, marker='*', s=5)  # -1 to align with diff indices
        # # plt.xscale('log')
        # # plt.yscale('log')
        # plt.xlabel('Variance')
        # plt.ylabel('Mean Integral')
        # plt.title('Correlation between Variance and Mean Integral Differences')
        # plt.legend()
        # plt.grid(True)
        # plt.show()

    return masked_powers, mask

# Data Processing Utilities
def subtractBaseline(powers, spectral_axis, freq_center, sigma, deg, n):
    """
    Performs polynomial baseline fitting on the power excluding +/- the central frequency, then subtracts
    from the entire measurement. Also performs local fitting on rolling averages of n bins (excluding start/ends)
    
    Args:
    powers (np.array): 2D array of power readings (frequencies x measurements).
    spectral_axis (np.array): 1D array of frequencies in Hz.
    freq_center (float): Central frequency to exclude from fitting.
    sigma (float): Width around the central frequency to exclude from fitting (+/- sigma).
    deg (int): Degree of the polynomial to fit.
    n (int): Number of adjacent measurements to use for local fitting (i+n//2,i-n//2) to compute n's baseline.
    """

    if TEST_BOOL:
        start = time.time()

    new_powers = np.zeros_like(powers)

    # Determine frequency closest to the center frequency for masking
    freq_center_actual = spectral_axis[np.argmin(np.abs(spectral_axis - freq_center))]

    # Itterate over each measurement
    for i in range(powers.shape[1]):

        # Exclude start/end measurements that can't form full bins
        if i < n//2 or i > powers.shape[1] - n//2:
            continue

        # Get average power of given bin (+/- n/2 measurements)
        bin_avrg_power = powers[:,i-n//2:i+n//2].mean(axis=1)

        # Get mask out central region for fitting
        masked_bin_avrg_power = bin_avrg_power[(spectral_axis < (freq_center_actual - sigma)) | (spectral_axis > (freq_center_actual + sigma))]
        masked_freqs = spectral_axis[(spectral_axis < (freq_center_actual - sigma)) | (spectral_axis > (freq_center_actual + sigma))]

        # Fit polynomial to masked data
        coeffs = np.polyfit(masked_freqs, masked_bin_avrg_power, deg=deg)
        baseline = np.polyval(coeffs, spectral_axis)

        # Subtract baseline from original power data
        new_powers[:,i] = powers[:,i] - baseline
    
    # delete start/end excluded zero cols
    new_powers = new_powers[:,n//2:-n//2]

    if TEST_BOOL:
        print(f"Baseline subtraction took {time.time() - start:.4f} seconds")

        # Plot three random measurements with their baselines for debugging
        plt.figure(figsize=(12, 6))
        for _ in range(3):
            idx = np.random.randint(n//2, powers.shape[1] - n//2)
            # Compute baseline for this measurement
            bin_avrg_power = powers[:,idx-n//2:idx+n//2].mean(axis=1)
            masked_bin_avrg_power = bin_avrg_power[(spectral_axis < (freq_center_actual - sigma)) | (spectral_axis > (freq_center_actual + sigma))]
            masked_freqs = spectral_axis[(spectral_axis < (freq_center_actual - sigma)) | (spectral_axis > (freq_center_actual + sigma))]
            coeffs = np.polyfit(masked_freqs, masked_bin_avrg_power, deg=deg)
            baseline = np.polyval(coeffs, spectral_axis)
            
            plt.plot(spectral_axis, powers[:, idx], label=f'Original Measurement {idx}')
            plt.plot(spectral_axis, baseline, label=f'Baseline {idx}', alpha=0.6)
            plt.plot(spectral_axis, new_powers[:, idx-n//2], label=f'Baseline Subtracted Measurement {idx}', alpha=0.7)
        plt.xlabel('Frequency (Hz)')
        plt.ylabel('Power (W)')
        plt.title('Baseline Subtraction Example')
        plt.legend()
        plt.grid(True)
        plt.show()
    
    return new_powers

def computeNoiseIntegral(powers, spectral_axis, freq_center, sigma):
    """
    Returns the variance of the power over consequitive averaged measurements, integrated over a frequency range outside the central frequency.

    Args:
        powers (np.array): 2D array of power readings (cycles x frequencies).
        spectral_axis (np.array): 1D array of frequencies in Hz.
        freq_center (float): Central frequency to integrate outside of.
        sigma (float): Width around the central frequency to exclude in integration (+/- sigma).

    Returns:
        variance_integral (np.array): 1D array of integrated variance of power for each consequitive measurement.
        mean_powers (np.array): 1D array of mean power for each consequitive measurement (for reference).
    """

    if TEST_BOOL:
        start = time.time()

    # Get mask for frequencies outside the central region
# 1. Apply frequency mask (vectorized)
    mask = (spectral_axis < (freq_center - sigma)) | (spectral_axis > (freq_center + sigma))
    masked_powers = powers[mask, :] # Shape: (frequencies, measurements)

    # 2. Compute the running mean across measurements (axis=1)
    # cumsum / counts gives the mean of [:, 0:i+1] for every i
    counts = np.arange(1, masked_powers.shape[1] + 1)
    integrated_power_history = np.cumsum(masked_powers, axis=1) / counts

    # 3. Compute variance and mean for each integration step
    # We take the variance and mean across the frequency axis (axis=0)
    variance_integral = np.var(integrated_power_history, axis=0)
    mean_power_levels = np.mean(integrated_power_history, axis=0)

    print(f'Final Mean Power Integral: {mean_power_levels[-1]:.2e} W, '
          f'Final Variance Integral: {variance_integral[-1]:.2e} W')
    
    if TEST_BOOL:
        print(f"Noise integral computation took {time.time() - start:.4f} seconds")
        print(f'Log(abs)-lin correlation between variance and mean integrals: {np.corrcoef((np.diff(variance_integral[1:])), (np.diff(mean_power_levels[1:])))[0, 1]:.4f}')

        plt.scatter(variance_integral[1:], mean_power_levels[1:], label='Variance vs Mean Integral', color='purple', alpha=0.7)
        plt.show()
    
    return variance_integral, mean_power_levels


