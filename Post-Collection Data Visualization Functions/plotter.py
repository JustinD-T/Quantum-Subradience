import pandas as pd
import numpy as np

import matplotlib.pyplot as plt

def plot_pressure_data(csv_path):
    """
    Reads pressure data from a CSV, plots the data on a log-log scale,
    fits a power law (linear fit in log-log space), extends the fit to 1 atm,
    and displays the estimated time to full decompression.

    Args:
        csv_path (str): The path to the CSV file. The file should have
                        'Timestamp' and 'Pressure_hPa' columns.
    """
    # 1. Load and process data
    df = pd.read_csv(csv_path, sep=',')
    df['Timestamp'] = pd.to_datetime(df['Timestamp'])

    # Find the index of the minimum pressure and slice the data from that point
    min_pressure_idx = df['Pressure_hPa'].idxmin()
    df = df.loc[min_pressure_idx:].reset_index(drop=True)

    # Normalize time to minutes from the start of the sliced data
    time_minutes = (df['Timestamp'] - df['Timestamp'].iloc[0]).dt.total_seconds() / 60
    pressure_hpa = df['Pressure_hPa']

    # Filter out non-positive time values for log scale compatibility
    positive_time_mask = time_minutes > 0
    time_minutes_log_scale = time_minutes[positive_time_mask]
    pressure_hpa_log_scale = pressure_hpa[positive_time_mask]

    # 2. Perform power-law fit (linear fit in log-log space)
    # A degree of 1 in log-log space corresponds to a power law P = a * t^b
    degree = 3
    # Fit log(pressure) vs log(time)
    log_coeffs = np.polyfit(np.log(time_minutes_log_scale), np.log(pressure_hpa_log_scale), degree)
    log_poly_fit_func = np.poly1d(log_coeffs)

    # 3. Extend the fit until 1 atm (1013.25 hPa)
    target_pressure_hpa = 1013.25
    time_to_atm = None
    
    # We are solving log(P_target) = m*log(t) + c  for t
    # log(t) = (log(P_target) - c) / m
    # t = exp((log(P_target) - c) / m)
    # We are solving log(P_target) = p(log(t)) for t, where p is the polynomial fit.
    # This is equivalent to finding the roots of the polynomial p(log(t)) - log(P_target) = 0.
    poly_coeffs_for_roots = log_coeffs.copy()
    poly_coeffs_for_roots[-1] -= np.log(target_pressure_hpa)
    
    # Find the roots for log(time)
    log_time_roots = np.roots(poly_coeffs_for_roots)
    
    # Filter for real roots and convert to time
    real_log_time_roots = log_time_roots[np.isreal(log_time_roots)].real
    possible_times = np.exp(real_log_time_roots)
    
    # Find the first time that is greater than our last measurement
    valid_times = possible_times[possible_times > time_minutes_log_scale.max()]
    if len(valid_times) > 0:
        time_to_atm = np.min(valid_times)

    # Create a time array for plotting the fit, extended to the decompression time
    time_fit_end = time_to_atm if time_to_atm and time_to_atm > time_minutes_log_scale.max() else time_minutes_log_scale.max()
    time_fit = np.logspace(np.log10(time_minutes_log_scale.min()), np.log10(time_fit_end), 500)
    
    # Calculate pressure values from the fit in log-log space
    pressure_fit = np.exp(log_poly_fit_func(np.log(time_fit)))

    # 4. Plotting
    plt.style.use('seaborn-v0_8-whitegrid')
    fig, ax = plt.subplots(figsize=(12, 7))

    # Plot observed data (on log-log scale)
    ax.loglog(time_minutes_log_scale, pressure_hpa_log_scale, 'o', label='Observed Data', markersize=4)

    # Plot the power-law fit
    ax.loglog(time_fit, pressure_fit, '-', label=f'Power Law Fit (P ~ t^{log_coeffs[0]:.2f})', color='red')

    # Add a horizontal line for 1 atm
    ax.axhline(y=target_pressure_hpa, color='gray', linestyle='--', label='1 atm (1013.25 hPa)')

    # Display time to full decompression
    title = 'Pressure vs. Time (Log-Log Scale)'
    if time_to_atm is not None:
        title += f'\nEstimated Time to 1 atm: {time_to_atm:.2f} minutes'
    ax.set_title(title)
    
    ax.set_xlabel('Time (minutes from start)')
    ax.set_ylabel('Pressure (hPa)')
    ax.legend()
    ax.grid(True, which="both", ls="--")

    plt.tight_layout()
    plt.show()


if __name__ == '__main__':
    # Example usage:
    # Make sure to replace 'path/to/your/data.csv' with the actual file path.
    # For example: r'wave_data\data_20251030-124357.csv'
    try:
        print("Running plotter with data...")
        plot_pressure_data(r'wave_data\data_20251030-124357.csv')
    except FileNotFoundError:
        print("Error: Data file not found. Please update the path in the if __name__ == '__main__': block.")

