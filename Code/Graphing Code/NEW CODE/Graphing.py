from Utilities import loadData, binData, subtractBaseline, computeNoiseIntegral
from matplotlib import pyplot as plt
import numpy as np
import argparse

def plotNoiseVsTimeAndMeasurement(powers, spectral_axis, meta, sigma, save_fig=False):
    # Metadata parsing: convert ms to s
    sweep_time = float(meta.get('Sweep Time (ms)', 0))  
    n_measurements = powers.shape[1]
    time_axis = np.arange(n_measurements) * sweep_time

    variance_integral, mean_integral = computeNoiseIntegral(
        powers, spectral_axis, 
        freq_center=float(meta['Center Frequency (Hz)']), 
        sigma=sigma
    )

    fig, ax1 = plt.subplots(figsize=(12, 6), facecolor='black')
    ax1.set_facecolor('black')

    meas_indices = np.arange(1, n_measurements + 1)
    ax1.plot(meas_indices, variance_integral, color='cyan', linewidth=2, label='Variance')
    
    ax1.set_xlabel('Measurement Number', color='white', fontsize=12)
    ax1.set_ylabel('Variance Integral (W)', color='cyan', fontsize=12)
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
    ax2.plot(meas_indices, mean_integral, color='yellow', linewidth=2, alpha=0.6, label='Mean Power')
    ax2.set_ylabel('Mean Power Integral (W)', color='yellow', fontsize=12)
    ax2.tick_params(axis='y', labelcolor='yellow')
    ax2.spines['right'].set_color('yellow')

    plt.title('Noise Variance vs Measurement Number and Time', color='white', fontsize=14, pad=20)
    fig.tight_layout()

    if save_fig:
        plt.savefig('noise_vs_time_measurement.png', facecolor='black', dpi=300)
        plt.close()
    else:
        plt.show()

def plotSignal(powers, spectral_axis, title, sigma, central_freq, init_CO_level, sum_data=True, save_fig=False):
    signal = powers.sum(axis=1) if sum_data else powers.mean(axis=1)

    fig, ax = plt.subplots(figsize=(10, 6), facecolor='black')
    ax.set_facecolor('black')
    ax.plot(spectral_axis, signal, color='white', linewidth=1)
    
    ax.axvspan(central_freq - sigma, central_freq + sigma, color='green', alpha=0.3, label=r'$\pm \sigma$ Region')
    
    ax.set_xlabel('Frequency (Hz)', color='white')
    ax.set_ylabel('Power (W)', color='white')
    ax.set_title(f'{title}\nInitial CO: {init_CO_level}', color='white')
    
    for spine in ax.spines.values(): spine.set_color('white')
    ax.tick_params(colors='white')
    ax.legend(facecolor='black', labelcolor='white')
    
    fig.tight_layout()
    if save_fig:
        plt.savefig('signal_plot.png', facecolor='black', dpi=300)
        plt.close()
    else:
        plt.show()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--path', type=str, required=True)
    parser.add_argument('--sigma', type=float, default=500e3)
    parser.add_argument('--save_fig', action='store_true')
    parser.add_argument('--deg', type=int, default=2)
    parser.add_argument('--n_sub', type=int, default=6)
    parser.add_argument('--sub', action='store_true')
    parser.add_argument('--bin', action='store_true')
    parser.add_argument('--n_bins', type=int, default=101)
    parser.add_argument('--plot_noise', action='store_true')
    parser.add_argument('--plot_signal', action='store_true')
    parser.add_argument('--signal_sum', action='store_true')
    parser.add_argument('--defs', action='store_true')

    args = parser.parse_args()
    if args.defs:
        args.save_fig, args.sub, args.bin = True, True, True
        args.plot_noise, args.plot_signal, args.signal_sum = True, True, False

    powers, freqs, meta = loadData(args.path)

    if args.bin:
        powers, freqs = binData(powers, freqs, n=args.n_bins)

    if args.sub:
        powers = subtractBaseline(powers, freqs, float(meta['Center Frequency (Hz)']), args.sigma, args.deg, args.n_sub)
    
    if args.plot_noise:
        plotNoiseVsTimeAndMeasurement(powers, freqs, meta, args.sigma, args.save_fig)
    
    if args.plot_signal:
        plotSignal(powers, freqs, meta['Experiment Description'], args.sigma, float(meta['Center Frequency (Hz)']), meta['initial_CO_concentration (ppm)'], args.signal_sum, args.save_fig)