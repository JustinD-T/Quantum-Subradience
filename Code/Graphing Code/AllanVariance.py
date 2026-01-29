from Utils import load_data
from scipy.signal import savgol_filter
import numpy as np
import matplotlib.pyplot as plt

def determine_baseline(spectrum_df, window_size=101):

    average = spectrum_df.mean(axis=0)

    sv = savgol_filter(average, window_size, polyorder=2)

    return sv

def subtract_baseline(spectrum_df, baseline):
    corrected_df = spectrum_df - baseline
    return corrected_df

def allan_variance(spectrum_df, sweep_time):
    """
    Computes and plots the Allan variance for a given time series of spectral data.

    Args:
        spectrum_df (pd.DataFrame): DataFrame with frequencies as columns and
                                    time-series amplitude data in rows.
        sweep_time (float): The time in seconds between each row (measurement).
    """

    # Integrate over the frequency spectrum for each time point to get a single time series
    y = spectrum_df.sum(axis=1).values
    N = len(y)
    
    # Tau values (cluster sizes) to calculate variance for
    # Use powers of 2 for efficient calculation, up to N/2
    max_m = N // 2
    m = np.logspace(0, np.log10(max_m), 50, dtype=int)
    m = np.unique(m) # Remove duplicates

    taus = m * sweep_time
    allan_variances = []

    for val in m:
        if val == 0:
            continue
        # Number of clusters of size m
        num_clusters = N - 2 * val + 1
        if num_clusters <= 0:
            break
        
        # Calculate the difference of means of adjacent clusters
        term1 = y[val:N-val+1]
        term2 = y[:N-2*val+1]
        
        diffs = np.sum(np.reshape(term1 - term2, (num_clusters, val)), axis=1)
        
        # Allan variance for this tau
        avar = np.sum(diffs**2) / (2 * num_clusters * val**2 * sweep_time**2)
        allan_variances.append(avar)

    # The number of valid taus might be less than the initial list
    valid_taus = taus[:len(allan_variances)]

    # Plotting the Allan Deviation (sqrt of variance)
    plt.figure()
    plt.plot(valid_taus, np.sqrt(allan_variances))
    plt.xscale('log')
    plt.yscale('log')
    plt.xlabel('Integration Time (τ) [s]')
    plt.ylabel('Allan Deviation (σ_y(τ))')
    plt.title('Allan Deviation')
    plt.grid(True, which="both", ls="--")
    plt.show()

    return valid_taus, np.sqrt(allan_variances)

if __name__ == "__main__":
    path = r'Code\Graphing Code\ExperimentLog_20260129-123129.csv'
    headers_df, spectrum_df = load_data(path)
    baseline = determine_baseline(spectrum_df)
    corrected_df = subtract_baseline(spectrum_df, baseline)
    taus, allan_devs = allan_variance(corrected_df, 2.5)