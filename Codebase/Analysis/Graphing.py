import argparse
import time
from pathlib import Path
from datetime import datetime

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

    signal_mean = np.mean(signal[(spectral_axis < -sigma) | (spectral_axis > sigma)], axis=0)
    signal_std = np.std(signal[(spectral_axis < -sigma) | (spectral_axis > sigma)], axis=0)

    fig, ax = plt.subplots(figsize=(10, 6), facecolor='black')
    ax.set_facecolor('black')
    ax.plot(spectral_axis, signal, color='white', linewidth=1)
    
    
    ax.axhspan(signal_mean - signal_std, signal_mean + signal_std, color='red', alpha=0.05, label=r'±1σ Noise Level')
    ax.axhspan(signal_mean - 2*signal_std, signal_mean + 2*signal_std, color='orange', alpha=0.05, label=r'±2σ Noise Level')
    ax.axhspan(signal_mean - 3*signal_std, signal_mean + 3*signal_std, color='yellow', alpha=0.05, label=r'±3σ Noise Level')
    ax.axhline(signal_mean, color='red', linestyle='--', linewidth=1, label='Mean Noise Level', alpha=0.6)
    ax.axvspan(-sigma, +sigma, color='green', alpha=0.3, label=r'$\pm \sigma_{signal}$ Region')

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

