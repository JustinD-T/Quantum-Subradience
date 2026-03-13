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
    Given a path to an experiment log, return metadata, powers, spectral axis, and pressure.
    
    Args:
        path (str): Path to the experiment log file (CSV with comment metadata).

    Returns:
        metadata (dict): Dictionary of configuration parameters.
        powers (np.array): 2D array of power readings (frequencies x measurements).
        spectral_axis (np.array): 1D array of frequencies in Hz.
        pressure (np.array): 1D array of pressure readings for each measurement.
    """
    metadata = {}

    if TEST_BOOL:
        start = time.time()

    if path.endswith('.csv'):
        # 1. Parse Metadata from comments
        with open(path, 'r') as f:
            for i, line in enumerate(f):
                if line.startswith('#'):
                    # Clean up the line and split by first colon
                    content = line.lstrip('#').strip()
                    if ':' in content:
                        key, val = content.split(':', 1)
                        metadata[key.strip()] = val.strip()
                else:
                    break
        
        # 2. Load Data using pandas
        df = pd.read_csv(path, comment='#')
        
        # 3. Extract Spectral Axis (frequencies)
        freq_columns = [col for col in df.columns if 'Hz' in col]
        spectral_axis = np.array([float(col.split(' ')[0]) for col in freq_columns])
        
        # 4. Extract Power values
        powers = df[freq_columns].to_numpy().transpose()  # Transpose to get frequencies x measurements

        # 5. Extract Pressure values
        pressure = df['Pressure'].to_numpy()

        # Save as numpy arrays for faster processing
        folder_name = path.replace('.csv', '_pickled_data').split('/')[-1]
        os.makedirs(folder_name, exist_ok=True)
        
        np.save(os.path.join(folder_name, 'powers.npy'), powers)
        np.save(os.path.join(folder_name, 'freqs.npy'), spectral_axis)
        np.save(os.path.join(folder_name, 'pressure.npy'), pressure)
        with open(os.path.join(folder_name, 'metadata.json'), 'w') as f:
            json.dump(metadata, f, indent=4)

        print(f"Data loaded and saved as numpy arrays in folder: {folder_name}")

    elif os.path.isdir(path):
        # Load from pre-saved numpy arrays
        powers = np.load(os.path.join(path, 'powers.npy'))
        spectral_axis = np.load(os.path.join(path, 'freqs.npy'))
        pressure = np.load(os.path.join(path, 'pressure.npy'))
        with open(os.path.join(path, 'metadata.json'), 'r') as f:
            metadata = json.load(f)
    
    if TEST_BOOL:
        print(f"Data loading and parsing took {time.time() - start:.4f} seconds")

    return powers, spectral_axis, pressure, metadata

def binData(powers, spectral_axis, n=10):
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
    n_bins = spectral_axis.shape[0] // n
    new_spectral_axis = np.zeros(n_bins)
    new_powers = np.zeros((n_bins, powers.shape[1]))

    for i in range(n_bins):
        # Get start and end indices for the current bin
        start_row = i * (n)
        end_row = (i + 1) * (n)

        # Get mean of axis and sum of powers for the current bin
        new_spectral_axis[i] = spectral_axis[start_row:end_row].mean()
        new_powers[i, :] = powers[start_row:end_row, :].sum(axis=0)
    
    if TEST_BOOL:
        print(f"Binning data took {time.time() - start:.4f} seconds")

    return new_powers, new_spectral_axis

def cleanData(powers, spectral_axis, freq_center, sigma, deg, n_sub):
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

    shot_noise_outliers = shotNoiseReject(powers)
    print(f"Identified {len(shot_noise_outliers)}/{powers.shape[1]} outliers based on shot noise thresholding.")
    
    # --- METHOD 1 --- Outlier detection based on variance integral increases
    # outlier_indices = varianceIncreaseOutlierDet(powers, spectral_axis, freq_center, sigma, deg=deg, n=n_sub)

    # --- METHOD 2 --- Outlier detection based on mean power deviations (commented out for now, can be used for comparison)
    # outlier_indices = meanPowerOutlierDet(powers, spectral_axis, freq_center, sigma)

    # --- METHOD 3 --- Outlier detection based on power deviations from median (commented out for now, can be used for comparison)
    # outlier_indices = powerMedDeviationOutlierDet(powers, spectral_axis, sigma, freq_center, deg=deg, n_sub=n_sub, tresh=2)

    # --- METHOD 4 --- Outlier detection based on true rolling variance (commented out for now, can be used for comparison)
    outlier_indices = trueRollingVarOutierDet(powers, spectral_axis, freq_center, sigma, deg=deg, n=n_sub)

    outlier_indices = np.unique(np.concatenate((outlier_indices, shot_noise_outliers)))

    mask = np.ones(powers.shape[1], dtype=bool)
    mask[outlier_indices] = False
    masked_powers = powers[:, mask]

    print(f"Removed {len(outlier_indices)}/{powers.shape[1]} outlier measurements")

    if TEST_BOOL:
        print(f"Data cleaning took {time.time() - start:.4f} seconds")
    
    return masked_powers, mask

def truncData(powers, n):
    return powers[:,:n]

# Data Processing Utilities
def subtractBaseline(powers, spectral_axis, freq_center, sigma, deg, n, ret_coeffs=False):
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

    if deg == 0:
        return powers

    new_powers = np.zeros_like(powers)

    coeffs_arr = np.zeros((powers.shape[1], deg + 1))

    # if n is 1 or 0, just do a single global fit to each measurement
    if n <= 1:
        for i in range(powers.shape[1]):
            # Get mask out central region for fitting
            masked_power = powers[:,i][(spectral_axis < (freq_center - sigma)) | (spectral_axis > (freq_center + sigma))]
            masked_freqs = spectral_axis[(spectral_axis < (freq_center - sigma)) | (spectral_axis > (freq_center + sigma))]

            # Fit polynomial to masked data
            coeffs = np.polyfit(masked_freqs, masked_power, deg=deg)
            coeffs_arr[i,:] = coeffs

            baseline = np.polyval(coeffs, spectral_axis)

            # Subtract baseline from original power data
            new_powers[:,i] = powers[:,i] - baseline

            #  -- TESTING PLOT ---
            # plt.plot(spectral_axis, powers[:,i], label='Original')
            # polyval = np.polyval(coeffs, spectral_axis)
            # plt.plot(spectral_axis, polyval, label='Baseline Fit')
            # plt.show()
        
        if ret_coeffs:
            return new_powers, coeffs_arr
        else:
            return new_powers

    # For n > 1, perform local fitting on rolling averages of n bins (excluding start/ends)
    else:

        # Itterate over each measurement
        for i in range(powers.shape[1]):

            # Exclude start/end measurements that can't form full bins
            if i < n//2 or i > powers.shape[1] - n//2:
                continue

            # Get average power of given bin (+/- n/2 measurements)
            bin_avrg_power = powers[:,i-n//2:i+n//2].mean(axis=1)

            # Get mask out central region for fitting
            masked_bin_avrg_power = bin_avrg_power[(spectral_axis < (freq_center - sigma)) | (spectral_axis > (freq_center + sigma))]
            masked_freqs = spectral_axis[(spectral_axis < (freq_center - sigma)) | (spectral_axis > (freq_center + sigma))]

            # Fit polynomial to masked data
            coeffs = np.polyfit(masked_freqs, masked_bin_avrg_power, deg=deg)
            coeffs_arr[i,:] = coeffs
            baseline = np.polyval(coeffs, spectral_axis)

            # Subtract baseline from original power data
            new_powers[:,i] = powers[:,i] - baseline
        
        # delete start/end excluded zero cols
        new_powers = new_powers[:,n//2:-n//2]

    if TEST_BOOL:
        print(f"Baseline subtraction took {time.time() - start:.4f} seconds")

    if ret_coeffs:
        return new_powers, coeffs_arr
    else:
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
    
    return variance_integral, mean_power_levels


def meanPowerOutlierDet(powers, spectral_axis, freq_center, sigma):
    """
    Identifies outliers in the mean power across measurements using a rolling standard deviation approach.

    Args:
        powers (np.array): 2D array of power readings (frequencies x measurements).
        spectral_axis (np.array): 1D array of frequencies in Hz.
        freq_center (float): Central frequency to exclude from fitting.
        sigma (float): Width around the central frequency to exclude in fitting (+/- sigma).

    Returns:
        outlier_indices (np.array): Indices of measurements identified as outliers based on mean power deviations.
    """

    if TEST_BOOL:
        start = time.time()

    powers = subtractBaseline(powers, spectral_axis, freq_center, sigma, deg=3, n=2)

    # Mask out central region
    mask = (spectral_axis < (freq_center - sigma)) | (spectral_axis > (freq_center + sigma))
    powers = powers[mask, :]

    # Compute mean power for each measurement
    mean_powers = np.mean(powers, axis=0)

    std_powers = np.std(mean_powers)

    # Identify outliers as measurements where mean power deviates more than 3 standard deviations from the overall mean
    overall_mean = np.mean(mean_powers)
    outlier_indices = np.where(np.abs(mean_powers - overall_mean) > 2 * std_powers)[0]

    return outlier_indices

def varianceIncreaseOutlierDet(powers, spectral_axis, freq_center, sigma, deg, n):
    """
    Identifies outliers based on increases in the variance integral across measurements.

    Args:
        powers (np.array): 2D array of power readings (frequencies x measurements).
        spectral_axis (np.array): 1D array of frequencies in Hz.
        freq_center (float): Central frequency to exclude from fitting.
        sigma (float): Width around the central frequency to exclude in fitting (+/- sigma).

    Returns:
        outlier_indices (np.array): Indices of measurements identified as outliers based on variance integral increases.
    """

    if TEST_BOOL:
        start = time.time()

    # sub data
    powers = subtractBaseline(powers, spectral_axis, freq_center, sigma, deg=deg, n=n)

    variance_integral, _ = computeNoiseIntegral(powers, spectral_axis, freq_center, sigma)

    var_diffs = np.diff(variance_integral)

    # Reject data if variance integral increases 
    outlier_indices = np.where(var_diffs > 0)[0] + 1  # +1 to correct for the diff offset

    if TEST_BOOL:
        print(f"Variance increase outlier detection took {time.time() - start:.4f} seconds")
        print(f"Identified {len(outlier_indices)}/{len(variance_integral)} outliers based on variance increases.")

    return outlier_indices


def powerMedDeviationOutlierDet(powers, spectral_axis, sigma, center_freq, deg, n_sub, tresh=3):
    """Filters outliers based on a certain standard deviations of the measurement given by the maximum power outside the central region
    in a given measurement, divided by its median value
    Args:
        powers (np.array): 2D array of power readings (frequencies x measurements).
        spectral_axis (np.array): 1D array of frequencies in Hz.
        sigma (float): Width around the central frequency to exclude in fitting (+/- sigma).
        center_freq (float): Central frequency to exclude from fitting.
        tresh (float): Number of standard deviations from the median to use as the outlier threshold.
    Returns:
        outlier_indices (np.array): Indices of measurements identified as outliers based on power deviations.
    """

    Spectral_mask = (spectral_axis < (center_freq - sigma)) | (spectral_axis > (center_freq + sigma))

    sub_powers = subtractBaseline(powers, spectral_axis, center_freq, sigma, deg=deg, n=n_sub)

    max_powers = np.max(sub_powers[Spectral_mask, :], axis=0)
    median_powers = np.median(sub_powers[Spectral_mask, :], axis=0)

    err = (max_powers / median_powers)**2

    std_err = np.std(err)

    # Identify outliers based on the threshold
    outlier_indices = np.where(err > np.median(err) + tresh * std_err)[0]

    return outlier_indices

def pressureDecayCurve(pressures, sweep_time):
    # Fits and saves a pressure decay curve fit for extrapolation
    time = np.linspace(sweep_time, (pressures.shape[0]+1)*sweep_time, pressures.shape[0])

    log_time = np.log(time)
    log_pressure = np.log(pressures)

    coeffs = np.polyfit(log_time, log_pressure, deg=1)

    def pressure_fit(t):
        return np.exp(coeffs[1]) * t**coeffs[0]

    return pressure_fit

def trueRollingVarOutierDet(powers, spectral_axis, freq_center, sigma, deg, n):
    
    powers = subtractBaseline(powers, spectral_axis, freq_center, sigma, deg=deg, n=n)

    powers_mask = (spectral_axis < (freq_center - sigma)) | (spectral_axis > (freq_center + sigma))
    powers = powers[powers_mask, :]

    # compute mean up to a point
    # compute the std of that mean
    # add the next value, see if the std increases
    # if no then reject that index

    rejected_indices = []
    accepted_indices = []

    rolling_mean = np.mean(powers[:,0], axis=0)
    rolling_std = np.std(powers[:,0], axis=0)

    rolling_sum = powers[:,0].copy()
    accepted_indices.append(0)

    for i in range(powers.shape[1]):
        new_sum = rolling_sum + powers[:,i]
        mean = new_sum / (len(accepted_indices) + 1)
        new_std = np.std(mean)

        if new_std < rolling_std:
            rolling_sum = new_sum
            rolling_std = new_std
            accepted_indices.append(i)
        else:
            rejected_indices.append(i)
    return np.array(rejected_indices)

def shotNoiseReject(powers):
    stds = np.std(powers, axis=0)
    medians = np.median(powers, axis=0)

    up_bound = medians + 25*stds

    outlier_indices = np.where(np.any(powers > up_bound, axis=0))[0]

    return outlier_indices
