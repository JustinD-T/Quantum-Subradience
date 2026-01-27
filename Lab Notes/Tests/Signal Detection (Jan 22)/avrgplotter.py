from matplotlib import pyplot as plt
import numpy as np
import pandas as pd

def load_data(path):
    df = pd.read_csv(path, comment='#')
    cols = df.columns

    freq_cols = [col for col in cols if 'Hz' in col]

    freqs = [float(col.replace(' Hz', '').strip())/1e6 for col in freq_cols]

    amp_df = df[freq_cols]

    pressures = df['Pressure']

    return amp_df, freqs, pressures

def subtract_continuum(amp_df):
    # Fit a 2nd order polynomial to the mean spectrum
    p = np.polyfit(np.arange(len(amp_df.columns)), amp_df.mean(axis=0), 2)
    # Create the polynomial function
    poly = np.poly1d(p)
    # Evaluate the polynomial at each frequency point to get the continuum
    continuum = poly(np.arange(len(amp_df.columns)))
    # Subtract the continuum from each row of the dataframe
    amp_df_cont_subtracted = amp_df.subtract(continuum, axis=1)
    return amp_df_cont_subtracted

def bin_data(amp_df, freqs, bin_size=5):
    # Bin the data by averaging over 'bin_size' frequency points
    num_bins = amp_df.shape[1] // bin_size
    binned_data = []
    for i in range(num_bins):
        bin_slice = amp_df.iloc[:, i*bin_size:(i+1)*bin_size]
        binned_data.append(bin_slice.mean(axis=1))
    binned_df = pd.DataFrame(binned_data).transpose()
    binned_freqs = [np.mean(freqs[i*bin_size:(i+1)*bin_size]) for i in range(num_bins)]
    return binned_df, binned_freqs

def hanning_filter(amp_df, freqs, window_size=5):
    # Apply a Hanning window filter along the frequency axis
    hanning_window = np.hanning(window_size)
    hanning_window /= hanning_window.sum()  # Normalize the window

    filtered_data = amp_df.copy()
    for i in range(amp_df.shape[0]):
        filtered_data.iloc[i, :] = np.convolve(amp_df.iloc[i, :], hanning_window, mode='same')
    
    return filtered_data, freqs

def plot_data(amp_df, freqs, sweep_time=2.5):
    integration_time = sweep_time * amp_df.shape[0] / 60
    plt.figure(figsize=(18, 6))
    plt.grid(True)
    y = amp_df.mean(axis=0)
    x = freqs
    plt.plot(x, y)
    plt.xlabel('Frequency (MHz)')
    plt.ylabel('Mean Amplitude (dBm)')
    plt.suptitle('Power Spectrum Averaged over {:.2f} minutes'.format(integration_time))
    plt.savefig(r'Lab Notes\Tests\Signal Detection (Jan 22)\Plots\averaged_spectrum.png')
    plt.close()

def plot_change(amp_df, freqs, pressures, sweep_time=2.5, datapoint_interval=100, zoom_to=None):
    plt.figure(figsize=(18, 10))
    plt.grid(True)
    x = freqs
    for i in range(0, amp_df.shape[0], datapoint_interval):
        start_index = i
        end_index = i + datapoint_interval
        if end_index > amp_df.shape[0]:
            end_index = amp_df.shape[0]
        
        if start_index == end_index:
            continue

        interval_df = amp_df.iloc[start_index:end_index]
        interval_pressures = pressures.iloc[start_index:end_index]
        
        y = interval_df.mean(axis=0)
        integration_time = sweep_time * interval_df.shape[0] / 60
        plt.plot(x, y, alpha=0.4, label=f'{integration_time:.2f} min @ {interval_pressures.mean():.2e} mbar')
        

    # Plot the final full average with full opacity
    y_final = amp_df.mean(axis=0)
    integration_time_final = sweep_time * amp_df.shape[0] / 60
    plt.plot(x, y_final, alpha=0.8, color='red', linewidth=1.5, label=f'Final: {integration_time_final:.2f} min @ {pressures.iloc[-1]:.2e} mbar')

    # Zoom into 1MHz around the center frequency
    if zoom_to is not None:
        center_freq = np.median(freqs)
        plt.xlim(center_freq - zoom_to/2, center_freq + zoom_to/2)

    plt.xlabel('Frequency (MHz)')
    plt.ylabel('Mean Amplitude (dBm)')
    plt.suptitle('Interval Average Power Spectrum Evolution')
    plt.legend() # Optional: can be crowded
    plt.savefig(r'Lab Notes\Tests\Signal Detection (Jan 22)\Plots\interval_average_spectrum.png')
    plt.close()