def plotBaseline(powers, spectral_axis, center_freq, sigma=500e3, deg=3, n_sub=10, save_fig=False):
    powers = np.mean(powers, axis=1)
    power_mask = (spectral_axis >= center_freq - sigma) & (spectral_axis <= center_freq + sigma)
    baseline_mask = ~power_mask
    baseline_freqs = spectral_axis[baseline_mask]
    baseline_powers = powers[baseline_mask]
    coeffs = np.polyfit(baseline_freqs, baseline_powers, deg=deg)
    baseline_fit = np.polyval(coeffs, spectral_axis)
    fig, ax = plt.subplots(figsize=(10, 6), facecolor='black')
    ax.set_facecolor('black')
    ax.set_xlabel('Frequency (MHz)', color='white')
    ax.set_ylabel('Power (W)', color='white')
    ax.axvspan(center_freq - sigma, center_freq + sigma, color='red', alpha=0.2, label='Center Avoidance Area')
    ax.tick_params(colors='white')
    ax.plot(spectral_axis, powers, color='white', linewidth=1, label='Average Power', alpha=0.6)
    ax.plot(spectral_axis, baseline_fit, color='cyan', linewidth=2, label='Baseline Fit')

    if save_fig:
        plt.savefig(r'Codebase\Analysis\Figure Dump\baseline_fits.png', facecolor='black', dpi=300)
        plt.close()
    else:
        plt.show()
    plt.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--path', type=str, required=True)
    parser.add_argument('--sigma', type=float, default=2.5e6)
    parser.add_argument('--save_fig', action='store_true')
    parser.add_argument('--deg', type=int, default=3)
    parser.add_argument('--n_sub', type=int, default=1)
    parser.add_argument('--sub', action='store_true')
    parser.add_argument('--bin', action='store_true')
    parser.add_argument('--bin_factor', type=int, default=120)
    parser.add_argument('--plot_noise', action='store_true')
    parser.add_argument('--plot_signal', action='store_true')
    parser.add_argument('--signal_sum', action='store_true')
    parser.add_argument('--defs', action='store_true')
    parser.add_argument('--plot_baseline', action='store_true')
    parser.add_argument('--clean', action='store_true', help='Run cleaning routine to remove outlier data')

    args = parser.parse_args()
    if args.defs:
        args.save_fig, args.sub, args.bin = True, True, True
        args.plot_noise, args.plot_signal, args.signal_sum, args.clean = True, True, False, True
        args.plot_baseline = True
    powers, freqs, pressures, meta = loadData(args.path)

    # --- TESTING FEATURES ---
    SIM_DATA = False
    CHANGE_CONCENTRATION = False
    OFFSET_CENTER = False
    TRUNCATE_SIGNAL = False
    BRUTE_FORCE_CLEAN = False
    INTERPOLATE_PRESSURES = False
    GRAPH_REJECTS = False
    CLEANING_ROUTINES = {
        1 : "Single Itteration Variance Integral Clean",
        2 : "Mean Power Outlier Clean",
        3 : "Median Power Outlier Clean",
        4 : "True Rolling Variance Clean"
    }
    CLEANING_ROUTINE = 1

    # --- TEST: Interpolate pressures to match number of measurements if needed
    if INTERPOLATE_PRESSURES:
        from SignalSim import interpolatePressures
        pressures = interpolatePressures(pressures, int(powers.shape[1]), float(meta.get('Sweep Time (ms)', 4)))

    # --- TEST: Change initial CO concentration in metadata for testing ---
    if CHANGE_CONCENTRATION:
        new_conc = input('TEST: Input new initial CO concentration in ppm for testing: ')
        meta['initial_CO_concentration (ppm)'] = new_conc

    # --- TEST: Generate synthetic Gaussian noise for testing
    if SIM_DATA:
        from SignalSim import getSimulatedData
        SIM_SIGNAL = input('TEST: SIMULATE CO SIGNAL? (y/n): ').lower() == 'y'
        powers, freqs = getSimulatedData(powers, freqs, pressures, meta, sim_co=SIM_SIGNAL)

    # --- TEST: offset center
    if OFFSET_CENTER:
        offset = input('TEST: input center frequency offset in MHz: ')
        meta['Center Frequency (Hz)'] = float(meta['Center Frequency (Hz)']) + float(offset) * 1e6

    if TRUNCATE_SIGNAL:
        # --- TEST: Truncate to the first n measurements
        n = input('TEST: Input Data Truncation End Index: ')
        powers = truncData(powers, n=int(n))

    if args.plot_baseline:
        plotBaseline(powers, freqs, float(meta['Center Frequency (Hz)']), args.sigma, args.deg, args.n_sub, args.save_fig)
    
    if BRUTE_FORCE_CLEAN:
        cleaning_itterations = int(input('TEST: Input number of cleaning iterations; or \'0\' to run continously until rejection rate is 0: '))
        
        # recursive clean:
        if cleaning_itterations < 0:
            for i in range(cleaning_itterations):
                print(f"Cleaning iteration {i+1}/{cleaning_itterations}...", end='\r')
                powers, _ = cleanData(powers, freqs, float(meta['Center Frequency (Hz)']), args.sigma, deg=args.deg, n_sub=args.n_sub, cleaning_method=CLEANING_ROUTINES.get(CLEANING_ROUTINE))
        else:
            while True:
                print(f"Cleaning iteration {cleaning_itterations+1}...", end='\r')
                powers, mask = cleanData(powers, freqs, float(meta['Center Frequency (Hz)']), args.sigma, deg=args.deg, n_sub=args.n_sub, cleaning_method=CLEANING_ROUTINES.get(CLEANING_ROUTINE))
                cleaning_itterations += 1
                if mask.all():
                    break
        print("Data cleaning complete. Final shape:", powers.shape)
    # --- Preprocessing ---

    if args.clean:
        if GRAPH_REJECTS:
            _, mask = cleanData(powers, freqs, float(meta['Center Frequency (Hz)']), args.sigma, deg=args.deg, n_sub=args.n_sub, cleaning_method=CLEANING_ROUTINES.get(CLEANING_ROUTINE))
            powers = powers[:, ~mask]
        elif not BRUTE_FORCE_CLEAN:
            powers, _ = cleanData(powers, freqs, float(meta['Center Frequency (Hz)']), args.sigma, deg=args.deg, n_sub=args.n_sub, cleaning_method=CLEANING_ROUTINES.get(CLEANING_ROUTINE))

    if args.sub:
        powers = subtractBaseline(powers, freqs, float(meta['Center Frequency (Hz)']), args.sigma, args.deg, args.n_sub)

    if args.bin:
        powers, freqs = binData(powers, freqs, n=args.bin_factor)

    # --- Plotting ---

    if args.plot_noise:
        plotNoiseVsTimeAndMeasurement(powers, freqs, meta, args.sigma, args.save_fig)
    
    if args.plot_signal:
        plotSignal(powers, freqs, meta['Experiment Description'], args.sigma, float(meta['Center Frequency (Hz)']), meta['initial_CO_concentration (ppm)'], args.signal_sum, args.save_fig)
    
    if args.plot_signal or args.plot_noise or args.plot_baseline:
        out_dir = Path(r"Codebase\Analysis\Figure Dump")
        out_dir.mkdir(parents=True, exist_ok=True)
        info_file = out_dir / "Analysis_Run_Info.txt"

        lines = []
        lines.append(f"Run Timestamp: {datetime.now().isoformat(timespec='seconds')}")
        lines.append(f"Data Path: {args.path}")
        lines.append("")
        lines.append("[Arguments]")
        for key, value in sorted(vars(args).items()):
            lines.append(f"{key}: {value}")

        lines.append("")
        lines.append("[Testing Settings]")
        lines.append(f"SIM_DATA: {SIM_DATA}")
        if SIM_DATA:
            lines.append(f"SIM_SIGNAL: {locals().get('SIM_SIGNAL', 'N/A')}")

        lines.append(f"OFFSET_CENTER: {OFFSET_CENTER}")
        if OFFSET_CENTER:
            lines.append(f"offset_MHz: {locals().get('offset', 'N/A')}")
            lines.append(f"center_freq_Hz_after_offset: {meta.get('Center Frequency (Hz)', 'N/A')}")

        lines.append(f"TRUNCATE_SIGNAL: {TRUNCATE_SIGNAL}")
        if TRUNCATE_SIGNAL:
            lines.append(f"truncate_end_index: {locals().get('n', 'N/A')}")
        
        lines.append(f"BRUTE_FORCE_CLEAN: {BRUTE_FORCE_CLEAN}")
        if BRUTE_FORCE_CLEAN:
            BFC_factor = locals().get('cleaning_itterations', 'N/A')
            lines.append(f"cleaning_itterations: {BFC_factor if BFC_factor > 0 else 'Until 0% Rejection Rate'}")

        lines.append(f"INTERPOLATE_PRESSURES: {INTERPOLATE_PRESSURES}")

        lines.append(f"GRAPH_REJECTS: {GRAPH_REJECTS}")

        lines.append("")
        lines.append("[Resolved Processing Settings]")
        lines.append(f"baseline_subtraction_enabled: {args.sub}")
        if args.sub:
            lines.append(f"sub_deg: {args.deg}")
            lines.append(f"sub_n_sub: {args.n_sub}")
            lines.append(f"sub_sigma: {args.sigma}")

        lines.append(f"binning_enabled: {args.bin}")
        if args.bin:
            lines.append(f"bin_factor: {args.bin_factor}")

        lines.append(f"cleaning_enabled: {args.clean}")
        if args.clean:
            lines.append(f"clean_deg: {args.deg}")
            lines.append(f"clean_n_sub: {args.n_sub}")
            lines.append(f"clean_sigma: {args.sigma}")
            lines.append(f"cleaning_method: {CLEANING_ROUTINES.get(CLEANING_ROUTINE)}")
        lines.append("")
        lines.append("[Data Summary]")
        lines.append(f"powers_shape: {powers.shape}")
        lines.append(f"freqs_shape: {freqs.shape}")
        lines.append(f"n_pressures: {len(pressures) if hasattr(pressures, '__len__') else 'N/A'}")
        lines.append(f"center_frequency_Hz: {meta.get('Center Frequency (Hz)', 'N/A')}")
        lines.append(f"experiment_description: {meta.get('Experiment Description', 'N/A')}")

        info_file.write_text("\n".join(lines), encoding="utf-8")