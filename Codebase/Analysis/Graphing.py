import argparse
import time

from Utilities import loadData, binData, subtractBaseline, computeNoiseIntegral, cleanData, truncData

from matplotlib import pyplot as plt
import numpy as np
from scipy.signal import gauss_spline

global TEST_BOOL
TEST_BOOL = True

def plotNoiseVsTimeAndMeasurement(powers, spectral_axis, meta, sigma, save_fig=False):

    if TEST_BOOL:
        start = time.time()

    sweep_time = float(meta.get('Sweep Time (ms)', 0))  
    n_measurements = powers.shape[1]
    time_axis = np.arange(n_measurements) * sweep_time

    variance_integral, mean_integral = computeNoiseIntegral(
        powers, spectral_axis, 
        freq_center=float(meta['Center Frequency (Hz)']), 
        sigma=sigma
    )

    std_integral = np.sqrt(variance_integral)

    fig, ax1 = plt.subplots(figsize=(12, 6), facecolor='black')
    ax1.set_facecolor('black')

    meas_indices = np.arange(1, n_measurements + 1)
    ax1.plot(meas_indices[1:], std_integral[1:], color='magenta', linewidth=2, label='Std Dev')
    ax1.set_xlabel('Measurement Number', color='white', fontsize=12)
    ax1.set_ylabel('Std Dev Integral (W)', color='cyan', fontsize=12)
    ax1.set_yscale('log')
    ax1.set_xscale('log')
    ax1.tick_params(axis='both', colors='white')
    ax1.tick_params(axis='y', labelcolor='cyan')
    
    for spine in ['top', 'right']: ax1.spines[spine].set_visible(False)
    ax1.spines['bottom'].set_color('white')
    ax1.spines['left'].set_color('white')
    ax1.grid(True, alpha=0.2, color='white')

    # Top axis for Time
    ax1_top = ax1.twiny()
    ax1_top.set_xscale('log')
    ax1_top.set_xlim(ax1.get_xlim())
    
    def get_time_label(x):
        idx = int(round(x)) - 1
        return f"{time_axis[idx]:.2f}" if 0 <= idx < len(time_axis) else ""

    ticks = ax1.get_xticks()
    ax1_top.set_xticks(ticks)
    ax1_top.set_xticklabels([get_time_label(t) for t in ticks], color='white')
    ax1_top.set_xlabel('Time (s)', color='white', fontsize=12)

    # Right axis for Mean Power
    ax2 = ax1.twinx()
    # ax2.set_yscale('log')
    ax2.set_xscale('log')
    ax2.plot(meas_indices[1:], mean_integral[1:], color='yellow', linewidth=2, alpha=0.6, label='Mean Power')
    ax2.set_ylabel('Mean Power Integral (W)', color='yellow', fontsize=12)
    ax2.tick_params(axis='y', labelcolor='yellow')
    ax2.spines['right'].set_color('yellow')

    # Plot 1/sqrt(time) decay for reference
    white_noise_line = std_integral[1] / np.sqrt(time_axis[1:] / time_axis[1])
    ax1.plot(meas_indices[1:], white_noise_line, color='cyan', linestyle='--', linewidth=1.5, label=r'$\propto 1/\sqrt{t}$')
    ax1.legend(loc='upper left', facecolor='black', labelcolor='white')


    plt.title('Noise Variance vs Measurement Number and Time', color='white', fontsize=14, pad=20)
    fig.tight_layout()

    if TEST_BOOL:
        print(f"Noise vs Time plot generation took {time.time() - start:.4f} seconds")

    if save_fig:
        plt.savefig(r'Codebase\Analysis\Figure Dump\noise_vs_time_measurement.png', facecolor='black', dpi=300)
        plt.close()
    else:
        plt.show()
    plt.close()

def plotSignal(powers, spectral_axis, title, sigma, central_freq, init_CO_level, sum_data=True, save_fig=False):

    if TEST_BOOL:
        start = time.time()

    signal = powers.sum(axis=1) if sum_data else powers.mean(axis=1)

    # normalize spectral axis
    spectral_axis = spectral_axis - central_freq

    fig, ax = plt.subplots(figsize=(10, 6), facecolor='black')
    ax.set_facecolor('black')
    ax.plot(spectral_axis, signal, color='white', linewidth=1)
    
    ax.axvspan(-sigma, +sigma, color='green', alpha=0.3, label=r'$\pm \sigma$ Region')
    
    ax.set_xlabel('Frequency (MHz)', color='white')
    ax.set_ylabel('Power (W)', color='white')
    ax.set_title(f'{title}\nInitial CO: {init_CO_level}', color='white')
    
    for spine in ax.spines.values(): spine.set_color('white')
    ax.tick_params(colors='white')
    ax.legend(facecolor='black', labelcolor='white')

    if TEST_BOOL:
        print(f"Signal plot generation took {time.time() - start:.4f} seconds")

    
    fig.tight_layout()
    if save_fig:
        plt.savefig(r'Codebase\Analysis\Figure Dump\signal_plot.png', facecolor='black', dpi=300)
        plt.close()
    else:
        plt.show()
    plt.close()

