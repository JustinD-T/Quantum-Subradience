import json 
import csv

import numpy as np
import pandas as pd

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
    
    return powers, spectral_axis, metadata   

def binData(powers, spectral_axis, n=300):
    """
    Bin the power data into n groups, computing the sum of the power and 
    using the mean frequencies in each bin.

    Args:
        meta (dict): Metadata dictionary (not used in this function but can be useful for future extensions).
        powers (np.array): 2D array of power readings (frequencies x measurements).
        spectral_axis (np.array): 1D array of frequencies in Hz.
        n (int): Number of bins to create.
    
    Returns:
        binned_powers (np.array): 2D array of binned power values (bins x frequencies).
        binned_freqs (np.array): 1D array of mean frequencies for each bin.
    """

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

    return new_powers, new_spectral_axis

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

    # Get mask for frequencies outside the central region
    masked_powers = powers[(spectral_axis < (freq_center - sigma)) | (spectral_axis > (freq_center + sigma))]
    mean_power_levels = np.zeros(powers.shape[1])
    variance_integral = np.zeros(powers.shape[1])

    # Itterate over each measurement
    for i in range(powers.shape[1]):

        # Compute the mean up until i
        integrated_power = masked_powers[:,0:i+1].mean(axis=1)

        # Compute the variance and mean of the integrated power
        variance = integrated_power.var(axis=0)
        mean_power_level = integrated_power.mean(axis=0)

        variance_integral[i] = variance
        mean_power_levels[i] = mean_power_level
    
    print(f'Final Mean Power Integral: {mean_power_levels[-1]:.2e} W, Final Variance Integral: {variance_integral[-1]:.2e} W')
    return variance_integral, mean_power_levels