def plot_pressure_best_fit_derivative(pressures, sweep_time=2.5):
    time = np.arange(sweep_time, sweep_time * (len(pressures)+1), sweep_time ) / 60
    # Fit a linear model to the pressure data
    p = np.polyfit(time, pressures, 1)
    poly = np.poly1d(p)
    fitted_pressures = poly(time)
    derivative = p[0]  # Slope of the fitted line
    time_to_1mbar = (1 - p[1]) / derivative if derivative != 0 else float('inf')

    plt.figure(figsize=(10, 5))
    plt.grid(True)
    plt.plot(time, pressures, label='Measured Pressure')
    plt.plot(time, fitted_pressures, label='Best Fit Line', linestyle='--')
    plt.xlabel('Time (Minutes)')
    plt.ylabel('Pressure (mbar)')
    # plt.xscale('log')
    plt.yscale('log')
    plt.suptitle(f'Pressure versus Time with Best Fit Line\nDerivative: {derivative:.4e} mbar/min, Time to 1mbar: {time_to_1mbar:.2f} min')
    plt.legend()
    plt.savefig(r'Lab Notes\Tests\Signal Detection (Jan 22)\Plots\pressure_best_fit_derivative.png')
    plt.close()

def power_vs_pressure(amp_df, freqs, pressures, N_AVRG=100, WIDTH=0.05):
    """
    Plots the integrated power within a specified width around the central frequency
    versus the average pressure for intervals of N_AVRG readings.
    """
    # Find the central frequency and the indices for the integration width
    center_freq = np.median(freqs)
    freq_mask = (np.array(freqs) >= center_freq - WIDTH/2) & (np.array(freqs) <= center_freq + WIDTH/2)
    
    integrated_powers = []
    average_pressures = []

    # Iterate through the data in chunks of N_AVRG
    for i in range(0, amp_df.shape[0], N_AVRG):
        end_index = i + N_AVRG
        if end_index > amp_df.shape[0]:
            end_index = amp_df.shape[0]
        
        if i == end_index:
            continue

        # Select the chunk of data and pressures
        interval_df = amp_df.iloc[i:end_index]
        interval_pressures = pressures.iloc[i:end_index]

        # Calculate the mean spectrum for the interval
        mean_spectrum = interval_df.mean(axis=0)
        
        # Take the absolute value and integrate the power within the specified frequency width
        power_in_width = np.abs(mean_spectrum[freq_mask]).sum()
        
        # Calculate the average pressure for the interval
        avg_pressure = interval_pressures.median()

        integrated_powers.append(power_in_width)
        average_pressures.append(avg_pressure)

    # Create the scatter plot
    plt.figure(figsize=(10, 6))
    plt.grid(True)
    plt.scatter(average_pressures, integrated_powers)
    
    # Fit a line to the data
    p = np.polyfit(average_pressures, integrated_powers, 1)
    poly = np.poly1d(p)
    plt.plot(average_pressures, poly(average_pressures), "r--", label=f"Fit: y={p[0]:.2f}x + {p[1]:.2f}")

    plt.xlabel('Median Pressure (mbar)')
    # plt.xscale('log')
    plt.ylabel(f'Integrated Power (in +/- {WIDTH/2} MHz window)')
    plt.suptitle(f'Integrated Power vs. Pressure (Averaged over {N_AVRG} readings)')
    plt.legend()
    plt.savefig(r'Lab Notes\Tests\Signal Detection (Jan 22)\Plots\power_vs_pressure.png')
    plt.close()

if __name__ == "__main__":
    path = r'Lab Notes\Tests\Signal Detection (Jan 22)\Data\Jan22FullRun.csv'
    # path = r'Lab Notes\Tests\Signal Detection (Jan 22)\Data\Jan22FullRun.csv'
    sweep_time = 2.5  # seconds
    amp_df, freqs, pressures = load_data(path)
    # amp_df = subtract_continuum(amp_df)
    # amp_df, freqs = bin_data(amp_df, freqs, bin_size=5)
    # amp_df, freqs = hanning_filter(amp_df, freqs, window_size=5)
    plot_change(amp_df, freqs, pressures, sweep_time, datapoint_interval=1000, zoom_to=0.5)
    plot_data(amp_df, freqs, sweep_time)
    plot_pressure_best_fit_derivative(pressures, sweep_time)
    power_vs_pressure(amp_df, freqs, pressures, N_AVRG=50, WIDTH=0.001)