def plotPeakVsTime(powers, freqs, center_freq, sigma=500e3, save_fig=False):
    cumsum = np.cumsum(powers, axis=1)
    rol_avrg = cumsum / np.arange(1, powers.shape[1] + 1)
    peak_roll_avrg = rol_avrg[(freqs >= center_freq - sigma/2) & (freqs <= center_freq + sigma/2), :]
    peak_indices = np.argmax(peak_roll_avrg, axis=0) + np.where((freqs >= center_freq - sigma/2) & (freqs <= center_freq + sigma/2))[0][0]
    std = np.std(rol_avrg[((freqs <= center_freq - sigma/2) | (freqs >= center_freq + sigma/2)), :], axis=0)
    mean_powers = np.mean(rol_avrg[((freqs <= center_freq - sigma/2) | (freqs >= center_freq + sigma/2)), :], axis=0)
    power_ratio = (rol_avrg[peak_indices, np.arange(powers.shape[1])])[100:]
    meas_axis = np.arange(1, powers.shape[1] + 1)[100:]
    
    fig, ax = plt.subplots(figsize=(10, 6), facecolor='black')
    ax.set_facecolor('black')
    ax.fill_between(meas_axis, mean_powers[100:] - 3*std[100:], mean_powers[100:] + 3*std[100:], alpha=0.2, color='blue', label='±3σ Baseline Error')
    ax.fill_between(meas_axis, mean_powers[100:], alpha=0.4, label='Mean Power', color='blue')
    ax.plot(meas_axis, mean_powers[100:], 'b-', linewidth=2)
    ax.fill_between(meas_axis, power_ratio, alpha=0.4, label='Peak/Mean Power Ratio', color='green')
    ax.plot(meas_axis, power_ratio, 'g-', linewidth=2)
    # ax.axhline(1, color='red', linestyle='--', label='Ratio = 1')
    ax.set_xlabel('Measurement Number', color='white')
    ax.set_ylabel('Power (W)', color='white')
    # ax.set_xscale('log')
    ax.set_title('Peak to Mean Power Ratio vs Measurement Number', color='white')
    ax.tick_params(colors='white')
    for spine in ax.spines.values(): spine.set_color('white')
    ax.legend(facecolor='black', labelcolor='white')
    ax.grid(True, alpha=0.2, color='white')
    
    fig.tight_layout()
    if save_fig:
        plt.savefig(r'Codebase\Analysis\Figure Dump\peak_vs_time.png', facecolor='black', dpi=300)
    plt.close()



if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--path', type=str, required=True)
    parser.add_argument('--sigma', type=float, default=1e6)
    parser.add_argument('--save_fig', action='store_true')
    parser.add_argument('--deg', type=int, default=1)
    parser.add_argument('--n_sub', type=int, default=1)
    parser.add_argument('--sub', action='store_true')
    parser.add_argument('--bin', action='store_true')
    parser.add_argument('--bin_factor', type=int, default=120)
    parser.add_argument('--plot_noise', action='store_true')
    parser.add_argument('--plot_signal', action='store_true')
    parser.add_argument('--signal_sum', action='store_true')
    parser.add_argument('--defs', action='store_true')
    parser.add_argument('--clean', action='store_true', help='Run cleaning routine to remove outlier data')

    args = parser.parse_args()
    if args.defs:
        args.save_fig, args.sub, args.bin = True, True, True
        args.plot_noise, args.plot_signal, args.signal_sum, args.clean = True, True, False, True

    powers, freqs, meta = loadData(args.path)

    # --- TEST: Generate synthetic Gaussian noise for testing
    # n_measurements = 5587
    # n_points = 6667
    # freq_range = 20e6
    # freqs = np.linspace(-freq_range/2, freq_range/2, n_points) + 2.5e9
    # powers = np.random.normal(0, 1, (n_points, n_measurements))
    # powers, freqs = powers_test, freqs_test

    # --- TEST: offset center
    # meta['Center Frequency (Hz)'] = float(meta['Center Frequency (Hz)']) + 2.5e6

    # --- TEST: Truncate to the first n measurements
    # powers = truncData(powers, n=350)

    # --- Preprocessing ---

    if args.clean:
        powers, _ = cleanData(powers, freqs, float(meta['Center Frequency (Hz)']), args.sigma, deg=args.deg, n_sub=args.n_sub)

    if args.sub:
        powers = subtractBaseline(powers, freqs, float(meta['Center Frequency (Hz)']), args.sigma, args.deg, args.n_sub)

    # mask = (freqs < float(meta['Center Frequency (Hz)']) + args.sigma) | (freqs > float(meta['Center Frequency (Hz)']) + args.sigma)
    # plt.scatter(np.max(powers[mask, :], axis=0) - np.median(powers[mask, :], axis=0), np.arange(powers.shape[1]), s=1)
    # plt.show()

    if args.bin:
        powers, freqs = binData(powers, freqs, n=args.bin_factor)

    # --- Plotting ---

    if args.plot_noise:
        plotNoiseVsTimeAndMeasurement(powers, freqs, meta, args.sigma, args.save_fig)
    
    if args.plot_signal:
        plotSignal(powers, freqs, meta['Experiment Description'], args.sigma, float(meta['Center Frequency (Hz)']), meta['initial_CO_concentration (ppm)'], args.signal_sum, args.save_fig)